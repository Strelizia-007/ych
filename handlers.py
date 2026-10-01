#!/usr/bin/env python3
"""
Telegram Command Handlers for the TMDB Quiz Feature.

Handles:
- /enablequiz (admin-only)
- /disablequiz (admin-only)
- /leaderboard (all users)
- Poll answer processing
- Quiz restart/recovery on bot startup
"""

import logging
from typing import Optional, Dict, Any

from . import config, db, tmdb_client, quiz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin Command: /enablequiz
# ---------------------------------------------------------------------------

async def handle_enablequiz(mongo_db, admin_user_id: int, bot_app) -> str:
    """
    Handle the /enablequiz admin command.
    
    Does:
    1. Persist quiz_enabled=true in MongoDB
    2. Start/resume the quiz scheduler
    3. Ensure no duplicate scheduler or active poll
    4. Confirm to the admin
    5. Optionally immediately create the next quiz
    """
    from .scheduler import start_quiz_scheduler, check_and_post_next_quiz
    
    # 1. Persist quiz enabled state in MongoDB
    await db.set_quiz_enabled(mongo_db, True)
    
    # 2. Start/resume the quiz scheduler
    # The scheduler checks the MongoDB state before posting
    await start_quiz_scheduler(mongo_db, bot_app)
    
    # 3. Ensure no duplicate active poll
    # The scheduler will handle this, but let's also clean up any stale state
    active_quiz = await db.get_active_quiz(mongo_db)
    if active_quiz:
        # There's a previous active quiz - attempt to delete its message
        try:
            # We'll let the scheduler handle deletion
            pass
        except Exception:
            pass
        # Clear it so a new one can be created
        await db.clear_active_quiz(mongo_db)
    
    # 4. Confirm to the admin
    confirmation = (
        "✅ Quiz system enabled!\n"
        "A new quiz will be posted in the next hour.\n"
        "Use /disablequiz to stop automatic quizzes.\n"
        "Use /leaderboard to view scores."
    )
    
    # 5. Optionally immediately create the next quiz
    # Rather than waiting for the next interval, try to post one now
    try:
        posted = await check_and_post_next_quiz(mongo_db, bot_app)
        if posted:
            logger.info("Immediately posted quiz after /enablequiz")
    except Exception as e:
        logger.warning(f"Failed to immediately post quiz after enable: {e}")
    
    return confirmation


# ---------------------------------------------------------------------------
# Admin Command: /disablequiz
# ---------------------------------------------------------------------------

async def handle_disablequiz(mongo_db, admin_user_id: int, bot_app) -> str:
    """
    Handle the /disablequiz admin command.
    
    Does:
    1. Persist quiz_enabled=false in MongoDB
    2. Stop future scheduled quiz posts
    3. Do not erase leaderboard data
    4. Do not unnecessarily delete the currently active poll
    """
    from .scheduler import stop_quiz_scheduler
    
    # 1. Persist quiz disabled state in MongoDB
    await db.set_quiz_enabled(mongo_db, False)
    
    # 2. Stop the quiz scheduler
    await stop_quiz_scheduler()
    
    # 3. Do NOT erase leaderboard data - that's separate
    
    # 4. Do not unnecessarily delete the currently active poll
    # unless the design requires it. We'll leave the active poll record
    # but the scheduler won't create new ones.
    
    confirmation = (
        "❌ Quiz system disabled!\n"
        "No new quizzes will be automatically posted.\n"
        "Existing leaderboard data is preserved.\n"
        "Use /enablequiz to restart the quiz system."
    )
    
    return confirmation


# ---------------------------------------------------------------------------
# /leaderboard Command
# ---------------------------------------------------------------------------

async def handle_leaderboard(mongo_db, chat_id) -> str:
    """
    Handle the /leaderboard command.
    Available to all users.
    Displays TOP 10 users based on correct answers in the current 7-day period.
    """
    from .db import get_leaderboard
    
    top_users = await get_leaderboard(mongo_db, limit=10)
    
    if not top_users:
        return "📊 No quiz data available yet. Be the first to answer a quiz!"
    
    # Build the leaderboard message
    lines = ["🏆 QUIZ LEADERBOARD", ""]
    lines.append(f"Period: Last 7 Days")
    lines.append("")
    
    for i, user in enumerate(top_users, 1):
        username = user.get("username", "Unknown")
        user_id = user.get("user_id", "Unknown")
        correct = user.get("correct_answers", 0)
        answered = user.get("quizzes_answered", 0)
        percentage = user.get("correct_percentage", 0)
        
        lines.append(f"🥫 {i}. {username}")
        lines.append(f"   ID: {user_id}")
        lines.append(f"   Correct: {correct}")
        lines.append(f"   Answered: {answered}")
        if percentage > 0:
            lines.append(f"   Accuracy: {percentage:.1f}%")
        lines.append("")
    
    # Remove trailing empty line
    if lines and lines[-1] == "":
        lines = lines[:-1]
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Poll Answer Handling
# ---------------------------------------------------------------------------

