import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import DesktopBridge, KORTEXT_PATH, run_worker
from history_store import HistoryStore


class KortextBridgeTests(unittest.TestCase):
    def test_fresh_output_subfolder_and_page_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {'url': 'https://app.kortext.com', 'output_dir': directory,
                       'name': '../Book / one', 'max_pages': 0}
            command = DesktopBridge._kortext_command(payload)
            destination = Path(command[command.index('--output') + 1])
            self.assertEqual(destination.parent, Path(directory).resolve())
            self.assertFalse(destination.exists())
            self.assertEqual(command[-2:], ['--max-pages', '0'])
            self.assertEqual(Path(command[command.index('--config') + 1]).name, 'kortext-pdf.json')
            self.assertNotEqual(command, DesktopBridge._kortext_command(payload))

    def test_rejects_invalid_reader_inputs(self):
        for payload in ({'url': 'file:///tmp/book'}, {'url': 'https://user:pass@example.com'},
                        {'url': 'https://app.kortext.com', 'max_pages': -1}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                DesktopBridge._kortext_command(payload)

    def test_ready_capture_and_gallery_events(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = DesktopBridge()
            bridge._history = HistoryStore(Path(directory) / 'history.json')
            process = Mock()
            process.stdout = io.StringIO('Reader ready: sign in\nSaved capture 1: iv\nSaved: /tmp/book/index.html\n')
            process.wait.return_value = 0
            bridge._read_process(process, {'mode': 'kortext', 'source': 'https://app.kortext.com', 'label': 'Book'})
            types = [event['type'] for event in bridge.get_status()['events']]
            self.assertIn('verification', types)
            self.assertEqual(types.count('captured'), 1)
            self.assertEqual(types[-1], 'finished')
            self.assertEqual(bridge.get_history('kortext')[0]['path'], '/tmp/book/index.html')

    def test_packaged_worker_dispatch(self):
        with patch('app.runpy.run_path') as run, patch('app.sys.argv', []):
            self.assertEqual(run_worker('kortext', ['--help']), 0)
        run.assert_called_once_with(str(KORTEXT_PATH), run_name='__main__')
