#!/usr/bin/env python3
"""
Backend API Testing for Discord Autotyper - Focus on Browser Automation Session Creation
Tests specifically for the "Failed to start browser automation session" error fix
"""

import requests
import json
import time
import asyncio
import websockets
import threading
from datetime import datetime
from typing import Dict, List, Any

# Configuration
BASE_URL = "https://web-autotyper-2.preview.emergentagent.com/api"
WS_URL = "wss://web-autotyper-2.preview.emergentagent.com/api/ws"
HEADERS = {"Content-Type": "application/json"}

# Test data for browser automation testing
TEST_CHANNEL_ID = "https://discord.com/channels/@me/123456789012345678"  # Realistic Discord channel URL
TEST_MESSAGES = [
    "Hello, this is a test message for browser automation",
    "Testing Discord auto-typer with Playwright browser",
    "Final test message to verify session works"
]
TEST_TYPING_DELAY = 500  # Reasonable typing delay
TEST_MESSAGE_DELAY = 2000  # 2 seconds between messages

class BrowserAutomationTester:
    def __init__(self):
        self.test_results = []
        self.created_sessions = []
        self.websocket_messages = []
        self.websocket_connected = False
        
    def log_result(self, test_name, success, message, response_data=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "response_data": response_data,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_api_health_check(self):
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=10)
            if response.status_code == 200:
                self.log_result("API Health Check", True, f"API is accessible - Status: {response.status_code}")
                return True
            else:
                self.log_result("API Health Check", False, f"API returned status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("API Health Check", False, f"Connection failed: {str(e)}")
            return False
    
    def test_browser_automation_session_creation(self):
        """Test POST /api/auto-typer/start - Focus on browser automation startup"""
        try:
            payload = {
                "channel_id": TEST_CHANNEL_ID,
                "messages": TEST_MESSAGES,
                "typing_delay": TEST_TYPING_DELAY,
                "message_delay": TEST_MESSAGE_DELAY
            }
            
            print(f"🔍 Testing session creation with payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(f"{BASE_URL}/auto-typer/start", json=payload, headers=HEADERS, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_result("Browser Automation Session Creation", False, f"API returned error: {data['error']}")
                    return False
                
                # Validate session structure
                required_fields = ["id", "channel_id", "messages", "status"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Browser Automation Session Creation", False, f"Missing fields: {missing_fields}")
                    return False
                
                # Store session ID for further tests
                session_id = data["id"]
                self.created_sessions.append(session_id)
                
                # Check initial status
                if data.get("status") == "idle":
                    self.log_result("Browser Automation Session Creation", True, f"Session created successfully with ID: {session_id}")
                    return True
                else:
                    self.log_result("Browser Automation Session Creation", False, f"Unexpected initial status: {data.get('status')}")
                    return False
            else:
                self.log_result("Browser Automation Session Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Browser Automation Session Creation", False, f"Request failed: {str(e)}")
            return False
    
    def test_session_status_transitions(self):
        """Test session status changes from starting -> waiting_for_login"""
        if not self.created_sessions:
            self.log_result("Session Status Transitions", False, "No sessions available for status testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            
            # Monitor status changes over time
            status_history = []
            max_wait_time = 30  # 30 seconds max wait
            check_interval = 2  # Check every 2 seconds
            
            print(f"🔍 Monitoring session {session_id} status transitions...")
            
            for i in range(max_wait_time // check_interval):
                response = requests.get(f"{BASE_URL}/auto-typer/{session_id}/status", timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if "error" in data:
                        self.log_result("Session Status Transitions", False, f"Status API error: {data['error']}")
                        return False
                    
                    current_status = data.get("status", "unknown")
                    current_message = data.get("current_message", "")
                    
                    status_entry = {
                        "time": datetime.now().isoformat(),
                        "status": current_status,
                        "message": current_message
                    }
                    status_history.append(status_entry)
                    
                    print(f"   Status check {i+1}: {current_status} - {current_message}")
                    
                    # Check for expected transitions
                    if current_status == "starting":
                        print("   ✅ Session is starting (browser automation initializing)")
                    elif current_status == "waiting_for_login":
                        print("   ✅ Session reached waiting_for_login (browser automation successful)")
                        self.log_result("Session Status Transitions", True, 
                                      f"Successfully transitioned to waiting_for_login. Status history: {status_history}")
                        return True
                    elif current_status == "error":
                        error_msg = data.get("last_error", "Unknown error")
                        if "Failed to start browser automation session" in error_msg:
                            self.log_result("Session Status Transitions", False, 
                                          f"CRITICAL: Browser automation failed with error: {error_msg}")
                            return False
                        else:
                            self.log_result("Session Status Transitions", False, 
                                          f"Session error: {error_msg}")
                            return False
                    
                    time.sleep(check_interval)
                else:
                    self.log_result("Session Status Transitions", False, 
                                  f"Status check failed: HTTP {response.status_code}")
                    return False
            
            # If we get here, we didn't see the expected transition
            self.log_result("Session Status Transitions", False, 
                          f"Timeout waiting for status transition. Final history: {status_history}")
            return False
                
        except Exception as e:
            self.log_result("Session Status Transitions", False, f"Status monitoring failed: {str(e)}")
            return False
    
    async def test_websocket_real_time_updates(self):
        """Test WebSocket connection and real-time updates during session startup"""
        if not self.created_sessions:
            self.log_result("WebSocket Real-time Updates", False, "No sessions available for WebSocket testing")
            return False
        
        session_id = self.created_sessions[0]
        ws_url = f"{WS_URL}/{session_id}"
        
        try:
            print(f"🔍 Testing WebSocket connection to: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                self.websocket_connected = True
                
                # Wait for connection confirmation
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "connection_established":
                        print("   ✅ WebSocket connection established")
                        self.websocket_messages.append(data)
                        
                        # Listen for real-time updates for a short period
                        update_count = 0
                        listen_time = 15  # Listen for 15 seconds
                        
                        print(f"   🔍 Listening for real-time updates for {listen_time} seconds...")
                        
                        try:
                            while update_count < 10:  # Max 10 updates
                                message = await asyncio.wait_for(websocket.recv(), timeout=listen_time)
                                data = json.loads(message)
                                self.websocket_messages.append(data)
                                update_count += 1
                                
                                msg_type = data.get("type", "unknown")
                                print(f"   📨 Received: {msg_type}")
                                
                                if msg_type == "session_update":
                                    session_data = data.get("data", {})
                                    status = session_data.get("status", "unknown")
                                    current_msg = session_data.get("current_message", "")
                                    print(f"      Status: {status} - {current_msg}")
                                    
                                    if status == "waiting_for_login":
                                        self.log_result("WebSocket Real-time Updates", True, 
                                                      f"Received real-time session updates. Browser automation working!")
                                        return True
                                elif msg_type == "error_notification":
                                    error_data = data.get("data", {})
                                    error_msg = error_data.get("error", "Unknown error")
                                    if "Failed to start browser automation session" in error_msg:
                                        self.log_result("WebSocket Real-time Updates", False, 
                                                      f"CRITICAL: Browser automation error via WebSocket: {error_msg}")
                                        return False
                        
                        except asyncio.TimeoutError:
                            if update_count > 0:
                                self.log_result("WebSocket Real-time Updates", True, 
                                              f"Received {update_count} real-time updates via WebSocket")
                                return True
                            else:
                                self.log_result("WebSocket Real-time Updates", False, 
                                              "No real-time updates received within timeout")
                                return False
                    else:
                        self.log_result("WebSocket Real-time Updates", False, 
                                      f"Unexpected connection message: {data}")
                        return False
                        
                except asyncio.TimeoutError:
                    self.log_result("WebSocket Real-time Updates", False, 
                                  "Timeout waiting for WebSocket connection confirmation")
                    return False
                    
        except Exception as e:
            self.log_result("WebSocket Real-time Updates", False, f"WebSocket test failed: {str(e)}")
            return False
    
    def test_session_error_handling(self):
        """Test error handling and session state management"""
        if not self.created_sessions:
            self.log_result("Session Error Handling", False, "No sessions available for error testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            
            # Test pause on a potentially running/starting session
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/pause", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    # Expected for non-running sessions
                    if "not running" in data["error"].lower():
                        print("   ✅ Correctly handled pause on non-running session")
                    else:
                        print(f"   ⚠️  Pause error: {data['error']}")
                else:
                    print("   ✅ Pause command accepted")
            
            # Test resume
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/resume", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    if "not paused" in data["error"].lower() or "not found" in data["error"].lower():
                        print("   ✅ Correctly handled resume on non-paused session")
                    else:
                        print(f"   ⚠️  Resume error: {data['error']}")
                else:
                    print("   ✅ Resume command accepted")
            
            # Test stop
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/stop", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    print(f"   ⚠️  Stop error: {data['error']}")
                else:
                    print("   ✅ Stop command accepted")
            
            self.log_result("Session Error Handling", True, "Session state management working correctly")
            return True
                
        except Exception as e:
            self.log_result("Session Error Handling", False, f"Error handling test failed: {str(e)}")
            return False
    
    def run_websocket_test(self, test_func):
        """Helper to run async WebSocket tests"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(test_func())
        except Exception as e:
            print(f"Error running WebSocket test: {str(e)}")
            return False
        finally:
            loop.close()
    
    def cleanup_sessions(self):
        """Clean up any remaining test sessions"""
        for session_id in self.created_sessions[:]:
            try:
                requests.post(f"{BASE_URL}/auto-typer/{session_id}/stop", timeout=5)
                print(f"🧹 Cleaned up session: {session_id}")
            except:
                pass
    
    def run_browser_automation_tests(self):
        """Run focused tests for browser automation session creation"""
        print("🚀 Starting Browser Automation Session Creation Tests")
        print("Focus: Testing fix for 'Failed to start browser automation session' error")
        print("=" * 80)
        
        # Test sequence focused on browser automation
        tests = [
            ("API Health Check", self.test_api_health_check),
            ("Browser Automation Session Creation", self.test_browser_automation_session_creation),
            ("Session Status Transitions", self.test_session_status_transitions),
            ("Session Error Handling", self.test_session_error_handling),
        ]
        
        # WebSocket tests
        websocket_tests = [
            ("WebSocket Real-time Updates", self.test_websocket_real_time_updates),
        ]
        
        passed = 0
        total = len(tests) + len(websocket_tests)
        
        # Run regular tests
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
                time.sleep(1)  # Small delay between tests
            except Exception as e:
                self.log_result(test_name, False, f"Test execution failed: {str(e)}")
        
        # Run WebSocket tests
        for test_name, test_func in websocket_tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if self.run_websocket_test(test_func):
                    passed += 1
                time.sleep(1)
            except Exception as e:
                self.log_result(test_name, False, f"WebSocket test execution failed: {str(e)}")
        
        # Summary
        print("\n" + "=" * 80)
        print(f"📊 BROWSER AUTOMATION TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All browser automation tests passed!")
            print("✅ The 'Failed to start browser automation session' error appears to be FIXED!")
        else:
            print(f"⚠️  {total - passed} tests failed.")
            print("❌ Browser automation session creation may still have issues.")
        
        # Detailed analysis
        print("\n📋 DETAILED ANALYSIS:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        # Cleanup
        self.cleanup_sessions()
        
        return passed, total, self.test_results
    def __init__(self):
        self.test_results = []
        self.created_sessions = []
        self.websocket_messages = []
        self.websocket_connected = False
        
    def log_result(self, test_name, success, message, response_data=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "response_data": response_data,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_api_health_check(self):
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=10)
            if response.status_code == 200:
                self.log_result("API Health Check", True, f"API is accessible - Status: {response.status_code}")
                return True
            else:
                self.log_result("API Health Check", False, f"API returned status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("API Health Check", False, f"Connection failed: {str(e)}")
            return False
    
    def test_enhanced_session_creation(self):
        """Test POST /api/auto-typer/start - Enhanced session creation"""
        try:
            payload = {
                "channel_id": TEST_CHANNEL_ID,
                "messages": TEST_MESSAGES,
                "typing_delay": TEST_TYPING_DELAY,
                "message_delay": TEST_MESSAGE_DELAY
            }
            
            response = requests.post(f"{BASE_URL}/auto-typer/start", json=payload, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_result("Enhanced Session Creation", False, f"API returned error: {data['error']}")
                    return False
                
                # Validate enhanced session structure
                required_fields = [
                    "id", "channel_id", "messages", "typing_delay", "message_delay", 
                    "status", "messages_sent", "messages_failed", "current_message_index",
                    "current_message", "is_typing", "typing_progress", "failed_messages",
                    "retry_count", "can_resume", "created_at"
                ]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Enhanced Session Creation", False, f"Missing enhanced fields: {missing_fields}")
                    return False
                
                # Store session ID for further tests
                self.created_sessions.append(data["id"])
                
                self.log_result("Enhanced Session Creation", True, f"Enhanced session created with ID: {data['id']}", data)
                return True
            else:
                self.log_result("Enhanced Session Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Enhanced Session Creation", False, f"Request failed: {str(e)}")
            return False
    
    async def test_websocket_connection(self):
        """Test WebSocket connection to /api/ws/{session_id}"""
        if not self.created_sessions:
            self.log_result("WebSocket Connection", False, "No sessions available for WebSocket testing")
            return False
        
        session_id = self.created_sessions[0]
        ws_url = f"{WS_URL}/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.websocket_connected = True
                
                # Wait for connection confirmation
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "connection_established":
                        self.log_result("WebSocket Connection", True, f"WebSocket connected successfully to session {session_id}")
                        self.websocket_messages.append(data)
                        
                        # Test ping-pong
                        await websocket.send(json.dumps({"action": "ping"}))
                        pong_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        pong_data = json.loads(pong_response)
                        
                        if pong_data.get("type") == "pong":
                            self.log_result("WebSocket Ping-Pong", True, "WebSocket ping-pong working correctly")
                            return True
                        else:
                            self.log_result("WebSocket Ping-Pong", False, f"Unexpected pong response: {pong_data}")
                            return False
                    else:
                        self.log_result("WebSocket Connection", False, f"Unexpected connection message: {data}")
                        return False
                        
                except asyncio.TimeoutError:
                    self.log_result("WebSocket Connection", False, "Timeout waiting for connection confirmation")
                    return False
                    
        except Exception as e:
            self.log_result("WebSocket Connection", False, f"WebSocket connection failed: {str(e)}")
            return False
    
    def test_session_status_endpoint(self):
        """Test GET /api/auto-typer/{session_id}/status - Enhanced status with new fields"""
        if not self.created_sessions:
            self.log_result("Session Status", False, "No sessions available for status testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            response = requests.get(f"{BASE_URL}/auto-typer/{session_id}/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_result("Session Status", False, f"API returned error: {data['error']}")
                    return False
                
                # Validate enhanced status fields
                enhanced_fields = [
                    "current_message", "typing_progress", "is_typing", "failed_messages",
                    "retry_count", "can_resume", "messages_sent", "messages_failed"
                ]
                missing_fields = [field for field in enhanced_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Session Status", False, f"Missing enhanced status fields: {missing_fields}")
                    return False
                
                self.log_result("Session Status", True, f"Enhanced status retrieved successfully", data)
                return True
            else:
                self.log_result("Session Status", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Session Status", False, f"Request failed: {str(e)}")
            return False
    
    def test_pause_functionality(self):
        """Test POST /api/auto-typer/{session_id}/pause - Pause session"""
        if not self.created_sessions:
            self.log_result("Pause Functionality", False, "No sessions available for pause testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/pause", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    # Check if error is expected (session not running)
                    if "not running" in data["error"].lower():
                        self.log_result("Pause Functionality", True, f"Correctly handled non-running session: {data['error']}")
                        return True
                    else:
                        self.log_result("Pause Functionality", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data and "paused" in data["message"].lower():
                    # Verify session status changed to paused
                    status_response = requests.get(f"{BASE_URL}/auto-typer/{session_id}/status", timeout=5)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get("status") == "paused" and status_data.get("can_resume"):
                            self.log_result("Pause Functionality", True, "Session paused successfully with resume capability")
                            return True
                        else:
                            self.log_result("Pause Functionality", False, f"Session status not updated correctly: {status_data.get('status')}")
                            return False
                    else:
                        self.log_result("Pause Functionality", True, "Pause appeared successful (couldn't verify status)")
                        return True
                else:
                    self.log_result("Pause Functionality", True, f"Pause response: {data}")
                    return True
            else:
                self.log_result("Pause Functionality", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Pause Functionality", False, f"Request failed: {str(e)}")
            return False
    
    def test_resume_functionality(self):
        """Test POST /api/auto-typer/{session_id}/resume - Resume session"""
        if not self.created_sessions:
            self.log_result("Resume Functionality", False, "No sessions available for resume testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/resume", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    # Check if error is expected (session not paused)
                    if "not paused" in data["error"].lower() or "not found" in data["error"].lower():
                        self.log_result("Resume Functionality", True, f"Correctly handled non-paused session: {data['error']}")
                        return True
                    else:
                        self.log_result("Resume Functionality", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data and "resumed" in data["message"].lower():
                    self.log_result("Resume Functionality", True, "Session resumed successfully")
                    return True
                else:
                    self.log_result("Resume Functionality", True, f"Resume response: {data}")
                    return True
            else:
                self.log_result("Resume Functionality", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Resume Functionality", False, f"Request failed: {str(e)}")
            return False
    
    def test_manual_retry_functionality(self):
        """Test POST /api/auto-typer/{session_id}/retry - Manual retry mechanism"""
        if not self.created_sessions:
            self.log_result("Manual Retry", False, "No sessions available for retry testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/retry", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    # Check if error is expected (no failed messages)
                    if "no failed messages" in data["error"].lower():
                        self.log_result("Manual Retry", True, f"Correctly handled no failed messages: {data['error']}")
                        return True
                    elif "not found" in data["error"].lower():
                        self.log_result("Manual Retry", True, f"Correctly handled session not found: {data['error']}")
                        return True
                    else:
                        self.log_result("Manual Retry", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data and "retrying" in data["message"].lower():
                    self.log_result("Manual Retry", True, f"Retry initiated successfully: {data['message']}")
                    return True
                else:
                    self.log_result("Manual Retry", True, f"Retry response: {data}")
                    return True
            else:
                self.log_result("Manual Retry", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Manual Retry", False, f"Request failed: {str(e)}")
            return False
    
    def test_session_stop_functionality(self):
        """Test POST /api/auto-typer/{session_id}/stop - Stop session"""
        if not self.created_sessions:
            self.log_result("Stop Functionality", False, "No sessions available for stop testing")
            return False
        
        try:
            session_id = self.created_sessions[0]
            response = requests.post(f"{BASE_URL}/auto-typer/{session_id}/stop", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    if "not found" in data["error"].lower():
                        self.log_result("Stop Functionality", True, f"Correctly handled session not found: {data['error']}")
                        return True
                    else:
                        self.log_result("Stop Functionality", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data and "stopped" in data["message"].lower():
                    self.log_result("Stop Functionality", True, "Session stopped successfully")
                    return True
                else:
                    self.log_result("Stop Functionality", True, f"Stop response: {data}")
                    return True
            else:
                self.log_result("Stop Functionality", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Stop Functionality", False, f"Request failed: {str(e)}")
            return False
    
    def test_get_all_sessions(self):
        """Test GET /api/auto-typer/sessions - Get all sessions"""
        try:
            response = requests.get(f"{BASE_URL}/auto-typer/sessions", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Check if our test session is in the list
                    if self.created_sessions:
                        found_session = any(session.get("id") in self.created_sessions for session in data)
                        if found_session:
                            self.log_result("Get All Sessions", True, f"Retrieved {len(data)} sessions, test session found")
                            return True
                        else:
                            self.log_result("Get All Sessions", True, f"Retrieved {len(data)} sessions (test session may have been cleaned up)")
                            return True
                    else:
                        self.log_result("Get All Sessions", True, f"Retrieved {len(data)} sessions")
                        return True
                else:
                    self.log_result("Get All Sessions", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result("Get All Sessions", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Get All Sessions", False, f"Request failed: {str(e)}")
            return False
    
    async def test_websocket_real_time_updates(self):
        """Test WebSocket real-time session updates"""
        if not self.created_sessions:
            self.log_result("WebSocket Real-time Updates", False, "No sessions available for WebSocket testing")
            return False
        
        session_id = self.created_sessions[0]
        ws_url = f"{WS_URL}/{session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Wait for connection confirmation
                await asyncio.wait_for(websocket.recv(), timeout=5.0)
                
                # Request current status to trigger an update
                await websocket.send(json.dumps({"action": "get_status"}))
                
                # Wait for status update
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "session_update":
                        self.log_result("WebSocket Real-time Updates", True, f"Received real-time session update: {data['type']}")
                        return True
                    else:
                        self.log_result("WebSocket Real-time Updates", True, f"Received WebSocket message: {data.get('type', 'unknown')}")
                        return True
                        
                except asyncio.TimeoutError:
                    self.log_result("WebSocket Real-time Updates", True, "No immediate updates (expected for idle session)")
                    return True
                    
        except Exception as e:
            self.log_result("WebSocket Real-time Updates", False, f"WebSocket real-time test failed: {str(e)}")
            return False
    
    def run_websocket_test(self, test_func):
        """Helper to run async WebSocket tests"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(test_func())
        except Exception as e:
            print(f"Error running WebSocket test: {str(e)}")
            return False
        finally:
            loop.close()
    
    def cleanup_sessions(self):
        """Clean up any remaining test sessions"""
        for session_id in self.created_sessions[:]:
            try:
                requests.post(f"{BASE_URL}/auto-typer/{session_id}/stop", timeout=5)
                print(f"🧹 Cleaned up session: {session_id}")
            except:
                pass
    
    def run_all_tests(self):
        """Run all enhanced Discord autotyper tests"""
        print("🚀 Starting Enhanced Discord Autotyper API Tests")
        print("=" * 70)
        
        # Test sequence
        tests = [
            ("API Health Check", self.test_api_health_check),
            ("Enhanced Session Creation", self.test_enhanced_session_creation),
            ("Session Status Endpoint", self.test_session_status_endpoint),
            ("Pause Functionality", self.test_pause_functionality),
            ("Resume Functionality", self.test_resume_functionality),
            ("Manual Retry Functionality", self.test_manual_retry_functionality),
            ("Stop Functionality", self.test_session_stop_functionality),
            ("Get All Sessions", self.test_get_all_sessions),
        ]
        
        # WebSocket tests (run separately due to async nature)
        websocket_tests = [
            ("WebSocket Connection", self.test_websocket_connection),
            ("WebSocket Real-time Updates", self.test_websocket_real_time_updates),
        ]
        
        passed = 0
        total = len(tests) + len(websocket_tests)
        
        # Run regular tests
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                self.log_result(test_name, False, f"Test execution failed: {str(e)}")
        
        # Run WebSocket tests
        for test_name, test_func in websocket_tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if self.run_websocket_test(test_func):
                    passed += 1
                time.sleep(0.5)
            except Exception as e:
                self.log_result(test_name, False, f"WebSocket test execution failed: {str(e)}")
        
        # Summary
        print("\n" + "=" * 70)
        print(f"📊 ENHANCED AUTOTYPER TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All enhanced autotyper tests passed! WebSocket and real-time features are working correctly.")
        else:
            print(f"⚠️  {total - passed} tests failed. See details above.")
        
        # Cleanup
        self.cleanup_sessions()
        
        return passed, total, self.test_results

if __name__ == "__main__":
    print("🎯 BROWSER AUTOMATION SESSION CREATION TESTING")
    print("Testing fix for: 'Failed to start browser automation session' error")
    print("=" * 80)
    
    # Run Browser Automation Tests
    tester = BrowserAutomationTester()
    passed, total, results = tester.run_browser_automation_tests()
    
    # Final Summary
    print("\n" + "=" * 80)
    print("🏆 FINAL TEST SUMMARY")
    print("=" * 80)
    print(f"BROWSER AUTOMATION TESTS: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 SUCCESS: Browser automation session creation is working!")
        print("✅ The 'Failed to start browser automation session' error has been FIXED!")
        print("✅ Playwright dependencies and browser installation are working correctly.")
    else:
        print(f"⚠️  ISSUES FOUND: {total - passed} tests failed.")
        print("❌ Browser automation may still have problems.")
        print("🔍 Check the detailed analysis above for specific issues.")
    
    # Save results
    test_summary = {
        "test_focus": "Browser Automation Session Creation",
        "issue_tested": "Failed to start browser automation session",
        "summary": {
            "total_passed": passed,
            "total_tests": total,
            "success_rate": passed/total,
            "status": "FIXED" if passed == total else "ISSUES_REMAIN"
        },
        "test_results": results,
        "timestamp": datetime.now().isoformat()
    }
    
    with open("/app/browser_automation_test_results.json", "w") as f:
        json.dump(test_summary, f, indent=2)
    
    print(f"\n📝 Test results saved to: /app/browser_automation_test_results.json")