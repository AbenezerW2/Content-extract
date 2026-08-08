# YouTube Extractor

A small Python command-line tool that downloads available YouTube captions and
saves them as clean UTF-8 text files.

It supports standard YouTube links, short links, Shorts, Live links, embed
links, and bare video IDs. It can prioritize preferred caption languages,
fall back to another available language, optionally translate captions, and
report whether the selected captions are manual or automatically generated.

## Requirements

- Python 3.8 or newer
- An internet connection

## Installation

Clone the repository and install its dependency:

```bash
git clone https://github.com/AbenezerW2/youtube-extractor.git
cd youtube-extractor
python -m pip install -r requirements.txt
```

## Usage

Start interactive mode:

```bash
python youtube_transcript_extractor.py
```

By default, downloaded transcripts are saved in
`~/Documents/YouTube Transcripts`, regardless of the Terminal's current folder.
Use `--output-dir` to select a different location.

In interactive mode, the video's YouTube title is suggested as the filename.
Press Enter to accept it or type a different name. If the file already exists,
choose whether to keep both copies, overwrite the existing file, or cancel.

Download one video's captions:

```bash
python youtube_transcript_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Choose an output file:

```bash
python youtube_transcript_extractor.py "YOUTUBE_URL" --output transcript.txt
```

Replacing an existing output file is intentionally explicit:

```bash
python youtube_transcript_extractor.py "YOUTUBE_URL" --output transcript.txt --overwrite
```

Set preferred languages in priority order:

```bash
python youtube_transcript_extractor.py "YOUTUBE_URL" --language am --language en
```

Translate another available transcript to English when preferred captions are
not available:

```bash
python youtube_transcript_extractor.py "YOUTUBE_URL" --translate en
```

Require one of the requested languages instead of accepting captions in
another language:

```bash
python youtube_transcript_extractor.py "YOUTUBE_URL" --language am --strict-language
```

Run `python youtube_transcript_extractor.py --help` for all options.

## Optional proxy configuration

YouTube may block repeated transcript requests, particularly from cloud-hosted
IP addresses. The tool optionally supports Webshare residential proxy
credentials through environment variables:

```bash
export WEBSHARE_PROXY_USERNAME="your-username"
export WEBSHARE_PROXY_PASSWORD="your-password"
python youtube_transcript_extractor.py
```

Never commit proxy credentials to the repository.

## Limitations

- The tool downloads captions that already exist on YouTube; it does not
  transcribe audio when a video has no captions.
- Private, unavailable, region-restricted, or age-restricted videos may not be
  accessible.
- YouTube can temporarily block high-volume requests.

Please respect video creators' rights and YouTube's applicable terms when using
downloaded captions.
