#!/usr/bin/env python3
"""
Test script for the Plex Debrid Web Interface
"""

import sys
import os

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from web.app import app
        print("✓ Web app imports successfully")
    except Exception as e:
        print(f"✗ Web app import failed: {e}")
        return False
    
    try:
        from web.routes.api import router
        print("✓ API routes import successfully")
    except Exception as e:
        print(f"✗ API routes import failed: {e}")
        return False
    
    try:
        from web.routes.static import router as static_router
        print("✓ Static routes import successfully")
    except Exception as e:
        print(f"✗ Static routes import failed: {e}")
        return False
    
    return True

def test_database_connection():
    """Test database connection"""
    print("\nTesting database connection...")
    
    try:
        from store.sqlite_store import _get_connection
        conn = _get_connection()
        print("✓ Database connection successful")
        
        # Test if tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'media_%'")
        tables = cursor.fetchall()
        print(f"✓ Found {len(tables)} media tables: {[table[0] for table in tables]}")
        
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_api_endpoints():
    """Test that API endpoints can be created"""
    print("\nTesting API endpoints...")
    
    try:
        from web.routes.api import router
        routes = [route for route in router.routes]
        print(f"✓ Found {len(routes)} API routes")
        
        # Check for specific endpoints
        endpoint_paths = [route.path for route in routes]
        expected_endpoints = ['/pending', '/pending/movies', '/pending/shows', '/pending/episodes', '/downloading', '/ignored', '/stats']
        
        for endpoint in expected_endpoints:
            if endpoint in endpoint_paths:
                print(f"✓ Found endpoint: {endpoint}")
            else:
                print(f"✗ Missing endpoint: {endpoint}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ API endpoints test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Plex Debrid Web Interface Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_database_connection,
        test_api_endpoints
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! Web interface is ready to use.")
        print("\nTo start the web server:")
        print("1. Activate your virtual environment: source venv_3.12/bin/activate")
        print("2. Run: python web_server.py")
        print("3. Open: http://127.0.0.1:8008/dashboard")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
