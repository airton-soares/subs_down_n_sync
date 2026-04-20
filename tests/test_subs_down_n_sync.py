from pathlib import Path

import pytest
from subs_down_n_sync import (
    InvalidVideoError,
    MissingDependencyError,
    check_ffmpeg,
    main,
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
