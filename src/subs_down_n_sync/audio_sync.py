from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from scipy.spatial.distance import cdist
from sentence_transformers import SentenceTransformer

from subs_down_n_sync._srt_utils import (
    _cues_to_srt,
    _mean_offset_seconds,
    _read_text_detected,
    _srt_to_segments,
)
from subs_down_n_sync.exceptions import SubtitleSyncError

ProgressCallback = Callable[[str, str], None]

SYNC_THRESHOLD_SECONDS = 0.2
_LINEAR_STD_THRESHOLD = 2.0
_SEMANTIC_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("ctranslate2").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

_sentence_model_cache: SentenceTransformer | None = None
_whisper_model_cache: tuple[str, WhisperModel] | None = None


def _get_sentence_model() -> SentenceTransformer:
    global _sentence_model_cache
    if _sentence_model_cache is None:
        _sentence_model_cache = SentenceTransformer(_SEMANTIC_MODEL)
    return _sentence_model_cache


def _get_whisper_model(model_size: str) -> WhisperModel:
    global _whisper_model_cache
    if _whisper_model_cache is None or _whisper_model_cache[0] != model_size:
        _whisper_model_cache = (
            model_size,
            WhisperModel(model_size, device="cpu", compute_type="int8"),
        )
    return _whisper_model_cache[1]


@dataclass(frozen=True)
class SyncResult:
    synced: bool
    offset_seconds: float
    sync_mode: str = "none"  # "ref" | "audio_linear" | "audio_dtw" | "none"


def _align_cues_by_semantics(
    target_cues: list[dict],
    ref_cues: list[dict],
) -> list[dict]:
    """Alinha cues de legenda alvo aos timestamps da referência via embeddings semânticos + DTW."""
    model = _get_sentence_model()

    target_emb = model.encode([c["text"] for c in target_cues], convert_to_numpy=True)
    ref_emb = model.encode([c["text"] for c in ref_cues], convert_to_numpy=True)

    # matriz de distância coseno: shape (len_target, len_ref)
    dist_matrix = cdist(target_emb, ref_emb, metric="cosine")

    # DTW simples: encontra caminho de alinhamento ótimo
    n, m = dist_matrix.shape
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i, j] = dist_matrix[i - 1, j - 1] + min(
                cost[i - 1, j],
                cost[i, j - 1],
                cost[i - 1, j - 1],
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

    target_to_refs: dict[int, list[int]] = defaultdict(list)
    for ti, ri in path:
        target_to_refs[ti].append(ri)

    result = []
    for ti, cue in enumerate(target_cues):
        mapped = target_to_refs.get(ti, [])
        orig_duration = max(cue["end"] - cue["start"], 0.0)

        if mapped:
            start = float(ref_cues[mapped[0]]["start"])
            end = start + orig_duration
        else:
            start, end = cue["start"], cue["end"]

        # duração mínima de leitura: ~60ms/char, mínimo 1s, teto 7s
        min_duration = max(1.0, min(len(cue["text"]) * 0.06, 7.0))
        if end - start < min_duration:
            end = start + min_duration

        result.append({"start": start, "end": end, "text": cue["text"]})

    # garante ordem monotônica
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


def sync_subtitle(
    srt_path: Path,
    ref_path: Path,
) -> SyncResult:
    """Alinha legenda alvo usando legenda EN de referência via embeddings semânticos."""
    target_text = _read_text_detected(srt_path)
    target_cues = _srt_to_segments(target_text)
    target_ts_orig = [c["start"] for c in target_cues]

    ref_text = _read_text_detected(ref_path)
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


def _extract_audio(video_path: Path, output_wav: Path, duration_s: int = 600) -> None:
    """Extrai trecho de áudio mono 16kHz do vídeo via ffmpeg."""
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    total = float(json.loads(probe.stdout)["format"]["duration"])
    start = max(0.0, (total - duration_s) / 2)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(video_path),
            "-t",
            str(duration_s),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            str(output_wav),
        ],
        capture_output=True,
        check=True,
    )


def _transcribe(wav_path: Path, model_size: str) -> list[dict]:
    """Transcreve áudio usando faster-whisper. Retorna lista de segmentos."""
    model = _get_whisper_model(model_size)
    segments, _ = model.transcribe(str(wav_path))
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


def _apply_linear_offset(cues: list[dict], offset: float) -> list[dict]:
    """Aplica offset linear a todos os cues, garantindo timestamps não-negativos."""
    return [
        {
            "start": max(0.0, c["start"] + offset),
            "end": max(0.0, c["end"] + offset),
            "text": c["text"],
        }
        for c in cues
    ]


def sync_by_audio(
    srt_path: Path,
    video_path: Path,
    model_size: str = "tiny",
    on_progress: ProgressCallback | None = None,
) -> SyncResult:
    """Sincroniza legenda extraindo e transcrevendo o áudio do vídeo com faster-whisper."""

    def _notify(step: str, detail: str = "") -> None:
        if on_progress:
            on_progress(step, detail)

    _notify("transcrevendo", f"modelo={model_size}")

    with tempfile.TemporaryDirectory() as tmpdir:
        wav = Path(tmpdir) / "audio.wav"
        _extract_audio(video_path, wav)
        transcript = _transcribe(wav, model_size)

    if not transcript:
        return SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")

    target_text = _read_text_detected(srt_path)
    target_cues = _srt_to_segments(target_text)

    if not target_cues:
        return SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")

    _notify("alinhando", f"{len(target_cues)} cues")

    try:
        aligned_cues = _align_cues_by_semantics(target_cues, transcript)
    except Exception as e:
        raise SubtitleSyncError(f"alinhamento por áudio falhou: {e}") from e

    target_ts_orig = [c["start"] for c in target_cues]
    aligned_ts = [c["start"] for c in aligned_cues]

    deltas = [
        aligned_ts[i] - target_ts_orig[i] for i in range(min(len(target_ts_orig), len(aligned_ts)))
    ]

    if not deltas:
        return SyncResult(synced=False, offset_seconds=0.0, sync_mode="none")

    median_offset = float(np.median(deltas))
    std_dev = float(np.std(deltas))

    if std_dev < _LINEAR_STD_THRESHOLD:
        _notify("offset_linear", f"{median_offset:+.2f}s")
        shifted = _apply_linear_offset(target_cues, median_offset)
        srt_path.write_text(_cues_to_srt(shifted), encoding="utf-8")
        return SyncResult(synced=True, offset_seconds=abs(median_offset), sync_mode="audio_linear")

    _notify("audio_dtw", f"std_dev={std_dev:.2f}s")
    srt_path.write_text(_cues_to_srt(aligned_cues), encoding="utf-8")
    offset = _mean_offset_seconds(target_ts_orig, aligned_ts)
    return SyncResult(synced=True, offset_seconds=offset, sync_mode="audio_dtw")
