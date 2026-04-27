from pathlib import Path

import pytest
from babelfish import Language
from subliminal.video import Episode

from subs_down_n_sync.cli import main
from subs_down_n_sync.core import (
    RunSummary,
    SubtitleInfo,
    SyncResult,
    _align_cues_by_semantics,
    _compute_needs_sync,
    _filename_similarity,
    _mean_offset_seconds,
    _parse_srt_timestamps,
    check_ffmpeg,
    finalize_output_path,
    find_and_download_subtitle,
    find_reference_subtitle,
    load_credentials,
    parse_language,
    run,
    sync_subtitle,
    validate_video_path,
)
from subs_down_n_sync.exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mini.srt"


def test_main_with_no_args_exits_with_code_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "uso" in captured.err.lower() or "usage" in captured.err.lower()


def test_validate_video_path_returns_path_when_valid(tmp_path):
    f = tmp_path / "filme.mkv"
    f.write_bytes(b"\x00" * 10)
    assert validate_video_path(str(f)) == f


def test_validate_video_path_raises_when_missing(tmp_path):
    with pytest.raises(InvalidVideoError, match="não existe"):
        validate_video_path(str(tmp_path / "sumiu.mkv"))


def test_validate_video_path_raises_when_extension_invalid(tmp_path):
    f = tmp_path / "nota.txt"
    f.write_text("oi")
    with pytest.raises(InvalidVideoError, match=r"(?i)extensão"):
        validate_video_path(str(f))


def test_validate_video_path_raises_when_path_is_directory(tmp_path):
    with pytest.raises(InvalidVideoError, match="não é um arquivo"):
        validate_video_path(str(tmp_path))


def test_check_ffmpeg_passes_when_binary_found(mocker):
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )
    check_ffmpeg()  # não deve levantar


def test_check_ffmpeg_raises_when_binary_missing(mocker):
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value=None)
    with pytest.raises(MissingDependencyError, match="ffmpeg"):
        check_ffmpeg()


def test_load_credentials_returns_tuple_when_both_set(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "joao")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "senha123")
    assert load_credentials() == ("joao", "senha123")


def test_load_credentials_raises_when_username_missing(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "x")
    with pytest.raises(MissingCredentialsError, match="OPENSUBTITLES_USERNAME"):
        load_credentials()


def test_load_credentials_raises_when_both_missing(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_USERNAME", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_PASSWORD", raising=False)
    with pytest.raises(MissingCredentialsError) as exc:
        load_credentials()
    assert "OPENSUBTITLES_USERNAME" in str(exc.value)
    assert "OPENSUBTITLES_PASSWORD" in str(exc.value)


def test_parse_language_pt_br_returns_portuguese_brazil():
    lang = parse_language("pt-BR")
    assert lang.alpha3 == "por"
    assert lang.country is not None and lang.country.alpha2 == "BR"


def test_parse_language_en_returns_english():
    lang = parse_language("en")
    assert lang.alpha3 == "eng"


def test_parse_language_es_returns_spanish():
    lang = parse_language("es")
    assert lang.alpha3 == "spa"


def test_parse_language_raises_when_invalid():
    with pytest.raises(InvalidLanguageError, match="xx-YY"):
        parse_language("xx-YY")


@pytest.fixture
def stub_subliminal(mocker):
    """Stuba scan_video/list_subtitles/download_subtitles.

    Retorna o mock do subtitle para os testes configurarem `.get_matches`,
    `.provider_name` e `.text`. A escrita do .srt no disco fica a cargo do
    próprio `find_and_download_subtitle` (write_text em UTF-8), então o stub
    só precisa garantir que `subtitle.text` seja uma string válida.
    """
    fake_video = Episode(
        "Raising.Hope.S01E01.720p.HDTV.X264",
        "Raising Hope",
        1,
        1,
        source="HDTV",
        resolution="720p",
        video_codec="H.264",
    )
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.get_path.return_value = "Filme.pt-BR.srt"
    fake_sub.text = "1\n00:00:01,000 --> 00:00:02,000\noi\n"
    fake_sub.get_matches.return_value = set()
    fake_sub.language = Language("por", country="BR")
    fake_sub.filename = "Filme.pt-BR.srt"

    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch("subs_down_n_sync.core.subliminal.download_subtitles")

    return fake_sub


