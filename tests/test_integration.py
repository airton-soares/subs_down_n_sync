"""Testes de integração: exercitam sentence-transformers com legendas reais.

Rodar com:
    pytest -m integration
"""

from __future__ import annotations

import pytest

from subs_down_n_sync.core import SYNC_THRESHOLD_SECONDS, _align_cues_by_semantics, sync_subtitle

pytestmark = pytest.mark.integration


def _make_cues(pairs: list[tuple[float, float, str]]) -> list[dict]:
    return [{"start": s, "end": e, "text": t} for s, e, t in pairs]


def test_align_cues_by_semantics_real_model_1to1():
    """Modelo real deve alinhar cues semanticamente equivalentes EN→pt-BR."""
    ref_cues = _make_cues(
        [
            (1.0, 3.0, "Hello, how are you?"),
            (5.0, 7.0, "I am fine, thank you."),
            (10.0, 12.0, "See you tomorrow."),
        ]
    )
    target_cues = _make_cues(
        [
            (0.5, 2.5, "Olá, como vai você?"),
            (4.5, 6.5, "Estou bem, obrigado."),
            (9.5, 11.5, "Até amanhã."),
        ]
    )

    result = _align_cues_by_semantics(target_cues, ref_cues)

    assert len(result) == 3
    # timestamps devem ser os da referência EN
    assert result[0]["start"] == pytest.approx(1.0, abs=0.5)
    assert result[1]["start"] == pytest.approx(5.0, abs=0.5)
    assert result[2]["start"] == pytest.approx(10.0, abs=0.5)
    # textos originais pt-BR preservados
    assert result[0]["text"] == "Olá, como vai você?"
    assert result[1]["text"] == "Estou bem, obrigado."
    assert result[2]["text"] == "Até amanhã."


def test_align_cues_by_semantics_preserves_monotonic_order_real_model():
    """Timestamps resultantes devem ser monotonicamente crescentes com modelo real."""
    ref_cues = _make_cues(
        [
            (2.0, 4.0, "First line of dialogue."),
            (6.0, 8.0, "Second line of dialogue."),
            (12.0, 14.0, "Third line of dialogue."),
        ]
    )
    target_cues = _make_cues(
        [
            (1.0, 3.0, "Primeira linha de diálogo."),
            (5.0, 7.0, "Segunda linha de diálogo."),
            (11.0, 13.0, "Terceira linha de diálogo."),
        ]
    )

    result = _align_cues_by_semantics(target_cues, ref_cues)

    starts = [c["start"] for c in result]
    assert starts == sorted(starts), f"timestamps não monotônicos: {starts}"


def test_sync_subtitle_real_model(tmp_path):
    """sync_subtitle com modelo real deve detectar dessincronia e corrigir."""
    ref = tmp_path / "ref.en.srt"
    ref.write_text(
        "1\n00:00:03,000 --> 00:00:05,000\nHello, how are you?\n\n"
        "2\n00:00:08,000 --> 00:00:10,000\nI am fine, thank you.\n",
        encoding="utf-8",
    )

    srt = tmp_path / "target.pt-BR.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nOlá, como vai você?\n\n"
        "2\n00:00:06,000 --> 00:00:08,000\nEstou bem, obrigado.\n",
        encoding="utf-8",
    )

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is True, (
        f"esperava sync=True (offset ≥ {SYNC_THRESHOLD_SECONDS}s), "
        f"obtido offset={result.offset_seconds:.3f}s"
    )
    assert result.offset_seconds >= SYNC_THRESHOLD_SECONDS
    assert result.sync_mode == "ref"

    synced_text = srt.read_text(encoding="utf-8")
    assert "00:00:03" in synced_text or "00:00:08" in synced_text
