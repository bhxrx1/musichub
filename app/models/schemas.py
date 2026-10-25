from typing import List, Optional
from pydantic import BaseModel
from .domain import DownloadStatus, QualityOption, SearchResultItem, Album, DownloadTask, ProviderInfo

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]

class BatchDownloadRequest(BaseModel):
    provider: str
    album_id: str
    track_ids: List[str]
    preferred_bitrate: int = 320
    strict_320k: bool = False

class SingleDownloadRequest(BaseModel):
    provider: str
    track_id: str
    album_id: str
    bitrate: int = 320
    custom_url: Optional[str] = None
    strict_320k: bool = False

class DownloadQueueResponse(BaseModel):
    active_count: int
    queued_count: int
    completed_count: int
    failed_count: int
    tasks: List[DownloadTask]

class ProviderDiagnosticResponse(BaseModel):
    provider_id: str
    provider_name: str
    healthy: bool
    latency_ms: Optional[float] = None
    message: str

class UpdateSettingsRequest(BaseModel):
    download_dir: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    strict_320kbps: Optional[bool] = None
    preferred_bitrate_kbps: Optional[int] = None
