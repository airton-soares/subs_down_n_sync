# subs_down_n_sync — Design Spec

## Resumo

Script Python CLI que busca a legenda mais adequada (em qualquer idioma suportado pelo OpenSubtitles) para um arquivo de vídeo (filme/série) e, se necessário, sincroniza automaticamente usando o áudio como referência. Padrão: **pt-BR**, configurável via flag.

## Uso

```bash
python subs_down_n_sync.py /caminho/para/filme.mkv            # pt-BR (padrão)
python subs_down_n_sync.py /caminho/para/filme.mkv --lang en  # inglês
python subs_down_n_sync.py /caminho/para/filme.mkv -l es      # espanhol
```

O valor de `--lang/-l` é uma tag BCP 47: aceita código simples (`en`, `es`, `pt`) ou com região (`pt-BR`, `en-US`). É parseado com `babelfish.Language.fromietf()`.

Saída: arquivo `.<lang>.srt` no mesmo diretório do vídeo, com o mesmo nome base (ex.: `filme.pt-BR.srt`, `filme.en.srt`). Isso evita sobrescrever legendas de idiomas diferentes para o mesmo vídeo.

## Arquitetura

Fluxo sequencial em 3 fases:

```
arquivo de vídeo → [Busca] → [Avaliação + Sincronização] → legenda .srt pronta
```

### Fase 1: Busca de Legendas

Usa a biblioteca `subliminal` para buscar legendas no idioma solicitado nos provedores disponíveis (principalmente OpenSubtitles).

**Prioridade de match:**

1. Match por hash do vídeo (hash OpenSubtitles: primeiros + últimos 64KB) — maior confiança, mesma versão/release
2. Match por nome de release (parser do subliminal extrai grupo, codec, resolução e compara) — boa confiança
3. Melhor nota/downloads nos provedores — fallback

**Credenciais:** lidas de variáveis de ambiente `OPENSUBTITLES_USERNAME` e `OPENSUBTITLES_PASSWORD`.

**Formato:** apenas SRT.

### Fase 2: Avaliação e Sincronização

Após baixar a melhor legenda candidata:

1. Rodar `ffsubsync` comparando a legenda com o áudio do vídeo (detecção de atividade de voz — VAD)
2. Se a diferença média de alinhamento for **< 0.1s**: legenda já está boa, manter a original
3. Se a diferença for **>= 0.1s**: salvar a versão sincronizada

Em ambos os casos, o resultado final é um único arquivo `<nome_do_video>.<lang>.srt` no diretório do vídeo.

### Feedback no Terminal

- Qual legenda foi encontrada (provedor, tipo de match)
- Se sincronização foi necessária e o ajuste aplicado
- Tempo total de execução

## Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| Arquivo de vídeo não existe / formato inválido | Mensagem clara, exit code 1 |
| Código de idioma inválido (não parseável como BCP 47) | Mensagem clara, exit code 2 (erro de CLI) |
| Credenciais do OpenSubtitles não configuradas | Avisa quais variáveis faltam, exit code 1 |
| Nenhuma legenda encontrada para o idioma pedido | Informa o idioma, exit code 1 |
| Falha na sincronização (ffsubsync erro) | Mantém legenda original não-sincronizada, avisa que não sincronizou mas salvou |
| ffmpeg não instalado | Detecta antes de começar, avisa como instalar, exit code 1 |

Nenhum caso silencia o erro.

## Dependências

### Pacotes Python (pip)

- `subliminal` — busca de legendas multi-provedor
- `ffsubsync` — sincronização por áudio (VAD + FFT)

### Dependências de sistema

- `ffmpeg` — usado internamente pelo ffsubsync

## Estrutura do Projeto

```
~/Git/subs_down_n_sync/
├── subs_down_n_sync.py    # script principal
└── requirements.txt       # subliminal, ffsubsync
```

## Setup

```bash
cd ~/Git/subs_down_n_sync
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuracao (uma unica vez)

```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
```

## Decisoes de Design

- **Python em vez de Elixir:** ecossistema de legendas em Python muito mais maduro (subliminal, ffsubsync). Elixir nao tem libs equivalentes.
- **Limiar de 0.1s:** abaixo disso a legenda e considerada bem sincronizada. Acima, ffsubsync corrige.
- **Sempre rodar ffsubsync:** em vez de tentar heuristicas proprias para detectar dessincronizacao, delegamos ao ffsubsync que ja faz analise + correcao.
- **Saida substitui:** a versao sincronizada substitui a original, pois e estritamente melhor.
- **Legenda pre-existente:** se ja existir um `.srt` com o mesmo nome no diretorio do video, o script sobrescreve sem perguntar (comportamento CLI simples, sem interatividade).
- **Idioma configuravel com default pt-BR:** a origem do projeto foi legendas em pt-BR. Mantemos esse default para nao quebrar o uso diario, mas aceitamos `--lang` para qualquer BCP 47 suportado pelo provedor.
- **Nome do arquivo inclui o idioma (`.<lang>.srt`):** permite manter multiplas legendas do mesmo video em idiomas diferentes sem sobrescrever. A tag exata usada e a que o usuario passou (ex.: `pt-BR`, `en`), normalizada via `babelfish` para forma canonica.
