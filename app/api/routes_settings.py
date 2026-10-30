import asyncio
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import db
from ..services.storage import storage
from ..services.download_manager import download_manager
from ..services.folder_picker import validate_directory_path, open_native_folder_picker
from ..providers.registry import registry
from ..models.schemas import (
    ProviderDiagnosticResponse,
    UpdateSettingsRequest,
    BrowseFolderRequest,
    BrowseFolderResponse
)

settings_router = APIRouter(prefix="/api", tags=["Settings & Diagnostics"])

@settings_router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    return {
        "download_dir": str(settings.download_dir),
        "database_path": str(settings.database_path),
        "max_concurrent_downloads": settings.max_concurrent_downloads,
        "strict_320kbps": settings.strict_320kbps,
        "preferred_bitrate_kbps": settings.preferred_bitrate_kbps,
        "pagalnew_base_url": settings.pagalnew_base_url,
        "allowed_domains": list(settings.allowed_domains)
    }

@settings_router.post("/settings")
async def update_settings(req: UpdateSettingsRequest) -> Dict[str, Any]:
    if req.download_dir is not None:
        is_valid, msg, res_path = validate_directory_path(req.download_dir)
        if not is_valid or res_path is None:
            raise HTTPException(status_code=400, detail=msg)
        settings.download_dir = res_path
        storage.set_download_dir(res_path)
        db.set_setting("download_dir", str(res_path))

    if req.max_concurrent_downloads is not None:
        if not (1 <= req.max_concurrent_downloads <= 10):
            raise HTTPException(status_code=400, detail="Max concurrent downloads must be between 1 and 10.")
        download_manager.update_concurrency(req.max_concurrent_downloads)
        db.set_setting("max_concurrent_downloads", str(req.max_concurrent_downloads))

    if req.strict_320kbps is not None:
        settings.strict_320kbps = req.strict_320kbps
        db.set_setting("strict_320kbps", "true" if req.strict_320kbps else "false")

    if req.preferred_bitrate_kbps is not None:
        settings.preferred_bitrate_kbps = req.preferred_bitrate_kbps
        db.set_setting("preferred_bitrate_kbps", str(req.preferred_bitrate_kbps))

    if req.pagalnew_base_url:
        settings.update_pagalnew_domain(req.pagalnew_base_url)
        p_prov = registry.get("pagalnew")
        if p_prov and hasattr(p_prov, "_base_url"):
            p_prov._base_url = settings.pagalnew_base_url
        db.set_setting("pagalnew_base_url", settings.pagalnew_base_url)

    return await get_settings()

@settings_router.post("/settings/browse-folder", response_model=BrowseFolderResponse)
async def browse_folder(req: BrowseFolderRequest = BrowseFolderRequest()) -> BrowseFolderResponse:
    """Asynchronously open the native Windows folder picker dialog."""
    current = req.current_path or str(settings.download_dir)
    res = await asyncio.to_thread(open_native_folder_picker, current)
    return BrowseFolderResponse(
        selected_path=res.get("selected_path"),
        cancelled=res.get("cancelled", False),
        available=res.get("available", True),
        error=res.get("error")
    )

@settings_router.get("/diagnostics/providers", response_model=List[ProviderDiagnosticResponse])
async def test_providers():
    diagnostics = []
    for prov in registry._providers.values():
        diag = await prov.test_connection()
        diagnostics.append(diag)
    return diagnostics
