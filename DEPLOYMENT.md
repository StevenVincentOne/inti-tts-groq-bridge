# TTS Groq Bridge - Production Deployment Guide

Based on the successful STT and LLM proxy deployment patterns.

## Quick Deploy (Production Ready)

### Prerequisites
- Docker Swarm cluster running
- `unmute-net` overlay network created
- Valid Groq API key

### 1. Deploy from Docker Hub (Recommended)

```bash
# Extract API key from existing service
KEY=$(docker service inspect -f '{{json .Spec.TaskTemplate.ContainerSpec.Env}}' unmute_unmute | tr -d '[]"' | tr , '\n' | grep '^OPENAI_API_KEY=' | cut -d= -f2-)

# Remove existing placeholder service
docker service rm unmute_unmute_tts || true

# Deploy production TTS bridge
docker service create \
  --name unmute_unmute_tts \
  --network unmute-net \
  --env GROQ_API_KEY="$KEY" \
  --env OPENAI_API_KEY="$KEY" \
  --env GROQ_TTS_MODEL=playai-tts \
  --env GROQ_TTS_VOICE=Ruby-PlayAI \
  --health-cmd="curl -f http://localhost:8080/api/build_info || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  intellipedia/inti-tts-groq-bridge:latest
```

### 2. Verify Deployment

```bash
# Check service status
docker service ps unmute_unmute_tts --no-trunc

# Check logs
docker service logs unmute_unmute_tts --tail 50

# Test health endpoint
curl -s http://unmute_unmute_tts:8080/api/build_info | jq .
# Expected: {"status":"ok","service":"tts-ws-groq-proxy","version":"v1.0.0"}

# Verify Unmute can reach TTS service
docker service logs unmute_unmute --tail 100 | grep -i tts
```

### 3. Update Unmute Configuration

Ensure Unmute service points to the TTS bridge:

```bash
# Update Unmute to use TTS bridge
docker service update \
  --env-add KYUTAI_TTS_URL=ws://unmute_unmute_tts:8080 \
  --force unmute_unmute
```

## Development Deployment

### Build from Source

```bash
# Clone repository
git clone https://github.com/StevenVincentOne/inti-tts-groq-bridge.git
cd inti-tts-groq-bridge

# Build image locally  
docker build -t intellipedia/inti-tts-groq-bridge:latest .

# Deploy locally built image
docker service create \
  --name unmute_unmute_tts \
  --network unmute-net \
  --env GROQ_API_KEY="your_api_key" \
  intellipedia/inti-tts-groq-bridge:latest
```

## Testing & Validation

### Automated Test Suite

```bash
# Build test container
docker build -f Dockerfile.test -t tts-test .

# Run comprehensive tests
docker service create \
  --name tts-test-service \
  --network unmute-net \
  --env GROQ_API_KEY="$KEY" \
  --restart-condition none \
  tts-test

# Check results
docker service logs tts-test-service
# Expected: "🎉 All tests passed! TTS bridge is working correctly."

# Cleanup
docker service rm tts-test-service
```

### Manual Testing

```bash
# Test WebSocket connection with Python
python3 -c "
import asyncio
import websockets
import json

async def test():
    async with websockets.connect('ws://unmute_unmute_tts:8080/') as ws:
        await ws.send(json.dumps({'text': 'Hello test'}))
        response = await ws.recv()
        data = json.loads(response)
        print(f'Response: {data.get(\"type\")} - {len(data.get(\"audio_data\", \"\"))} chars')

asyncio.run(test())
"
```

## Integration with Existing Stack

### Complete Swarm Service Update

Replace the placeholder TTS service in your existing swarm deployment:

```yaml
# In your swarm-deploy.yml, replace the nginx TTS service with:
unmute_tts:
  image: intellipedia/inti-tts-groq-bridge:latest
  environment:
    - GROQ_API_KEY=${GROQ_API_KEY}
    - GROQ_TTS_MODEL=playai-tts
    - GROQ_TTS_VOICE=Ruby-PlayAI
  networks:
    - unmute-net
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/api/build_info"]
    interval: 30s
    timeout: 10s
    retries: 3
  deploy:
    update_config:
      order: start-first
```

### Service Discovery Integration

