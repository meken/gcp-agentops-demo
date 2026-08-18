"""FastAPI application entrypoint for ADK Agent Runtime BYOC deployment."""

import os
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from app.agent import app as adk_app

# Enable OpenTelemetry cloud tracing when running on Agent Runtime
enable_telemetry = os.getenv("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true").lower() in ("true", "1", "yes")

# Build unified FastAPI app with ADK routes and reasoning engine contract
app: FastAPI = get_fast_api_app(
    adk_app,
    web=True,
    otel_to_cloud=enable_telemetry,
)

# Root health check endpoint
@app.get("/healthz")
async def health_check():
    return {"status": "HEALTHY", "service": "cymbal-retail-agent", "runtime": "agent_runtime_byoc"}
