import pytest
import asyncio
from pathlib import Path
from app.models.domain import Album, Track, QualityOption, DownloadStatus
from app.services.download_manager import DownloadManager
from app.database import db

@pytest.mark.asyncio
async def test_queue_enqueue_and_strict_skip(temp_env):
    dm = DownloadManager()

    # Track with only 128k
    track = Track(
        id="t-128",
        album_id="a-1",
        provider="mock",
        title="Only 128",
        artists=["Singer"],
        qualities=[
            QualityOption(bitrate_kbps=128, format="mp3", download_url="http://testserver/mock-cdn/stream/t-128/128", is_confirmed_320k=False)
        ]
    )
    album = Album(id="a-1", provider="mock", title="Album 1", tracks=[track])

    # 1. Enqueue with strict_320k = True
    skipped_task = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=True)
    assert skipped_task.status == DownloadStatus.SKIPPED_QUALITY
    assert "Strict 320 kbps" in (skipped_task.error_message or "")

    # Task is persisted in database
    saved = db.get_task(skipped_task.task_id)
    assert saved is not None
    assert saved.status == DownloadStatus.SKIPPED_QUALITY

    # 2. Enqueue with strict_320k = False (fallback to 128)
    queued_task = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)
    assert queued_task.selected_bitrate == 128
    assert queued_task.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)

@pytest.mark.asyncio
async def test_batch_enqueue(temp_env):
    dm = DownloadManager()

    t1 = Track(
        id="bt-1",
        album_id="ba-1",
        provider="mock",
        title="Batch Song 1",
        artists=["Artist A"],
        qualities=[QualityOption(bitrate_kbps=320, format="mp3", download_url="http://testserver/mock-cdn/stream/bt-1/320", is_confirmed_320k=True)]
    )
    t2 = Track(
        id="bt-2",
        album_id="ba-1",
        provider="mock",
        title="Batch Song 2",
        artists=["Artist B"],
        qualities=[QualityOption(bitrate_kbps=320, format="mp3", download_url="http://testserver/mock-cdn/stream/bt-2/320", is_confirmed_320k=True)]
    )
    album = Album(id="ba-1", provider="mock", title="Batch Album", tracks=[t1, t2])

    tasks = await dm.enqueue_batch(album, [t1, t2], preferred_bitrate=320, strict_320k=False)
    assert len(tasks) == 2
    assert tasks[0].track_id == "bt-1"
    assert tasks[1].track_id == "bt-2"

@pytest.mark.asyncio
async def test_task_cancellation(temp_env):
    dm = DownloadManager()

    track = Track(
        id="cancel-trk",
        album_id="cancel-alb",
        provider="mock",
        title="To Be Cancelled",
        artists=["Artist C"],
        qualities=[QualityOption(bitrate_kbps=320, format="mp3", download_url="http://testserver/mock-cdn/stream/cancel-trk/320", is_confirmed_320k=True)]
    )
    album = Album(id="cancel-alb", provider="mock", title="Cancel Album", tracks=[track])

    task = await dm.enqueue_track(track, album, preferred_bitrate=320, strict_320k=False)
    
    # Cancel the task
    cancelled = dm.cancel_task(task.task_id)
    assert cancelled is True

    # Check state in db
    updated = db.get_task(task.task_id)
    assert updated.status == DownloadStatus.CANCELLED