def test_find_and_download_subtitle_calls_hash_refiner(tmp_path, stub_subliminal, mocker):
    """scan_video não computa hash automaticamente — hash_refine deve ser chamado."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    mock_refine = mocker.patch("subs_down_n_sync.core.hash_refine")

    find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    mock_refine.assert_called_once()


def test_find_and_download_subtitle_returns_path_and_info(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.2024.1080p.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"hash", "release_group"}
    stub_subliminal.get_path.return_value = "Filme.2024.1080p.pt-BR.srt"

    srt_path, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert srt_path.exists()
    assert srt_path.suffix == ".srt"
    assert info.provider == "opensubtitles"
    assert info.match_type == "hash"  # hash tem prioridade


def test_find_and_download_subtitle_raises_when_no_results(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)

    fake_video = Episode("Filme.S01E01", "Filme", 1, 1)
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        return_value={fake_video: []},
    )
    mocker.patch("subs_down_n_sync.core.subliminal.download_subtitles")

    with pytest.raises(SubtitleNotFoundError, match="eng"):
        find_and_download_subtitle(video_path, language=Language("eng"), credentials=("u", "p"))


def test_match_type_is_release_when_no_hash(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"release_group", "resolution"}

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.match_type == "release"


def test_match_type_is_fallback_when_only_title_match(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.match_type == "fallback"


def test_find_and_download_subtitle_writes_utf8(tmp_path, stub_subliminal):
    """Regressão: subliminal.save_subtitles grava bytes no encoding detectado
    (ex.: cp1252) em um arquivo .srt, o que confunde ffsubsync e produz mojibake.
    O código agora pega subtitle.text (já decodificado) e escreve em UTF-8.
    """
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.text = "1\n00:00:01,000 --> 00:00:02,000\nVocê não está lá.\n"

    srt_path, _ = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    raw = srt_path.read_bytes()
    assert raw.decode("utf-8") == stub_subliminal.text
    # Garantir que não caiu em mojibake tipo 'VocÃª' (utf-8 de latin-1 de utf-8)
    assert "Você" in raw.decode("utf-8")
    assert "ę" not in raw.decode("utf-8")


def test_parse_srt_timestamps_extracts_start_times():
    starts = _parse_srt_timestamps(FIXTURE.read_text())
    assert starts == [1.0, 5.0]


def test_mean_offset_seconds_is_zero_when_equal():
    assert _mean_offset_seconds([1.0, 5.0], [1.0, 5.0]) == 0.0


def test_mean_offset_seconds_returns_uniform_shift():
    assert _mean_offset_seconds([1.0, 5.0], [1.5, 5.5]) == pytest.approx(0.5)


def test_mean_offset_seconds_uses_min_length_when_sizes_differ():
    assert _mean_offset_seconds([1.0, 5.0, 10.0], [1.5, 5.5]) == pytest.approx(0.5)


def test_finalize_output_path_renames_with_language_tag(tmp_path):
    video = tmp_path / "Filme.2024.mkv"
    srt = tmp_path / "Filme.2024.pt-BR.srt"
    srt.write_text("conteudo")

    result = finalize_output_path(video, srt, "pt-BR")

    assert result == tmp_path / "Filme.2024.pt-BR.srt"
    assert result.exists()
    assert result.read_text() == "conteudo"


def test_finalize_output_path_overwrites_existing(tmp_path):
    video = tmp_path / "Filme.mkv"
    existing = tmp_path / "Filme.en.srt"
    existing.write_text("velho")
    source = tmp_path / "Filme.eng.srt"
    source.write_text("novo")

    result = finalize_output_path(video, source, "en")

    assert result == tmp_path / "Filme.en.srt"
    assert result.read_text() == "novo"


def test_finalize_output_path_is_noop_when_already_canonical(tmp_path):
    video = tmp_path / "Filme.mkv"
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("x")

    result = finalize_output_path(video, srt, "pt-BR")

    assert result == srt
    assert result.read_text() == "x"


def test_finalize_output_path_handles_different_lang_from_saved_name(tmp_path):
    """subliminal pode salvar como Filme.pob.srt; queremos Filme.pt-BR.srt."""
    video = tmp_path / "Filme.mkv"
    srt = tmp_path / "Filme.pob.srt"
    srt.write_text("conteudo")

    result = finalize_output_path(video, srt, "pt-BR")

    assert result == tmp_path / "Filme.pt-BR.srt"
    assert result.read_text() == "conteudo"
    assert not srt.exists()


def test_finalize_output_path_preserves_dotted_name(tmp_path):
    """Nome com múltiplos pontos (Serie.S01E01.1080p.mkv) → tag de idioma substitui só .mkv."""
    video = tmp_path / "Serie.S01E01.1080p.mkv"
    srt = tmp_path / "Serie.S01E01.1080p.pt-BR.srt"
    srt.write_text("conteudo")

    result = finalize_output_path(video, srt, "pt-BR")

    assert result == tmp_path / "Serie.S01E01.1080p.pt-BR.srt"
    assert result.exists()
    assert result.read_text() == "conteudo"


def test_run_full_pipeline_when_sync_needed(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"
    ref_path = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=True),
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.25, sync_mode="ref"),
    )

    summary = run(str(video), lang_tag="pt-BR")

    assert summary.output_path == tmp_path / "Filme.pt-BR.srt"
    assert summary.output_path.exists()
    assert summary.provider == "opensubtitles"
    assert summary.match_type == "hash"
    assert summary.synced is True
    assert summary.offset_seconds == pytest.approx(1.25)
    assert summary.lang_tag == "pt-BR"


def test_run_keeps_subtitle_when_sync_fails(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.en.srt"
    ref_path = tmp_path / "Filme.en.ref.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=True),
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        side_effect=SubtitleSyncError("boom"),
    )

    summary = run(str(video), lang_tag="en")

    assert summary.output_path == tmp_path / "Filme.en.srt"
    assert summary.output_path.exists()
    assert summary.synced is False
    assert summary.sync_error == "boom"


def test_main_success_prints_summary(tmp_path, monkeypatch, mocker, capsys):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    fake_summary = RunSummary(
        output_path=tmp_path / "Filme.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=True,
        offset_seconds=0.42,
        sync_mode="ref",
        sync_error=None,
        elapsed_seconds=1.23,
        lang_tag="pt-BR",
    )
    mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    code = main([str(video)])

    assert code == 0
    captured = capsys.readouterr()
    assert "opensubtitles" in captured.out
    assert "hash" in captured.out
    assert "0.42" in captured.out


def test_main_lang_flag_uses_custom_language(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    fake_summary = RunSummary(
        output_path=tmp_path / "Filme.en.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.5,
        lang_tag="en",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    code = main([str(video), "--lang", "en"])

    assert code == 0
    assert mock_run.call_args.kwargs["lang_tag"] == "en"


def test_main_expected_error_returns_1(tmp_path, capsys):
    code = main([str(tmp_path / "naoexiste.mkv")])

    assert code == 1
    captured = capsys.readouterr()
    assert "não existe" in captured.err


# --- testes para _filename_similarity ---


def test_filename_similarity_exact_match():
    score = _filename_similarity(
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.srt",
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.mkv",
    )
    assert score == pytest.approx(1.0)


def test_filename_similarity_partial_match():
    score = _filename_similarity(
        "Raising.Hope.S01E03.720p.WEB-DL.DD5.1.H.264-NT.srt",
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.mkv",
    )
    assert 0.0 < score < 1.0


def test_filename_similarity_no_match():
    assert _filename_similarity(
        "totally.different.srt", "Raising.Hope.S01E03.mkv"
    ) == pytest.approx(0.0)


def test_filename_similarity_prefers_closer_release(stub_subliminal):
    """Legenda com tokens mais próximos do vídeo deve ter maior similaridade."""
    score_close = _filename_similarity(
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.srt",
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.mkv",
    )
    score_far = _filename_similarity(
        "Raising.Hope.S01E03.720p.WEB-DL.NT.srt",
        "Raising.Hope.S01E03.720p.HDTV.X264-MRSK.mkv",
    )
    assert score_close > score_far


# --- testes para _compute_needs_sync ---


def test_compute_needs_sync_hash_always_false():
    assert _compute_needs_sync("hash", 0.0) is False
    assert _compute_needs_sync("hash", 1.0) is False


def test_compute_needs_sync_release_always_false():
    assert _compute_needs_sync("release", 0.0) is False
    assert _compute_needs_sync("release", 1.0) is False


def test_compute_needs_sync_fallback_below_threshold_is_true():
    assert _compute_needs_sync("fallback", 0.89) is True


def test_compute_needs_sync_fallback_at_threshold_is_false():
    assert _compute_needs_sync("fallback", 0.9) is False


def test_compute_needs_sync_fallback_above_threshold_is_false():
    assert _compute_needs_sync("fallback", 1.0) is False


def test_compute_needs_sync_existing_below_threshold_is_true():
    assert _compute_needs_sync("existing", 0.5) is True


def test_compute_needs_sync_existing_at_threshold_is_false():
    assert _compute_needs_sync("existing", 0.9) is False


# --- testes para lógica de needs_sync ---


def test_needs_sync_false_when_hash_match(tmp_path, stub_subliminal, mocker):
    """Hash match → needs_sync=False, sem chamar sync."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"hash"}

    mocker.patch(
        "subs_down_n_sync.core.compute_score",
        return_value=971,
    )

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is False
    assert info.match_type == "hash"


