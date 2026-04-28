import os
import sqlite3
import datetime
from typing import Optional

_connection: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def init_db(db_dir: Optional[str] = None, filename: str = "plex_debrid.sqlite3") -> str:
    """Initialize the SQLite database and ensure all tables and views exist.

    Args:
        db_dir: Directory to place the database file. Defaults to './store'.
        filename: Database filename. Defaults to 'plex_debrid.sqlite3'.

    Returns:
        The absolute path to the database file.
    """
    global _connection, _db_path

    if db_dir is None:
        db_dir = ""

    db_file = os.path.abspath(os.path.join(db_dir, filename))
    _ensure_dir(db_file)

    if _connection is None or _db_path != db_file:
        # Close previous connection if switching DB targets
        if _connection is not None and _db_path and _db_path != db_file:
            try:
                _connection.close()
            except Exception:
                pass
        _connection = sqlite3.connect(db_file, check_same_thread=False)
        
        # Load and execute the comprehensive database setup script
        setup_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database_setup.sql')
        with open(setup_script_path, 'r') as f:
            setup_script = f.read()
        _connection.executescript(setup_script)
        # Lightweight schema migration for older databases
        try:
            cols = [r[1] for r in _connection.execute("PRAGMA table_info(media_show)").fetchall()]
            if "collected_episode_count" not in cols:
                _connection.execute("ALTER TABLE media_show ADD COLUMN collected_episode_count INTEGER DEFAULT 0")
            if "last_collection_progress_at" not in cols:
                _connection.execute("ALTER TABLE media_show ADD COLUMN last_collection_progress_at TEXT")
        except Exception:
            pass
        _connection.commit()

        _db_path = db_file

    return db_file


def _get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        # Lazy-init with default location if not initialized explicitly
        init_db()
    assert _connection is not None
    return _connection


def _convert_watchlisted_at(media_obj) -> Optional[str]:
    """Convert watchlisted_at from Unix timestamp to ISO8601 format.
    
    Args:
        media_obj: The media object containing watchlistedAt attribute
        
    Returns:
        ISO8601 formatted string or None if no valid timestamp
    """
    if hasattr(media_obj, 'watchlistedAt') and media_obj.watchlistedAt is not None:
        if isinstance(media_obj.watchlistedAt, int) and media_obj.watchlistedAt > 0:
            return datetime.datetime.fromtimestamp(media_obj.watchlistedAt).isoformat()
        elif isinstance(media_obj.watchlistedAt, str) and media_obj.watchlistedAt.strip() != "":
            return media_obj.watchlistedAt
    return None


def _compute_key_guid(media_obj) -> Optional[str]:
    """Compute a stable key guid for a media object similar to update_db."""
    guid = getattr(media_obj, "guid", None)
    media_type = getattr(media_obj, "type", None)
    if guid is not None and str(guid).strip() != "":
        return str(guid)
    if getattr(media_obj, "ratingKey", None):
        return f"plex://{str(media_type)}/{str(media_obj.ratingKey)}"
    if getattr(media_obj, "key", None):
        return media_obj.key
    return None


def _count_collected_episodes(media_obj, library_list) -> int:
    """Best-effort collected-episode count for a show media object."""
    try:
        leaf_count = int(getattr(media_obj, "leafCount", 0) or 0)
    except Exception:
        leaf_count = 0
    try:
        if callable(getattr(media_obj, "uncollected", None)):
            uncollected = media_obj.uncollected(library_list)
            if isinstance(uncollected, list):
                return max(0, leaf_count - len(uncollected))
    except Exception:
        pass
    # Fallback: explicit episode checks if available
    count = 0
    try:
        for season in getattr(media_obj, "Seasons", []) or []:
            for episode in getattr(season, "Episodes", []) or []:
                try:
                    if callable(getattr(episode, "collected", None)) and episode.collected(library_list):
                        count += 1
                except Exception:
                    continue
    except Exception:
        pass
    return count


