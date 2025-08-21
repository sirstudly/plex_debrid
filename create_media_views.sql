-- Plex Debrid Media Views
-- This script creates views to simplify the web interface queries

-- Drop existing views if they exist
DROP VIEW IF EXISTS v_media;
DROP VIEW IF EXISTS v_pending_items;
DROP VIEW IF EXISTS v_downloading_items;
DROP VIEW IF EXISTS v_ignored_items;

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

-- Episodes with status
SELECT 
    'episode' as media_type,
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

-- Create indexes on the view for better performance
-- Note: SQLite doesn't support indexes on views, but the underlying tables should have indexes

-- Example usage queries:
-- 
-- Get all pending items:
-- SELECT * FROM v_media WHERE status = 'pending';
--
-- Get pending movies only:
-- SELECT * FROM v_media WHERE status = 'pending' AND media_type = 'movie';
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
