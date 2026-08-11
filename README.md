# Content Extract

Content Extract is a local desktop and command-line toolkit for turning public
web pages, whole sites, chapter-based online books, and available YouTube
captions into clean study files.

This monorepo combines the histories of
[`web_crawler`](https://github.com/AbenezerW2/web_crawler) and
[`youtube-extractor`](https://github.com/AbenezerW2/youtube-extractor). Both
standalone command-line tools remain available, while the desktop app exposes
the combined workflows from one interface.

## Features

- Extract one web page and use its page title as the default filename.
- Crawl up to 30 same-site pages, following eligible links breadth-first.
- Extract chapter-based online books.
- Extract one YouTube transcript or a playlist of up to 30 videos.
- Save any workflow as plain text, Markdown, or JSON.
- Export clean portable HTML or a full-page visual snapshot from the repository CLI.
- Override automatically detected filenames when needed.
- Reopen recent results from persistent, per-workflow history.

## Repository layout

```text
apps/
  web-extractor/      Python crawler, desktop bridge, and React interface
  youtube-extractor/  YouTube caption extractor CLI
app.py                Unified desktop entry point
requirements.txt      Unified Python installation
```

## Install

Python 3.10 or newer and Node.js 20 or newer are recommended.

### Windows PowerShell

Use the Windows Python launcher (`py`) to create the environment, then run
Playwright through that environment so Chromium is installed for the same
Python interpreter as the app:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium

Push-Location apps\web-extractor\frontend
npm install
npm run build
Pop-Location

python app.py
```

Run the npm commands inside `apps\web-extractor\frontend`; the repository root
does not contain the frontend package.

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium

cd apps/web-extractor/frontend
npm install
npm run build
cd ../../..
```

## Launch the desktop app from source

```bash
python app.py
```

Choose **Web page**, **Whole site**, **Whole book**, or **YouTube**. Every
workflow runs locally and writes only to the output folder you choose.
The desktop app defaults to `~/Documents/Extracted`; you can replace it with
another folder at any time.

For frontend development, run `npm run dev` inside
`apps/web-extractor/frontend`, then launch:

```bash
python app.py --dev
```

## Build the installable macOS app

The repository now includes a production packaging pipeline. It compiles the
React interface, bundles the Python extraction engine and Chromium, creates a
native application icon, and produces a standalone `Content Extract.app`.

On macOS, from the repository root:

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
open "dist/Content Extract.app"
```

The packaged app does not require the user to install Python, Node.js, or
Playwright. Extraction history is stored in
`~/Library/Application Support/Content Extract`, while generated documents
continue to default to `~/Documents/Extracted`.

The output is currently unsigned. For distribution outside your own Mac, sign
the app with an Apple Developer ID and notarize it before publishing a DMG.

## Standalone command-line tools

The original CLIs remain usable:

```bash
python apps/web-extractor/crawler.py "https://example.com" --auto-name --format markdown
python apps/web-extractor/crawler.py "https://example.com" --crawl-site --max-pages 30 --format json
python apps/web-extractor/crawler.py "https://example.com" --auto-name --format html --html-mode clean
python apps/web-extractor/crawler.py "https://example.com" --playwright --auto-name --format html --html-mode snapshot
python apps/youtube-extractor/youtube_transcript_extractor.py "YOUTUBE_URL" --format markdown
python apps/youtube-extractor/youtube_transcript_extractor.py "PLAYLIST_URL" --playlist --max-videos 30 --format json
```

Run either command with `--help` for its complete options.

HTML output is available in both the desktop app and repository CLI. Clean HTML
embeds ordinary images and applies a safe readable layout; snapshot HTML retains
the complete fetched or rendered page structure.

## Responsible use

Use the tools only for content you are permitted to access. The web extractor
honors `robots.txt` and does not bypass authentication, CAPTCHAs, paywalls, or
access controls. The YouTube workflow downloads captions that are already
available; it does not transcribe unavailable audio or bypass video restrictions.
Audio/video transcription is a possible future workflow and is not included yet.

Proxy credentials, when used, must be supplied through environment variables
and must never be committed.

## History preservation

The source repositories were imported as unsquashed Git subtrees. Their original
commits remain reachable in this repository's history under their respective
`apps/` directories.
