# subs_down_n_sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI Python que recebe um arquivo de vídeo e um código de idioma (flag `--lang/-l`, default `pt-BR`), busca a legenda mais adequada via `subliminal`, sincroniza com `ffsubsync` quando necessário (>= 0.1s de offset) e salva `<nome_do_video>.<lang>.srt` ao lado do vídeo.

**Arquitetura:** Script único com funções puras orquestradas por um `main()`. Pipeline sequencial em 3 fases: (1) validação de entrada + credenciais + `ffmpeg`; (2) busca/download via `subliminal`; (3) avaliação de sincronia via `ffsubsync` + substituição condicional. Erros propagam como exceções tipadas capturadas no `main`, que converte em mensagem legível + exit code.

**Tech Stack:** Python 3.10+, `subliminal`, `ffsubsync`, `pytest` (testes), `ffmpeg` (binário de sistema).

---

## File Structure

- `subs_down_n_sync.py` — módulo principal com as funções puras (`check_ffmpeg`, `load_credentials`, `find_and_download_subtitle`, `sync_subtitle_if_needed`, `finalize_output_path`, `run`) e o `main()` CLI. Executável diretamente via `python subs_down_n_sync.py ...`.
- `requirements.txt` — dependências de runtime.
- `requirements-dev.txt` — `pytest` + `pytest-mock`.
- `tests/test_subs_down_n_sync.py` — testes unitários das funções, mockando I/O (subliminal, ffsubsync, subprocess).
- `tests/fixtures/` — arquivos mínimos de apoio (ex: um `.srt` válido curto).
- `.gitignore` — ignora `.venv`, `__pycache__`, `*.pyc`, `.pytest_cache`.
- `README.md` — instruções de setup e uso (espelha a spec).

Decomposição: funções pequenas e isoladas por responsabilidade (validação, busca, sync). Cada uma é testável mockando a borda externa. `main()` é o único ponto com side effects de I/O para terminal e exit code.

---

## Task 1: Bootstrap do projeto

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Criar `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.srt.bak
```

- [ ] **Step 2: Criar `requirements.txt`**

```
subliminal>=2.2
ffsubsync>=0.4.25
```

- [ ] **Step 3: Criar `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
pytest-mock>=3.12
```

- [ ] **Step 4: Criar `tests/__init__.py` (vazio)**

Arquivo vazio apenas para marcar o diretório como pacote.

- [ ] **Step 5: Criar `tests/fixtures/.gitkeep` (vazio)**

Placeholder para manter o diretório no git.

- [ ] **Step 6: Criar o venv e instalar dev deps**

Run:
```bash
cd ~/Git/subs_down_n_sync
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Expected: instalação sem erros. `pytest --version` retorna 8.x.

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt tests/__init__.py tests/fixtures/.gitkeep
git commit -m "chore: bootstrap do projeto (deps, gitignore, estrutura de testes)"
```

---

## Task 2: Esqueleto do módulo + CLI entrypoint

**Files:**
- Create: `subs_down_n_sync.py`
- Test: `tests/test_subs_down_n_sync.py`

- [ ] **Step 1: Escrever teste que falha — `main()` sem args retorna exit code 2**

Em `tests/test_subs_down_n_sync.py`:

```python
import pytest
from subs_down_n_sync import main


def test_main_sem_args_erra(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "uso" in captured.err.lower() or "usage" in captured.err.lower()
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_subs_down_n_sync.py::test_main_sem_args_erra -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'subs_down_n_sync'`.

- [ ] **Step 3: Criar `subs_down_n_sync.py` com esqueleto mínimo**

```python
"""subs_down_n_sync: busca e sincroniza legendas pt-BR."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs_down_n_sync",
        description="Busca e sincroniza legenda pt-BR para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # A lógica real virá nas próximas tasks.
    print(f"video: {args.video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_subs_down_n_sync.py::test_main_sem_args_erra -v`
Expected: PASS. (argparse dispara `SystemExit(2)` automaticamente quando o argumento posicional está ausente.)

- [ ] **Step 5: Smoke test manual**

Run: `.venv/bin/python subs_down_n_sync.py /tmp/fake.mkv`
Expected: imprime `video: /tmp/fake.mkv` e exit 0.

