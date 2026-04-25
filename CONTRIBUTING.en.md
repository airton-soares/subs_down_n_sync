# How to contribute

Thanks for your interest! Here's how to get started.

## Reporting a bug

Open an [issue](https://github.com/airton-soares/subs_down_n_sync/issues/new?template=bug_report.yml) describing the problem.

## Suggesting a feature

Open an [issue](https://github.com/airton-soares/subs_down_n_sync/issues/new?template=feature_request.yml) describing the use case.

## Submitting code

1. Fork the repository and clone it locally
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   pip install -e ".[dev]"
   ```
3. Create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   # or
   git checkout -b fix/my-bug
   ```
4. Commit following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add support for X` — new feature (minor bump)
   - `fix: correct Y` — bug fix (patch bump)
   - `docs: update README` — documentation (no bump)
   - `BREAKING CHANGE` in footer — incompatible change (major bump)
5. Run the tests (90% coverage minimum required):
   ```bash
   pytest
   ```
6. Open a Pull Request to `main`

## Project standards

- Identifiers in English; comments and UX messages in Portuguese
- All exceptions in `src/subs_down_n_sync/exceptions.py`
- Lint and formatting via Ruff: `ruff check . && ruff format --check .`
