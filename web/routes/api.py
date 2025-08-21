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

@router.get("/media")
async def get_media_items(
    status: Optional[str] = Query(None, description="Filter by status: pending, downloading, ignored, collected"),
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source: plex, trakt, overseerr"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("watchlisted_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get media items using the simplified v_media view"""
    conn = get_db_connection()
    
    try:
        # Build query using the view
        query = "SELECT * FROM v_media WHERE 1=1"
        params = []
        
        # Add filters
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if media_type:
            query += " AND media_type = ?"
            params.append(media_type)
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        if year:
            query += " AND year = ?"
            params.append(year)
        
        if search:
            query += " AND title LIKE ?"
            params.append(f'%{search}%')
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
        count_cursor = conn.execute(count_query, params)
        total_count = count_cursor.fetchone()[0]
        
        # Add sorting and pagination
        offset = (page - 1) * page_size
        
        # Validate sort column to prevent SQL injection
        valid_sort_columns = ["watchlisted_at", "title", "year", "updated_at"]
        if sort_by not in valid_sort_columns:
            sort_by = "watchlisted_at"
        
        query += f" ORDER BY {sort_by} DESC LIMIT {page_size} OFFSET {offset}"
        
        cursor = conn.execute(query, params)
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
                "status": status,
                "media_type": media_type,
                "source": source,
                "year": year,
                "search": search
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/pending")
async def get_pending_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source: plex, trakt, overseerr"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("watchlisted_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending items using the simplified view"""
    return await get_media_items(
        status="pending",
        media_type=media_type,
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/pending/movies")
async def get_pending_movies(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("watchlisted_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending movies only"""
    return await get_media_items(
        status="pending",
        media_type="movie",
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/pending/shows")
async def get_pending_shows(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("watchlisted_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending TV shows only"""
    return await get_media_items(
        status="pending",
        media_type="show",
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/pending/episodes")
async def get_pending_episodes(
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("watchlisted_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get pending episodes only"""
    return await get_media_items(
        status="pending",
        media_type="episode",
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/downloading")
async def get_downloading_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("updated_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get downloading items using the simplified view"""
    return await get_media_items(
        status="downloading",
        media_type=media_type,
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/ignored")
async def get_ignored_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("updated_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get ignored items using the simplified view"""
    return await get_media_items(
        status="ignored",
        media_type=media_type,
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/collected")
async def get_collected_items(
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, episode"),
    source: Optional[str] = Query(None, description="Filter by watchlist source"),
    year: Optional[int] = Query(None, description="Filter by year"),
    search: Optional[str] = Query(None, description="Search in titles"),
    sort_by: Optional[str] = Query("updated_at", description="Sort by: watchlisted_at, title, year, updated_at"),
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get collected items using the simplified view"""
    return await get_media_items(
        status="collected",
        media_type=media_type,
        source=source,
        year=year,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )

@router.get("/stats")
async def get_statistics() -> Dict[str, Any]:
    """Get summary statistics using the simplified view"""
    conn = get_db_connection()
    
    try:
        # Get counts for different statuses and media types
        stats_query = """
            SELECT 
                SUM(CASE WHEN status = 'pending' AND media_type = 'movie' THEN 1 ELSE 0 END) as pending_movies,
                SUM(CASE WHEN status = 'pending' AND media_type = 'show' THEN 1 ELSE 0 END) as pending_shows,
                SUM(CASE WHEN status = 'pending' AND media_type = 'episode' THEN 1 ELSE 0 END) as pending_episodes,
                SUM(CASE WHEN status = 'downloading' AND media_type = 'movie' THEN 1 ELSE 0 END) as downloading_movies,
                SUM(CASE WHEN status = 'downloading' AND media_type = 'episode' THEN 1 ELSE 0 END) as downloading_episodes,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'movie' THEN 1 ELSE 0 END) as ignored_movies,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'show' THEN 1 ELSE 0 END) as ignored_shows,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'episode' THEN 1 ELSE 0 END) as ignored_episodes,
                SUM(CASE WHEN status = 'collected' AND media_type = 'movie' THEN 1 ELSE 0 END) as collected_movies,
                SUM(CASE WHEN status = 'collected' AND media_type = 'show' THEN 1 ELSE 0 END) as collected_shows,
                SUM(CASE WHEN status = 'collected' AND media_type = 'episode' THEN 1 ELSE 0 END) as collected_episodes
            FROM v_media
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
