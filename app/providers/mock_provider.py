import time
from typing import List, Optional, Dict
from .base import BaseMusicProvider
from ..models.domain import Album, Track, QualityOption, SearchResultItem
from ..models.schemas import ProviderDiagnosticResponse, CategoryBrowseResponse
from ..config import settings

MOCK_ALBUMS: Dict[str, Album] = {}
MOCK_TRACKS: Dict[str, Track] = {}

def _init_mock_catalogue():
    # Album 1: Awarapan 2 (2026) - Bollywood
    alb1_tracks = [
        Track(
            id="mock-trk-101",
            album_id="mock-alb-01",
            provider="mock",
            title="Yeh Awarapan",
            artists=["Arijit Singh"],
            composer="Amaal Mallik",
            duration_seconds=275,
            track_number=1,
            artwork_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop",
            qualities=[
                QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-101/128", file_size_bytes=4400000, is_confirmed_320k=False),
                QualityOption(bitrate_kbps=320, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-101/320", file_size_bytes=11000000, is_confirmed_320k=True),
            ]
        ),
        Track(
            id="mock-trk-102",
            album_id="mock-alb-01",
            provider="mock",
            title="Laado",
            artists=["Jubin Nautiyal"],
            composer="Mithoon",
            duration_seconds=240,
            track_number=2,
            artwork_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop",
            qualities=[
                QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-102/128", file_size_bytes=3800000, is_confirmed_320k=False),
                QualityOption(bitrate_kbps=320, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-102/320", file_size_bytes=9600000, is_confirmed_320k=True),
            ]
        ),
        Track(
            id="mock-trk-103",
            album_id="mock-alb-01",
            provider="mock",
            title="Tera Mera Rishta (Acoustic)",
            artists=["Saaj Bhatt", "Subodhh Sharma"],
            composer="Jeet Gannguli",
            duration_seconds=210,
            track_number=3,
            artwork_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop",
            # This track deliberately has ONLY 128 kbps to test strict-320k mode behavior
            qualities=[
                QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-103/128", file_size_bytes=3300000, is_confirmed_320k=False),
            ]
        ),
    ]

    alb1 = Album(
        id="mock-alb-01",
        provider="mock",
        title="Awarapan 2",
        year=2026,
        artists=["Arijit Singh", "Jubin Nautiyal", "Saaj Bhatt"],
        composer="Mithoon, Amaal Mallik, Jeet Gannguli",
        starcast=["Emraan Hashmi", "Disha Patani"],
        language="Hindi",
        artwork_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop",
        tracks=alb1_tracks
    )

    # Album 2: Rockstar (2011) - AR Rahman
    alb2_tracks = [
        Track(
            id="mock-trk-201",
            album_id="mock-alb-02",
            provider="mock",
            title="Kun Faya Kun",
            artists=["A.R. Rahman", "Javed Ali", "Mohit Chauhan"],
            composer="A.R. Rahman",
            duration_seconds=473,
            track_number=1,
            artwork_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500&auto=format&fit=crop",
            qualities=[
                QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-201/128", file_size_bytes=7500000, is_confirmed_320k=False),
                QualityOption(bitrate_kbps=320, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-201/320", file_size_bytes=18900000, is_confirmed_320k=True),
            ]
        ),
        Track(
            id="mock-trk-202",
            album_id="mock-alb-02",
            provider="mock",
            title="Nadaan Parindey",
            artists=["Mohit Chauhan", "A.R. Rahman"],
            composer="A.R. Rahman",
            duration_seconds=386,
            track_number=2,
            artwork_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500&auto=format&fit=crop",
            qualities=[
                QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-202/128", file_size_bytes=6100000, is_confirmed_320k=False),
                QualityOption(bitrate_kbps=320, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-202/320", file_size_bytes=15400000, is_confirmed_320k=True),
            ]
        )
    ]

    alb2 = Album(
        id="mock-alb-02",
        provider="mock",
        title="Rockstar",
        year=2011,
        artists=["Mohit Chauhan", "A.R. Rahman", "Javed Ali"],
        composer="A.R. Rahman",
        starcast=["Ranbir Kapoor", "Nargis Fakhri"],
        language="Hindi",
        artwork_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500&auto=format&fit=crop",
        tracks=alb2_tracks
    )

    MOCK_ALBUMS[alb1.id] = alb1
    MOCK_ALBUMS[alb2.id] = alb2

    single_track = Track(
        id="mock-trk-single-01",
        album_id="unknown",
        provider="mock",
        title="Tum Hi Aana (Single)",
        artists=["Jubin Nautiyal"],
        composer="Payal Dev",
        duration_seconds=245,
        track_number=1,
        artwork_url="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop",
        qualities=[
            QualityOption(bitrate_kbps=128, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-single-01/128", file_size_bytes=3900000, is_confirmed_320k=False),
            QualityOption(bitrate_kbps=320, format="mp3", download_url=f"http://127.0.0.1:{settings.port}/mock-cdn/stream/mock-trk-single-01/320", file_size_bytes=9800000, is_confirmed_320k=True),
        ]
    )

    for t in alb1_tracks + alb2_tracks + [single_track]:
        MOCK_TRACKS[t.id] = t

_init_mock_catalogue()

class MockMusicProvider(BaseMusicProvider):
    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def provider_name(self) -> str:
        return "Local Mock Provider"

    @property
    def supports_batch_download(self) -> bool:
        return True

    async def search(self, query: str, search_type: str = "all") -> List[SearchResultItem]:
        q = query.lower().strip()
        results: List[SearchResultItem] = []

        if not q:
            # Return all albums as default view
            for alb in MOCK_ALBUMS.values():
                results.append(SearchResultItem(
                    id=alb.id,
                    provider=self.provider_id,
                    item_type="album",
                    title=alb.title,
                    album_title=alb.title,
                    year=alb.year,
                    artists=alb.artists,
                    composer=alb.composer,
                    artwork_url=alb.artwork_url,
                    track_count=len(alb.tracks),
                    album_id=alb.id
                ))
            return results

        # 1. Search Albums
        for alb in MOCK_ALBUMS.values():
            album_match = (
                q in alb.title.lower() or
                (alb.composer and q in alb.composer.lower()) or
                (alb.year and q == str(alb.year)) or
                any(q in a.lower() for a in alb.artists) or
                any(q in s.lower() for s in alb.starcast)
            )
            if album_match:
                results.append(SearchResultItem(
                    id=alb.id,
                    provider=self.provider_id,
                    item_type="album",
                    title=alb.title,
                    album_title=alb.title,
                    year=alb.year,
                    artists=alb.artists,
                    composer=alb.composer,
                    artwork_url=alb.artwork_url,
                    track_count=len(alb.tracks),
                    album_id=alb.id
                ))

        # 2. Search Individual Tracks
        for trk in MOCK_TRACKS.values():
            parent_alb = MOCK_ALBUMS.get(trk.album_id)
            track_match = (
                q in trk.title.lower() or
                (trk.composer and q in trk.composer.lower()) or
                any(q in a.lower() for a in trk.artists)
            )
            if track_match:
                results.append(SearchResultItem(
                    id=trk.id,
                    provider=self.provider_id,
                    item_type="track",
                    title=trk.title,
                    album_title=parent_alb.title if parent_alb else None,
                    year=parent_alb.year if parent_alb else None,
                    artists=trk.artists,
                    composer=trk.composer,
                    artwork_url=trk.artwork_url,
                    album_id=trk.album_id
                ))

        return results

    async def browse_category(self, category_key: str = "bollywood-2026", page: int = 1) -> CategoryBrowseResponse:
        """Browse mock category with pagination support."""
        if page == 1:
            items = []
            for alb in MOCK_ALBUMS.values():
                items.append(SearchResultItem(
                    id=alb.id,
                    provider=self.provider_id,
                    item_type="album",
                    title=alb.title,
                    album_title=alb.title,
                    year=alb.year,
                    artists=alb.artists,
                    composer=alb.composer,
                    artwork_url=alb.artwork_url,
                    track_count=len(alb.tracks),
                    album_id=alb.id
                ))
            return CategoryBrowseResponse(
                category=category_key,
                current_page=1,
                has_next=False,
                has_prev=False,
                total_pages=1,
                items=items
            )
        return CategoryBrowseResponse(
            category=category_key,
            current_page=page,
            has_next=False,
            has_prev=True,
            total_pages=1,
            items=[]
        )

    async def get_album(self, album_id: str) -> Optional[Album]:
        return MOCK_ALBUMS.get(album_id)

    async def get_track(self, track_id: str) -> Optional[Track]:
        return MOCK_TRACKS.get(track_id)

    async def test_connection(self) -> ProviderDiagnosticResponse:
        start = time.perf_counter()
        count = len(MOCK_ALBUMS)
        latency = (time.perf_counter() - start) * 1000
        return ProviderDiagnosticResponse(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            healthy=True,
            latency_ms=round(latency, 2),
            message=f"Mock provider operating normally with {count} catalogue albums."
        )
