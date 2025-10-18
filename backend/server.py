from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global storage for active sessions
active_sessions: Dict[str, Dict[str, Any]] = {}

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_message(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending WebSocket message to {session_id}: {str(e)}")
                    self.disconnect(session_id)

    async def broadcast_session_update(self, session_id: str, update_data: dict):
        """Send session update to connected client"""
        await self.send_message(session_id, {
            "type": "session_update",
            "session_id": session_id,
            "data": update_data
        })

    async def send_typing_update(self, session_id: str, typing_data: dict):
        """Send typing indicator update"""
        await self.send_message(session_id, {
            "type": "typing_update", 
            "session_id": session_id,
            "data": typing_data
        })

    async def send_error_notification(self, session_id: str, error_data: dict):
        """Send error notification"""
        await self.send_message(session_id, {
            "type": "error_notification",
            "session_id": session_id,
            "data": error_data
        })

manager = ConnectionManager()

# Discord automation function will be defined after models


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class AutoTyperSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    messages: List[str]
    typing_delay: int = 1000
    message_delay: int = 5000
    status: str = "idle"  # idle, running, paused, stopped, error, waiting_for_login
    messages_sent: int = 0
    messages_failed: int = 0
    current_message_index: int = 0
    current_message: Optional[str] = None
    is_typing: bool = False
    typing_progress: float = 0.0
    failed_messages: List[Dict[str, Any]] = []  # Store failed messages for retry
    last_error: Optional[str] = None
    retry_count: int = 0
    can_resume: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    
class AutoTyperSessionCreate(BaseModel):
    channel_id: str
    messages: List[str]
    typing_delay: int = 1000
    message_delay: int = 5000

class AutoTyperSessionUpdate(BaseModel):
    status: Optional[str] = None
    messages_sent: Optional[int] = None
    messages_failed: Optional[int] = None
    current_message_index: Optional[int] = None
    current_message: Optional[str] = None
    is_typing: Optional[bool] = None
    typing_progress: Optional[float] = None
    last_error: Optional[str] = None
    retry_count: Optional[int] = None
    can_resume: Optional[bool] = None

# Discord Channel Models
class DiscordChannel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str  # Discord Channel ID
    channel_name: Optional[str] = None
    guild_id: Optional[str] = None
    guild_name: Optional[str] = None
    category: Optional[str] = None  # Custom category set by user
    is_favorite: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
class DiscordChannelCreate(BaseModel):
    channel_id: str
    category: Optional[str] = None
    is_favorite: bool = False

class DiscordChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    category: Optional[str] = None  
    is_favorite: Optional[bool] = None

# Enhanced Discord automation function with real-time updates
async def discord_automation(session_id: str, session_data: AutoTyperSession):
    """Enhanced browser automation for Discord message sending with real-time updates"""
    browser = None
    try:
        logger.info(f"Starting Discord automation for session {session_id}")
        
        async with async_playwright() as p:
            # Launch browser in NON-headless mode so user can see and login
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Navigate to Discord
            await page.goto('https://discord.com/channels/@me', wait_until='networkidle')
            
            # Update session status and notify via WebSocket
            await update_session_status(session_id, {
                'status': 'waiting_for_login',
                'current_message': 'Please login to Discord in the browser window that opened...'
            })
            
            # Wait for user to login with extended timeout
            login_timeout = 300  # 5 minutes timeout for login
            try:
                logger.info(f"Waiting for Discord login for session {session_id}...")
                # Try multiple selectors for Discord interface
                await page.wait_for_selector('[data-list-id="channels"], [class*="sidebar"], [class*="channelName"]', timeout=login_timeout * 1000)
                logger.info(f"Discord interface detected for session {session_id}")
                
                # Give extra time for Discord to fully load
                await asyncio.sleep(2)
            except Exception as e:
                error_msg = f"Discord login timeout - please login manually within {login_timeout} seconds. Error: {str(e)}"
                logger.error(f"Login timeout for session {session_id}: {str(e)}")
                await handle_session_error(session_id, error_msg, can_retry=True)
                return

            # Navigate to the specific channel
            channel_url = f"https://discord.com/channels/@me/{session_data.channel_id}"
            if session_data.channel_id.startswith('https://discord.com'):
                channel_url = session_data.channel_id
            
            logger.info(f"Navigating to channel: {channel_url}")
            await page.goto(channel_url, wait_until='networkidle')
            
            # Give Discord time to load
            await asyncio.sleep(3)

            # Wait for message input to be visible with multiple possible selectors
            message_input_found = False
            selectors_to_try = [
                '[role="textbox"][data-slate-editor="true"]',  # New Discord selector
                '[data-slate-editor="true"]',  # Old selector
                'div[class*="slateTextArea"]',  # Alternative selector
                '[contenteditable="true"][role="textbox"]',  # Generic contenteditable
                'div[class*="editor"]'  # Fallback
            ]
            
            message_input_selector = None
            for selector in selectors_to_try:
                try:
                    logger.info(f"Trying selector: {selector}")
                    await page.wait_for_selector(selector, timeout=5000)
                    message_input_selector = selector
                    message_input_found = True
                    logger.info(f"Found message input with selector: {selector}")
                    break
                except Exception as e:
                    logger.warning(f"Selector {selector} not found: {str(e)}")
                    continue
            
            if not message_input_found:
                error_msg = "Could not find message input - check channel permissions or Discord UI may have changed"
                logger.error(f"Message input not found for session {session_id}")
                await handle_session_error(session_id, error_msg, can_retry=True)
                return

            await update_session_status(session_id, {
                'status': 'running',
                'current_message': 'Session started successfully'
            })

            # Main message sending loop
            message_index = active_sessions[session_id].get('current_message_index', 0)
            messages = session_data.messages

            while (active_sessions[session_id]['status'] == 'running' and 
                   message_index < len(messages)):

                # Check for pause state
                if active_sessions[session_id]['status'] == 'paused':
                    await update_session_status(session_id, {
                        'status': 'paused',
                        'current_message': 'Session paused',
                        'can_resume': True,
                        'current_message_index': message_index
                    })
                    
                    # Wait for resume or stop
                    while active_sessions[session_id]['status'] == 'paused':
                        await asyncio.sleep(1)
                    
                    # Check if resumed or stopped
                    if active_sessions[session_id]['status'] != 'running':
                        break

                message = messages[message_index]
                
                # Update current message being processed
                await update_session_status(session_id, {
                    'current_message': message,
                    'current_message_index': message_index,
                    'is_typing': True,
                    'typing_progress': 0.0
                })

                success = await send_message_with_typing(page, session_id, message, session_data.typing_delay, message_input_selector)
                
                if success:
                    # Update success count
                    active_sessions[session_id]['messages_sent'] += 1
                    await update_session_status(session_id, {
                        'messages_sent': active_sessions[session_id]['messages_sent'],
                        'is_typing': False,
                        'typing_progress': 100.0
                    })
                    logger.info(f"Message sent in session {session_id}: {message[:50]}...")
                else:
                    # Handle failed message
                    await handle_message_failure(session_id, message, message_index)

                # Wait before next message
                await asyncio.sleep(session_data.message_delay / 1000)
                message_index += 1

            # Session completed
            await update_session_status(session_id, {
                'status': 'completed',
                'current_message': 'All messages sent successfully',
                'is_typing': False
            })

    except Exception as e:
        logger.error(f"Discord automation error for session {session_id}: {str(e)}")
        await handle_session_error(session_id, str(e), can_retry=True)
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

async def send_message_with_typing(page, session_id: str, message: str, typing_delay: int):
    """Send message with real-time typing progress"""
    try:
        # Find and click the message input
        message_input = await page.wait_for_selector('[data-slate-editor="true"]', timeout=10000)
        await message_input.click()

        # Type with progress updates
        chars_per_update = max(1, len(message) // 10)  # Update 10 times during typing
        
        for i, char in enumerate(message):
            await page.keyboard.type(char, delay=typing_delay // len(message))
            
            # Update typing progress
            if i % chars_per_update == 0 or i == len(message) - 1:
                progress = ((i + 1) / len(message)) * 100
                await manager.send_typing_update(session_id, {
                    'typing_progress': progress,
                    'current_char_index': i + 1,
                    'total_chars': len(message)
                })

        # Send the message
        await page.keyboard.press('Enter')
        return True

    except Exception as e:
        logger.error(f"Error sending message in session {session_id}: {str(e)}")
        return False

async def update_session_status(session_id: str, update_data: dict):
    """Update session status in database and notify via WebSocket"""
    if session_id in active_sessions:
        # Update active session
        for key, value in update_data.items():
            active_sessions[session_id][key] = value

        # Update database
        await db.auto_typer_sessions.update_one(
            {"id": session_id},
            {"$set": update_data}
        )

        # Notify via WebSocket
        await manager.broadcast_session_update(session_id, update_data)

async def handle_session_error(session_id: str, error_msg: str, can_retry: bool = False):
    """Handle session error with notification"""
    error_data = {
        'status': 'error',
        'last_error': error_msg,
        'can_resume': can_retry,
        'retry_count': active_sessions[session_id].get('retry_count', 0),
        'is_typing': False
    }
    
    await update_session_status(session_id, error_data)
    await manager.send_error_notification(session_id, {
        'error': error_msg,
        'can_retry': can_retry,
        'session_id': session_id
    })

async def handle_message_failure(session_id: str, message: str, message_index: int):
    """Handle individual message failure"""
    active_sessions[session_id]['messages_failed'] += 1
    
    # Add to failed messages for retry
    if 'failed_messages' not in active_sessions[session_id]:
        active_sessions[session_id]['failed_messages'] = []
    
    active_sessions[session_id]['failed_messages'].append({
        'message': message,
        'index': message_index,
        'timestamp': datetime.utcnow().isoformat(),
        'error': 'Failed to send message'
    })
    
    await update_session_status(session_id, {
        'messages_failed': active_sessions[session_id]['messages_failed'],
        'is_typing': False
    })

    # Send error notification
    await manager.send_error_notification(session_id, {
        'error': f'Failed to send message: {message[:50]}...',
        'message_index': message_index,
        'can_retry': True
    })

# WebSocket endpoint
@api_router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        # Send initial connection confirmation
        await manager.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "message": "WebSocket connection established"
        })
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                data = await websocket.receive_json()
                
                # Handle client commands
                if data.get("action") == "ping":
                    await manager.send_message(session_id, {"type": "pong"})
                elif data.get("action") == "get_status":
                    # Send current session status
                    session = await db.auto_typer_sessions.find_one({"id": session_id})
                    if session:
                        # Remove MongoDB ObjectId to avoid JSON serialization issues
                        if "_id" in session:
                            del session["_id"]
                        await manager.broadcast_session_update(session_id, session)
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for session {session_id}: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket connection error for session {session_id}: {str(e)}")
    finally:
        manager.disconnect(session_id)

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

@api_router.post("/auto-typer/start", response_model=AutoTyperSession)
async def start_auto_typer_session(session_create: AutoTyperSessionCreate):
    """Start a new Discord auto-typer session with enhanced features"""
    session = AutoTyperSession(**session_create.dict())
    
    # Store in database
    await db.auto_typer_sessions.insert_one(session.dict())
    
    # Initialize enhanced active session
    active_sessions[session.id] = {
        'status': 'starting',
        'messages_sent': 0,
        'messages_failed': 0,
        'current_message_index': 0,
        'current_message': None,
        'is_typing': False,
        'typing_progress': 0.0,
        'failed_messages': [],
        'last_error': None,
        'retry_count': 0,
        'can_resume': False,
        'task': None
    }
    
    # Start browser automation in background
    task = asyncio.create_task(discord_automation(session.id, session))
    active_sessions[session.id]['task'] = task
    
    logger.info(f"Started enhanced auto-typer session {session.id}")
    return session

@api_router.post("/auto-typer/{session_id}/stop")
async def stop_auto_typer_session(session_id: str):
    """Stop an active auto-typer session"""
    if session_id in active_sessions:
        active_sessions[session_id]['status'] = 'stopped'
        
        # Cancel the background task
        if active_sessions[session_id]['task']:
            active_sessions[session_id]['task'].cancel()
        
        # Update database
        await db.auto_typer_sessions.update_one(
            {"id": session_id},
            {"$set": {"status": "stopped"}}
        )
        
        logger.info(f"Stopped auto-typer session {session_id}")
        return {"message": "Session stopped successfully"}
    else:
        return {"error": "Session not found"}

@api_router.post("/auto-typer/{session_id}/pause")
async def pause_auto_typer_session(session_id: str):
    """Pause an active auto-typer session"""
    if session_id in active_sessions:
        if active_sessions[session_id]['status'] == 'running':
            active_sessions[session_id]['status'] = 'paused'
            
            # Update database with pause timestamp
            await db.auto_typer_sessions.update_one(
                {"id": session_id},
                {"$set": {
                    "status": "paused",
                    "can_resume": True,
                    "paused_at": datetime.utcnow()
                }}
            )
            
            # Notify via WebSocket
            await manager.broadcast_session_update(session_id, {
                "status": "paused",
                "can_resume": True,
                "current_message": "Session paused by user"
            })
            
            logger.info(f"Paused auto-typer session {session_id}")
            return {"message": "Session paused successfully"}
        else:
            return {"error": "Session is not running"}
    else:
        return {"error": "Session not found"}

@api_router.post("/auto-typer/{session_id}/resume")
async def resume_auto_typer_session(session_id: str):
    """Resume a paused auto-typer session"""
    if session_id in active_sessions:
        if active_sessions[session_id]['status'] == 'paused':
            active_sessions[session_id]['status'] = 'running'
            
            # Update database with resume timestamp
            await db.auto_typer_sessions.update_one(
                {"id": session_id},
                {"$set": {
                    "status": "running",
                    "resumed_at": datetime.utcnow()
                }}
            )
            
            # Notify via WebSocket
            await manager.broadcast_session_update(session_id, {
                "status": "running",
                "current_message": "Session resumed by user"
            })
            
            logger.info(f"Resumed auto-typer session {session_id}")
            return {"message": "Session resumed successfully"}
        else:
            return {"error": "Session is not paused"}
    else:
        # Check if session can be resumed from database
        session_data = await db.auto_typer_sessions.find_one({"id": session_id})
        if session_data and session_data.get('can_resume'):
            # Reinitialize session for resume
            active_sessions[session_id] = {
                'status': 'running',
                'messages_sent': session_data.get('messages_sent', 0),
                'messages_failed': session_data.get('messages_failed', 0),
                'current_message_index': session_data.get('current_message_index', 0),
                'failed_messages': session_data.get('failed_messages', []),
                'retry_count': session_data.get('retry_count', 0),
                'task': None
            }
            
            # Start automation from where it left off
            session_obj = AutoTyperSession(**session_data)
            task = asyncio.create_task(discord_automation(session_id, session_obj))
            active_sessions[session_id]['task'] = task
            
            logger.info(f"Resumed auto-typer session {session_id} from database")
            return {"message": "Session resumed successfully"}
        else:
            return {"error": "Session not found or cannot be resumed"}

@api_router.post("/auto-typer/{session_id}/retry")
async def retry_failed_messages(session_id: str):
    """Retry failed messages for a session"""
    if session_id not in active_sessions:
        return {"error": "Session not found"}
    
    failed_messages = active_sessions[session_id].get('failed_messages', [])
    if not failed_messages:
        return {"error": "No failed messages to retry"}
    
    # Clear failed messages and reset counters
    active_sessions[session_id]['failed_messages'] = []
    active_sessions[session_id]['retry_count'] += 1
    
    # Update database
    await db.auto_typer_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "retry_count": active_sessions[session_id]['retry_count'],
            "failed_messages": []
        }}
    )
    
    # Notify via WebSocket
    await manager.send_message(session_id, {
        "type": "retry_initiated",
        "session_id": session_id,
        "data": {
            "retry_count": active_sessions[session_id]['retry_count'],
            "messages_to_retry": len(failed_messages)
        }
    })
    
    logger.info(f"Retrying {len(failed_messages)} failed messages for session {session_id}")
    return {"message": f"Retrying {len(failed_messages)} failed messages"}