The TTS bridge provides the `/api/build_info` endpoint that Unmute's health check system expects:

```python
# Unmute health check will call:
GET http://unmute_unmute_tts:8080/api/build_info

# Expected response:
{
  "status": "ok",
  "service": "tts-ws-groq-proxy", 
  "version": "v1.0.0"
}
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Groq API key (required) |
| `OPENAI_API_KEY` | - | Alternative API key variable |
| `GROQ_TTS_MODEL` | `playai-tts` | TTS model name |
| `GROQ_TTS_VOICE` | `Ruby-PlayAI` | Voice selection |
| `GROQ_TTS_URL` | `https://api.groq.com/openai/v1/audio/speech` | API endpoint |
| `WS_PORT` | `8080` | WebSocket port |

### Groq Voice Options

Available voices for `GROQ_TTS_VOICE`:
- `Ruby-PlayAI` (default)
- `Alloy-PlayAI`
- `Echo-PlayAI` 
- `Fable-PlayAI`
- `Onyx-PlayAI`
- `Nova-PlayAI`
- `Shimmer-PlayAI`

## Monitoring & Observability

### Health Monitoring

```bash
# Continuous health monitoring
watch -n 5 'docker service ps unmute_unmute_tts && echo && curl -s http://unmute_unmute_tts:8080/api/build_info'

# Log monitoring
docker service logs unmute_unmute_tts --follow
```

### Key Log Patterns

**Healthy Operation:**
```
INFO - TTS Bridge server started successfully
INFO - TTS WebSocket connection #1 from 10.0.1.5:45678
INFO - Synthesizing text: 'Hello, how are you?'
INFO - TTS success: 15243 bytes audio generated  
INFO - Streamed audio: 20324 base64 chars
```

**Error Conditions:**
```
ERROR - Groq TTS API error 401: Invalid API key
ERROR - TTS API call failed: Connection timeout
ERROR - Failed to stream audio: Connection closed
```

## Troubleshooting

### Common Issues

1. **Service Not Starting**
   ```bash
   # Check Docker service events
   docker service ps unmute_unmute_tts --no-trunc
   
   # Check container logs
   docker service logs unmute_unmute_tts
   ```

2. **401 API Errors**
   ```bash
   # Verify API key is set
   docker service inspect -f '{{json .Spec.TaskTemplate.ContainerSpec.Env}}' unmute_unmute_tts | jq .
   
   # Test API key manually
   curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
   ```

3. **WebSocket Connection Issues**
   ```bash
   # Check if service is reachable
   docker exec -it $(docker ps -q --filter name=unmute_unmute) curl http://unmute_unmute_tts:8080/api/build_info
   
   # Check network connectivity
   docker network ls | grep unmute-net
   ```

4. **Audio Generation Failures**
   ```bash
   # Monitor TTS logs during test
   docker service logs unmute_unmute_tts --follow &
   
   # Test with simple text
   python3 -c "
   import asyncio, websockets, json
   async def test():
       async with websockets.connect('ws://unmute_unmute_tts:8080/') as ws:
           await ws.send(json.dumps({'text': 'test'}))
           resp = await ws.recv()
           print(json.loads(resp))
   asyncio.run(test())
   "
   ```

### Performance Optimization

For high-load environments:

```bash
# Deploy with resource constraints and scaling
docker service update \
  --replicas 2 \
  --limit-cpu 0.5 \
  --limit-memory 512M \
  --reserve-cpu 0.1 \
  --reserve-memory 128M \
  unmute_unmute_tts
```

## Rollback Procedure

If issues occur, rollback to nginx placeholder:

```bash
# Remove TTS bridge
docker service rm unmute_unmute_tts

# Deploy nginx placeholder (temporary)
docker service create \
  --name unmute_unmute_tts \
  --network unmute-net \
  nginx:alpine

# Restore will require nginx config for /api/build_info endpoint
```

## Success Criteria

✅ **Deployment Successful When:**
- Service status shows 1/1 replicas running
- Health check returns 200 OK with proper JSON
- WebSocket connections accepted and processed
- Text synthesis returns audio data
- Unmute health panel shows "TTS: Up"
- End-to-end voice workflow functional

The TTS bridge follows the proven architecture patterns from STT and LLM services, ensuring consistent operation and maintainability.