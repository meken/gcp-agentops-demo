FROM python:3.13-slim

WORKDIR /app

# Copy uv binary directly from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install only production dependencies into .venv (cached layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-cache --no-install-project --no-dev

# Environment configuration for Cloud Run / Agent Runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental \
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=EVENT_ONLY \
    GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true \
    GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false

# Copy application source code
COPY retail_agent/ ./retail_agent/
COPY fast_api_app.py .

# Create and switch to unprivileged user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "exec uv run --no-sync uvicorn fast_api_app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
