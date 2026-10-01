from __future__ import annotations

import io
import logging
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config       import ADMINS, BOT_TOKEN, CHANNEL_FILMS, CHANNEL_ANIME, DEFAULT_CHNL_FILMS, DEFAULT_CHNL_ANIMES
from parser       import parse_movies, parse_series
from formatter    import format_movie_post, format_series_post
from tmdb_client  import search, fetch_poster, Candidate, is_anime, get_image_url
import db as database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── stage constants ─────────────────────────────────────────────
STAGE_WAIT_CONTENTS = "wait_contents"
STAGE_WAIT_AUDIOS   = "wait_audios"
STAGE_PREVIEW       = "preview"

# ── per-user state ──────────────────────────────────────────────
# {
#   user_id: {
#     "stage":       str,                  # current stage
#     "candidate":   Candidate,            # the chosen TMDB result
#     "poster_bytes": bytes | None,        # downloaded poster (cached)
#     "parsed":      MovieParsed | SeriesParsed | None,
#     "audios":      str,
#     "formatted":   str,
#     "raw_contents": str,                 # original pasted text (for go-back)
#   }
# }
_state: dict[int, dict[str, Any]] = {}

# ── keyboard factories ──────────────────────────────────────────
_PREVIEW_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Post to Channel", callback_data="post")],
    [InlineKeyboardButton("🔙 Go Back",        callback_data="goback")],
    [InlineKeyboardButton("❌ Cancel",         callback_data="cancel")],
])


# ════════════════════════════════════════════════════════════════
# /tmdb <title>
# ════════════════════════════════════════════════════════════════
async def cmd_tmdb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS:
        await update.effective_message.reply_text("❌ Not authorized.")
        return
    raw = (update.effective_message.text or "").split(None, 1)
    if len(raw) < 2:
        await update.effective_message.reply_text("Usage:\n/tmdb <title>")
        return

    query = raw[1].strip()
    candidates = await search(query)

    if not candidates:
        await update.effective_message.reply_text(
            f'😕 No TMDB results for "<b>{query}</b>".\nTry a different title.',
            parse_mode="HTML",
        )
        return

    # ── build one button per result ─────────────
    buttons: list[list[InlineKeyboardButton]] = []
    for i, c in enumerate(candidates):
        icon  = "🎬" if c.media_type == "movie" else "📺"
        label = f"{icon} {c.title} ({c.year})" if c.year else f"{icon} {c.title}"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"pick:{i}")
        ])

    # stash candidate list so the callback can look it up
    _state[update.effective_user.id] = {
        "stage":          None,              # not in a flow yet
        "_candidates":    candidates,        # temporary, removed after pick
    }

    await update.effective_message.reply_text(
        "🔍 Select the correct title:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ════════════════════════════════════════════════════════════════
# Callback: user picks a TMDB result
# ════════════════════════════════════════════════════════════════
async def cb_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid   = update.effective_user.id
    state = _state.get(uid, {})
    idx   = int(update.callback_query.data.split(":")[1])

    candidates: list[Candidate] = state.get("_candidates", [])
    if idx >= len(candidates):
        await update.callback_query.answer("⚠️ Invalid selection.")
        return

    chosen: Candidate = candidates[idx]
    await update.callback_query.answer(f"Selected: {chosen.title}")

    # ── download poster now (cache it) ──────────
    poster_bytes = await fetch_poster(chosen)

    # ── detect anime once here, carry through the whole flow ────
    anime_flag = is_anime(chosen)

    # ── transition → WAIT_CONTENTS ──────────────
    _state[uid] = {
        "stage":        STAGE_WAIT_CONTENTS,
        "candidate":    chosen,
        "poster_bytes": poster_bytes,
        "anime":        anime_flag,          # True → anime channel + @PiRaTe_RiPs
        "parsed":       None,
        "audios":       "",
        "formatted":    "",
        "raw_contents": "",
    }

    kind_label = "🎬 Movie" if chosen.media_type == "movie" else "📺 Series"
    chan_label = "🎌 Anime Channel" if anime_flag else "🎥 Films Channel"
    await update.callback_query.edit_message_text(
        f"{kind_label} <code>{chosen.title}</code> ({chosen.year}) selected!\n"
        f"📍 Will post to: {chan_label}\n\n"
        "📋 Share your contents (paste the raw text):",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════
# Plain-text handler — routes to the correct stage
# ════════════════════════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid   = update.effective_user.id
    state = _state.get(uid)
    if state is None or state.get("stage") is None:
        return                              # not in any flow

    stage = state["stage"]
    text  = (update.effective_message.text or "").strip()

    if stage == STAGE_WAIT_CONTENTS:
        await _handle_contents(update, uid, state, text)
    elif stage == STAGE_WAIT_AUDIOS:
        await _handle_audios(update, uid, state, text)


# ─── contents received ──────────────────────────────────────────
async def _handle_contents(update: Update, uid: int, state: dict, text: str) -> None:
    candidate: Candidate = state["candidate"]
    state["raw_contents"] = text          # save for go-back

    # ── parse according to the type TMDB told us ────
    if candidate.media_type == "movie":
        parsed = parse_movies(text)
        if not parsed.entries:
            await update.effective_message.reply_text(
                "⚠️ Couldn't parse movie entries. Paste again in the correct format.",
            )
            return
    else:
        parsed = parse_series(text)
        if not parsed.links:
            await update.effective_message.reply_text(
                "⚠️ Couldn't parse series links. Make sure you have the base name on the first line, then links below.",
            )
            return

    state["parsed"] = parsed
    state["stage"]  = STAGE_WAIT_AUDIOS

    # ── keyboard with Skip & Post button ────────
    skip_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Skip & Post", callback_data="skip_audio")],
    ])

    await update.effective_message.reply_text(
        "🔊 Enter the audio languages (e.g. <b>Eng, Jap, Hin</b>):\n"
        "<i>Or press the button below to skip.</i>",
        parse_mode="HTML",
        reply_markup=skip_kb,
    )


