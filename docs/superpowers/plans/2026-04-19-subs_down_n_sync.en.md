# subs_down_n_sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python CLI that receives a video file and a language code (flag `--lang/-l`, default `pt-BR`), finds the most suitable subtitle via `subliminal`, synchronizes with `ffsubsync` when needed (>= 0.1s offset) and saves `<video_name>.<lang>.srt` next to the video.

**Architecture:** Single script with pure functions orchestrated by a `main()`. Sequential 3-phase pipeline: (1) input validation + credentials + `ffmpeg`; (2) search/download via `subliminal`; (3) sync evaluation via `ffsubsync` + conditional replacement. Errors propagate as typed exceptions caught in `main`, which converts them to readable messages + exit codes.

**Tech Stack:** Python 3.12+, `subliminal`, `ffsubsync`, `pytest` (tests), `ffmpeg` (system binary).

---

## File Structure

- `src/subs_down_n_sync/core.py` — main module with pure functions (`check_ffmpeg`, `load_credentials`, `find_and_download_subtitle`, `sync_subtitle_if_needed`, `finalize_output_path`, `run`) and business logic.
- `src/subs_down_n_sync/cli.py` — argparse entry point with `main()` and `build_parser()`.
- `src/subs_down_n_sync/exceptions.py` — all typed exceptions.
- `src/subs_down_n_sync/__init__.py` — exports `__version__` and `run`.
- `src/subs_down_n_sync/__main__.py` — enables `python -m subs_down_n_sync`.
- `pyproject.toml` — single configuration source (deps, pytest, ruff, coverage).
- `tests/test_core.py` — unit tests for functions, mocking I/O (subliminal, ffsubsync, subprocess).
- `tests/fixtures/` — minimal support files (e.g. a short valid `.srt`).

---

## Tasks (summarized — implementation already complete)

The following tasks were executed to build the project from scratch:

1. **Project bootstrap** — pyproject.toml, src-layout, venv setup
2. **Module skeleton + CLI entrypoint** — argparse, `main()`, exit code 2 on missing args
3. **Video file validation** — `validate_video_path()`, `InvalidVideoError`
4. **ffmpeg binary check** — `check_ffmpeg()`, `MissingDependencyError`
5. **OpenSubtitles credentials loading** — `load_credentials()`, `MissingCredentialsError`
6. **Language parsing + subtitle search via subliminal** — `parse_language()`, `find_and_download_subtitle()`, match classification (hash > release > fallback)
7. **Subtitle synchronization via ffsubsync** — `sync_subtitle_if_needed()`, 0.1s threshold, `SyncResult`
8. **Output path finalization** — `finalize_output_path()`, canonical `<video>.<lang>.srt` naming
9. **`run()` orchestration + `main()` integration** — `RunSummary`, feedback output, exit codes
10. **README** — setup, configuration, usage documentation

All tasks follow TDD: failing test written first, then minimal implementation, then passing test verified, then commit.
