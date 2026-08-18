import os

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# Enable OpenTelemetry cloud tracing when running on Agent Runtime
enable_telemetry = os.getenv(
    "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true"
).lower() in ("true", "1", "yes")

# Base directory where agent folders are located
agents_dir = os.path.dirname(os.path.abspath(__file__))

# Build unified FastAPI app with ADK routes and reasoning engine contract
app: FastAPI = get_fast_api_app(
    agents_dir=agents_dir,
    web=True,
    otel_to_cloud=enable_telemetry,
)


# Root health check endpoint
@app.get("/healthz")
async def health_check():
    return {
        "status": "HEALTHY",
        "service": "cymbal-retail-agent",
        "runtime": "agent_runtime_byoc",
    }