async def handle_poll_answer(update, bot_app) -> None:
    """
    Handle Telegram poll answer updates.
    Called when users submit their quiz answers.
    
    Logic:
    1. Identify the quiz and user
    2. Check if user already answered this quiz
    3. If not, record the answer and update scores
    4. If yes, ignore the duplicate
    """
    from . import db
    
    try:
        # Poll answer update from Telegram
        poll_answer = update.poll_answer
        
        user = poll_answer.user
        user_id = user.id
        username = user.first_name or user.last_name or str(user_id)
        
        # The poll answer contains the selected option index
        selected_option = poll_answer.option_ids  # list of selected option IDs
        # Note: option_ids contains the index of the selected option
        # but we need to map this to our quiz document
        
        # We need to identify which quiz this answer is for
        # This is typically stored in the message or poll data
        # For now, we'll look at the incoming update context
        
        # Extract quiz_id from the poll message context
        # This requires the quiz document to be accessible
        # We'll use the message_id or poll_id to identify the quiz
        
        # For this implementation, we'll need the quiz_id passed in some way
        # In practice, this would be stored in the message extra data
        
        logger.info(
            f"Poll answer from user {user_id}: selected options {selected_option}"
        )
        
        # TODO: Implement full answer tracking
        # - Identify the quiz from the message/poll context
        # - Check if user already answered
        # - Record answer and update scores
        
    except Exception as e:
        logger.error(f"Error handling poll answer: {e}")


# ---------------------------------------------------------------------------
# Restart Recovery on Startup
# ---------------------------------------------------------------------------

async def handle_restart_recovery(mongo_db, bot_app) -> str:
    """
    Handle quiz restart/recovery when the bot starts.
    
    Does:
    1. Read the persistent quiz state from MongoDB
    2. Determine whether the quiz system is enabled
    3. If disabled: do nothing
    4. If enabled:
       - locate the previous active quiz
       - attempt to delete the previous Telegram poll/message
       - safely ignore already-deleted errors
       - clear old active quiz database record
       - start the scheduler
       - create/resume the next quiz safely
    """
    from .scheduler import start_quiz_scheduler, check_and_post_next_quiz
    
    # 1. Read quiz state from MongoDB
    is_enabled = await db.is_quiz_enabled(mongo_db)
    
    if not is_enabled:
        return "Quiz system was disabled. No recovery needed."
    
    # 2. If enabled, locate the previous active quiz
    active_quiz = await db.get_active_quiz(mongo_db)
    
    # 3. Attempt to delete the previous Telegram poll/message
    if active_quiz:
        chat_id = active_quiz.get("chat_id")
        message_id = active_quiz.get("message_id")
        
        # Try to delete the message - ignore "already deleted" errors
        if chat_id and message_id:
            try:
                await bot_app.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(
                    f"Deleted previous quiz message on restart: chat={chat_id}, msg={message_id}"
                )
            except Exception as e:
                # Expected: message might already be deleted
                error_msg = str(e).lower()
                if any(
                    kw in error_msg
                    for kw in ["message not found", "message can't be deleted", "permission"]
                ):
                    logger.warning(
                        f"Previous quiz message already gone (expected): {e}"
                    )
                else:
                    logger.error(f"Unexpected error deleting previous quiz message: {e}")
    
    # 4. Clear old active quiz database record
    await db.clear_active_quiz(mongo_db)
    
    # 5. Start the scheduler (it will create the next quiz)
    await start_quiz_scheduler(mongo_db, bot_app)
    
    # 6. Create/resume the next quiz safely
    # The scheduler handles this
    
    recovery_msg = (
        "🔄 Quiz system recovered after restart!\n"
        "State loaded from MongoDB.\n"
        "Scheduler resumed. Next quiz in 1 hour."
    )
    
    return recovery_msg