- [ ] **Step 6: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: esqueleto do CLI com parsing de argumentos"
```

---

## Task 3: Validação do arquivo de vídeo

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

A spec diz: "Arquivo de vídeo não existe / formato inválido → Mensagem clara, exit code 1". Formatos aceitos: extensões comuns de vídeo (`.mkv`, `.mp4`, `.avi`, `.mov`, `.m4v`, `.wmv`, `.flv`, `.webm`).

- [ ] **Step 1: Escrever testes que falham**

Adicionar ao topo do arquivo de teste:

```python
from pathlib import Path
from subs_down_n_sync import validate_video_path, InvalidVideoError
```

E os casos de teste:

```python
def test_validate_video_path_ok(tmp_path):
    f = tmp_path / "filme.mkv"
    f.write_bytes(b"\x00" * 10)
    assert validate_video_path(str(f)) == f


def test_validate_video_path_inexistente(tmp_path):
    with pytest.raises(InvalidVideoError, match="não existe"):
        validate_video_path(str(tmp_path / "sumiu.mkv"))


def test_validate_video_path_extensao_invalida(tmp_path):
    f = tmp_path / "nota.txt"
    f.write_text("oi")
    with pytest.raises(InvalidVideoError, match="extensão"):
        validate_video_path(str(f))


def test_validate_video_path_diretorio(tmp_path):
    with pytest.raises(InvalidVideoError, match="não é um arquivo"):
        validate_video_path(str(tmp_path))
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k validate_video_path`
Expected: 4 FAILs — `ImportError: cannot import name 'validate_video_path'`.

- [ ] **Step 3: Implementar validação**

Adicionar em `subs_down_n_sync.py` (acima de `main`):

```python
from pathlib import Path

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}


class SubsDownError(Exception):
    """Erro base do script — mensagem é o que vai para o usuário."""


class InvalidVideoError(SubsDownError):
    pass


def validate_video_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.exists():
        raise InvalidVideoError(f"Arquivo de vídeo não existe: {p}")
    if not p.is_file():
        raise InvalidVideoError(f"Caminho não é um arquivo: {p}")
    if p.suffix.lower() not in VIDEO_EXTENSIONS:
        raise InvalidVideoError(
            f"Extensão não suportada ({p.suffix}). "
            f"Esperado um destes: {sorted(VIDEO_EXTENSIONS)}"
        )
    return p
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k validate_video_path`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: validação do arquivo de vídeo de entrada"
```

---

## Task 4: Checagem do binário `ffmpeg`

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

- [ ] **Step 1: Escrever testes que falham**

```python
from subs_down_n_sync import check_ffmpeg, MissingDependencyError


def test_check_ffmpeg_presente(mocker):
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
    check_ffmpeg()  # não deve levantar


def test_check_ffmpeg_ausente(mocker):
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(MissingDependencyError, match="ffmpeg"):
        check_ffmpeg()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k check_ffmpeg`
Expected: 2 FAILs — `ImportError`.

- [ ] **Step 3: Implementar `check_ffmpeg` + exceção**

Em `subs_down_n_sync.py`, logo após `InvalidVideoError`:

```python
import shutil


class MissingDependencyError(SubsDownError):
    pass


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MissingDependencyError(
            "ffmpeg não encontrado no PATH. "
            "Instale com: sudo apt install ffmpeg  (ou equivalente na sua distro)."
        )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k check_ffmpeg`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: checagem do binário ffmpeg no PATH"
```

---

## Task 5: Carregamento de credenciais do OpenSubtitles

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

- [ ] **Step 1: Escrever testes que falham**

```python
from subs_down_n_sync import load_credentials, MissingCredentialsError


def test_load_credentials_ok(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "joao")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "senha123")
    assert load_credentials() == ("joao", "senha123")


def test_load_credentials_faltando_username(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "x")
    with pytest.raises(MissingCredentialsError, match="OPENSUBTITLES_USERNAME"):
        load_credentials()


