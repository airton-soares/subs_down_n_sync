# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)

CLI Python para baixar e sincronizar legendas para arquivos de vídeo. Idioma padrão: **pt-BR**, configurável via flag `--lang` (qualquer tag BCP 47).

A sincronização usa o modelo Whisper tiny via [stable-ts](https://github.com/jianfch/stable-ts): alinha os timestamps da legenda baixada ao áudio do vídeo. Legendas com match exato (hash ou release group) são usadas sem sincronização.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Instale também o `ffmpeg` no sistema:

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
subs-down-n-sync /caminho/para/filme.mkv

# Outro idioma (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
subs-down-n-sync /caminho/para/filme.mkv --lang en
subs-down-n-sync /caminho/para/filme.mkv -l es

# Processar diretório inteiro (busca vídeos recursivamente)
subs-down-n-sync /caminho/para/pasta/
subs-down-n-sync /caminho/para/pasta/ --lang en
subs-down-n-sync /caminho/para/pasta/ --overwrite   # sobrescreve legendas existentes
subs-down-n-sync /caminho/para/pasta/ --parallel    # processa até 2 vídeos simultâneos

# Ou via módulo Python
python -m subs_down_n_sync /caminho/para/filme.mkv
```

Ao passar um diretório, vídeos que já têm legenda (`<video>.<lang>.srt`) são pulados por padrão. Use `--overwrite` / `-o` para reprocessar. Use `--parallel` / `-p` para processar até 2 vídeos em paralelo.

Saída: `/caminho/para/filme.<lang>.srt` (ex.: `filme.pt-BR.srt`, `filme.en.srt`). Isso permite manter legendas do mesmo vídeo em idiomas diferentes sem sobrescrever.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Os testes unitários rodam com gate de cobertura de 90% (configurado em `pyproject.toml`). O CI falha se a cobertura cair abaixo disso.

Para rodar sem o gate (útil ao explorar com `-k` ou `--collect-only`):

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

- **Testes unitários** (padrão, `pytest`) — rápidos, mockam `subliminal` e `stable_whisper`. Não precisam de rede nem de binários externos além do Python.
- **Testes de integração** (`pytest -m integration`) — exercitam o `stable-ts` real com o trailer do Sintel (Blender Foundation, Creative Commons). O vídeo é baixado automaticamente na primeira execução e cacheado em `tests/fixtures/.cache/`. Requer `ffmpeg` no PATH e acesso à internet no primeiro run.

Como rodar cada camada:

```bash
pytest                    # só unit (rápido)
pytest -m integration     # só integração (baixa vídeo ~4 MB, roda stable-ts real)
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
