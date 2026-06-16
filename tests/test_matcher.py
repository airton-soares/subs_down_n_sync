from unittest.mock import MagicMock

import pytest

from subs_down_n_sync.matcher import SubtitleInfo, filename_similarity, pick_subtitle


def _make_sub(matches: set, filename: str = "", provider: str = "opensubtitles") -> MagicMock:
    sub = MagicMock()
    sub.get_matches.return_value = matches
    sub.filename = filename
    sub.provider_name = provider
    return sub


def _make_video(name: str = "Filme.2024.1080p.BluRay.mkv") -> MagicMock:
    video = MagicMock()
    video.name = name
    return video


class TestFilenameSimilarity:
    def test_identical_names(self):
        assert filename_similarity("Filme.mkv", "Filme.mkv") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert filename_similarity("OutroFilme.srt", "Filme.mkv") == pytest.approx(0.0)

    def test_partial_overlap(self):
        sim = filename_similarity("Filme.2024.srt", "Filme.2024.BluRay.mkv")
        assert 0.0 < sim < 1.0

    def test_empty_video_name(self):
        assert filename_similarity("Filme.srt", "") == pytest.approx(0.0)


class TestTier1Hash:
    def test_hash_match_returns_tier1(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=971)
        video = _make_video()
        sub = _make_sub({"hash", "title"})

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 1
        assert info.match_type == "hash"
        assert info.needs_sync is False
        assert "hash" in info.matched_fields

    def test_hash_wins_over_release_plus_metadata(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", side_effect=[200, 971])
        video = _make_video()
        hash_sub = _make_sub({"hash"}, provider="prov_hash")
        release_sub = _make_sub({"release_group", "year"}, provider="prov_release")

        chosen, info = pick_subtitle([hash_sub, release_sub], video)

        assert info.match_tier == 1
        assert chosen is hash_sub


class TestTier2Metadata:
    def test_release_plus_year_is_tier2(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=500)
        video = _make_video()
        sub = _make_sub({"release_group", "year", "title"})

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 2
        assert info.match_type == "release"
        assert info.needs_sync is False
        assert "release_group" in info.matched_fields
        assert "year" in info.matched_fields

    def test_release_plus_season_episode_is_tier2(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=612)
        video = _make_video("Serie.S01E01.1080p.mkv")
        sub = _make_sub({"release_group", "season", "episode"})

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 2
        assert "season" in info.matched_fields

    def test_release_group_alone_is_not_tier2(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=400)
        video = _make_video("Filme.mkv")
        sub = _make_sub({"release_group", "title"}, filename="Filme.mkv")

        _, info = pick_subtitle([sub], video)

        assert info.match_tier != 2


class TestTier3Filename:
    def test_high_similarity_no_sync(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=200)
        video = _make_video("Raising.Hope.S01E01.720p.HDTV.X264.mkv")
        sub = _make_sub({"title"}, filename="Raising.Hope.S01E01.720p.HDTV.X264.pt-BR.srt")

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 3
        assert info.needs_sync is False

    def test_low_similarity_needs_sync(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=100)
        video = _make_video("Filme.2024.1080p.BluRay.mkv")
        sub = _make_sub({"title"}, filename="OutroFilme.srt")

        _, info = pick_subtitle([sub], video)

        assert info.needs_sync is True

    def test_release_only_candidates_go_to_tier3(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=400)
        video = _make_video("Filme.mkv")
        sub = _make_sub({"release_group"}, filename="Filme.mkv")

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 3
        assert info.match_type == "release"


class TestTier4Audio:
    def test_empty_filename_very_low_score_is_tier4(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=50)
        video = _make_video("FilmeRaro.Titulo.Diferente.mkv")
        sub = _make_sub(set(), filename="")

        _, info = pick_subtitle([sub], video)

        assert info.match_tier == 4
        assert info.match_type == "audio"
        assert info.needs_sync is True

    def test_subtitleinfo_fields_populated(self, mocker):
        mocker.patch("subs_down_n_sync.matcher.compute_score", return_value=971)
        video = _make_video()
        sub = _make_sub({"hash"})

        _, info = pick_subtitle([sub], video)

        assert isinstance(info, SubtitleInfo)
        assert isinstance(info.matched_fields, list)
        assert isinstance(info.match_tier, int)