def test_load_credentials_faltando_ambos(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_PASSWORD", raising=False)
    with pytest.raises(MissingCredentialsError) as exc:
        load_credentials()
    assert "OPENSUBTITLES_USERNAME" in str(exc.value)
    assert "OPENSUBTITLES_PASSWORD" in str(exc.value)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k load_credentials`
Expected: 3 FAILs — `ImportError`.

- [ ] **Step 3: Implementar `load_credentials`**

Em `subs_down_n_sync.py`:

```python
import os


class MissingCredentialsError(SubsDownError):
    pass


def load_credentials() -> tuple[str, str]:
    user = os.environ.get("OPENSUBTITLES_USERNAME")
    pwd = os.environ.get("OPENSUBTITLES_PASSWORD")
    missing = [
        name
        for name, val in (
            ("OPENSUBTITLES_USERNAME", user),
            ("OPENSUBTITLES_PASSWORD", pwd),
        )
        if not val
    ]
    if missing:
        raise MissingCredentialsError(
            "Variáveis de ambiente obrigatórias faltando: " + ", ".join(missing)
        )
    return user, pwd  # type: ignore[return-value]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k load_credentials`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: leitura de credenciais do OpenSubtitles via env vars"
```

---

## Task 6: Parse de idioma + busca e download via `subliminal`

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

Esta task combina dois pedaços que eram separados no plano original: parse do código de idioma (BCP 47) e busca/download da legenda. Precisam aparecer juntos porque os testes da busca dependem do parse.

Nota sobre `subliminal`: a API alta-nível é `subliminal.scan_video(path) → Video`, `subliminal.download_best_subtitles({video}, {Language(...)}, providers=..., provider_configs=...) → {Video: [Subtitle]}` e `subliminal.save_subtitles(video, subtitles) → [Subtitle]`. O `Subtitle` traz atributos como `provider_name`, `hearing_impaired`, `matches` (set com strings como `"hash"`, `"release_group"`, etc.). Essa info alimenta o feedback da spec ("provedor, tipo de match").

Nota sobre idioma: aceitamos BCP 47 (`pt`, `pt-BR`, `en`, `en-US`, `es`, `ja`, etc.) e parseamos com `babelfish.Language.fromietf()`. Erros de parsing viram `InvalidLanguageError`.

- [ ] **Step 1: Escrever testes que falham**

```python
from subs_down_n_sync import (
    parse_language,
    find_and_download_subtitle,
    SubtitleNotFoundError,
    InvalidLanguageError,
    SubtitleInfo,
)
from babelfish import Language


def test_parse_language_pt_br():
    lang = parse_language("pt-BR")
    assert lang.alpha3 == "por"
    assert lang.country is not None and lang.country.alpha2 == "BR"


def test_parse_language_en_simples():
    lang = parse_language("en")
    assert lang.alpha3 == "eng"


def test_parse_language_es():
    lang = parse_language("es")
    assert lang.alpha3 == "spa"


def test_parse_language_invalido():
    with pytest.raises(InvalidLanguageError, match="xx-YY"):
        parse_language("xx-YY")


def test_find_and_download_subtitle_ok(tmp_path, mocker):
    video_path = tmp_path / "Filme.2024.1080p.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock(name="Video")
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"hash", "release_group"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )

    def fake_save(video, subs, directory=None):
        out = tmp_path / "Filme.2024.1080p.pt-BR.srt"
        out.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return [subs[0]]

    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles", side_effect=fake_save
    )

    srt_path, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )

    assert srt_path.exists()
    assert srt_path.suffix == ".srt"
    assert info.provider == "opensubtitles"
    assert info.match_type == "hash"  # hash tem prioridade


def test_find_and_download_subtitle_sem_resultado(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("eng")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: []},
    )

    with pytest.raises(SubtitleNotFoundError, match="eng"):
        find_and_download_subtitle(video_path, language=lang, credentials=("u", "p"))


def test_match_type_release_quando_nao_tem_hash(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"release_group", "resolution"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles",
        side_effect=lambda v, s, directory=None: (
            (tmp_path / "Filme.pt-BR.srt").write_text("x") or [s[0]]
        ),
    )

    _, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )
    assert info.match_type == "release"


def test_match_type_fallback(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"title"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles",
        side_effect=lambda v, s, directory=None: (
            (tmp_path / "Filme.pt-BR.srt").write_text("x") or [s[0]]
        ),
    )

    _, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )
    assert info.match_type == "fallback"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k "parse_language or find_and_download or match_type"`
Expected: falhas por `ImportError`.

- [ ] **Step 3: Implementar `parse_language`, `find_and_download_subtitle` e dependências**

Adicionar em `subs_down_n_sync.py`:

```python
from dataclasses import dataclass

import subliminal
from babelfish import Language


class InvalidLanguageError(SubsDownError):
    pass


class SubtitleNotFoundError(SubsDownError):
    pass


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"


def parse_language(raw: str) -> Language:
    try:
        return Language.fromietf(raw)
    except (ValueError, Exception) as e:
        raise InvalidLanguageError(
            f"Código de idioma inválido: {raw!r}. "
            f"Use tags BCP 47 como 'pt-BR', 'en', 'es', 'ja'."
        ) from e


def _classify_match(matches: set[str]) -> str:
    if "hash" in matches:
        return "hash"
    if "release_group" in matches:
        return "release"
    return "fallback"


