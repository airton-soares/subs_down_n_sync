"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
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
            f"Nenhuma legenda em {language.alpha3} encontrada para: {video_path.name}"
        )

    subtitle = subs[0]
    saved = subliminal.save_subtitles(video, [subtitle], directory=str(video_path.parent))
    
    if not saved:
        raise SubtitleNotFoundError(
            f"subliminal não conseguiu salvar a legenda para: {video_path.name}"
        )

    # subliminal calcula o nome via subtitle.get_path e depois joga no directory,
    # então o caminho final é determinístico: parent / basename(get_path).
    srt_path = video_path.parent / Path(saved[0].get_path(video)).name
    
    if not srt_path.exists():
        raise SubtitleNotFoundError(
            f"Arquivo .srt não apareceu após download: {srt_path}"
        )

    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=_classify_match(set(subtitle.matches or [])),
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

    # Substitui o original pela versão sincronizada.
    synced_path.replace(srt_path)

    return SyncResult(synced=True, offset_seconds=offset)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subs_down_n_sync",
        description="Busca e sincroniza legenda para um arquivo de vídeo.",
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