def test_needs_sync_false_when_release_group_match(tmp_path, stub_subliminal, mocker):
    """release_group match sem hash → needs_sync=False (bem casado com o release)."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"series", "season", "episode", "release_group"}
    stub_subliminal.filename = "Filme.release_group.srt"

    mocker.patch(
        "subs_down_n_sync.core.compute_score",
        return_value=612,
    )

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is False
    assert info.match_type == "release"


def test_needs_sync_true_when_fallback_low_similarity(tmp_path, stub_subliminal, mocker):
    """Fallback com filename de baixa similaridade → needs_sync=True."""
    video_path = tmp_path / "Filme.2024.1080p.BluRay.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}
    stub_subliminal.filename = "OutroFilme.srt"  # baixa similaridade

    mocker.patch("subs_down_n_sync.core.compute_score", return_value=162)

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is True
    assert info.match_type == "fallback"


def test_needs_sync_false_when_fallback_high_similarity(tmp_path, stub_subliminal, mocker):
    """Fallback com filename de alta similaridade → needs_sync=False."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}
    # Match the full episode name for high similarity (>= 0.9)
    stub_subliminal.filename = "Raising.Hope.S01E01.720p.HDTV.X264.pt-BR.srt"

    mocker.patch("subs_down_n_sync.core.compute_score", return_value=162)

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is False
    assert info.match_type == "fallback"


