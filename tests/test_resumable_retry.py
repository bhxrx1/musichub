import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch
import httpx
from httpx import ASGITransport

from app.main import app
from app.config import settings
from app.models.domain import Album, Track, QualityOption, DownloadStatus
from app.services.download_manager import DownloadManager
from app.services.storage import storage
from app.database import db

@pytest.mark.asyncio
async def test_resumable_download_mock_cdn(temp_env):
    """Verifies actual HTTP Range resumable download against the local mock cdn stream."""
    dm = DownloadManager()

    track = Track(
        id="resume-trk",
        album_id="resume-alb",
        provider="mock",
        title="Resumable Test Song",
        artists=["Tester"],
        track_number=1,
        qualities=[
            QualityOption(
                bitrate_kbps=128,
                format="mp3",
                download_url="http://testserver/mock-cdn/stream/resume-trk/128",
                is_confirmed_320k=False
            )
        ]
    )
    album = Album(id="resume-alb", provider="mock", title="Resume Album", tracks=[track])

    # 1. Simulate partial download: write 1024 bytes directly to the .part file first
    final_path = storage.resolve_track_path(
        artist="Tester",
        album="Resume Album",
        track_title="Resumable Test Song",
        bitrate_kbps=128,
        track_num=1
    )
    part_path = storage.get_partial_path(final_path)
    part_path.parent.mkdir(parents=True, exist_ok=True)
    with open(part_path, "wb") as f:
        f.write(b"ID3\x04" + (b"\x00" * 1020))

    initial_part_size = part_path.stat().st_size
    assert initial_part_size == 1024

    # 2. Use ASGITransport client inside DownloadManager
    transport = ASGITransport(app=app)
    original_client_cls = httpx.AsyncClient
    
    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    with patch("app.services.download_manager.httpx.AsyncClient", side_effect=client_factory):
        task = await dm.enqueue_track(track, album, preferred_bitrate=128, strict_320k=False)
        
        # Wait for worker completion
        for _ in range(30):
            await asyncio.sleep(0.1)
            t = db.get_task(task.task_id)
            if t and t.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
                break

    task_result = db.get_task(task.task_id)
    assert task_result is not None
    assert task_result.status == DownloadStatus.COMPLETED
    assert final_path.exists()
    assert not part_path.exists()
    assert final_path.stat().st_size > initial_part_size

@pytest.mark.asyncio
async def test_bounded_retry_exhaustion_marks_failed(temp_env):
    """Verifies that persistent HTTP errors trigger retries and finally fail when exhausted."""
    # Temporarily lower backoff factor for fast test execution
    original_factor = settings.retry_backoff_factor
    settings.retry_backoff_factor = 0.02
    
    try:
        dm = DownloadManager()

        track = Track(
            id="fail-trk",
            album_id="fail-alb",
            provider="mock",
            title="Failing Song",
            artists=["Error Artist"],
            qualities=[
                QualityOption(
                    bitrate_kbps=320,
                    format="mp3",
                    download_url="http://testserver/mock-cdn/stream/fail-trk/320",
                    is_confirmed_320k=True
                )
            ]
        )
        album = Album(id="fail-alb", provider="mock", title="Fail Album", tracks=[track])

        class MockStreamContext:
            async def __aenter__(self):
                raise httpx.ConnectError("Connection refused by test mock")
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        class MockFailingClient:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            def stream(self, *args, **kwargs):
                return MockStreamContext()

        with patch("app.services.download_manager.httpx.AsyncClient", side_effect=MockFailingClient):
            task = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)

            # Wait for retries to exhaust
            for _ in range(40):
                await asyncio.sleep(0.05)
                t = db.get_task(task.task_id)
                if t and t.status in (DownloadStatus.FAILED, DownloadStatus.COMPLETED):
                    break

        final_task = db.get_task(task.task_id)
        assert final_task is not None
        assert final_task.status == DownloadStatus.FAILED
        assert "ConnectError" in (final_task.error_message or "")
    finally:
        settings.retry_backoff_factor = original_factor
