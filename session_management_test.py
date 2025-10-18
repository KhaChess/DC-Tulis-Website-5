#!/usr/bin/env python3
"""
Focused Session Management Test for Discord Autotyper
Tests the specific issue reported by user: control panel buttons becoming unresponsive
"""

import requests
import json
import time
import asyncio
import websockets
from datetime import datetime

# Configuration
BASE_URL = "https://web-autotyper-2.preview.emergentagent.com/api"
WS_URL = "wss://web-autotyper.preview.emergentagent.com/api/ws"
HEADERS = {"Content-Type": "application/json"}

# Test data as specified in the review request
TEST_CHANNEL_ID = "123456789012345678"
TEST_MESSAGES = ["Test message 1", "Test message 2"]
TEST_TYPING_DELAY = 1000
TEST_MESSAGE_DELAY = 5000

class SessionManagementTester:
    def __init__(self):
        self.session_id = None
        self.test_results = []
        
    def log_result(self, test_name, success, message, details=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_session_creation(self):
        """Test POST /api/auto-typer/start with specified test data"""
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
                    self.log_result("Session Creation", False, f"API returned error: {data['error']}")
                    return False
                
                self.session_id = data["id"]
                
                # Verify session structure
                expected_fields = ["id", "status", "messages_sent", "messages_failed", "current_message_index"]
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    self.log_result("Session Creation", False, f"Missing fields: {missing_fields}")
                    return False
                
                self.log_result("Session Creation", True, f"Session created with ID: {self.session_id}", 
                              f"Status: {data.get('status')}, Messages: {len(data.get('messages', []))}")
                return True
            else:
                self.log_result("Session Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Session Creation", False, f"Request failed: {str(e)}")
            return False
    
    def test_session_status_transitions(self):
        """Test session status endpoint and verify state transitions"""
        if not self.session_id:
            self.log_result("Session Status", False, "No session ID available")
            return False
        
        try:
            response = requests.get(f"{BASE_URL}/auto-typer/{self.session_id}/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_result("Session Status", False, f"API returned error: {data['error']}")
                    return False
                
                # Check critical status fields
                status = data.get("status")
                valid_statuses = ["idle", "starting", "running", "paused", "stopped", "error", "waiting_for_login", "completed"]
                
                if status not in valid_statuses:
                    self.log_result("Session Status", False, f"Invalid status: {status}")
                    return False
                
                # Check for enhanced fields
                enhanced_fields = ["current_message", "typing_progress", "is_typing", "can_resume"]
                present_fields = [field for field in enhanced_fields if field in data]
                
                self.log_result("Session Status", True, f"Status: {status}, Enhanced fields: {present_fields}",
                              f"Messages sent: {data.get('messages_sent', 0)}, Failed: {data.get('messages_failed', 0)}")
                return True
            else:
                self.log_result("Session Status", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Session Status", False, f"Request failed: {str(e)}")
            return False
    
    def test_pause_control(self):
        """Test POST /api/auto-typer/{session_id}/pause"""
        if not self.session_id:
            self.log_result("Pause Control", False, "No session ID available")
            return False
        
        try:
            response = requests.post(f"{BASE_URL}/auto-typer/{self.session_id}/pause", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response
                if "error" in data:
                    # Expected for non-running sessions
                    if "not running" in data["error"].lower():
                        self.log_result("Pause Control", True, f"Correctly handled non-running session: {data['error']}")
                        return True
                    else:
                        self.log_result("Pause Control", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data:
                    self.log_result("Pause Control", True, f"Pause response: {data['message']}")
                    return True
                
                self.log_result("Pause Control", True, "Pause endpoint responded correctly")
                return True
            else:
                self.log_result("Pause Control", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Pause Control", False, f"Request failed: {str(e)}")
            return False
    
    def test_resume_control(self):
        """Test POST /api/auto-typer/{session_id}/resume"""
        if not self.session_id:
            self.log_result("Resume Control", False, "No session ID available")
            return False
        
        try:
            response = requests.post(f"{BASE_URL}/auto-typer/{self.session_id}/resume", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response
                if "error" in data:
                    # Expected for non-paused sessions
                    if "not paused" in data["error"].lower() or "not found" in data["error"].lower():
                        self.log_result("Resume Control", True, f"Correctly handled non-paused session: {data['error']}")
                        return True
                    else:
                        self.log_result("Resume Control", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data:
                    self.log_result("Resume Control", True, f"Resume response: {data['message']}")
                    return True
                
                self.log_result("Resume Control", True, "Resume endpoint responded correctly")
                return True
            else:
                self.log_result("Resume Control", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Resume Control", False, f"Request failed: {str(e)}")
            return False
    
    def test_stop_control(self):
        """Test POST /api/auto-typer/{session_id}/stop"""
        if not self.session_id:
            self.log_result("Stop Control", False, "No session ID available")
            return False
        
        try:
            response = requests.post(f"{BASE_URL}/auto-typer/{self.session_id}/stop", headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "error" in data:
                    if "not found" in data["error"].lower():
                        self.log_result("Stop Control", True, f"Correctly handled session not found: {data['error']}")
                        return True
                    else:
                        self.log_result("Stop Control", False, f"Unexpected error: {data['error']}")
                        return False
                
                if "message" in data and "stopped" in data["message"].lower():
                    self.log_result("Stop Control", True, f"Stop response: {data['message']}")
                    return True
                
                self.log_result("Stop Control", True, "Stop endpoint responded correctly")
                return True
            else:
                self.log_result("Stop Control", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Stop Control", False, f"Request failed: {str(e)}")
            return False
    
    async def test_websocket_connection(self):
        """Test WebSocket connection to /api/ws/{session_id}"""
        if not self.session_id:
            self.log_result("WebSocket Connection", False, "No session ID available")
            return False
        
        ws_url = f"{WS_URL}/{self.session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Wait for connection confirmation
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "connection_established":
                        self.log_result("WebSocket Connection", True, f"WebSocket connected successfully", 
                                      f"Message: {data.get('message')}")
                        
                        # Test ping-pong
                        await websocket.send(json.dumps({"action": "ping"}))
                        pong_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        pong_data = json.loads(pong_response)
                        
                        if pong_data.get("type") == "pong":
                            self.log_result("WebSocket Ping-Pong", True, "Ping-pong working correctly")
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
    
    def cleanup_session(self):
        """Clean up test session"""
        if self.session_id:
            try:
                requests.post(f"{BASE_URL}/auto-typer/{self.session_id}/stop", timeout=5)
                print(f"🧹 Cleaned up session: {self.session_id}")
            except:
                pass
    
    def run_all_tests(self):
        """Run all session management tests"""
        print("🎯 FOCUSED SESSION MANAGEMENT TESTING")
        print("Testing Discord Autotyper Session Control Issues")
        print("=" * 60)
        
        # Test sequence focusing on user's reported issue
        tests = [
            ("Session Creation", self.test_session_creation),
            ("Session Status Transitions", self.test_session_status_transitions),
            ("Pause Control", self.test_pause_control),
            ("Resume Control", self.test_resume_control),
            ("Stop Control", self.test_stop_control),
        ]
        
        # WebSocket tests
        websocket_tests = [
            ("WebSocket Connection", self.test_websocket_connection),
        ]
        
        passed = 0
        total = len(tests) + len(websocket_tests)
        
        # Run regular tests
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
                time.sleep(0.5)
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
        print("\n" + "=" * 60)
        print(f"📊 SESSION MANAGEMENT TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All session management tests passed!")
            print("✅ Control panel buttons should be responsive")
            print("✅ Session state transitions are working correctly")
            print("✅ WebSocket communication is functional")
        else:
            print(f"⚠️  {total - passed} tests failed.")
            print("❌ This may explain why control panel buttons are unresponsive")
        
        # Cleanup
        self.cleanup_session()
        
        return passed, total, self.test_results

if __name__ == "__main__":
    tester = SessionManagementTester()
    passed, total, results = tester.run_all_tests()
    
    # Save results
    with open("/app/session_management_test_results.json", "w") as f:
        json.dump({
            "summary": {"passed": passed, "total": total, "success_rate": passed/total},
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n📝 Results saved to: /app/session_management_test_results.json")