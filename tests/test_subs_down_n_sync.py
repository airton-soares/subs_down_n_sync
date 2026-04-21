import shutil as shutil_
from pathlib import Path

import pytest
from babelfish import Language
from exceptions import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleNotFoundError,
    SubtitleSyncError,
)
from subs_down_n_sync import (
    SubtitleInfo,
    SyncResult,
    _mean_offset_seconds,
    _parse_srt_timestamps,
    check_ffmpeg,
    find_and_download_subtitle,
    load_credentials,
    main,
    parse_language,
    sync_subtitle_if_needed,
    validate_video_path,
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
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
    check_ffmpeg()  # não deve levantar


def test_check_ffmpeg_raises_when_binary_missing(mocker):
    mocker.patch("shutil.which", return_value=None)
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
def stub_subliminal(mocker, tmp_path):
    """Stuba scan_video/download_best_subtitles/save_subtitles.

    Retorna o mock do subtitle para os testes configurarem `.matches` / `.provider_name`.
    O fake `save_subtitles` grava um arquivo no `directory` usando o caminho retornado
    por `subtitle.get_path`, espelhando o comportamento real do subliminal.
    """
    fake_video = mocker.MagicMock(name="Video")
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.get_path.return_value = "Filme.pt-BR.srt"

    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )

    def fake_save(video, subs, directory=None):
        out = Path(directory) / Path(subs[0].get_path(video)).name
        out.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return [subs[0]]

    mocker.patch("subs_down_n_sync.subliminal.save_subtitles", side_effect=fake_save)
    return fake_sub


def test_find_and_download_subtitle_returns_path_and_info(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.2024.1080p.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.matches = {"hash", "release_group"}
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
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: []},
    )

    with pytest.raises(SubtitleNotFoundError, match="eng"):
        find_and_download_subtitle(
            video_path, language=Language("eng"), credentials=("u", "p")
        )


def test_match_type_is_release_when_no_hash(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.matches = {"release_group", "resolution"}

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.match_type == "release"


def test_match_type_is_fallback_when_only_title_match(tmp_path, stub_subliminal):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    stub_subliminal.matches = {"title"}

    _, info = find_and_download_subtitle(
        video_path,
        language=Language("por", country="BR"),
        credentials=("u", "p"),
    )
    assert info.match_type == "fallback"


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
        "1\n00:00:03,000 --> 00:00:04,000\nlinha 1\n\n"
        "2\n00:00:07,000 --> 00:00:08,000\nlinha 2\n"
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
