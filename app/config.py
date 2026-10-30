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
    
    # Server network configuration
    host: str = "127.0.0.1"
    port: int = 8001
    
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

def load_persisted_settings(db_instance=None) -> None:
    """Loads saved settings from the SQLite database and synchronises runtime services."""
    try:
        if db_instance is not None:
            target_db = db_instance
        else:
            from .database import db as default_db
            target_db = default_db

        stored = target_db.get_all_settings()
        if not stored:
            return

        if "download_dir" in stored and stored["download_dir"]:
            try:
                p = Path(stored["download_dir"]).resolve()
                settings.download_dir = p
                from .services.storage import storage
                storage.set_download_dir(p)
            except Exception as e:
                print(f"[Settings] Failed to restore download_dir: {e}")

        if "max_concurrent_downloads" in stored and stored["max_concurrent_downloads"]:
            try:
                val = int(stored["max_concurrent_downloads"])
                if 1 <= val <= 10:
                    settings.max_concurrent_downloads = val
                    from .services.download_manager import download_manager
                    download_manager.update_concurrency(val)
            except Exception as e:
                print(f"[Settings] Failed to restore max_concurrent_downloads: {e}")

        if "strict_320kbps" in stored and stored["strict_320kbps"] is not None:
            try:
                v = str(stored["strict_320kbps"]).strip().lower()
                settings.strict_320kbps = (v in ("true", "1", "yes"))
            except Exception as e:
                print(f"[Settings] Failed to restore strict_320kbps: {e}")

        if "preferred_bitrate_kbps" in stored and stored["preferred_bitrate_kbps"]:
            try:
                settings.preferred_bitrate_kbps = int(stored["preferred_bitrate_kbps"])
            except Exception as e:
                print(f"[Settings] Failed to restore preferred_bitrate_kbps: {e}")

        if "pagalnew_base_url" in stored and stored["pagalnew_base_url"]:
            try:
                settings.update_pagalnew_domain(stored["pagalnew_base_url"])
                from .providers.registry import registry
                p_prov = registry.get("pagalnew")
                if p_prov and hasattr(p_prov, "_base_url"):
                    p_prov._base_url = settings.pagalnew_base_url
            except Exception as e:
                print(f"[Settings] Failed to restore pagalnew_base_url: {e}")
    except Exception as e:
        print(f"[Settings] Error restoring persisted settings: {e}")

settings = Settings()
settings.ensure_directories()