@api_router.get("/auto-typer/{session_id}/status")
async def get_auto_typer_session_status(session_id: str):
    """Get the current status of an auto-typer session"""
    # Get from database
    session_data = await db.auto_typer_sessions.find_one({"id": session_id})
    if not session_data:
        return {"error": "Session not found"}
    
    # Remove MongoDB ObjectId to avoid JSON serialization issues
    if "_id" in session_data:
        del session_data["_id"]
    
    # Merge with active session data if available
    if session_id in active_sessions:
        for key in ['messages_sent', 'messages_failed', 'status', 'current_message_index', 
                   'current_message', 'is_typing', 'typing_progress', 'failed_messages',
                   'last_error', 'retry_count', 'can_resume']:
            if key in active_sessions[session_id]:
                session_data[key] = active_sessions[session_id][key]
    
    return session_data

@api_router.get("/auto-typer/sessions", response_model=List[AutoTyperSession])
async def get_auto_typer_sessions():
    """Get all auto-typer sessions"""
    sessions = await db.auto_typer_sessions.find().sort("created_at", -1).limit(50).to_list(50)
    
    # Remove MongoDB ObjectId to avoid JSON serialization issues
    for session in sessions:
        if "_id" in session:
            del session["_id"]
    
    # Update with active session data
    for session in sessions:
        if session['id'] in active_sessions:
            for key in ['messages_sent', 'messages_failed', 'status', 'current_message_index',
                       'current_message', 'is_typing', 'typing_progress', 'can_resume']:
                if key in active_sessions[session['id']]:
                    session[key] = active_sessions[session['id']][key]
    
    return [AutoTyperSession(**session) for session in sessions]

