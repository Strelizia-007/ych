#!/usr/bin/env python3
"""
Core Quiz Module for the TMDB Telegram Bot.

Handles:
- TMDB movie/TV selection
- Quiz question generation
- Four answer option creation (1 correct, 3 incorrect)
- Option shuffling and storage
- Quiz document formatting for Telegram
"""

import random
import logging
from typing import Optional, List, Dict, Any, Tuple

from .tmdb_client import (
    TMDBClient,
    fetch_random_suitable_movie,
    fetch_random_suitable_tv,
    fetch_movie_details,
    fetch_tv_details,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Question Generation
# ---------------------------------------------------------------------------

def generate_movie_question(movie: dict) -> Optional[dict]:
    """
    Generate a quiz question from movie data.
    Returns dict with 'question' and 'correct_answer' keys, or None if
    insufficient data.
    """
    title = movie.get("title", "")
    release_date = movie.get("release_date", "")
    overview = movie.get("overview", "")
    genres = movie.get("genre_ids", [])
    original_title = movie.get("original_title", "")

    # Try to extract year from release_date
    year = None
    if release_date:
        try:
            year = release_date.split("-")[0]
        except (AttributeError, IndexError):
            year = None

    # Question type 1: Release year
    if year:
        question = f"In which year was the movie '{title}' released?"
        return {
            "question": question,
            "correct_answer": year,
            "question_type": "movie_year",
            "media_type": "movie",
            "tmdb_title": title,
        }

    # Question type 2: Original title
    if original_title and original_title != title:
        question = f"What is the original title of the movie '{title}'?"
        return {
            "question": question,
            "correct_answer": original_title,
            "question_type": "movie_original_title",
            "media_type": "movie",
            "tmdb_title": title,
        }

    # Question type 3: Genre
    if genres:
        # Get genre names would require another API call; for now use IDs as fallback
        question = f"Which movie has genre IDs {', '.join(map(str, genres[:3]))}?"
        return {
            "question": question,
            "correct_answer": title,
            "question_type": "movie_genre",
            "media_type": "movie",
            "tmdb_title": title,
        }

    # Question type 4: Tagline/description
    if overview:
        # Create a simple question from the overview
        words = overview.split()
        if len(words) > 5:
            # Use first few words as a hint
            hint = " ".join(words[:5]) + "..."
            question = f"Which movie does this describe: '{hint}'?"
            return {
                "question": question,
                "correct_answer": title,
                "question_type": "movie_description",
                "media_type": "movie",
                "tmdb_title": title,
            }

    return None


def generate_tv_question(tv: dict) -> Optional[dict]:
    """
    Generate a quiz question from TV/series data.
    Returns dict with 'question' and 'correct_answer' keys, or None if
    insufficient data.
    """
    name = tv.get("name", "")
    first_air_date = tv.get("first_air_date", "")
    overview = tv.get("overview", "")
    genres = tv.get("genre_ids", [])
    original_name = tv.get("original_name", "")

    # Try to extract year from first_air_date
    year = None
    if first_air_date:
        try:
            year = first_air_date.split("-")[0]
        except (AttributeError, IndexError):
            year = None

    # Question type 1: First air year
    if year:
        question = f"In which year did the TV series '{name}' first air?"
        return {
            "question": question,
            "correct_answer": year,
            "question_type": "tv_year",
            "media_type": "tv",
            "tmdb_title": name,
        }

    # Question type 2: Original name
    if original_name and original_name != name:
        question = f"What is the original name of the TV series '{name}'?"
        return {
            "question": question,
            "correct_answer": original_name,
            "question_type": "tv_original_name",
            "media_type": "tv",
            "tmdb_title": name,
        }

    # Question type 3: Genre
    if genres:
        question = f"Which TV series has genre IDs {', '.join(map(str, genres[:3]))}?"
        return {
            "question": question,
            "correct_answer": name,
            "question_type": "tv_genre",
            "media_type": "tv",
            "tmdb_title": name,
        }

    # Question type 4: Description
    if overview:
        words = overview.split()
        if len(words) > 5:
            hint = " ".join(words[:5]) + "..."
            question = f"Which TV series does this describe: '{hint}'?"
            return {
                "question": question,
                "correct_answer": name,
                "question_type": "tv_description",
                "media_type": "tv",
                "tmdb_title": name,
            }

    return None


# ---------------------------------------------------------------------------
# Answer Option Generation
# ---------------------------------------------------------------------------

def generate_wrong_answers(correct_answer: str, existing_options: List[str] = None) -> List[str]:
    """
    Generate 3 wrong answer options.
    The correct answer is excluded. Options should be plausible but incorrect.
    """
    existing_options = existing_options or []
    wrong = []
    
    # Common movie/TV facts we can use as distractors
    # These are generated based on the correct answer type
    
    if existing_options:
        # Use provided options as base, replace one if needed
        pass
    
    # Strategy: generate plausible but incorrect answers
    # We'll use a simple approach based on the correct answer
    
    attempt = 0
    while len(wrong) < 3 and attempt < 20:
        attempt += 1
        # Generate a distracter based on the correct answer
        if correct_answer.isdigit() and len(correct_answer) == 4:
            # It's a year - generate nearby years
            year = int(correct_answer)
            # Pick a different year, avoiding adjacent years
            distracter_year = year + random.choice([-5, -3, 3, 5])
            if distracter_year > 1888 and distracter_year < 2028:
                wrong.append(str(distracter_year))
        else:
            # For titles, use common movie titles that are different
            # Simple approach: use well-known movies/series as distractors
            distractors = [
                "The Matrix", "Inception", "Interstellar", "The Godfather",
                "Game of Thrones", "Friends", "Breaking Bad", "Stranger Things"
            ]
            # Pick one that's different from correct_answer
            option = random.choice(distractors)
            if option != correct_answer and option not in wrong:
                wrong.append(option)
    
    # If we don't have enough, fill with generic options
    while len(wrong) < 3:
        wrong.append(f"Option {len(wrong) + 1}")
    
    # Ensure no duplicates and correct answer is not in wrong
    wrong = list(dict.fromkeys(wrong))  # remove duplicates
    if correct_answer in wrong:
        wrong.remove(correct_answer)
    
    # Pad to exactly 3
    while len(wrong) < 3:
        wrong.append("Unknown")
    
    return wrong[:3]


def create_four_options(
    correct_answer: str,
    incorrect_hints: List[str] = None
) -> Tuple[List[str], int]:
    """
    Create exactly 4 answer options with randomized order.
    
    Returns:
        (options_list, correct_option_index)
        - options_list: list of exactly 4 strings
        - correct_option_index: index (0-3) where the correct answer is placed
    """
    # Generate 3 wrong answers
    wrong = generate_wrong_answers(correct_answer, incorrect_hints)
    
    # Combine: wrong + correct, then shuffle
    all_options = wrong + [correct_answer]
    
    # Shuffle the options
    random.shuffle(all_options)
    
    # Find the index of the correct answer after shuffling
    correct_index = all_options.index(correct_answer)
    
    # Final safety: ensure exactly 4 options and exactly 1 correct
    assert len(all_options) == 4, f"Expected 4 options, got {len(all_options)}"
    assert correct_index >= 0 and correct_index <= 3, "Correct index out of range"
    
    # Double-check: correct answer should only appear once
    assert all_options.count(correct_answer) == 1, "Correct answer appears more than once"
    
    return all_options, correct_index


# ---------------------------------------------------------------------------
# Quiz Document Construction
# ---------------------------------------------------------------------------

def build_quiz_document(
    question: str,
    options: List[str],
    correct_option_index: int,
    tmdb_id: int,
    media_type: str,
    tmdb_title: str,
    question_type: str,
) -> dict:
    """
    Build a quiz document suitable for storage in MongoDB and Telegram poll creation.
    
    Returns dict with:
    - question: the quiz question text
    - options: list of 4 answer options (shuffled order)
    - correct_option_id: index 0-3 of the correct answer
    - tmdb_id: the TMDB ID of the media
    - media_type: "movie" or "tv"
    - tmdb_title: the title/name
    - question_type: the type of question generated
    - created_at: Unix timestamp
    """
    return {
        "question": question,
        "options": options,
        "correct_option_id": correct_option_index,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "tmdb_title": tmdb_title,
        "question_type": question_type,
        "created_at": __import__("time").time(),
    }


# ---------------------------------------------------------------------------
# Main Quiz Generation Function
# ---------------------------------------------------------------------------

async def generate_quiz_from_tmdb(
    tmdb: TMDBClient,
    max_attempts: int = 5,
) -> Optional[dict]:
    """
    Generate a complete quiz by:
    1. Randomly selecting a suitable movie or TV from TMDB
    2. Generating a question
    3. Creating 4 answer options (1 correct, 3 incorrect)
    4. Building the quiz document
    
    Returns a quiz document dict, or None if no suitable content found
    after max_attempts.
    """
    for attempt in range(max_attempts):
        # Randomly choose movie or TV
        media_type = random.choice(["movie", "tv"])
        
        # Fetch suitable content
        if media_type == "movie":
            content = await fetch_random_suitable_movie(tmdb)
            if not content:
                continue
            
            # Generate question
            question_data = generate_movie_question(content)
            if not question_data:
                continue
            
            # Create options
            options, correct_index = create_four_options(question_data["correct_answer"])
            
            # Build quiz document
            quiz_doc = build_quiz_document(
                question=question_data["question"],
                options=options,
                correct_option_index=correct_index,
                tmdb_id=content.get("id", 0),
                media_type="movie",
                tmdb_title=question_data["tmdb_title"],
                question_type=question_data["question_type"],
            )
            
            # Verify no duplicate options
            if len(set(quiz_doc["options"])) != 4:
                logger.warning(f"Quiz attempt {attempt + 1}: Duplicate options, retrying")
                continue
            
            return quiz_doc
            
        else:  # tv
            content = await fetch_random_suitable_tv(tmdb)
            if not content:
                continue
            
            # Generate question
            question_data = generate_tv_question(content)
            if not question_data:
                continue
            
            # Create options
            options, correct_index = create_four_options(question_data["correct_answer"])
            
            # Build quiz document
            quiz_doc = build_quiz_document(
                question=question_data["question"],
                options=options,
                correct_option_index=correct_index,
                tmdb_id=content.get("id", 0),
                media_type="tv",
                tmdb_title=question_data["tmdb_title"],
                question_type=question_data["question_type"],
            )
            
            # Verify no duplicate options
            if len(set(quiz_doc["options"])) != 4:
                logger.warning(f"Quiz attempt {attempt + 1}: Duplicate options, retrying")
                continue
            
            return quiz_doc
    
    logger.error(
        f"Failed to generate suitable quiz after {max_attempts} attempts"
    )
    return None