def test_run_skips_sync_when_needs_sync_false(tmp_path, monkeypatch, mocker):
    """needs_sync=False → sync_subtitle_if_needed não é chamado."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=False),
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mock_sync = mocker.patch("subs_down_n_sync.core.sync_subtitle")

    summary = run(str(video), lang_tag="pt-BR")

    mock_sync.assert_not_called()
    assert summary.synced is False
    assert summary.offset_seconds == 0.0


def test_run_calls_sync_when_needs_sync_true(tmp_path, monkeypatch, mocker):
    """needs_sync=True → find_reference_subtitle e sync_subtitle são chamados."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"
    ref_path = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="fallback", needs_sync=True),
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mock_sync = mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.5),
    )

    summary = run(str(video), lang_tag="pt-BR")

    mock_sync.assert_called_once()
    assert summary.synced is True


def test_run_skips_sync_when_no_reference_available(tmp_path, monkeypatch, mocker):
    """needs_sync=True mas EN não disponível → sem sync, sem erro fatal."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="fallback", needs_sync=True),
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=None)
    mock_sync = mocker.patch("subs_down_n_sync.core.sync_subtitle")

    summary = run(str(video), lang_tag="pt-BR")

    mock_sync.assert_not_called()
    assert summary.synced is False
    assert summary.sync_error is not None


def test_run_resync_uses_existing_subtitle_dotted_name(tmp_path, monkeypatch, mocker):
    """resync=True + nome com pontos (Serie.S01E01.1080p.mkv) → legenda existente encontrada."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Serie.S01E01.1080p.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Serie.S01E01.1080p.pt-BR.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")

    mock_find = mocker.patch("subs_down_n_sync.core.find_and_download_subtitle")
    ref_path = tmp_path / "Serie.S01E01.1080p.en.srt"
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.5, sync_mode="ref"),
    )

    summary = run(str(video), lang_tag="pt-BR", resync=True)

    mock_find.assert_not_called()
    assert summary.provider == "local"
    assert summary.match_type == "existing"
    assert summary.synced is True


def test_run_resync_uses_existing_subtitle_without_api(tmp_path, monkeypatch, mocker):
    """resync=True + legenda existente → find_and_download_subtitle não chamada."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")

    mock_find = mocker.patch("subs_down_n_sync.core.find_and_download_subtitle")
    ref_path = tmp_path / "Filme.en.srt"
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.5, sync_mode="ref"),
    )

    summary = run(str(video), lang_tag="pt-BR", resync=True)

    mock_find.assert_not_called()
    assert summary.provider == "local"
    assert summary.match_type == "existing"
    assert summary.synced is True


def test_run_resync_falls_back_to_api_when_no_existing_subtitle(tmp_path, monkeypatch, mocker):
    """resync=True + sem legenda existente → fluxo normal (download da API)."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    # sem srt existente

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=False),
        )

    mock_find = mocker.patch(
        "subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find
    )

    summary = run(str(video), lang_tag="pt-BR", resync=True)

    mock_find.assert_called_once()
    assert summary.provider == "opensubtitles"


