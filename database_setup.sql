-- Plex Debrid Database Setup
-- This script creates all necessary tables and views for the web interface

-- ============================================================================
-- TABLE CREATION
-- ============================================================================

-- Movies table
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
    source TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Shows table
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
    source TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seasons table
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
    source TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Episodes table
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
    source TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Releases table
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
);

-- ============================================================================
-- VIEW CREATION
-- ============================================================================

-- Drop existing views if they exist
DROP VIEW IF EXISTS v_media;

-- Create comprehensive media view with all items and their status
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
    watchlisted_at,
    source,
    updated_at,
    CASE 
        WHEN collected = 1 THEN 'collected'
        WHEN ignored = 1 THEN 'ignored'
        WHEN downloading = 1 THEN 'downloading'
        ELSE 'pending'
    END as status,
    collected,
    ignored,
    downloading
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
    watchlisted_at,
    source,
    updated_at,
    CASE 
        WHEN collected = 1 THEN 'collected'
        WHEN ignored = 1 THEN 'ignored'
        ELSE 'pending'
    END as status,
    collected,
    ignored,
    0 as downloading
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
    updated_at as watchlisted_at,
    source,
    updated_at,
    CASE 
        WHEN collected = 1 THEN 'collected'
        WHEN ignored = 1 THEN 'ignored'
        ELSE 'pending'
    END as status,
    collected,
    ignored,
    0 as downloading
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
    updated_at as watchlisted_at,
    source,
    updated_at,
    CASE 
        WHEN collected = 1 THEN 'collected'
        WHEN ignored = 1 THEN 'ignored'
        WHEN downloading = 1 THEN 'downloading'
        ELSE 'pending'
    END as status,
    collected,
    ignored,
    downloading
FROM media_episode;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Create indexes on commonly queried columns
CREATE INDEX IF NOT EXISTS idx_media_movie_status ON media_movie(collected, ignored, downloading);
CREATE INDEX IF NOT EXISTS idx_media_movie_year ON media_movie(year);
CREATE INDEX IF NOT EXISTS idx_media_movie_watchlisted_by ON media_movie(watchlisted_by);
CREATE INDEX IF NOT EXISTS idx_media_movie_watchlisted_at ON media_movie(watchlisted_at);
CREATE INDEX IF NOT EXISTS idx_media_movie_source ON media_movie(source);

CREATE INDEX IF NOT EXISTS idx_media_show_status ON media_show(collected, ignored);
CREATE INDEX IF NOT EXISTS idx_media_show_year ON media_show(year);
CREATE INDEX IF NOT EXISTS idx_media_show_watchlisted_by ON media_show(watchlisted_by);
CREATE INDEX IF NOT EXISTS idx_media_show_watchlisted_at ON media_show(watchlisted_at);
CREATE INDEX IF NOT EXISTS idx_media_show_source ON media_show(source);

CREATE INDEX IF NOT EXISTS idx_media_season_status ON media_season(collected, ignored);
CREATE INDEX IF NOT EXISTS idx_media_season_year ON media_season(year);
CREATE INDEX IF NOT EXISTS idx_media_season_watchlisted_by ON media_season(watchlisted_by);
CREATE INDEX IF NOT EXISTS idx_media_season_updated_at ON media_season(updated_at);
CREATE INDEX IF NOT EXISTS idx_media_season_source ON media_season(source);

CREATE INDEX IF NOT EXISTS idx_media_episode_status ON media_episode(collected, ignored, downloading);
CREATE INDEX IF NOT EXISTS idx_media_episode_year ON media_episode(year);
CREATE INDEX IF NOT EXISTS idx_media_episode_watchlisted_by ON media_episode(watchlisted_by);
CREATE INDEX IF NOT EXISTS idx_media_episode_updated_at ON media_episode(updated_at);
CREATE INDEX IF NOT EXISTS idx_media_episode_source ON media_episode(source);

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================

-- Example queries for the web interface:
-- 
-- Get all pending items:
-- SELECT * FROM v_media WHERE status = 'pending';
--
-- Get pending movies only:
-- SELECT * FROM v_media WHERE status = 'pending' AND media_type = 'movie';
--
-- Get pending seasons only:
-- SELECT * FROM v_media WHERE status = 'pending' AND media_type = 'season';
--
-- Get downloading items:
-- SELECT * FROM v_media WHERE status = 'downloading';
--
-- Get ignored items:
-- SELECT * FROM v_media WHERE status = 'ignored';
--
-- Get collected items:
-- SELECT * FROM v_media WHERE status = 'collected';
--
-- Get items by source:
-- SELECT * FROM v_media WHERE watchlisted_by LIKE '%plex%';
--
-- Get items by year:
-- SELECT * FROM v_media WHERE year = 2024;
--
-- Get items by search term:
-- SELECT * FROM v_media WHERE title LIKE '%search_term%';
--
-- Get statistics:
-- SELECT 
--     SUM(CASE WHEN status = 'pending' AND media_type = 'movie' THEN 1 ELSE 0 END) as pending_movies,
--     SUM(CASE WHEN status = 'pending' AND media_type = 'show' THEN 1 ELSE 0 END) as pending_shows,
--     SUM(CASE WHEN status = 'pending' AND media_type = 'season' THEN 1 ELSE 0 END) as pending_seasons,
--     SUM(CASE WHEN status = 'pending' AND media_type = 'episode' THEN 1 ELSE 0 END) as pending_episodes
-- FROM v_media;
