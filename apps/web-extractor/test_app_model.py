import unittest

from app_model import (
    AppValidationError,
    ExtractionOptions,
    YouTubeExtractionOptions,
    build_crawler_command,
    build_youtube_command,
)


class AppModelTests(unittest.TestCase):
    def test_builds_whole_book_command(self):
        options = ExtractionOptions(
            url="https://books.example/title/",
            name="Book Name",
            output_dir="outputs/book-name",
            start_chapter=5,
            end_chapter=8,
        )

        command = build_crawler_command(options, "python", "crawler.py")

        self.assertEqual(command[:3], ["python", "crawler.py", "https://books.example/title/"])
        self.assertIn("--wait-for-user", command)
        self.assertEqual(command[command.index("--start-chapter") + 1], "5")
        self.assertEqual(command[command.index("--batch-chapters") + 1], "8")
        self.assertEqual(command[command.index("--name") + 1], "Book Name - Chapter")
        self.assertEqual(options.expected_outputs, 4)

    def test_builds_single_page_requests_command(self):
        options = ExtractionOptions(
            url="https://example.com/chapter",
            name="Chapter notes",
            output_dir="outputs",
            whole_book=False,
            playwright=False,
            headed=False,
            wait_for_user=False,
            delay=0,
        )

        command = build_crawler_command(options, "python", "crawler.py")

        self.assertNotIn("--playwright", command)
        self.assertNotIn("--batch-chapters", command)
        self.assertEqual(command[command.index("--name") + 1], "Chapter notes")
        self.assertEqual(options.expected_outputs, 1)

    def test_builds_snapshot_html_command_without_embedded_images(self):
        options = ExtractionOptions(
            url="https://example.com/article",
            name="Visual archive",
            output_dir="outputs",
            output_format="html",
            html_mode="snapshot",
            embed_images=False,
            whole_book=False,
            playwright=True,
            headed=False,
            wait_for_user=False,
        )

        command = build_crawler_command(options, "python", "crawler.py")

        self.assertEqual(command[command.index("--format") + 1], "html")
        self.assertEqual(command[command.index("--html-mode") + 1], "snapshot")
        self.assertIn("--no-embed-images", command)

    def test_rejects_invalid_url(self):
        with self.assertRaises(AppValidationError):
            ExtractionOptions("file:///notes", "Book", "outputs").validated()

    def test_rejects_backwards_chapter_range(self):
        with self.assertRaises(AppValidationError):
            ExtractionOptions(
                "https://books.example/title/",
                "Book",
                "outputs",
                start_chapter=8,
                end_chapter=5,
            ).validated()

    def test_manual_verification_requires_visible_playwright(self):
        with self.assertRaises(AppValidationError):
            ExtractionOptions(
                "https://example.com",
                "Page",
                "outputs",
                whole_book=False,
                playwright=True,
                headed=False,
                wait_for_user=True,
            ).validated()

    def test_builds_youtube_transcript_command(self):
        options = YouTubeExtractionOptions(
            url="https://youtu.be/dQw4w9WgXcQ",
            name="Lesson 1",
            output_dir="outputs/youtube",
            languages=("am", "en"),
            translate_to="en",
            strict_language=True,
            output_format="markdown",
        )

        command = build_youtube_command(options, "python", "youtube_extractor.py")

        self.assertEqual(command[:3], ["python", "youtube_extractor.py", options.url])
        self.assertEqual(command[command.index("--output-dir") + 1], "outputs/youtube")
        self.assertEqual(command[command.index("--name") + 1], "Lesson 1")
        self.assertEqual(command[command.index("--format") + 1], "markdown")
        self.assertEqual(command.count("--language"), 2)
        self.assertIn("--strict-language", command)

    def test_youtube_uses_detected_title_and_playlist_limit(self):
        options = YouTubeExtractionOptions(
            url="https://youtube.com/playlist?list=demo",
            name="",
            output_dir="outputs/youtube",
            playlist=True,
            max_videos=12,
        )

        command = build_youtube_command(options, "python", "youtube_extractor.py")

        self.assertNotIn("--name", command)
        self.assertEqual(command[command.index("--max-videos") + 1], "12")
        self.assertEqual(options.expected_outputs, 12)

    def test_builds_bounded_site_crawl_command_with_auto_names(self):
        options = ExtractionOptions(
            url="https://example.com",
            name="",
            output_dir="outputs/sites",
            whole_book=False,
            playwright=False,
            headed=False,
            wait_for_user=False,
            crawl_site=True,
            max_pages=20,
        )

        command = build_crawler_command(options, "python", "crawler.py")

        self.assertIn("--auto-name", command)
        self.assertIn("--crawl-site", command)
        self.assertEqual(command[command.index("--max-pages") + 1], "20")
        self.assertEqual(options.expected_outputs, 20)

    def test_youtube_name_rejects_folder_separator(self):
        with self.assertRaises(AppValidationError):
            YouTubeExtractionOptions(
                url="dQw4w9WgXcQ",
                name="course/lesson",
                output_dir="outputs/youtube",
            ).validated()

    def test_youtube_rejects_html_output(self):
        with self.assertRaises(AppValidationError):
            YouTubeExtractionOptions(
                url="dQw4w9WgXcQ",
                name="Lesson",
                output_dir="outputs/youtube",
                output_format="html",
            ).validated()


if __name__ == "__main__":
    unittest.main()
