import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from reader_capture import CaptureError, Reader, ReaderConfig, capture


# A label changes immediately, but the canvas changes later. This reproduces
# the failure that otherwise saves the previous image with the new label.
FIXTURE = """<!doctype html><html><body>
<input id="label" value="iv"><div id="loading" hidden>Loading</div>
<canvas id="content" width="360" height="480"></canvas>
<button id="next" onclick="advance()">Next</button>
<script>
let n=0; const labels=['iv','1','2'];
const canvas=document.querySelector('canvas'); const ctx=canvas.getContext('2d');
function draw(){ctx.fillStyle=['#eee','#ddd','#ccc'][n];ctx.fillRect(0,0,360,480);
ctx.fillStyle='#111';ctx.font='30px Arial';ctx.fillText('Book page '+labels[n],25,60);}
function advance(){n++;document.querySelector('#label').value=labels[n];
document.querySelector('#loading').hidden=false;
setTimeout(()=>{draw();document.querySelector('#loading').hidden=true;
document.querySelector('#next').disabled=n===2;},350);}
draw();
</script></body></html>"""


class BrowserCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_content(FIXTURE)
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "capture"
        self.config = ReaderConfig("#content", "#next", "#label", "#loading")

    def tearDown(self):
        self.context.close()
        self.temp.cleanup()

    def run_capture(self, **kwargs):
        return capture(Reader(self.page, self.config, 3), self.folder, settle=.2, **kwargs)

    def test_delayed_canvas_numbering_and_end(self):
        result = self.run_capture()
        self.assertEqual(result["status"], "complete")
        self.assertEqual([p["displayed_label"] for p in result["pages"]], ["iv", "1", "2"])
        self.assertEqual(len({p["sha256"] for p in result["pages"]}), 3)
        for row in result["pages"]:
            data = (self.folder / row["file"]).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG"))
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
        self.assertIn("page-iv.png", (self.folder / "index.html").read_text())

    def test_optional_limit_does_not_click_next(self):
        result = self.run_capture(max_pages=1)
        self.assertEqual(result["status"], "page_limit")
        self.assertEqual(self.page.locator("#label").input_value(), "iv")

    def test_transparent_loading_indicator_is_not_busy(self):
        self.page.locator("#loading").evaluate("el => {el.hidden=false; el.style.opacity='0';}")
        self.assertEqual(self.run_capture(max_pages=1)["status"], "page_limit")

    def test_stale_canvas_does_not_get_new_label(self):
        self.page.locator("#next").evaluate("el => el.onclick = () => document.querySelector('#label').value = '1'")
        with self.assertRaises(CaptureError):
            self.run_capture()
        manifest = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(len(manifest["pages"]), 1)

    def test_missing_controls_is_failure_not_completion(self):
        self.page.locator("#next").evaluate("el => el.onclick = () => {advance(); el.remove();}")
        with self.assertRaises(CaptureError):
            self.run_capture()
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["status"], "failed")

    def test_repeated_page_loop_stops(self):
        self.page.evaluate("advance = () => {n = n === 0 ? 1 : 0; document.querySelector('#label').value=labels[n];draw();}")
        with self.assertRaisesRegex(CaptureError, "previously captured"):
            self.run_capture()
        self.assertEqual(len(list(self.folder.glob("*.png"))), 2)

    def test_existing_destination_is_never_overwritten(self):
        self.folder.mkdir()
        marker = self.folder / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.run_capture()
        self.assertEqual(marker.read_text(), "keep")

    def test_content_frame_with_outer_controls(self):
        self.page.set_content('<input id="label" value="7"><button id="next" aria-disabled="true">Next</button><iframe id="book" srcdoc="<div id=content>Framed book page</div>"></iframe>')
        self.config = ReaderConfig("#content", "#next", "#label", content_frame_selector="#book")
        result = self.run_capture()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["pages"][0]["displayed_label"], "7")

    def test_ambiguous_selector_rejected(self):
        self.config = ReaderConfig("#content", "input, button", "#label")
        with self.assertRaisesRegex(CaptureError, "exactly one"):
            self.run_capture()

    def test_gallery_escapes_labels_and_paths(self):
        self.page.locator("#label").fill('../../<script>alert(1)</script>')
        result = self.run_capture(max_pages=1)
        self.assertNotIn("/", result["pages"][0]["file"])
        self.assertNotIn("<script>", (self.folder / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
