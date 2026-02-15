# ResoLute Docker Image
# Serves both the game frontend and backend API

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies directly (no hatch in production)
COPY agent/pyproject.toml agent/
RUN pip install --no-cache-dir hatch && \
    cd agent && \
    hatch dep show requirements > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip uninstall -y hatch && \
    rm /tmp/requirements.txt

# Copy the backend source
COPY agent/src/ agent/src/

# Copy the pre-built Godot web export
COPY build/web/ build/web/

# Environment configuration
ENV PYTHONPATH=/app/agent/src
ENV RESOLUTE_WEB_BUILD_PATH=/app/build/web
ENV RESOLUTE_HOST=0.0.0.0
ENV RESOLUTE_PORT=8000
ENV RESOLUTE_DATABASE_URL=sqlite:///data/resolute.db

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "resolute.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
