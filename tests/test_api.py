import pytest

@pytest.mark.asyncio
async def test_api_serve_frontend(async_client):
    res = await async_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "MusicHub" in res.text

@pytest.mark.asyncio
async def test_api_search_endpoint(async_client):
    res = await async_client.get("/api/search?q=Rockstar")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] >= 1
    assert any("Rockstar" in item["title"] for item in data["results"])

@pytest.mark.asyncio
async def test_api_get_album_and_track(async_client):
    # Valid album
    res = await async_client.get("/api/albums/mock/mock-alb-01")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Awarapan 2"
    assert len(data["tracks"]) >= 3

    # Invalid album
    res_404 = await async_client.get("/api/albums/mock/non-existent-alb")
    assert res_404.status_code == 404

    # Valid track
    res_trk = await async_client.get("/api/tracks/mock/mock-trk-101")
    assert res_trk.status_code == 200
    trk_data = res_trk.json()
    assert trk_data["title"] == "Yeh Awarapan"

@pytest.mark.asyncio
async def test_api_downloads_endpoints(async_client, temp_env):
    # 1. Enqueue download
    req_body = {
        "provider": "mock",
        "album_id": "mock-alb-01",
        "track_id": "mock-trk-101",
        "bitrate": 320,
        "strict_320k": False
    }
    start_res = await async_client.post("/api/downloads/start", json=req_body)
    assert start_res.status_code == 200
    task_data = start_res.json()
    assert task_data["task_id"] is not None

    # 2. Check queue
    queue_res = await async_client.get("/api/downloads/queue")
    assert queue_res.status_code == 200
    q_data = queue_res.json()
    assert len(q_data["tasks"]) >= 1

    # 3. Cancel task
    cancel_res = await async_client.post(f"/api/downloads/{task_data['task_id']}/cancel")
    assert cancel_res.status_code == 200

@pytest.mark.asyncio
async def test_api_batch_download_endpoint(async_client, temp_env):
    req_body = {
        "provider": "mock",
        "album_id": "mock-alb-01",
        "track_ids": ["mock-trk-101", "mock-trk-102"],
        "preferred_bitrate": 320,
        "strict_320k": False
    }
    res = await async_client.post("/api/downloads/batch", json=req_body)
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 2

@pytest.mark.asyncio
async def test_api_settings_and_diagnostics(async_client, temp_env):
    # Diagnostics
    diag_res = await async_client.get("/api/diagnostics/providers")
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    assert len(diag_data) >= 1
    assert any(d["provider_id"] == "mock" and d["healthy"] for d in diag_data)

    # Get settings
    get_res = await async_client.get("/api/settings")
    assert get_res.status_code == 200

    # Update settings
    post_res = await async_client.post("/api/settings", json={"max_concurrent_downloads": 5, "strict_320kbps": True})
    assert post_res.status_code == 200
    updated = post_res.json()
    assert updated["max_concurrent_downloads"] == 5
    assert updated["strict_320kbps"] is True

@pytest.mark.asyncio
async def test_mock_cdn_stream(async_client):
    # Full content
    res_full = await async_client.get("/mock-cdn/stream/test/128")
    assert res_full.status_code == 200
    assert res_full.headers["accept-ranges"] == "bytes"
    assert int(res_full.headers["content-length"]) > 0

    # Range content
    res_range = await async_client.get("/mock-cdn/stream/test/128", headers={"Range": "bytes=0-1023"})
    assert res_range.status_code == 206
    assert res_range.headers["content-range"].startswith("bytes 0-1023/")
    assert len(res_range.content) == 1024
