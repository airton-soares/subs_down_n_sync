# Reestruturação do Projeto para src-layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar o projeto para src-layout, consolidar configs em `pyproject.toml`, criar entry point `subs-down-n-sync`, e estabelecer padrão bilíngue (pt-BR + inglês) para README, CLAUDE.md e docs.

**Architecture:** Todo código de negócio migra para `src/subs_down_n_sync/` dividido em `core.py` (lógica), `cli.py` (argparse + entry point) e `exceptions.py`. Configs de pytest, ruff, requirements e coverage consolidam em `pyproject.toml`. Documentação bilíngue criada para README, CLAUDE.md e todos os docs em `docs/superpowers/`.

**Tech Stack:** Python 3.12, setuptools src-layout, pytest, ruff, subliminal, ffsubsync

---

## Mapa de Arquivos

| Ação | Arquivo |
|------|---------|
| Criar | `src/subs_down_n_sync/__init__.py` |
| Criar | `src/subs_down_n_sync/__main__.py` |
| Criar | `src/subs_down_n_sync/core.py` |
| Criar | `src/subs_down_n_sync/cli.py` |
| Criar | `src/subs_down_n_sync/exceptions.py` |
| Criar | `pyproject.toml` |
| Criar | `tests/test_core.py` |
| Criar | `README.en.md` |
| Criar | `CLAUDE.en.md` |
| Criar | `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.en.md` |
| Criar | `docs/superpowers/specs/2026-04-22-github-pipeline-design.en.md` |
| Criar | `docs/superpowers/specs/2026-04-22-project-restructure-design.en.md` |
| Criar | `docs/superpowers/plans/2026-04-19-subs_down_n_sync.en.md` |
| Criar | `docs/superpowers/plans/2026-04-22-github-pipeline.en.md` |
| Criar | `docs/superpowers/plans/2026-04-22-project-restructure.en.md` |
| Modificar | `tests/test_integration.py` |
| Modificar | `scripts/smoke_test.py` |
| Modificar | `CLAUDE.md` |
| Modificar | `README.md` |
| Modificar | `.github/workflows/ci.yml` |
| Deletar | `subs_down_n_sync.py` |
| Deletar | `exceptions.py` |
| Deletar | `pytest.ini` |
| Deletar | `ruff.toml` |
| Deletar | `requirements.txt` |
| Deletar | `requirements-dev.txt` |
| Deletar | `.coveragerc` |

---

### Task 1: Criar `pyproject.toml` e estrutura `src/`

**Files:**

- Create: `pyproject.toml`
- Create: `src/subs_down_n_sync/__init__.py`
- Create: `src/subs_down_n_sync/__main__.py`

- [ ] **Step 1: Criar diretório src**

```bash
mkdir -p src/subs_down_n_sync
```

- [ ] **Step 2: Criar `pyproject.toml`**

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
markers = ["integration: testes que dependem de ffmpeg, ffsubsync e rede"]
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

- [ ] **Step 3: Criar `src/subs_down_n_sync/__init__.py`**

```python
"""subs_down_n_sync: busca e sincroniza legendas."""

from __future__ import annotations

__version__ = "0.1.0"

from subs_down_n_sync.core import run

__all__ = ["run", "__version__"]
```

- [ ] **Step 4: Criar `src/subs_down_n_sync/__main__.py`**

```python
from subs_down_n_sync.cli import main

main()
```

- [ ] **Step 5: Reinstalar o pacote em modo editável**

```bash
pip install -e ".[dev]"
```

Expected: linha `Successfully installed subs-down-n-sync-0.1.0 ...` (ou similar indicando sucesso).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/subs_down_n_sync/__init__.py src/subs_down_n_sync/__main__.py
git commit -m "chore: criar pyproject.toml e estrutura src/subs_down_n_sync"
```

---

### Task 2: Criar `src/subs_down_n_sync/exceptions.py`

**Files:**

- Create: `src/subs_down_n_sync/exceptions.py`

- [ ] **Step 1: Criar o arquivo**

Conteúdo idêntico ao `exceptions.py` da raiz:

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

### Task 3: Criar `src/subs_down_n_sync/core.py`

**Files:**

- Create: `src/subs_down_n_sync/core.py`

Toda a lógica de negócio de `subs_down_n_sync.py` — sem argparse, sem `sys.exit`.

- [ ] **Step 1: Criar o arquivo**

```python
"""Lógica de negócio: download e sincronização de legendas."""

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

    # Não usamos subliminal.save_subtitles porque ele grava os bytes crus no
    # encoding detectado (ex.: cp1252) em um arquivo UTF-8 por convenção, o que
    # produz mojibake quando ferramentas como ffsubsync tentam re-detectar.
    # Em vez disso, pegamos o texto já decodificado e escrevemos em UTF-8.
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

