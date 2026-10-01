# Experimental Kortext / paginated-reader capture — v2.2

This adds a standalone command-line capture workflow for readers whose Next
button changes the displayed page without changing the URL. It uses the same
Playwright dependency as the existing web extractor. The desktop interface includes a dedicated Kortext tab. Open the
browser, sign in and select a PDF book in single-page / fit-page view,
then return to the app and select Start capture. The tab defaults to a
three-page trial; set the page limit to 0 to continue to the last page.
Each run creates a fresh subfolder with PNGs, a manifest and an HTML gallery.

## Branch base and missing v2

`v2.2` starts from GitHub `main` at
`2e992c6aba921bbfd1974a7152d39fbce8406627`. The previously reported `v2`
commit `fdd0368` was not available on GitHub when this branch was created.
This branch does **not** claim to include or replace that missing work.
The existing whole-site crawler still has its existing 30-page limit.
The new reader capture workflow defaults to unlimited captures and offers
an optional `--max-pages` limit for a short trial.

## Changes

- Opens one visible, temporary browser session. Sign in yourself, then open
  the desired book in that same tab. The session stays alive throughout capture.
- Captures only the configured content region, including canvas/image readers.
- Reads the actual displayed page label, including input fields and Roman
  numerals; records it separately from capture sequence. It does not infer a
  printed book page number from a viewer index.
- Clicks Next, waits for **both** label and image to change, waits for visible
  loading indicators to disappear and images to load, and checks stability.
- Saves numbered PNG files, a `manifest.json` with labels and SHA-256 hashes,
  and a browsable `index.html` gallery.
- Supports separate iframe selectors for content and navigation controls.
- Detects navigation cycles and timeouts, preserves partial results, and marks
  the run failed instead of calling a stuck reader complete.
- Requires a fresh output directory to prevent overwriting or mixing books.
- Does not export credentials, cookies, browser storage, session files,
  authenticated URLs, or page HTML. The browser context closes on exit. The
  program does not promise forensic secure erasure of browser temporary data.

## Install

From the repository root, using Python 3.10+ in a virtual environment:

```bash
python -m pip install -r apps/web-extractor/requirements-playwright.txt
python -m playwright install chromium
```

## Configure the reader

The supplied `kortext-pdf.json` configuration was verified against the live
Kortext PDF reader on September 28, 2026. Use it for an initial short trial.
Other reader versions and EPUB books may require different selectors. For
those readers, obtain selectors from the actual open reader using browser
developer tools or Playwright Inspector. A custom configuration looks like:

```json
{
  "content_selector": "#book-page",
  "next_selector": "button[aria-label='Next page']",
  "page_label_selector": "input[aria-label='Page number']",
  "loading_selector": "[role='progressbar']",
  "content_frame_selector": "",
  "controls_frame_selector": ""
}
```

**These selectors are illustrative, not confirmed Kortext selectors.** Replace
them with the reader's actual selectors. Content, label and Next must each
match exactly one visible element. Optional fields can be omitted or empty.
The loading selector may match multiple indicators and is scoped to the
controls frame. Use a content container that excludes toolbars and page labels;
otherwise a changing label can disguise stale page artwork. If the content is
inside an iframe but controls are outside, set only `content_frame_selector`.
Nested iframe chains are not implemented.

## Run a short trial

```bash
python apps/web-extractor/kortext/reader_capture.py "https://app.kortext.com" \
  --config apps/web-extractor/kortext/kortext-pdf.json \
  --output outputs/kortext-trial --max-pages 3
```

Sign in manually in the new browser, open the book in that same tab, select
single-page / fit-page view, and navigate to the starting page. Return to the
terminal and press Enter. Nothing clicks through pages until that step.
The in-app browser and this script's browser do not share login sessions.

Review the screenshots and their labels in `outputs/kortext-trial/index.html`.
When the setup is correct, omit `--max-pages` for capture through the last page.
Each run starts from the currently displayed page; it does not automatically
rewind to the cover. Choose a new output directory each time. Press Ctrl+C to
stop and retain completed captures.

`complete` means Next was visibly disabled. `page_limit` means the requested
capture count was reached. `failed` and `interrupted` identify partial runs.
A missing Next button is an error, not proof that the book ended.

## Limits and troubleshooting

- This is visual capture, not original PDF/EPUB download, OCR, or DRM decryption.
  Use it for content you are permitted to capture. It does not bypass login,
  paywalls, CAPTCHAs, or access controls.
- Scrollable content can be clipped; use a view where the entire intended page
  fits. A two-page spread is one capture, not two separately numbered pages.
- Stable screenshots are a heuristic, not proof of rendering completion. Wire
  up the actual loading indicator, increase `--settle` for a slow reader, and
  visually review the trial before a long run. `--timeout` must exceed settle.
- Identical consecutive artwork, continuously animated content, unchanged page
  labels, image-only labels, or a login/session expiry can stop the run. This
  deliberately avoids silently saving stale pages. No automatic retry clicks
  are sent, because they could skip a page.
- Completed captures are preserved after errors; automatic resume is not
  implemented. Navigate manually to the next needed page and use a new folder.

## Verification

```bash
python -m unittest discover -s apps/web-extractor/kortext -p 'test_*.py' -v
python -m unittest discover -s apps/web-extractor -p 'test_crawler.py' -v
```

The browser integration tests exercise delayed canvas rendering, Roman and
numeric labels, disabled/missing Next controls, stale artwork, navigation
cycles, capture limits, iframes, ambiguous selectors, escaped labels, and output
preservation. They use a controlled fixture, not a Kortext account.

On September 28, 2026, a live trial after manual sign-in successfully captured
three consecutive PDF reader pages labelled 2, 3 and 4. All three screenshots
were visually checked against their printed page numbers. The run stopped at
the requested three-page limit. Kortext's loading bar remains mounted with
opacity zero when idle; the loading check now accounts for transparent elements
and ancestors, with a regression test covering this behavior.

The URL advanced from `/reader/pdf/5626/2` to `/reader/pdf/5626/4` during the
trial. Navigation in this implementation still clicks Next; numbered-URL
navigation has not been implemented. Whole-book completion, other titles,
EPUB readers, and expired-session recovery have not been verified live.
Captured book pages and login state are not included in this repository.
