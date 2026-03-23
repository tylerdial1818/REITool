"""REITool — uvicorn entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="REITool",
    description="Commercial real estate property briefing API for New York State",
    version="0.1.0",
)


# Routes will be included here once implemented
# from app.api.routes import router
# app.include_router(router)
