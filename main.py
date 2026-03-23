"""REITool — uvicorn entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import router
from app.middleware.logging_middleware import RequestLoggingMiddleware

app = FastAPI(
    title="REITool",
    description="Commercial real estate property briefing API for New York State",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(router)


@app.get("/")
async def serve_frontend():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
