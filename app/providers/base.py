from abc import ABC, abstractmethod
from typing import List, Optional
from ..models.domain import Album, Track, SearchResultItem
from ..models.schemas import ProviderDiagnosticResponse

class BaseMusicProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier string for the provider (e.g. 'mock', 'pagalnew')."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable display name."""
        pass

    @property
    @abstractmethod
    def supports_batch_download(self) -> bool:
        """Whether the provider authorises and supports batch album downloading."""
        pass

    @abstractmethod
    async def search(self, query: str, search_type: str = "all") -> List[SearchResultItem]:
        """Search music provider by query string across songs/albums/artists/composers."""
        pass

    @abstractmethod
    async def get_album(self, album_id: str) -> Optional[Album]:
        """Fetch complete album metadata, artwork, and track list."""
        pass

    @abstractmethod
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Fetch specific track metadata and audio quality options."""
        pass

    @abstractmethod
    async def test_connection(self) -> ProviderDiagnosticResponse:
        """Performs a diagnostic connection test to verify health and measure latency."""
        pass
