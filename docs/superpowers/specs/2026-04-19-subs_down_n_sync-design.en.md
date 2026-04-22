# subs_down_n_sync — Design Spec

## Summary

Python CLI script that finds the most suitable subtitle (in any language supported by OpenSubtitles) for a video file (movie/series) and, when needed, automatically synchronizes it using the audio as reference. Default: **pt-BR**, configurable via flag.

## Usage

```bash
subs-down-n-sync /path/to/movie.mkv            # pt-BR (default)
subs-down-n-sync /path/to/movie.mkv --lang en  # English
subs-down-n-sync /path/to/movie.mkv -l es      # Spanish
```

The `--lang/-l` value is a BCP 47 tag: accepts simple codes (`en`, `es`, `pt`) or with region (`pt-BR`, `en-US`). Parsed with `babelfish.Language.fromietf()`.

Output: `.<lang>.srt` file in the same directory as the video, with the same base name (e.g. `movie.pt-BR.srt`, `movie.en.srt`). This avoids overwriting subtitles of different languages for the same video.

## Architecture

Sequential 3-phase pipeline:

```
video file → [Search] → [Evaluation + Sync] → ready .srt subtitle
```

### Phase 1: Subtitle Search

Uses the `subliminal` library to search for subtitles in the requested language from available providers (mainly OpenSubtitles).

**Match priority:**

1. Video hash match (OpenSubtitles hash: first + last 64KB) — highest confidence, same version/release
2. Release name match (subliminal parser extracts group, codec, resolution and compares) — good confidence
3. Best score/downloads from providers — fallback

**Credentials:** read from environment variables `OPENSUBTITLES_USERNAME` and `OPENSUBTITLES_PASSWORD`.

**Format:** SRT only.

### Phase 2: Evaluation and Synchronization

After downloading the best subtitle candidate:

1. Run `ffsubsync` comparing the subtitle against the video audio (Voice Activity Detection — VAD)
2. If the mean alignment difference is **< 0.1s**: subtitle is already good, keep the original
3. If the difference is **>= 0.1s**: save the synchronized version

In both cases, the final result is a single `<video_name>.<lang>.srt` file in the video directory.

### Terminal Feedback

- Which subtitle was found (provider, match type)
- Whether synchronization was needed and the applied adjustment
- Total execution time

## Error Handling

| Scenario | Behavior |
|---|---|
| Video file does not exist / invalid format | Clear message, exit code 1 |
| Invalid language code (not parseable as BCP 47) | Clear message, exit code 2 (CLI error) |
| OpenSubtitles credentials not configured | Reports which variables are missing, exit code 1 |
| No subtitle found for the requested language | Reports the language, exit code 1 |
| Sync failure (ffsubsync error) | Keeps original unsynced subtitle, warns that sync failed but subtitle was saved |
| ffmpeg not installed | Detected before starting, warns how to install, exit code 1 |

No case silences the error.

## Dependencies

### Python packages (pip)

- `subliminal` — multi-provider subtitle search
- `ffsubsync` — audio-based synchronization (VAD + FFT)

### System dependencies

- `ffmpeg` — used internally by ffsubsync

## Project Structure

```text
~/Git/subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── core.py
│       └── exceptions.py
├── tests/
├── scripts/
└── pyproject.toml
```

## Setup

```bash
cd ~/Git/subs_down_n_sync
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration (once)

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

## Design Decisions

- **Python instead of Elixir:** Python subtitle ecosystem is much more mature (subliminal, ffsubsync). Elixir has no equivalent libraries.
- **0.1s threshold:** below this the subtitle is considered well synchronized. Above, ffsubsync corrects it.
- **Always run ffsubsync:** instead of trying custom heuristics to detect desync, we delegate to ffsubsync which already does analysis + correction.
- **Output replaces:** the synchronized version replaces the original, as it is strictly better.
- **Pre-existing subtitle:** if a `.srt` with the same name already exists in the video directory, the script overwrites without asking (simple CLI behavior, no interactivity).
- **Configurable language with pt-BR default:** the project originated from pt-BR subtitles. We keep this default to not break daily use, but accept `--lang` for any BCP 47 supported by the provider.
- **Filename includes the language (`.<lang>.srt`):** allows keeping multiple subtitles for the same video in different languages without overwriting. The exact tag used is what the user passed (e.g. `pt-BR`, `en`), normalized via `babelfish` to canonical form.
