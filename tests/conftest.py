import pytest
import asyncio
from pathlib import Path
import httpx
from httpx import ASGITransport

from app.config import settings
from app.database import db
from app.services import storage
from app.main import app

@pytest.fixture(scope="function")
def temp_env(tmp_path: Path):
    """Sets up an isolated database and download folder for each test."""
    temp_dir = tmp_path / "musichub_test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    db_file = temp_dir / "test.db"
    download_dir = temp_dir / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    # Patch settings
    settings.database_path = db_file
    settings.download_dir = download_dir
    settings.max_concurrent_downloads = 3
    settings.strict_320kbps = False

    # Initialize isolated database and storage
    original_db_path = db.db_path
    original_storage_dir = storage.base_dir

    db.db_path = db_file
    db._init_db()
    storage.base_dir = download_dir

    yield {
        "db": db,
        "storage": storage,
        "download_dir": download_dir,
        "db_file": db_file
    }

    db.db_path = original_db_path
    storage.base_dir = original_storage_dir

@pytest.fixture
async def async_client():
    """Async test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