def find_and_download_subtitle(
    video_path: Path,
    language: Language,
    credentials: tuple[str, str],
) -> tuple[Path, SubtitleInfo]:
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    provider_configs = {
        "opensubtitles": {"username": user, "password": pwd},
    }
    results = subliminal.download_best_subtitles(
        {video},
        {language},
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    subs = results.get(video, [])
    if not subs:
        raise SubtitleNotFoundError(
            f"Nenhuma legenda em {language} encontrada para: {video_path.name}"
        )
    subtitle = subs[0]
    saved = subliminal.save_subtitles(video, [subtitle], directory=str(video_path.parent))
    if not saved:
        raise SubtitleNotFoundError(
            f"subliminal não conseguiu salvar a legenda para: {video_path.name}"
        )
    # subliminal.save_subtitles grava como <nome>.<lang>.srt; localizamos o arquivo.
    candidates = sorted(
        video_path.parent.glob(f"{video_path.stem}*.srt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SubtitleNotFoundError(
            f"Arquivo .srt não apareceu no diretório após download: {video_path.parent}"
        )
    srt_path = candidates[0]
    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=_classify_match(set(subtitle.matches or [])),
    )
    return srt_path, info
```

Nota sobre a mensagem de `SubtitleNotFoundError`: `str(Language("eng"))` retorna `"eng"` (3 letras ISO 639-3), e `str(Language("por", country="BR"))` retorna `"pob"` ou `"por-BR"` dependendo da versão do babelfish. A asserção do teste (`match="eng"`) valida que o código aparece na mensagem — suficiente para feedback humano.

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k "parse_language or find_and_download or match_type"`
Expected: 7 PASS (4 de parse_language + 4 de find_and_download/match_type — total 8 se contar o `ok`; conferir contagem real).

- [ ] **Step 5: Commit**

Duas opções, escolher baseado em volume da alteração — **preferência: dois commits** para manter escopo atômico:

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: parse de idioma BCP 47 para busca de legendas"
# (se fez tudo junto, apenas um commit abaixo:)
git commit -m "feat: busca e download de legenda via subliminal com idioma configurável"
```

---

## Task 7: Sincronização da legenda via `ffsubsync`

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

A estratégia aqui difere da spec por um ponto pragmático: `ffsubsync` não expõe cleanly o "offset médio" como API — ele tem CLI e a API interna ajusta o SRT já de saída. Vamos usar a abordagem: (1) rodar `ffsubsync video.mkv -i legenda.srt -o legenda.sync.srt` via subprocess; (2) comparar os timestamps do original vs sincronizado — se a diferença média absoluta for < 0.1s, descartar o sincronizado e manter o original; senão, substituir. Isso respeita o critério de 0.1s da spec sem depender de internals do ffsubsync.

- [ ] **Step 1: Criar fixture de SRT**

Criar `tests/fixtures/mini.srt`:

```
1
00:00:01,000 --> 00:00:02,000
linha 1

2
00:00:05,000 --> 00:00:06,000
linha 2
```

- [ ] **Step 2: Escrever testes que falham**

```python
import shutil as shutil_  # evita colisão com a var mockada em outros testes
from subs_down_n_sync import (
    sync_subtitle_if_needed,
    SyncResult,
    SubtitleSyncError,
    _mean_offset_seconds,
    _parse_srt_timestamps,
)


FIXTURE = Path(__file__).parent / "fixtures" / "mini.srt"


def test_parse_srt_timestamps():
    starts = _parse_srt_timestamps(FIXTURE.read_text())
    # dois blocos: 1.0s e 5.0s
    assert starts == [1.0, 5.0]


def test_mean_offset_seconds_zero():
    assert _mean_offset_seconds([1.0, 5.0], [1.0, 5.0]) == 0.0


def test_mean_offset_seconds_positivo():
    # shift uniforme de 0.5s
    assert _mean_offset_seconds([1.0, 5.0], [1.5, 5.5]) == pytest.approx(0.5)


def test_mean_offset_tamanhos_diferentes_usa_min():
    # se o ffsubsync remover/adicionar cues, comparamos só o overlap.
    assert _mean_offset_seconds([1.0, 5.0, 10.0], [1.5, 5.5]) == pytest.approx(0.5)


def test_sync_nao_necessario_mantem_original(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    def fake_run(cmd, capture_output, text, check):  # noqa: ARG001
        out = Path([a for a in cmd if a.endswith(".sync.srt")][0])
        # saída "quase igual" (0.05s de shift < 0.1s)
        out.write_text(
            "1\n00:00:01,050 --> 00:00:02,050\nlinha 1\n\n"
            "2\n00:00:05,050 --> 00:00:06,050\nlinha 2\n"
        )
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle_if_needed(video, srt)
    assert result == SyncResult(synced=False, offset_seconds=pytest.approx(0.05))
    # arquivo original permanece com conteúdo da fixture
    assert srt.read_text() == FIXTURE.read_text()


def test_sync_necessario_substitui(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    synced_text = (
        "1\n00:00:03,000 --> 00:00:04,000\nlinha 1\n\n"
        "2\n00:00:07,000 --> 00:00:08,000\nlinha 2\n"
    )

    def fake_run(cmd, capture_output, text, check):  # noqa: ARG001
        out = Path([a for a in cmd if a.endswith(".sync.srt")][0])
        out.write_text(synced_text)
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle_if_needed(video, srt)
    assert result.synced is True
    assert result.offset_seconds == pytest.approx(2.0)
    assert srt.read_text() == synced_text


def test_sync_falha_mantem_original(tmp_path, mocker):
    import subprocess

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "ffsubsync", stderr="boom"),
    )

    with pytest.raises(SubtitleSyncError, match="ffsubsync"):
        sync_subtitle_if_needed(video, srt)
    # original intacto
    assert srt.read_text() == FIXTURE.read_text()
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k "sync or offset or parse_srt"`
Expected: falhas por `ImportError`.

- [ ] **Step 4: Implementar `_parse_srt_timestamps`, `_mean_offset_seconds`, `sync_subtitle_if_needed`**

Adicionar em `subs_down_n_sync.py`:

```python
import re
import subprocess


class SubtitleSyncError(SubsDownError):
    pass


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float


_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)


