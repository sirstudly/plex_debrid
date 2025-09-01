#!/usr/bin/env python3
"""
Test the web interface with the simplified API
"""

import requests
import json
import sys

def test_api_endpoints():
    """Test all API endpoints"""
    base_url = "http://localhost:8008"
    
    print("Testing Web Interface with Simplified API")
    print("=" * 50)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health endpoint working")
        else:
            print("✗ Health endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Health endpoint error: {e}")
        return False
    
    # Test stats endpoint
    try:
        response = requests.get(f"{base_url}/api/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Stats endpoint working - {stats['pending']['total']} pending items")
        else:
            print("✗ Stats endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Stats endpoint error: {e}")
        return False
    
    # Test pending endpoint
    try:
        response = requests.get(f"{base_url}/api/pending?page_size=3")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Pending endpoint working - {len(data['items'])} items returned")
            if data['items']:
                first_item = data['items'][0]
                print(f"  - First item: {first_item['title']} ({first_item['media_type']}) - {first_item['status']}")
        else:
            print("✗ Pending endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Pending endpoint error: {e}")
        return False
    
    # Test filtering
    try:
        response = requests.get(f"{base_url}/api/pending?media_type=movie&page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Filtering working - {len(data['items'])} movie items returned")
        else:
            print("✗ Filtering failed")
            return False
    except Exception as e:
        print(f"✗ Filtering error: {e}")
        return False
    
    # Test search
    try:
        response = requests.get(f"{base_url}/api/pending?search=Predator&page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Search working - {len(data['items'])} items with 'Predator' found")
        else:
            print("✗ Search failed")
            return False
    except Exception as e:
        print(f"✗ Search error: {e}")
        return False
    
    # Test year filter
    try:
        response = requests.get(f"{base_url}/api/pending?year=2025&page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Year filter working - {len(data['items'])} items from 2025 found")
        else:
            print("✗ Year filter failed")
            return False
    except Exception as e:
        print(f"✗ Year filter error: {e}")
        return False
    
    # Test downloading endpoint
    try:
        response = requests.get(f"{base_url}/api/downloading?page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Downloading endpoint working - {len(data['items'])} items returned")
        else:
            print("✗ Downloading endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Downloading endpoint error: {e}")
        return False
    
    # Test ignored endpoint
    try:
        response = requests.get(f"{base_url}/api/ignored?page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Ignored endpoint working - {len(data['items'])} items returned")
        else:
            print("✗ Ignored endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Ignored endpoint error: {e}")
        return False
    
    # Test new /media endpoint
    try:
        response = requests.get(f"{base_url}/api/media?status=collected&page_size=2")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Media endpoint working - {len(data['items'])} collected items returned")
        else:
            print("✗ Media endpoint failed")
            return False
    except Exception as e:
        print(f"✗ Media endpoint error: {e}")
        return False
    
    print("\n🎉 All API endpoints working correctly!")
    return True

def test_data_structure():
    """Test that the data structure is consistent"""
    print("\n--- Testing Data Structure ---")
    
    try:
        response = requests.get("http://localhost:8008/api/pending?page_size=1")
        if response.status_code == 200:
            data = response.json()
            if data['items']:
                item = data['items'][0]
                required_fields = ['media_type', 'title', 'status', 'watchlisted_by', 'watchlisted_at']
                missing_fields = [field for field in required_fields if field not in item]
                
                if missing_fields:
                    print(f"✗ Missing fields: {missing_fields}")
                    return False
                else:
                    print("✓ All required fields present")
                    print(f"  - media_type: {item['media_type']}")
                    print(f"  - status: {item['status']}")
                    print(f"  - title: {item['title']}")
                    return True
            else:
                print("✗ No items returned")
                return False
        else:
            print("✗ API request failed")
            return False
    except Exception as e:
        print(f"✗ Data structure test error: {e}")
        return False

def main():
    """Main function"""
    print("Testing Web Interface with Simplified API")
    print("=" * 50)
    
    # Test API endpoints
    if not test_api_endpoints():
        print("\n✗ API endpoint tests failed")
        sys.exit(1)
    
    # Test data structure
    if not test_data_structure():
        print("\n✗ Data structure tests failed")
        sys.exit(1)
    
    print("\n🎉 All tests passed! The web interface is ready to use.")
    print("\nYou can now access the dashboard at:")
    print("  http://localhost:8008")
    print("\nFeatures available:")
    print("  - Real-time data from v_media view")
    print("  - Advanced filtering (type, status, source, year, search)")
    print("  - Pagination and sorting")
    print("  - Auto-refresh and dark mode")
    print("  - Export functionality")
    print("  - Keyboard shortcuts")

if __name__ == "__main__":
    main()
