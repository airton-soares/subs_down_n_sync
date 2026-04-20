"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""
from __future__ import annotations

import argparse
import os
import shutil
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
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"


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
