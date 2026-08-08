#!/usr/bin/env python3
"""Download available YouTube captions as text, Markdown, or JSON."""

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
OUTPUT_EXTENSIONS = {"text": ".txt", "markdown": ".md", "json": ".json"}
MAX_PLAYLIST_VIDEOS = 30


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


def write_text_atomic(content: str, output_file: Path, *, overwrite: bool = False) -> None:
    """Write complete UTF-8 content without leaving a partial file."""
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
            temp_file.write(content)
            if content and not content.endswith("\n"):
                temp_file.write("\n")

        # Refuse to replace a file created while the transcript was downloading.
        if output_file.exists() and not overwrite:
            raise FileExistsError(f"Output file already exists: {output_file}")
        os.replace(temp_name, output_file)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def write_transcript_atomic(
    lines: list[str], output_file: Path, *, overwrite: bool = False
) -> None:
    """Backward-compatible plain-text transcript writer."""
    write_text_atomic("\n".join(lines), output_file, overwrite=overwrite)


def sanitize_filename(name: str, output_format: str = "text") -> str:
    """Turn a user-provided label into a safe local filename."""
    if output_format not in OUTPUT_EXTENSIONS:
        raise ValueError(f"Unsupported output format: {output_format}")
    clean_name = INVALID_FILENAME_CHARS_RE.sub("_", name.strip())
    clean_name = clean_name.lstrip(" ._").rstrip(" .") or "transcript"
    for extension in OUTPUT_EXTENSIONS.values():
        if clean_name.lower().endswith(extension):
            clean_name = clean_name[: -len(extension)]
            break
    return f"{clean_name}{OUTPUT_EXTENSIONS[output_format]}"


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


def list_playlist_entries(playlist_url: str, max_videos: int) -> list[dict[str, str]]:
    """Return a bounded list of video IDs and titles without downloading media."""
    if not 1 <= max_videos <= MAX_PLAYLIST_VIDEOS:
        raise ValueError(f"Playlist limit must be between 1 and {MAX_PLAYLIST_VIDEOS}")
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError("Playlist support requires yt-dlp; install requirements.txt") from exc

    options = {
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "playlistend": max_videos,
        "quiet": True,
        "skip_download": True,
    }
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(playlist_url, download=False)
    entries = info.get("entries", []) if isinstance(info, dict) else []
    videos: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = entry.get("id")
        if not isinstance(video_id, str) or not VIDEO_ID_RE.fullmatch(video_id):
            continue
        title = entry.get("title")
        videos.append(
            {
                "id": video_id,
                "title": title.strip() if isinstance(title, str) and title.strip() else video_id,
            }
        )
        if len(videos) >= max_videos:
            break
    if not videos:
        raise RuntimeError("No public videos were found in that playlist")
    return videos


def transcript_data(transcript, video_id: str, title: str | None) -> dict:
    """Build a serializable transcript document with timestamps and metadata."""
    captions = [
        {
            "text": snippet.text.replace("\n", " ").strip(),
            "start": float(getattr(snippet, "start", 0)),
            "duration": float(getattr(snippet, "duration", 0)),
        }
        for snippet in transcript
        if snippet.text.replace("\n", " ").strip()
    ]
    return {
        "title": title or video_id,
        "video_id": video_id,
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
        "language": getattr(transcript, "language", None),
        "language_code": getattr(transcript, "language_code", None),
        "is_generated": bool(getattr(transcript, "is_generated", False)),
        "captions": captions,
    }


def render_transcript(data: dict, output_format: str) -> str:
    """Render a transcript document in text, Markdown, or JSON."""
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    caption_text = "\n".join(item["text"] for item in data["captions"])
    if output_format == "markdown":
        return (
            f"# {data['title']}\n\n"
            f"Source: {data['source_url']}\n\n"
            f"Language: {data.get('language') or 'unknown'}\n\n"
            f"{caption_text}\n"
        )
    if output_format == "text":
        return caption_text + "\n"
    raise ValueError(f"Unsupported output format: {output_format}")


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
    output_format: str = "text",
    title: str | None = None,
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
        data = transcript_data(transcript, video_id, title)
        if not data["captions"]:
            print("Error: YouTube returned an empty transcript.", file=sys.stderr)
            return False

        write_text_atomic(
            render_transcript(data, output_format),
            Path(output_file),
            overwrite=overwrite,
        )
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
            f"saved: {Path(output_file).resolve()}\n"
            f"Transcript saved ({output_format}) "
            f"({transcript.language}, {caption_type} captions)."
        )
        return True

    return False


