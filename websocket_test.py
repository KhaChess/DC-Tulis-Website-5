#!/usr/bin/env python3
"""
WebSocket Real-time Testing for Discord Autotyper
Tests WebSocket connection and real-time updates during session startup
"""

import asyncio
import websockets
import json
import requests
from datetime import datetime

BASE_URL = "https://web-autotyper-2.preview.emergentagent.com/api"
WS_URL = "wss://web-autotyper-1.preview.emergentagent.com/api/ws"
HEADERS = {"Content-Type": "application/json"}

async def test_websocket_with_session():
    """Test WebSocket connection with a real session"""
    
    # Create a session first
    payload = {
        "channel_id": "https://discord.com/channels/@me/123456789012345678",
        "messages": ["Test message for WebSocket"],
        "typing_delay": 500,
        "message_delay": 2000
    }
    
    print("🔍 Creating session for WebSocket test...")
    response = requests.post(f"{BASE_URL}/auto-typer/start", json=payload, headers=HEADERS, timeout=15)
    
    if response.status_code != 200:
        print(f"❌ Failed to create session: {response.status_code}")
        return False
    
    session_data = response.json()
    session_id = session_data["id"]
    print(f"✅ Session created: {session_id}")
    
    # Connect to WebSocket
    ws_url = f"{WS_URL}/{session_id}"
    print(f"🔍 Connecting to WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connected")
            
            # Listen for messages for 10 seconds
            messages_received = []
            start_time = datetime.now()
            
            try:
                while (datetime.now() - start_time).seconds < 10:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    messages_received.append(data)
                    
                    msg_type = data.get("type", "unknown")
                    print(f"📨 Received: {msg_type}")
                    
                    if msg_type == "session_update":
                        session_data = data.get("data", {})
                        status = session_data.get("status", "unknown")
                        current_msg = session_data.get("current_message", "")
                        print(f"   Status: {status} - {current_msg}")
                        
                        if status == "waiting_for_login":
                            print("✅ Browser automation working - reached waiting_for_login!")
                            break
                    elif msg_type == "error_notification":
                        error_data = data.get("data", {})
                        error_msg = error_data.get("error", "Unknown error")
                        print(f"❌ Error notification: {error_msg}")
                        if "Failed to start browser automation session" in error_msg:
                            print("❌ CRITICAL: Browser automation still failing!")
                            return False
                            
            except asyncio.TimeoutError:
                print("⏰ WebSocket listening timeout")
            
            print(f"📊 Total messages received: {len(messages_received)}")
            
            # Clean up session
            try:
                requests.post(f"{BASE_URL}/auto-typer/{session_id}/stop", timeout=5)
                print(f"🧹 Cleaned up session: {session_id}")
            except:
                pass
            
            return len(messages_received) > 0
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 WebSocket Real-time Testing")
    print("=" * 50)
    
    result = asyncio.run(test_websocket_with_session())
    
    if result:
        print("✅ WebSocket real-time communication is working!")
    else:
        print("❌ WebSocket real-time communication has issues.")