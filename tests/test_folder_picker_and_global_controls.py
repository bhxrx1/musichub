import asyncio
import time
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.database import db
from app.models.domain import DownloadTask, DownloadStatus, Album, Track, QualityOption
from app.services.download_manager import download_manager
from app.services.storage import storage
from app.services.folder_picker import validate_directory_path, open_native_folder_picker
from app.providers.pagalnew_provider import parse_pagination_info, get_category_path

@pytest.mark.asyncio
async def test_validate_directory_path(temp_env):
    tmp_path = temp_env["download_dir"]

    # Valid absolute directory
    valid, msg, res_path = validate_directory_path(str(tmp_path))
    assert valid is True
    assert res_path == tmp_path.resolve()

    # Subdirectory that needs creation
    new_subdir = tmp_path / "music_library_sub"
    valid, msg, res_path = validate_directory_path(str(new_subdir))
    assert valid is True
    assert new_subdir.exists()

    # Relative path should fail
    valid, msg, res_path = validate_directory_path("relative/path/downloads")
    assert valid is False
    assert "Path must be an absolute Windows path" in msg

    # Empty string should fail
    valid, msg, res_path = validate_directory_path("")
    assert valid is False

    # Reserved Windows device names should fail
    valid, msg, res_path = validate_directory_path("C:\\Music\\CON\\tracks")
    assert valid is False
    assert "reserved Windows device name" in msg

    valid, msg, res_path = validate_directory_path("C:\\Music\\NUL")
    assert valid is False
    assert "reserved Windows device name" in msg

    # Illegal wildcard characters should fail
    valid, msg, res_path = validate_directory_path("C:\\Music\\*\\tracks")
    assert valid is False
    assert "illegal character" in msg

