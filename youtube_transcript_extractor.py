#!/usr/bin/env python3
"""Download available YouTube captions as plain text."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/*?:"<>|\x00-\x1f]')


def default_output_dir() -> Path:
    """Return a predictable user-owned folder for saved transcripts."""
    documents = Path.home() / "Documents"
    return (documents if documents.is_dir() else Path.home()) / "YouTube Transcripts"


def extract_video_id(value: str) -> str | None:
    """Return a video ID from a YouTube URL or a bare 11-character ID."""
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value

    candidate_url = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate_url)
    host = (parsed.hostname or "").lower()

    candidate: str | None = None
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif host in YOUTUBE_HOSTS:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
            candidate = parts[1]

    return candidate if candidate and VIDEO_ID_RE.fullmatch(candidate) else None


def write_transcript_atomic(
    lines: list[str], output_file: Path, *, overwrite: bool = False
) -> None:
    """Write a complete UTF-8 transcript without leaving a partial file."""
    output_file = output_file.expanduser()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_file}")

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_file.parent,
            prefix=f".{output_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write("\n".join(lines))
            temp_file.write("\n")

        # Refuse to replace a file created while the transcript was downloading.
        if output_file.exists() and not overwrite:
            raise FileExistsError(f"Output file already exists: {output_file}")
        os.replace(temp_name, output_file)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def sanitize_filename(name: str) -> str:
    """Turn a user-provided label into a safe local text filename."""
    clean_name = INVALID_FILENAME_CHARS_RE.sub("_", name.strip())
    clean_name = clean_name.lstrip(" ._").rstrip(" .") or "transcript"
    return clean_name if clean_name.lower().endswith(".txt") else f"{clean_name}.txt"


def fetch_video_title(
    video_id: str,
    timeout: float = 10.0,
    proxies: dict[str, str] | None = None,
) -> str | None:
    """Retrieve a public video's title through YouTube's oEmbed endpoint.

    Routed through the same proxy as the transcript API (when one is
    configured) so this request doesn't hit YouTube from an IP that's
    already being blocked, which was silently failing every lookup.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    if proxies:
        # Mirrors the transcript API's own handling for rotating proxies:
        # close the connection so the next request can land on a different IP.
        headers["Connection"] = "close"

    try:
        response = requests.get(
            "https://www.youtube.com/oembed",
            params={
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "format": "json",
            },
            headers=headers,
            proxies=proxies,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError, json.JSONDecodeError) as error:
        print(
            f"Warning: could not retrieve the video title "
            f"({type(error).__name__}: {error}). Using a numbered filename instead.",
            file=sys.stderr,
        )
        return None

    title = data.get("title")
    return title.strip() if isinstance(title, str) and title.strip() else None


def unique_path(path: Path) -> Path:
    """Return path or a numbered variant that does not already exist."""
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def choose_existing_file_action(path: Path) -> tuple[Path | None, bool]:
    """Ask whether to keep both files, overwrite, or cancel."""
    if not path.exists():
        return path, False

    while True:
        choice = input(
            f"'{path.name}' already exists. "
            "[K]eep both, [O]verwrite, or [C]ancel: "
        ).strip().lower()
        if choice in {"", "k", "keep", "keep both"}:
            return unique_path(path), False
        if choice in {"o", "overwrite"}:
            return path, True
        if choice in {"c", "cancel"}:
            return None, False
        print("Please enter K, O, or C.")


def build_proxy_config():
    """Build a WebshareProxyConfig from the environment, or None if unset."""
    username = os.environ.get("WEBSHARE_PROXY_USERNAME")
    password = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if bool(username) != bool(password):
        raise ValueError(
            "Set both WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD, or neither."
        )
    if username and password:
        from youtube_transcript_api.proxies import WebshareProxyConfig

        return WebshareProxyConfig(proxy_username=username, proxy_password=password)
    return None


def build_api(proxy_config=None):
    """Build an API client, using proxy_config if given, else reading one from the environment."""
    from youtube_transcript_api import YouTubeTranscriptApi

    if proxy_config is None:
        proxy_config = build_proxy_config()
    return YouTubeTranscriptApi(proxy_config=proxy_config)


def fetch_best_transcript(
    api,
    video_id: str,
    languages: list[str],
    translate_to: str | None,
    allow_any_language: bool,
):
    """Fetch preferred captions, then optionally translate or use another language."""
    from youtube_transcript_api import (
        NoTranscriptFound,
        NotTranslatable,
        TranslationLanguageNotAvailable,
    )

    transcript_list = api.list(video_id)
    try:
        return transcript_list.find_transcript(languages).fetch()
    except NoTranscriptFound:
        if not allow_any_language:
            raise

    available = list(transcript_list)
    if not available:
        raise NoTranscriptFound(video_id, languages, transcript_list)

    if translate_to:
        for transcript in available:
            if transcript.is_translatable:
                try:
                    return transcript.translate(translate_to).fetch()
                except (NotTranslatable, TranslationLanguageNotAvailable):
                    continue

    return available[0].fetch()


