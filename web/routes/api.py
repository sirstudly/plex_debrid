from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import sqlite3
import os
import sys

# Add the parent directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from store.sqlite_store import _get_connection

router = APIRouter()

def get_db_connection():
    """Get database connection"""
    try:
        return _get_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@router.get("/pending")
async def get_pending_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source: plex, trakt, overseerr"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get all pending media items"""
    conn = get_db_connection()
    
    try:
        # Build query based on media type
        if media_type == "movie":
            query = """
                SELECT guid, title, year, imdb, tmdb, tvdb, watchlisted_by, watchlisted_at, updated_at
                FROM media_movie 
                WHERE collected = 0 AND ignored = 0 AND downloading = 0
            """
        elif media_type == "show":
            query = """
                SELECT guid, title, year, imdb, tmdb, tvdb, watchlisted_by, watchlisted_at, updated_at
                FROM media_show 
                WHERE collected = 0 AND ignored = 0
            """
        elif media_type == "episode":
            query = """
                SELECT guid, title, parent_title, grandparent_title, parent_index, idx, year, 
                       watchlisted_by, updated_at
                FROM media_episode 
                WHERE collected = 0 AND ignored = 0 AND downloading = 0
            """
        else:
            # Get all types
            query = """
                SELECT 'movie' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, watchlisted_at, updated_at
                FROM media_movie 
                WHERE collected = 0 AND ignored = 0 AND downloading = 0
                UNION ALL
                SELECT 'show' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, watchlisted_at, updated_at
                FROM media_show 
                WHERE collected = 0 AND ignored = 0
                UNION ALL
                SELECT 'episode' as type, guid, 
                       CASE 
                           WHEN parent_title IS NOT NULL AND parent_title != '' 
                           THEN title || ' (' || parent_title || ')'
                           ELSE title 
                       END as title, 
                       year, NULL as imdb, NULL as tmdb, NULL as tvdb, 
                       watchlisted_by, updated_at as watchlisted_at, updated_at
                FROM media_episode 
                WHERE collected = 0 AND ignored = 0 AND downloading = 0
            """
        
        # Add source filter if specified
        if source:
            if "WHERE" in query:
                query += f" AND watchlisted_by LIKE '%{source}%'"
            else:
                query += f" WHERE watchlisted_by LIKE '%{source}%'"
        
        # Get total count first
        if "UNION ALL" in query:
            # For UNION ALL queries, we need to wrap the entire query in a subquery
            count_query = f"SELECT COUNT(*) as total FROM ({query}) as subquery"
        else:
            # For single table queries, replace the entire SELECT clause
            # Find the position of FROM and replace everything between SELECT and FROM
            from_pos = query.find("FROM")
            if from_pos != -1:
                count_query = "SELECT COUNT(*) as total " + query[from_pos:]
            else:
                # Fallback: just replace SELECT with COUNT
                count_query = query.replace("SELECT", "SELECT COUNT(*) as total", 1)
        
        count_cursor = conn.execute(count_query)
        total_count = count_cursor.fetchone()[0]
        
        # Add pagination
        offset = (page - 1) * page_size
        if media_type == "episode":
            query += f" ORDER BY updated_at DESC LIMIT {page_size} OFFSET {offset}"
        else:
            query += f" ORDER BY watchlisted_at DESC LIMIT {page_size} OFFSET {offset}"
        
        cursor = conn.execute(query)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        items = []
        for row in rows:
            item = dict(zip(columns, row))
            items.append(item)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            },
            "filters": {
                "media_type": media_type,
                "source": source
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/pending/movies")
async def get_pending_movies(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending movies only"""
    return await get_pending_items(media_type="movie", source=source, page=page, page_size=page_size)

@router.get("/pending/shows")
async def get_pending_shows(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending TV shows only"""
    return await get_pending_items(media_type="show", source=source, page=page, page_size=page_size)

@router.get("/pending/episodes")
async def get_pending_episodes(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending episodes only"""
    return await get_pending_items(media_type="episode", source=source, page=page, page_size=page_size)

@router.get("/downloading")
async def get_downloading_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, episode"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get currently downloading items"""
    conn = get_db_connection()
    
    try:
        if media_type == "movie":
            query = """
                SELECT 'movie' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_movie 
                WHERE downloading = 1
                ORDER BY updated_at DESC
            """
        elif media_type == "episode":
            query = """
                SELECT 'episode' as type, guid, 
                       CASE 
                           WHEN parent_title IS NOT NULL AND parent_title != '' 
                           THEN title || ' (' || parent_title || ')'
                           ELSE title 
                       END as title, 
                       year, NULL as imdb, NULL as tmdb, NULL as tvdb, 
                       watchlisted_by, updated_at
                FROM media_episode 
                WHERE downloading = 1
                ORDER BY updated_at DESC
            """
        else:
            query = """
                SELECT 'movie' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_movie 
                WHERE downloading = 1
                UNION ALL
                SELECT 'episode' as type, guid, 
                       CASE 
                           WHEN parent_title IS NOT NULL AND parent_title != '' 
                           THEN title || ' (' || parent_title || ')'
                           ELSE title 
                       END as title, 
                       year, NULL as imdb, NULL as tmdb, NULL as tvdb, 
                       watchlisted_by, updated_at
                FROM media_episode 
                WHERE downloading = 1
                ORDER BY updated_at DESC
            """
        
        # Get total count first
        if "UNION ALL" in query:
            # For UNION ALL queries, we need to wrap the entire query in a subquery
            count_query = f"SELECT COUNT(*) as total FROM ({query}) as subquery"
        else:
            # For single table queries, replace the entire SELECT clause
            # Find the position of FROM and replace everything between SELECT and FROM
            from_pos = query.find("FROM")
            if from_pos != -1:
                count_query = "SELECT COUNT(*) as total " + query[from_pos:]
            else:
                # Fallback: just replace SELECT with COUNT
                count_query = query.replace("SELECT", "SELECT COUNT(*) as total", 1)
        
        count_cursor = conn.execute(count_query)
        total_count = count_cursor.fetchone()[0]
        
        # Add pagination
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        cursor = conn.execute(query)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        items = []
        for row in rows:
            item = dict(zip(columns, row))
            items.append(item)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/ignored")
async def get_ignored_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get ignored items"""
    conn = get_db_connection()
    
    try:
        if media_type == "movie":
            query = """
                SELECT 'movie' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_movie 
                WHERE ignored = 1
            """
        elif media_type == "show":
            query = """
                SELECT 'show' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_show 
                WHERE ignored = 1
            """
        elif media_type == "episode":
            query = """
                SELECT 'episode' as type, guid, 
                       CASE 
                           WHEN parent_title IS NOT NULL AND parent_title != '' 
                           THEN title || ' (' || parent_title || ')'
                           ELSE title 
                       END as title, 
                       year, NULL as imdb, NULL as tmdb, NULL as tvdb, 
                       watchlisted_by, updated_at
                FROM media_episode 
                WHERE ignored = 1
            """
        else:
            query = """
                SELECT 'movie' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_movie 
                WHERE ignored = 1
                UNION ALL
                SELECT 'show' as type, guid, title, year, imdb, tmdb, tvdb, watchlisted_by, updated_at
                FROM media_show 
                WHERE ignored = 1
                UNION ALL
                SELECT 'episode' as type, guid, 
                       CASE 
                           WHEN parent_title IS NOT NULL AND parent_title != '' 
                           THEN title || ' (' || parent_title || ')'
                           ELSE title 
                       END as title, 
                       year, NULL as imdb, NULL as tmdb, NULL as tvdb, 
                       watchlisted_by, updated_at
                FROM media_episode 
                WHERE ignored = 1
            """
        
        # Get total count first
        if "UNION ALL" in query:
            # For UNION ALL queries, we need to wrap the entire query in a subquery
            count_query = f"SELECT COUNT(*) as total FROM ({query}) as subquery"
        else:
            # For single table queries, replace the entire SELECT clause
            # Find the position of FROM and replace everything between SELECT and FROM
            from_pos = query.find("FROM")
            if from_pos != -1:
                count_query = "SELECT COUNT(*) as total " + query[from_pos:]
            else:
                # Fallback: just replace SELECT with COUNT
                count_query = query.replace("SELECT", "SELECT COUNT(*) as total", 1)
        
        count_cursor = conn.execute(count_query)
        total_count = count_cursor.fetchone()[0]
        
        # Add pagination
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        cursor = conn.execute(query)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        items = []
        for row in rows:
            item = dict(zip(columns, row))
            items.append(item)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/stats")
async def get_statistics() -> Dict[str, Any]:
    """Get summary statistics"""
    conn = get_db_connection()
    
    try:
        # Get counts for different media types and statuses
        stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM media_movie WHERE collected = 0 AND ignored = 0 AND downloading = 0) as pending_movies,
                (SELECT COUNT(*) FROM media_show WHERE collected = 0 AND ignored = 0) as pending_shows,
                (SELECT COUNT(*) FROM media_episode WHERE collected = 0 AND ignored = 0 AND downloading = 0) as pending_episodes,
                (SELECT COUNT(*) FROM media_movie WHERE downloading = 1) as downloading_movies,
                (SELECT COUNT(*) FROM media_episode WHERE downloading = 1) as downloading_episodes,
                (SELECT COUNT(*) FROM media_movie WHERE ignored = 1) as ignored_movies,
                (SELECT COUNT(*) FROM media_show WHERE ignored = 1) as ignored_shows,
                (SELECT COUNT(*) FROM media_episode WHERE ignored = 1) as ignored_episodes,
                (SELECT COUNT(*) FROM media_movie WHERE collected = 1) as collected_movies,
                (SELECT COUNT(*) FROM media_show WHERE collected = 1) as collected_shows,
                (SELECT COUNT(*) FROM media_episode WHERE collected = 1) as collected_episodes
        """
        
        cursor = conn.execute(stats_query)
        row = cursor.fetchone()
        
        if row:
            stats = {
                "pending": {
                    "movies": row[0],
                    "shows": row[1],
                    "episodes": row[2],
                    "total": row[0] + row[1] + row[2]
                },
                "downloading": {
                    "movies": row[3],
                    "episodes": row[4],
                    "total": row[3] + row[4]
                },
                "ignored": {
                    "movies": row[5],
                    "shows": row[6],
                    "episodes": row[7],
                    "total": row[5] + row[6] + row[7]
                },
                "collected": {
                    "movies": row[8],
                    "shows": row[9],
                    "episodes": row[10],
                    "total": row[8] + row[9] + row[10]
                }
            }
        else:
            stats = {
                "pending": {"movies": 0, "shows": 0, "episodes": 0, "total": 0},
                "downloading": {"movies": 0, "episodes": 0, "total": 0},
                "ignored": {"movies": 0, "shows": 0, "episodes": 0, "total": 0},
                "collected": {"movies": 0, "shows": 0, "episodes": 0, "total": 0}
            }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
