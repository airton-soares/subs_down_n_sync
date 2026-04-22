# Design: Reestruturação do Projeto para Padrão Python src-layout

**Data:** 2026-04-22
**Status:** Aprovado

## Objetivo

Reorganizar o projeto para seguir o padrão Python moderno com `src/` layout, consolidar todas as configurações em `pyproject.toml`, criar entry point instalável `subs-down-n-sync`, e estabelecer padrão bilíngue (pt-BR + inglês) para README, CLAUDE.md e docs.

## Estrutura de Diretórios Final

```text
subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py          # exporta __version__
│       ├── __main__.py          # permite `python -m subs_down_n_sync`
│       ├── cli.py               # argparse + entry point main()
│       ├── core.py              # lógica principal (movida de subs_down_n_sync.py)
│       └── exceptions.py        # movido de raiz
├── tests/
│   ├── __init__.py
│   ├── test_core.py             # renomeado de test_subs_down_n_sync.py
│   └── test_integration.py
├── scripts/
│   └── smoke_test.py
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   ├── *.md             # pt-BR
│       │   └── *.en.md          # inglês
│       └── plans/
│           ├── *.md             # pt-BR
│           └── *.en.md          # inglês
├── .github/workflows/ci.yml
├── .gitignore
├── CLAUDE.md                    # pt-BR, incrementado
├── CLAUDE.en.md                 # inglês
├── README.md                    # pt-BR (existente)
├── README.en.md                 # inglês (novo)
└── pyproject.toml               # único arquivo de configuração
```

## pyproject.toml

Consolida `pytest.ini`, `ruff.toml`, `requirements.txt` e `requirements-dev.txt` em arquivo único. Todos os quatro arquivos originais são deletados.

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
```

## Divisão do Código Fonte

### `src/subs_down_n_sync/core.py`

Toda lógica de negócio extraída de `subs_down_n_sync.py`:

- Dataclasses: `SubtitleInfo`, `SyncResult`, `RunSummary`
- Constantes: `VIDEO_EXTENSIONS`, `DEFAULT_LANG`, `SYNC_THRESHOLD_SECONDS`
- Funções: `download_subtitle()`, `sync_subtitle()`, `run()`
- Sem argparse, sem `sys.exit`

### `src/subs_down_n_sync/cli.py`

- Argparse completo
- Função `main()` que chama `run()` e imprime resultado
- `sys.exit` apenas aqui
- Entry point `subs-down-n-sync` aponta para `subs_down_n_sync.cli:main`

### `src/subs_down_n_sync/__init__.py`

```python
__version__ = "0.1.0"

from subs_down_n_sync.core import run

__all__ = ["run", "__version__"]
```

### `src/subs_down_n_sync/__main__.py`

```python
from subs_down_n_sync.cli import main

main()
```

### `src/subs_down_n_sync/exceptions.py`

Movido de `exceptions.py` (raiz) sem alteração de conteúdo.

## Testes

- `tests/test_subs_down_n_sync.py` renomeado para `tests/test_core.py`
- Imports atualizados: `from subs_down_n_sync` → `from subs_down_n_sync.core`
- `tests/test_integration.py` atualiza imports igualmente
- `scripts/smoke_test.py` atualiza imports se necessário

## Padrão Bilíngue

Convenção estabelecida para todos os projetos:

| Arquivo | Idioma |
|---------|--------|
| `README.md` | pt-BR |
| `README.en.md` | inglês |
| `CLAUDE.md` | pt-BR |
| `CLAUDE.en.md` | inglês |
| `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | pt-BR |
| `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.en.md` | inglês |
| `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` | pt-BR |
| `docs/superpowers/plans/YYYY-MM-DD-<topic>.en.md` | inglês |

Conteúdo dos `.en.md`: tradução fiel do `.md` correspondente, sem informação adicional.

## CLAUDE.md Incrementado

Seções a incluir:

- Descrição do projeto e propósito
- Estrutura de diretórios anotada
- Setup de desenvolvimento (`pip install -e ".[dev]"`, ativação do venv)
- Como rodar (`subs-down-n-sync /path/video.mkv` ou `python -m subs_down_n_sync`)
- Como rodar testes (`pytest`, `pytest -m integration`)
- Padrões do projeto:
  - Idioma: identificadores em inglês, comentários/UX em português
  - Commits: Conventional Commits em português
  - Exceções: sempre em `exceptions.py`, importadas explicitamente
  - Linhas em branco entre blocos lógicos dentro de funções
  - Padrão bilíngue para README, CLAUDE.md e docs

## CI Atualizado

Mudanças em `.github/workflows/ci.yml`:

- `pip install -r requirements-dev.txt` → `pip install -e ".[dev]"`
- Referências explícitas a `subs_down_n_sync.py` ou `exceptions.py` → `src/` e `tests/`
- Estrutura dos jobs (lint, unit, integration) permanece igual

## Arquivos Deletados

- `subs_down_n_sync.py` (conteúdo movido para `src/`)
- `exceptions.py` (movido para `src/subs_down_n_sync/exceptions.py`)
- `pytest.ini` (consolidado em `pyproject.toml`)
- `ruff.toml` (consolidado em `pyproject.toml`)
- `requirements.txt` (consolidado em `pyproject.toml`)
- `requirements-dev.txt` (consolidado em `pyproject.toml`)
- `.coveragerc` (configuração de coverage migrada para `[tool.coverage]` em `pyproject.toml`)
