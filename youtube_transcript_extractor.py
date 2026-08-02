#!/usr/bin/env python3
"""Download available YouTube captions as plain text."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse


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


def write_transcript_atomic(lines: list[str], output_file: Path) -> None:
    """Write a complete UTF-8 transcript without leaving a partial file."""
    output_file = output_file.expanduser()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
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
        if output_file.exists():
            raise FileExistsError(f"Output file already exists: {output_file}")
        os.replace(temp_name, output_file)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def sanitize_filename(name: str) -> str:
    """Turn a user-provided label into a safe local text filename."""
    clean_name = INVALID_FILENAME_CHARS_RE.sub("_", Path(name.strip()).name)
    clean_name = clean_name.strip(" .") or "transcript"
    return clean_name if clean_name.lower().endswith(".txt") else f"{clean_name}.txt"


def build_api():
    """Build an API client, optionally using proxy credentials from the environment."""
    from youtube_transcript_api import YouTubeTranscriptApi

    username = os.environ.get("WEBSHARE_PROXY_USERNAME")
    password = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if bool(username) != bool(password):
        raise ValueError(
            "Set both WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD, or neither."
        )
    if username and password:
        from youtube_transcript_api.proxies import WebshareProxyConfig

        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=username,
                proxy_password=password,
            )
        )
    return YouTubeTranscriptApi()


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

        write_transcript_atomic(lines, Path(output_file))
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
        api = build_api()
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        print(f"Error configuring the transcript tool: {error}", file=sys.stderr)
        return 1

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

        label = input("Filename (press Enter for the next day number): ").strip()
        output_file = (
            output_dir / sanitize_filename(label)
            if label
            else next_day_file(output_dir)
        )
        get_youtube_transcript(
            value,
            output_file,
            languages,
            translate_to=translate_to,
            allow_any_language=allow_any_language,
            api=api,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", nargs="?", help="YouTube URL or video ID")
    parser.add_argument("-o", "--output", type=Path, help="output text file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("transcripts"),
        help="interactive/default output directory (default: ./transcripts)",
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

    output_file = args.output or next_day_file(args.output_dir)
    return (
        0
        if get_youtube_transcript(
            args.video,
            output_file,
            languages,
            translate_to=args.translate,
            allow_any_language=not args.strict_language,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
