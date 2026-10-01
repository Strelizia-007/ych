#!/usr/bin/env python3
"""
Database module for the TMDB Telegram Bot Quiz feature.

Adds quiz-related MongoDB operations to the existing database layer.
Designed to be imported and extended by the bot project's db module.

DO NOT replace the existing db.py - only add quiz-related functions.
"""

import asyncio
import time
from datetime import datetime, timedelta

# MongoDB collection names (strings to avoid circular imports)
QUIZ_STATE_COLLECTION = "quiz_state"
QUIZ_HISTORY_COLLECTION = "quiz_history"
QUIZ_ANSWERS_COLLECTION = "quiz_answers"
QUIZ_SCORES_COLLECTION = "quiz_scores"


# ---------------------------------------------------------------------------
# QUIZ STATE
# ---------------------------------------------------------------------------

async def set_quiz_enabled(mongo_db, enabled: bool):
    """
    Persist the quiz enabled/disabled state in MongoDB.
    Creates/updates a single document in quiz_state collection.
    """
    await mongo_db[QUIZ_STATE_COLLECTION].replace_one(
        {"type": "quiz_config"},
        {"type": "quiz_config", "quiz_enabled": enabled, "updated_at": time.time()},
        upsert=True,
    )


async def is_quiz_enabled(mongo_db) -> bool:
    """
    Check whether the quiz system is enabled.
    Returns False if no state document exists (safe default).
    """
    doc = await mongo_db[QUIZ_STATE_COLLECTION].find_one({"type": "quiz_config"})
    if doc is None:
        return False
    return doc.get("quiz_enabled", False)


async def get_quiz_interval_config(mongo_db) -> int:
    """
    Get the quiz interval from MongoDB configuration.
    Falls back to the default (1 hour) if not set.
    """
    doc = await mongo_db[QUIZ_STATE_COLLECTION].find_one({"type": "quiz_config"})
    if doc and "interval_hours" in doc:
        return doc["interval_hours"]
    return 1  # default


async def set_quiz_interval(mongo_db, hours: int):
    """Set the quiz interval in hours."""
    await mongo_db[QUIZ_STATE_COLLECTION].update_one(
        {"type": "quiz_config"},
        {"$set": {"interval_hours": hours, "updated_at": time.time()}},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# ACTIVE QUIZ
# ---------------------------------------------------------------------------

async def set_active_quiz(mongo_db, quiz_doc: dict):
    """
    Set the active quiz in MongoDB.
    This atomically replaces any previous active quiz.
    """
    # First, clean up the previous active quiz if exists
    await mongo_db[QUIZ_STATE_COLLECTION].delete_one(
        {"type": "active_quiz", "chat_id": quiz_doc.get("chat_id")}
    )
    # Insert the new active quiz
    await mongo_db[QUIZ_STATE_COLLECTION].insert_one(quiz_doc)


async def get_active_quiz(mongo_db):
    """
    Get the current active quiz, if any.
    Returns None if no active quiz exists.
    """
    doc = await mongo_db[QUIZ_STATE_COLLECTION].find_one({"type": "active_quiz"})
    return doc


async def clear_active_quiz(mongo_db):
    """Clear the active quiz record from MongoDB."""
    await mongo_db[QUIZ_STATE_COLLECTION].delete_one({"type": "active_quiz"})


# ---------------------------------------------------------------------------
# QUIZ HISTORY (duplicate prevention)
# ---------------------------------------------------------------------------

async def has_quiz_been_asked_today(mongo_db, tmdb_id: int, media_type: str) -> bool:
    """
    Check if a TMDB item has been used as a quiz question within the current
    7-day period. Used for duplicate prevention.
    """
    seven_days_ago = time.time() - (7 * 24 * 3600)
    doc = await mongo_db[QUIZ_HISTORY_COLLECTION].find_one(
        {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "created_at": {"$gt": seven_days_ago},
        }
    )
    return doc is not None


async def record_quiz_history(mongo_db, tmdb_id: int, media_type: str):
    """
    Record that a TMDB item was used for a quiz.
    This helps prevent duplicate questions within the 7-day period.
    """
    await mongo_db[QUIZ_HISTORY_COLLECTION].insert_one(
        {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "created_at": time.time(),
        }
    )


async def cleanup_old_quiz_history(mongo_db):
    """
    Remove quiz history older than 7 days.
    Can be run as a scheduled task.
    """
    seven_days_ago = time.time() - (7 * 24 * 3600)
    await mongo_db[QUIZ_HISTORY_COLLECTION].delete_many(
        {"created_at": {"$lt": seven_days_ago}}
    )


# ---------------------------------------------------------------------------
# QUIZ ANSWERS / ANSWER TRACKING
# ---------------------------------------------------------------------------

async def record_user_answer(mongo_db, quiz_id: str, user_id: int, username: str,
                             selected_option_index: int, is_correct: bool):
    """
    Record a user's answer to a quiz.
    Uses upsert with quiz_id + user_id to ensure one answer per user per quiz.
    """
    await mongo_db[QUIZ_ANSWERS_COLLECTION].update_one(
        {"quiz_id": quiz_id, "user_id": user_id},
        {
            "$set": {
                "quiz_id": quiz_id,
                "user_id": user_id,
                "username": username,
                "selected_option_index": selected_option_index,
                "is_correct": is_correct,
                "answered_at": time.time(),
            }
        },
        upsert=True,
    )


async def user_already_answered(mongo_db, quiz_id: str, user_id: int) -> bool:
    """
    Check whether a user has already answered this quiz.
    Returns True if the user has already submitted an answer.
    """
    doc = await mongo_db[QUIZ_ANSWERS_COLLECTION].find_one(
        {"quiz_id": quiz_id, "user_id": user_id}
    )
    return doc is not None


async def get_quiz_correct_count(mongo_db, quiz_id: str) -> int:
    """Get the number of correct answers for a given quiz."""
    docs = await mongo_db[QUIZ_ANSWERS_COLLECTION].find(
        {"quiz_id": quiz_id, "is_correct": True}
    ).to(length=None)
    return len(list(docs))


async def get_quiz_answered_count(mongo_db, quiz_id: str) -> int:
    """Get the total number of answers for a given quiz."""
    docs = await mongo_db[QUIZ_ANSWERS_COLLECTION].find({"quiz_id": quiz_id}).to(length=None)
    return len(list(docs))


# ---------------------------------------------------------------------------
# QUIZ SCORES / LEADERBOARD
# ---------------------------------------------------------------------------

async def add_user_score(mongo_db, user_id: int, username: str, is_correct: bool):
    """
    Update a user's quiz score/correct-answer count.
    Uses upsert with user_id to maintain rolling 7-day statistics.
    """
    # The period_start is managed separately; this function updates the counts
    now = time.time()
    period_start = now - (7 * 24 * 3600)  # start of 7-day period

    await mongo_db[QUIZ_SCORES_COLLECTION].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "username": username,
                "period_start": period_start,
                "last_answered_at": now,
            }
        },
        upsert=True,
    )

    # Increment the appropriate counter
    if is_correct:
        await mongo_db[QUIZ_SCORES_COLLECTION].update_one(
            {"user_id": user_id},
            {"$inc": {"correct_answers": 1}},
        )
    # Always increment quizzes_answered
    await mongo_db[QUIZ_SCORES_COLLECTION].update_one(
        {"user_id": user_id},
        {"$inc": {"quizzes_answered": 1}},
    )