def test_run_resync_warns_but_does_not_rewrite_when_already_synced(tmp_path, monkeypatch, mocker):
    """resync=True + legenda já sincronizada (offset < 0.1s) → synced=False, arquivo inalterado."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    original_content = "1\n00:00:01,000 --> 00:00:02,000\noi\n"
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text(original_content)

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle")
    ref_path = tmp_path / "Filme.en.srt"
    mocker.patch("subs_down_n_sync.core.find_reference_subtitle", return_value=ref_path)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=False, offset_seconds=0.05, sync_mode="none"),
    )

    summary = run(str(video), lang_tag="pt-BR", resync=True)

    assert summary.synced is False
    assert summary.sync_error is None
    assert srt.read_text() == original_content


def test_find_reference_subtitle_returns_path_when_en_found(tmp_path, mocker):
    """find_reference_subtitle retorna path quando EN disponível."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)

    fake_video = Episode("Filme.S01E01", "Filme", 1, 1)
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.get_path.return_value = "Filme.en.srt"
    fake_sub.text = "1\n00:00:01,000 --> 00:00:02,000\nhello\n"
    fake_sub.get_matches.return_value = {"hash"}
    fake_sub.language = Language("eng")

    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch("subs_down_n_sync.core.subliminal.download_subtitles")
    mocker.patch("subs_down_n_sync.core.hash_refine")

    ref_path = find_reference_subtitle(video_path, credentials=("u", "p"))

    assert ref_path is not None
    assert ref_path.suffix == ".srt"
    assert ref_path.exists()


