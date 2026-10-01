"""
formatter.py — pure functions that turn parsed structs into the exact
               text that will be posted to the Telegram channel.

No side-effects, no I/O — easy to unit-test.
"""

from __future__ import annotations

import re
from parser import MovieParsed, SeriesParsed


# ── watermark resolver ──────────────────────────────────────────
_GROUP_FILMS = "LioNriPs"
_GROUP_ANIME = "PiRaTe_RiPs"

def _resolve_watermark(anime: bool) -> str:
    return _GROUP_ANIME if anime else _GROUP_FILMS


# ─── Movie formatter ────────────────────────────────────────────
def format_movie_post(parsed: MovieParsed, audios: str, anime: bool = False, title: str = "", year: str = "", image_url: str = "") -> str:
    """
    Output example
    ──────────────
    🦁 <b>Drawing Closer</b> <b>(2024)</b>

    <b>1. 📁 Drawing.Closer.2024.1080p.NF.WEB-DL.DDP5.1.AV1-LioN.mkv</b>
       <b>📏 Size:</b> <code>2.35 GB</code>
       <b>🔗</b> https://gdflix.dev/file/p9b39ueRRTy74G8

    …

    <blockquote><b>🔊 : Jap, Eng</b></blockquote>

    <tg-spoiler>@LioNriPs</tg-spoiler>
    """
    # ── header line with embedded image preview ─
    if image_url:
        # Embed image URL as invisible hyperlink - Telegram shows preview
        lion_with_preview = f'<a href="{image_url}">🦁</a>'
    else:
        lion_with_preview = "🦁"
    
    if title and year:
        header = f"{lion_with_preview} <b>{title}</b> <b>({year})</b>"
    elif title:
        header = f"{lion_with_preview} <b>{title}</b>"
    else:
        # Fallback to old format if no title provided
        tags: list[str] = []
        if parsed.platform_tag:
            tags.append(f"#{parsed.platform_tag}")
        tags.append("#WEBDL")
        tags.append("#EXCLUSIVE")
        header = lion_with_preview + " " + " ".join(tags)

    # ── numbered entries ────────────────────────
    blocks: list[str] = []
    for idx, entry in enumerate(parsed.entries, 1):
        block = (
            f"<b>• {entry.filename}</b>\n" 
            f"   <b>× Size:</b> [<code>{entry.size}</code>]\n"
            f"   <b> {entry.link}</b>"
        )
        blocks.append(block)

    # ── audio line (blockquote) ─────────────────
    audio_line = f"<blockquote><b>🔊 : {audios}</b></blockquote>" if audios else ""

    # ── watermark with spoiler ──────────────────
    watermark_line = f"<tg-spoiler>@{_resolve_watermark(anime)}</tg-spoiler>"

    # ── assemble ────────────────────────────────
    parts = [header, "", "\n\n".join(blocks)]
    if audio_line:
        parts.append("")
        parts.append(audio_line)
    parts.append("")
    parts.append(watermark_line)

    return "\n".join(parts)


# ─── Series formatter ───────────────────────────────────────────
def format_series_post(parsed: SeriesParsed, audios: str = "", anime: bool = False, title: str = "", year: str = "", image_url: str = "") -> str:
    """
    Auto-generates season filenames from base_name
    ──────────────────────────────────────────────
    🦁 <b>The Handmaid's Tale</b> <b>(2017)</b>

    <b>1. 🏷️ The.Handmaid's.Tale.2018.S01.1080p.AMZN.WEB-DL.DDP5.1.SDR.H.265-LioN</b>
       <b>📥</b> https://gdflix.dev/pack/hjCyCqNn25

    <b>2. 🏷️ The.Handmaid's.Tale.2018.S02.1080p.AMZN.WEB-DL.DDP5.1.SDR.H.265-LioN</b>
       <b>📥</b> https://gdflix.dev/pack/abc123xyz

    <blockquote><b>🔊 : Eng</b></blockquote>

    <tg-spoiler>@LioNriPs</tg-spoiler>
    """
    # ── header line with embedded image preview ─
    if image_url:
        # Embed image URL as invisible hyperlink - Telegram shows preview
        lion_with_preview = f'<a href="{image_url}">🦁</a>'
    else:
        lion_with_preview = "🦁"
    
    if title and year:
        header = f"{lion_with_preview} <b>{title}</b> <b>({year})</b>"
    elif title:
        header = f"{lion_with_preview} <b>{title}</b>"
    else:
        # Fallback to old format if no title provided
        tags: list[str] = []
        if parsed.platform_tag:
            tags.append(f"#{parsed.platform_tag}")
        tags.append("#WEBDL")
        tags.append("#UNTOUCHED")
        header = lion_with_preview + " " + " ".join(tags)

    # ── auto-generate season filenames ──────────
    blocks: list[str] = []
    single_season = len(parsed.links) == 1
    
    # Clean base_name: strip existing S01/S02 pattern if present
    base_clean = re.sub(r"[.\s_-]?S\d{2}[.\s_-]?", ".", parsed.base_name, flags=re.IGNORECASE).strip(".")
    
    for idx, link in enumerate(parsed.links, 1):
        # Insert S01, S02, ... before the quality/codec info
        # Find insertion point: before resolution (1080p, 720p, 2160p etc)
        match = re.search(r"(\d{3,4}p)", base_clean, re.IGNORECASE)
        if match:
            insert_pos = match.start()
            season_filename = base_clean[:insert_pos] + f"S{idx:02d}." + base_clean[insert_pos:]
        else:
            # Fallback: just append season at the end before extension
            season_filename = f"{base_clean}.S{idx:02d}"
        
        # No number prefix if single season
        prefix = "" if single_season else f"{idx}. "
        
        block = (
            f"<b>{season_filename}</b>\n" #add {prefix} instead of {idx} for num count on series
            f"   <b> {link}</b>"
        )
        blocks.append(block)

    # ── audio line (blockquote) ─────────────────
    audio_line = f"<blockquote><b>🔊 : {audios}</b></blockquote>" if audios else ""

    # ── watermark with spoiler ──────────────────
    watermark_line = f"<tg-spoiler>@{_resolve_watermark(anime)}</tg-spoiler>"

    # ── assemble ────────────────────────────────
    parts = [header, "", "\n\n".join(blocks)]
    if audio_line:
        parts.append("")
        parts.append(audio_line)
    parts.append("")
    parts.append(watermark_line)

    return "\n".join(parts)