async def get_leaderboard(mongo_db, limit: int = 10):
    """
    Get the top users for the leaderboard based on correct answers (primary)
    and quizzes_answered (secondary).
    Only includes users from the current 7-day period.
    """
    now = time.time()
    period_start = now - (7 * 24 * 3600)

    pipeline = [
        {
            "$match": {
                "period_start": {"$gte": period_start},
            }
        },
        {
            "$sort": {
                "correct_answers": -1,
                "quizzes_answered": -1,  # secondary sort
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "user_id": 1,
                "username": 1,
                "correct_answers": 1,
                "quizzes_answered": 1,
                # Calculate percentage for display
                "correct_percentage": {
                    "$cond": [
                        {"$gt": ["$quizzes_answered", 0]},
                        {"$multiply": [{"$divide": ["$correct_answers", "$quizzes_answered"]}, 100]},
                        0,
                    ]
                },
            }
        },
    ]

    cursor = mongo_db[QUIZ_SCORES_COLLECTION].aggregate(pipeline)
    return await cursor.to_list(length=limit)


async def cleanup_old_scores(mongo_db):
    """
    Remove quiz score records older than 7 days.
    Should be run as a scheduled task.
    """
    now = time.time()
    period_start = now - (7 * 24 * 3600)
    await mongo_db[QUIZ_SCORES_COLLECTION].delete_many(
        {"period_start": {"$lt": period_start}}
    )


# Ensure unique index: one answer per user per quiz
async def ensure_quiz_answer_indexes(mongo_db):
    """
    Create MongoDB indexes that enforce business rules:
    - One answer per user per quiz (quiz_id + user_id unique)
    - Fast lookup by user_id
    """
    # Prevent duplicate answers for same quiz + user
    await mongo_db[QUIZ_ANSWERS_COLLECTION].create_index(
        [("quiz_id", 1), ("user_id", 1)], unique=True
    )
    # Index for fast user lookups in leaderboard
    await mongo_db[QUIZ_SCORES_COLLECTION].create_index([("user_id", 1)])
    # Index for period-based queries
    await mongo_db[QUIZ_SCORES_COLLECTION].create_index([("period_start", 1)])
    # Index for quiz history
    await mongo_db[QUIZ_HISTORY_COLLECTION].create_index([("created_at", 1)])
    # Index for active quiz lookups
    await mongo_db[QUIZ_STATE_COLLECTION].create_index([("type", 1)])