def test_find_reference_subtitle_returns_none_when_en_not_found(tmp_path, mocker):
    """find_reference_subtitle retorna None quando EN não disponível."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)

    fake_video = Episode("Filme.S01E01", "Filme", 1, 1)
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        return_value={fake_video: []},
    )
    mocker.patch("subs_down_n_sync.core.subliminal.download_subtitles")
    mocker.patch("subs_down_n_sync.core.hash_refine")

    ref_path = find_reference_subtitle(video_path, credentials=("u", "p"))

    assert ref_path is None


def test_align_cues_by_semantics_simple_1to1(mocker):
    """Alinhamento 1:1: cues semânticamente equivalentes recebem timestamps da ref."""
    import numpy as np

    ref_cues = [
        {"start": 3.0, "end": 5.0, "text": "hello world"},
        {"start": 11.0, "end": 13.0, "text": "good morning"},
    ]
    target_cues = [
        {"start": 2.0, "end": 4.0, "text": "olá mundo"},
        {"start": 10.0, "end": 12.0, "text": "bom dia"},
    ]

    fake_embeddings = {
        "hello world": np.array([1.0, 0.0]),
        "good morning": np.array([0.0, 1.0]),
        "olá mundo": np.array([0.99, 0.01]),
        "bom dia": np.array([0.01, 0.99]),
    }

    mock_model = mocker.MagicMock()
    mock_model.encode.side_effect = lambda texts, **kw: np.array(
        [fake_embeddings[t] for t in texts]
    )
    mocker.patch("subs_down_n_sync.core.SentenceTransformer", return_value=mock_model)

    result = _align_cues_by_semantics(target_cues, ref_cues)

    assert result[0]["start"] == pytest.approx(3.0)
    assert result[0]["end"] == pytest.approx(5.0)
    assert result[1]["start"] == pytest.approx(11.0)
    assert result[1]["end"] == pytest.approx(13.0)
    assert result[0]["text"] == "olá mundo"
    assert result[1]["text"] == "bom dia"


def test_align_cues_by_semantics_preserves_target_duration(mocker):
    """End-time deve respeitar duração do target, não copiar do ref (mais curto)."""
    import numpy as np

    ref_cues = [
        {"start": 10.0, "end": 11.0, "text": "hi"},
    ]
    target_cues = [
        {"start": 5.0, "end": 8.0, "text": "frase portuguesa mais longa"},
    ]

    fake_embeddings = {
        "hi": np.array([1.0, 0.0]),
        "frase portuguesa mais longa": np.array([0.99, 0.01]),
    }

    mock_model = mocker.MagicMock()
    mock_model.encode.side_effect = lambda texts, **kw: np.array(
        [fake_embeddings[t] for t in texts]
    )
    mocker.patch("subs_down_n_sync.core.SentenceTransformer", return_value=mock_model)

    result = _align_cues_by_semantics(target_cues, ref_cues)

    assert result[0]["start"] == pytest.approx(10.0)
    assert result[0]["end"] == pytest.approx(13.0)


def test_align_cues_by_semantics_enforces_min_reading_duration(mocker):
    """Duração mínima de leitura aplicada se target original curto demais."""
    import numpy as np

    ref_cues = [
        {"start": 10.0, "end": 10.2, "text": "hi"},
    ]
    target_cues = [
        {"start": 5.0, "end": 5.2, "text": "uma frase bem grande que precisa de tempo"},
    ]

    fake_embeddings = {
        "hi": np.array([1.0, 0.0]),
        "uma frase bem grande que precisa de tempo": np.array([0.99, 0.01]),
    }

    mock_model = mocker.MagicMock()
    mock_model.encode.side_effect = lambda texts, **kw: np.array(
        [fake_embeddings[t] for t in texts]
    )
    mocker.patch("subs_down_n_sync.core.SentenceTransformer", return_value=mock_model)

    result = _align_cues_by_semantics(target_cues, ref_cues)

    duration = result[0]["end"] - result[0]["start"]
    expected_min = len(target_cues[0]["text"]) * 0.06
    assert duration >= expected_min


def test_align_cues_by_semantics_clamps_end_to_next_start(mocker):
    """End do cue i não deve invadir start do cue i+1 (mantém gap mínimo)."""
    import numpy as np

    ref_cues = [
        {"start": 10.0, "end": 15.0, "text": "first"},
        {"start": 11.0, "end": 12.0, "text": "second"},
    ]
    target_cues = [
        {"start": 5.0, "end": 10.0, "text": "primeiro longo"},
        {"start": 10.5, "end": 11.0, "text": "segundo"},
    ]

    def fake_encode(texts, **kw):
        mapping = {"first": 0, "second": 1, "primeiro longo": 0, "segundo": 1}
        return np.array([np.eye(2)[mapping[t]] for t in texts])

    mock_model = mocker.MagicMock()
    mock_model.encode.side_effect = fake_encode
    mocker.patch("subs_down_n_sync.core.SentenceTransformer", return_value=mock_model)

    result = _align_cues_by_semantics(target_cues, ref_cues)

    assert result[0]["end"] < result[1]["start"], "end invade próximo start"


def test_align_cues_by_semantics_preserves_order(mocker):
    """Timestamps resultantes devem ser monotonicamente crescentes."""
    import numpy as np

    ref_cues = [
        {"start": 1.0, "end": 2.0, "text": "first"},
        {"start": 3.0, "end": 4.0, "text": "second"},
        {"start": 5.0, "end": 6.0, "text": "third"},
    ]
    target_cues = [
        {"start": 0.5, "end": 1.5, "text": "primeiro"},
        {"start": 2.5, "end": 3.5, "text": "segundo"},
        {"start": 4.5, "end": 5.5, "text": "terceiro"},
    ]

    def fake_encode(texts, **kw):
        mapping = {"first": 0, "second": 1, "third": 2, "primeiro": 0, "segundo": 1, "terceiro": 2}
        return np.array([np.eye(3)[mapping[t]] for t in texts])

    mock_model = mocker.MagicMock()
    mock_model.encode.side_effect = fake_encode
    mocker.patch("subs_down_n_sync.core.SentenceTransformer", return_value=mock_model)

    result = _align_cues_by_semantics(target_cues, ref_cues)

    starts = [c["start"] for c in result]
    assert starts == sorted(starts), "timestamps devem ser monotonicamente crescentes"


def test_sync_subtitle_uses_semantic_alignment(tmp_path, mocker):
    """sync_subtitle chama _align_cues_by_semantics e reescreve srt com novos timestamps."""
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text(
        "1\n00:00:02,000 --> 00:00:04,000\nolá mundo\n\n2\n00:00:10,000 --> 00:00:12,000\nbom dia\n"
    )
    ref = tmp_path / "Filme.en.srt"
    ref.write_text(
        "1\n00:00:03,000 --> 00:00:05,000\nhello world\n\n"
        "2\n00:00:11,000 --> 00:00:13,000\ngood morning\n"
    )

    aligned_cues = [
        {"start": 3.0, "end": 5.0, "text": "olá mundo"},
        {"start": 11.0, "end": 13.0, "text": "bom dia"},
    ]
    mocker.patch("subs_down_n_sync.core._align_cues_by_semantics", return_value=aligned_cues)

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is True
    assert result.sync_mode == "ref"
    assert result.offset_seconds == pytest.approx(1.0)
    synced = srt.read_text()
    assert "00:00:03,000" in synced
    assert "00:00:11,000" in synced


def test_sync_subtitle_raises_when_alignment_fails(tmp_path, mocker):
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
    ref = tmp_path / "Filme.en.srt"
    ref.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
    original_text = srt.read_text()

    mocker.patch(
        "subs_down_n_sync.core._align_cues_by_semantics",
        side_effect=RuntimeError("modelo falhou"),
    )

    with pytest.raises(SubtitleSyncError, match="alinhamento semântico falhou"):
        sync_subtitle(srt, ref_path=ref)

    assert srt.read_text() == original_text


def test_sync_subtitle_returns_not_synced_when_offset_below_threshold(tmp_path, mocker):
    srt = tmp_path / "Filme.pt-BR.srt"
    original_text = "1\n00:00:01,000 --> 00:00:02,000\nlinha 1\n"
    srt.write_text(original_text)
    ref = tmp_path / "Filme.en.srt"
    ref.write_text("1\n00:00:01,000 --> 00:00:02,000\nline 1\n")

    aligned_cues = [{"start": 1.05, "end": 2.05, "text": "linha 1"}]
    mocker.patch("subs_down_n_sync.core._align_cues_by_semantics", return_value=aligned_cues)

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is False
    assert srt.read_text() == original_text


def test_sync_subtitle_reads_latin1_encoded_file(tmp_path, mocker):
    """Legenda em Latin-1 (cp1252) é lida corretamente e salva em UTF-8."""
    srt = tmp_path / "Filme.pt-BR.srt"
    content = "1\n00:00:02,000 --> 00:00:04,000\nação dramática\n\n2\n00:00:10,000 --> 00:00:12,000\ncoração\n"
    srt.write_bytes(content.encode("latin-1"))

    ref = tmp_path / "Filme.en.srt"
    ref.write_text(
        "1\n00:00:03,000 --> 00:00:05,000\ndramatic action\n\n2\n00:00:11,000 --> 00:00:13,000\nheart\n"
    )

    aligned_cues = [
        {"start": 3.0, "end": 5.0, "text": "ação dramática"},
        {"start": 11.0, "end": 13.0, "text": "coração"},
    ]
    mocker.patch("subs_down_n_sync.core._align_cues_by_semantics", return_value=aligned_cues)

    result = sync_subtitle(srt, ref_path=ref)

    assert result.synced is True
    output = srt.read_text(encoding="utf-8")
    assert "ação" in output
    assert "coração" in output


def test_build_parser_accepts_directory_path(tmp_path):
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args([str(tmp_path)])
    assert args.path == str(tmp_path)


def test_build_parser_resync_flag_defaults_to_false():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path"])
    assert args.resync is False


def test_build_parser_resync_flag_sets_true():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path", "--resync"])
    assert args.resync is True


def test_build_parser_resync_short_flag():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path", "-r"])
    assert args.resync is True


def test_run_directory_processes_all_videos(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    v1 = tmp_path / "a.mkv"
    v2 = tmp_path / "b.mp4"
    v1.write_bytes(b"\x00")
    v2.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=tmp_path / "a.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", resync=False)

    assert mock_run.call_count == 2
    assert len(results) == 2
    assert len(skipped) == 0
    assert len(errors) == 0


def test_run_directory_skips_when_srt_exists_and_no_resync(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")
    srt = tmp_path / "filme.pt-BR.srt"
    srt.write_text("legenda")

    mock_run = mocker.patch("subs_down_n_sync.cli.run")

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", resync=False)

    mock_run.assert_not_called()
    assert len(skipped) == 1
    assert skipped[0] == v
    assert len(results) == 0


def test_run_directory_processes_existing_srt_when_resync_true(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")
    srt = tmp_path / "filme.pt-BR.srt"
    srt.write_text("legenda")

    fake_summary = RunSummary(
        output_path=srt,
        provider="local",
        match_type="existing",
        synced=True,
        offset_seconds=1.2,
        sync_mode="ref",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", resync=True)

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs.get("resync") is True
    assert len(results) == 1
    assert len(skipped) == 0


def test_run_directory_continues_after_error(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary
    from subs_down_n_sync.exceptions import SubsDownError

    v1 = tmp_path / "a.mkv"
    v2 = tmp_path / "b.mkv"
    v1.write_bytes(b"\x00")
    v2.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=tmp_path / "b.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )

    def side_effect(path, **kwargs):
        if "a.mkv" in path:
            raise SubsDownError("falhou")
        return fake_summary

    mocker.patch("subs_down_n_sync.cli.run", side_effect=side_effect)

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", resync=False)

    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0][0] == v1
    assert "falhou" in errors[0][1]


def test_run_directory_finds_videos_recursively(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    subdir = tmp_path / "sub"
    subdir.mkdir()
    v = subdir / "filme.mkv"
    v.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=subdir / "filme.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", resync=False)

    mock_run.assert_called_once()
    assert len(results) == 1


def test_run_directory_empty_dir_returns_empty_lists(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory

    mock_run = mocker.patch("subs_down_n_sync.cli.run")

    results, skipped, errors = _run_directory(tmp_path, lang_tag="pt-BR", overwrite=False)

    mock_run.assert_not_called()
    assert results == []
    assert skipped == []
    assert errors == []


def test_main_dispatches_to_run_directory_when_path_is_dir(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mock_run_dir = mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [], []),
    )

    code = main([str(tmp_path)])

    mock_run_dir.assert_called_once_with(
        tmp_path, lang_tag="pt-BR", overwrite=False, resync=False, parallel=False
    )
    assert code == 0


def test_main_returns_1_when_directory_has_errors(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [], [(v, "sem legenda")]),
    )

    code = main([str(tmp_path)])

    assert code == 1


def test_main_returns_0_when_directory_all_skipped(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [v], []),
    )

    code = main([str(tmp_path)])

    assert code == 0


def test_main_returns_1_when_path_does_not_exist(tmp_path):
    from subs_down_n_sync.cli import main

    code = main([str(tmp_path / "naoexiste")])

    assert code == 1


def test_main_passes_overwrite_flag_to_run_directory(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mock_run_dir = mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [], []),
    )

    main([str(tmp_path), "--overwrite"])

    mock_run_dir.assert_called_once_with(
        tmp_path, lang_tag="pt-BR", overwrite=True, resync=False, parallel=False
    )


def test_build_parser_parallel_flag_defaults_to_false():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path"])
    assert args.parallel is False


def test_build_parser_parallel_flag_sets_true():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path", "--parallel"])
    assert args.parallel is True


def test_build_parser_parallel_short_flag():
    from subs_down_n_sync.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["/any/path", "-p"])
    assert args.parallel is True


def test_main_passes_parallel_flag_to_run_directory(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mock_run_dir = mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [], []),
    )

    main([str(tmp_path), "--parallel"])

    mock_run_dir.assert_called_once_with(
        tmp_path, lang_tag="pt-BR", overwrite=False, resync=False, parallel=True
    )


def test_run_directory_parallel_processes_all_videos(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    v1 = tmp_path / "a.mkv"
    v2 = tmp_path / "b.mp4"
    v3 = tmp_path / "c.mkv"
    for v in (v1, v2, v3):
        v.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=tmp_path / "a.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    results, skipped, errors = _run_directory(
        tmp_path, lang_tag="pt-BR", overwrite=False, parallel=True
    )

    assert mock_run.call_count == 3
    assert len(results) == 3
    assert len(errors) == 0


def test_run_directory_parallel_continues_after_error(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary
    from subs_down_n_sync.exceptions import SubsDownError

    v1 = tmp_path / "a.mkv"
    v2 = tmp_path / "b.mkv"
    v1.write_bytes(b"\x00")
    v2.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=tmp_path / "b.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )

    def side_effect(path, **kwargs):
        if "a.mkv" in path:
            raise SubsDownError("falhou")
        return fake_summary

    mocker.patch("subs_down_n_sync.cli.run", side_effect=side_effect)

    results, skipped, errors = _run_directory(
        tmp_path, lang_tag="pt-BR", overwrite=False, parallel=True
    )

    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0][0] == v1


def test_run_directory_invokes_on_progress_callback(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    fake_summary = RunSummary(
        output_path=tmp_path / "filme.pt-BR.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )

    def fake_run(path, lang_tag, on_progress=None, **kwargs):
        assert on_progress is not None
        on_progress("validando", path)
        on_progress("baixado", "ok")
        return fake_summary

    mocker.patch("subs_down_n_sync.cli.run", side_effect=fake_run)

    results, _, _ = _run_directory(tmp_path, lang_tag="pt-BR", overwrite=False)

    assert len(results) == 1


def test_main_passes_resync_flag_to_run_directory(tmp_path, mocker):
    from subs_down_n_sync.cli import main

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")

    mock_run_dir = mocker.patch(
        "subs_down_n_sync.cli._run_directory",
        return_value=([], [], []),
    )

    main([str(tmp_path), "--resync"])

    mock_run_dir.assert_called_once_with(
        tmp_path, lang_tag="pt-BR", overwrite=False, resync=True, parallel=False
    )


def test_run_directory_overwrite_wins_over_resync(tmp_path, mocker):
    from subs_down_n_sync.cli import _run_directory
    from subs_down_n_sync.core import RunSummary

    v = tmp_path / "filme.mkv"
    v.write_bytes(b"\x00")
    srt = tmp_path / "filme.pt-BR.srt"
    srt.write_text("legenda")

    fake_summary = RunSummary(
        output_path=srt,
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
        sync_mode="none",
        sync_error=None,
        elapsed_seconds=0.1,
        lang_tag="pt-BR",
    )
    mock_run = mocker.patch("subs_down_n_sync.cli.run", return_value=fake_summary)

    results, skipped, errors = _run_directory(
        tmp_path, lang_tag="pt-BR", overwrite=True, resync=True
    )

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs.get("resync") is False  # overwrite vence
    assert len(results) == 1
