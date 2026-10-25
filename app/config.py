from pathlib import Path
from typing import List, Set
from urllib.parse import urlparse
from pydantic import BaseModel, Field

class Settings(BaseModel):
    app_name: str = "MusicHub"
    app_version: str = "1.2.0"
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data")
    download_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent / "downloads")
    database_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "musichub.db")
    
    # Download manager configuration
    max_concurrent_downloads: int = 3
    chunk_size_bytes: int = 65536  # 64 KB chunks
    max_retries: int = 3
    retry_backoff_factor: float = 1.5
    request_timeout_seconds: float = 20.0
    
    # Quality policy
    preferred_bitrate_kbps: int = 320
    strict_320kbps: bool = False

    # Provider configuration
    # Note: If changing domain, revalidate target website structure, selectors, and download endpoints.
    pagalnew_base_url: str = "https://pagalnew.com"
    
    # Security: Domain whitelist for SSRF defense
    allowed_domains: Set[str] = {
        "localhost",
        "127.0.0.1",
        "testserver",
        "pagalnew.com",
        "320.pagalnew.com",
        "128.pagalnew.com",
        "mock-cdn.local",
        "images.unsplash.com"
    }

    def update_pagalnew_domain(self, new_url: str) -> None:
        """Centralised update for PagalNew base URL and SSRF domain whitelist."""
        clean_url = new_url.rstrip("/")
        parsed = urlparse(clean_url)
        if parsed.hostname:
            self.pagalnew_base_url = clean_url
            self.allowed_domains.add(parsed.hostname.lower())

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
