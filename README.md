# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)

CLI Python para baixar e sincronizar legendas para arquivos de vídeo. Idioma padrão: **pt-BR**, configurável via flag.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Instale também o `ffmpeg` no sistema (usado pelo `ffsubsync`):

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

## Configuração (uma única vez)

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

## Uso

```bash
# Default: pt-BR
python subs_down_n_sync.py /caminho/para/filme.mkv

# Outro idioma (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
python subs_down_n_sync.py /caminho/para/filme.mkv --lang en
python subs_down_n_sync.py /caminho/para/filme.mkv -l es
```

Saída: `/caminho/para/filme.<lang>.srt` (ex.: `filme.pt-BR.srt`, `filme.en.srt`). Isso permite manter legendas do mesmo vídeo em idiomas diferentes sem sobrescrever.

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes unitários rodam com gate de cobertura de 90% (configurado em `pytest.ini`). O CI falha se a cobertura cair abaixo disso.

Para rodar sem o gate (útil ao explorar com `-k` ou `--co`):

```bash
pytest --no-cov
```

## Lint e formatação

O projeto usa [Ruff](https://docs.astral.sh/ruff/) para formatação e lint.

```bash
ruff format .           # aplica formatação
ruff format --check .   # verifica sem escrever (usado no CI)
ruff check .            # roda lint
ruff check --fix .      # aplica fixes automáticos
```

O CI falha se `ruff format --check` ou `ruff check` encontrarem problemas.

## Testes de integração

O projeto tem duas camadas de testes:

- **Testes unitários** (padrão, `pytest`) — rápidos, mockam `subliminal` e `ffsubsync`. Não precisam de rede nem de binários externos além do Python.
- **Testes de integração** (`pytest -m integration`) — exercitam o `ffsubsync` real com o trailer do Sintel (Blender Foundation, Creative Commons). O vídeo é baixado automaticamente na primeira execução e cacheado em `tests/fixtures/.cache/`. Requer `ffmpeg` e `ffsubsync` no PATH e acesso à internet no primeiro run.

Como rodar cada camada:

```bash
pytest                    # só unit (rápido)
pytest -m integration     # só integração (baixa vídeo ~4 MB, roda ffsubsync real)
pytest -m ""              # tudo (unit + integração)
```

## Smoke test manual

Para testar o pipeline completo contra um vídeo real do seu disco, com credenciais reais do OpenSubtitles:

```bash
export OPENSUBTITLES_USERNAME="..."
export OPENSUBTITLES_PASSWORD="..."
python scripts/smoke_test.py /caminho/para/filme.mkv
python scripts/smoke_test.py /caminho/para/filme.mkv --lang en
```

Esse script consome cota real da API do OpenSubtitles e **não é chamado por `pytest`**. Use-o para validar o fluxo completo de ponta a ponta antes de um release ou após alterar a lógica de busca/sincronização.
