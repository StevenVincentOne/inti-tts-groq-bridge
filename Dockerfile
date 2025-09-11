FROM python:3.12-slim

LABEL maintainer="Inti Ops <ops@intellipedia.ai>"
LABEL description="TTS WebSocket to Groq API Bridge"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bridge application
COPY bridge.py .

# Create non-root user for security
RUN useradd -r -s /bin/false ttsbridge
USER ttsbridge

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/build_info || exit 1

# Start the bridge
CMD ["python", "bridge.py"]