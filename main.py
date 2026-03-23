"""REITool — uvicorn entry point."""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="REITool",
    description="Commercial real estate property briefing API for New York State",
    version="0.1.0",
)

app.include_router(router)
