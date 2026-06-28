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
│       ├── core.py              # orquestração: run(), find_and_download_subtitle()
│       ├── credentials.py       # credenciais criptografadas (Fernet + machine-id)
│       ├── matcher.py           # pick_subtitle(), SubtitleInfo, 4 tiers de match
│       ├── audio_sync.py        # SyncResult, sync_subtitle() (ref), sync_by_audio() (whisper)
│       ├── _srt_utils.py        # parsing/formatação SRT (módulo interno)
│       └── exceptions.py        # todas as exceções do projeto
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   └── mini.srt
│   ├── test_audio_sync.py       # testes de audio_sync.py
│   ├── test_core.py             # testes unitários de core.py
│   ├── test_credentials.py      # testes de credentials.py
│   ├── test_integration.py      # testes de integração (marcador: integration)
│   └── test_matcher.py          # testes de matcher.py
├── docs/
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
```

Configure as credenciais do OpenSubtitles:

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

As credenciais também podem ser salvas automaticamente:
no primeiro uso sem env vars, o CLI solicita usuário e senha e os salva em
`~/.config/subs-down-n-sync/credentials.enc` (criptografado com AES-128).
Env vars sempre têm prioridade sobre o arquivo.

## Como rodar

```bash
# Via entry point instalado (após pip install -e ".[dev]")
subs-down-n-sync /caminho/para/filme.mkv
subs-down-n-sync /caminho/para/filme.mkv --lang en

# Processar diretório inteiro (recursivo)
subs-down-n-sync /caminho/para/pasta/
subs-down-n-sync /caminho/para/pasta/ --lang en
subs-down-n-sync /caminho/para/pasta/ --overwrite   # sobrescreve legendas existentes (baixa da API)
subs-down-n-sync /caminho/para/pasta/ --resync      # sincroniza legenda existente sem bater na API
subs-down-n-sync /caminho/para/pasta/ --parallel    # processa até 2 vídeos simultâneos
subs-down-n-sync /caminho/para/filme.mkv --whisper-model base  # modelo Whisper maior (mais preciso)
subs-down-n-sync /caminho/para/filme.mkv --ref-lang es         # idioma original diferente de EN

# Via módulo Python
python -m subs_down_n_sync /caminho/para/filme.mkv
```

## Como rodar os testes

```bash
pytest                    # testes unitários (padrão, com gate de cobertura 90%)
pytest --no-cov           # sem gate (útil com -k ou --collect-only)
pytest -m integration     # testes de integração (baixa modelo sentence-transformers, requer rede)
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
- **Docs bilíngues:** todo arquivo `.md` tem par `.en.md` em inglês (README, CLAUDE)
