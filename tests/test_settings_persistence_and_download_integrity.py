import asyncio
import os
import time
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest

from app.config import settings, load_persisted_settings
from app.database import db
from app.models.domain import Album, Track, QualityOption, DownloadStatus
from app.services.download_manager import DownloadManager
from app.services.storage import storage, safe_replace_file, safe_unlink_file

@pytest.mark.asyncio
async def test_settings_persistence_lifecycle(async_client, temp_env):
    """Verifies that changing settings via API persists in SQLite and survives app re-initialization."""
    test_db = temp_env["db"]
    new_dir = temp_env["download_dir"] / "custom_music"
    new_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initially concurrency is 3
    assert settings.max_concurrent_downloads == 3

    # 2. Update settings: change concurrency to 10, set custom download dir, enable strict mode
    res = await async_client.post("/api/settings", json={
        "max_concurrent_downloads": 10,
        "download_dir": str(new_dir),
        "strict_320kbps": True,
        "preferred_bitrate_kbps": 320,
        "pagalnew_base_url": "https://custom.pagalnew.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["max_concurrent_downloads"] == 10
    assert data["download_dir"] == str(new_dir.resolve())
    assert data["strict_320kbps"] is True

    # 3. Verify SQLite app_settings table directly
    all_stored = test_db.get_all_settings()
    assert all_stored["max_concurrent_downloads"] == "10"
    assert all_stored["strict_320kbps"] == "true"
    assert all_stored["pagalnew_base_url"] == "https://custom.pagalnew.com"

    # 4. Partial update: changing only one setting must NOT overwrite or erase others
    res2 = await async_client.post("/api/settings", json={
        "strict_320kbps": False
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["strict_320kbps"] is False
    assert data2["max_concurrent_downloads"] == 10  # Preserved!
    assert data2["download_dir"] == str(new_dir.resolve())  # Preserved!

    # 5. Simulate application restart: reset in-memory settings to defaults, then call load_persisted_settings
    settings.max_concurrent_downloads = 3
    settings.strict_320kbps = True
    load_persisted_settings(test_db)

    # Verify restored settings
    assert settings.max_concurrent_downloads == 10
    assert settings.strict_320kbps is False
    assert str(settings.download_dir) == str(new_dir.resolve())
    assert settings.pagalnew_base_url == "https://custom.pagalnew.com"

    # 6. Verify GET /api/settings returns the restored settings
    res3 = await async_client.get("/api/settings")
    assert res3.status_code == 200
    cfg = res3.json()
    assert cfg["max_concurrent_downloads"] == 10
    assert cfg["strict_320kbps"] is False
    assert cfg["download_dir"] == str(new_dir.resolve())

@pytest.mark.asyncio
async def test_duplicate_track_enqueue_deduplication(temp_env):
    """Verifies that enqueuing the exact same track does not spawn competing concurrent workers."""
    dm = DownloadManager()

    track = Track(
        id="dedup-trk-1",
        album_id="dedup-alb-1",
        provider="mock",
        title="Deduplication Song",
        artists=["Artist D"],
        qualities=[QualityOption(bitrate_kbps=320, format="mp3", download_url="http://testserver/mock-cdn/stream/dedup-1/320", is_confirmed_320k=True)]
    )
    album = Album(id="dedup-alb-1", provider="mock", title="Dedup Album", tracks=[track])

    # Enqueue first time
    task1 = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)
    assert task1.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)

    # Enqueue same track second time while task1 is active
    task2 = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)

    # Must return the existing task, preventing duplicate workers
    assert task2.task_id == task1.task_id

@pytest.mark.asyncio
async def test_progress_percent_clamping(temp_env):
    """Verifies that progress_pct is strictly clamped between 0% and 100% even if byte count anomalies occur."""
    task = db.get_task("nonexistent")
    track = Track(
        id="clamp-trk",
        album_id="clamp-alb",
        provider="mock",
        title="Clamping Test Song",
        artists=["Singer"],
        qualities=[QualityOption(bitrate_kbps=320, format="mp3", download_url="http://testserver/mock-cdn/stream/clamp-1/320", is_confirmed_320k=True)]
    )
    album = Album(id="clamp-alb", provider="mock", title="Clamp Album", tracks=[track])

    dm = DownloadManager()
    t = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)
    t.total_bytes = 1000

    # Normal progress
    t.downloaded_bytes = 500
    assert t.progress_pct == 50.0

    # Oversized downloaded_bytes (e.g. from an old bug)
    t.downloaded_bytes = 1705
    assert t.progress_pct == 100.0  # Clamped to 100.0!

    # Negative downloaded bytes
    t.downloaded_bytes = -50
    assert t.progress_pct == 0.0

@pytest.mark.asyncio
async def test_safe_replace_and_unlink_file_windows(tmp_path):
    """Verifies safe_replace_file and safe_unlink_file handle file operations atomically and cleanly."""
    work_dir = tmp_path / "file_test"
    work_dir.mkdir()

    src = work_dir / "test.part"
    dst = work_dir / "test.mp3"

    src.write_bytes(b"AudioDataV1")
    assert src.exists()

    # 1. Replace when dst does not exist
    safe_replace_file(src, dst)
    assert not src.exists()
    assert dst.exists()
    assert dst.read_bytes() == b"AudioDataV1"

    # 2. Replace when dst already exists
    src2 = work_dir / "test2.part"
    src2.write_bytes(b"AudioDataV2")
    safe_replace_file(src2, dst)
    assert not src2.exists()
    assert dst.read_bytes() == b"AudioDataV2"

    # 3. Safe unlink
    assert safe_unlink_file(dst) is True
    assert not dst.exists()
    # Safe unlink on non-existent file returns True
    assert safe_unlink_file(dst) is True

@pytest.mark.asyncio
async def test_destination_lock_prevents_overlap(temp_env):
    """Verifies that destination locks prevent two tasks from targeting the same file path concurrently."""
    dm = DownloadManager()
    target = str(temp_env["download_dir"] / "Song.mp3")

    lock1 = await dm._get_destination_lock(target)
    lock2 = await dm._get_destination_lock(target)
    assert lock1 is lock2  # Identical lock object for identical resolved path

    acquired_order = []

    async def worker(worker_id: int):
        async with await dm._get_destination_lock(target):
            acquired_order.append(f"{worker_id}_enter")
            await asyncio.sleep(0.05)
            acquired_order.append(f"{worker_id}_exit")

    await asyncio.gather(worker(1), worker(2))

    # Locks must execute sequentially: enter -> exit -> enter -> exit
    assert acquired_order[1] == f"{acquired_order[0][0]}_exit"
