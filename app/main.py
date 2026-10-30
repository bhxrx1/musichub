from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .database import db
    from .config import load_persisted_settings
    load_persisted_settings(db)
    settings.ensure_directories()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MusicHub — Unified Music Discovery & Resumable Download Manager",
    lifespan=lifespan
)

# CORS middleware for local desktop integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API
app.include_router(api_router)

# Mount Static UI
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = static_dir / "index.html"
    return FileResponse(index_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