def upsert_release(media_obj, release, downloaded: bool = False) -> None:
    """Upsert a release row for the given media item.

    Args:
        media_obj: The media object (movie/episode) the release belongs to.
        release: A release instance from releases.release with attributes.
        downloaded: Whether this release has been downloaded.
    """
    try:
        conn = _get_connection()
        key_guid = _compute_key_guid(media_obj)
        if key_guid is None:
            return
        title = getattr(release, 'title', None)
        try:
            size = float(getattr(release, 'size', 0) or 0)
        except Exception:
            size = None
        link = None
        dl = getattr(release, 'download', None)
        if isinstance(dl, list) and len(dl) > 0:
            link = str(dl[0])
        hash_value = getattr(release, 'hash', None)
        try:
            seeders = int(getattr(release, 'seeders', 0) or 0)
        except Exception:
            seeders = None
        source = getattr(release, 'source', None)
        
        # Determine status based on downloaded flag
        status = 'downloaded' if downloaded else 'pending'

        conn.execute(
            """
            INSERT INTO media_release (
                guid, title, size, link, hash, seeders, source, status, requested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guid, hash) DO UPDATE SET
                title=excluded.title,
                size=excluded.size,
                link=excluded.link,
                seeders=excluded.seeders,
                source=excluded.source,
                status=CASE 
                    WHEN excluded.status = 'downloaded' THEN 'downloaded'
                    WHEN media_release.status = 'downloaded' THEN 'downloaded'
                    ELSE excluded.status
                END,
                updated_at=datetime('now')
            """,
            (
                key_guid,
                None if title is None else str(title),
                size,
                None if link is None else str(link),
                None if hash_value is None else str(hash_value),
                seeders,
                None if source is None else str(source),
                status,
                None,  # requested_at - default to None for auto-discovered releases
            ),
        )
        conn.commit()
    except Exception as e:
        print("[sqlite] error: couldnt upsert release: " + str(e))


def mark_release_downloaded(media_obj, release) -> None:
    """Mark an existing or new release as downloaded for a media item."""
    try:
        conn = _get_connection()
        key_guid = _compute_key_guid(media_obj)
        if key_guid is None:
            return
        hash_value = getattr(release, 'hash', None)
        if hash_value is None:
            return
        
        # Update the status to downloaded
        conn.execute(
            "UPDATE media_release SET status = 'downloaded', updated_at = datetime('now') WHERE guid = ? AND hash = ?",
            (key_guid, str(hash_value))
        )
        conn.commit()
    except Exception as e:
        print("[sqlite] error: couldnt mark release as downloaded: " + str(e))


def is_release_at_status(media_obj, release, statuses) -> bool:
    """Check if a release has any of the specified statuses in the database.
    
    Args:
        media_obj: The media object (movie/episode) the release belongs to.
        release: A release instance from releases.release with attributes.
        statuses: A string or list of strings representing the status(es) to check for.
        
    Returns:
        True if the release has any of the specified statuses, False otherwise.
    """
    try:
        conn = _get_connection()
        key_guid = _compute_key_guid(media_obj)
        if key_guid is None:
            return False
        hash_value = getattr(release, 'hash', None)
        if hash_value is None:
            return False
        
        # Normalize statuses to a list
        if isinstance(statuses, str):
            statuses = [statuses]
        
        # Query the database for the release status
        cursor = conn.execute(
            "SELECT status FROM media_release WHERE guid = ? AND hash = ?",
            (key_guid, str(hash_value))
        )
        result = cursor.fetchone()
        
        # Return True if the release has any of the specified statuses
        return result and result[0] in statuses
        
    except Exception as e:
        print("[sqlite] error: couldnt check release status: " + str(e))
        return False


def is_media_blacklisted(media_obj) -> bool:
    """Check if a media item (movie, show, season, or episode) is blacklisted in the database.
    
    Args:
        media_obj: The media object to check (movie, show, season, or episode).
        
    Returns:
        True if the media item is blacklisted, False otherwise.
    """
    try:
        conn = _get_connection()
        key_guid = _compute_key_guid(media_obj)
        if key_guid is None:
            return False
        
        media_type = getattr(media_obj, 'type', None)
        if media_type is None:
            return False
        
        # Map media type to table name
        table_map = {
            'movie': 'media_movie',
            'show': 'media_show',
            'season': 'media_season',
            'episode': 'media_episode'
        }
        
        table_name = table_map.get(media_type)
        if table_name is None:
            return False
        
        # Query the database for blacklisted status
        cursor = conn.execute(
            f"SELECT blacklisted FROM {table_name} WHERE guid = ?",
            (key_guid,)
        )
        result = cursor.fetchone()
        
        # Return True if blacklisted = 1
        return result is not None and result[0] == 1
        
    except Exception as e:
        print("[sqlite] error: couldnt check blacklisted status: " + str(e))
        return False


