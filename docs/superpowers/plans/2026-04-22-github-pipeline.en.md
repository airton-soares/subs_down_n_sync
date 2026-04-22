# GitHub Actions CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CI pipeline on GitHub Actions that runs lint (Ruff), unit tests with 90% coverage gate, and integration tests (real ffsubsync) on each PR and push to `main`.

**Architecture:** A single workflow `.github/workflows/ci.yml` with three jobs: `lint` and `unit` run in parallel; `integration` depends on `unit` and only runs if unit tests pass. All configuration lives in `pyproject.toml`. No secrets required.

**Tech Stack:** GitHub Actions, Ruff, pytest, pytest-cov, ffmpeg/ffsubsync (installed by runner).

**Spec:** [docs/superpowers/specs/2026-04-22-github-pipeline-design.md](../specs/2026-04-22-github-pipeline-design.md)

**Task order (important):** Tasks are ordered so that CI is born green when activated. First normalize the baseline (format + coverage), then add configurations, and only at the end enable the workflow.

---

## Task 1: Add Ruff and pytest-cov to dev dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml` dev extras**

Ensure `[project.optional-dependencies]` dev section contains:

```toml
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-cov>=6.0",
    "ruff>=0.9",
]
```

- [ ] **Step 2: Install new deps in local venv**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: installs `ruff` and `pytest-cov` without error.

- [ ] **Step 3: Verify installation**

Run: `source .venv/bin/activate && ruff --version && pytest --version`
Expected: prints Ruff version (>=0.9) and pytest version (>=8.0).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: adicionar ruff e pytest-cov ao pyproject.toml"
```

---

## Task 2: Configure Ruff and format baseline

**Files:**
- Modify: `pyproject.toml` (add ruff config sections)
- Modify: all `.py` files in repo (via `ruff format` and `ruff check --fix`)

- [ ] **Step 1: Ensure `pyproject.toml` has ruff config**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"
```

- [ ] **Step 2: Run `ruff format` on entire repo**

Run: `source .venv/bin/activate && ruff format .`
Expected: Ruff prints number of reformatted files. No parse errors.

- [ ] **Step 3: Run `ruff check --fix` on entire repo**

Run: `source .venv/bin/activate && ruff check --fix .`
Expected: Ruff applies automatic fixes.

- [ ] **Step 4: Verify clean**

Run: `source .venv/bin/activate && ruff format --check . && ruff check .`
Expected: both exit 0.

- [ ] **Step 5: Run unit tests to confirm formatting didn't break anything**

Run: `source .venv/bin/activate && pytest -m "not integration"`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "style: aplicar ruff format e ruff check --fix no baseline"
```

---

## Task 3: Measure current coverage and decide gate

**Files:**
- Modify: `pyproject.toml` (add coverage config)

- [ ] **Step 1: Add coverage config to `pyproject.toml`**

```toml
[tool.coverage.run]
source = ["src/subs_down_n_sync"]

[tool.coverage.report]
fail_under = 90
```

- [ ] **Step 2: Measure current coverage**

Run: `source .venv/bin/activate && pytest -m "not integration" --cov=src/subs_down_n_sync --cov-report=term-missing`
Expected: prints coverage table. Note the TOTAL (%).

- [ ] **Step 3: Decision on 90% gate**

Three scenarios:

- **Coverage >= 90%:** proceed to Step 4.
- **Coverage between 80% and 89%:** stop. Show uncovered lines and ask user whether to write tests or lower threshold.
- **Coverage < 80%:** stop. Show output and ask user.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: adicionar configuração de coverage ao pyproject.toml"
```

---

## Task 4: Enable coverage gate in pytest config

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `[tool.pytest.ini_options]`**

```toml
[tool.pytest.ini_options]
markers = ["integration: testes que dependem de ffmpeg, ffsubsync e rede"]
addopts = "-m 'not integration' --cov=src/subs_down_n_sync --cov-report=term-missing --cov-fail-under=90"
```

- [ ] **Step 2: Run pytest and confirm gate passes**

Run: `source .venv/bin/activate && pytest`
Expected: tests pass and does NOT print `FAIL Required test coverage of X% not reached`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "test: ativar gate de cobertura 90% no pyproject.toml"
```

---

## Task 5: Create `ci.yml` workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create workflow directory**

Run: `mkdir -p .github/workflows`

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

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

- [ ] **Step 3: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output and exit 0.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: adicionar workflow com jobs lint, unit e integration"
```

---

## Task 6: Document CI in README

See `README.md` and `README.en.md` — already updated with CI badge and lint section.

---

## Task 7: Push and validate pipeline on GitHub

- [ ] **Step 1: Push branch**

Run: `git push -u origin chore/repair-project-structure`

- [ ] **Step 2: Open PR to `main`**

- [ ] **Step 3: Monitor job execution**

Expected: all three jobs complete green.

- [ ] **Step 4: Configure branch protection (manual)**

After CI passes green on the PR, go to **Settings → Branches → Branch protection rules → `main`** and mark `lint`, `unit`, `integration` as required status checks. This step is manual in the GitHub UI.
