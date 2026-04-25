# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)
[![PyPI version](https://img.shields.io/pypi/v/subs-down-n-sync?v=1)](https://pypi.org/project/subs-down-n-sync/)
[![Python versions](https://img.shields.io/pypi/pyversions/subs-down-n-sync?v=1)](https://pypi.org/project/subs-down-n-sync/)
[![License](https://img.shields.io/pypi/l/subs-down-n-sync)](LICENSE)

Python CLI for downloading and synchronizing subtitles for video files. Default language: **pt-BR**, configurable via `--lang` flag (any BCP 47 tag).

Synchronization uses multilingual semantic embeddings ([sentence-transformers](https://www.sbert.net/), model `paraphrase-multilingual-MiniLM-L12-v2`) combined with DTW: downloads an EN reference subtitle and aligns target cues to the reference timestamps via semantic similarity. Subtitles with an exact match (hash or release group) are used without synchronization.

## Installation

```bash
pip install subs-down-n-sync
```

Also install `ffmpeg`:

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
winget install Gyan.FFmpeg # Windows
```

Set your OpenSubtitles credentials:

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

> For development setup, see [Setup](#setup).

## Setup

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Windows (cmd.exe):

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
```

Also install `ffmpeg` on your system:

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

```powershell
winget install Gyan.FFmpeg          # Windows (winget)
choco install ffmpeg                # Windows (Chocolatey)
scoop install ffmpeg                # Windows (Scoop)
```

Confirm `ffmpeg` is on your `PATH` by running `ffmpeg -version` in a new terminal.

## Configuration (once)

Linux/macOS:

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

Windows (PowerShell, current session):

```powershell
$env:OPENSUBTITLES_USERNAME = "your_username"
$env:OPENSUBTITLES_PASSWORD = "your_password"
```

Windows (persistent, future sessions):

```powershell
setx OPENSUBTITLES_USERNAME "your_username"
setx OPENSUBTITLES_PASSWORD "your_password"
```

## Usage

```bash
# Default: pt-BR
subs-down-n-sync /path/to/movie.mkv

# Other language (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
subs-down-n-sync /path/to/movie.mkv --lang en
subs-down-n-sync /path/to/movie.mkv -l es

# Process an entire directory (recursively scans for videos)
subs-down-n-sync /path/to/folder/
subs-down-n-sync /path/to/folder/ --lang en
subs-down-n-sync /path/to/folder/ --overwrite   # overwrite existing subtitles
subs-down-n-sync /path/to/folder/ --parallel    # process up to 2 videos in parallel

# Or via Python module
python -m subs_down_n_sync /path/to/movie.mkv
```

When passing a directory, videos that already have a subtitle (`<video>.<lang>.srt`) are skipped by default. Use `--overwrite` / `-o` to reprocess. Use `--parallel` / `-p` to process up to 2 videos concurrently.

Output: `/path/to/movie.<lang>.srt` (e.g. `movie.pt-BR.srt`, `movie.en.srt`). This allows keeping subtitles for the same video in different languages without overwriting.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Unit tests run with a 90% coverage gate (configured in `pyproject.toml`). CI fails if coverage drops below that.

To run without the gate (useful with `-k` or `--collect-only`):

```bash
pytest --no-cov
```

## Lint and formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.

```bash
ruff format .           # apply formatting
ruff format --check .   # check without writing (used in CI)
ruff check .            # run lint
ruff check --fix .      # apply automatic fixes
```

CI fails if `ruff format --check` or `ruff check` find any issues.

## Integration tests

The project has two test layers:

- **Unit tests** (default, `pytest`) — fast, mock `subliminal` and `sentence_transformers`. No network or external binaries required beyond Python.
- **Integration tests** (`pytest -m integration`) — exercise the real semantic alignment pipeline (`sentence-transformers` model download + DTW) over real subtitles. Requires internet access on first run to download the model (~120 MB), cached by Hugging Face under `~/.cache/huggingface/`.

How to run each layer:

```bash
pytest                    # unit only (fast)
pytest -m integration     # integration only (downloads embedding model, runs real DTW)
pytest -m ""              # everything (unit + integration)
```
