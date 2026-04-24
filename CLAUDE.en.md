# subs_down_n_sync

Python CLI for automatic subtitle download and synchronization for video files. Default language: **pt-BR**, configurable via `--lang` flag (any BCP 47 tag).

## Project structure

```text
subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py          # exports __version__ and run
│       ├── __main__.py          # enables python -m subs_down_n_sync
│       ├── cli.py               # argparse + entry point main()
│       ├── core.py              # all business logic
│       └── exceptions.py        # all project exceptions
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   └── mini.srt
│   ├── test_core.py             # unit tests
│   └── test_integration.py      # integration tests (marker: integration)
├── scripts/
│   └── smoke_test.py            # manual test against real API
├── docs/
├── .github/workflows/ci.yml
├── .gitignore
├── CLAUDE.md                    # Portuguese version
├── CLAUDE.en.md                 # this file (English)
├── README.md                    # Portuguese
├── README.en.md                 # English
└── pyproject.toml               # single configuration source
```

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install system dependencies:

```bash
# ffmpeg
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

Configure OpenSubtitles credentials:

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

## How to run

```bash
# Via installed entry point (after pip install -e ".[dev]")
subs-down-n-sync /path/to/movie.mkv
subs-down-n-sync /path/to/movie.mkv --lang en

# Process an entire directory (recursive)
subs-down-n-sync /path/to/folder/
subs-down-n-sync /path/to/folder/ --lang en
subs-down-n-sync /path/to/folder/ --overwrite   # overwrite existing subtitles

# Via Python module
python -m subs_down_n_sync /path/to/movie.mkv
```

## How to run tests

```bash
pytest                    # unit tests (default, with 90% coverage gate)
pytest --no-cov           # no gate (useful with -k or --collect-only)
pytest -m integration     # integration tests (requires ffmpeg, stable-ts and network)
pytest -m ""              # everything (unit + integration)
```

## Lint and formatting

```bash
ruff format .           # apply formatting
ruff format --check .   # check without writing (used in CI)
ruff check .            # run lint
ruff check --fix .      # apply automatic fixes
```

## Project standards

- **Language:** identifiers in English; comments and UX messages in Portuguese
- **Commits:** Conventional Commits in Portuguese (e.g. `feat: adicionar suporte a ...`)
- **Exceptions:** all in `src/subs_down_n_sync/exceptions.py`, imported explicitly
- **Blank lines:** separate logical blocks inside functions with one blank line
- **Bilingual docs:** every `.md` file has a `.en.md` English counterpart (README, CLAUDE)