def next_day_file(directory: Path, output_format: str = "text") -> Path:
    """Find the first unused dayN.txt filename in a directory."""
    day = 1
    extension = OUTPUT_EXTENSIONS[output_format]
    while (directory / f"day{day}{extension}").exists():
        day += 1
    return directory / f"day{day}{extension}"


def interactive_mode(
    languages: list[str],
    output_dir: Path,
    translate_to: str | None,
    allow_any_language: bool,
    output_format: str,
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
            output_dir / sanitize_filename(title, output_format)
            if title
            else next_day_file(output_dir, output_format)
        )
        label = input(
            f"Filename [{suggested_file.name}] "
            "(press Enter to use it, or type another name): "
        ).strip()
        output_file = output_dir / sanitize_filename(label, output_format) if label else suggested_file
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
            output_format=output_format,
            title=title,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", nargs="?", help="YouTube URL or video ID")
    parser.add_argument("-o", "--output", type=Path, help="exact output file for one video")
    parser.add_argument("-n", "--name", help="optional custom filename; the video title is the default")
    parser.add_argument(
        "--format",
        choices=tuple(OUTPUT_EXTENSIONS),
        default="text",
        help="Output format: text, markdown, or json (default: text)",
    )
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
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Extract each public video in a YouTube playlist",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=MAX_PLAYLIST_VIDEOS,
        help=f"Maximum playlist videos (1–{MAX_PLAYLIST_VIDEOS}; default: {MAX_PLAYLIST_VIDEOS})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_videos <= MAX_PLAYLIST_VIDEOS:
        print(
            f"Error: --max-videos must be between 1 and {MAX_PLAYLIST_VIDEOS}.",
            file=sys.stderr,
        )
        return 2
    if args.playlist and args.output:
        print("Error: --output cannot represent multiple playlist files.", file=sys.stderr)
        return 2
    languages = args.languages or ["en", "en-US", "en-GB"]
    if not args.video:
        if args.playlist:
            print("Error: --playlist requires a playlist URL.", file=sys.stderr)
            return 2
        return interactive_mode(
            languages,
            args.output_dir,
            args.translate,
            not args.strict_language,
            args.format,
        )

    try:
        proxy_config = build_proxy_config()
    except ValueError as error:
        print(f"Error configuring the transcript tool: {error}", file=sys.stderr)
        return 1
    proxies = proxy_config.to_requests_dict() if proxy_config else None
    api = build_api(proxy_config)

    if args.playlist:
        try:
            entries = list_playlist_entries(args.video, args.max_videos)
            args.output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Error reading playlist: {error}", file=sys.stderr)
            return 1
        completed = 0
        failed = 0
        for index, entry in enumerate(entries, start=1):
            title = entry["title"]
            label = f"{args.name} - {index:02d} - {title}" if args.name else title
            output_file = args.output_dir / sanitize_filename(label, args.format)
            if output_file.exists() and not args.overwrite:
                output_file = unique_path(output_file)
            print(f"Playlist item {index}/{len(entries)}: {title}")
            success = get_youtube_transcript(
                entry["id"],
                output_file,
                languages,
                translate_to=args.translate,
                allow_any_language=not args.strict_language,
                api=api,
                overwrite=args.overwrite,
                output_format=args.format,
                title=title,
            )
            completed += int(success)
            failed += int(not success)
        print(f"completed: {completed} playlist transcripts; failed: {failed}")
        return 0 if completed else 1

    video_id = extract_video_id(args.video)
    if not video_id:
        print("Error: enter a valid YouTube URL or 11-character video ID.", file=sys.stderr)
        return 1
    title = fetch_video_title(video_id, proxies=proxies)
    if args.output:
        output_file = args.output
    elif args.name:
        output_file = args.output_dir / sanitize_filename(args.name, args.format)
    else:
        output_file = (
            args.output_dir / sanitize_filename(title, args.format)
            if title
            else next_day_file(args.output_dir, args.format)
        )
        if output_file.exists() and not args.overwrite:
            output_file = unique_path(output_file)
    return (
        0
        if get_youtube_transcript(
            args.video,
            output_file,
            languages,
            translate_to=args.translate,
            allow_any_language=not args.strict_language,
            api=api,
            overwrite=args.overwrite,
            output_format=args.format,
            title=title,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
