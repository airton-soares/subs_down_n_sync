# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)

Python CLI for downloading and synchronizing subtitles for video files. Default language: **pt-BR**, configurable via `--lang` flag (any BCP 47 tag).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Also install `ffmpeg` on your system (used by `ffsubsync`):

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

## Configuration (once)

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

## Usage

```bash
# Default: pt-BR
subs-down-n-sync /path/to/movie.mkv

# Other language (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
subs-down-n-sync /path/to/movie.mkv --lang en
subs-down-n-sync /path/to/movie.mkv -l es

# Or via Python module
python -m subs_down_n_sync /path/to/movie.mkv
```

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

- **Unit tests** (default, `pytest`) — fast, mock `subliminal` and `ffsubsync`. No network or external binaries required beyond Python.
- **Integration tests** (`pytest -m integration`) — exercise real `ffsubsync` with the Sintel trailer (Blender Foundation, Creative Commons). The video is downloaded automatically on first run and cached in `tests/fixtures/.cache/`. Requires `ffmpeg` and `ffsubsync` in PATH and internet access on first run.

How to run each layer:

```bash
pytest                    # unit only (fast)
pytest -m integration     # integration only (downloads ~4 MB video, runs real ffsubsync)
pytest -m ""              # everything (unit + integration)
```

## Manual smoke test

To test the full pipeline against a real video on your disk, with real OpenSubtitles credentials:

```bash
export OPENSUBTITLES_USERNAME="..."
export OPENSUBTITLES_PASSWORD="..."
python scripts/smoke_test.py /path/to/movie.mkv
python scripts/smoke_test.py /path/to/movie.mkv --lang en
```

This script consumes real OpenSubtitles API quota and **is not called by `pytest`**. Use it to validate the full end-to-end flow before a release or after changing download/sync logic.
