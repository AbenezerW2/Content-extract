import tempfile
import unittest
from pathlib import Path

from history_store import HistoryStore


class HistoryStoreTests(unittest.TestCase):
    def test_records_and_filters_history_by_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.json")
            store.record(mode="page", source="https://example.com", path="page.md")
            store.record(mode="youtube", source="video-id", path="video.txt")

            page_history = store.list("page")

            self.assertEqual(len(page_history), 1)
            self.assertEqual(page_history[0]["label"], "page")

    def test_latest_duplicate_path_replaces_older_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.json")
            store.record(mode="page", source="old", path="page.md")
            store.record(mode="page", source="new", path="page.md")

            history = store.list("page")

            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["source"], "new")


if __name__ == "__main__":
    unittest.main()
