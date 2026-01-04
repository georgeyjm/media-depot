FROM python:3.13-slim

# Install system dependencies
# yt-dlp may need ffmpeg for some operations
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen
RUN uv add psycopg-binary

# Copy application code
COPY . .

# Create directories for media and cache (if they don't exist)
# These will be mounted as volumes, but we create them for safety
RUN mkdir -p media .cache

# Expose port for FastAPI
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

