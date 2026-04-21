# subs_down_n_sync

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
