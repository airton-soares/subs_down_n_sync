import shutil as shutil_
from pathlib import Path

import pytest
from babelfish import Language
from subliminal.video import Episode

from subs_down_n_sync.cli import main
from subs_down_n_sync.core import (
    RunSummary,
    SubtitleInfo,
    SyncResult,
    _mean_offset_seconds,
    _parse_srt_timestamps,
    align_subtitle_to_reference,
    check_alass,
    check_ffmpeg,
    finalize_output_path,
    find_and_download_subtitle,
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


def test_check_alass_raises_when_binary_missing(mocker):
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value=None)
    with pytest.raises(MissingDependencyError, match="alass"):
        check_alass()


def test_check_alass_passes_when_binary_found(mocker):
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/alass")
    check_alass()  # não deve levantar


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

    srt_path, info, _ = find_and_download_subtitle(
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

    _, info, _ = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.match_type == "release"


def test_match_type_is_fallback_when_only_title_match(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    _, info, _ = find_and_download_subtitle(
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

    srt_path, _, _ref = find_and_download_subtitle(
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


def test_run_full_pipeline_when_sync_needed(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=True),
            None,
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.25),
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
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=True),
            None,
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
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
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

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
    assert "Filme.pt-BR.srt" in captured.out


def test_main_lang_flag_uses_custom_language(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

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

    _, info, _ = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is False
    assert info.match_type == "hash"


def test_needs_sync_false_when_release_group_match(tmp_path, stub_subliminal, mocker):
    """release_group match → needs_sync=False."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"series", "season", "episode", "release_group"}

    mocker.patch(
        "subs_down_n_sync.core.compute_score",
        return_value=612,
    )

    _, info, _ = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is False
    assert info.match_type == "release"


def test_needs_sync_true_when_fallback_match(tmp_path, stub_subliminal, mocker):
    """Só title match → needs_sync=True."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    mocker.patch(
        "subs_down_n_sync.core.compute_score",
        return_value=162,
    )

    _, info, _ = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.needs_sync is True
    assert info.match_type == "fallback"


def test_run_skips_sync_when_needs_sync_false(tmp_path, monkeypatch, mocker):
    """needs_sync=False → sync_subtitle_if_needed não é chamado."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="hash", needs_sync=False),
            None,
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mock_sync = mocker.patch("subs_down_n_sync.core.sync_subtitle")

    summary = run(str(video), lang_tag="pt-BR")

    mock_sync.assert_not_called()
    assert summary.synced is False
    assert summary.offset_seconds == 0.0


def test_run_calls_sync_when_needs_sync_true(tmp_path, monkeypatch, mocker):
    """needs_sync=True → sync_subtitle_if_needed é chamado."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="fallback", needs_sync=True),
            None,
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mock_sync = mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.5),
    )

    summary = run(str(video), lang_tag="pt-BR")

    mock_sync.assert_called_once()
    assert summary.synced is True


def test_find_and_download_subtitle_returns_ref_path_when_en_available(
    tmp_path, stub_subliminal, mocker
):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    fake_ref_sub = mocker.MagicMock()
    fake_ref_sub.provider_name = "opensubtitles"
    fake_ref_sub.get_path.return_value = "Filme.en.srt"
    fake_ref_sub.text = "1\n00:00:01,000 --> 00:00:02,000\nhi\n"
    fake_ref_sub.get_matches.return_value = {"hash"}  # hash → needs_sync=False
    fake_ref_sub.language = Language("eng")

    stub_subliminal.language = Language("por", country="BR")

    # pt-BR score baixo (fallback), en score alto (hash) → só en é confiável como ref
    mocker.patch(
        "subs_down_n_sync.core.compute_score",
        side_effect=lambda sub, video: 971 if sub is fake_ref_sub else 100,
    )

    en_lang = Language("eng")

    def list_subtitles_side_effect(videos, languages, **kwargs):
        video = list(videos)[0]
        result = {video: []}
        for lang in languages:
            if lang == en_lang:
                result[video].append(fake_ref_sub)
            else:
                result[video].append(stub_subliminal)
        return result

    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        side_effect=list_subtitles_side_effect,
    )

    srt_path, info, ref_path = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert ref_path is not None
    assert ref_path.suffix == ".srt"
    assert ref_path.exists()