def _parse_srt_timestamps(srt_text: str) -> list[float]:
    out: list[float] = []
    for h, m, s, ms in _TS_RE.findall(srt_text):
        out.append(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000)
    return out


def _mean_offset_seconds(orig: list[float], synced: list[float]) -> float:
    n = min(len(orig), len(synced))
    if n == 0:
        return 0.0
    total = sum(abs(synced[i] - orig[i]) for i in range(n))
    return total / n


SYNC_THRESHOLD_SECONDS = 0.1


def sync_subtitle_if_needed(video_path: Path, srt_path: Path) -> SyncResult:
    synced_path = srt_path.with_suffix(".sync.srt")
    cmd = [
        "ffsubsync",
        str(video_path),
        "-i",
        str(srt_path),
        "-o",
        str(synced_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SubtitleSyncError(
            f"ffsubsync falhou (exit {e.returncode}): {e.stderr or e.stdout or '<sem saída>'}"
        ) from e
    except FileNotFoundError as e:
        raise SubtitleSyncError(
            "ffsubsync não encontrado no PATH. Instalou as deps do requirements.txt?"
        ) from e

    if not synced_path.exists():
        raise SubtitleSyncError("ffsubsync terminou sem criar o arquivo de saída.")

    orig_ts = _parse_srt_timestamps(srt_path.read_text(encoding="utf-8", errors="replace"))
    sync_ts = _parse_srt_timestamps(synced_path.read_text(encoding="utf-8", errors="replace"))
    offset = _mean_offset_seconds(orig_ts, sync_ts)

    if offset < SYNC_THRESHOLD_SECONDS:
        synced_path.unlink(missing_ok=True)
        return SyncResult(synced=False, offset_seconds=offset)

    # Substitui o original pela versão sincronizada.
    synced_path.replace(srt_path)
    return SyncResult(synced=True, offset_seconds=offset)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k "sync or offset or parse_srt"`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py tests/fixtures/mini.srt
git commit -m "feat: sincronização condicional via ffsubsync com limiar de 0.1s"
```

---

## Task 8: Renomear a legenda para o nome canônico `<video>.<lang>.srt`

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

A spec diz: saída é `<nome_do_video>.<lang>.srt` no mesmo diretório, onde `<lang>` é a tag BCP 47 que o usuário passou. Isso permite coexistir múltiplas legendas do mesmo vídeo em idiomas diferentes. O `subliminal` já grava algo como `<nome>.pt-BR.srt`, mas queremos controle sobre o sufixo exato (o formato do sufixo varia entre versões do babelfish/subliminal — normalizamos aqui).

Comportamento: se já existir arquivo no caminho-alvo, sobrescreve sem perguntar.

- [ ] **Step 1: Escrever testes que falham**

```python
from subs_down_n_sync import finalize_output_path


def test_finalize_renomeia_com_tag_idioma(tmp_path):
    video = tmp_path / "Filme.2024.mkv"
    srt = tmp_path / "Filme.2024.pt-BR.srt"  # saída do subliminal
    srt.write_text("conteudo")

    final = finalize_output_path(video, srt, lang_tag="pt-BR")
    assert final == tmp_path / "Filme.2024.pt-BR.srt"
    assert final.exists()
    assert final.read_text() == "conteudo"


def test_finalize_sobrescreve_existente(tmp_path):
    video = tmp_path / "Filme.mkv"
    existente = tmp_path / "Filme.en.srt"
    existente.write_text("velho")
    srt = tmp_path / "Filme.eng.srt"  # nome que subliminal usou
    srt.write_text("novo")

    final = finalize_output_path(video, srt, lang_tag="en")
    assert final == tmp_path / "Filme.en.srt"
    assert final.read_text() == "novo"


def test_finalize_noop_quando_ja_tem_nome_canonico(tmp_path):
    video = tmp_path / "Filme.mkv"
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("x")

    final = finalize_output_path(video, srt, lang_tag="pt-BR")
    assert final == srt
    assert final.read_text() == "x"


def test_finalize_com_lang_diferente_do_nome_gravado(tmp_path):
    """subliminal pode ter salvo como Filme.pob.srt; queremos Filme.pt-BR.srt."""
    video = tmp_path / "Filme.mkv"
    srt = tmp_path / "Filme.pob.srt"
    srt.write_text("conteudo")

    final = finalize_output_path(video, srt, lang_tag="pt-BR")
    assert final == tmp_path / "Filme.pt-BR.srt"
    assert final.read_text() == "conteudo"
    assert not srt.exists()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k finalize`
Expected: 4 FAILs — `ImportError`.

- [ ] **Step 3: Implementar `finalize_output_path`**

```python
def finalize_output_path(video_path: Path, srt_path: Path, lang_tag: str) -> Path:
    target = video_path.with_suffix(f".{lang_tag}.srt")
    if srt_path == target:
        return target
    srt_path.replace(target)  # replace sobrescreve atomicamente
    return target
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_subs_down_n_sync.py -v -k finalize`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: finalização do arquivo de saída com tag de idioma"
```

---

## Task 9: Orquestração `run()` + integração no `main()`

**Files:**
- Modify: `subs_down_n_sync.py`
- Modify: `tests/test_subs_down_n_sync.py`

Agora unimos tudo. `run()` é pura (recebe caminho + deps injetáveis) e retorna um objeto com o resumo. `main()` faz o wiring e print.

- [ ] **Step 1: Escrever testes que falham**

```python
from subs_down_n_sync import run, RunSummary


def test_run_pipeline_completo_sync_necessario(tmp_path, mocker, monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "u")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "p")
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):  # noqa: ARG001
        downloaded.write_text("dummy")
        return downloaded, SubtitleInfo(provider="opensubtitles", match_type="hash")

    mocker.patch("subs_down_n_sync.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.sync_subtitle_if_needed",
        return_value=SyncResult(synced=True, offset_seconds=1.25),
    )

    summary = run(str(video), lang_tag="pt-BR")

    assert summary.output_path == tmp_path / "Filme.pt-BR.srt"
    assert summary.output_path.exists()
    assert summary.provider == "opensubtitles"
    assert summary.match_type == "hash"
    assert summary.synced is True
    assert summary.offset_seconds == pytest.approx(1.25)
    assert summary.lang_tag == "pt-BR"


