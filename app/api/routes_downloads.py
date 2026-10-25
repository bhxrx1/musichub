from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..database import db
from ..providers.registry import registry
from ..services.download_manager import download_manager
from ..models.domain import DownloadTask, DownloadStatus
from ..models.schemas import (
    SingleDownloadRequest,
    BatchDownloadRequest,
    DownloadQueueResponse
)

downloads_router = APIRouter(prefix="/api/downloads", tags=["Download Manager"])

@downloads_router.get("/queue", response_model=DownloadQueueResponse)
async def get_download_queue():
    tasks = db.list_tasks(limit=100)
    active = sum(1 for t in tasks if t.status == DownloadStatus.DOWNLOADING)
    queued = sum(1 for t in tasks if t.status == DownloadStatus.QUEUED)
    completed = sum(1 for t in tasks if t.status == DownloadStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status in (DownloadStatus.FAILED, DownloadStatus.CANCELLED, DownloadStatus.SKIPPED_QUALITY))
    return DownloadQueueResponse(
        active_count=active,
        queued_count=queued,
        completed_count=completed,
        failed_count=failed,
        tasks=tasks
    )

@downloads_router.get("/history", response_model=List[Dict[str, Any]])
async def get_download_history():
    return db.get_history(limit=50)

@downloads_router.post("/start", response_model=DownloadTask)
async def start_single_download(req: SingleDownloadRequest):
    prov = registry.get(req.provider)
    if not prov:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")

    track = await prov.get_track(req.track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    album = await prov.get_album(req.album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    try:
        task = await download_manager.enqueue_track(
            track=track,
            album=album,
            preferred_bitrate=req.bitrate,
            strict_320k=req.strict_320k
        )
        return task
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@downloads_router.post("/batch", response_model=List[DownloadTask])
async def start_batch_download(req: BatchDownloadRequest):
    prov = registry.get(req.provider)
    if not prov:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")

    if not prov.supports_batch_download:
        raise HTTPException(status_code=403, detail=f"Provider '{req.provider}' does not support batch downloads")

    album = await prov.get_album(req.album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    tracks_to_download = [t for t in album.tracks if t.id in req.track_ids]
    if not tracks_to_download:
        raise HTTPException(status_code=400, detail="No matching track IDs found in album")

    tasks = await download_manager.enqueue_batch(
        album=album,
        tracks=tracks_to_download,
        preferred_bitrate=req.preferred_bitrate,
        strict_320k=req.strict_320k
    )
    return tasks

@downloads_router.post("/{task_id}/cancel")
async def cancel_download(task_id: str):
    success = download_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or cannot be cancelled")
    return {"status": "cancelled", "task_id": task_id}

@downloads_router.post("/{task_id}/retry", response_model=DownloadTask)
async def retry_download(task_id: str):
    old_task = db.get_task(task_id)
    if not old_task:
        raise HTTPException(status_code=404, detail="Task not found")

    prov = registry.get(old_task.provider)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")

    track = await prov.get_track(old_task.track_id)
    album = await prov.get_album(old_task.album_id)
    if not track or not album:
        raise HTTPException(status_code=404, detail="Track or album source unavailable")

    new_task = await download_manager.enqueue_track(
        track=track,
        album=album,
        preferred_bitrate=old_task.selected_bitrate,
        strict_320k=False
    )
    return new_task
