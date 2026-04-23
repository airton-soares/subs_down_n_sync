# Project Restructure to src-layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the project to src-layout, consolidate configs into `pyproject.toml`, create `subs-down-n-sync` entry point, and establish bilingual standard (pt-BR + English) for README, CLAUDE.md and docs.

**Architecture:** All business logic migrates to `src/subs_down_n_sync/` split into `core.py` (logic), `cli.py` (argparse + entry point) and `exceptions.py`. pytest, ruff, requirements and coverage configs consolidate into `pyproject.toml`. Bilingual documentation created for README, CLAUDE.md and all docs in `docs/superpowers/`.

**Tech Stack:** Python 3.12, setuptools src-layout, pytest, ruff, subliminal, ffsubsync

---

## File Map

| Action | File |
|--------|------|
| Create | `src/subs_down_n_sync/__init__.py` |
| Create | `src/subs_down_n_sync/__main__.py` |
| Create | `src/subs_down_n_sync/core.py` |
| Create | `src/subs_down_n_sync/cli.py` |
| Create | `src/subs_down_n_sync/exceptions.py` |
| Create | `pyproject.toml` |
| Create | `tests/test_core.py` |
| Create | `README.en.md` |
| Create | `CLAUDE.en.md` |
| Create | `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.en.md` |
| Create | `docs/superpowers/specs/2026-04-22-github-pipeline-design.en.md` |
| Create | `docs/superpowers/specs/2026-04-22-project-restructure-design.en.md` |
| Create | `docs/superpowers/plans/2026-04-19-subs_down_n_sync.en.md` |
| Create | `docs/superpowers/plans/2026-04-22-github-pipeline.en.md` |
| Create | `docs/superpowers/plans/2026-04-22-project-restructure.en.md` |
| Modify | `tests/test_integration.py` |
| Modify | `scripts/smoke_test.py` |
| Modify | `CLAUDE.md` |
| Modify | `README.md` |
| Modify | `.github/workflows/ci.yml` |
| Delete | `subs_down_n_sync.py` |
| Delete | `exceptions.py` |
| Delete | `pytest.ini` |
| Delete | `ruff.toml` |
| Delete | `requirements.txt` |
| Delete | `requirements-dev.txt` |
| Delete | `.coveragerc` |

---

### Task 1: Create `pyproject.toml` and `src/` structure

**Files:**

- Create: `pyproject.toml`
- Create: `src/subs_down_n_sync/__init__.py`
- Create: `src/subs_down_n_sync/__main__.py`

- [ ] **Step 1: Create src directory**

```bash
mkdir -p src/subs_down_n_sync
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "subs-down-n-sync"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "subliminal>=2.2",
    "ffsubsync>=0.4.25",
    "setuptools<81",
]

[project.scripts]
subs-down-n-sync = "subs_down_n_sync.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-cov>=6.0",
    "ruff>=0.9",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
markers = ["integration: tests that require ffmpeg, ffsubsync and network"]
addopts = "-m 'not integration' --cov=src/subs_down_n_sync --cov-report=term-missing --cov-fail-under=90"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"

[tool.coverage.run]
source = ["src/subs_down_n_sync"]

[tool.coverage.report]
fail_under = 90
```

- [ ] **Step 3: Create `src/subs_down_n_sync/__init__.py`**

```python
"""subs_down_n_sync: busca e sincroniza legendas."""

from __future__ import annotations

__version__ = "0.1.0"

from subs_down_n_sync.core import run

__all__ = ["run", "__version__"]
```

- [ ] **Step 4: Create `src/subs_down_n_sync/__main__.py`**

```python
from subs_down_n_sync.cli import main

main()
```

- [ ] **Step 5: Reinstall package in editable mode**

```bash
pip install -e ".[dev]"
```

