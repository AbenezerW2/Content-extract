from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


WEB_OUTPUT_FORMATS = ("markdown", "json", "text", "html")
TRANSCRIPT_OUTPUT_FORMATS = ("markdown", "json", "text")
HTML_MODES = ("clean", "snapshot")
DEFAULT_YOUTUBE_LANGUAGES = ("en", "en-US", "en-GB")


class AppValidationError(ValueError):
    """Raised when desktop-app form values cannot produce a safe command."""


@dataclass(frozen=True)
class ExtractionOptions:
    url: str
    name: str
    output_dir: str
    output_format: str = "markdown"
    html_mode: str = "clean"
    embed_images: bool = True
    whole_book: bool = True
    start_chapter: int = 1
    end_chapter: int = 1
    playwright: bool = True
    headed: bool = True
    wait_for_user: bool = True
    delay: float = 1
    overwrite: bool = False
    crawl_site: bool = False
    max_pages: int = 30

    def validated(self) -> "ExtractionOptions":
        url = self.url.strip()
        name = self.name.strip()
        output_dir = self.output_dir.strip()
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AppValidationError("Enter a complete public http:// or https:// URL.")
        if self.whole_book and not name:
            raise AppValidationError("Enter a book name or output name.")
        if not output_dir:
            raise AppValidationError("Choose an output folder.")
        if self.output_format not in WEB_OUTPUT_FORMATS:
            raise AppValidationError("Choose Markdown, JSON, text, or HTML output.")
        if self.html_mode not in HTML_MODES:
            raise AppValidationError("Choose clean or snapshot HTML mode.")
        if self.delay < 0:
            raise AppValidationError("Delay cannot be negative.")
        if self.crawl_site and not 1 <= self.max_pages <= 30:
            raise AppValidationError("Whole-site extraction must be limited to 1–30 pages.")
        if self.wait_for_user and not (self.playwright and self.headed):
            raise AppValidationError("Manual verification requires Playwright and a visible browser.")
        if self.headed and not self.playwright:
            raise AppValidationError("A visible browser requires Playwright.")
        if self.whole_book:
            if not self.playwright:
                raise AppValidationError("Whole-book extraction requires Playwright.")
            if self.start_chapter < 1 or self.end_chapter < self.start_chapter:
                raise AppValidationError("The ending chapter must be at or after the starting chapter.")

        return ExtractionOptions(
            url=url,
            name=name,
            output_dir=output_dir,
            output_format=self.output_format,
            html_mode=self.html_mode,
            embed_images=self.embed_images,
            whole_book=self.whole_book,
            start_chapter=self.start_chapter,
            end_chapter=self.end_chapter,
            playwright=self.playwright,
            headed=self.headed,
            wait_for_user=self.wait_for_user,
            delay=self.delay,
            overwrite=self.overwrite,
            crawl_site=self.crawl_site,
            max_pages=self.max_pages,
        )

    @property
    def expected_outputs(self) -> int:
        if self.whole_book:
            return self.end_chapter - self.start_chapter + 1
        if self.crawl_site:
            return self.max_pages
        return 1


@dataclass(frozen=True)
class YouTubeExtractionOptions:
    url: str
    name: str
    output_dir: str
    languages: tuple[str, ...] = DEFAULT_YOUTUBE_LANGUAGES
    translate_to: str = ""
    strict_language: bool = False
    overwrite: bool = False
    output_format: str = "text"
    playlist: bool = False
    max_videos: int = 30

    def validated(self) -> "YouTubeExtractionOptions":
        url = self.url.strip()
        name = self.name.strip()
        output_dir = self.output_dir.strip()
        languages = tuple(language.strip() for language in self.languages if language.strip())

        if not url:
            raise AppValidationError("Enter a YouTube URL or video ID.")
        if name and (Path(name).name != name or name in {".", ".."}):
            raise AppValidationError("Transcript name cannot contain folder separators.")
        if not output_dir:
            raise AppValidationError("Choose an output folder.")
        if not languages:
            raise AppValidationError("Enter at least one preferred caption language.")
        if self.output_format not in TRANSCRIPT_OUTPUT_FORMATS:
            raise AppValidationError("Choose Markdown, JSON, or text output.")
        if self.playlist and not 1 <= self.max_videos <= 30:
            raise AppValidationError("Playlist extraction must be limited to 1–30 videos.")

        return YouTubeExtractionOptions(
            url=url,
            name=name,
            output_dir=output_dir,
            languages=languages,
            translate_to=self.translate_to.strip(),
            strict_language=self.strict_language,
            overwrite=self.overwrite,
            output_format=self.output_format,
            playlist=self.playlist,
            max_videos=self.max_videos,
        )

    @property
    def expected_outputs(self) -> int:
        return self.max_videos if self.playlist else 1


def build_crawler_command(
    options: ExtractionOptions,
    python_executable: str,
    crawler_path: str | Path,
) -> list[str]:
    options = options.validated()
    command = [python_executable, str(crawler_path), options.url]

    if options.playwright:
        command.append("--playwright")
    if options.headed:
        command.append("--headed")
    if options.wait_for_user:
        command.append("--wait-for-user")
    if options.whole_book:
        command.extend(
            [
                "--start-chapter",
                str(options.start_chapter),
                "--batch-chapters",
                str(options.end_chapter),
                "--name",
                f"{options.name} - Chapter",
            ]
        )
    elif options.name:
        command.extend(["--name", options.name])
    else:
        command.append("--auto-name")
    if options.crawl_site:
        command.extend(["--crawl-site", "--max-pages", str(options.max_pages)])

    command.extend(
        [
            "--format",
            options.output_format,
            "--output-dir",
            options.output_dir,
            "--delay",
            f"{options.delay:g}",
        ]
    )
    if options.overwrite:
        command.append("--overwrite")
    if options.output_format == "html":
        command.extend(["--html-mode", options.html_mode])
        if not options.embed_images:
            command.append("--no-embed-images")
    return command


def build_youtube_command(
    options: YouTubeExtractionOptions,
    python_executable: str,
    extractor_path: str | Path,
) -> list[str]:
    options = options.validated()
    command = [
        python_executable,
        str(extractor_path),
        options.url,
        "--output-dir",
        options.output_dir,
        "--format",
        options.output_format,
    ]
    if options.name:
        command.extend(["--name", options.name])
    if options.playlist:
        command.extend(["--playlist", "--max-videos", str(options.max_videos)])
    for language in options.languages:
        command.extend(["--language", language])
    if options.translate_to:
        command.extend(["--translate", options.translate_to])
    if options.strict_language:
        command.append("--strict-language")
    if options.overwrite:
        command.append("--overwrite")
    return command
