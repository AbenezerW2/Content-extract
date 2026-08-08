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

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
playwright install chromium

cd apps/web-extractor/frontend
npm install
npm run build
cd ../../..
```

## Launch the desktop app

```bash
python app.py
```

Choose **Web page**, **Whole site**, **Whole book**, or **YouTube**. Every
workflow runs locally and writes only to the output folder you choose.

For frontend development, run `npm run dev` inside
`apps/web-extractor/frontend`, then launch:

```bash
python app.py --dev
```

## Standalone command-line tools

The original CLIs remain usable:

```bash
python apps/web-extractor/crawler.py "https://example.com" --auto-name --format markdown
python apps/web-extractor/crawler.py "https://example.com" --crawl-site --max-pages 30 --format json
python apps/youtube-extractor/youtube_transcript_extractor.py "YOUTUBE_URL" --format markdown
python apps/youtube-extractor/youtube_transcript_extractor.py "PLAYLIST_URL" --playlist --max-videos 30 --format json
```

Run either command with `--help` for its complete options.

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