# Discord Channel Management API Endpoints
@api_router.post("/channels", response_model=DiscordChannel)
async def create_discord_channel(channel_create: DiscordChannelCreate):
    """Add a new Discord channel to saved list"""
    try:
        # Check if channel already exists
        existing = await db.discord_channels.find_one({"channel_id": channel_create.channel_id})
        if existing:
            raise HTTPException(status_code=400, detail="Channel already exists in saved list")
        
        # Create new channel record
        channel = DiscordChannel(**channel_create.dict())
        
        # Try to fetch channel info from Discord API if token is available
        discord_token = os.environ.get('DISCORD_BOT_TOKEN')
        if discord_token:
            try:
                channel_info = await fetch_discord_channel_info(channel_create.channel_id, discord_token)
                if channel_info:
                    channel.channel_name = channel_info.get('name')
                    channel.guild_id = channel_info.get('guild_id') 
                    channel.guild_name = channel_info.get('guild_name')
            except Exception as e:
                logger.warning(f"Could not fetch Discord channel info: {str(e)}")
        
        # Save to database
        await db.discord_channels.insert_one(channel.dict())
        logger.info(f"Added Discord channel {channel.channel_id}")
        return channel
        
    except Exception as e:
        logger.error(f"Error creating Discord channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/channels", response_model=List[DiscordChannel])
