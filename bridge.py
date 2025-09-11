#!/usr/bin/env python3
"""
TTS Groq Bridge v2 - ServiceWithStartup Protocol Implementation

Implements Unmute's ServiceWithStartup protocol for proper service discovery.
Accepts WebSocket connections from Unmute, processes text synthesis requests,
calls Groq's TTS API, and streams audio back via WebSocket.

Service Discovery Protocol:
- Sends {"type": "ready"} on successful connection
- Sends {"type": "error", "message": "..."} when at capacity
- Implements proper startup handshake for find_instance mechanism

Data Flow:
- Input: Text via WebSocket from Unmute
- Output: Audio chunks via WebSocket to Unmute  
- API: HTTP POST to Groq's /v1/audio/speech endpoint
"""

import asyncio
import json
import logging
import base64
import os
from typing import Optional, Dict, Any
import websockets
import aiohttp
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
GROQ_TTS_URL = os.environ.get("GROQ_TTS_URL", "https://api.groq.com/openai/v1/audio/speech")
GROQ_TTS_MODEL = os.environ.get("GROQ_TTS_MODEL", "playai-tts")
GROQ_TTS_VOICE = os.environ.get("GROQ_TTS_VOICE", "Ruby-PlayAI")
WS_PORT = int(os.environ.get("WS_PORT", "8080"))

# Service discovery configuration
MAX_CONCURRENT_SESSIONS = int(os.environ.get("MAX_CONCURRENT_SESSIONS", "10"))
STARTUP_TIMEOUT = float(os.environ.get("STARTUP_TIMEOUT", "5.0"))

# Validate configuration
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY or OPENAI_API_KEY environment variable is required")
    exit(1)

logger.info(f"TTS Bridge v2 starting with model: {GROQ_TTS_MODEL}, voice: {GROQ_TTS_VOICE}")
logger.info(f"Service capacity: {MAX_CONCURRENT_SESSIONS} concurrent sessions")