def test_run_falha_ffsubsync_mantem_legenda(tmp_path, mocker, monkeypatch, capsys):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "u")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "p")
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):  # noqa: ARG001
        downloaded.write_text("dummy")
        return downloaded, SubtitleInfo(provider="opensubtitles", match_type="release")

    mocker.patch("subs_down_n_sync.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.sync_subtitle_if_needed",
        side_effect=SubtitleSyncError("boom"),
    )

    summary = run(str(video), lang_tag="en")

    # spec: mantém a legenda original, avisa que não sincronizou.
    assert summary.output_path == tmp_path / "Filme.en.srt"
    assert summary.output_path.exists()
    assert summary.synced is False
    assert summary.sync_error == "boom"


def test_main_sucesso_imprime_resumo(tmp_path, mocker, monkeypatch, capsys):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "u")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "p")
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    fake_summary = RunSummary(
        output_path=tmp_path / "Filme.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=True,
        offset_seconds=0.42,
        sync_error=None,
        elapsed_seconds=1.23,
        lang_tag="pt-BR",
    )
    mocker.patch("subs_down_n_sync.run", return_value=fake_summary)

    code = main([str(video)])  # sem --lang, deve usar default pt-BR
    assert code == 0
    out = capsys.readouterr().out
    assert "opensubtitles" in out
    assert "hash" in out
    assert "0.42" in out or "0,42" in out
    assert "Filme.pt-BR.srt" in out


