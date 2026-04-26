"""subs_down_n_sync: busca e sincroniza legendas (pt-BR por padrão, qualquer BCP 47)."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import subliminal
from babelfish import Language
from scipy.spatial.distance import cdist
from sentence_transformers import SentenceTransformer
from subliminal.refiners.hash import refine as hash_refine
from subliminal.score import compute_score

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

SYNC_THRESHOLD_SECONDS = 0.1

_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)

_SRT_BLOCK_RE = re.compile(
    r"(\d+)\n"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\n"
    r"((?:.+\n?)+)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback"
    needs_sync: bool


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float
    sync_mode: str = "none"  # "video" | "none"


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


def _filename_similarity(sub_filename: str, video_name: str) -> float:
    """Fração de tokens do stem do vídeo presentes no nome da legenda."""
    norm = re.compile(r"[\W_]+")
    video_stem = Path(video_name).stem
    sub_tokens = set(norm.sub(" ", sub_filename.lower()).split())
    video_tokens = set(norm.sub(" ", video_stem.lower()).split())
    if not video_tokens:
        return 0.0
    return len(sub_tokens & video_tokens) / len(video_tokens)


def _pick_subtitle(
    candidates: list,
    video: object,
) -> tuple[object, str, bool]:
    """Escolhe melhor legenda e decide se precisa de sync.

    Retorna (subtitle, match_type, needs_sync).
    Ordem de preferência:
      1. hash match → sem sync
      2. release_group match → melhor filename similarity → com sync
      3. fallback → melhor filename similarity → com sync
    """
    video_name = getattr(video, "name", "") or ""

    scored = [(sub, compute_score(sub, video)) for sub in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 1. hash match
    for sub, _ in scored:
        if "hash" in set(sub.get_matches(video)):
            return sub, "hash", False

    # 2. release_group match
    release_candidates = [
        (sub, score) for sub, score in scored if "release_group" in set(sub.get_matches(video))
    ]
    pool = release_candidates if release_candidates else scored
    match_type = "release" if release_candidates else "fallback"

    best_sub = max(
        pool,
        key=lambda x: _filename_similarity(getattr(x[0], "filename", "") or "", video_name),
    )[0]
    return best_sub, match_type, True


def _download_sub(
    video: object,
    language: Language,
    provider_configs: dict,
) -> object | None:
    """Busca e baixa melhor legenda disponível para o idioma. Retorna subtitle ou None."""
    results = subliminal.list_subtitles(
        {video},
        {language},
        providers=["opensubtitles"],
        provider_configs=provider_configs,
    )
    candidates = results.get(video, [])
    candidates = [s for s in candidates if getattr(s, "language", None) == language]

    if not candidates:
        return None

    scored = [(sub, compute_score(sub, video)) for sub in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    best = scored[0][0]

    subliminal.download_subtitles([best], provider_configs=provider_configs)
    return best if best.text else None


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

    subtitle, match_type, needs_sync = _pick_subtitle(target_candidates, video)

    subliminal.download_subtitles([subtitle], provider_configs=provider_configs)

    # Não usamos subliminal.save_subtitles porque ele grava os bytes crus no
    # encoding detectado (ex.: cp1252), produzindo mojibake. Pegamos o texto
    # já decodificado e escrevemos em UTF-8.
    if not subtitle.text:
        raise SubtitleNotFoundError(f"Legenda veio vazia do provider para: {video_path.name}")

    srt_path = video_path.parent / Path(subtitle.get_path(video)).name
    srt_path.write_text(subtitle.text, encoding="utf-8")

    info = SubtitleInfo(
        provider=subtitle.provider_name,
        match_type=match_type,
        needs_sync=needs_sync,
    )

    return srt_path, info


def find_reference_subtitle(
    video_path: Path,
    credentials: tuple[str, str],
) -> Path | None:
    """Baixa legenda EN como referência de alinhamento. Retorna path ou None."""
    user, pwd = credentials
    video = subliminal.scan_video(str(video_path))
    hash_refine(video)

    en = Language("eng")
    provider_configs = {"opensubtitles": {"username": user, "password": pwd}}

    subtitle = _download_sub(video, en, provider_configs)
    if subtitle is None:
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="subs_ref_"))
    ref_path = tmp_dir / Path(subtitle.get_path(video)).name
    ref_path.write_text(subtitle.text, encoding="utf-8")

    return ref_path


def _ts(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _seconds_to_ts(total: float) -> str:
    total = max(0.0, total)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = int(total % 60)
    ms = round((total - int(total)) * 1000)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _srt_to_segments(srt_text: str) -> list[dict]:
    segments = []
    for m in _SRT_BLOCK_RE.finditer(srt_text):
        segments.append(
            {
                "start": _ts(m.group(2), m.group(3), m.group(4), m.group(5)),
                "end": _ts(m.group(6), m.group(7), m.group(8), m.group(9)),
                "text": m.group(10).strip(),
            }
        )
    return segments


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


_SEMANTIC_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _align_cues_by_semantics(
    target_cues: list[dict],
    ref_cues: list[dict],
) -> list[dict]:
    """Alinha cues de legenda alvo aos timestamps da referência via embeddings semânticos + DTW.

    Para cada cue alvo, encontra o(s) cue(s) ref mais similar(es) semanticamente
    e copia os timestamps. Garante ordem monotônica crescente no resultado.
    """
    model = SentenceTransformer(_SEMANTIC_MODEL)

    target_texts = [c["text"] for c in target_cues]
    ref_texts = [c["text"] for c in ref_cues]

    target_emb = model.encode(target_texts, convert_to_numpy=True)
    ref_emb = model.encode(ref_texts, convert_to_numpy=True)

    # matriz de distância coseno: shape (len_target, len_ref)
    dist_matrix = cdist(target_emb, ref_emb, metric="cosine")

    # DTW simples: encontra caminho de alinhamento ótimo
    n, m = dist_matrix.shape
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i, j] = dist_matrix[i - 1, j - 1] + min(
                cost[i - 1, j],  # inserção
                cost[i, j - 1],  # deleção
                cost[i - 1, j - 1],  # match
            )

    # traceback
    path: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        options = [
            (cost[i - 1, j - 1], i - 1, j - 1),
            (cost[i - 1, j], i - 1, j),
            (cost[i, j - 1], i, j - 1),
        ]
        _, i, j = min(options, key=lambda x: x[0])
    path.reverse()

    # para cada cue alvo, coleta os ref_cues mapeados e usa média dos timestamps
    from collections import defaultdict

    target_to_refs: dict[int, list[int]] = defaultdict(list)
    for ti, ri in path:
        target_to_refs[ti].append(ri)

    result = []
    for ti, cue in enumerate(target_cues):
        mapped = target_to_refs.get(ti, [])
        orig_duration = max(cue["end"] - cue["start"], 0.0)

        if mapped:
            # usa start do primeiro ref mapeado (não média, evita puxar p/ meio)
            start = float(ref_cues[mapped[0]]["start"])
            # preserva duração original do target (frase pt pode ser mais longa que en)
            end = start + orig_duration
        else:
            start, end = cue["start"], cue["end"]

        # duração mínima de leitura: ~60ms/char, mínimo 1s, teto 7s
        min_duration = max(1.0, min(len(cue["text"]) * 0.06, 7.0))
        if end - start < min_duration:
            end = start + min_duration

        result.append({"start": start, "end": end, "text": cue["text"]})

    # garante ordem monotônica e clamp contra próximo cue
    for i in range(1, len(result)):
        if result[i]["start"] <= result[i - 1]["start"]:
            gap = max(result[i - 1]["end"] - result[i - 1]["start"], 0.1)
            result[i]["start"] = result[i - 1]["start"] + gap
            duration = result[i]["end"] - result[i]["start"]
            result[i]["end"] = result[i]["start"] + max(duration, 0.1)

    # clamp: end do cue i não invade start do cue i+1 (deixa 50ms de gap)
    for i in range(len(result) - 1):
        max_end = result[i + 1]["start"] - 0.05
        if result[i]["end"] > max_end:
            result[i]["end"] = max(max_end, result[i]["start"] + 0.1)

    return result


def _cues_to_srt(cues: list[dict]) -> str:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(
            f"{i}\n{_seconds_to_ts(cue['start'])} --> {_seconds_to_ts(cue['end'])}\n{cue['text']}\n"
        )
    return "\n".join(lines)


def sync_subtitle(
    srt_path: Path,
    ref_path: Path,
) -> SyncResult:
    """Alinha legenda alvo usando legenda EN de referência via embeddings semânticos."""
    target_text = srt_path.read_text(encoding="utf-8", errors="replace")
    target_cues = _srt_to_segments(target_text)
    target_ts_orig = [c["start"] for c in target_cues]

    ref_text = ref_path.read_text(encoding="utf-8", errors="replace")
    ref_cues = _srt_to_segments(ref_text)

    try:
        aligned_cues = _align_cues_by_semantics(target_cues, ref_cues)
    except Exception as e:
        raise SubtitleSyncError(f"alinhamento semântico falhou: {e}") from e

    aligned_ts = [c["start"] for c in aligned_cues]
    offset = _mean_offset_seconds(target_ts_orig, aligned_ts)

    if offset < SYNC_THRESHOLD_SECONDS:
        return SyncResult(synced=False, offset_seconds=offset, sync_mode="none")

    srt_path.write_text(_cues_to_srt(aligned_cues), encoding="utf-8")
    return SyncResult(synced=True, offset_seconds=offset, sync_mode="ref")


def finalize_output_path(video_path: Path, srt_path: Path, lang_tag: str) -> Path:
    target = video_path.with_suffix(f".{lang_tag}.srt")

    if srt_path == target:
        return target

    srt_path.replace(target)

    return target


ProgressCallback = Callable[[str, str], None]


def run(
    video_arg: str,
    lang_tag: str = DEFAULT_LANG,
    on_progress: ProgressCallback | None = None,
    resync: bool = False,
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

    if resync and srt_existing.exists():
        srt_path = srt_existing
        info = SubtitleInfo(provider="local", match_type="existing", needs_sync=True)
        _notify("usando_existente", str(srt_path))
    else:
        _notify("buscando", f"idioma={lang_tag}")
        srt_path, info = find_and_download_subtitle(
            video_path, language=language, credentials=credentials
        )
        _notify("baixado", f"provider={info.provider} match={info.match_type}")

    sync_error: str | None = None

    if info.needs_sync:
        _notify("referencia", "buscando EN")
        ref_path = find_reference_subtitle(video_path, credentials=credentials)

        if ref_path is None:
            sync_error = "legenda EN de referência não encontrada — sincronização ignorada"
            sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
            _notify("sem_referencia", "")
        else:
            _notify("sincronizando", "embeddings semânticos")
            try:
                sync_result = sync_subtitle(srt_path, ref_path=ref_path)
                _notify("sincronizado", f"offset={sync_result.offset_seconds:.2f}s")
            except SubtitleSyncError as e:
                sync_error = str(e)
                sync_result = SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")
                _notify("erro_sync", str(e))
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
    )