@pytest.mark.asyncio
async def test_settings_folder_validation_and_update(temp_env):
    tmp_path = temp_env["download_dir"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid directory path
        res_invalid = await client.post("/api/settings", json={
            "download_dir": "relative/path"
        })
        assert res_invalid.status_code == 400
        assert "Path must be an absolute Windows path" in res_invalid.json()["detail"]

        # Valid directory path
        new_dir = tmp_path / "valid_musichub_dir"
        res_valid = await client.post("/api/settings", json={
            "download_dir": str(new_dir)
        })
        assert res_valid.status_code == 200
        data = res_valid.json()
        assert Path(data["download_dir"]).resolve() == new_dir.resolve()
        assert storage.base_dir == new_dir.resolve()
        assert new_dir.exists()

@pytest.mark.asyncio
async def test_browse_folder_endpoint(temp_env, monkeypatch):
    tmp_path = temp_env["download_dir"]
    def mock_picker(initial_dir=None):
        return {
            "selected_path": str(tmp_path.resolve()),
            "cancelled": False,
            "available": True,
            "error": None
        }

    monkeypatch.setattr("app.api.routes_settings.open_native_folder_picker", mock_picker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/settings/browse-folder", json={"current_path": str(tmp_path)})
        assert res.status_code == 200
        data = res.json()
        assert data["selected_path"] == str(tmp_path.resolve())
        assert data["cancelled"] is False
        assert data["available"] is True

@pytest.mark.asyncio
async def test_global_pause_and_resume_all(temp_env):
    alb_id = f"pause-alb-{uuid.uuid4().hex[:6]}"
    alb = Album(
        id=alb_id,
        provider="mock",
        title="Pause Test Album",
        year=2026,
        tracks=[
            Track(
                id=f"track-pause-{uuid.uuid4().hex[:6]}",
                album_id=alb_id,
                provider="mock",
                title=f"Pause Song {i}",
                artists=["Test Artist"],
                track_number=i,
                qualities=[
                    QualityOption(
                        bitrate_kbps=320,
                        format="mp3",
                        download_url=f"http://127.0.0.1:8000/mock-cdn/stream/pause-{i}/320",
                        file_size_bytes=5000000,
                        is_confirmed_320k=True
                    )
                ]
            )
            for i in range(1, 4)
        ]
    )

    tasks = await download_manager.enqueue_batch(album=alb, tracks=alb.tracks)
    assert len(tasks) == 3

    # Pause All
    affected = download_manager.pause_all()
    assert affected >= 1
    assert download_manager.is_paused is True

    # Check tasks in DB are now PAUSED
    paused_tasks = db.get_tasks_by_status([DownloadStatus.PAUSED])
    assert len(paused_tasks) >= 3

    # Ensure enqueuing while globally paused sets task to PAUSED directly
    t_extra = await download_manager.enqueue_track(track=alb.tracks[0], album=alb)
    assert t_extra.status == DownloadStatus.PAUSED

    # Resume All
    resumed_count = await download_manager.resume_all()
    assert resumed_count >= 3
    assert download_manager.is_paused is False

    # Check status changed from PAUSED
    paused_remaining = db.get_tasks_by_status([DownloadStatus.PAUSED])
    assert len(paused_remaining) == 0

@pytest.mark.asyncio
async def test_active_download_cancellation(temp_env):
    """Verifies cancellation during active network transfer stops cleanly and unlinks partial .part file."""
    tmp_path = temp_env["download_dir"]
    target_file = tmp_path / "Active Cancel Album" / "Cancelled Song.mp3"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    part_file = storage.get_partial_path(target_file)
    part_file.write_bytes(b"A" * 1024 * 100) # 100 KB partial data
    assert part_file.exists()

    task_id = f"test-active-cancel-{uuid.uuid4().hex}"
    now = time.time()
    task = DownloadTask(
        task_id=task_id,
        track_id="t-cancel-1",
        album_id="a-cancel-1",
        provider="mock",
        title="Cancelled Song",
        artist="Test Singer",
        album_title="Active Cancel Album",
        selected_bitrate=320,
        download_url="http://127.0.0.1:8000/mock-cdn/stream/t-cancel-1/320",
        target_file_path=str(target_file),
        status=DownloadStatus.DOWNLOADING,
        total_bytes=1000000,
        downloaded_bytes=102400,
        created_at=now,
        updated_at=now
    )
    db.save_task(task)

    # Cancel task
    cancelled = download_manager.cancel_task(task_id)
    assert cancelled is True

    # Assert status is CANCELLED and .part file is unlinked
    updated_task = db.get_task(task_id)
    assert updated_task.status == DownloadStatus.CANCELLED
    assert not part_file.exists()

@pytest.mark.asyncio
async def test_global_cancel_all(temp_env):
    alb_id = f"cancel-all-{uuid.uuid4().hex[:6]}"
    alb = Album(
        id=alb_id,
        provider="mock",
        title="Cancel All Album",
        year=2026,
        tracks=[
            Track(
                id=f"track-cancel-all-{uuid.uuid4().hex[:6]}",
                album_id=alb_id,
                provider="mock",
                title=f"Cancel Song {i}",
                artists=["Artist"],
                track_number=i,
                qualities=[
                    QualityOption(
                        bitrate_kbps=320,
                        format="mp3",
                        download_url=f"http://127.0.0.1:8000/mock-cdn/stream/cancel-all-{i}/320",
                        file_size_bytes=4000000,
                        is_confirmed_320k=True
                    )
                ]
            )
            for i in range(1, 3)
        ]
    )

    tasks = await download_manager.enqueue_batch(album=alb, tracks=alb.tracks)
    assert len(tasks) == 2

    # Global Cancel All
    affected = download_manager.cancel_all()
    assert affected >= 2

    active_tasks = db.get_tasks_by_status([DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED])
    assert len(active_tasks) == 0

@pytest.mark.asyncio
async def test_pagination_html_parsing():
    # Page 1 with next page and >> link to page 5
    html_page_1 = """
    <div class="pagination"><br/><br/>
      <a href="https://pagalnew.com/category/bollywood-tracks">&lt;&lt;</a>
      <b><a class="currentactive">1</a></b>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/2/2026">2</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/3/2026">3</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/4/2026">4</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/5/2026">&gt;&gt;</a>
    </div>
    """
    info1 = parse_pagination_info(html_page_1, current_page=1)
    assert info1["current_page"] == 1
    assert info1["has_prev"] is False
    assert info1["has_next"] is True
    assert info1["total_pages"] == 5

    # Page 5 (last page: no >> link, active is 5)
    html_page_5 = """
    <div class="pagination"><br/><br/>
      <a href="https://pagalnew.com/category/bollywood-tracks">&lt;&lt;</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/2/2026">2</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/3/2026">3</a>
      <a href="https://pagalnew.com/category/bollywood-mp3-songs/4/2026">4</a>
      <b><a class="currentactive">5</a></b>
    </div>
    """
    info5 = parse_pagination_info(html_page_5, current_page=5)
    assert info5["current_page"] == 5
    assert info5["has_prev"] is True
    assert info5["has_next"] is False
    assert info5["total_pages"] == 5

    # Single page without pagination bar
    html_no_pag = "<div class='content'>No pagination</div>"
    info_none = parse_pagination_info(html_no_pag, current_page=1)
    assert info_none["current_page"] == 1
    assert info_none["has_prev"] is False
    assert info_none["has_next"] is False
    assert info_none["total_pages"] == 1

@pytest.mark.asyncio
async def test_category_paths():
    assert get_category_path("bollywood-2026", 1) == "/category/bollywood-mp3-songs/1/2026"
    assert get_category_path("bollywood-2026", 3) == "/category/bollywood-mp3-songs/3/2026"
    assert get_category_path("bollywood-2025", 2) == "/category/bollywood-mp3-songs/2/2025"
    assert get_category_path("indipop", 2) == "/category/indipop-mp3-songs/2"
    assert get_category_path("punjabi", 4) == "/category/punjabi-mp3-songs/4"

@pytest.mark.asyncio
async def test_browse_endpoint_with_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mock provider page 1
        res1 = await client.get("/api/browse/mock/bollywood-2026?page=1")
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["category"] == "bollywood-2026"
        assert d1["current_page"] == 1
        assert d1["has_prev"] is False
        assert len(d1["items"]) > 0

        # Mock provider page 2 (out of bounds for mock)
        res2 = await client.get("/api/browse/mock/bollywood-2026?page=2")
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["current_page"] == 2
        assert d2["has_prev"] is True
        assert d2["has_next"] is False
        assert len(d2["items"]) == 0
