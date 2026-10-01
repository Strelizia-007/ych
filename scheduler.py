#!/usr/bin/env python3
"""
Hourly Quiz Scheduler for the TMDB Telegram Bot.

Handles the 1-hour quiz cycle:
- Post a new quiz every hour
- Delete the previous quiz poll from POLL_CHAT before posting the next one
- Ensure only ONE active quiz poll exists at a time
- Resume after bot restart if /enablequiz is still active
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

from . import config, db, tmdb_client, quiz, handlers
from .db import (
    set_active_quiz,
    clear_active_quiz,
    get_active_quiz,
    has_quiz_been_asked_today,
    record_quiz_history,
)

logger = logging.getLogger(__name__)

# Scheduler state
_scheduler_task: Optional[asyncio.Task] = None
_is_running = False


# ---------------------------------------------------------------------------
# Scheduler Control
# ---------------------------------------------------------------------------

async def start_quiz_scheduler(mongo_db, bot_app) -> asyncio.Task:
    """
    Start the hourly quiz scheduler.
    Returns the asyncio.Task for the scheduler.
    
    Should be called when the bot starts or when /enablequiz is executed.
    """
    global _scheduler_task, _is_running
    
    if _is_running:
        logger.warning("Quiz scheduler already running")
        return _scheduler_task
    
    _is_running = True
    
    # Cancel any existing task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    
    # Start new scheduler task
    _scheduler_task = asyncio.create_task(_quiz_scheduler_loop(mongo_db, bot_app))
    
    logger.info("Quiz scheduler started")
    return _scheduler_task


async def stop_quiz_scheduler() -> None:
    """
    Stop the hourly quiz scheduler.
    Called when /disablequiz is executed.
    """
    global _scheduler_task, _is_running
    
    if not _is_running:
        logger.info("Quiz scheduler already stopped")
        return
    
    _is_running = False
    
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
    
    logger.info("Quiz scheduler stopped")


# ---------------------------------------------------------------------------
# Check and post next quiz (called by handlers)
# ---------------------------------------------------------------------------

async def check_and_post_next_quiz(mongo_db, bot_app) -> bool:
    """
    Check if a new quiz should be posted and post it.
    Called by /enablequiz handler to immediately post a quiz.
    
    Returns True if a quiz was posted, False otherwise.
    """
    # Check if quiz is enabled
    is_enabled = await db.is_quiz_enabled(mongo_db)
    if not is_enabled:
        logger.info("Quiz disabled - cannot post next quiz")
        return False
    
    # Delete previous poll first
    await _delete_previous_poll(mongo_db, bot_app)
    
    # Generate a new quiz
    new_quiz = await _generate_new_quiz(mongo_db)
    
    if not new_quiz:
        logger.warning("Failed to generate new quiz - skipping")
        return False
    
    # Send the quiz poll
    poll_result = await _send_quiz_poll(bot_app, new_quiz)
    
    if not poll_result:
        logger.error("Failed to send quiz poll - discarding quiz state")
        await db.clear_active_quiz(mongo_db)
        return False
    
    # Save the active poll information
    await _save_active_poll(mongo_db, new_quiz, poll_result)
    
    # Record the TMDB item in history (duplicate prevention)
    await record_quiz_history(mongo_db, new_quiz["tmdb_id"], new_quiz["media_type"])
    
    logger.info("Posted next quiz immediately (via /enablequiz)")
    return True


# ---------------------------------------------------------------------------
# Main Scheduler Loop
# ---------------------------------------------------------------------------

async def _quiz_scheduler_loop(mongo_db, bot_app) -> None:
    """
    The main scheduler loop that runs hourly.
    
    Flow:
    1. Wait for the configured interval (default: 1 hour)
    2. Check if quiz is enabled (via MongoDB)
    3. If enabled:
       a. Find and delete the previous active poll
       b. Generate a new TMDB quiz
       c. Send the quiz poll to POLL_CHAT
       d. Save the active poll information
    4. Repeat from step 1
    """
    interval_seconds = config.get_quiz_interval() * 3600
    
    logger.info(f"Quiz scheduler starting with {config.get_quiz_interval()}-hour interval")
    
    while _is_running:
        try:
            # Wait for the interval
            await asyncio.sleep(interval_seconds)
            
            # Check if quiz is still enabled before proceeding
            is_enabled = await db.is_quiz_enabled(mongo_db)
            
            if not is_enabled:
                logger.info("Quiz disabled - scheduler will wait for re-enable")
                # Wait for enable or shutdown
                while _is_running:
                    await asyncio.sleep(60)  # check every minute
                    is_enabled = await db.is_quiz_enabled(mongo_db)
                    if is_enabled:
                        break
                if not _is_running:
                    break
            
            # Quiz is enabled - proceed with the hourly cycle
            await _cycle_quiz(mongo_db, bot_app)
            
        except asyncio.CancelledError:
            logger.info("Quiz scheduler loop cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}")
            # Continue the loop even if there's an error
            continue


# ---------------------------------------------------------------------------
# Single Quiz Cycle
# ---------------------------------------------------------------------------

async def _cycle_quiz(mongo_db, bot_app) -> None:
    """
    Execute one quiz cycle:
    1. Delete the previous active poll (if any)
    2. Generate a new TMDB quiz
    3. Send the quiz poll to POLL_CHAT
    4. Save the active poll information
    """
    # Step 1: Delete the previous active poll
    await _delete_previous_poll(mongo_db, bot_app)
    
    # Step 2: Generate a new TMDB quiz
    new_quiz = await _generate_new_quiz(mongo_db)
    
    if not new_quiz:
        logger.warning("Failed to generate new quiz - skipping this cycle")
        return
    
    # Step 3: Send the quiz poll to POLL_CHAT
    poll_result = await _send_quiz_poll(bot_app, new_quiz)
    
    if not poll_result:
        logger.error("Failed to send quiz poll - discarding quiz state")
        await db.clear_active_quiz(mongo_db)
        return
    
    # Step 4: Save the active poll information in MongoDB
    await _save_active_poll(mongo_db, new_quiz, poll_result)
    
    # Step 5: Record the TMDB item in history (duplicate prevention)
    await record_quiz_history(mongo_db, new_quiz["tmdb_id"], new_quiz["media_type"])
    
    logger.info("Quiz cycle completed successfully")


# ---------------------------------------------------------------------------
# Delete Previous Poll
# ---------------------------------------------------------------------------

async def _delete_previous_poll(mongo_db, bot_app) -> None:
    """
    Delete the previous active quiz poll from POLL_CHAT.
    Only deletes if DELPREVIOUSPOLL=TRUE (default).
    Silently handles "message not found" errors.
    """
    # Check if we should delete the previous poll
    if not config.is_del_previous_poll():
        logger.info("DELPREVIOUSPOLL=FALSE - keeping previous poll")
        return
    
    active_quiz = await db.get_active_quiz(mongo_db)
    
    if not active_quiz:
        return  # No previous poll to delete
    
    chat_id = active_quiz.get("chat_id")
    message_id = active_quiz.get("message_id")
    
    if not chat_id or not message_id:
        # No chat ID or message ID to delete
        # Just clear the record
        await db.clear_active_quiz(mongo_db)
        return
    
    try:
        # Delete the Telegram message
        # This will fail if the message is already deleted - that's OK
        await bot_app.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(
            f"Deleted previous quiz poll: chat={chat_id}, message={message_id}"
        )
    except Exception as e:
        # Expected errors: message already deleted, bot lacks permission, etc.
        # The important thing is we don't crash the scheduler
        error_msg = str(e).lower()
        if any(
            kw in error_msg
            for kw in ["message not found", "message can't be deleted", "permission"]
        ):
            logger.warning(
                f"Previous poll deletion (expected): {e}"
            )
        else:
            logger.error(f"Unexpected error deleting previous poll: {e}")
    
    # Always clear the old active quiz record after attempting deletion
    await db.clear_active_quiz(mongo_db)


# ---------------------------------------------------------------------------
# Generate New Quiz
# ---------------------------------------------------------------------------

async def _generate_new_quiz(mongo_db) -> Optional[dict]:
    """
    Generate a new quiz using TMDB.
    Ensures the selected TMDB item hasn't been used in the current 7-day period.
    """
    from .tmdb_client import TMDBClient
    
    # Get the TMDB API key from the bot's configuration
    api_key = config.get_tmdb_api_key()
    
    if not api_key:
        logger.error("TMDB_API_KEY not configured")
        return None
    
    tmdb = TMDBClient(api_key=api_key)
    
    # Try to generate a quiz, checking for duplicates
    for attempt in range(5):
        # Generate a quiz from TMDB
        new_quiz = await quiz.generate_quiz_from_tmdb(tmdb)
        
        if not new_quiz:
            logger.warning(f"Quiz attempt {attempt + 1}: No suitable TMDB content")
            continue
        
        # Check duplicate prevention: has this TMDB item been used recently?
        tmdb_id = new_quiz["tmdb_id"]
        media_type = new_quiz["media_type"]
        
        already_used = await db.has_quiz_been_asked_today(mongo_db, tmdb_id, media_type)
        
        if already_used:
            logger.info(
                f"Quiz item TMDB {tmdb_id} was used recently, selecting another"
            )
            # Skip this one and try again (the quiz generation will pick a different title)
            continue
        
        # Valid quiz found - record it in history immediately
        await db.record_quiz_history(mongo_db, tmdb_id, media_type)
        
        return new_quiz
    
    # Failed to find a non-duplicate quiz after all attempts
    logger.error("Failed to generate unique quiz after 5 attempts")
    return None


# ---------------------------------------------------------------------------
# Send Quiz Poll
# ---------------------------------------------------------------------------

async def _send_quiz_poll(bot_app, quiz_doc: dict) -> Optional[dict]:
    """
    Send the quiz poll to POLL_CHAT using Telegram's native QUIZ poll.
    
    Returns the poll result dict with message_id, poll_id, etc., or None on failure.
    """
    from . import config
    
    poll_chat = config.get_poll_chat()
    
    if not poll_chat:
        logger.error("POLL_CHAT not configured - cannot send quiz")
        return None
    
    question = quiz_doc["question"]
    options = quiz_doc["options"]
    correct_index = quiz_doc["correct_option_id"]
    
    try:
        # Send the quiz poll using Telegram's native quiz poll
        result = await bot_app.send_poll(
            chat_id=poll_chat,
            question=question,
            options=options,
            is_anonymous=False,
            type="quiz",
            correct_option_id=correct_index,
        )
        
        logger.info(
            f"Sent quiz poll to {poll_chat}: question={question[:50]}..."
        )
        
        return {
            "message_id": result.message_id,
            "poll_id": result.poll_id,
            "chat_id": poll_chat,
            "question": question,
            "options": options,
            "correct_option_id": correct_index,
            "tmdb_title": quiz_doc.get("tmdb_title", ""),
            "media_type": quiz_doc.get("media_type", "movie"),
            "created_at": time.time(),
        }
        
    except Exception as e:
        logger.error(f"Failed to send quiz poll: {e}")
        # Telegram errors: invalid chat ID, bot lacks permissions, etc.
        return None


# ---------------------------------------------------------------------------
# Save Active Poll
# ---------------------------------------------------------------------------

async def _save_active_poll(
    mongo_db, quiz_doc: dict, poll_result: dict
) -> None:
    """
    Save the active poll information in MongoDB.
    This records the quiz that's currently active in POLL_CHAT.
    """
    chat_id = poll_result.get("chat_id")
    message_id = poll_result.get("message_id")
    poll_id = poll_result.get("poll_id")
    
    if not chat_id or not message_id:
        return
    
    # Build the active quiz document
    active_quiz_doc = {
        "type": "active_quiz",
        "chat_id": chat_id,
        "message_id": message_id,
        "poll_id": poll_id,
        "tmdb_id": quiz_doc["tmdb_id"],
        "media_type": quiz_doc["media_type"],
        "question": quiz_doc["question"],
        "options": quiz_doc["options"],
        "correct_option_id": quiz_doc["correct_option_id"],
        "tmdb_title": quiz_doc["tmdb_title"],
        "created_at": poll_result.get("created_at", time.time()),
    }
    
    # Set as active quiz (atomically replaces any previous)
    await db.set_active_quiz(mongo_db, active_quiz_doc)
    
    logger.info(
        f"Saved active quiz: chat={chat_id}, msg={message_id}, "
        f"TMDB={quiz_doc['tmdb_id']}, type={quiz_doc['media_type']}"
    )