def test_main_lang_flag_usa_idioma_custom(tmp_path, mocker, monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "u")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "p")
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    fake_run = mocker.patch(
        "subs_down_n_sync.run",
        return_value=RunSummary(
            output_path=tmp_path / "Filme.en.srt",
            provider="opensubtitles",
            match_type="hash",
            synced=False,
            offset_seconds=0.0,
            sync_error=None,
            elapsed_seconds=0.1,
            lang_tag="en",
        ),
    )

    code = main([str(video), "--lang", "en"])
    assert code == 0
    # run() deve ter sido chamado com lang_tag="en"
    assert fake_run.call_args.kwargs.get("lang_tag") == "en" or (
        len(fake_run.call_args.args) >= 2 and fake_run.call_args.args[1] == "en"
    )


def test_main_erro_esperado_retorna_1(tmp_path, mocker, monkeypatch, capsys):
    # video inexistente → InvalidVideoError → exit 1
    code = main([str(tmp_path / "naoexiste.mkv")])
    assert code == 1
    err = capsys.readouterr().err
    assert "não existe" in err
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_subs_down_n_sync.py -v -k "run_pipeline or run_falha or main_sucesso or main_erro"`
Expected: falhas (`run` e `RunSummary` ainda não existem; `main` só imprime `video: ...`).

- [ ] **Step 3: Implementar `run()`, `RunSummary` e reescrever `main()`**

Adicionar/substituir em `subs_down_n_sync.py`:

Primeiro, atualizar `build_parser()` (em Task 2) para aceitar `--lang/-l`:

```python
DEFAULT_LANG = "pt-BR"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs_down_n_sync",
        description="Busca e sincroniza legenda para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    parser.add_argument(
        "-l", "--lang",
        default=DEFAULT_LANG,
        help=f"Código de idioma BCP 47 (ex: pt-BR, en, es). Default: {DEFAULT_LANG}.",
    )
    return parser
```

Depois, adicionar/substituir o restante em `subs_down_n_sync.py`:

```python
import time


@dataclass(frozen=True)
class RunSummary:
    output_path: Path
    provider: str
    match_type: str
    synced: bool
    offset_seconds: float
    sync_error: str | None
    elapsed_seconds: float
    lang_tag: str


def run(video_arg: str, lang_tag: str = DEFAULT_LANG) -> RunSummary:
    start = time.monotonic()
    check_ffmpeg()
    credentials = load_credentials()
    video_path = validate_video_path(video_arg)
    language = parse_language(lang_tag)

    srt_path, info = find_and_download_subtitle(
        video_path, language=language, credentials=credentials
    )

    sync_error: str | None = None
    try:
        sync_result = sync_subtitle_if_needed(video_path, srt_path)
    except SubtitleSyncError as e:
        sync_error = str(e)
        sync_result = SyncResult(synced=False, offset_seconds=0.0)

    final_path = finalize_output_path(video_path, srt_path, lang_tag=lang_tag)
    elapsed = time.monotonic() - start
    return RunSummary(
        output_path=final_path,
        provider=info.provider,
        match_type=info.match_type,
        synced=sync_result.synced,
        offset_seconds=sync_result.offset_seconds,
        sync_error=sync_error,
        elapsed_seconds=elapsed,
        lang_tag=lang_tag,
    )


def _print_summary(summary: RunSummary) -> None:
    print(f"Legenda ({summary.lang_tag}): {summary.provider} (match: {summary.match_type})")
    if summary.sync_error:
        print(
            f"Aviso: sincronização falhou — mantendo legenda original. "
            f"Detalhe: {summary.sync_error}"
        )
    elif summary.synced:
        print(f"Sincronizada (ajuste médio: {summary.offset_seconds:.2f}s)")
    else:
        print(
            f"Já sincronizada (offset médio: {summary.offset_seconds:.2f}s < 0.10s)"
        )
    print(f"Arquivo: {summary.output_path}")
    print(f"Tempo total: {summary.elapsed_seconds:.2f}s")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run(args.video, lang_tag=args.lang)
    except SubsDownError as e:
        print(str(e), file=sys.stderr)
        return 1
    _print_summary(summary)
    return 0
```

Remover o `print(f"video: {args.video}")` antigo.

- [ ] **Step 4: Rodar TODOS os testes e confirmar que passam**

Run: `pytest tests/ -v`
Expected: todos PASS (suites anteriores + novas).

- [ ] **Step 5: Commit**

```bash
git add subs_down_n_sync.py tests/test_subs_down_n_sync.py
git commit -m "feat: orquestração run() + CLI integrado com feedback e exit codes"
```

---

## Task 10: README com setup e uso

**Files:**
- Create: `README.md`

- [ ] **Step 1: Escrever README.md**

```markdown
# subs_down_n_sync

