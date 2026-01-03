#!/usr/bin/env python3
"""
Migration Script: Add blacklisted column to media tables

This script safely adds the blacklisted column to existing Plex Debrid databases.
It is idempotent and can be run multiple times safely.

Usage:
    python migrate_add_blacklisted_column.py [db_path]

If db_path is not provided, it will use the default database location from sqlite_store.
"""

import os
import sys
import sqlite3

# Add the parent directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from store.sqlite_store import _get_connection, _db_path
except ImportError:
    _db_path = None
    _get_connection = None


def column_exists(conn, table_name, column_name):
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_blacklisted_column(conn, table_name):
    """Add blacklisted column to a table if it doesn't exist."""
    if not column_exists(conn, table_name, 'blacklisted'):
        print(f"  Adding blacklisted column to {table_name}...")
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN blacklisted INTEGER DEFAULT 0")
        return True
    else:
        print(f"  Column 'blacklisted' already exists in {table_name}, skipping...")
        return False


def recreate_v_media_view(conn):
    """Recreate the v_media view with blacklisted status support."""
    print("  Recreating v_media view...")
    conn.execute("DROP VIEW IF EXISTS v_media")
    
    view_sql = """
    CREATE VIEW v_media AS
    -- Movies with status
    SELECT 
        'movie' as media_type,
        guid,
        title,
        year,
        imdb,
        tmdb,
        tvdb,
        watchlisted_by,
        COALESCE(datetime(watchlisted_at), datetime('1970-01-01')) as watchlisted_at,
        source,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as updated_at,
        CASE 
            WHEN blacklisted = 1 THEN 'blacklisted'
            WHEN collected = 1 THEN 'collected'
            WHEN ignored = 1 THEN 'ignored'
            WHEN downloading = 1 THEN 'downloading'
            ELSE 'pending'
        END as status,
        collected,
        ignored,
        downloading,
        blacklisted
    FROM media_movie

    UNION ALL

    -- Shows with status
    SELECT 
        'show' as media_type,
        guid,
        title,
        year,
        imdb,
        tmdb,
        tvdb,
        watchlisted_by,
        COALESCE(datetime(watchlisted_at), datetime('1970-01-01')) as watchlisted_at,
        source,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as updated_at,
        CASE 
            WHEN blacklisted = 1 THEN 'blacklisted'
            WHEN collected = 1 THEN 'collected'
            WHEN ignored = 1 THEN 'ignored'
            ELSE 'pending'
        END as status,
        collected,
        ignored,
        0 as downloading,
        blacklisted
    FROM media_show

    UNION ALL

    -- Seasons with status
    SELECT 
        'season' as media_type,
        guid,
        CASE 
            WHEN parent_title IS NOT NULL AND parent_title != '' 
            THEN title || ' (' || parent_title || ')'
            ELSE title 
        END as title,
        year,
        NULL as imdb,
        NULL as tmdb,
        NULL as tvdb,
        watchlisted_by,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as watchlisted_at,
        source,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as updated_at,
        CASE 
            WHEN blacklisted = 1 THEN 'blacklisted'
            WHEN collected = 1 THEN 'collected'
            WHEN ignored = 1 THEN 'ignored'
            ELSE 'pending'
        END as status,
        collected,
        ignored,
        0 as downloading,
        blacklisted
    FROM media_season

    UNION ALL

    -- Episodes with status
    SELECT 
        'episode' as media_type,
        guid,
        CASE 
            WHEN grandparent_title IS NOT NULL AND grandparent_title != '' AND parent_title IS NOT NULL AND parent_title != '' 
            THEN title || ' (' || grandparent_title || ' - ' || parent_title || ')'
            WHEN grandparent_title IS NOT NULL AND grandparent_title != '' 
            THEN title || ' (' || grandparent_title || ')'
            WHEN parent_title IS NOT NULL AND parent_title != '' 
            THEN title || ' (' || parent_title || ')'
            ELSE title 
        END as title,
        year,
        NULL as imdb,
        NULL as tmdb,
        NULL as tvdb,
        watchlisted_by,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as watchlisted_at,
        source,
        COALESCE(datetime(updated_at), datetime('1970-01-01')) as updated_at,
        CASE 
            WHEN blacklisted = 1 THEN 'blacklisted'
            WHEN collected = 1 THEN 'collected'
            WHEN ignored = 1 THEN 'ignored'
            WHEN downloading = 1 THEN 'downloading'
            ELSE 'pending'
        END as status,
        collected,
        ignored,
        downloading,
        blacklisted
    FROM media_episode
    """
    
    conn.execute(view_sql)


def add_indexes(conn):
    """Add indexes for blacklisted column if they don't exist."""
    print("  Adding indexes for blacklisted column...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_media_movie_blacklisted ON media_movie(blacklisted)",
        "CREATE INDEX IF NOT EXISTS idx_media_show_blacklisted ON media_show(blacklisted)",
        "CREATE INDEX IF NOT EXISTS idx_media_season_blacklisted ON media_season(blacklisted)",
        "CREATE INDEX IF NOT EXISTS idx_media_episode_blacklisted ON media_episode(blacklisted)"
    ]
    
    for index_sql in indexes:
        conn.execute(index_sql)


def run_migration(db_path=None):
    """Run the migration to add blacklisted column."""
    print("=" * 60)
    print("Plex Debrid Database Migration: Add blacklisted column")
    print("=" * 60)
    
    # Determine database path
    if db_path:
        db_file = os.path.abspath(db_path)
    elif _db_path:
        db_file = _db_path
    else:
        # Try to get from environment or use default
        db_dir = os.getenv('DB_DIR', './store')
        db_file = os.path.abspath(os.path.join(db_dir, 'plex_debrid.sqlite3'))
    
    if not os.path.exists(db_file):
        print(f"ERROR: Database file not found: {db_file}")
        print("Please provide the correct path to your database file.")
        return False
    
    print(f"Database: {db_file}")
    print()
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_file)
        conn.execute("BEGIN TRANSACTION")
        
        # Check if tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'media_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['media_movie', 'media_show', 'media_season', 'media_episode']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"ERROR: Required tables not found: {missing_tables}")
            conn.rollback()
            conn.close()
            return False
        
        print("Adding blacklisted column to media tables...")
        changes_made = False
        
        # Add blacklisted column to each table
        for table in required_tables:
            if add_blacklisted_column(conn, table):
                changes_made = True
        
        # Recreate v_media view (always do this to ensure it's up to date)
        recreate_v_media_view(conn)
        changes_made = True
        
        # Add indexes
        add_indexes(conn)
        
        # Commit changes
        conn.commit()
        print()
        print("✓ Migration completed successfully!")
        
        if not changes_made:
            print("  (No changes were needed - database already up to date)")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"ERROR: Database error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_migration(db_path)
    sys.exit(0 if success else 1)

