from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter
from ..config import settings
from ..services.storage import storage
from ..services.download_manager import download_manager
from ..providers.registry import registry
from ..models.schemas import ProviderDiagnosticResponse, UpdateSettingsRequest

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
    if req.download_dir:
        p = Path(req.download_dir)
        settings.download_dir = p
        storage.set_download_dir(p)
    if req.max_concurrent_downloads is not None:
        download_manager.update_concurrency(req.max_concurrent_downloads)
    if req.strict_320kbps is not None:
        settings.strict_320kbps = req.strict_320kbps
    if req.preferred_bitrate_kbps is not None:
        settings.preferred_bitrate_kbps = req.preferred_bitrate_kbps
    if req.pagalnew_base_url:
        settings.update_pagalnew_domain(req.pagalnew_base_url)
        p_prov = registry.get("pagalnew")
        if p_prov and hasattr(p_prov, "_base_url"):
            p_prov._base_url = settings.pagalnew_base_url

    return await get_settings()

@settings_router.get("/diagnostics/providers", response_model=List[ProviderDiagnosticResponse])
async def test_providers():
    diagnostics = []
    for prov in registry._providers.values():
        diag = await prov.test_connection()
        diagnostics.append(diag)
    return diagnostics