async def get_discord_channels(search: Optional[str] = None, category: Optional[str] = None, favorites_only: bool = False):
    """Get all saved Discord channels with optional filtering"""
    try:
        # Build query
        query = {}
        if favorites_only:
            query["is_favorite"] = True
        if category:
            query["category"] = category
            
        channels = await db.discord_channels.find(query).sort("created_at", -1).to_list(1000)
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            channels = [
                channel for channel in channels 
                if (search_lower in (channel.get('channel_name') or '').lower() or
                    search_lower in (channel.get('guild_name') or '').lower() or  
                    search_lower in (channel.get('category') or '').lower() or
                    search_lower in (channel.get('channel_id') or '').lower())
            ]
        
        return [DiscordChannel(**channel) for channel in channels]
        
    except Exception as e:
        logger.error(f"Error fetching Discord channels: {str(e)}")
        return []

@api_router.put("/channels/{channel_id}", response_model=DiscordChannel)
async def update_discord_channel(channel_id: str, channel_update: DiscordChannelUpdate):
    """Update a saved Discord channel"""
    try:
        # Find existing channel
        existing = await db.discord_channels.find_one({"id": channel_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        # Prepare update data
        update_data = channel_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        # Update in database
        await db.discord_channels.update_one(
            {"id": channel_id},
            {"$set": update_data}
        )
        
        # Return updated channel
        updated_channel = await db.discord_channels.find_one({"id": channel_id})
        return DiscordChannel(**updated_channel)
        
    except Exception as e:
        logger.error(f"Error updating Discord channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/channels/{channel_id}")
async def delete_discord_channel(channel_id: str):
    """Delete a saved Discord channel"""
    try:
        result = await db.discord_channels.delete_one({"id": channel_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        logger.info(f"Deleted Discord channel {channel_id}")
        return {"message": "Channel deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting Discord channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/channels/categories")
async def get_channel_categories():
    """Get all unique categories used by saved channels"""
    try:
        categories = await db.discord_channels.distinct("category")
        # Filter out None/empty categories  
        categories = [cat for cat in categories if cat and cat.strip()]
        return {"categories": sorted(categories)}
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return {"categories": []}

# Helper function to fetch Discord channel info
async def fetch_discord_channel_info(channel_id: str, bot_token: str):
    """Fetch channel information from Discord API"""
    try:
        import aiohttp
        
        headers = {
            'Authorization': f'Bot {bot_token}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            # Get channel info
            async with session.get(
                f'https://discord.com/api/v10/channels/{channel_id}',
                headers=headers
            ) as response:
                if response.status == 200:
                    channel_data = await response.json()
                    
                    result = {
                        'name': channel_data.get('name'),
                        'guild_id': channel_data.get('guild_id')
                    }
                    
                    # Get guild info if guild_id exists
                    if result['guild_id']:
                        async with session.get(
                            f'https://discord.com/api/v10/guilds/{result["guild_id"]}',
                            headers=headers
                        ) as guild_response:
                            if guild_response.status == 200:
                                guild_data = await guild_response.json()
                                result['guild_name'] = guild_data.get('name')
                    
                    return result
                else:
                    logger.warning(f"Discord API error {response.status} for channel {channel_id}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error fetching Discord channel info: {str(e)}")
        return None

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
