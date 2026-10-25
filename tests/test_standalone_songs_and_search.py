import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.providers.pagalnew_provider import PagalnewMusicProvider
from app.providers.mock_provider import MockMusicProvider
from app.models.domain import Track, QualityOption, SearchResultItem

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "pagalnew"

@pytest.fixture
def search_html():
    with open(FIXTURE_DIR / "search_awarapan.html", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def song_html():
    with open(FIXTURE_DIR / "song_yeh_awarapan.html", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def song_single_quality_html():
    with open(FIXTURE_DIR / "song_single_quality.html", "r", encoding="utf-8") as f:
        return f.read()

# 1. Search item classification
def test_search_classification_album_vs_track(search_html):
    provider = PagalnewMusicProvider()
    results = provider.parse_search_html(search_html)

    albums = [r for r in results if r.item_type == "album"]
    tracks = [r for r in results if r.item_type == "track"]

    assert len(albums) > 0, "Expected at least one album in search results"
    assert len(tracks) > 0, "Expected at least one track in search results"

    for alb in albums:
        assert alb.item_type == "album"
        assert alb.id is not None
        assert alb.title is not None
        assert alb.provider == "pagalnew"

    for trk in tracks:
        assert trk.item_type == "track"
        assert trk.id is not None
        assert trk.title is not None
        assert trk.provider == "pagalnew"

# 2. Standalone track parsing and metadata verification
def test_standalone_track_metadata_parsing(song_html):
    provider = PagalnewMusicProvider()
    track = provider.parse_track_html("yeh-awarapan", song_html)

    assert track.id == "yeh-awarapan"
    assert "Yeh Awarapan" in track.title
    assert "Arijit Singh" in track.artists
    assert track.album_title == "Awarapan 2"
    assert track.album_id == "awarapan-2-2026"

    # Bitrate qualities
    bitrates = [q.bitrate_kbps for q in track.qualities]
    assert 320 in bitrates
    assert 128 in bitrates
    assert track.artwork_url is not None

# 3. GET /api/tracks/{provider}/{track_id} endpoint
@pytest.mark.asyncio
async def test_get_track_details_endpoint(async_client):
    res = await async_client.get("/api/tracks/mock/mock-trk-101")
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == "mock-trk-101"
    assert data["title"] == "Yeh Awarapan"
    assert "Arijit Singh" in data["artists"]
    assert len(data["qualities"]) >= 2
    assert any(q["bitrate_kbps"] == 320 for q in data["qualities"])

# 4. Standalone song download enqueuing without an album page
@pytest.mark.asyncio
async def test_standalone_song_download_enqueuing_with_custom_release(async_client, temp_env):
    req_body = {
        "provider": "mock",
        "album_id": None,
        "album_title": "Indipop Singles 2026",
        "track_id": "mock-trk-101",
        "bitrate": 320,
        "strict_320k": False
    }

    res = await async_client.post("/api/downloads/start", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert "task_id" in data

    # Check queue to confirm task state and album title preservation
    queue_res = await async_client.get("/api/downloads/queue")
    assert queue_res.status_code == 200
    queue_data = queue_res.json()
    task = next((t for t in queue_data["tasks"] if t["task_id"] == data["task_id"]), None)
    assert task is not None
    assert task["album_title"] == "Indipop Singles 2026"
    assert task["selected_bitrate"] == 320

# 5. Standalone song download defaulting to "Singles" folder when album unknown
@pytest.mark.asyncio
async def test_standalone_song_download_default_singles_folder(async_client, temp_env):
    req_body = {
        "provider": "mock",
        "album_id": None,
        "album_title": None,
        "track_id": "mock-trk-single-01",
        "bitrate": 320,
        "strict_320k": False
    }

    res = await async_client.post("/api/downloads/start", json=req_body)
    assert res.status_code == 200
    data = res.json()

    queue_res = await async_client.get("/api/downloads/queue")
    queue_data = queue_res.json()
    task = next((t for t in queue_data["tasks"] if t["task_id"] == data["task_id"]), None)
    assert task is not None
    assert task["album_title"] == "Singles"

# 6. Standalone song strict 320k skip behavior
@pytest.mark.asyncio
async def test_standalone_song_strict_320k_rejection(async_client, temp_env):
    # Track with only 128 kbps available
    track_128 = Track(
        id="single-128-only",
        provider="mock",
        title="Lo-Fi Single",
        artists=["Indie Artist"],
        album_id="unknown",
        album_title="Singles",
        qualities=[QualityOption(bitrate_kbps=128, download_url="http://mock.test/128.mp3", format="mp3")]
    )

    with patch.object(MockMusicProvider, "get_track", return_value=track_128):
        req_body = {
            "provider": "mock",
            "album_id": None,
            "album_title": "Singles",
            "track_id": "single-128-only",
            "bitrate": 320,
            "strict_320k": True
        }

        res = await async_client.post("/api/downloads/start", json=req_body)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SKIPPED_QUALITY"
        assert "Strict 320 kbps" in data["error_message"]

        # Verify task is recorded as skipped in queue
        queue_res = await async_client.get("/api/downloads/queue")
        queue_data = queue_res.json()
        saved_task = next((t for t in queue_data["tasks"] if t["task_id"] == data["task_id"]), None)
        assert saved_task is not None
        assert saved_task["status"] == "SKIPPED_QUALITY"

# 7. Search Clear All safety & scope verification
@pytest.mark.asyncio
async def test_search_and_clear_scope_does_not_affect_history_or_queue(async_client, temp_env):
    # 1. Enqueue a task
    req_body = {
        "provider": "mock",
        "album_id": "mock-alb-01",
        "track_id": "mock-trk-101",
        "bitrate": 320,
        "strict_320k": False
    }
    start_res = await async_client.post("/api/downloads/start", json=req_body)
    assert start_res.status_code == 200
    task_id = start_res.json()["task_id"]

    # 2. Perform search queries
    search_res = await async_client.get("/api/search?q=Awarapan")
    assert search_res.status_code == 200

    # 3. Verify queue is completely intact
    queue_res = await async_client.get("/api/downloads/queue")
    assert queue_res.status_code == 200
    queue_tasks = queue_res.json()["tasks"]
    assert any(t["task_id"] == task_id for t in queue_tasks)

    # 4. Verify history is intact
    hist_res = await async_client.get("/api/downloads/history")
    assert hist_res.status_code == 200
