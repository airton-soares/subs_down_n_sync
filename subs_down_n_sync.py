"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import subliminal
from babelfish import Language

from exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubsDownError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}

DEFAULT_LANG = "pt-BR"


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"


SYNC_THRESHOLD_SECONDS = 0.1

_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float


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


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MissingDependencyError(
            "ffmpeg não encontrado no PATH. Instale via gerenciador de pacotes "
            "(ex.: sudo apt install ffmpeg, brew install ffmpeg)."
        )


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


def validate_video_path(raw: str) -> Path:
    p = Path(raw).expanduser()

    if not p.exists():
        raise InvalidVideoError(f"Arquivo de vídeo não existe: {p}")
    if not p.is_file():
        raise InvalidVideoError(f"Caminho não é um arquivo: {p}")
    if p.suffix.lower() not in VIDEO_EXTENSIONS:
        raise InvalidVideoError(
            f"Extensão não suportada ({p.suffix}). "
            f"Esperado um destes: {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )

    return p


def parse_language(raw: str) -> Language:
    try:
        return Language.fromietf(raw)
    except Exception as e:
        raise InvalidLanguageError(
            f"Código de idioma inválido: {raw!r}. Use tags BCP 47 como 'pt-BR', 'en', 'es', 'ja'."
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
            f"Nenhuma legenda em {language.alpha3} encontrada para: {video_path.name}"
        )

    subtitle = subs[0]

    # Não usamos subliminal.save_subtitles porque ele grava os bytes crus no
    # encoding detectado (ex.: cp1252) em um arquivo UTF-8 por convenção, o que
    # produz mojibake quando ferramentas como ffsubsync tentam re-detectar.
    # Em vez disso, pegamos o texto já decodificado e escrevemos em UTF-8.
    if not subtitle.text:
        raise SubtitleNotFoundError(f"Legenda veio vazia do provider para: {video_path.name}")

    srt_path = video_path.parent / Path(subtitle.get_path(video)).name
    srt_path.write_text(subtitle.text, encoding="utf-8")

    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=_classify_match(set(subtitle.get_matches(video))),
    )

    return srt_path, info


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

    synced_path.replace(srt_path)

    return SyncResult(synced=True, offset_seconds=offset)


def finalize_output_path(video_path: Path, srt_path: Path, lang_tag: str) -> Path:
    target = video_path.with_suffix(f".{lang_tag}.srt")

    if srt_path == target:
        return target

    srt_path.replace(target)

    return target


def run(video_arg: str, lang_tag: str = DEFAULT_LANG) -> RunSummary:
    start = time.monotonic()
    video_path = validate_video_path(video_arg)
    check_ffmpeg()
    language = parse_language(lang_tag)
    credentials = load_credentials()

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
        print(f"Já sincronizada (offset médio: {summary.offset_seconds:.2f}s < 0.10s)")

    print(f"Arquivo: {summary.output_path}")
    print(f"Tempo total: {summary.elapsed_seconds:.2f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs_down_n_sync",
        description="Busca e sincroniza legenda para um arquivo de vídeo.",
    )
    parser.add_argument("video", help="Caminho para o arquivo de vídeo.")
    parser.add_argument(
        "-l",
        "--lang",
        default=DEFAULT_LANG,
        help=f"Código de idioma BCP 47 (ex: pt-BR, en, es). Default: {DEFAULT_LANG}.",
    )

    return parser


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


if __name__ == "__main__":
    sys.exit(main())