def test_find_and_download_subtitle_ref_path_none_when_target_is_en(
    tmp_path, stub_subliminal, mocker
):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}
    stub_subliminal.language = Language("eng")
    mocker.patch("subs_down_n_sync.core.compute_score", return_value=100)

    srt_path, info, ref_path = find_and_download_subtitle(
        video_path,
        language=Language("eng"),
        credentials=("u", "p"),
    )

    assert ref_path is None


def test_sync_subtitle_uses_align_when_ref_available(tmp_path):
    """Com ref_path: aplica align_subtitle_to_reference sem chamar alass."""
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    # ref começa em 74s, pt começa em 2s → shift de ~72s
    ref_text = "1\n00:01:14,000 --> 00:01:16,000\nhi\n"
    srt = tmp_path / "Filme.pt-BR.srt"
    srt.write_text("1\n00:00:02,000 --> 00:00:04,000\noi\n")

    ref = tmp_path / "Filme.en.srt"
    ref.write_text(ref_text)

    result = sync_subtitle(video, srt, ref_path=ref)

    assert result.synced is True
    assert result.sync_mode == "ref"
    # primeiro timestamp deve estar próximo de 74s
    timestamps = _parse_srt_timestamps(srt.read_text())
    assert abs(timestamps[0] - 74.0) < 1.0


def test_sync_subtitle_uses_video_when_ref_not_available(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    synced_text = "1\n00:00:03,000 --> 00:00:04,000\nlinha 1\n"

    def fake_run(cmd, capture_output, text, check):
        assert str(video) == cmd[1]  # vídeo é segundo argumento
        assert str(srt) == cmd[2]  # alvo é terceiro
        Path(cmd[3]).write_text(synced_text)
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle(video, srt, ref_path=None)

    assert result.synced is True
    assert result.sync_mode == "video"


def test_sync_subtitle_raises_when_alass_fails(tmp_path, mocker):
    import subprocess as subprocess_

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess_.CalledProcessError(1, "alass", stderr="erro alass"),
    )

    with pytest.raises(SubtitleSyncError, match="alass"):
        sync_subtitle(video, srt, ref_path=None)

    assert srt.read_text() == FIXTURE.read_text()


def test_sync_subtitle_returns_not_synced_when_output_identical(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)
    original_text = srt.read_text()

    def fake_run(cmd, capture_output, text, check):
        Path(cmd[3]).write_text(original_text)
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle(video, srt, ref_path=None)

    assert result.synced is False
    assert srt.read_text() == original_text


def test_find_and_download_subtitle_ref_path_none_when_en_not_available(
    tmp_path, stub_subliminal, mocker
):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}
    stub_subliminal.language = Language("por", country="BR")
    mocker.patch("subs_down_n_sync.core.compute_score", return_value=100)

    def list_subtitles_side_effect(videos, languages, **kwargs):
        video = list(videos)[0]
        result = {video: [stub_subliminal]}  # só pt-BR, sem en
        return result

    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        side_effect=list_subtitles_side_effect,
    )

    srt_path, info, ref_path = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert ref_path is None


def test_find_and_download_subtitle_ref_path_none_when_en_needs_sync(
    tmp_path, stub_subliminal, mocker
):
    """en com score baixo (fallback) → ref_path=None, evita referência não confiável."""
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}
    stub_subliminal.language = Language("por", country="BR")

    fake_ref_sub = mocker.MagicMock()
    fake_ref_sub.provider_name = "opensubtitles"
    fake_ref_sub.get_path.return_value = "Filme.en.srt"
    fake_ref_sub.text = "1\n00:00:01,000 --> 00:00:02,000\nhi\n"
    fake_ref_sub.get_matches.return_value = {"title"}  # fallback — needs_sync=True
    fake_ref_sub.language = Language("eng")

    en_lang = Language("eng")

    def list_subtitles_side_effect(videos, languages, **kwargs):
        video = list(videos)[0]
        result = {video: []}
        for lang in languages:
            if lang == en_lang:
                result[video].append(fake_ref_sub)
            else:
                result[video].append(stub_subliminal)
        return result

    mocker.patch(
        "subs_down_n_sync.core.subliminal.list_subtitles",
        side_effect=list_subtitles_side_effect,
    )

    # score baixo para ambos (fallback)
    mocker.patch("subs_down_n_sync.core.compute_score", return_value=100)

    srt_path, info, ref_path = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert ref_path is None  # en não confiável → não usar como referência


