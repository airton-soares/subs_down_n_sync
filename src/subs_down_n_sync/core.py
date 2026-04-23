"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import subliminal
from babelfish import Language
from subliminal.refiners.hash import refine as hash_refine
from subliminal.score import compute_score, get_scores

from subs_down_n_sync.exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}

DEFAULT_LANG = "pt-BR"


SCORE_THRESHOLD = 0.9  # score/max_score >= 90% → sem sync


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"
    needs_sync: bool


SYNC_THRESHOLD_SECONDS = 0.1

_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float
    sync_mode: str = "none"  # "ref" | "video" | "none"


@dataclass(frozen=True)
class RunSummary:
    output_path: Path
    provider: str
    match_type: str
    synced: bool
    offset_seconds: float
    sync_mode: str
    sync_error: str | None
    elapsed_seconds: float
    lang_tag: str


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MissingDependencyError(
            "ffmpeg não encontrado no PATH. Instale via gerenciador de pacotes "
            "(ex.: sudo apt install ffmpeg, brew install ffmpeg)."
        )


def check_alass() -> None:
    if shutil.which("alass") is None:
        raise MissingDependencyError(
            "alass não encontrado no PATH. Baixe o binário em "
            "https://github.com/kaegi/alass/releases e coloque no PATH."
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


def _pick_subtitle(
    candidates: list,
    video: object,
) -> tuple[object, str, bool]:
    """Escolhe melhor legenda e decide se precisa de sync.

    Retorna (subtitle, match_type, needs_sync).
    Ordem de preferência:
      1. score >= 90% do máximo → sem sync
      2. release_group match → sem sync
      3. melhor score disponível → com sync
    """
    max_score = get_scores(video)["hash"]
    threshold = int(max_score * SCORE_THRESHOLD)

    scored = [(sub, compute_score(sub, video)) for sub in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    for sub, score in scored:
        matches = set(sub.get_matches(video))
        if score >= threshold:
            return sub, _classify_match(matches), False
        if "release_group" in matches:
            return sub, "release", False

    best_sub, _ = scored[0]
    match_type = _classify_match(set(best_sub.get_matches(video)))
    return best_sub, match_type, True


def find_and_download_subtitle(
    video_path: Path,
    language: Language,
    credentials: tuple[str, str],
) -> tuple[Path, SubtitleInfo, Path | None]:
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    hash_refine(video)
    provider_configs = {
        "opensubtitles": {"username": user, "password": pwd},
    }
    en_lang = Language("eng")
    needs_ref = language != en_lang

    languages_to_fetch = {language, en_lang} if needs_ref else {language}

    results = subliminal.list_subtitles(
        {video},
        languages_to_fetch,
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    candidates = results.get(video, [])

    target_candidates = [s for s in candidates if getattr(s, "language", None) == language]
    if not target_candidates:
        raise SubtitleNotFoundError(
            f"Nenhuma legenda em {language.alpha3} encontrada para: {video_path.name}"
        )

    subtitle, match_type, needs_sync = _pick_subtitle(target_candidates, video)

    ref_candidates = (
        [s for s in candidates if getattr(s, "language", None) == en_lang] if needs_ref else []
    )
    # Usar en como referência só se ela própria não precisar de sync — legenda
    # dessincronizada como referência piora o resultado do alass.
    ref_subtitle = None
    if ref_candidates:
        best_ref, _, ref_needs_sync = _pick_subtitle(ref_candidates, video)
        if not ref_needs_sync:
            ref_subtitle = best_ref

    to_download = [subtitle]
    if ref_subtitle is not None:
        to_download.append(ref_subtitle)

    subliminal.download_subtitles(to_download, provider_configs=provider_configs)

    # Não usamos subliminal.save_subtitles porque ele grava os bytes crus no
    # encoding detectado (ex.: cp1252), produzindo mojibake. Pegamos o texto
    # já decodificado e escrevemos em UTF-8.
    if not subtitle.text:
        raise SubtitleNotFoundError(f"Legenda veio vazia do provider para: {video_path.name}")

    srt_path = video_path.parent / Path(subtitle.get_path(video)).name
    srt_path.write_text(subtitle.text, encoding="utf-8")

    ref_path: Path | None = None
    if ref_subtitle is not None and ref_subtitle.text:
        ref_path = video_path.parent / Path(ref_subtitle.get_path(video)).name
        ref_path.write_text(ref_subtitle.text, encoding="utf-8")

    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=match_type,
        needs_sync=needs_sync,
    )

    return srt_path, info, ref_path


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


def sync_subtitle(
    video_path: Path,
    srt_path: Path,
    ref_path: Path | None,
) -> SyncResult:
    synced_path = srt_path.with_suffix(".synced.srt")
    reference = str(ref_path) if ref_path is not None else str(video_path)
    sync_mode = "ref" if ref_path is not None else "video"

    cmd = ["alass", reference, str(srt_path), str(synced_path)]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise SubtitleSyncError(
            f"alass falhou (exit {e.returncode}): {e.stderr or e.stdout or '<sem saída>'}"
        ) from e
    except FileNotFoundError as e:
        raise SubtitleSyncError(
            "alass não encontrado no PATH. Baixe em https://github.com/kaegi/alass/releases"
        ) from e

    if not synced_path.exists():
        raise SubtitleSyncError("alass terminou sem criar o arquivo de saída.")

    orig_ts = _parse_srt_timestamps(srt_path.read_text(encoding="utf-8", errors="replace"))
    sync_ts = _parse_srt_timestamps(synced_path.read_text(encoding="utf-8", errors="replace"))
    offset = _mean_offset_seconds(orig_ts, sync_ts)

    if offset < SYNC_THRESHOLD_SECONDS:
        synced_path.unlink(missing_ok=True)
        return SyncResult(synced=False, offset_seconds=offset, sync_mode="none")

    synced_path.replace(srt_path)
    return SyncResult(synced=True, offset_seconds=offset, sync_mode=sync_mode)


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
    check_alass()
    language = parse_language(lang_tag)
    credentials = load_credentials()

    srt_path, info, ref_path = find_and_download_subtitle(
        video_path, language=language, credentials=credentials
    )

    sync_error: str | None = None
    if info.needs_sync:
        try:
            sync_result = sync_subtitle(video_path, srt_path, ref_path)
        except SubtitleSyncError as e:
            sync_error = str(e)
            sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
        finally:
            if ref_path is not None:
                ref_path.unlink(missing_ok=True)
    else:
        sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")

    final_path = finalize_output_path(video_path, srt_path, lang_tag=lang_tag)
    elapsed = time.monotonic() - start

    return RunSummary(
        output_path=final_path,
        provider=info.provider,
        match_type=info.match_type,
        synced=sync_result.synced,
        offset_seconds=sync_result.offset_seconds,
        sync_mode=sync_result.sync_mode,
        sync_error=sync_error,
        elapsed_seconds=elapsed,
        lang_tag=lang_tag,
    )