# ─── audios received → build preview ────────────────────────────
async def _handle_audios(update: Update, uid: int, state: dict, text: str) -> None:
    audios   = "" if text.lower() == "skip" else text
    state["audios"] = audios

    candidate: Candidate = state["candidate"]
    parsed = state["parsed"]
    anime  = state["anime"]

    # ── get image URL for webpage preview ───────
    image_url = get_image_url(candidate)

    # ── format with TMDB title + year + image ───
    if candidate.media_type == "movie":
        formatted = format_movie_post(parsed, audios, anime=anime, title=candidate.title, year=candidate.year, image_url=image_url)
    else:
        formatted = format_series_post(parsed, audios, anime=anime, title=candidate.title, year=candidate.year, image_url=image_url)

    state["formatted"] = formatted
    state["stage"]     = STAGE_PREVIEW

    # ── show preview ────────────────────────────
    await _send_preview(update, state)


# ─── preview sender (shared by audio-handler & go-back) ─────────
async def _send_preview(update: Update, state: dict) -> None:
    poster_bytes: bytes | None = state.get("poster_bytes")
    candidate: Candidate       = state["candidate"]
    formatted: str             = state["formatted"]
    anime: bool                = state["anime"]

    chan_label = "🎌 Anime Channel" if anime else "🎥 Films Channel"
    header = (
        f"🔍 <b>{candidate.title}</b> ({candidate.year})\n"
        f"📍 Target: {chan_label}\n"
        "──── Preview ────\n"
    )

    # ── send text with embedded preview (no separate photo) ──
    await update.effective_message.reply_text(
        header + formatted,
        parse_mode="HTML",
        reply_markup=_PREVIEW_KB,
        disable_web_page_preview=False,  # Enable preview for embedded image
    )


# ════════════════════════════════════════════════════════════════
# Audio skip button callback
# ════════════════════════════════════════════════════════════════
async def cb_skip_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """⏭️ Skip audio and go directly to preview."""
    uid   = update.effective_user.id
    state = _state.get(uid)
    if state is None or state.get("stage") != STAGE_WAIT_AUDIOS:
        await update.callback_query.answer("Session expired or invalid state.")
        return

    await update.callback_query.answer("Skipping audio...")

    # Build preview with empty audios
    state["audios"] = ""
    
    candidate: Candidate = state["candidate"]
    parsed = state["parsed"]
    anime  = state["anime"]

    # ── get image URL for webpage preview ───────
    image_url = get_image_url(candidate)

    # ── format with TMDB title + year + image ───
    if candidate.media_type == "movie":
        formatted = format_movie_post(parsed, "", anime=anime, title=candidate.title, year=candidate.year, image_url=image_url)
    else:
        formatted = format_series_post(parsed, "", anime=anime, title=candidate.title, year=candidate.year, image_url=image_url)

    state["formatted"] = formatted
    state["stage"]     = STAGE_PREVIEW

    # ── show preview ────────────────────────────
    chan_label = "🎌 Anime Channel" if anime else "🎥 Films Channel"
    header = (
        f"🔍 <b>{candidate.title}</b> ({candidate.year})\n"
        f"📍 Target: {chan_label}\n"
        "──── Preview ────\n"
    )

    # Edit the audio prompt message to show preview
    await update.callback_query.edit_message_text(
        header + formatted,
        parse_mode="HTML",
        reply_markup=_PREVIEW_KB,
    )


