# GitHub Actions CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um pipeline CI no GitHub Actions que roda lint (Ruff), testes unitários com gate de cobertura de 90% e testes de integração (ffsubsync real) em cada PR e em push para `main`.

**Architecture:** Um workflow único `.github/workflows/ci.yml` com três jobs: `lint` e `unit` rodam em paralelo; `integration` depende de `unit` e só roda se os testes unitários passarem. Configurações do Ruff e do coverage ficam em arquivos standalone (`ruff.toml`, `.coveragerc`) para evitar introduzir `pyproject.toml`. Nenhum secret é necessário.

**Tech Stack:** GitHub Actions, Ruff, pytest, pytest-cov, ffmpeg/ffsubsync (instalados pelo runner).

**Spec:** [docs/superpowers/specs/2026-04-22-github-pipeline-design.md](../specs/2026-04-22-github-pipeline-design.md)

**Ordem das tarefas (importante):** As tarefas foram ordenadas para que o CI nasça verde quando for ligado. Primeiro normalizamos o baseline (format + cobertura), depois adicionamos as configurações e só no final ligamos o workflow.

---

## Task 1: Adicionar Ruff e pytest-cov ao requirements-dev

**Files:**
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Editar `requirements-dev.txt`**

Substituir o conteúdo inteiro por:

```
-r requirements.txt
pytest>=8.0
pytest-mock>=3.12
pytest-cov>=5.0
ruff>=0.5
```

- [ ] **Step 2: Instalar as novas deps no venv local**

Run: `source .venv/bin/activate && pip install -r requirements-dev.txt`
Expected: instala `ruff` e `pytest-cov` sem erro. Existing deps ficam no cache.

- [ ] **Step 3: Verificar instalação**

Run: `source .venv/bin/activate && ruff --version && pytest --version`
Expected: imprime versão do Ruff (>=0.5) e do pytest (>=8.0).

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt
git commit -m "chore: adicionar ruff e pytest-cov ao requirements-dev"
```

---

## Task 2: Criar `ruff.toml` e formatar o baseline

**Files:**
- Create: `ruff.toml`
- Modify: todos os arquivos `.py` do repo (via `ruff format` e `ruff check --fix`)

- [ ] **Step 1: Criar `ruff.toml`**

Conteúdo exato:

```toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = []

[format]
quote-style = "double"
```

- [ ] **Step 2: Rodar `ruff format` no repo inteiro**

Run: `source .venv/bin/activate && ruff format .`
Expected: Ruff imprime número de arquivos reformatados (pode ser 0 ou mais). Não pode dar erro de parse.

- [ ] **Step 3: Rodar `ruff check --fix` no repo inteiro**

Run: `source .venv/bin/activate && ruff check --fix .`
Expected: Ruff aplica fixes automáticos (import sort, upgrades de sintaxe). Pode restar violações não-autofixáveis — nesse caso pare aqui, mostre as violações e peça orientação antes de continuar. Não faça edits manuais sem autorização.

- [ ] **Step 4: Verificar que está tudo limpo**

Run: `source .venv/bin/activate && ruff format --check . && ruff check .`
Expected: ambos exit 0. Se algo falhar, investigar antes de prosseguir.

- [ ] **Step 5: Rodar os testes unitários para garantir que formatação não quebrou nada**

Run: `source .venv/bin/activate && pytest -m "not integration"`
Expected: todos os testes passam. `--cov*` ainda não está no addopts, então isso é só unit puro.

- [ ] **Step 6: Commit**

```bash
git add ruff.toml
git add -u
git commit -m "style: aplicar ruff format e ruff check --fix no baseline"
```

---

## Task 3: Medir cobertura atual e decidir gate

**Files:**
- Create: `.coveragerc`

- [ ] **Step 1: Criar `.coveragerc`**

Conteúdo exato:

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

- [ ] **Step 2: Medir cobertura atual**

Run: `source .venv/bin/activate && pytest -m "not integration" --cov=. --cov-report=term-missing`
Expected: imprime tabela de cobertura. Anotar o TOTAL (%).

- [ ] **Step 3: Decidir sobre o gate de 90%**

Três cenários. Siga o que se aplica:

- **Cobertura >= 90%:** prossiga para Step 4.
- **Cobertura entre 80% e 89%:** pare. Mostre ao usuário as linhas descobertas (`term-missing` output) e pergunte se deve escrever testes para fechar o gap antes de ligar o gate, ou baixar o limiar.
- **Cobertura < 80%:** pare. Mostre o output e pergunte ao usuário se quer escrever muitos testes ou baixar o limiar para algo realista (ex.: cobertura atual + 5%).

Não prossiga sem decisão explícita do usuário.

- [ ] **Step 4: Commit do `.coveragerc`**

```bash
git add .coveragerc
git commit -m "chore: adicionar configuracao de coverage"
```

---

## Task 4: Ativar gate de cobertura no `pytest.ini`

**Files:**
- Modify: `pytest.ini`

- [ ] **Step 1: Editar `pytest.ini`**

Substituir o conteúdo inteiro por:

```ini
[pytest]
markers =
    integration: testes de integração que dependem de binários externos (ffmpeg, ffsubsync) e de rede para baixar fixture de vídeo
