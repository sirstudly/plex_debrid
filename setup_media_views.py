#!/usr/bin/env python3
"""
Setup Media Views for Plex Debrid Web Interface

This script creates database views to simplify queries for the web interface.
"""

import os
import sys
import sqlite3

# Add the parent directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.sqlite_store import _get_connection

def setup_media_views():
    """Create the media views in the database and test them"""
    
    # Read the SQL script
    script_path = os.path.join(os.path.dirname(__file__), 'create_media_views.sql')
    
    try:
        with open(script_path, 'r') as f:
            sql_script = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {script_path}")
        return False
    
    # Get database connection
    try:
        conn = _get_connection()
        print("✓ Connected to database successfully")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False
    
    try:
        # Execute the SQL script
        conn.executescript(sql_script)
        conn.commit()
        print("✓ Media views created successfully")
        
        # Test the view
        cursor = conn.execute("SELECT COUNT(*) FROM v_media")
        total_count = cursor.fetchone()[0]
        print(f"✓ View contains {total_count} total items")
        
        # Test different statuses
        statuses = ['pending', 'downloading', 'ignored', 'collected']
        for status in statuses:
            cursor = conn.execute(f"SELECT COUNT(*) FROM v_media WHERE status = ?", (status,))
            count = cursor.fetchone()[0]
            print(f"  - {status}: {count} items")
        
        # Test media types
        types = ['movie', 'show', 'episode']
        for media_type in types:
            cursor = conn.execute(f"SELECT COUNT(*) FROM v_media WHERE media_type = ?", (media_type,))
            count = cursor.fetchone()[0]
            print(f"  - {media_type}: {count} items")
        
        print("\n✓ All tests passed! The view is ready to use.")
        
        # Test additional queries
        print("\n--- Testing View Queries ---")
        
        # Test 1: Get pending movies
        cursor = conn.execute("""
            SELECT title, year, watchlisted_by 
            FROM v_media 
            WHERE status = 'pending' AND media_type = 'movie' 
            LIMIT 5
        """)
        pending_movies = cursor.fetchall()
        print(f"✓ Pending movies (first 5): {len(pending_movies)} found")
        
        # Test 2: Get downloading items
        cursor = conn.execute("""
            SELECT media_type, title, watchlisted_by 
            FROM v_media 
            WHERE status = 'downloading' 
            LIMIT 5
        """)
        downloading = cursor.fetchall()
        print(f"✓ Downloading items: {len(downloading)} found")
        
        # Test 3: Get items by source
        cursor = conn.execute("""
            SELECT COUNT(*) 
            FROM v_media 
            WHERE watchlisted_by LIKE '%plex%'
        """)
        plex_count = cursor.fetchone()[0]
        print(f"✓ Items from Plex: {plex_count}")
        
        # Test 4: Get items by year
        cursor = conn.execute("""
            SELECT COUNT(*) 
            FROM v_media 
            WHERE year = 2024
        """)
        year_2024_count = cursor.fetchone()[0]
        print(f"✓ Items from 2024: {year_2024_count}")
        
        print("✓ All view queries working correctly!")
        return True
        
    except Exception as e:
        print(f"✗ Error creating views: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Plex Debrid Media Views Setup")
    print("=" * 40)
    
    # Setup the views
    if not setup_media_views():
        print("\n✗ Failed to setup media views")
        sys.exit(1)
    
    print("\n🎉 Media views setup completed successfully!")
    print("\nYou can now use the simplified API endpoints:")
    print("- GET /api/pending?status=pending")
    print("- GET /api/downloading?status=downloading")
    print("- GET /api/ignored?status=ignored")
    print("- GET /api/media?status=pending&media_type=movie")

if __name__ == "__main__":
    main()
