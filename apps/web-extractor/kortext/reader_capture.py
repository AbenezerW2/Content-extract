#!/usr/bin/env python3
"""Capture a paginated browser reader using explicitly configured controls."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReaderConfig:
    content_selector: str
    next_selector: str
    page_label_selector: str
    loading_selector: str = ""
    content_frame_selector: str = ""
    controls_frame_selector: str = ""

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
        for key in ("content_selector", "next_selector", "page_label_selector"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} must not be empty")


def label_slug(label):
    return re.sub(r"[^\w-]+", "-", label, flags=re.UNICODE).strip("-")[:70] or "unlabelled"


def read_label(locator):
    # Readers often put the page number in an editable input, not a text node.
    value = locator.evaluate("el => 'value' in el ? String(el.value) : (el.innerText || el.textContent || '')")
    value = " ".join(value.split())
    if not value:
        raise CaptureError("The configured page label is empty.")
    return value


class Reader:
    def __init__(self, page, config, timeout):
        self.page = page
        self.timeout = timeout
        self.config = config
        content_root = page.frame_locator(config.content_frame_selector) if config.content_frame_selector else page
        controls_root = page.frame_locator(config.controls_frame_selector) if config.controls_frame_selector else page
        self.content = content_root.locator(config.content_selector)
        self.label = controls_root.locator(config.page_label_selector)
        self.next = controls_root.locator(config.next_selector)
        self.loading = controls_root.locator(config.loading_selector) if config.loading_selector else None

    def validate(self):
        for name, locator in (("content", self.content), ("page label", self.label), ("Next button", self.next)):
            if locator.count() != 1:
                raise CaptureError(f"The {name} selector must match exactly one element; found {locator.count()}.")
            locator.wait_for(state="visible", timeout=self.timeout * 1000)

    def is_loading(self):
        return self.loading is not None and any(item.is_visible() for item in self.loading.all())

    def snapshot(self):
        if self.is_loading():
            return None
        if not self.content.is_visible() or not self.label.is_visible():
            return None
        if not self.content.evaluate("el => Array.from(el.querySelectorAll('img')).concat(el.tagName === 'IMG' ? [el] : []).every(i => i.complete && i.naturalWidth > 0)"):
            return None
        before = read_label(self.label)
        png = self.content.screenshot(type="png", animations="disabled", caret="hide", timeout=self.timeout * 1000)
        if self.is_loading() or before != read_label(self.label):
            return None
        return before, hashlib.sha256(png).hexdigest(), png

    def stable_page(self, previous=None, settle=1.0):
        deadline = time.monotonic() + self.timeout
        candidate = None
        stable_since = time.monotonic()
        while time.monotonic() < deadline:
            sample = self.snapshot()
            # Both signals must advance. A changed label with stale artwork is
            # a common asynchronous-reader failure and must not be saved.
            advanced = sample and (previous is None or (sample[0] != previous[0] and sample[1] != previous[1]))
            if advanced:
                key = sample[:2]
                if key != candidate:
                    candidate, stable_since = key, time.monotonic()
                elif time.monotonic() - stable_since >= settle:
                    return sample
            else:
                candidate = None
                stable_since = time.monotonic()
            self.page.wait_for_timeout(150)
        raise CaptureError("Page did not reach a new, stable label and image before timeout. Check loading controls, selectors, or session expiry.")

    def at_end(self):
        if self.next.count() != 1 or not self.next.is_visible():
            raise CaptureError("Next button disappeared; cannot confirm the end of the book.")
        return not self.next.is_enabled() or self.next.get_attribute("aria-disabled") == "true"

    def advance(self):
        self.next.click(timeout=self.timeout * 1000)


def write_manifest(folder, manifest):
    temp = folder / "manifest.json.tmp"
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(folder / "manifest.json")


def write_gallery(folder, manifest):
    pages = []
    for row in manifest["pages"]:
        label = html.escape(row["displayed_label"])
        image = html.escape(row["file"], quote=True)
        pages.append(f'<figure><figcaption>Capture {row["sequence"]} · {label}</figcaption><img src="{image}" alt="Page {label}" loading="lazy"></figure>')
    (folder / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>Reader capture</title><style>body{font:18px system-ui;background:#eee;margin:2rem auto;max-width:1000px;padding:0 1rem}'
        'figure{margin:2rem 0}img{display:block;max-width:100%;height:auto;margin-top:.5rem}figcaption{font-weight:600}</style>'
        f'<h1>Reader capture</h1><p>Status: {html.escape(manifest["status"])} · {len(pages)} captured pages</p>'
        + "".join(pages) + '</html>', encoding="utf-8")


def capture(reader, folder, *, max_pages=0, settle=1.0):
    if max_pages < 0 or settle <= 0:
        raise ValueError("max_pages must be nonnegative and settle must be positive")
    folder = Path(folder)
    # Never mix books, silently overwrite screenshots, or mistake an old run
    # for a successful capture. Every run requires a fresh destination.
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"version": 1, "started_at": datetime.now(timezone.utc).isoformat(), "status": "running", "pages": []}
    write_manifest(folder, manifest)
    previous = None
    seen = set()
    try:
        reader.validate()
        while True:
            sample = reader.stable_page(previous, settle)
            label, digest, png = sample
            if sample[:2] in seen:
                raise CaptureError("Navigation returned to a previously captured page; stopped to avoid a loop.")
            seen.add(sample[:2])
            sequence = len(manifest["pages"]) + 1
            name = f"{sequence:06d}-page-{label_slug(label)}.png"
            (folder / name).write_bytes(png)
            manifest["pages"].append({"sequence": sequence, "displayed_label": label, "file": name, "sha256": digest})
            write_manifest(folder, manifest)
            print(f"Saved capture {sequence}: {label}", flush=True)
            if reader.at_end():
                manifest["status"] = "complete"
                break
            if max_pages and sequence >= max_pages:
                manifest["status"] = "page_limit"
                break
            previous = sample[:2]
            reader.advance()
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        raise
    except Exception:
        manifest["status"] = "failed"
        # Do not persist exception strings: browser errors can contain URLs or
        # details from an authenticated page.
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_manifest(folder, manifest)
        write_gallery(folder, manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Reader or login URL")
    parser.add_argument("--config", required=True, type=Path, help="JSON reader selectors; see readme.md")
    parser.add_argument("--output", required=True, type=Path, help="New directory for screenshots and manifest")
    parser.add_argument("--max-pages", type=int, default=0, help="Optional capture limit; 0 = unlimited")
    parser.add_argument("--timeout", type=float, default=30, help="Seconds allowed for each page to settle")
    parser.add_argument("--settle", type=float, default=1.0, help="Seconds that label and screenshot must remain stable")
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        parser.error("Provide an HTTP(S) URL without embedded credentials.")
    if args.max_pages < 0 or not 0 < args.settle < args.timeout:
        parser.error("Use max-pages >= 0 and 0 < settle < timeout.")
    if args.output.exists():
        parser.error("Output already exists; choose a fresh directory.")
    try:
        config = ReaderConfig(**json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        parser.error(f"Invalid reader configuration: {exc}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("Install requirements-playwright.txt and run: python -m playwright install chromium")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=False)
            try:
                page = context.new_page()
                page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
                input("Sign in in the browser, open the reader in this tab, choose single-page / fit-page view and the starting page. Press Enter here when ready: ")
                result = capture(Reader(page, config, args.timeout), args.output, max_pages=args.max_pages, settle=args.settle)
                print(f'{result["status"]}: {len(result["pages"])} pages saved to {args.output}')
            finally:
                context.close()
                browser.close()
    except (KeyboardInterrupt, EOFError):
        print("Capture cancelled. Any captured pages have been kept.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Capture failed ({type(exc).__name__}). {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
