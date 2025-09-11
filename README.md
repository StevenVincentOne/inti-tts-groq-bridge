# Inti TTS Groq Bridge

WebSocket to HTTP bridge for Text-to-Speech integration between Unmute and Groq's TTS API.

## Overview

This bridge accepts WebSocket connections from the Unmute service, processes text synthesis requests, calls Groq's TTS API, and streams audio back via WebSocket. It follows the proven architecture pattern from the successful STT bridge implementation.

## Architecture

```
Unmute Service → TTS Bridge → Groq TTS API
    (WS)         (WS Server)     (HTTP POST)
                     ↓
              Audio Streaming ←─────────┘
```

## Features

- ✅ WebSocket server for Unmute integration
- ✅ Groq TTS API integration with authentication
- ✅ Real-time audio streaming with Base64 encoding
- ✅ Health endpoint for service discovery
- ✅ Comprehensive error handling and logging
- ✅ Docker containerization for production deployment

## Protocol

### WebSocket Input (from Unmute)
```json
{"text": "Hello, how are you?"}
```

### WebSocket Output (to Unmute)
```json
{
  "type": "audio",
  "audio_data": "<base64-encoded-mp3-audio>",
  "format": "mp3"
}
```

### Error Response
```json
{
  "type": "error",
  "message": "TTS synthesis failed"
}
```

## Configuration

### Environment Variables

- `GROQ_API_KEY` or `OPENAI_API_KEY`: Groq API key (required)
- `GROQ_TTS_MODEL`: TTS model name (default: `playai-tts`)
- `GROQ_TTS_VOICE`: Voice selection (default: `Ruby-PlayAI`)
- `GROQ_TTS_URL`: API endpoint (default: `https://api.groq.com/openai/v1/audio/speech`)
- `WS_PORT`: WebSocket port (default: `8080`)

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export GROQ_API_KEY="your_groq_api_key"

# Run bridge
python bridge.py
```

### Testing WebSocket Connection

```python
import asyncio
import websockets
import json

async def test_tts():
    uri = "ws://localhost:8080"
    async with websockets.connect(uri) as websocket:
        # Send text for synthesis
        message = {"text": "Hello, this is a test"}
        await websocket.send(json.dumps(message))
        
        # Receive audio response
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Response type: {data.get('type')}")
        print(f"Audio data length: {len(data.get('audio_data', ''))}")

# Run test
asyncio.run(test_tts())
```

### Health Check

```bash
curl http://localhost:8080/api/build_info
```

Expected response:
```json
{
  "status": "ok",
  "service": "tts-ws-groq-proxy",
  "version": "v1.0.0"
}
```

## Docker Deployment

### Build Image

```bash
docker build -t intellipedia/inti-tts-groq-bridge:latest .
```

### Run Container

```bash
docker run -d \
  --name tts-bridge \
  -p 8080:8080 \
  -e GROQ_API_KEY="your_api_key" \
  intellipedia/inti-tts-groq-bridge:latest
```

### Docker Swarm Deployment

```bash
docker service create \
  --name unmute_unmute_tts \
  --network unmute-net \
  --env GROQ_API_KEY="your_api_key" \
  --env GROQ_TTS_MODEL=playai-tts \
  --env GROQ_TTS_VOICE=Ruby-PlayAI \
  intellipedia/inti-tts-groq-bridge:latest
```

## Production Integration

### Unmute Configuration

Ensure Unmute service uses the TTS bridge:

```yaml
environment:
  - KYUTAI_TTS_URL=ws://unmute_unmute_tts:8080
```

### Service Health Monitoring

The bridge provides a health endpoint at `/api/build_info` that Unmute's health check system expects. This endpoint returns `200 OK` with service status information.

## Logging

The bridge provides comprehensive logging for monitoring and debugging:

- Connection tracking and client information
- Text synthesis requests and responses
- API call status and timing
- Error conditions and recovery
- Audio streaming metrics

## Audio Format

- **Input Format**: Text strings via JSON messages
- **Output Format**: MP3 audio encoded as Base64 strings
- **Sample Rate**: Optimized for 24kHz compatibility with Unmute
- **Streaming**: Currently single-chunk delivery (chunked streaming planned for future releases)

## Error Handling

- Groq API failures are handled gracefully with error responses
- WebSocket connection errors are logged and connections cleaned up properly  
- Invalid message formats are rejected with descriptive error messages
- Timeout handling for API calls prevents hanging connections

## Security

- Non-root user execution in Docker container
- API keys passed via environment variables (not hardcoded)
- Input validation for text synthesis requests
- Connection limits and resource management

## Monitoring

- Health check endpoint for service discovery
- Comprehensive logging for observability
- Connection counting and tracking
- Performance metrics in logs

## Future Enhancements

- [ ] Chunked audio streaming for lower latency
- [ ] Prometheus metrics export
- [ ] Voice selection per request
- [ ] Audio format negotiation
- [ ] Connection pooling optimization
- [ ] Rate limiting and backpressure handling

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check `GROQ_API_KEY` environment variable
2. **Connection refused**: Verify port 8080 is available and bridge is running
3. **Empty audio responses**: Check Groq API limits and text input validation
4. **WebSocket disconnections**: Monitor logs for connection errors and API timeouts

### Debug Mode

Enable debug logging:

```bash
export PYTHONPATH=/app
python -c "
import logging
logging.getLogger().setLevel(logging.DEBUG)
exec(open('bridge.py').read())
"
```

## License

This project is part of the Inti voice AI platform.