CLI Python para baixar e sincronizar legendas para arquivos de vídeo. Idioma padrão: **pt-BR**, configurável via flag.

## Setup

​```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
​```

Instale também o `ffmpeg` no sistema (usado pelo `ffsubsync`):

​```bash
sudo apt install ffmpeg    # Debian/Ubuntu
brew install ffmpeg        # macOS
​```

## Configuração (uma única vez)

​```bash
export OPENSUBTITLES_USERNAME="seu_usuario"
export OPENSUBTITLES_PASSWORD="sua_senha"
​```

## Uso

​```bash
# Default: pt-BR
python subs_down_n_sync.py /caminho/para/filme.mkv

# Outro idioma (BCP 47: 'en', 'pt-BR', 'en-US', 'es', 'ja', ...)
python subs_down_n_sync.py /caminho/para/filme.mkv --lang en
python subs_down_n_sync.py /caminho/para/filme.mkv -l es
​```

Saída: `/caminho/para/filme.<lang>.srt` (ex.: `filme.pt-BR.srt`, `filme.en.srt`). Isso permite manter legendas do mesmo vídeo em idiomas diferentes sem sobrescrever.

## Desenvolvimento

​```bash
pip install -r requirements-dev.txt
pytest
​```
```

**Nota:** ao escrever o README, substituir as sequências `​```` (zero-width space + três crases) por apenas três crases — os zero-width chars acima são só para escapar o code fence dentro do próprio plano.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README com instruções de setup, configuração e uso"
```

---

## Task 11: Atualizar CLAUDE.md e fechar

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Atualizar status**

Substituir o bloco `## Status` de `CLAUDE.md` por:

```markdown
## Status

Implementação concluída. Testado via `pytest`. Para rodar:

```bash
source .venv/bin/activate
python subs_down_n_sync.py /caminho/para/video.mkv
```

## Plano de Implementação

docs/superpowers/plans/2026-04-19-subs_down_n_sync.md
```

- [ ] **Step 2: Rodar a suite completa uma última vez**

Run: `pytest tests/ -v`
Expected: todos PASS.

- [ ] **Step 3: Commit final**

```bash
git add CLAUDE.md
git commit -m "docs: marcar implementação como concluída no CLAUDE.md"
```

---

## Self-Review (checado antes de entregar)

1. **Cobertura da spec:**
   - Uso `python subs_down_n_sync.py /caminho/...` → Task 2 (entrypoint) + Task 9 (main).
   - Saída `.srt` mesmo diretório/mesmo nome base → Task 8.
   - Subliminal + pt-BR + match por hash > release > fallback → Task 6 (`_classify_match`).
   - Credenciais via env vars → Task 5.
   - Apenas SRT → Task 6 (download_best_subtitles + extensão `.srt`).
   - ffsubsync + limiar 0.1s + substitui se >= 0.1s → Task 7.
   - Feedback (provedor, tipo de match, sync aplicado, tempo) → Task 9 (`_print_summary`).
   - Tabela de erros (arquivo inválido, credenciais faltando, sem legenda, falha sync, ffmpeg ausente) → Tasks 3, 4, 5, 6, 7, 9.
   - Sobrescreve `.srt` pré-existente → Task 8 (`replace`).
   - Dependências subliminal + ffsubsync → Task 1.
   - ffmpeg de sistema → Task 4.
   - Estrutura `subs_down_n_sync.py` + `requirements.txt` → Tasks 1 e 2.
   - Setup `python -m venv` + `pip install -r` → Task 10 (README) + Task 1 (criação).

2. **Placeholders:** Nenhum "TBD", "similar a", "handle edge cases", etc. Todo passo tem código ou comando concreto.

3. **Consistência de tipos:**
   - `SubsDownError` é superclasse de `InvalidVideoError`, `MissingDependencyError`, `MissingCredentialsError`, `SubtitleNotFoundError`, `SubtitleSyncError` — capturada única vez em `main` (Task 9).
   - `SubtitleInfo(provider, match_type)` definido em Task 6, usado em Task 9.
   - `SyncResult(synced, offset_seconds)` definido em Task 7, usado em Task 9.
   - `RunSummary` definido em Task 9 — campos batem com o que `_print_summary` consome.
   - `validate_video_path`, `check_ffmpeg`, `load_credentials`, `find_and_download_subtitle`, `sync_subtitle_if_needed`, `finalize_output_path`, `run`, `main` — todos nomes consistentes entre tasks e chamadas.