### Task 4: Criar `src/subs_down_n_sync/cli.py`

**Files:**

- Create: `src/subs_down_n_sync/cli.py`

- [ ] **Step 1: Criar o arquivo**

```python
"""Entry point CLI: argparse e impressão de resultados."""

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

- [ ] **Step 2: Verificar que o entry point funciona**

```bash
python -m subs_down_n_sync --help
```

Expected: usage com `subs-down-n-sync` e argumento `video`.

- [ ] **Step 3: Commit**

```bash
git add src/subs_down_n_sync/cli.py
git commit -m "refactor: extrair CLI para src/subs_down_n_sync/cli.py"
```

---

### Task 5: Criar `tests/test_core.py` e atualizar testes

**Files:**

- Create: `tests/test_core.py`
- Modify: `tests/test_integration.py`
- Modify: `scripts/smoke_test.py`

- [ ] **Step 1: Criar `tests/test_core.py`**

Conteúdo idêntico ao `tests/test_subs_down_n_sync.py`, com imports atualizados:

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

Após esses imports, copiar **todo o restante** de `tests/test_subs_down_n_sync.py` a partir da linha 35 (todos os `def test_...`), substituindo:

- `mocker.patch("subs_down_n_sync.subliminal.` → `mocker.patch("subs_down_n_sync.core.subliminal.`
- `mocker.patch("subs_down_n_sync.find_and_download_subtitle"` → `mocker.patch("subs_down_n_sync.core.find_and_download_subtitle"`
- `mocker.patch("subs_down_n_sync.sync_subtitle_if_needed"` → `mocker.patch("subs_down_n_sync.core.sync_subtitle_if_needed"`
- `mocker.patch("subs_down_n_sync.run"` → `mocker.patch("subs_down_n_sync.cli.run"`

- [ ] **Step 2: Rodar testes para verificar que passam**

```bash
pytest tests/test_core.py -v
```

Expected: todos os testes PASS.

- [ ] **Step 3: Atualizar imports em `tests/test_integration.py`**

Substituir:

```python
from exceptions import ...
from subs_down_n_sync import ...
```

Por:

```python
from subs_down_n_sync.exceptions import ...
from subs_down_n_sync.core import ...
```

- [ ] **Step 4: Verificar `scripts/smoke_test.py` imports**

Abrir `scripts/smoke_test.py` e substituir qualquer `from exceptions import` ou `from subs_down_n_sync import` pelos equivalentes do pacote:

```python
from subs_down_n_sync.exceptions import ...
from subs_down_n_sync.core import ...
```

- [ ] **Step 5: Rodar toda a suite**

```bash
pytest -v
```

Expected: todos os testes PASS, cobertura ≥ 90%.

- [ ] **Step 6: Commit**

```bash
git add tests/test_core.py tests/test_integration.py scripts/smoke_test.py
git commit -m "refactor: atualizar testes e scripts para imports do pacote src/"
```

---

### Task 6: Deletar arquivos antigos e atualizar CI

**Files:**

- Delete: `subs_down_n_sync.py`, `exceptions.py`, `pytest.ini`, `ruff.toml`, `requirements.txt`, `requirements-dev.txt`, `.coveragerc`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Deletar arquivos obsoletos**

```bash
git rm subs_down_n_sync.py exceptions.py pytest.ini ruff.toml requirements.txt requirements-dev.txt
```

Se `.coveragerc` existir:

```bash
git rm .coveragerc
```

- [ ] **Step 2: Rodar testes para confirmar nada quebrou**

```bash
pytest -v
```

Expected: todos os testes PASS.

- [ ] **Step 3: Atualizar `.github/workflows/ci.yml`**

Substituir todas as ocorrências de `cache-dependency-path: requirements-dev.txt` por `cache-dependency-path: pyproject.toml`.

Substituir todas as ocorrências de `pip install -r requirements-dev.txt` por `pip install -e ".[dev]"`.

O arquivo final deve ficar assim:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  lint:
    name: Lint (Ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: pyproject.toml

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Ruff format check
        run: ruff format --check .

      - name: Ruff lint
        run: ruff check .

  unit:
    name: Unit tests + coverage
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: pyproject.toml

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Run unit tests with coverage gate
        run: pytest

  integration:
    name: Integration tests (ffsubsync)
    runs-on: ubuntu-latest
    needs: [unit]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: pyproject.toml

      - name: Install ffmpeg
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Cache Sintel trailer fixture
        uses: actions/cache@v4
        with:
          path: tests/fixtures/.cache
          key: sintel-trailer-480p-v1

      - name: Run integration tests
        run: pytest -m integration --no-cov
```

- [ ] **Step 4: Rodar lint para confirmar que ruff funciona com nova config**

```bash
ruff check .
ruff format --check .
```

Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: migrar para pyproject.toml e pip install -e .[dev]"
```

---

### Task 7: Atualizar `CLAUDE.md` e criar `CLAUDE.en.md`

**Files:**

- Modify: `CLAUDE.md`
- Create: `CLAUDE.en.md`

- [ ] **Step 1: Reescrever `CLAUDE.md`**

```markdown
# subs_down_n_sync

CLI Python para buscar e sincronizar legendas automaticamente para filmes e séries. Idioma padrão: **pt-BR**, configurável via `--lang` (qualquer tag BCP 47).

## Estrutura do Projeto

```text
subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py       # exporta __version__ e run
│       ├── __main__.py       # permite python -m subs_down_n_sync
│       ├── cli.py            # argparse + entry point main()
│       ├── core.py           # toda a lógica de negócio
│       └── exceptions.py     # todas as exceções do projeto
├── tests/
│   ├── test_core.py          # testes unitários
│   └── test_integration.py   # testes de integração (ffsubsync real)
├── scripts/
│   └── smoke_test.py         # teste manual contra API real
├── docs/superpowers/
│   ├── specs/                # specs de design (*.md pt-BR, *.en.md inglês)
│   └── plans/                # planos de implementação (*.md pt-BR, *.en.md inglês)
└── pyproject.toml            # todas as configs (deps, pytest, ruff, coverage)
```

## Setup de Desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Instale `ffmpeg` no sistema:

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

## Como Rodar

```bash
# via entry point instalado
subs-down-n-sync /caminho/para/filme.mkv

# via módulo Python
python -m subs_down_n_sync /caminho/para/filme.mkv

# outro idioma
subs-down-n-sync /caminho/para/filme.mkv --lang en
```

Requer variáveis de ambiente:

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

## Como Rodar Testes

```bash
pytest                    # unit tests + coverage gate 90%
pytest --no-cov           # sem gate (útil com -k ou --collect-only)
pytest -m integration     # testes de integração (requer ffmpeg + rede)
pytest -m ""              # tudo (unit + integração)
```

## Lint e Formatação

```bash
ruff format .             # aplica formatação
ruff format --check .     # verifica sem escrever
ruff check .              # lint
ruff check --fix .        # aplica fixes automáticos
```

## Padrões do Projeto

- **Idioma em código:** identificadores sempre em inglês; mensagens UX e comentários em português
- **Commits:** Conventional Commits em português (ex.: `feat: adicionar suporte a...`, `fix: corrigir...`)
- **Exceções:** todas ficam em `exceptions.py`, importadas explicitamente — nunca criadas inline
- **Linhas em branco:** separar blocos lógicos dentro de funções com uma linha em branco
- **Padrão bilíngue:** todo arquivo de documentação tem versão pt-BR (`.md`) e inglês (`.en.md`):
  - `README.md` / `README.en.md`
  - `CLAUDE.md` / `CLAUDE.en.md`
  - `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` / `.en.md`
  - `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` / `.en.md`

## Specs e Planos

- Spec de design original: `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.md`
- Plano de implementação original: `docs/superpowers/plans/2026-04-19-subs_down_n_sync.md`
- Spec de reestruturação: `docs/superpowers/specs/2026-04-22-project-restructure-design.md`
```

- [ ] **Step 2: Criar `CLAUDE.en.md`**

Tradução fiel do `CLAUDE.md` acima para inglês:

```markdown
# subs_down_n_sync

Python CLI to automatically search and synchronize subtitles for movies and TV shows. Default language: **pt-BR**, configurable via `--lang` (any BCP 47 tag).

## Project Structure

```text
subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py       # exports __version__ and run
│       ├── __main__.py       # enables python -m subs_down_n_sync
│       ├── cli.py            # argparse + entry point main()
│       ├── core.py           # all business logic
│       └── exceptions.py     # all project exceptions
├── tests/
│   ├── test_core.py          # unit tests
│   └── test_integration.py   # integration tests (real ffsubsync)
├── scripts/
│   └── smoke_test.py         # manual test against real API
├── docs/superpowers/
│   ├── specs/                # design specs (*.md pt-BR, *.en.md English)
│   └── plans/                # implementation plans (*.md pt-BR, *.en.md English)
└── pyproject.toml            # all configs (deps, pytest, ruff, coverage)
```

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install `ffmpeg` on your system:

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

## How to Run

```bash
# via installed entry point
subs-down-n-sync /path/to/movie.mkv

# via Python module
python -m subs_down_n_sync /path/to/movie.mkv

# other language
subs-down-n-sync /path/to/movie.mkv --lang en
```

Requires environment variables:

```bash
export OPENSUBTITLES_USERNAME="your_username"
export OPENSUBTITLES_PASSWORD="your_password"
```

## How to Run Tests

```bash
pytest                    # unit tests + 90% coverage gate
pytest --no-cov           # without gate (useful with -k or --collect-only)
pytest -m integration     # integration tests (requires ffmpeg + network)
pytest -m ""              # everything (unit + integration)
```

## Lint and Formatting

```bash
ruff format .             # apply formatting
ruff format --check .     # check without writing
ruff check .              # lint
ruff check --fix .        # apply automatic fixes
```

## Project Standards

- **Code language:** identifiers always in English; UX messages and comments in Portuguese
- **Commits:** Conventional Commits in Portuguese (e.g., `feat: adicionar suporte a...`, `fix: corrigir...`)
- **Exceptions:** all exceptions live in `exceptions.py`, imported explicitly — never created inline
- **Blank lines:** separate logical blocks inside functions with one blank line
- **Bilingual standard:** every documentation file has a pt-BR version (`.md`) and English version (`.en.md`):
  - `README.md` / `README.en.md`
  - `CLAUDE.md` / `CLAUDE.en.md`
  - `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` / `.en.md`
  - `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` / `.en.md`

## Specs and Plans

- Original design spec: `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.md`
- Original implementation plan: `docs/superpowers/plans/2026-04-19-subs_down_n_sync.md`
- Restructure spec: `docs/superpowers/specs/2026-04-22-project-restructure-design.md`
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CLAUDE.en.md
git commit -m "docs: incrementar CLAUDE.md e criar CLAUDE.en.md"
```

---

### Task 8: Atualizar `README.md` e criar `README.en.md`

**Files:**

- Modify: `README.md`
- Create: `README.en.md`

- [ ] **Step 1: Atualizar `README.md`**

Atualizar seção de Setup:

```markdown
## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```
```

Atualizar seção de Uso:

```markdown
## Uso

```bash
# Default: pt-BR
subs-down-n-sync /caminho/para/filme.mkv

# Outro idioma (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
subs-down-n-sync /caminho/para/filme.mkv --lang en
subs-down-n-sync /caminho/para/filme.mkv -l es
```
```

Atualizar seção de Desenvolvimento:

```markdown
## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Os testes unitários rodam com gate de cobertura de 90% (configurado em `pyproject.toml`). O CI falha se a cobertura cair abaixo disso.
```

Remover referências a `pytest.ini` — substituir por `pyproject.toml` onde aparecerem.

- [ ] **Step 2: Criar `README.en.md`**

Tradução fiel do `README.md` para inglês. O badge de CI no topo deve ser mantido. Exemplo de estrutura:

```markdown
# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)

Python CLI to download and synchronize subtitles for video files. Default language: **pt-BR**, configurable via flag.

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

## Configuration (one-time)

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
```

Output: `/path/to/movie.<lang>.srt` (e.g., `movie.pt-BR.srt`, `movie.en.srt`). This allows keeping subtitles for the same video in different languages without overwriting each other.

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

## Lint and Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.

```bash
ruff format .           # apply formatting
ruff format --check .   # check without writing (used in CI)
ruff check .            # run lint
ruff check --fix .      # apply automatic fixes
```

CI fails if `ruff format --check` or `ruff check` find issues.

## Integration Tests

The project has two test layers:

- **Unit tests** (default, `pytest`) — fast, mock `subliminal` and `ffsubsync`. No network or external binaries needed beyond Python.
- **Integration tests** (`pytest -m integration`) — exercise real `ffsubsync` with the Sintel trailer (Blender Foundation, Creative Commons). Video is downloaded automatically on first run and cached in `tests/fixtures/.cache/`. Requires `ffmpeg` and `ffsubsync` in PATH and internet access on first run.

How to run each layer:

```bash
pytest                    # unit only (fast)
pytest -m integration     # integration only (downloads ~4 MB video, runs real ffsubsync)
pytest -m ""              # everything (unit + integration)
```

## Manual Smoke Test

To test the full pipeline against a real video from your disk, with real OpenSubtitles credentials:

```bash
export OPENSUBTITLES_USERNAME="..."
export OPENSUBTITLES_PASSWORD="..."
python scripts/smoke_test.py /path/to/movie.mkv
python scripts/smoke_test.py /path/to/movie.mkv --lang en
```

This script consumes real OpenSubtitles API quota and **is not called by `pytest`**. Use it to validate the full end-to-end flow before a release or after changing search/sync logic.
```

- [ ] **Step 3: Commit**

```bash
git add README.md README.en.md
git commit -m "docs: atualizar README.md e criar README.en.md"
```

---

### Task 9: Criar versões `.en.md` dos docs de superpowers

**Files:**

- Create: `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.en.md`
- Create: `docs/superpowers/specs/2026-04-22-github-pipeline-design.en.md`
- Create: `docs/superpowers/specs/2026-04-22-project-restructure-design.en.md`
- Create: `docs/superpowers/plans/2026-04-19-subs_down_n_sync.en.md`
- Create: `docs/superpowers/plans/2026-04-22-github-pipeline.en.md`
- Create: `docs/superpowers/plans/2026-04-22-project-restructure.en.md`

- [ ] **Step 1: Criar traduções das specs**

Para cada arquivo `.md` em `docs/superpowers/specs/`, criar um `.en.md` correspondente com tradução fiel para inglês do conteúdo completo. Os arquivos a traduzir são:

- `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.md`
- `docs/superpowers/specs/2026-04-22-github-pipeline-design.md`
- `docs/superpowers/specs/2026-04-22-project-restructure-design.md`

- [ ] **Step 2: Criar traduções dos plans**

Para cada arquivo `.md` em `docs/superpowers/plans/`, criar um `.en.md` correspondente com tradução fiel para inglês. Os arquivos a traduzir são:

- `docs/superpowers/plans/2026-04-19-subs_down_n_sync.md`
- `docs/superpowers/plans/2026-04-22-github-pipeline.md`
- `docs/superpowers/plans/2026-04-22-project-restructure.md` *(este arquivo — traduzir após completar)*

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/
git commit -m "docs: criar versões .en.md de todos os docs de superpowers"
```

---

### Task 10: Verificação final

**Files:** nenhum novo

- [ ] **Step 1: Rodar suite completa de unit tests**

```bash
pytest -v
```

Expected: todos PASS, cobertura ≥ 90%.

- [ ] **Step 2: Verificar entry point instalado**

```bash
subs-down-n-sync --help
```

Expected: usage com `subs-down-n-sync` e argumento `video`.

- [ ] **Step 3: Verificar `python -m subs_down_n_sync`**

```bash
python -m subs_down_n_sync --help
```

Expected: mesmo output do step anterior.

- [ ] **Step 4: Rodar lint**

```bash
ruff check . && ruff format --check .
```

Expected: sem erros.

- [ ] **Step 5: Confirmar que arquivos antigos foram deletados**

```bash
ls subs_down_n_sync.py exceptions.py pytest.ini ruff.toml requirements.txt requirements-dev.txt 2>&1
```

Expected: `No such file or directory` para todos.

- [ ] **Step 6: Commit final se necessário**

Se houver arquivos modificados não commitados:

```bash
git status
git add <arquivos>
git commit -m "chore: finalizar reestruturação para src-layout"
```
