# Build custom container for Agent Runtime BYOC deployment
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental \
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=EVENT_ONLY \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies using uv sync
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-cache --no-install-project

# Copy application files
COPY app/ ./app/
COPY fast_api_app.py .

EXPOSE 8080

# Start FastAPI server for Agent Runtime
CMD ["uvicorn", "fast_api_app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
