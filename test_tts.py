#!/usr/bin/env python3
"""
Comprehensive test suite for TTS Groq Bridge
Based on the successful STT bridge test pattern
"""

import asyncio
import json
import logging
import os
import base64
import websockets
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TTS_BRIDGE_HOST = os.environ.get("TTS_BRIDGE_HOST", "unmute_unmute_tts")
TTS_BRIDGE_PORT = int(os.environ.get("TTS_BRIDGE_PORT", "8080"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY or OPENAI_API_KEY required for testing")
    exit(1)


class TTSBridgeTestSuite:
    """Comprehensive test suite for TTS bridge functionality."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
    
    async def test_health_endpoint(self):
        """Test 1: Health endpoint availability and response format."""
        logger.info("🧪 Test 1: Health endpoint")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{TTS_BRIDGE_HOST}:{TTS_BRIDGE_PORT}/api/build_info"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "ok" and "tts" in data.get("service", "").lower():
                            logger.info(f"✅ PASS Health Endpoint: {data}")
                            self.tests_passed += 1
                            return True
                        else:
                            logger.error(f"❌ FAIL Health endpoint returned invalid data: {data}")
                    else:
                        logger.error(f"❌ FAIL Health endpoint returned {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ FAIL Health endpoint error: {e}")
        
        self.tests_failed += 1
        return False
    
    async def test_groq_api_direct(self):
        """Test 2: Direct Groq TTS API connectivity."""
        logger.info("🧪 Test 2: Groq TTS API Direct")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.groq.com/openai/v1/audio/speech"
                payload = {
                    "model": "playai-tts",
                    "input": "Test synthesis",
                    "voice": "Ruby-PlayAI",
                    "response_format": "mp3"
                }
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        if len(audio_data) > 0:
                            logger.info(f"✅ PASS Groq TTS Direct: Generated {len(audio_data)} bytes audio")
                            self.tests_passed += 1
                            return True
                        else:
                            logger.error("❌ FAIL Groq TTS returned empty audio")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ FAIL Groq TTS API {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ FAIL Groq TTS API error: {e}")
        
        self.tests_failed += 1
        return False
    
    async def test_websocket_tts(self):
        """Test 3: End-to-end WebSocket TTS synthesis."""
        logger.info("🧪 Test 3: WebSocket TTS Bridge")
        
        try:
            uri = f"ws://{TTS_BRIDGE_HOST}:{TTS_BRIDGE_PORT}/"
            
            async with websockets.connect(uri, timeout=10) as websocket:
                logger.info(f"Connected to TTS bridge at {uri}")
                
                # Send text synthesis request
                test_text = "Hello, this is a TTS test!"
                message = {"text": test_text}
                await websocket.send(json.dumps(message))
                logger.info(f"Sent text for synthesis: '{test_text}'")
                
                # Wait for audio response
                response_raw = await asyncio.wait_for(websocket.recv(), timeout=30)
                response = json.loads(response_raw)
                
                # Validate response format
                if response.get("type") == "audio":
                    audio_data = response.get("audio_data", "")
                    audio_format = response.get("format", "")
                    
                    if audio_data and audio_format:
                        # Validate base64 audio data
                        try:
                            audio_bytes = base64.b64decode(audio_data)
                            logger.info(f"✅ PASS WebSocket TTS: Got {len(audio_bytes)} bytes audio in {audio_format} format")
                            self.tests_passed += 1
                            return True
                        except Exception as decode_error:
                            logger.error(f"❌ FAIL Invalid base64 audio data: {decode_error}")
                    else:
                        logger.error(f"❌ FAIL Missing audio data or format in response: {response}")
                elif response.get("type") == "error":
                    logger.error(f"❌ FAIL Bridge returned error: {response.get('message')}")
                else:
                    logger.error(f"❌ FAIL Unexpected response format: {response}")
                    
        except asyncio.TimeoutError:
            logger.error("❌ FAIL WebSocket TTS test timed out")
        except Exception as e:
            logger.error(f"❌ FAIL WebSocket TTS error: {e}")
        
        self.tests_failed += 1
        return False
    
    async def test_error_handling(self):
        """Test 4: Error handling for invalid requests."""
        logger.info("🧪 Test 4: Error handling")
        
        try:
            uri = f"ws://{TTS_BRIDGE_HOST}:{TTS_BRIDGE_PORT}/"
            
            async with websockets.connect(uri, timeout=10) as websocket:
                # Test empty text
                message = {"text": ""}
                await websocket.send(json.dumps(message))
                
                response_raw = await asyncio.wait_for(websocket.recv(), timeout=10)
                response = json.loads(response_raw)
                
                if response.get("type") == "error":
                    logger.info(f"✅ PASS Error Handling: {response.get('message')}")
                    self.tests_passed += 1
                    return True
                else:
                    logger.error(f"❌ FAIL Expected error response, got: {response}")
                    
        except Exception as e:
            logger.error(f"❌ FAIL Error handling test failed: {e}")
        
        self.tests_failed += 1
        return False
    
    async def run_all_tests(self):
        """Run complete test suite."""
        logger.info("🧪 TTS Bridge Container Test Suite")
        logger.info("=" * 40)
        
        # Run all tests
        await self.test_health_endpoint()
        await self.test_groq_api_direct()
        await self.test_websocket_tts()
        await self.test_error_handling()
        
        # Summary
        total_tests = self.tests_passed + self.tests_failed
        logger.info("")
        logger.info(f"🏁 Overall: {self.tests_passed}/{total_tests} tests passed")
        
        if self.tests_failed == 0:
            logger.info("🎉 All tests passed! TTS bridge is working correctly.")
            return True
        else:
            logger.error(f"❌ {self.tests_failed} test(s) failed. Bridge needs fixes.")
            return False


async def main():
    """Run TTS bridge test suite."""
    test_suite = TTSBridgeTestSuite()
    
    logger.info(f"Testing TTS bridge at {TTS_BRIDGE_HOST}:{TTS_BRIDGE_PORT}")
    logger.info("Waiting 5 seconds for service to be ready...")
    await asyncio.sleep(5)
    
    success = await test_suite.run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())