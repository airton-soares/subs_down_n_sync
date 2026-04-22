"""Testes de integração: exercitam ffsubsync com vídeo real baixado do Blender.

Camada A da estratégia de testes. Rodar com:
    pytest -m integration

Download único e cacheado em tests/fixtures/.cache/.
"""

from __future__ import annotations

import random
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from subs_down_n_sync.exceptions import SubtitleSyncError
from subs_down_n_sync.core import SYNC_THRESHOLD_SECONDS, sync_subtitle_if_needed

pytestmark = pytest.mark.integration

SINTEL_TRAILER_URL = "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4"
CACHE_DIR = Path(__file__).parent / "fixtures" / ".cache"
VIDEO_CACHE = CACHE_DIR / "sintel_trailer-480p.mp4"


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = round((seconds - int(seconds)) * 1000)

    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _make_srt(cues: list[tuple[float, float, str]]) -> str:
    """Gera texto SRT a partir de lista de (start_s, end_s, texto)."""
    lines: list[str] = []

    for i, (start, end, text) in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


@pytest.fixture(scope="session")
def sintel_trailer() -> Path:
    if not _have("ffmpeg"):
        pytest.skip("ffmpeg não instalado")
    if not _have("ffsubsync"):
        pytest.skip("ffsubsync não instalado")

    if VIDEO_CACHE.exists():
        return VIDEO_CACHE

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # User-Agent explícito: servidor do Blender/Cloudflare retorna 403 para "Python-urllib/*".
    request = urllib.request.Request(
        SINTEL_TRAILER_URL,
        headers={"User-Agent": "subs_down_n_sync-tests/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            VIDEO_CACHE.write_bytes(response.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        pytest.skip(f"não foi possível baixar fixture de vídeo: {e}")

    return VIDEO_CACHE


def test_ffsubsync_detects_random_per_cue_shift_and_replaces_original(sintel_trailer, tmp_path):
    """ffsubsync deve detectar dessincronia aleatória por cue (0–2s) e substituir o SRT."""
    # Seed fixa para reprodutibilidade dos shifts entre runs.
    rng = random.Random(42)
    base_cues = [(5.0, 7.0, "cue 1"), (15.0, 17.0, "cue 2"), (30.0, 32.0, "cue 3")]
    shifted_cues = [
        (start + rng.uniform(0.0, 2.0), end + rng.uniform(0.0, 2.0), text)
        for start, end, text in base_cues
    ]

    srt_path = tmp_path / "sintel_trailer-480p.pt-BR.srt"
    srt_path.write_text(_make_srt(shifted_cues), encoding="utf-8")
    original_content = srt_path.read_text(encoding="utf-8")

    result = sync_subtitle_if_needed(sintel_trailer, srt_path)

    # Tolerância larga: ffsubsync não é determinístico em áudios curtos com música.
    assert result.synced is True, (
        f"ffsubsync deveria detectar os shifts aleatórios como acima do limiar "
        f"{SYNC_THRESHOLD_SECONDS}s, mas offset medido foi {result.offset_seconds:.3f}s"
    )
    assert 0.1 <= result.offset_seconds < 6.0, (
        f"offset esperado entre 0.1 e 6.0s, obtido {result.offset_seconds:.3f}s"
    )
    assert srt_path.exists()
    assert srt_path.read_text(encoding="utf-8") != original_content
    assert not list(tmp_path.glob("*.sync.srt")), "não deve restar arquivo .sync.srt temporário"


def test_ffsubsync_fails_cleanly_on_bad_video(tmp_path):
    """ffsubsync deve falhar com SubtitleSyncError ao receber vídeo corrompido."""
    bogus_video = tmp_path / "bogus.mkv"
    bogus_video.write_bytes(b"\x00\x01\x02\x03")

    srt_path = tmp_path / "bogus.pt-BR.srt"
    srt_path.write_text(_make_srt([(1.0, 2.0, "teste")]), encoding="utf-8")

    with pytest.raises(SubtitleSyncError):
        sync_subtitle_if_needed(bogus_video, srt_path)