def test_run_deletes_ref_path_after_sync(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch(
        "subs_down_n_sync.core.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}",
    )

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"
    ref_path = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        ref_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        return (
            downloaded_path,
            SubtitleInfo(provider="opensubtitles", match_type="fallback", needs_sync=True),
            ref_path,
        )

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle",
        return_value=SyncResult(synced=True, offset_seconds=1.5, sync_mode="ref"),
    )

    run(str(video), lang_tag="pt-BR")

    assert not ref_path.exists()


# --- testes para align_subtitle_to_reference ---


def test_align_subtitle_shifts_and_scales_timestamps():
    """Shift + FPS scale aplicados corretamente."""
    # ref começa em 74s, pt começa em 2.951s → shift = 74 - 2.951 = 71.049s
    # FPS: pt em 25fps, ref em 23.976fps → scale = 23.976/25
    ref_text = "1\n00:01:14,000 --> 00:01:16,000\nhi\n"
    pt_text = "1\n00:00:02,951 --> 00:00:05,053\noi\n\n2\n00:00:05,054 --> 00:00:07,288\ndois\n"

    result = align_subtitle_to_reference(pt_text, ref_text)

    # primeiro cue deve começar perto de 74s
    timestamps = _parse_srt_timestamps(result)
    assert abs(timestamps[0] - 74.0) < 1.0


def test_align_subtitle_returns_valid_srt():
    """Output é SRT válido com timestamps positivos."""
    ref_text = "1\n00:01:14,000 --> 00:01:16,000\nhi\n"
    pt_text = "1\n00:00:02,951 --> 00:00:05,053\noi\n"

    result = align_subtitle_to_reference(pt_text, ref_text)

    assert "-->" in result
    timestamps = _parse_srt_timestamps(result)
    assert all(t >= 0 for t in timestamps)


# --- testes para opensubtitlescom como provider ---


def test_find_and_download_subtitle_uses_opensubtitlescom_when_api_key_set(
    tmp_path, stub_subliminal, mocker, monkeypatch
):
    """OPENSUBTITLESCOM_API_KEY setada → opensubtitlescom incluído nos providers."""
    monkeypatch.setenv("OPENSUBTITLESCOM_API_KEY", "test-api-key")

    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    captured_providers = []

    def capture_list(videos, languages, *, providers=None, **kwargs):
        captured_providers.extend(providers or [])
        video = list(videos)[0]
        return {video: [stub_subliminal]}

    mocker.patch("subs_down_n_sync.core.subliminal.list_subtitles", side_effect=capture_list)

    find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert "opensubtitlescom" in captured_providers


def test_find_and_download_subtitle_omits_opensubtitlescom_when_no_api_key(
    tmp_path, stub_subliminal, mocker, monkeypatch
):
    """OPENSUBTITLESCOM_API_KEY ausente → só opensubtitles."""
    monkeypatch.delenv("OPENSUBTITLESCOM_API_KEY", raising=False)

    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.get_matches.return_value = {"title"}

    captured_providers = []

    def capture_list(videos, languages, *, providers=None, **kwargs):
        captured_providers.extend(providers or [])
        video = list(videos)[0]
        return {video: [stub_subliminal]}

    mocker.patch("subs_down_n_sync.core.subliminal.list_subtitles", side_effect=capture_list)

    find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )

    assert "opensubtitlescom" not in captured_providers
    assert "opensubtitles" in captured_providers