def update_db(media_obj, library_list, source=None) -> None:
    """Upsert current media status for movies, shows, seasons, and episodes.

    Movies: upsert into media_movie (with imdb/tmdb/tvdb, booleans, ignored).
    Shows: upsert into media_show (with booleans).
    Seasons: upsert into media_season.
    Episodes: upsert into media_episode.

    If guid is missing, we fall back to the first available id among imdb/tmdb/tvdb or a title|year composite.
    """
    try:
        guid = getattr(media_obj, "guid", None)
        title = getattr(media_obj, "title", None)
        year = getattr(media_obj, "year", None)
        media_type = getattr(media_obj, "type", None)

        # Extract watchlisted_by from user attribute
        watchlisted_by = ""
        if hasattr(media_obj, "user") and isinstance(media_obj.user, list):
            # user is a list of lists, where each inner list is [username, token]
            usernames = []
            for user_entry in media_obj.user:
                if isinstance(user_entry, list) and len(user_entry) > 0:
                    usernames.append(str(user_entry[0]))  # username is first element
            watchlisted_by = ",".join(usernames)

        # Extract ids for imdb/tmdb/tvdb from any available EID lists
        eid_list = []
        if hasattr(media_obj, "EID") and isinstance(media_obj.EID, list):
            eid_list = media_obj.EID
        elif hasattr(media_obj, "parentEID") and isinstance(media_obj.parentEID, list):
            eid_list = media_obj.parentEID
        elif hasattr(media_obj, "grandparentEID") and isinstance(media_obj.grandparentEID, list):
            eid_list = media_obj.grandparentEID

        imdb_id = None
        tmdb_id = None
        tvdb_id = None
        for eid in eid_list:
            try:
                service, value = str(eid).split('://', 1)
                if service == 'imdb' and imdb_id is None:
                    imdb_id = value
                elif service == 'tmdb' and tmdb_id is None:
                    tmdb_id = value
                elif service == 'tvdb' and tvdb_id is None:
                    tvdb_id = value
            except Exception:
                continue

        # Compute booleans using existing helpers
        released = 1 if callable(getattr(media_obj, "released", None)) and media_obj.released() else 0
        collected = 1 if callable(getattr(media_obj, "collected", None)) and media_obj.collected(library_list) else 0
        watched = 1 if callable(getattr(media_obj, "watched", None)) and media_obj.watched() else 0
        downloading = 1 if callable(getattr(media_obj, "downloading", None)) and media_obj.downloading() else 0

        # Ignored flag: whether the item is currently in the global ignored list
        try:
            from content import classes as content_classes
            ignored = 1 if any(media_obj == x for x in content_classes.ignore.ignored) else 0
        except Exception:
            ignored = 0

        # Determine source if not provided
        if source is None:
            try:
                if hasattr(media_obj, 'watchlist') and hasattr(media_obj.watchlist, '__module__'):
                    source = media_obj.watchlist.__module__.split('.')[-1]
                else:
                    source = 'plex'  # Default fallback
            except Exception:
                source = 'plex'  # Default fallback

        # Determine unique key
        key_guid = None
        if guid is not None and str(guid).strip() != "":
            key_guid = str(guid)
        elif getattr(media_obj, "ratingKey", None):
            key_guid = f"plex://{str(media_type)}/{str(media_obj.ratingKey)}"
        elif getattr(media_obj, "key", None):
            key_guid = media_obj.key
        else:
            print(f"[sqlite] error: couldnt determine key for {media_type}: {title} ({year})")
            return

        conn = _get_connection()
        if media_type == 'movie':
            conn.execute(
            """
            INSERT INTO media_movie (
                guid, title, year, imdb, tmdb, tvdb, released, collected, watched, downloading, ignored, watchlisted_by, watchlisted_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guid) DO UPDATE SET
                title=excluded.title,
                year=excluded.year,
                imdb=excluded.imdb,
                tmdb=excluded.tmdb,
                tvdb=excluded.tvdb,
                released=excluded.released,
                collected=excluded.collected,
                watched=excluded.watched,
                downloading=excluded.downloading,
                ignored=excluded.ignored,
                watchlisted_by=excluded.watchlisted_by,
                watchlisted_at=excluded.watchlisted_at,
                source=excluded.source,
                updated_at=datetime('now')
            """,
                (
                    key_guid,
                    None if title is None else str(title),
                    None if year is None else int(year),
                    None if imdb_id is None else str(imdb_id),
                    None if tmdb_id is None else str(tmdb_id),
                    None if tvdb_id is None else str(tvdb_id),
                    released,
                    collected,
                    watched,
                    downloading,
                    ignored,
                    watchlisted_by,
                    _convert_watchlisted_at(media_obj),
                    source,
                ),
            )
        elif media_type == 'show':
            collected_episode_count = _count_collected_episodes(media_obj, library_list)
            now_iso = datetime.datetime.utcnow().isoformat()
            prev_count = None
            prev_progress_at = None
            try:
                row = conn.execute(
                    "SELECT collected_episode_count, last_collection_progress_at FROM media_show WHERE guid = ?",
                    (key_guid,),
                ).fetchone()
                if row:
                    prev_count, prev_progress_at = row[0], row[1]
            except Exception:
                pass
            if prev_count is None:
                progress_at = now_iso
            elif collected_episode_count > int(prev_count or 0):
                progress_at = now_iso
            else:
                progress_at = prev_progress_at or now_iso
            conn.execute(
                """
                INSERT INTO media_show (
                    guid, leaf_count, child_count, collected_episode_count, last_collection_progress_at, title, year, watchlisted_at, public_pages_url, imdb, tmdb, tvdb, released, collected, watched, ignored, watchlisted_by, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    leaf_count=excluded.leaf_count,
                    child_count=excluded.child_count,
                    collected_episode_count=excluded.collected_episode_count,
                    last_collection_progress_at=excluded.last_collection_progress_at,
                    title=excluded.title,
                    year=excluded.year,
                    watchlisted_at=excluded.watchlisted_at,
                    public_pages_url=excluded.public_pages_url,
                    imdb=excluded.imdb,
                    tmdb=excluded.tmdb,
                    tvdb=excluded.tvdb,
                    released=excluded.released,
                    collected=excluded.collected,
                    watched=excluded.watched,
                    ignored=excluded.ignored,
                    watchlisted_by=excluded.watchlisted_by,
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                (
                    key_guid,
                    getattr(media_obj, 'leafCount', None),
                    getattr(media_obj, 'childCount', None),
                    collected_episode_count,
                    progress_at,
                    None if title is None else str(title),
                    None if year is None else int(year),
                    _convert_watchlisted_at(media_obj),
                    getattr(media_obj, 'publicPagesURL', None),
                    None if imdb_id is None else str(imdb_id),
                    None if tmdb_id is None else str(tmdb_id),
                    None if tvdb_id is None else str(tvdb_id),
                    released,
                    collected,
                    watched,
                    ignored,
                    watchlisted_by,
                    source,
                ),
            )
        elif media_type == 'season':
            # Determine season year
            season_year = getattr(media_obj, 'year', None)
            if season_year is None:
                season_year = getattr(media_obj, 'parentYear', None)
            conn.execute(
                """
                INSERT INTO media_season (
                    guid, parent_title, title, parent_guid, year, leaf_count, idx, collected, ignored, watchlisted_by, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    parent_title=excluded.parent_title,
                    title=excluded.title,
                    parent_guid=excluded.parent_guid,
                    year=excluded.year,
                    leaf_count=excluded.leaf_count,
                    idx=excluded.idx,
                    collected=excluded.collected,
                    ignored=excluded.ignored,
                    watchlisted_by=excluded.watchlisted_by,
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                (
                    key_guid,
                    getattr(media_obj, 'parentTitle', None),
                    getattr(media_obj, 'title', None),
                    getattr(media_obj, 'parentGuid', None),
                    season_year,
                    getattr(media_obj, 'leafCount', None),
                    getattr(media_obj, 'index', None),
                    collected,
                    ignored,
                    watchlisted_by,
                    source,
                ),
            )
        elif media_type == 'episode':
            # Determine episode year
            episode_year = getattr(media_obj, 'year', None)
            if episode_year is None:
                episode_year = getattr(media_obj, 'grandparentYear', None)
            downloading_flag = 1 if callable(getattr(media_obj, 'downloading', None)) and media_obj.downloading() else 0
            conn.execute(
                """
                INSERT INTO media_episode (
                    guid, grandparent_title, parent_title, title, parent_guid, parent_index, idx, year, collected, downloading, ignored, watchlisted_by, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    grandparent_title=excluded.grandparent_title,
                    parent_title=excluded.parent_title,
                    title=excluded.title,
                    parent_guid=excluded.parent_guid,
                    parent_index=excluded.parent_index,
                    idx=excluded.idx,
                    year=excluded.year,
                    collected=excluded.collected,
                    downloading=excluded.downloading,
                    ignored=excluded.ignored,
                    watchlisted_by=excluded.watchlisted_by,
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                (
                    key_guid,
                    getattr(media_obj, 'grandparentTitle', None),
                    getattr(media_obj, 'parentTitle', None),
                    getattr(media_obj, 'title', None),
                    getattr(media_obj, 'parentGuid', None),
                    getattr(media_obj, 'parentIndex', None),
                    getattr(media_obj, 'index', None),
                    episode_year,
                    collected,
                    downloading_flag,
                    ignored,
                    watchlisted_by,
                    source,
                ),
            )
        conn.commit()
    except Exception as e:
        # Log via ui_print if available; otherwise ignore
        print("[sqlite] error: couldnt update database: " + str(e))


def get_show_inactivity_days(media_obj) -> Optional[int]:
    """Return days since last collection progress for a show, or None if unknown."""
    try:
        if getattr(media_obj, "type", None) != "show":
            return None
        key_guid = _compute_key_guid(media_obj)
        if key_guid is None:
            return None
        conn = _get_connection()
        row = conn.execute(
            "SELECT last_collection_progress_at FROM media_show WHERE guid = ?",
            (key_guid,),
        ).fetchone()
        if not row or not row[0]:
            return None
        s = str(row[0])
        dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(s.split("+")[0].split("Z")[0], fmt)
                break
            except Exception:
                continue
        if dt is None:
            return None
        return max(0, (datetime.datetime.utcnow() - dt).days)
    except Exception:
        return None

