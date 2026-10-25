import pytest
import os
from pathlib import Path
import httpx

from app.providers.pagalnew_provider import PagalnewMusicProvider
from app.models.domain import DownloadStatus

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "pagalnew"

@pytest.fixture
def search_html():
    with open(FIXTURE_DIR / "search_awarapan.html", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def album_html():
    with open(FIXTURE_DIR / "album_awarapan_2.html", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def song_html():
    with open(FIXTURE_DIR / "song_yeh_awarapan.html", "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def song_single_quality_html():
    with open(FIXTURE_DIR / "song_single_quality.html", "r", encoding="utf-8") as f:
        return f.read()

def test_parse_search_html(search_html):
    provider = PagalnewMusicProvider()
    results = provider.parse_search_html(search_html)

    assert len(results) >= 6
    # Check album result
    album_res = next((r for r in results if r.item_type == "album" and "Awarapan 2" in r.title), None)
    assert album_res is not None
    assert album_res.id == "awarapan-2-2026"
    assert album_res.year == 2026
    assert album_res.artwork_url is not None
    assert "pagalnew.com" in album_res.artwork_url

    # Check track result
    track_res = next((r for r in results if r.item_type == "track" and "Yeh Awarapan" in r.title), None)
    assert track_res is not None
    assert track_res.id == "yeh-awarapan"
    assert "Arijit Singh" in track_res.artists
    assert track_res.album_title == "Awarapan 2"

def test_parse_album_html(album_html):
    provider = PagalnewMusicProvider()
    album = provider.parse_album_html("awarapan-2-2026", album_html)

    assert album is not None
    assert album.id == "awarapan-2-2026"
    assert album.title == "Awarapan 2"
    assert album.year == 2026
    assert "Arijit Singh" in album.artists
    assert "Jubin Nautiyal" in album.artists
    assert "Emraan Hashmi" in album.starcast
    assert album.composer is not None
    assert "Mithoon" in album.composer
    assert album.artwork_url is not None
    assert "awarapan-2-2026-500-500.jpg" in album.artwork_url

    # Tracklist verification
    assert len(album.tracks) == 8
    t1 = album.tracks[0]
    assert t1.title == "Laado"
    assert "Jubin Nautiyal" in t1.artists

    t_yeh = next((t for t in album.tracks if t.title == "Yeh Awarapan"), None)
    assert t_yeh is not None
    assert "Arijit Singh" in t_yeh.artists

def test_parse_track_html_and_quality_options(song_html):
    provider = PagalnewMusicProvider()
    track = provider.parse_track_html("yeh-awarapan", song_html)

    assert track is not None
    assert track.id == "yeh-awarapan"
    assert track.title == "Yeh Awarapan"
    assert "Arijit Singh" in track.artists
    assert track.composer == "Amaal Mallik"
    assert track.album_id == "awarapan-2-2026"

    # Quality options verification
    assert len(track.qualities) == 2
    q320 = next((q for q in track.qualities if q.bitrate_kbps == 320), None)
    assert q320 is not None
    assert q320.is_confirmed_320k is True
    assert "320-download/54291" in q320.download_url

    q128 = next((q for q in track.qualities if q.bitrate_kbps == 128), None)
    assert q128 is not None
    assert q128.is_confirmed_320k is False
    assert "128-downloads/54291" in q128.download_url

    # Quality policy tests on real parsed track
    best = track.get_best_quality(prefer_320k=True, strict_320k=True)
    assert best is not None
    assert best.bitrate_kbps == 320

def test_track_strict_mode_with_single_quality(song_single_quality_html):
    provider = PagalnewMusicProvider()
    track = provider.parse_track_html("yeh-awarapan-128", song_single_quality_html)

    assert track is not None
    # 320k is not available in this fixture
    assert all(q.bitrate_kbps < 320 for q in track.qualities)

    # 1. Strict 320k mode must return None (skips track)
    strict_best = track.get_best_quality(prefer_320k=True, strict_320k=True)
    assert strict_best is None

    # 2. Non-strict mode must fall back to 128 kbps
    fallback_best = track.get_best_quality(prefer_320k=True, strict_320k=False)
    assert fallback_best is not None
    assert fallback_best.bitrate_kbps == 128

@pytest.mark.asyncio
async def test_pagalnew_provider_mock_transport(search_html, album_html, song_html, temp_env):
    """Tests end-to-end provider methods using httpx.MockTransport with fixture HTML."""
    def handler(request: httpx.Request):
        url = str(request.url)
        if "search.php" in url:
            return httpx.Response(200, text=search_html)
        elif "/album/awarapan-2-2026.html" in url:
            return httpx.Response(200, text=album_html)
        elif "/songs/" in url:
            return httpx.Response(200, text=song_html)
        elif url.rstrip("/") == "https://pagalnew.com":
            return httpx.Response(200, text="OK")
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://pagalnew.com") as client:
        provider = PagalnewMusicProvider(http_client=client)

        # 1. Search
        search_results = await provider.search("Awarapan")
        assert len(search_results) > 0
        assert any(r.id == "awarapan-2-2026" for r in search_results)

        # 2. Get Album (with parallel track enrichment)
        album = await provider.get_album("awarapan-2-2026")
        assert album is not None
        assert album.title == "Awarapan 2"
        assert len(album.tracks) == 8
        # Ensure track qualities were enriched
        assert len(album.tracks[0].qualities) > 0

        # 3. Get Track
        track = await provider.get_track("yeh-awarapan")
        assert track is not None
        assert track.title == "Yeh Awarapan"

        # 4. Connection test
        diag = await provider.test_connection()
        assert diag.healthy is True
        assert diag.latency_ms >= 0

@pytest.mark.asyncio
async def test_pagalnew_error_handling(temp_env):
    """Ensures provider handles 404, 500, and network failures gracefully."""
    def error_handler(request: httpx.Request):
        url = str(request.url)
        if "404" in url:
            return httpx.Response(404, text="Not Found")
        elif "500" in url:
            return httpx.Response(500, text="Internal Server Error")
        raise httpx.ConnectError("Connection drop simulation")

    transport = httpx.MockTransport(error_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = PagalnewMusicProvider(http_client=client)

        # Search handles errors
        results = await provider.search("trigger-network-error")
        assert results == []

        # Album handles 404
        album_404 = await provider.get_album("album-404")
        assert album_404 is None

        # Track handles 500
        track_500 = await provider.get_track("track-500")
        assert track_500 is None

        # Diagnostic handles failure
        diag = await provider.test_connection()
        assert diag.healthy is False
        assert "Connection failed" in diag.message
