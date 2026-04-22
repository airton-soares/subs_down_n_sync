# Design: Pipeline CI no GitHub Actions

**Data:** 2026-04-22
**Branch:** `feat/adds-github-pipeline`
**Status:** Aprovado para implementação

## Objetivo

Configurar um pipeline de CI no GitHub Actions para o projeto `subs_down_n_sync` que, em cada pull request e em cada push para `main`, execute:

1. Verificação de formatação e lint do código (Ruff).
2. Testes unitários com gate de cobertura de **90%** (pytest + pytest-cov).
3. Testes de integração não-manuais (`pytest -m integration`), que exercitam `ffsubsync` real contra o trailer do Sintel.

O smoke test manual em `scripts/smoke_test.py` **não** entra no CI — ele consome API real do OpenSubtitles e exige credenciais.

## Decisões de design

| Tópico | Decisão | Motivo |
|---|---|---|
| Ferramenta de format/lint | Ruff (sem Black, sem Flake8) | Uma ferramenta só; rápido; cobre format + lint + isort. |
| Cobertura | pytest-cov com `--cov-fail-under=90` | Gate real; sem dependência de serviço externo. |
| Testes de integração | Job separado, `needs: [unit]` | Isola falhas; paraleliza lint+unit; não queima minutos se unit quebra. |
| Triggers | `pull_request` (qualquer branch) + `push` em `main` | Feedback cedo em PR; garante `main` verde pós-merge. |
| Matriz Python | Só 3.12 | Versão única alinhada ao `setuptools<81` do requirements. |
| Postura de format | CI só verifica (`--check`), sem auto-format | Sem bots escrevendo no branch; dev corrige local. |
| Credenciais | Nenhuma | Unit mocka; integração usa só ffsubsync + trailer público. |
| Organização | Workflow único (`ci.yml`) com 3 jobs | Simplicidade; paralelismo entre lint/unit; integration depende de unit. |

## Arquivos

### Novos

- `.github/workflows/ci.yml` — workflow com jobs `lint`, `unit`, `integration`.
- `ruff.toml` — config standalone do Ruff (sem introduzir `pyproject.toml`).
- `.coveragerc` — config standalone do coverage.

### Alterados

- `requirements-dev.txt` — adicionar `ruff` e `pytest-cov`.
- `pytest.ini` — adicionar flags de cobertura ao `addopts` existente.
- `README.md` — badge do CI e seção curta sobre lint/format.

## Jobs

### `lint`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependência:** nenhuma
**Passos:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` com `python-version: '3.12'` e `cache: 'pip'` apontando para `requirements-dev.txt`.
3. `pip install -r requirements-dev.txt`
4. `ruff format --check .`
5. `ruff check .`

**Config `ruff.toml`:**

```toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = []

[format]
quote-style = "double"
```

Regras selecionadas: pycodestyle (E/W), pyflakes (F), isort (I), pyupgrade (UP), bugbear (B), simplify (SIM).

### `unit`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependência:** nenhuma (paralelo ao `lint`)
**Passos:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` com cache de pip.
3. `pip install -r requirements-dev.txt`
4. `pytest` — herda o default de `pytest.ini` (já filtra integração e aplica cov).

**Alteração em `pytest.ini`:**

```ini
[pytest]
markers =
    integration: testes de integração que dependem de binários externos (ffmpeg, ffsubsync) e de rede para baixar fixture de vídeo
addopts = -m "not integration" --cov=. --cov-report=term-missing --cov-fail-under=90
```

**Config `.coveragerc`:**

```ini
[run]
branch = True
source = .
omit =
    tests/*
    scripts/*
    .venv/*

[report]
exclude_lines =
    pragma: no cover
    if __name__ == .__main__.:
    raise NotImplementedError
```

`tests/` e `scripts/` ficam fora da cobertura: a pasta de testes não deve medir a si mesma, e `scripts/smoke_test.py` é código manual que nunca roda no CI.

### `integration`

**Runner:** `ubuntu-latest`
**Python:** 3.12
**Dependência:** `needs: [unit]`
**Passos:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` com cache de pip.
3. `sudo apt-get update && sudo apt-get install -y ffmpeg`
4. `pip install -r requirements-dev.txt` (traz `ffsubsync` via `requirements.txt`).
5. `actions/cache@v4` em `tests/fixtures/.cache` com chave `sintel-trailer-480p-v1`.
6. `pytest -m integration` (sem flags de cobertura).

**Comportamento em caso de falha de download:** a fixture `sintel_trailer` em [tests/test_integration.py](tests/test_integration.py) já executa `pytest.skip` se o download falhar ou se `ffmpeg`/`ffsubsync` não estiverem no PATH. Isso é intencional: o job fica **verde com skip** quando infra externa (servidor Blender) está indisponível, evitando bloquear merge por flakiness.

## Triggers e concurrency

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

- `push` em `main` mantém o branch principal verde.
- `pull_request` (sem filtro) cobre PRs para qualquer branch.
- `concurrency` cancela runs obsoletas no mesmo ref (útil em force-push / pushes rápidos em PRs).
- `permissions: contents: read` aplica least privilege (o workflow não publica nada).

## Status checks (configuração manual pós-merge)

Após o primeiro merge do pipeline em `main`, configurar em **Settings → Branches → Branch protection rules → `main`**:

- Require status checks to pass before merging.
- Marcar como required: `lint`, `unit`, `integration`.

Configuração feita na UI do GitHub, fora do escopo deste PR.

## Riscos e mitigações

1. **Cobertura atual abaixo de 90%.** O plano de implementação deve medir cobertura antes de ativar o gate. Se < 90%, ou escrevemos testes para fechar o gap, ou ajustamos o limiar. O gate só é ligado quando o código atual passa.
2. **Formatação atual fora do padrão Ruff.** Primeira execução do `ruff format .` vai produzir diff. O plano inclui um passo para formatar e commitar antes de ligar `format --check` no CI.
3. **Download do trailer falha.** Tratado por `pytest.skip` na fixture — job fica verde com skip. Se o servidor Blender cair com frequência, mitigação futura: versionar o trailer como release asset do repo.
4. **Este próprio PR valida o CI que ele introduz.** Esperado e desejado. Branch protection só deve ser ligada depois que o PR passar pelo menos uma vez.

## Fora do escopo

- Publicação em PyPI.
- Release automation / deploy.
- Serviços externos (Codecov, Coveralls, SonarQube).
- Auto-format bot / pre-commit hooks.
- Dependabot / security scanning.
- Matriz multi-OS (macOS, Windows).
- Testes em múltiplas versões de Python.

Qualquer um desses pode ser adicionado depois em PRs separados.

## Critério de sucesso

- CI roda em verde em PR e em push para `main`.
- Os três jobs (`lint`, `unit`, `integration`) aparecem como checks distintos no PR.
- `unit` falha se cobertura < 90%.
- `lint` falha se há diff de formatação ou lint error.
- `integration` passa (ou skipa graciosamente) contra o trailer do Sintel.
- Nenhum secret configurado no repo.
- README traz badge de status do CI.
