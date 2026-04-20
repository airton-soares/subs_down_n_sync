from pathlib import Path

import pytest
from babelfish import Language
from subs_down_n_sync import (
    InvalidLanguageError,
    InvalidVideoError,
    MissingCredentialsError,
    MissingDependencyError,
    SubtitleInfo,
    SubtitleNotFoundError,
    check_ffmpeg,
    find_and_download_subtitle,
    load_credentials,
    main,
    parse_language,
    validate_video_path,
)


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


def test_find_and_download_subtitle_returns_path_and_info(tmp_path, mocker):
    video_path = tmp_path / "Filme.2024.1080p.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock(name="Video")
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"hash", "release_group"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )

    def fake_save(video, subs, directory=None):
        out = tmp_path / "Filme.2024.1080p.pt-BR.srt"
        out.write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n")
        return [subs[0]]

    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles", side_effect=fake_save
    )

    srt_path, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )

    assert srt_path.exists()
    assert srt_path.suffix == ".srt"
    assert info.provider == "opensubtitles"
    assert info.match_type == "hash"  # hash tem prioridade


def test_find_and_download_subtitle_raises_when_no_results(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("eng")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: []},
    )

    with pytest.raises(SubtitleNotFoundError, match="eng"):
        find_and_download_subtitle(video_path, language=lang, credentials=("u", "p"))


def test_match_type_is_release_when_no_hash(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"release_group", "resolution"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles",
        side_effect=lambda v, s, directory=None: (
            (tmp_path / "Filme.pt-BR.srt").write_text("x") or [s[0]]
        ),
    )

    _, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )
    assert info.match_type == "release"


def test_match_type_is_fallback_when_only_title_match(tmp_path, mocker):
    video_path = tmp_path / "Filme.mkv"
    video_path.write_bytes(b"\x00" * 10)
    lang = Language("por", country="BR")

    fake_video = mocker.MagicMock()
    mocker.patch("subs_down_n_sync.subliminal.scan_video", return_value=fake_video)

    fake_sub = mocker.MagicMock()
    fake_sub.provider_name = "opensubtitles"
    fake_sub.matches = {"title"}
    mocker.patch(
        "subs_down_n_sync.subliminal.download_best_subtitles",
        return_value={fake_video: [fake_sub]},
    )
    mocker.patch(
        "subs_down_n_sync.subliminal.save_subtitles",
        side_effect=lambda v, s, directory=None: (
            (tmp_path / "Filme.pt-BR.srt").write_text("x") or [s[0]]
        ),
    )

    _, info = find_and_download_subtitle(
        video_path, language=lang, credentials=("u", "p")
    )
    assert info.match_type == "fallback"
