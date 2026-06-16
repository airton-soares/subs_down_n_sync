from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from subliminal.score import compute_score

SCORE_THRESHOLD = 0.9
_TIER4_THRESHOLD = 0.3
_METADATA_FIELDS = frozenset({"year", "season", "episode", "imdb_id"})


@dataclass(frozen=True)
class SubtitleInfo:
    provider: str
    match_type: str  # "hash" | "release" | "fallback" | "audio" | "existing"
    needs_sync: bool
    match_tier: int  # 1 | 2 | 3 | 4
    matched_fields: list[str] = field(default_factory=list)


def _compute_needs_sync(match_type: str, similarity: float) -> bool:
    """Decide se legenda precisa de sincronização.

    Hash e release matches são confiáveis → sem sync.
    Fallback e existing dependem da similaridade → sync se < threshold.
    """
    if match_type in ("hash", "release"):
        return False
    return similarity < SCORE_THRESHOLD


def _filename_similarity(sub_filename: str, video_name: str) -> float:
    norm = re.compile(r"[\W_]+")
    video_stem = Path(video_name).stem
    sub_tokens = set(norm.sub(" ", sub_filename.lower()).split())
    video_tokens = set(norm.sub(" ", video_stem.lower()).split())
    if not video_tokens:
        return 0.0
    return len(sub_tokens & video_tokens) / len(video_tokens)


def pick_subtitle(
    candidates: list,
    video: object,
) -> tuple[object, SubtitleInfo]:
    video_name = getattr(video, "name", "") or ""

    scored = [(sub, compute_score(sub, video)) for sub in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Tier 1: hash match
    for sub, _ in scored:
        if "hash" in set(sub.get_matches(video)):
            return sub, SubtitleInfo(
                provider=sub.provider_name,
                match_type="hash",
                needs_sync=False,
                match_tier=1,
                matched_fields=["hash"],
            )

    # Tier 2: release_group + pelo menos um campo de metadata
    for sub, _ in scored:
        matches = set(sub.get_matches(video))
        if "release_group" in matches:
            extra = sorted(matches & _METADATA_FIELDS)
            if extra:
                return sub, SubtitleInfo(
                    provider=sub.provider_name,
                    match_type="release",
                    needs_sync=False,
                    match_tier=2,
                    matched_fields=["release_group"] + extra,
                )

    # Tier 3: melhor filename similarity (release_group candidates primeiro)
    pool_with_sim = [
        (sub, score, _filename_similarity(getattr(sub, "filename", "") or "", video_name))
        for sub, score in scored
    ]

    release_pool = [
        (s, sc, sim) for s, sc, sim in pool_with_sim if "release_group" in set(s.get_matches(video))
    ]
    chosen_pool = release_pool if release_pool else pool_with_sim
    match_type = "release" if release_pool else "fallback"

    if chosen_pool:
        best_sub, _, best_sim = max(chosen_pool, key=lambda x: x[2])

        if best_sim >= _TIER4_THRESHOLD:
            return best_sub, SubtitleInfo(
                provider=best_sub.provider_name,
                match_type=match_type,
                needs_sync=best_sim < SCORE_THRESHOLD,
                match_tier=3,
                matched_fields=[f"filename_similarity={best_sim:.2f}"],
            )

    # Tier 4: melhor candidato por score subliminal, confiança muito baixa
    best_sub, _ = scored[0]
    return best_sub, SubtitleInfo(
        provider=best_sub.provider_name,
        match_type="audio",
        needs_sync=True,
        match_tier=4,
        matched_fields=[],
    )
