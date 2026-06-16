from __future__ import annotations

import re
from pathlib import Path

import charset_normalizer

_TS_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE,
)

_SRT_BLOCK_RE = re.compile(
    r"(\d+)\n"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\n"
    r"((?:.+\n?)+)",
    re.MULTILINE,
)


def _ts(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _seconds_to_ts(total: float) -> str:
    total = max(0.0, total)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = int(total % 60)
    ms = round((total - int(total)) * 1000)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _srt_to_segments(srt_text: str) -> list[dict]:
    segments = []
    for match in _SRT_BLOCK_RE.finditer(srt_text):
        segments.append(
            {
                "start": _ts(match.group(2), match.group(3), match.group(4), match.group(5)),
                "end": _ts(match.group(6), match.group(7), match.group(8), match.group(9)),
                "text": match.group(10).strip(),
            }
        )
    return segments


def _cues_to_srt(cues: list[dict]) -> str:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(
            f"{i}\n{_seconds_to_ts(cue['start'])} --> {_seconds_to_ts(cue['end'])}\n{cue['text']}\n"
        )
    return "\n".join(lines)


def _parse_srt_timestamps(srt_text: str) -> list[float]:
    out: list[float] = []
    for h, m, s, ms in _TS_RE.findall(srt_text):
        out.append(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000)
    return out


def _mean_offset_seconds(orig: list[float], synced: list[float]) -> float:
    n = min(len(orig), len(synced))
    if n == 0:
        return 0.0
    total = sum(abs(synced[i] - orig[i]) for i in range(n))
    return total / n


def _read_text_detected(path: Path) -> str:
    raw = path.read_bytes()
    result = charset_normalizer.from_bytes(raw).best()
    encoding = str(result.encoding) if result else "utf-8"
    return raw.decode(encoding, errors="replace")