def get_youtube_transcript(
    video_url: str,
    output_file: str | Path = "transcript.txt",
    languages: list[str] | None = None,
    *,
    translate_to: str | None = None,
    allow_any_language: bool = True,
    api=None,
    overwrite: bool = False,
) -> bool:
    """Fetch captions and save them. Return True only after a successful save."""
    video_id = extract_video_id(video_url)
    if not video_id:
        print("Error: enter a valid YouTube URL or 11-character video ID.", file=sys.stderr)
        return False

    try:
        from youtube_transcript_api import (
            AgeRestricted,
            IpBlocked,
            NoTranscriptFound,
            RequestBlocked,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError:
        print(
            "Missing dependency. Install it with: "
            "python -m pip install youtube-transcript-api==1.2.4",
            file=sys.stderr,
        )
        return False

    print(f"Extracting transcript for video {video_id}...")
    try:
        api = api or build_api()
        transcript = fetch_best_transcript(
            api,
            video_id,
            languages or ["en", "en-US", "en-GB"],
            translate_to,
            allow_any_language,
        )
        lines = [snippet.text.replace("\n", " ").strip() for snippet in transcript]
        lines = [line for line in lines if line]
        if not lines:
            print("Error: YouTube returned an empty transcript.", file=sys.stderr)
            return False

        write_transcript_atomic(lines, Path(output_file), overwrite=overwrite)
    except TranscriptsDisabled:
        print("Error: captions are disabled for this video.", file=sys.stderr)
    except NoTranscriptFound:
        requested = ", ".join(languages or ["en"])
        print(f"Error: no transcript found for: {requested}.", file=sys.stderr)
    except VideoUnavailable:
        print("Error: the video is unavailable or private.", file=sys.stderr)
    except AgeRestricted:
        print("Error: the video is age-restricted.", file=sys.stderr)
    except (RequestBlocked, IpBlocked):
        print(
            "Error: YouTube blocked this request. Wait and retry from a normal "
            "residential connection; avoid rapid bulk requests.",
            file=sys.stderr,
        )
    except FileExistsError as error:
        print(f"Error: {error}", file=sys.stderr)
    except OSError as error:
        print(f"Error writing transcript: {error}", file=sys.stderr)
    except Exception as error:
        print(f"Error retrieving transcript: {error}", file=sys.stderr)
    else:
        caption_type = "automatic" if transcript.is_generated else "manual"
        print(
            f"Transcript saved to '{Path(output_file)}' "
            f"({transcript.language}, {caption_type} captions)."
        )
        return True

    return False


def next_day_file(directory: Path) -> Path:
    """Find the first unused dayN.txt filename in a directory."""
    day = 1
    while (directory / f"day{day}.txt").exists():
        day += 1
    return directory / f"day{day}.txt"


def interactive_mode(
    languages: list[str],
    output_dir: Path,
    translate_to: str | None,
    allow_any_language: bool,
) -> int:
    """Prompt for videos until the user enters 'stop'."""
    try:
        proxy_config = build_proxy_config()
        api = build_api(proxy_config)
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        print(f"Error configuring the transcript tool: {error}", file=sys.stderr)
        return 1
    proxies = proxy_config.to_requests_dict() if proxy_config else None

    print(f"Transcripts will be saved in: {output_dir.resolve()}")
    while True:
        try:
            value = input("Enter YouTube URL/ID (or 'stop' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return 0

        if value.lower() in {"stop", "quit", "exit"}:
            print("Goodbye!")
            return 0
        if not value:
            continue

        video_id = extract_video_id(value)
        if not video_id:
            print("Error: enter a valid YouTube URL or 11-character video ID.")
            continue

        print("Looking up the video title...")
        title = fetch_video_title(video_id, proxies=proxies)
        suggested_file = (
            output_dir / sanitize_filename(title)
            if title
            else next_day_file(output_dir)
        )
        label = input(
            f"Filename [{suggested_file.name}] "
            "(press Enter to use it, or type another name): "
        ).strip()
        output_file = output_dir / sanitize_filename(label) if label else suggested_file
        output_file, overwrite = choose_existing_file_action(output_file)
        if output_file is None:
            print("Cancelled; no transcript was downloaded.")
            continue

        get_youtube_transcript(
            value,
            output_file,
            languages,
            translate_to=translate_to,
            allow_any_language=allow_any_language,
            api=api,
            overwrite=overwrite,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", nargs="?", help="YouTube URL or video ID")
    parser.add_argument("-o", "--output", type=Path, help="output text file")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing output file (non-interactive mode only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="interactive/default output directory (default: ~/Documents/YouTube Transcripts)",
    )
    parser.add_argument(
        "-l",
        "--language",
        dest="languages",
        action="append",
        default=[],
        help="preferred language code; repeat for fallbacks (default: en, en-US, en-GB)",
    )
    parser.add_argument(
        "--translate",
        metavar="LANGUAGE",
        help="translate another available transcript when preferred languages are absent",
    )
    parser.add_argument(
        "--strict-language",
        action="store_true",
        help="fail instead of falling back to captions in another language",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    languages = args.languages or ["en", "en-US", "en-GB"]
    if not args.video:
        return interactive_mode(
            languages,
            args.output_dir,
            args.translate,
            not args.strict_language,
        )

    try:
        proxy_config = build_proxy_config()
    except ValueError as error:
        print(f"Error configuring the transcript tool: {error}", file=sys.stderr)
        return 1
    proxies = proxy_config.to_requests_dict() if proxy_config else None

    if args.output:
        output_file = args.output
    else:
        video_id = extract_video_id(args.video)
        title = fetch_video_title(video_id, proxies=proxies) if video_id else None
        output_file = (
            args.output_dir / sanitize_filename(title)
            if title
            else next_day_file(args.output_dir)
        )
    return (
        0
        if get_youtube_transcript(
            args.video,
            output_file,
            languages,
            translate_to=args.translate,
            allow_any_language=not args.strict_language,
            api=build_api(proxy_config),
            overwrite=args.overwrite,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())