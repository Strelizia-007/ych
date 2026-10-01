#!/usr/bin/env python3
"""
Configuration module for the TMDB Telegram Bot Quiz feature.

Uses environment variables for configuration. All settings are
designed to be compatible with an existing bot architecture.

This module should be imported after the bot's existing config
to add quiz-specific settings without replacing existing ones.
"""

import os

# Quiz Configuration - environment variables
# These are designed to be merged with existing config, not replace it.
# The existing bot project's config.py should be the primary source.

# Try to load .env file, but don't fail if it doesn't exist
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    # python-dotenv not installed; rely on OS environment variables
    pass

# If QUIZ_ENABLED is not set in env, use "false" as default
# This ensures the quiz starts disabled by default unless explicitly enabled
ENABLED_DEFAULT = os.getenv("QUIZ_ENABLED", "false").lower() == "true"
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", "1"))  # default: 1 hour
POLL_CHAT = os.getenv("POLL_CHAT")  # e.g., -1001234567890 - must be set in bot's .env
DEL_PREVIOUS_POLL = os.getenv("DEL_PREVIOUS_POLL", "true").lower() == "true"

# Seven-day retention configuration
RETENTION_DAYS = 7

# Admin configuration - references existing ADMINS from the bot project
# ADMINS should be set in the existing bot configuration
# This module does NOT create a second admin system.


def is_del_previous_poll():
    """Whether to delete the previous poll before posting a new one."""
    return DEL_PREVIOUS_POLL


def is_quiz_enabled_default():
    """Return the default quiz enabled state from env."""
    return ENABLED_DEFAULT


def get_quiz_interval():
    """Return the quiz interval in hours."""
    return QUIZ_INTERVAL


def get_poll_chat():
    """Return the POLL_CHAT environment variable value."""
    return POLL_CHAT


def get_retention_days():
    """Return the leaderboard data retention period in days."""
    return RETENTION_DAYS


def get_tmdb_api_key():
    """Return the TMDB API key from environment."""
    return os.getenv("TMDB_API_KEY")