# Design: CI Pipeline on GitHub Actions

**Date:** 2026-04-22
**Branch:** `feat/adds-github-pipeline`
**Status:** Approved for implementation

## Objective

Configure a CI pipeline on GitHub Actions for the `subs_down_n_sync` project that, on each pull request and each push to `main`, runs:

1. Code formatting and lint verification (Ruff).
2. Unit tests with **90%** coverage gate (pytest + pytest-cov).
3. Non-manual integration tests (`pytest -m integration`), which exercise real `ffsubsync` against the Sintel trailer.

The manual smoke test in `scripts/smoke_test.py` does **not** enter CI — it consumes real OpenSubtitles API and requires credentials.

## Design Decisions

| Topic | Decision | Reason |
|---|---|---|
| Format/lint tool | Ruff (no Black, no Flake8) | Single tool; fast; covers format + lint + isort. |
| Coverage | pytest-cov with `--cov-fail-under=90` | Real gate; no dependency on external service. |
| Integration tests | Separate job, `needs: [unit]` | Isolates failures; parallelizes lint+unit; doesn't burn minutes if unit breaks. |
| Triggers | `pull_request` (any branch) + `push` on `main` | Early feedback on PR; ensures `main` stays green post-merge. |
| Python matrix | Only 3.12 | Single version aligned with `setuptools<81` requirement. |
| Format posture | CI only checks (`--check`), no auto-format | No bots writing to branch; dev fixes locally. |
| Credentials | None | Unit mocks; integration uses only ffsubsync + public trailer. |
| Organization | Single workflow (`ci.yml`) with 3 jobs | Simplicity; parallelism between lint/unit; integration depends on unit. |

## Files

### New

- `.github/workflows/ci.yml` — workflow with `lint`, `unit`, `integration` jobs.

### Modified

- `pyproject.toml` — consolidates all configuration (replaces ruff.toml, pytest.ini, requirements*.txt, .coveragerc).
- `README.md` — CI badge and lint/format section.

## Jobs

### `lint`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependency:** none
**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with `python-version: '3.12'` and `cache: 'pip'` pointing to `pyproject.toml`.
3. `pip install -e ".[dev]"`
4. `ruff format --check .`
5. `ruff check .`

**Ruff config (in `pyproject.toml`):**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"
```

Selected rules: pycodestyle (E/W), pyflakes (F), isort (I), pyupgrade (UP), bugbear (B), simplify (SIM).

### `unit`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependency:** none (parallel to `lint`)
**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with pip cache.
3. `pip install -e ".[dev]"`
4. `pytest` — inherits defaults from `pyproject.toml` (filters integration tests and applies coverage).

### `integration`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependency:** `needs: [unit]`
**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with pip cache.
3. `sudo apt-get update && sudo apt-get install -y ffmpeg`
4. `pip install -e ".[dev]"`
5. `actions/cache@v4` on `tests/fixtures/.cache` with key `sintel-trailer-480p-v1`.
6. `pytest -m integration --no-cov` (no coverage flags).

**Behavior on download failure:** the `sintel_trailer` fixture in `tests/test_integration.py` runs `pytest.skip` if download fails or if `ffmpeg`/`ffsubsync` are not in PATH. This is intentional: the job stays **green with skip** when external infra (Blender server) is unavailable, avoiding blocked merges due to flakiness.

## Triggers and concurrency

```yaml
on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
```

- `push` on `main` keeps the main branch green.
- `pull_request` (no filter) covers PRs to any branch.
- `concurrency` cancels stale runs on the same ref (useful for force-push / rapid pushes in PRs).
- `permissions: contents: read` applies least privilege (the workflow publishes nothing).

## Status checks (manual post-merge configuration)

After the first pipeline merge to `main`, configure in **Settings → Branches → Branch protection rules → `main`**:

- Require status checks to pass before merging.
- Mark as required: `lint`, `unit`, `integration`.

Configuration done in the GitHub UI, outside the scope of this PR.

## Risks and mitigations

1. **Current coverage below 90%.** The implementation plan must measure coverage before enabling the gate. If < 90%, either write tests to close the gap, or adjust the threshold. The gate is only enabled when the current code passes.
2. **Current formatting outside Ruff standard.** First run of `ruff format .` will produce a diff. The plan includes a step to format and commit before enabling `format --check` in CI.
3. **Trailer download fails.** Handled by `pytest.skip` in the fixture — job stays green with skip. If the Blender server goes down frequently, future mitigation: version the trailer as a repo release asset.
4. **This PR validates the CI it introduces.** Expected and desired. Branch protection should only be enabled after the PR passes at least once.

## Out of scope

- PyPI publication.
- Release automation / deploy.
- External services (Codecov, Coveralls, SonarQube).
- Auto-format bot / pre-commit hooks.
- Dependabot / security scanning.
- Multi-OS matrix (macOS, Windows).
- Tests on multiple Python versions.

Any of these can be added later in separate PRs.

## Success criteria

- CI runs green on PR and on push to `main`.
- The three jobs (`lint`, `unit`, `integration`) appear as distinct checks on the PR.
- `unit` fails if coverage < 90%.
- `lint` fails if there is a formatting diff or lint error.
- `integration` passes (or skips gracefully) against the Sintel trailer.
- No secrets configured in the repo.
- README has CI status badge.
