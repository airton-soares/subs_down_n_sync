import shutil as shutil_
from pathlib import Path

import pytest
from babelfish import Language

from subs_down_n_sync.cli import main
from subs_down_n_sync.core import (
    RunSummary,
    SubtitleInfo,
    SyncResult,
    _mean_offset_seconds,
    _parse_srt_timestamps,
    check_ffmpeg,
    finalize_output_path,
    find_and_download_subtitle,
    load_credentials,
    parse_language,
    run,
    sync_subtitle_if_needed,
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
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")
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
    """Stuba scan_video/download_best_subtitles.

    Retorna o mock do subtitle para os testes configurarem `.get_matches`,
    `.provider_name` e `.text`. A escrita do .srt no disco fica a cargo do
    próprio `find_and_download_subtitle` (write_text em UTF-8), então o stub
    só precisa garantir que `subtitle.text` seja uma string válida.
    """
    fake_video = mocker.MagicMock(name="Video")
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.get_path.return_value = "Filme.pt-BR.srt"
    fake_sub.text = "1\n00:00:01,000 --> 00:00:02,000\noi\n"
    fake_sub.get_matches.return_value = set()

    mocker.patch(
        "subs_down_n_sync.core.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )

    return fake_sub


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

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.core.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.core.subliminal.download_best_subtitles",
        return_value={fake_video: []},
    )

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


def test_sync_skips_replacement_when_offset_below_threshold(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    def fake_run(cmd, capture_output, text, check):  # noqa: ARG001
        out = Path([a for a in cmd if a.endswith(".sync.srt")][0])
        out.write_text(
            "1\n00:00:01,050 --> 00:00:02,050\nlinha 1\n\n"
            "2\n00:00:05,050 --> 00:00:06,050\nlinha 2\n"
        )
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle_if_needed(video, srt)
    assert result == SyncResult(synced=False, offset_seconds=pytest.approx(0.05))
    assert srt.read_text() == FIXTURE.read_text()


def test_sync_replaces_original_when_offset_above_threshold(tmp_path, mocker):
    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    synced_text = (
        "1\n00:00:03,000 --> 00:00:04,000\nlinha 1\n\n2\n00:00:07,000 --> 00:00:08,000\nlinha 2\n"
    )

    def fake_run(cmd, capture_output, text, check):  # noqa: ARG001
        out = Path([a for a in cmd if a.endswith(".sync.srt")][0])
        out.write_text(synced_text)
        return mocker.MagicMock(returncode=0, stdout="", stderr="")

    mocker.patch("subprocess.run", side_effect=fake_run)

    result = sync_subtitle_if_needed(video, srt)
    assert result.synced is True
    assert result.offset_seconds == pytest.approx(2.0)
    assert srt.read_text() == synced_text


def test_sync_raises_when_ffsubsync_fails(tmp_path, mocker):
    import subprocess

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)
    srt = tmp_path / "Filme.pt-BR.srt"
    shutil_.copy(FIXTURE, srt)

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "ffsubsync", stderr="boom"),
    )

    with pytest.raises(SubtitleSyncError, match="ffsubsync"):
        sync_subtitle_if_needed(video, srt)
    assert srt.read_text() == FIXTURE.read_text()


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
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.pt-BR.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return downloaded_path, SubtitleInfo(provider="opensubtitles", match_type="hash")

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle_if_needed",
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


def test_run_keeps_subtitle_when_ffsubsync_fails(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "user")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "pass")
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    downloaded_path = tmp_path / "Filme.en.srt"

    def fake_find(video_path, language, credentials):
        downloaded_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        return downloaded_path, SubtitleInfo(provider="opensubtitles", match_type="hash")

    mocker.patch("subs_down_n_sync.core.find_and_download_subtitle", side_effect=fake_find)
    mocker.patch(
        "subs_down_n_sync.core.sync_subtitle_if_needed",
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
    mocker.patch("subs_down_n_sync.core.shutil.which", return_value="/usr/bin/ffmpeg")

    video = tmp_path / "Filme.mkv"
    video.write_bytes(b"\x00" * 10)

    fake_summary = RunSummary(
        output_path=tmp_path / "Filme.en.srt",
        provider="opensubtitles",
        match_type="hash",
        synced=False,
        offset_seconds=0.0,
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
