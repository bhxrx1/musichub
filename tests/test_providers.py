import pytest
from app.providers.mock_provider import MockMusicProvider
from app.providers.registry import ProviderRegistry

@pytest.mark.asyncio
async def test_mock_provider_search():
    provider = MockMusicProvider()
    
    # 1. Search by Movie/Album title
    results_album = await provider.search("Rockstar")
    assert any(r.item_type == "album" and "Rockstar" in r.title for r in results_album)

    # 2. Search by Artist
    results_artist = await provider.search("Arijit")
    assert any("Arijit" in ", ".join(r.artists) for r in results_artist)

    # 3. Search by Composer
    results_composer = await provider.search("Rahman")
    assert any(r.composer and "Rahman" in r.composer for r in results_composer)

    # 4. Search by Song Title
    results_song = await provider.search("Yeh Awarapan")
    assert any(r.item_type == "track" and "Yeh Awarapan" in r.title for r in results_song)

    # 5. Search by Year
    results_year = await provider.search("2026")
    assert any(r.year == 2026 for r in results_year)

@pytest.mark.asyncio
async def test_mock_provider_get_album_and_track():
    provider = MockMusicProvider()
    
    album = await provider.get_album("mock-alb-01")
    assert album is not None
    assert album.title == "Awarapan 2"
    assert len(album.tracks) >= 3

    track = await provider.get_track("mock-trk-101")
    assert track is not None
    assert track.title == "Yeh Awarapan"
    assert len(track.qualities) >= 2

@pytest.mark.asyncio
async def test_provider_registry():
    registry = ProviderRegistry()
    providers = registry.list_providers()
    assert len(providers) >= 1
    assert any(p.id == "mock" for p in providers)

    diag = await registry.get("mock").test_connection()
    assert diag.healthy is True
    assert diag.latency_ms >= 0