addopts = -m "not integration" --cov=. --cov-report=term-missing --cov-fail-under=90
```

Se na Task 3 o usuário optou por um limiar diferente de 90, substitua `90` pelo valor acordado.

- [ ] **Step 2: Rodar pytest e confirmar que o gate passa**

Run: `source .venv/bin/activate && pytest`
Expected: testes passam e NÃO imprime `FAIL Required test coverage of X% not reached`. Imprime `Required test coverage of X% reached. Total coverage: Y%`.

Se falhar, volte para Task 3 — o gate não deve ser ligado com cobertura insuficiente.

- [ ] **Step 3: Commit**

```bash
git add pytest.ini
git commit -m "test: ativar gate de cobertura 90% em pytest.ini"
```

---

## Task 5: Criar o workflow `ci.yml`

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Criar o diretório do workflow**

Run: `mkdir -p .github/workflows`
Expected: diretório criado (ou já existente).

- [ ] **Step 2: Criar `.github/workflows/ci.yml`**

Conteúdo exato:

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
          cache-dependency-path: requirements-dev.txt

      - name: Install dev dependencies
        run: pip install -r requirements-dev.txt

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
          cache-dependency-path: requirements-dev.txt

      - name: Install dev dependencies
        run: pip install -r requirements-dev.txt

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
          cache-dependency-path: requirements-dev.txt

      - name: Install ffmpeg
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Install dev dependencies
        run: pip install -r requirements-dev.txt

      - name: Cache Sintel trailer fixture
        uses: actions/cache@v4
        with:
          path: tests/fixtures/.cache
          key: sintel-trailer-480p-v1

      - name: Run integration tests
        run: pytest -m integration
```

- [ ] **Step 3: Validar sintaxe YAML localmente**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: sem output e exit 0. Se der erro de parse, corrija antes de commitar.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: adicionar workflow com jobs lint, unit e integration"
```

---

## Task 6: Documentar CI no README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Ler o README atual**

Run: `cat README.md`
Expected: inspecionar a estrutura atual para inserir badge no topo e seção de lint/CI no lugar certo.

- [ ] **Step 2: Adicionar badge de CI no topo**

Editar [README.md](README.md) para adicionar, imediatamente abaixo da linha `# subs_down_n_sync`, uma linha em branco seguida de:

```markdown
![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)
```

- [ ] **Step 3: Adicionar seção "Lint e formatação"**

Inserir antes da seção "## Testes de integração" (ou ao final da seção "## Desenvolvimento" se essa ordem fizer mais sentido pela estrutura atual):

```markdown
## Lint e formatação

O projeto usa [Ruff](https://docs.astral.sh/ruff/) para formatação e lint.

```bash
ruff format .          # aplica formatação
ruff format --check .  # verifica sem escrever (usado no CI)
ruff check .           # roda lint
ruff check --fix .     # aplica fixes automáticos
```

O CI falha se `ruff format --check` ou `ruff check` encontrarem problemas.
```

- [ ] **Step 4: Verificar cobertura no README**

Atualizar a seção "## Desenvolvimento" para refletir o gate de 90% (ou o valor acordado na Task 3):

```markdown
## Desenvolvimento

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes unitários rodam com um gate de cobertura de 90% (configurado em `pytest.ini`). O CI falha se a cobertura cair abaixo disso.
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: adicionar badge de CI e documentar ruff no README"
```

---

## Task 7: Push e validação do pipeline no GitHub

**Files:**
- Nenhuma alteração local.

- [ ] **Step 1: Push da branch**

Run: `git push -u origin feat/adds-github-pipeline`
Expected: push bem-sucedido; GitHub ou confirmação de remote atualizado.

- [ ] **Step 2: Abrir PR para `main` (se ainda não existir)**

Run: `gh pr create --base main --head feat/adds-github-pipeline --title "ci: adicionar pipeline CI no GitHub Actions" --body "$(cat <<'EOF'
## Summary
- Adiciona workflow `.github/workflows/ci.yml` com jobs lint (Ruff), unit (pytest + cov 90%) e integration (ffsubsync + Sintel)
- Normaliza baseline com `ruff format` e liga o gate de cobertura
- Atualiza README com badge e docs de lint

## Test plan
- [ ] Job lint passa em verde no PR
- [ ] Job unit passa em verde e relata coverage >= gate
- [ ] Job integration passa (ou skipa graciosamente em falha de download)
- [ ] Todos os três jobs aparecem como checks distintos no PR

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"`
Expected: imprime a URL do PR criado.

- [ ] **Step 3: Acompanhar a execução dos jobs**

Run: `gh run watch` (ou `gh run list --workflow=ci.yml --limit 1` para inspecionar).
Expected: os três jobs concluem. Cenários:

- **Tudo verde:** prossiga.
- **Lint falha:** rodar `ruff format .` e `ruff check --fix .` local, commitar e pushar. Se o CI passar no runner mas não local, investigar diferença de versão do Ruff.
- **Unit falha (cov < gate):** rodar `pytest` local para reproduzir; escrever testes ou (com autorização do usuário) ajustar `--cov-fail-under`.
- **Integration falha sem skip:** ler logs; se for erro real no ffsubsync, bug legítimo — investigar. Se for erro de instalação do apt ou de rede, registrar como flakiness e reexecutar.

- [ ] **Step 4: Confirmar com o usuário e deixar branch protection como próxima ação**

Após o CI ficar verde no PR, avisar o usuário:

> CI passou em verde no PR. Para tornar os três jobs obrigatórios antes de merge, vá em **Settings → Branches → Branch protection rules → `main`** e marque `lint`, `unit`, `integration` como required status checks. Essa etapa é manual na UI do GitHub e fica fora deste PR.

Não configurar branch protection via API sem autorização — é mudança em config compartilhada do repo.
