from fastapi import APIRouter, HTTPException, Query, Body
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
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, season, episode"),
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
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, season, episode"),
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
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, season, episode"),
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
    media_type: Optional[str] = Query(None, description="Filter by media type: movie, show, season, episode"),
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
                SUM(CASE WHEN status = 'pending' AND media_type = 'season' THEN 1 ELSE 0 END) as pending_seasons,
                SUM(CASE WHEN status = 'pending' AND media_type = 'episode' THEN 1 ELSE 0 END) as pending_episodes,
                SUM(CASE WHEN status = 'downloading' AND media_type = 'movie' THEN 1 ELSE 0 END) as downloading_movies,
                SUM(CASE WHEN status = 'downloading' AND media_type = 'episode' THEN 1 ELSE 0 END) as downloading_episodes,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'movie' THEN 1 ELSE 0 END) as ignored_movies,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'show' THEN 1 ELSE 0 END) as ignored_shows,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'season' THEN 1 ELSE 0 END) as ignored_seasons,
                SUM(CASE WHEN status = 'ignored' AND media_type = 'episode' THEN 1 ELSE 0 END) as ignored_episodes,
                SUM(CASE WHEN status = 'collected' AND media_type = 'movie' THEN 1 ELSE 0 END) as collected_movies,
                SUM(CASE WHEN status = 'collected' AND media_type = 'show' THEN 1 ELSE 0 END) as collected_shows,
                SUM(CASE WHEN status = 'collected' AND media_type = 'season' THEN 1 ELSE 0 END) as collected_seasons,
                SUM(CASE WHEN status = 'collected' AND media_type = 'episode' THEN 1 ELSE 0 END) as collected_episodes
            FROM v_media
        """
        
        cursor = conn.execute(stats_query)
        row = cursor.fetchone()
        
        # Get local requests count
        local_requests_cursor = conn.execute(
            "SELECT COUNT(*) FROM media_release WHERE status = 'pending' AND requested_at IS NOT NULL"
        )
        local_requests_count = local_requests_cursor.fetchone()[0]
        
        if row:
            stats = {
                "pending": {
                    "movies": row[0],
                    "shows": row[1],
                    "seasons": row[2],
                    "episodes": row[3],
                    "total": row[0] + row[1] + row[2] + row[3]
                },
                "downloading": {
                    "movies": row[4],
                    "episodes": row[5],
                    "total": row[4] + row[5]
                },
                "ignored": {
                    "movies": row[6],
                    "shows": row[7],
                    "seasons": row[8],
                    "episodes": row[9],
                    "total": row[6] + row[7] + row[8] + row[9]
                },
                "collected": {
                    "movies": row[10],
                    "shows": row[11],
                    "seasons": row[12],
                    "episodes": row[13],
                    "total": row[10] + row[11] + row[12] + row[13]
                },
                "local_requests": {
                    "total": local_requests_count
                }
            }
        else:
            stats = {
                "pending": {"movies": 0, "shows": 0, "seasons": 0, "episodes": 0, "total": 0},
                "downloading": {"movies": 0, "episodes": 0, "total": 0},
                "ignored": {"movies": 0, "shows": 0, "seasons": 0, "episodes": 0, "total": 0},
                "collected": {"movies": 0, "shows": 0, "seasons": 0, "episodes": 0, "total": 0},
                "local_requests": {"total": local_requests_count}
            }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.get("/releases")
async def get_releases_for_media(guid: str = Query(..., description="Media item GUID")) -> Dict[str, Any]:
    """Get all releases for a specific media item by GUID"""
    conn = get_db_connection()
    
    try:
        query = """
            SELECT 
                title,
                size,
                seeders,
                source,
                status,
                requested_at,
                link,
                hash,
                updated_at
            FROM media_release 
            WHERE guid = ?
            ORDER BY updated_at DESC
        """
        
        cursor = conn.execute(query, (guid,))
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        releases = []
        for row in rows:
            release = dict(zip(columns, row))
            releases.append(release)
        
        return {
            "guid": guid,
            "releases": releases,
            "count": len(releases)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@router.post("/releases/blacklist")
async def toggle_blacklist_status(guid: str = Query(..., description="Media item GUID"), hash_value: str = Query(..., description="Release hash")) -> Dict[str, Any]:
    """Toggle the blacklist status of a specific release"""
    conn = get_db_connection()
    
    try:
        # First, get the current status
        cursor = conn.execute(
            "SELECT status FROM media_release WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Release not found")
        
        current_status = row[0]
        new_status = 'blacklisted' if current_status != 'blacklisted' else 'pending'
        
        # Update the status
        conn.execute(
            "UPDATE media_release SET status = ?, updated_at = datetime('now') WHERE guid = ? AND hash = ?",
            (new_status, guid, hash_value)
        )
        conn.commit()
        
        return {
            "guid": guid,
            "hash": hash_value,
            "status": new_status,
            "message": f"Release {'blacklisted' if new_status == 'blacklisted' else 'unblacklisted'} successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")

@router.post("/releases/queue")
async def queue_release_for_download(
    guid: str = Query(..., description="Media item GUID"), 
    hash_value: str = Query(..., description="Release hash"),
    release_title: str = Query(..., description="Release title")
) -> Dict[str, Any]:
    """Queue a release for download via local request"""
    conn = get_db_connection()
    
    try:
        # Check if this release is already queued
        cursor = conn.execute(
            "SELECT status FROM media_release WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Release not found")
        
        if row[0] == 'pending' and cursor.execute(
            "SELECT requested_at FROM media_release WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        ).fetchone()[0] is not None:
            raise HTTPException(status_code=409, detail="Release is already queued for download")
        
        # Update the release to mark it as locally requested
        conn.execute(
            "UPDATE media_release SET status = 'pending', requested_at = datetime('now'), updated_at = datetime('now') WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        )
        
        conn.commit()
        
        return {
            "guid": guid,
            "hash": hash_value,
            "title": release_title,
            "status": "queued",
            "message": f"Release '{release_title}' queued for download successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue release: {str(e)}")

@router.delete("/releases/queue")
async def remove_release_from_queue(
    guid: str = Query(..., description="Media item GUID"), 
    hash_value: str = Query(..., description="Release hash")
) -> Dict[str, Any]:
    """Remove a release from the download queue"""
    conn = get_db_connection()
    
    try:
        # Get the release details first
        cursor = conn.execute(
            "SELECT title, requested_at FROM media_release WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Release not found")
        
        release_title, requested_at = row
        
        if requested_at is None:
            raise HTTPException(status_code=404, detail="Release is not queued for download")
        
        # Update the release to remove the local request
        conn.execute(
            "UPDATE media_release SET requested_at = NULL, updated_at = datetime('now') WHERE guid = ? AND hash = ?",
            (guid, hash_value)
        )
        
        conn.commit()
        
        return {
            "guid": guid,
            "hash": hash_value,
            "title": release_title,
            "status": "removed",
            "message": f"Release '{release_title}' removed from download queue"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove release from queue: {str(e)}")

@router.get("/releases/queue")
async def get_queued_releases(
    page: Optional[int] = Query(1, description="Page number (1-based)", ge=1),
    page_size: Optional[int] = Query(50, description="Items per page", ge=1, le=200)
) -> Dict[str, Any]:
    """Get all queued releases"""
    conn = get_db_connection()
    
    try:
        # Get total count
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM media_release WHERE status = 'pending' AND requested_at IS NOT NULL"
        )
        total_count = count_cursor.fetchone()[0]
        
        # Calculate pagination
        offset = (page - 1) * page_size
        
        # Get queued releases with media info
        query = """
            SELECT mr.guid, mr.hash, mr.title, mr.requested_at,
                   m.title as media_title, m.year
            FROM media_release mr
            LEFT JOIN media_movie m ON mr.guid = m.guid
            WHERE mr.status = 'pending' AND mr.requested_at IS NOT NULL
            ORDER BY mr.requested_at DESC
            LIMIT ? OFFSET ?
        """
        
        cursor = conn.execute(query, (page_size, offset))
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
