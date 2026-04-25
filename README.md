# subs_down_n_sync

![CI](https://github.com/airton-soares/subs_down_n_sync/actions/workflows/ci.yml/badge.svg)

CLI Python para baixar e sincronizar legendas para arquivos de vídeo. Idioma padrão: **pt-BR**, configurável via flag `--lang` (qualquer tag BCP 47).

A sincronização usa embeddings semânticos multilíngues ([sentence-transformers](https://www.sbert.net/), modelo `paraphrase-multilingual-MiniLM-L12-v2`) combinados com DTW: baixa uma legenda EN de referência e alinha os cues da legenda alvo aos timestamps da referência por similaridade semântica. Legendas com match exato (hash ou release group) são usadas sem sincronização.

## Setup

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Windows (cmd.exe):

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
```

Instale também o `ffmpeg` no sistema:

```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
```

```powershell
winget install Gyan.FFmpeg          # Windows (winget)
choco install ffmpeg                # Windows (Chocolatey)
scoop install ffmpeg                # Windows (Scoop)
```

Confirme que `ffmpeg` está no `PATH` rodando `ffmpeg -version` em novo terminal.

## Configuração (uma única vez)

Linux/macOS:

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

Windows (PowerShell, sessão atual):

```powershell
$env:OPENSUBTITLES_USERNAME = "seu_usuario"
$env:OPENSUBTITLES_PASSWORD = "sua_senha"
```

Windows (persistente, próximas sessões):

```powershell
setx OPENSUBTITLES_USERNAME "seu_usuario"
setx OPENSUBTITLES_PASSWORD "sua_senha"
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

- **Testes unitários** (padrão, `pytest`) — rápidos, mockam `subliminal` e `sentence_transformers`. Não precisam de rede nem de binários externos além do Python.
- **Testes de integração** (`pytest -m integration`) — exercitam o pipeline real de alinhamento semântico (download do modelo `sentence-transformers` + DTW) sobre legendas reais. Requer acesso à internet no primeiro run para baixar o modelo (~120 MB), cacheado pelo Hugging Face em `~/.cache/huggingface/`.

Como rodar cada camada:

```bash
pytest                    # só unit (rápido)
pytest -m integration     # só integração (baixa modelo de embeddings, roda DTW real)
pytest -m ""              # tudo (unit + integração)
```
