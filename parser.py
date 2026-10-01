"""
parser.py — turns raw user text into structured data the formatter needs.

Movie input example
───────────────────
Drawing.Closer.2024.1080p.NF.WEB-DL.DDP5.1.AV1-LioN.mkv [2.35 GB]
https://gdflix.dev/file/p9b39ueRRTy74G8

Drawing.Closer.2024.1080p.NF.WEB-DL.DDP5.1.H.265-LioN.mkv [2.08 GB]
https://gdflix.dev/file/z3P3Ut5HdgVGGCs

Series input example
────────────────────
The.Following.S01.1080p.NF.WEB-DL.DDP5.1.SDR.AV1-LioN [10.2 GB]
https://gdflix.dev/pack/GDwOvx0ui6
The.Following.S02.1080p.NF.WEB-DL.DDP5.1.H.265-LioN [9.8 GB]
https://gdflix.dev/pack/gi0kygn58B
The.Following.S03.1080p.NF.WEB-DL.DDP5.1.H.265-LioN
https://gdflix.dev/pack/ilW1ukzKPk

(Size is optional per season)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─── Movie ──────────────────────────────────────────────────────
@dataclass
class MovieEntry:
    filename: str
    size: str          # e.g. "2.35 GB"
    link: str


@dataclass
class MovieParsed:
    entries: list[MovieEntry] = field(default_factory=list)
    platform_tag: str = ""          # e.g. "NF", "AMZN"
    group_name: str = ""            # e.g. "LioNriPs"
    raw_first_filename: str = ""    # kept so TMDB search can use it


# ─── Series ─────────────────────────────────────────────────────
@dataclass
class SeriesParsed:
    base_name: str = ""             # e.g. "The.Handmaid's.Tale.2018.1080p.AMZN.WEB-DL..."
    links: list[str] = field(default_factory=list)
    platform_tag: str = ""
    group_name: str = ""


# ─── shared regex helpers ───────────────────────────────────────
# platform tag sits right before WEB-DL / WEB-Rip / HDTV …
_PLATFORM_RE = re.compile(
    r"(?:^|[.\s_-])"
    r"(NF|AMZN|HMAX|DIS\+?|DSNP|PMTP|APTS|STAN|PCOK|CRAV|LTVO|HULU|FUBO|PARA)"
    r"(?:[.\s_-])",
    re.IGNORECASE,
)

# group name after the last hyphen, before extension
_GROUP_RE = re.compile(r"-([A-Za-z0-9]+?)(?:\.\w{2,4})?$")


def _extract_platform(text: str) -> str:
    m = _PLATFORM_RE.search(text)
    return m.group(1).upper() if m else ""


def _extract_group(text: str) -> str:
    m = _GROUP_RE.search(text.strip())
    return m.group(1) if m else ""


# ─── movie parser ───────────────────────────────────────────────
def parse_movies(raw: str) -> MovieParsed:
    """
    Expects alternating lines:
        <filename> [<size>]
        <url>
    Blank lines between pairs are fine.
    """
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]

    entries: list[MovieEntry] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # ── is this a filename line? (contains a video extension or [size])
        size_match = re.search(r"\[([^\]]+)\]", line)
        if size_match:
            filename = re.sub(r"\s*\[[^\]]+\]", "", line).strip()
            size = size_match.group(1)

            # next non-blank line should be a link
            link = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                link = lines[i + 1]
                i += 2
            else:
                i += 1

            entries.append(MovieEntry(filename=filename, size=size, link=link))
        else:
            i += 1

    parsed = MovieParsed(entries=entries)
    if entries:
        first = entries[0].filename
        parsed.raw_first_filename = first
        parsed.platform_tag = _extract_platform(first)
        parsed.group_name = _extract_group(first)

    return parsed


# ─── series parser ──────────────────────────────────────────────
def parse_series(raw: str) -> SeriesParsed:
    """
    Simple format: base name on first line, then links (one per season).
    
    Example input:
        The.Handmaid's.Tale.2018.S01.1080p.AMZN.WEB-DL.DDP5.1.SDR.H.265-LioN
        https://gdflix.dev/pack/hjCyCqNn25
        https://gdflix.dev/pack/abc123xyz
        https://gdflix.dev/pack/def456uvw
    
    Bot will auto-generate S01, S02, S03... labels for each link.
    """
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if not lines:
        return SeriesParsed()

    base_name = lines[0]
    links = [l for l in lines[1:] if l.startswith("http")]

    return SeriesParsed(
        base_name=base_name,
        links=links,
        platform_tag=_extract_platform(base_name),
        group_name=_extract_group(base_name),
    )
