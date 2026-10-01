#!/usr/bin/env python3
"""
TMDB Client module for the Telegram Bot Quiz feature.

Provides functions to fetch movies and TV/series from TMDB API.
Designed to be imported by the quiz module.

Reuses TMDB API authentication pattern from the existing project.
"""

import asyncio
import random
import logging
from typing import Optional, Dict, List, Any

import aiohttp

logger = logging.getLogger(__name__)


# TMDB API base URL
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Default timeout for TMDB requests
TMDB_TIMEOUT = 10  # seconds


class TMDBClient:
    """Async TMDB API client."""

    def __init__(self, api_key: str, timeout: int = TMDB_TIMEOUT):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = TMDB_BASE_URL

    async def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """
        Make an async GET request to TMDB API.
        Returns parsed JSON or None on failure.
        """
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key
        params["language"] = "en-US"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        logger.error("TMDB API: Unauthorized (401) - check API key")
                    elif response.status == 404:
                        logger.warning("TMDB API: Not found (404)")
                    else:
                        logger.warning(f"TMDB API: HTTP {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error("TMDB API request timed out")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"TMDB API client error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected TMDB error: {e}")
            return None

    async def get_movie(self, movie_id: int) -> Optional[dict]:
        """Fetch a movie by ID from TMDB."""
        return await self._request(f"movie/{movie_id}")

    async def get_tv_show(self, tv_id: int) -> Optional[dict]:
        """Fetch a TV show by ID from TMDB."""
        return await self._request(f"tv/{tv_id}")

    async def discover_movies(self, **kwargs) -> Optional[dict]:
        """Discover movies with optional filters."""
        return await self._request("discover/movie", kwargs)

    async def discover_tv(self, **kwargs) -> Optional[dict]:
        """Discover TV series with optional filters."""
        return await self._request("discover/tv", kwargs)

    async def get_movie_genres(self) -> Optional[dict]:
        """Fetch movie genres from TMDB."""
        return await self._request("genre/movie/list")

    async def get_tv_genres(self) -> Optional[dict]:
        """Fetch TV genres from TMDB."""
        return await self._request("genre/tv/list")

    async def search_movie(self, query: str) -> Optional[dict]:
        """Search for a movie by query text."""
        return await self._request("search/movie", {"query": query})

    async def search_tv(self, query: str) -> Optional[dict]:
        """Search for a TV series by query text."""
        return await self._request("search/tv", {"query": query})


# ---------------------------------------------------------------------------
# Quiz-Ready Data Fetching
# ---------------------------------------------------------------------------

async def fetch_random_suitable_movie(tmdb: TMDBClient) -> Optional[dict]:
    """
    Fetch a random movie from TMDB that has enough data for a quiz question.
    Returns a movie dict with: title, release_date, genres, overview, etc.
    Returns None if no suitable movie found.
    """
    # Try discovering popular movies
    # We'll try a few approaches to find suitable content
    
    # Approach 1: Get popular movies
    result = await tmdb.discover_movies(
        with_original_language="en",
        sort_by="popularity.desc",
        limit=20  # we'll only use first page
    )
    
    if not result:
        return None
    
    movies = result.get("results", [])
    if not movies:
        return None
    
    # Filter movies that have release date and overview
    suitable = []
    for movie in movies:
        release_date = movie.get("release_date")
        overview = movie.get("overview")
        title = movie.get("title")
        if release_date and overview and title:
            suitable.append(movie)
    
    if not suitable:
        return None
    
    # Return a random suitable movie
    return random.choice(suitable)


async def fetch_random_suitable_tv(tmdb: TMDBClient) -> Optional[dict]:
    """
    Fetch a random TV/series from TMDB that has enough data for a quiz question.
    Returns a TV show dict with: name, first_air_date, genres, overview, etc.
    Returns None if no suitable show found.
    """
    # Try discovering popular TV shows
    result = await tmdb.discover_tv(
        with_original_language="en",
        sort_by="popularity.desc",
    )
    
    if not result:
        return None
    
    shows = result.get("results", [])
    if not shows:
        return None
    
    # Filter shows that have first air date and overview
    suitable = []
    for show in shows:
        first_air_date = show.get("first_air_date")
        overview = show.get("overview")
        name = show.get("name")
        if first_air_date and overview and name:
            suitable.append(show)
    
    if not suitable:
        return None
    
    # Return a random suitable show
    return random.choice(suitable)


async def fetch_movie_details(tmdb: TMDBClient, movie_id: int) -> Optional[dict]:
    """Fetch full movie details from TMDB by ID."""
    return await tmdb.get_movie(movie_id)


async def fetch_tv_details(tmdb: TMDBClient, tv_id: int) -> Optional[dict]:
    """Fetch full TV show details from TMDB by ID."""
    return await tmdb.get_tv_show(tv_id)