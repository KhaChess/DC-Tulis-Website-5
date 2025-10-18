#!/usr/bin/env python3
"""
Focused test for search functionality
"""

import requests
import json

BASE_URL = "https://web-autotyper-2.preview.emergentagent.com/api"
HEADERS = {"Content-Type": "application/json"}
TEST_CHANNEL_ID = "123456789012345678"

def test_search_functionality():
    print("🔍 Testing Search Functionality")
    
    # First create a channel
    payload = {
        "channel_id": TEST_CHANNEL_ID,
        "category": "Test Category",
        "is_favorite": False
    }
    
    create_response = requests.post(f"{BASE_URL}/channels", json=payload, headers=HEADERS)
    print(f"Create response: {create_response.status_code}")
    if create_response.status_code == 200:
        create_data = create_response.json()
        print(f"Created channel: {create_data}")
        channel_uuid = create_data.get('id')
        
        # Test search by channel ID
        search_response = requests.get(f"{BASE_URL}/channels?search={TEST_CHANNEL_ID}")
        print(f"Search response: {search_response.status_code}")
        search_data = search_response.json()
        print(f"Search results: {search_data}")
        
        # Check if channel is found
        found = any(ch.get("channel_id") == TEST_CHANNEL_ID for ch in search_data)
        print(f"Channel found in search: {found}")
        
        # Clean up
        if channel_uuid:
            delete_response = requests.delete(f"{BASE_URL}/channels/{channel_uuid}")
            print(f"Cleanup: {delete_response.status_code}")
    
if __name__ == "__main__":
    test_search_functionality()