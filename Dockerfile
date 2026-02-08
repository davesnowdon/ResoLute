# ResoLute Docker Image
# Serves both the game frontend and backend API

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install backend
COPY agent/pyproject.toml agent/
COPY agent/src/ agent/src/
RUN pip install --no-cache-dir -e ./agent

# Copy pre-built game (must be built before docker build)
COPY build/web/ ./build/web/

# Environment configuration
ENV RESOLUTE_WEB_BUILD_PATH=/app/build/web
ENV RESOLUTE_HOST=0.0.0.0
ENV RESOLUTE_PORT=8000
ENV RESOLUTE_DATABASE_URL=sqlite:///data/resolute.db

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "resolute"]
