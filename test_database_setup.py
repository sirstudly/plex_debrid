#!/usr/bin/env python3
"""
Test Database Setup for Plex Debrid

This script verifies that the database setup is working correctly.
"""

import os
import sys
import sqlite3

# Add the parent directory to the path so we can import from the main project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from store.sqlite_store import _get_connection, init_db

def test_database_setup():
    """Test that the database setup is working correctly"""
    
    print("Testing Database Setup")
    print("=" * 40)
    
    try:
        # Initialize database (this should run the setup script)
        db_path = init_db()
        print(f"✓ Database initialized at: {db_path}")
        
        # Get connection
        conn = _get_connection()
        print("✓ Database connection successful")
        
        # Test that all tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'media_%'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        expected_tables = ['media_movie', 'media_show', 'media_season', 'media_episode', 'media_release']
        missing_tables = [table for table in expected_tables if table not in table_names]
        
        if missing_tables:
            print(f"✗ Missing tables: {missing_tables}")
            return False
        else:
            print(f"✓ All expected tables found: {table_names}")
        
        # Test that the view exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='v_media'")
        views = cursor.fetchall()
        
        if not views:
            print("✗ v_media view not found")
            return False
        else:
            print("✓ v_media view found")
        
        # Test that the view works
        cursor = conn.execute("SELECT COUNT(*) FROM v_media")
        total_count = cursor.fetchone()[0]
        print(f"✓ v_media view contains {total_count} items")
        
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
        
        # Test that indexes exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        index_names = [index[0] for index in indexes]
        
        if index_names:
            print(f"✓ Found {len(index_names)} performance indexes")
        else:
            print("⚠ No performance indexes found (this is okay for small datasets)")
        
        print("\n✓ All database setup tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Database setup test failed: {e}")
        return False

def test_api_compatibility():
    """Test that the API can still work with the new setup"""
    
    print("\n--- Testing API Compatibility ---")
    
    try:
        import requests
        
        # Test health endpoint
        response = requests.get("http://localhost:8008/health")
        if response.status_code == 200:
            print("✓ Health endpoint working")
        else:
            print("✗ Health endpoint failed")
            return False
        
        # Test stats endpoint
        response = requests.get("http://localhost:8008/api/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Stats endpoint working - {stats['pending']['total']} pending items")
        else:
            print("✗ Stats endpoint failed")
            return False
        
        # Test pending endpoint
        response = requests.get("http://localhost:8008/api/pending?page_size=3")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Pending endpoint working - {len(data['items'])} items returned")
        else:
            print("✗ Pending endpoint failed")
            return False
        
        print("✓ All API compatibility tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ API compatibility test failed: {e}")
        return False

def main():
    """Main function"""
    print("Plex Debrid Database Setup Test")
    print("=" * 50)
    
    # Test database setup
    if not test_database_setup():
        print("\n✗ Database setup tests failed")
        sys.exit(1)
    
    # Test API compatibility
    if not test_api_compatibility():
        print("\n✗ API compatibility tests failed")
        sys.exit(1)
    
    print("\n🎉 All tests passed! Database setup is working correctly.")
    print("\nBenefits of the new setup:")
    print("  - Single consolidated SQL setup file")
    print("  - Automatic database initialization on startup")
    print("  - Performance indexes for better query speed")
    print("  - Unified v_media view for all queries")
    print("  - Simplified maintenance and deployment")

if __name__ == "__main__":
    main()
