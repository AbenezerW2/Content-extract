import tempfile
import unittest
from pathlib import Path

from youtube_transcript_extractor import (
    extract_video_id,
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

    def test_atomic_writer_protects_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "transcript.txt"
            write_transcript_atomic(["first"], output)

            with self.assertRaises(FileExistsError):
                write_transcript_atomic(["second"], output)

            self.assertEqual(output.read_text(encoding="utf-8"), "first\n")


if __name__ == "__main__":
    unittest.main()
