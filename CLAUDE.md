# subs_down_n_sync

CLI Python para busca e sincronização automática de legendas para arquivos de vídeo. Idioma padrão: **pt-BR**, configurável via flag `--lang` (qualquer tag BCP 47).

## Estrutura do projeto

```text
subs_down_n_sync/
├── src/
│   └── subs_down_n_sync/
│       ├── __init__.py          # exporta __version__ e run
│       ├── __main__.py          # permite python -m subs_down_n_sync
│       ├── cli.py               # argparse + entry point main()
│       ├── core.py              # toda a lógica de negócio
│       └── exceptions.py        # todas as exceções do projeto
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   └── mini.srt
│   ├── test_core.py             # testes unitários
│   └── test_integration.py      # testes de integração (marcador: integration)
├── scripts/
│   └── smoke_test.py            # teste manual contra API real
├── docs/
│   └── superpowers/
│       ├── specs/               # design docs (pt-BR + .en.md inglês)
│       └── plans/               # planos de implementação (pt-BR + .en.md inglês)
├── .github/workflows/ci.yml
├── .gitignore
├── CLAUDE.md                    # este arquivo (pt-BR)
├── CLAUDE.en.md                 # tradução em inglês
├── README.md                    # pt-BR
├── README.en.md                 # inglês
└── pyproject.toml               # única fonte de configuração
```

## Setup de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Instale as dependências do sistema:

```bash
# ffmpeg
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS

# alass (binário Rust — baixar release em https://github.com/kaegi/alass/releases)
# Exemplo Linux x86_64:
curl -L https://github.com/kaegi/alass/releases/latest/download/alass-linux-amd64 -o ~/.local/bin/alass
chmod +x ~/.local/bin/alass
```

Configure as credenciais do OpenSubtitles:

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

## Como rodar

```bash
# Via entry point instalado (após pip install -e ".[dev]")
subs-down-n-sync /caminho/para/filme.mkv
subs-down-n-sync /caminho/para/filme.mkv --lang en

# Via módulo Python
python -m subs_down_n_sync /caminho/para/filme.mkv
```

## Como rodar os testes

```bash
pytest                    # testes unitários (padrão, com gate de cobertura 90%)
pytest --no-cov           # sem gate (útil com -k ou --collect-only)
pytest -m integration     # testes de integração (requer ffmpeg, alass e rede)
pytest -m ""              # tudo (unit + integração)
```

## Lint e formatação

```bash
ruff format .           # aplica formatação
ruff format --check .   # verifica sem escrever (usado no CI)
ruff check .            # roda lint
ruff check --fix .      # aplica fixes automáticos
```

## Padrões do projeto

- **Idioma:** identificadores em inglês; comentários e mensagens de UX em português
- **Commits:** Conventional Commits em português (ex.: `feat: adicionar suporte a ...`)
- **Exceções:** todas em `src/subs_down_n_sync/exceptions.py`, importadas explicitamente
- **Linhas em branco:** separar blocos lógicos dentro de funções por uma linha em branco
- **Docs bilíngues:** todo arquivo `.md` tem par `.en.md` em inglês (README, CLAUDE, specs, plans)

## Specs e planos

- Spec original: `docs/superpowers/specs/2026-04-19-subs_down_n_sync-design.md`
- Spec de reestruturação: `docs/superpowers/specs/2026-04-22-project-restructure-design.md`
- Plano original: `docs/superpowers/plans/2026-04-19-subs_down_n_sync.md`
- Plano de reestruturação: `docs/superpowers/plans/2026-04-22-project-restructure.md`