class TTSBridge:
    """Text-to-Speech WebSocket bridge implementing ServiceWithStartup protocol."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.connection_count = 0
        self.active_sessions = 0
        self.is_running = True
    
    async def start_session(self):
        """Initialize HTTP session for Groq API calls."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("HTTP session initialized for Groq API")
    
    async def close_session(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP session closed")
    
    async def test_groq_api(self) -> bool:
        """
        Test Groq TTS API availability for service startup validation.
        
        Returns:
            True if API is available, False otherwise
        """
        if not self.session:
            await self.start_session()
        
        # Test with minimal request
        payload = {
            "model": GROQ_TTS_MODEL,
            "input": "test",
            "voice": GROQ_TTS_VOICE,
            "response_format": "mp3"
        }
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.debug("Testing Groq TTS API availability...")
            async with self.session.post(
                GROQ_TTS_URL, 
                json=payload, 
                headers=headers
            ) as response:
                if response.status == 200:
                    # Consume response to avoid connection issues
                    await response.read()
                    logger.info("Groq TTS API test successful")
                    return True
                else:
                    logger.error(f"Groq TTS API test failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Groq TTS API test error: {e}")
            return False
    
    async def synthesize_text(self, text: str) -> Optional[bytes]:
        """
        Call Groq TTS API to synthesize text into audio.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio bytes or None if failed
        """
        if not self.session:
            await self.start_session()
        
        payload = {
            "model": GROQ_TTS_MODEL,
            "input": text,
            "voice": GROQ_TTS_VOICE,
            "response_format": "mp3"  # Groq supports mp3, wav, flac, opus
        }
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            text_preview = text[:50] + ('...' if len(text) > 50 else '')
            logger.info(f"Synthesizing text: '{text_preview}'")
            
            async with self.session.post(
                GROQ_TTS_URL, 
                json=payload, 
                headers=headers
            ) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    logger.info(f"TTS success: {len(audio_data)} bytes audio generated")
                    return audio_data
                else:
                    error_text = await response.text()
                    logger.error(f"Groq TTS API error {response.status}: {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("Groq TTS API timeout")
            return None
        except Exception as e:
            logger.error(f"TTS API call failed: {e}")
            return None
    
    async def stream_audio_chunks(self, websocket: WebSocketServerProtocol, audio_data: bytes):
        """
        Stream audio data back to client in chunks to simulate real-time streaming.
        
        Args:
            websocket: WebSocket connection
            audio_data: Complete audio bytes to stream
        """
        # Convert to base64 for JSON transmission
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        # For now, send as single chunk. Future: implement chunked streaming
        response = {
            "type": "audio",
            "audio_data": audio_b64,
            "format": "mp3"
        }
        
        try:
            await websocket.send(json.dumps(response))
            logger.info(f"Streamed audio: {len(audio_b64)} base64 chars")
        except Exception as e:
            logger.error(f"Failed to stream audio: {e}")
    
    async def handle_text_message(self, websocket: WebSocketServerProtocol, message_data: Dict[str, Any]):
        """
        Handle text synthesis request from Unmute.
        
        Args:
            websocket: WebSocket connection
            message_data: Parsed JSON message
        """
        text = message_data.get("text", "").strip()
        
        if not text:
            logger.warning("Received empty text for synthesis")
            await self.send_error(websocket, "Empty text provided")
            return
        
        # Call Groq TTS API
        audio_data = await self.synthesize_text(text)
        
        if audio_data:
            # Stream audio back to client
            await self.stream_audio_chunks(websocket, audio_data)
        else:
            await self.send_error(websocket, "TTS synthesis failed")
    
    async def send_error(self, websocket: WebSocketServerProtocol, message: str):
        """Send error response to client."""
        error_response = {
            "type": "error",
            "message": message
        }
        try:
            await websocket.send(json.dumps(error_response))
            logger.info(f"Sent error: {message}")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def send_ready_message(self, websocket: WebSocketServerProtocol):
        """Send ready message for ServiceWithStartup protocol."""
        ready_message = {"type": "ready"}
        await websocket.send(json.dumps(ready_message))
        logger.info("Sent ready message to Unmute service discovery")
    
    async def send_capacity_error(self, websocket: WebSocketServerProtocol):
        """Send capacity error for ServiceWithStartup protocol."""
        error_message = {
            "type": "error", 
            "message": "Service at capacity"
        }
        await websocket.send(json.dumps(error_message))
        logger.warning(f"Sent capacity error - active sessions: {self.active_sessions}/{MAX_CONCURRENT_SESSIONS}")
    
    async def handle_websocket_connection(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle WebSocket connection from Unmute service with ServiceWithStartup protocol.
        
        Args:
            websocket: WebSocket connection
            path: Request path
        """
        self.connection_count += 1
        connection_id = self.connection_count
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        logger.info(f"TTS WebSocket connection #{connection_id} from {client_info}")
        
        try:
            # Implement ServiceWithStartup protocol
            if self.active_sessions >= MAX_CONCURRENT_SESSIONS:
                logger.warning(f"TTS service at capacity: {self.active_sessions}/{MAX_CONCURRENT_SESSIONS}")
                await self.send_capacity_error(websocket)
                return
            
            if not self.is_running:
                logger.error("TTS service not available")
                await self.send_error(websocket, "Service unavailable")
                return
            
            # Test Groq API availability before confirming ready
            if not await self.test_groq_api():
                logger.error("Groq TTS API not available")
                await self.send_error(websocket, "TTS API unavailable")
                return
            
            # Send ready message to complete startup handshake
            await self.send_ready_message(websocket)
            
            # Increment active session count
            self.active_sessions += 1
            logger.info(f"TTS session #{connection_id} started - active: {self.active_sessions}/{MAX_CONCURRENT_SESSIONS}")
            
            # Handle TTS requests
            async for message in websocket:
                try:
                    # Parse JSON message
                    if isinstance(message, str):
                        message_data = json.loads(message)
                        
                        # Handle text synthesis request
                        if "text" in message_data:
                            await self.handle_text_message(websocket, message_data)
                        else:
                            logger.warning(f"Unknown message format: {message_data}")
                            await self.send_error(websocket, "Invalid message format")
                    else:
                        logger.warning(f"Received non-text message: {type(message)}")
                        await self.send_error(websocket, "Text messages only")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    await self.send_error(websocket, "Invalid JSON")
                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    await self.send_error(websocket, "Message processing failed")
                    
        except ConnectionClosed:
            logger.info(f"TTS WebSocket connection #{connection_id} closed by client")
        except WebSocketException as e:
            logger.error(f"WebSocket error on connection #{connection_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error on connection #{connection_id}: {e}")
        finally:
            # Decrement active session count
            if self.active_sessions > 0:
                self.active_sessions -= 1
            logger.info(f"TTS WebSocket connection #{connection_id} ended - active: {self.active_sessions}/{MAX_CONCURRENT_SESSIONS}")


async def health_check_handler(path, request_headers):
    """
    Handle HTTP health check requests.
    Returns 200 OK for /api/build_info endpoint.
    """
    if path == "/api/build_info":
        health_response = {
            "status": "ok",
            "service": "tts-ws-groq-proxy-v2",
            "version": "v2.0.0",
            "protocol": "ServiceWithStartup"
        }
        
        response_body = json.dumps(health_response).encode('utf-8')
        response_headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body))),
        ]
        
        logger.debug("Health check: 200 OK")
        return (200, response_headers, response_body)
    
    # Reject non-health HTTP requests
    return None


async def main():
    """Start the TTS WebSocket bridge server."""
    tts_bridge = TTSBridge()
    
    try:
        logger.info(f"Starting TTS Groq Bridge v2 on port {WS_PORT}")
        logger.info(f"Health endpoint: http://localhost:{WS_PORT}/api/build_info")
        logger.info(f"WebSocket endpoint: ws://localhost:{WS_PORT}/")
        logger.info(f"ServiceWithStartup protocol enabled")
        
        # Start WebSocket server with health check support
        server = await websockets.serve(
            tts_bridge.handle_websocket_connection,
            "0.0.0.0",
            WS_PORT,
            process_request=health_check_handler,  # Handle HTTP health checks
            ping_interval=20,
            ping_timeout=10,
        )
        
        logger.info("TTS Bridge v2 server started successfully")
        
        # Keep server running
        await server.wait_closed()
        
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise
    finally:
        # Cleanup
        await tts_bridge.close_session()
        logger.info("TTS Bridge v2 server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        exit(1)