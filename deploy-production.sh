#!/bin/bash
# Production Deployment Script for TTS Bridge
# Replaces nginx placeholder with functional TTS bridge

set -e

echo "🚀 TTS Bridge Production Deployment"
echo "===================================="

# Extract API key from existing unmute service
echo "📋 Extracting API key from unmute service..."
KEY=$(docker service inspect -f '{{json .Spec.TaskTemplate.ContainerSpec.Env}}' unmute_unmute | tr -d '[]"' | tr , '\n' | grep '^OPENAI_API_KEY=' | cut -d= -f2-)

if [ -z "$KEY" ]; then
    echo "❌ Could not extract API key from unmute service"
    echo "Please provide API key manually:"
    read -s -p "Enter GROQ_API_KEY: " KEY
    echo
fi

echo "✅ API key obtained"

# Remove existing placeholder service
echo "🗑️  Removing existing TTS placeholder..."
docker service rm unmute_unmute_tts || true

echo "⏳ Waiting for service cleanup..."
sleep 3

# Deploy TTS bridge service
echo "🚀 Deploying TTS bridge service..."
docker service create \
  --name unmute_unmute_tts \
  --network unmute-net \
  --env GROQ_API_KEY="$KEY" \
  --env OPENAI_API_KEY="$KEY" \
  --env GROQ_TTS_MODEL=playai-tts \
  --env GROQ_TTS_VOICE=Ruby-PlayAI \
  --health-cmd "curl -f http://localhost:8080/api/build_info || exit 1" \
  --health-interval 30s \
  --health-timeout 10s \
  --health-retries 3 \
  --constraint 'node.role==manager' \
  intellipedia/inti-tts-groq-bridge:latest

echo "⏳ Waiting for service deployment..."
sleep 5

# Update Unmute to use TTS bridge
echo "🔧 Updating Unmute configuration..."
docker service update \
  --env-add KYUTAI_TTS_URL=ws://unmute_unmute_tts:8080 \
  --force unmute_unmute

echo "⏳ Waiting for Unmute update..."
sleep 3

# Verify deployment
echo "🔍 Verifying deployment..."

# Check service status
echo "📊 Service status:"
docker service ps unmute_unmute_tts --no-trunc

# Check logs
echo ""
echo "📝 Recent logs:"
docker service logs unmute_unmute_tts --tail 20

# Test health endpoint
echo ""
echo "🏥 Health check:"
sleep 2
if curl -s -f http://unmute_unmute_tts:8080/api/build_info > /dev/null 2>&1; then
    HEALTH_RESPONSE=$(curl -s http://unmute_unmute_tts:8080/api/build_info)
    echo "✅ Health check passed: $HEALTH_RESPONSE"
else
    echo "⚠️  Health check not yet available (service may still be starting)"
fi

# Check overall system health
echo ""
echo "🎯 Checking overall system health..."
sleep 2
if curl -s https://inti.intellipedia.ai/api/v1/health > /dev/null 2>&1; then
    SYSTEM_HEALTH=$(curl -s https://inti.intellipedia.ai/api/v1/health)
    echo "System health: $SYSTEM_HEALTH"
    
    # Check if TTS is up
    if echo "$SYSTEM_HEALTH" | grep -q '"tts_up":true'; then
        echo "🎉 SUCCESS: TTS service is now Up in system health!"
    else
        echo "⚠️  TTS service not yet showing as Up (may take a moment)"
    fi
else
    echo "⚠️  Could not reach system health endpoint"
fi

echo ""
echo "✅ TTS Bridge deployment complete!"
echo ""
echo "🎯 Next Steps:"
echo "1. Monitor logs: docker service logs unmute_unmute_tts --follow"
echo "2. Test voice workflow in PWA at https://inti.intellipedia.ai"
echo "3. Check system health: https://inti.intellipedia.ai/api/v1/health"
echo ""
echo "🔧 If issues occur:"
echo "- Check service status: docker service ps unmute_unmute_tts"
echo "- View logs: docker service logs unmute_unmute_tts"
echo "- Run test suite: see DEPLOYMENT.md"