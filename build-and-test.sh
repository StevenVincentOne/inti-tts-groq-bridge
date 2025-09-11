#!/bin/bash
# TTS Bridge Build and Test Script
# Usage: ./build-and-test.sh [API_KEY]

set -e

API_KEY=${1:-$GROQ_API_KEY}
if [ -z "$API_KEY" ]; then
    echo "Error: API key required"
    echo "Usage: ./build-and-test.sh [API_KEY]"
    echo "Or set GROQ_API_KEY environment variable"
    exit 1
fi

echo "🔨 Building TTS Bridge..."
docker build -t intellipedia/inti-tts-groq-bridge:latest .

echo "🔨 Building test container..."
docker build -f Dockerfile.test -t tts-test .

echo "🧪 Testing TTS Bridge locally..."

# Start bridge in background
echo "Starting TTS bridge container..."
CONTAINER_ID=$(docker run -d --name tts-bridge-test \
    -p 8080:8080 \
    -e GROQ_API_KEY="$API_KEY" \
    intellipedia/inti-tts-groq-bridge:latest)

# Wait for startup
echo "Waiting for bridge to start..."
sleep 5

# Run tests
echo "Running test suite..."
docker run --rm \
    --network container:tts-bridge-test \
    -e GROQ_API_KEY="$API_KEY" \
    -e TTS_BRIDGE_HOST=localhost \
    tts-test

# Cleanup
echo "🧹 Cleaning up..."
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID

echo "✅ Build and test complete!"
echo "Ready for production deployment."