from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DownloadStatus(str, Enum):
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED_QUALITY = "SKIPPED_QUALITY"

class QualityOption(BaseModel):
    bitrate_kbps: int
    format: str = "mp3"
    download_url: str
    file_size_bytes: Optional[int] = None
    is_confirmed_320k: bool = False

    @property
    def label(self) -> str:
        size_mb = f" ({self.file_size_bytes / (1024*1024):.1f} MB)" if self.file_size_bytes else ""
        return f"{self.bitrate_kbps} kbps {self.format.upper()}{size_mb}"

class Track(BaseModel):
    id: str
    album_id: str
    provider: str
    title: str
    artists: List[str] = Field(default_factory=list)
    composer: Optional[str] = None
    duration_seconds: Optional[int] = None
    artwork_url: Optional[str] = None
    track_number: Optional[int] = 1
    qualities: List[QualityOption] = Field(default_factory=list)

    def get_best_quality(self, prefer_320k: bool = True, strict_320k: bool = False) -> Optional[QualityOption]:
        """Implements the required quality selection policy:
        - Prefer 320 kbps when the source explicitly offers it.
        - If 320 kbps is unavailable and strict mode is on, return None (skips track).
        - If strict mode is off, return highest available bitrate option.
        """
        k320 = next((q for q in self.qualities if q.bitrate_kbps >= 320 and q.is_confirmed_320k), None)
        if k320:
            return k320
        if strict_320k:
            return None
        # Return highest available bitrate
        if self.qualities:
            return max(self.qualities, key=lambda q: q.bitrate_kbps)
        return None

class Album(BaseModel):
    id: str
    provider: str
    title: str
    year: Optional[int] = None
    artists: List[str] = Field(default_factory=list)
    composer: Optional[str] = None
    starcast: List[str] = Field(default_factory=list)
    language: Optional[str] = "Hindi"
    artwork_url: Optional[str] = None
    tracks: List[Track] = Field(default_factory=list)

class SearchResultItem(BaseModel):
    id: str
    provider: str
    item_type: str  # "album" or "track"
    title: str
    album_title: Optional[str] = None
    year: Optional[int] = None
    artists: List[str] = Field(default_factory=list)
    composer: Optional[str] = None
    artwork_url: Optional[str] = None
    track_count: Optional[int] = None
    album_id: Optional[str] = None

class DownloadTask(BaseModel):
    task_id: str
    track_id: str
    album_id: str
    provider: str
    title: str
    artist: str
    album_title: str
    selected_bitrate: int
    download_url: str
    target_file_path: str
    status: DownloadStatus = DownloadStatus.QUEUED
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: Optional[float] = None
    error_message: Optional[str] = None
    retries_left: int = 3
    created_at: float
    updated_at: float
    completed_at: Optional[float] = None

    @property
    def progress_pct(self) -> float:
        if self.total_bytes > 0:
            return round((self.downloaded_bytes / self.total_bytes) * 100, 1)
        return 0.0

class ProviderInfo(BaseModel):
    id: str
    name: str
    enabled: bool = True
    supports_batch_download: bool = False
    description: str
