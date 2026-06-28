"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import subliminal
from babelfish import Language
from subliminal.refiners.hash import refine as hash_refine

from subs_down_n_sync.audio_sync import (
    ProgressCallback,
    SyncResult,
    sync_by_audio,
    sync_subtitle,
)
from subs_down_n_sync.credentials import load_credentials
from subs_down_n_sync.exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)
from subs_down_n_sync.matcher import (
    SCORE_THRESHOLD,
    SubtitleInfo,
    filename_similarity,
    pick_subtitle,
)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}

DEFAULT_LANG = "pt-BR"


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
    match_tier: int = 0
    matched_fields: list[str] = field(default_factory=list)


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MissingDependencyError(
            "ffmpeg não encontrado no PATH. Instale via gerenciador de pacotes "
            "(ex.: sudo apt install ffmpeg, brew install ffmpeg)."
        )


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


def find_and_download_subtitle(
    video_path: Path,
    language: Language,
    credentials: tuple[str, str],
) -> tuple[Path, SubtitleInfo]:
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    hash_refine(video)

    provider_configs = {"opensubtitles": {"username": user, "password": pwd}}

    results = subliminal.list_subtitles(
        {video},
        {language},
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    candidates = results.get(video, [])
    target_candidates = [s for s in candidates if getattr(s, "language", None) == language]

    if not target_candidates:
        raise SubtitleNotFoundError(
            f"Nenhuma legenda em {language.alpha3} encontrada para: {video_path.name}"
        )

    subtitle, info = pick_subtitle(target_candidates, video)

    subliminal.download_subtitles([subtitle], provider_configs=provider_configs)

    # Não usamos subliminal.save_subtitles porque ele grava os bytes crus no
    # encoding detectado (ex.: cp1252), produzindo mojibake. Pegamos o texto
    # já decodificado e escrevemos em UTF-8.
    if not subtitle.text:
        raise SubtitleNotFoundError(f"Legenda veio vazia do provider para: {video_path.name}")

    srt_path = video_path.parent / Path(subtitle.get_path(video)).name
    srt_path.write_text(subtitle.text, encoding="utf-8")

    return srt_path, info


def find_reference_subtitle(
    video_path: Path,
    credentials: tuple[str, str],
    ref_lang: str = "en",
) -> Path | None:
    """Baixa legenda de referência para alinhamento. Retorna path ou None.

    Só aceita matches até tier 3 — tier 4 indica baixa confiança e não serve como âncora.
    """
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    hash_refine(video)

    lang = parse_language(ref_lang)
    provider_configs = {"opensubtitles": {"username": user, "password": pwd}}

    results = subliminal.list_subtitles(
        {video},
        {lang},
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    candidates = results.get(video, [])
    target_candidates = [s for s in candidates if getattr(s, "language", None) == lang]

    if not target_candidates:
        return None

    subtitle, info = pick_subtitle(target_candidates, video)

    if info.match_tier == 4:
        return None

    subliminal.download_subtitles([subtitle], provider_configs=provider_configs)
    if not subtitle.text:
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="subs_ref_"))
    ref_path = tmp_dir / Path(subtitle.get_path(video)).name
    ref_path.write_text(subtitle.text, encoding="utf-8")

    return ref_path


def finalize_output_path(video_path: Path, srt_path: Path, lang_tag: str) -> Path:
    target = video_path.with_suffix(f".{lang_tag}.srt")

    if srt_path == target:
        return target

    srt_path.replace(target)

    return target


def run(
    video_arg: str,
    lang_tag: str = DEFAULT_LANG,
    on_progress: ProgressCallback | None = None,
    resync: bool = False,
    overwrite: bool = False,
    whisper_model: str = "tiny",
    ref_lang: str = "en",
) -> RunSummary:
    def _notify(step: str, detail: str = "") -> None:
        if on_progress:
            on_progress(step, detail)

    start = time.monotonic()

    _notify("validando", video_arg)
    video_path = validate_video_path(video_arg)
    check_ffmpeg()
    language = parse_language(lang_tag)
    credentials = load_credentials()

    srt_existing = video_path.with_suffix(f".{lang_tag}.srt")

    if srt_existing.exists() and not overwrite and not resync:
        elapsed = time.monotonic() - start
        _notify("concluido", str(srt_existing))
        return RunSummary(
            output_path=srt_existing,
            provider="local",
            match_type="skipped",
            synced=False,
            offset_seconds=0.0,
            sync_mode="none",
            sync_error=None,
            elapsed_seconds=elapsed,
            lang_tag=lang_tag,
            match_tier=0,
            matched_fields=[],
        )

    if resync and srt_existing.exists():
        srt_path = srt_existing
        similarity = filename_similarity(srt_existing.name, video_path.name)
        needs_sync = similarity < SCORE_THRESHOLD
        info = SubtitleInfo(
            provider="local",
            match_type="existing",
            needs_sync=needs_sync,
            match_tier=3,
            matched_fields=[f"filename_similarity={similarity:.2f}"],
        )
        _notify("usando_existente", str(srt_path))
    else:
        _notify("buscando", f"idioma={lang_tag}")
        srt_path, info = find_and_download_subtitle(
            video_path, language=language, credentials=credentials
        )
        _notify("baixado", f"provider={info.provider} match={info.match_type}")

    sync_error: str | None = None

    if info.needs_sync:
        if info.match_tier == 4:
            _notify("tier4_audio", info.match_type)
            try:
                sync_result = sync_by_audio(
                    srt_path,
                    video_path,
                    model_size=whisper_model,
                    on_progress=on_progress,
                )
                _notify(
                    "sincronizado",
                    f"modo={sync_result.sync_mode} offset={sync_result.offset_seconds:.2f}s",
                )
            except SubtitleSyncError as e:
                sync_error = str(e)
                sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
                _notify("erro_sync", str(e))
        else:
            _notify("referencia", f"buscando {ref_lang}")
            ref_path = find_reference_subtitle(
                video_path, credentials=credentials, ref_lang=ref_lang
            )

            if ref_path:
                _notify("sincronizando", "embeddings semânticos")
                try:
                    sync_result = sync_subtitle(srt_path, ref_path=ref_path)
                    _notify("sincronizado", f"offset={sync_result.offset_seconds:.2f}s")
                except SubtitleSyncError as e:
                    sync_error = str(e)
                    sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
                    _notify("erro_sync", str(e))
            else:
                _notify("sem_referencia", "legenda usada sem sincronização")
                sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
    else:
        sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
        _notify("sem_sync", f"offset={sync_result.offset_seconds:.2f}s")

    final_path = finalize_output_path(video_path, srt_path, lang_tag=lang_tag)
    elapsed = time.monotonic() - start

    _notify("concluido", str(final_path))

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
        match_tier=info.match_tier,
        matched_fields=list(info.matched_fields),
    )
