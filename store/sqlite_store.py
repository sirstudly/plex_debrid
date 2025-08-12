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
    """Initialize the SQLite database and ensure the media tables exist.

    Args:
        db_dir: Directory to place the database file. Defaults to './store'.
        filename: Database filename. Defaults to 'plex_debrid.sqlite3'.

    Returns:
        The absolute path to the database file.
    """
    global _connection, _db_path

    if db_dir is None:
        db_dir = os.path.join(".", "store")

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
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media_movie (
                guid TEXT PRIMARY KEY,
                title TEXT,
                year INTEGER,
                imdb TEXT,
                tmdb TEXT,
                tvdb TEXT,
                released INTEGER,
                collected INTEGER,
                watched INTEGER,
                downloading INTEGER,
                ignored INTEGER,
                watchlisted_by TEXT,
                watchlisted_at TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media_show (
                guid TEXT PRIMARY KEY,
                leaf_count INTEGER,
                child_count INTEGER,
                title TEXT,
                year INTEGER,
                public_pages_url TEXT,
                imdb TEXT,
                tmdb TEXT,
                tvdb TEXT,
                released INTEGER,
                collected INTEGER,
                watched INTEGER,
                ignored INTEGER,
                watchlisted_by TEXT,
                watchlisted_at TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media_season (
                guid TEXT PRIMARY KEY,
                parent_title TEXT,
                title TEXT,
                parent_guid TEXT,
                year INTEGER,
                leaf_count INTEGER,
                idx INTEGER,
                collected INTEGER,
                ignored INTEGER,
                watchlisted_by TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media_episode (
                guid TEXT PRIMARY KEY,
                grandparent_title TEXT,
                parent_title TEXT,
                title TEXT,
                parent_guid TEXT,
                parent_index INTEGER,
                idx INTEGER,
                year INTEGER,
                collected INTEGER,
                downloading INTEGER,
                ignored INTEGER,
                watchlisted_by TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media_release (
                guid TEXT NOT NULL,
                title TEXT,
                size REAL,
                link TEXT,
                hash TEXT,
                seeders INTEGER,
                source TEXT,
                downloaded INTEGER,
                blacklisted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (guid, hash)
            )
            """
        )
        # No additional indices required currently
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
        downloaded_int = 1 if downloaded else 0

        conn.execute(
            """
            INSERT INTO media_release (
                guid, title, size, link, hash, seeders, source, downloaded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guid, hash) DO UPDATE SET
                title=excluded.title,
                size=excluded.size,
                link=excluded.link,
                seeders=excluded.seeders,
                source=excluded.source,
                downloaded=MAX(media_release.downloaded, excluded.downloaded),
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
                downloaded_int,
            ),
        )
        conn.commit()
    except Exception as e:
        print("[sqlite] error: couldnt upsert release: " + str(e))


def mark_release_downloaded(media_obj, release) -> None:
    """Mark an existing or new release as downloaded for a media item."""
    upsert_release(media_obj, release, downloaded=True)


def update_db(media_obj, library_list) -> None:
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
                guid, title, year, imdb, tmdb, tvdb, released, collected, watched, downloading, ignored, watchlisted_by, watchlisted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        elif media_type == 'show':
            conn.execute(
                """
                INSERT INTO media_show (
                    guid, leaf_count, child_count, title, year, watchlisted_at, public_pages_url, imdb, tmdb, tvdb, released, collected, watched, ignored, watchlisted_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    leaf_count=excluded.leaf_count,
                    child_count=excluded.child_count,
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
                    updated_at=datetime('now')
                """,
                (
                    key_guid,
                    getattr(media_obj, 'leafCount', None),
                    getattr(media_obj, 'childCount', None),
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
                    guid, parent_title, title, parent_guid, year, leaf_count, idx, collected, ignored, watchlisted_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    guid, grandparent_title, parent_title, title, parent_guid, parent_index, idx, year, collected, downloading, ignored, watchlisted_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        conn.commit()
    except Exception as e:
        # Log via ui_print if available; otherwise ignore
        print("[sqlite] error: couldnt update database: " + str(e))

