#!/usr/bin/env python3
"""
Debug search functionality
"""

import requests
import json

BASE_URL = "https://web-autotyper-2.preview.emergentagent.com/api"
HEADERS = {"Content-Type": "application/json"}
TEST_CHANNEL_ID = "123456789012345678"

def debug_search():
    print("🔍 Debugging Search Functionality")
    
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
        print(f"Created channel: {json.dumps(create_data, indent=2)}")
        channel_uuid = create_data.get('id')
        
        # Get all channels first
        all_response = requests.get(f"{BASE_URL}/channels")
        print(f"All channels response: {all_response.status_code}")
        all_data = all_response.json()
        print(f"All channels: {json.dumps(all_data, indent=2)}")
        
        # Test search by channel ID
        search_response = requests.get(f"{BASE_URL}/channels?search={TEST_CHANNEL_ID}")
        print(f"Search response: {search_response.status_code}")
        search_data = search_response.json()
        print(f"Search results: {json.dumps(search_data, indent=2)}")
        
        # Test search by partial channel ID
        partial_search = requests.get(f"{BASE_URL}/channels?search=123456")
        print(f"Partial search response: {partial_search.status_code}")
        partial_data = partial_search.json()
        print(f"Partial search results: {json.dumps(partial_data, indent=2)}")
        
        # Test search by category
        category_search = requests.get(f"{BASE_URL}/channels?search=Test")
        print(f"Category search response: {category_search.status_code}")
        category_data = category_search.json()
        print(f"Category search results: {json.dumps(category_data, indent=2)}")
        
        # Clean up
        if channel_uuid:
            delete_response = requests.delete(f"{BASE_URL}/channels/{channel_uuid}")
            print(f"Cleanup: {delete_response.status_code}")
    
if __name__ == "__main__":
    debug_search()