# ════════════════════════════════════════════════════════════════
# Preview buttons: Post / Go Back / Cancel
# ════════════════════════════════════════════════════════════════
async def cb_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """✅ Post to Channel."""
    uid   = update.effective_user.id
    state = _state.get(uid)
    if state is None:
        await update.callback_query.answer("Session expired. Start again.")
        return

    await update.callback_query.answer("Posting…")

    candidate: Candidate = state["candidate"]
    formatted: str       = state["formatted"]
    poster_bytes         = state.get("poster_bytes")
    anime: bool          = state["anime"]

    # ── pick the right channel ──────────────────
    raw_ch = CHANNEL_ANIME if anime else CHANNEL_FILMS
    try:
        ch_id: int | str = int(raw_ch)
    except ValueError:
        ch_id = raw_ch

    # ── send to channel (text with embedded image preview) ──
    sent_text_msg = await ctx.bot.send_message(
        chat_id=ch_id, 
        text=formatted, 
        parse_mode="HTML",
        disable_web_page_preview=False,  # Enable preview for embedded image URL
    )

    # ── copy to backup channel (no forward tag) ─
    if sent_text_msg:
        backup_ch_raw = DEFAULT_CHNL_ANIMES if anime else DEFAULT_CHNL_FILMS
        try:
            backup_ch_id: int | str = int(backup_ch_raw)
        except ValueError:
            backup_ch_id = backup_ch_raw
        
        try:
            # Copy text message with preview
            await ctx.bot.copy_message(
                chat_id=backup_ch_id,
                from_chat_id=ch_id,
                message_id=sent_text_msg.message_id,
            )
        except Exception as e:
            logger.warning(f"Failed to copy to backup channel: {e}")

    # ── persist to MongoDB ──────────────────────
    parsed = state["parsed"]
    try:
        await database.save_post(
            title         = candidate.title,
            post_type     = candidate.media_type,
            text          = formatted,
            platform_tag  = parsed.platform_tag,
            group_name    = parsed.group_name,
            audios        = state["audios"],
            tmdb_title    = candidate.title,
            tmdb_year     = candidate.year,
            channel_msg_id= sent_text_msg.message_id if sent_text_msg else None,
            anime         = anime,
        )
    except Exception as e:
        logger.error("MongoDB save failed: %s", e)

    # ── done ────────────────────────────────────
    del _state[uid]
    chan_label = "🎌 Anime Channel" if anime else "🎥 Films Channel"
    await update.callback_query.edit_message_text(f"✅ Posted to {chan_label} & saved to DB!")


# ─── 🔙 Go Back ─────────────────────────────────────────────────
async def cb_goback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Go back to "Share your contents" stage.
    Clears parsed / audios / formatted so the user can re-paste.
    """
    uid   = update.effective_user.id
    state = _state.get(uid)
    if state is None:
        await update.callback_query.answer("Session expired.")
        return

    await update.callback_query.answer("Going back…")

    # reset to contents stage
    state["stage"]     = STAGE_WAIT_CONTENTS
    state["parsed"]    = None
    state["audios"]    = ""
    state["formatted"] = ""
    # raw_contents kept — user can just re-paste or edit

    candidate: Candidate = state["candidate"]
    kind_label = "🎬 Movie" if candidate.media_type == "movie" else "📺 Series"
    chan_label = "🎌 Anime Channel" if state["anime"] else "🎥 Films Channel"

    await update.callback_query.edit_message_text(
        f"{kind_label} <b>{candidate.title}</b> ({candidate.year})\n"
        f"📍 Will post to: {chan_label}\n\n"
        "📋 Share your contents (paste the raw text):",
        parse_mode="HTML",
    )


# ─── ❌ Cancel ───────────────────────────────────────────────────
async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    _state.pop(uid, None)
    await update.callback_query.answer("Cancelled.")
    await update.callback_query.edit_message_text("❌ Post cancelled.")


# ════════════════════════════════════════════════════════════════
# /fetch <title>
# ════════════════════════════════════════════════════════════════
async def cmd_fetch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS:
        await update.effective_message.reply_text("❌ Not authorized.")
        return
    raw = (update.effective_message.text or "").split(None, 1)
    if len(raw) < 2:
        await update.effective_message.reply_text("Usage: /fetch <title>")
        return

    query = raw[1].strip()
    try:
        posts = await database.fetch_posts(query)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ DB error: {e}")
        return

    if not posts:
        await update.effective_message.reply_text(f'No posts found for "{query}".')
        return

    # Send each post as a separate message for better readability
    await update.effective_message.reply_text(
        f"🔍 Found <b>{len(posts)}</b> post(s) for \"<b>{query}</b>\":",
        parse_mode="HTML"
    )
    
    for i, p in enumerate(posts, 1):
        posted = p.get("posted_at", "—")
        post_type = p.get("type", "unknown")
        title = p.get("tmdb_title") or p.get("title", "Untitled")
        full_text = p.get("text", "")
        
        header = (
            f"<b>#{i} — {title}</b> ({post_type})\n"
            f"📅 Posted: {posted}\n"
            "─────────────────\n"
        )
        
        # Send full post content with disable_web_page_preview to show embedded images
        await update.effective_message.reply_text(
            header + full_text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )


# ════════════════════════════════════════════════════════════════
# App bootstrap
# ════════════════════════════════════════════════════════════════
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("tmdb",  cmd_tmdb))
    app.add_handler(CommandHandler("fetch", cmd_fetch))

    # inline-button callbacks
    app.add_handler(CallbackQueryHandler(cb_pick,       pattern=r"^pick:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_skip_audio, pattern="^skip_audio$"))
    app.add_handler(CallbackQueryHandler(cb_post,       pattern="^post$"))
    app.add_handler(CallbackQueryHandler(cb_goback,     pattern="^goback$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,     pattern="^cancel$"))

    # plain-text (contents / audios) — only active when user is mid-flow
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


if __name__ == "__main__":
    build_app().run_polling()