Expected: line `Successfully installed subs-down-n-sync-0.1.0 ...` (or similar indicating success).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/subs_down_n_sync/__init__.py src/subs_down_n_sync/__main__.py
git commit -m "chore: criar pyproject.toml e estrutura src/subs_down_n_sync"
```

---

### Task 2: Create `src/subs_down_n_sync/exceptions.py`

**Files:**

- Create: `src/subs_down_n_sync/exceptions.py`

- [ ] **Step 1: Create the file**

Content identical to `exceptions.py` at the root:

```python
"""Exceptions raised by subs_down_n_sync. Message is user-facing (in Portuguese)."""

from __future__ import annotations


class SubsDownError(Exception):
    """Erro base do script — mensagem é o que vai para o usuário."""


class InvalidVideoError(SubsDownError):
    pass


class MissingDependencyError(SubsDownError):
    pass


class MissingCredentialsError(SubsDownError):
    pass


class InvalidLanguageError(SubsDownError):
    pass


class SubtitleNotFoundError(SubsDownError):
    pass


class SubtitleSyncError(SubsDownError):
    pass
```

- [ ] **Step 2: Commit**

```bash
git add src/subs_down_n_sync/exceptions.py
git commit -m "refactor: mover exceptions.py para src/subs_down_n_sync/"
```

---

### Task 3: Create `src/subs_down_n_sync/core.py`

**Files:**

- Create: `src/subs_down_n_sync/core.py`

All business logic from `subs_down_n_sync.py` — no argparse, no `sys.exit`.

- [ ] **Step 1: Create the file**

```python
"""Business logic: subtitle download and synchronization."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import subliminal
from babelfish import Language

from subs_down_n_sync.exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}

DEFAULT_LANG = "pt-BR"

SYNC_THRESHOLD_SECONDS = 0.1

_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float


@dataclass(frozen=True)
class RunSummary:
    output_path: Path
    provider: str
    match_type: str
    synced: bool
    offset_seconds: float
    sync_error: str | None
    elapsed_seconds: float
    lang_tag: str


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MissingDependencyError(
            "ffmpeg não encontrado no PATH. Instale via gerenciador de pacotes "
            "(ex.: sudo apt install ffmpeg, brew install ffmpeg)."
        )


def load_credentials() -> tuple[str, str]:
    user = os.environ.get("OPENSUBTITLES_USERNAME")
    pwd = os.environ.get("OPENSUBTITLES_PASSWORD")

    missing = [
        name
        for name, val in (
            ("OPENSUBTITLES_USERNAME", user),
            ("OPENSUBTITLES_PASSWORD", pwd),
        )
        if not val
    ]

    if missing:
        raise MissingCredentialsError(
            "Variáveis de ambiente obrigatórias faltando: " + ", ".join(missing)
        )

    return user, pwd  # type: ignore[return-value]


def validate_video_path(raw: str) -> Path:
    p = Path(raw).expanduser()

    if not p.exists():
        raise InvalidVideoError(f"Arquivo de vídeo não existe: {p}")
    if not p.is_file():
        raise InvalidVideoError(f"Caminho não é um arquivo: {p}")
    if p.suffix.lower() not in VIDEO_EXTENSIONS:
        raise InvalidVideoError(
            f"Extensão não suportada ({p.suffix}). "
            f"Esperado um destes: {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )

    return p


def parse_language(raw: str) -> Language:
    try:
        return Language.fromietf(raw)
    except Exception as e:
        raise InvalidLanguageError(
            f"Código de idioma inválido: {raw!r}. Use tags BCP 47 como 'pt-BR', 'en', 'es', 'ja'."
        ) from e


def _classify_match(matches: set[str]) -> str:
    if "hash" in matches:
        return "hash"
    if "release_group" in matches:
        return "release"

    return "fallback"


def find_and_download_subtitle(
    video_path: Path,
    language: Language,
    credentials: tuple[str, str],
) -> tuple[Path, SubtitleInfo]:
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    provider_configs = {
        "opensubtitles": {"username": user, "password": pwd},
    }

    results = subliminal.download_best_subtitles(
        {video},
        {language},
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    subs = results.get(video, [])

    if not subs:
        raise SubtitleNotFoundError(
            f"Nenhuma legenda em {language.alpha3} encontrada para: {video_path.name}"
        )

    subtitle = subs[0]

    if not subtitle.text:
        raise SubtitleNotFoundError(f"Legenda veio vazia do provider para: {video_path.name}")

    srt_path = video_path.parent / Path(subtitle.get_path(video)).name
    srt_path.write_text(subtitle.text, encoding="utf-8")

    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=_classify_match(set(subtitle.get_matches(video))),
    )

    return srt_path, info


def _parse_srt_timestamps(srt_text: str) -> list[float]:
    out: list[float] = []

    for h, m, s, ms in _TS_RE.findall(srt_text):
        out.append(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000)

    return out


def _mean_offset_seconds(orig: list[float], synced: list[float]) -> float:
    n = min(len(orig), len(synced))

    if n == 0:
        return 0.0

    total = sum(abs(synced[i] - orig[i]) for i in range(n))

    return total / n


def sync_subtitle_if_needed(video_path: Path, srt_path: Path) -> SyncResult:
    synced_path = srt_path.with_suffix(".sync.srt")
    cmd = [
        "ffsubsync",
        str(video_path),
        "-i",
        str(srt_path),
        "-o",
        str(synced_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SubtitleSyncError(
            f"ffsubsync falhou (exit {e.returncode}): {e.stderr or e.stdout or '<sem saída>'}"
        ) from e
    except FileNotFoundError as e:
        raise SubtitleSyncError(
            "ffsubsync não encontrado no PATH. Instalou as deps do requirements.txt?"
        ) from e

    if not synced_path.exists():
        raise SubtitleSyncError("ffsubsync terminou sem criar o arquivo de saída.")

    orig_ts = _parse_srt_timestamps(srt_path.read_text(encoding="utf-8", errors="replace"))
    sync_ts = _parse_srt_timestamps(synced_path.read_text(encoding="utf-8", errors="replace"))
    offset = _mean_offset_seconds(orig_ts, sync_ts)

    if offset < SYNC_THRESHOLD_SECONDS:
        synced_path.unlink(missing_ok=True)

        return SyncResult(synced=False, offset_seconds=offset)

    synced_path.replace(srt_path)

    return SyncResult(synced=True, offset_seconds=offset)


def finalize_output_path(video_path: Path, srt_path: Path, lang_tag: str) -> Path:
    target = video_path.with_suffix(f".{lang_tag}.srt")

    if srt_path == target:
        return target

    srt_path.replace(target)

    return target


def run(video_arg: str, lang_tag: str = DEFAULT_LANG) -> RunSummary:
    start = time.monotonic()
    video_path = validate_video_path(video_arg)
    check_ffmpeg()
    language = parse_language(lang_tag)
    credentials = load_credentials()

    srt_path, info = find_and_download_subtitle(
        video_path, language=language, credentials=credentials
    )

    sync_error: str | None = None
    try:
        sync_result = sync_subtitle_if_needed(video_path, srt_path)
    except SubtitleSyncError as e:
        sync_error = str(e)
        sync_result = SyncResult(synced=False, offset_seconds=0.0)

    final_path = finalize_output_path(video_path, srt_path, lang_tag=lang_tag)
    elapsed = time.monotonic() - start

    return RunSummary(
        output_path=final_path,
        provider=info.provider,
        match_type=info.match_type,
        synced=sync_result.synced,
        offset_seconds=sync_result.offset_seconds,
        sync_error=sync_error,
        elapsed_seconds=elapsed,
        lang_tag=lang_tag,
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/subs_down_n_sync/core.py
git commit -m "refactor: extrair lógica de negócio para src/subs_down_n_sync/core.py"
```

---

### Task 4: Create `src/subs_down_n_sync/cli.py`

**Files:**

- Create: `src/subs_down_n_sync/cli.py`

- [ ] **Step 1: Create the file**

```python
"""CLI entry point: argparse and result printing."""

from __future__ import annotations

import argparse
import sys

from subs_down_n_sync.core import DEFAULT_LANG, RunSummary, run
from subs_down_n_sync.exceptions import SubsDownError


def _print_summary(summary: RunSummary) -> None:
    print(f"Legenda ({summary.lang_tag}): {summary.provider} (match: {summary.match_type})")

    if summary.sync_error:
        print(
            f"Aviso: sincronização falhou — mantendo legenda original. "
            f"Detalhe: {summary.sync_error}"
        )
    elif summary.synced:
        print(f"Sincronizada (ajuste médio: {summary.offset_seconds:.2f}s)")
    else:
        print(f"Já sincronizada (offset médio: {summary.offset_seconds:.2f}s < 0.10s)")

    print(f"Arquivo: {summary.output_path}")
    print(f"Tempo total: {summary.elapsed_seconds:.2f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs-down-n-sync",
        description="Busca e sincroniza legenda para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    parser.add_argument(
        "-l",
        "--lang",
        default=DEFAULT_LANG,
        help=f"Código de idioma BCP 47 (ex: pt-BR, en, es). Default: {DEFAULT_LANG}.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = run(args.video, lang_tag=args.lang)
    except SubsDownError as e:
        print(str(e), file=sys.stderr)
        return 1

    _print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify entry point works**

```bash
python -m subs_down_n_sync --help
```

Expected: usage with `subs-down-n-sync` and `video` argument.

- [ ] **Step 3: Commit**

```bash
git add src/subs_down_n_sync/cli.py
git commit -m "refactor: extrair CLI para src/subs_down_n_sync/cli.py"
```

---

### Task 5: Create `tests/test_core.py` and update tests

**Files:**

- Create: `tests/test_core.py`
- Modify: `tests/test_integration.py`
- Modify: `scripts/smoke_test.py`

- [ ] **Step 1: Create `tests/test_core.py`**

Content identical to `tests/test_subs_down_n_sync.py`, with updated imports:

```python
import shutil as shutil_
from pathlib import Path

import pytest
from babelfish import Language

from subs_down_n_sync.exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)
from subs_down_n_sync.core import (
    RunSummary,
    SubtitleInfo,
    SyncResult,
    _mean_offset_seconds,
    _parse_srt_timestamps,
    check_ffmpeg,
    finalize_output_path,
    find_and_download_subtitle,
    load_credentials,
    parse_language,
    run,
    sync_subtitle_if_needed,
    validate_video_path,
)
from subs_down_n_sync.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "mini.srt"
```

After these imports, copy **all remaining content** from `tests/test_subs_down_n_sync.py` starting at line 35 (all `def test_...`), replacing:

- `mocker.patch("subs_down_n_sync.subliminal.` → `mocker.patch("subs_down_n_sync.core.subliminal.`
- `mocker.patch("subs_down_n_sync.find_and_download_subtitle"` → `mocker.patch("subs_down_n_sync.core.find_and_download_subtitle"`
- `mocker.patch("subs_down_n_sync.sync_subtitle_if_needed"` → `mocker.patch("subs_down_n_sync.core.sync_subtitle_if_needed"`
- `mocker.patch("subs_down_n_sync.run"` → `mocker.patch("subs_down_n_sync.cli.run"`

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_core.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Update imports in `tests/test_integration.py`**

Replace:

```python
from exceptions import ...
from subs_down_n_sync import ...
```

With:

```python
from subs_down_n_sync.exceptions import ...
from subs_down_n_sync.core import ...
```

- [ ] **Step 4: Verify `scripts/smoke_test.py` imports**

Open `scripts/smoke_test.py` and replace any `from exceptions import` or `from subs_down_n_sync import` with package equivalents:

```python
from subs_down_n_sync.exceptions import ...
from subs_down_n_sync.core import ...
```

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS, coverage ≥ 90%.

- [ ] **Step 6: Commit**

```bash
git add tests/test_core.py tests/test_integration.py scripts/smoke_test.py
git commit -m "refactor: atualizar testes e scripts para imports do pacote src/"
```

---

### Task 6: Delete old files and update CI

**Files:**

- Delete: `subs_down_n_sync.py`, `exceptions.py`, `pytest.ini`, `ruff.toml`, `requirements.txt`, `requirements-dev.txt`, `.coveragerc`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Delete obsolete files**

```bash
git rm subs_down_n_sync.py exceptions.py pytest.ini ruff.toml requirements.txt requirements-dev.txt
```

If `.coveragerc` exists:

```bash
git rm .coveragerc
```

- [ ] **Step 2: Run tests to confirm nothing broke**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Update `.github/workflows/ci.yml`**

Replace all occurrences of `cache-dependency-path: requirements-dev.txt` with `cache-dependency-path: pyproject.toml`.

Replace all occurrences of `pip install -r requirements-dev.txt` with `pip install -e ".[dev]"`.

- [ ] **Step 4: Run lint to confirm ruff works with new config**

```bash
ruff check .
ruff format --check .
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: migrar para pyproject.toml e pip install -e .[dev]"
```

---

### Task 7: Update `CLAUDE.md` and create `CLAUDE.en.md`

**Files:**

- Modify: `CLAUDE.md`
- Create: `CLAUDE.en.md`

- [ ] **Step 1: Rewrite `CLAUDE.md`** (see pt-BR plan for content)

- [ ] **Step 2: Create `CLAUDE.en.md`** (English translation)

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CLAUDE.en.md
git commit -m "docs: incrementar CLAUDE.md e criar CLAUDE.en.md"
```

---

### Task 8: Update `README.md` and create `README.en.md`

**Files:**

- Modify: `README.md`
- Create: `README.en.md`

- [ ] **Step 1: Update `README.md`** — update Setup, Usage and Development sections to reference `pyproject.toml` instead of `pytest.ini`.

- [ ] **Step 2: Create `README.en.md`** — faithful English translation of `README.md`.

- [ ] **Step 3: Commit**

```bash
git add README.md README.en.md
git commit -m "docs: atualizar README.md e criar README.en.md"
```

---

### Task 9: Create `.en.md` versions of superpowers docs

**Files:**

- Create: `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.en.md`
- Create: `docs/superpowers/specs/2026-04-22-github-pipeline-design.en.md`
- Create: `docs/superpowers/specs/2026-04-22-project-restructure-design.en.md`
- Create: `docs/superpowers/plans/2026-04-19-subs_down_n_sync.en.md`
- Create: `docs/superpowers/plans/2026-04-22-github-pipeline.en.md`
- Create: `docs/superpowers/plans/2026-04-22-project-restructure.en.md`

- [ ] **Step 1: Create spec translations** — faithful English translations of all `.md` files in `docs/superpowers/specs/`.

- [ ] **Step 2: Create plan translations** — faithful English translations of all `.md` files in `docs/superpowers/plans/`.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/
git commit -m "docs: criar versões .en.md de todos os docs de superpowers"
```

---

### Task 10: Final verification

**Files:** none

- [ ] **Step 1: Run full unit test suite**

```bash
pytest -v
```

Expected: all PASS, coverage ≥ 90%.

- [ ] **Step 2: Verify installed entry point**

```bash
subs-down-n-sync --help
```

Expected: usage with `subs-down-n-sync` and `video` argument.

- [ ] **Step 3: Verify `python -m subs_down_n_sync`**

```bash
python -m subs_down_n_sync --help
```

Expected: same output as step above.

- [ ] **Step 4: Run lint**

```bash
ruff check . && ruff format --check .
```

Expected: no errors.

- [ ] **Step 5: Confirm old files were deleted**

```bash
ls subs_down_n_sync.py exceptions.py pytest.ini ruff.toml requirements.txt requirements-dev.txt 2>&1
```

Expected: `No such file or directory` for all.

- [ ] **Step 6: Final commit if needed**

```bash
git status
git add <files>
git commit -m "chore: finalizar reestruturação para src-layout"
```
