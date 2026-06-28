import logging

import pytest

import subs_down_n_sync.audio_sync as _audio_mod
from subs_down_n_sync.audio_sync import SyncResult, sync_by_audio, sync_subtitle


def test_sync_subtitle_ref_returns_synced_result(tmp_path, mocker):
    """sync_subtitle (ref-based) retorna synced=True quando offset > threshold."""
    srt = tmp_path / "Filme.pt-BR.srt"
    ref = tmp_path / "Filme.en.srt"
    srt.write_text("1\n00:00:03,000 --> 00:00:05,000\nolá mundo\n", encoding="utf-8")
    ref.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello world\n", encoding="utf-8")

    aligned = [{"start": 1.0, "end": 2.0, "text": "olá mundo"}]
    mocker.patch("subs_down_n_sync.audio_sync._align_cues_by_semantics", return_value=aligned)

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is True
    assert result.sync_mode == "ref"


def test_sync_subtitle_ref_skips_when_offset_below_threshold(tmp_path, mocker):
    """sync_subtitle não altera arquivo quando offset < SYNC_THRESHOLD_SECONDS."""
    srt = tmp_path / "Filme.pt-BR.srt"
    ref = tmp_path / "Filme.en.srt"
    original = "1\n00:00:01,050 --> 00:00:02,000\nolá\n"
    srt.write_text(original, encoding="utf-8")
    ref.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")

    aligned = [{"start": 1.0, "end": 2.0, "text": "olá"}]
    mocker.patch("subs_down_n_sync.audio_sync._align_cues_by_semantics", return_value=aligned)

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is False
    assert srt.read_text(encoding="utf-8") == original


def test_sync_by_audio_linear_offset(tmp_path, mocker):
    """sync_by_audio detecta e aplica offset linear quando std_dev baixo."""
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text(
        "1\n00:00:05,000 --> 00:00:07,000\nolá\n\n2\n00:00:10,000 --> 00:00:12,000\nmundo\n",
        encoding="utf-8",
    )
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    transcript = [
        {"start": 3.0, "end": 5.0, "text": "hello"},
        {"start": 8.0, "end": 10.0, "text": "world"},
    ]
    mocker.patch("subs_down_n_sync.audio_sync._extract_audio")
    mocker.patch("subs_down_n_sync.audio_sync._transcribe", return_value=transcript)

    import numpy as np

    fake_embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
    mock_model = mocker.MagicMock()
    mock_model.encode.return_value = fake_embeddings
    mocker.patch("subs_down_n_sync.audio_sync._get_sentence_model", return_value=mock_model)

    result = sync_by_audio(srt, video)

    assert result.synced is True
    assert result.sync_mode == "audio_linear"


def test_sync_by_audio_returns_no_sync_when_transcript_empty(tmp_path, mocker):
    """sync_by_audio retorna synced=False quando transcrição não produz segmentos."""
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nolá\n", encoding="utf-8")
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    mocker.patch("subs_down_n_sync.audio_sync._extract_audio")
    mocker.patch("subs_down_n_sync.audio_sync._transcribe", return_value=[])

    result = sync_by_audio(srt, video)

    assert result.synced is False
    assert result.sync_mode == "none"


def test_sync_by_audio_passes_model_size(tmp_path, mocker):
    """sync_by_audio passa model_size correto para _transcribe."""
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nolá\n", encoding="utf-8")
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    mocker.patch("subs_down_n_sync.audio_sync._extract_audio")
    mock_transcribe = mocker.patch("subs_down_n_sync.audio_sync._transcribe", return_value=[])

    sync_by_audio(srt, video, model_size="base")

    mock_transcribe.assert_called_once()
    assert mock_transcribe.call_args[0][1] == "base"


def test_sync_result_dataclass():
    """SyncResult é imutável e tem campos corretos."""
    r = SyncResult(synced=True, offset_seconds=2.5, sync_mode="audio_linear")
    assert r.synced is True
    assert r.offset_seconds == pytest.approx(2.5)
    assert r.sync_mode == "audio_linear"


def test_sentence_model_logs_suprimidos():
    """Loggers de bibliotecas de ML devem estar em WARNING para não poluir saída."""
    assert logging.getLogger("faster_whisper").level == logging.WARNING
    assert logging.getLogger("ctranslate2").level == logging.WARNING
    assert logging.getLogger("sentence_transformers").level == logging.WARNING


def test_get_sentence_model_cache_evita_recarga(mocker):
    """_get_sentence_model carrega SentenceTransformer apenas na primeira chamada."""
    _audio_mod._sentence_model_cache = None
    mock_ctor = mocker.patch("subs_down_n_sync.audio_sync.SentenceTransformer")

    _audio_mod._get_sentence_model()
    _audio_mod._get_sentence_model()

    mock_ctor.assert_called_once()


def test_get_whisper_model_cache_evita_recarga(mocker):
    """_get_whisper_model carrega WhisperModel apenas uma vez para mesmo model_size."""
    _audio_mod._whisper_model_cache = None
    mock_ctor = mocker.patch("subs_down_n_sync.audio_sync.WhisperModel")

    _audio_mod._get_whisper_model("tiny")
    _audio_mod._get_whisper_model("tiny")

    mock_ctor.assert_called_once()


def test_get_whisper_model_recarrega_ao_mudar_tamanho(mocker):
    """_get_whisper_model recarrega WhisperModel quando model_size muda."""
    _audio_mod._whisper_model_cache = None
    mock_ctor = mocker.patch("subs_down_n_sync.audio_sync.WhisperModel")

    _audio_mod._get_whisper_model("tiny")
    _audio_mod._get_whisper_model("base")

    assert mock_ctor.call_count == 2
