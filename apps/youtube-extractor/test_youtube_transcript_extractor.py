import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from youtube_transcript_extractor import (
    extract_video_id,
    list_playlist_entries,
    render_transcript,
    sanitize_filename,
    write_transcript_atomic,
)


class YouTubeTranscriptExtractorTests(unittest.TestCase):
    def test_extracts_supported_youtube_urls(self):
        video_id = "dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(video_id), video_id)
        self.assertEqual(extract_video_id(f"https://youtu.be/{video_id}"), video_id)
        self.assertEqual(
            extract_video_id(f"https://www.youtube.com/watch?v={video_id}"),
            video_id,
        )

    def test_sanitizes_transcript_filename(self):
        self.assertEqual(sanitize_filename(' Lecture: "One" '), "Lecture_ _One_.txt")
        self.assertEqual(sanitize_filename("Lecture.txt", "markdown"), "Lecture.md")

    def test_atomic_writer_protects_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "transcript.txt"
            write_transcript_atomic(["first"], output)

            with self.assertRaises(FileExistsError):
                write_transcript_atomic(["second"], output)

            self.assertEqual(output.read_text(encoding="utf-8"), "first\n")

    def test_renders_markdown_and_json_transcripts(self):
        data = {
            "title": "Lesson",
            "source_url": "https://youtube.com/watch?v=demo",
            "language": "English",
            "captions": [{"text": "Hello world", "start": 0.0, "duration": 1.0}],
        }

        self.assertIn("# Lesson", render_transcript(data, "markdown"))
        self.assertIn('"captions"', render_transcript(data, "json"))

    def test_playlist_listing_is_bounded(self):
        class FakeDownloader:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download=False):
                self.assert_download = download
                return {
                    "entries": [
                        {"id": "dQw4w9WgXcQ", "title": "One"},
                        {"id": "9bZkp7q19f0", "title": "Two"},
                    ]
                }

        fake_module = SimpleNamespace(YoutubeDL=FakeDownloader)
        with patch.dict("sys.modules", {"yt_dlp": fake_module}):
            entries = list_playlist_entries("https://youtube.com/playlist?list=demo", 1)

        self.assertEqual(entries, [{"id": "dQw4w9WgXcQ", "title": "One"}])


if __name__ == "__main__":
    unittest.main()
