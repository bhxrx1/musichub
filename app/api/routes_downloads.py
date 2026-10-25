from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..database import db
from ..providers.registry import registry
from ..services.download_manager import download_manager
from ..models.domain import DownloadTask, DownloadStatus
from ..models.schemas import (
    SingleDownloadRequest,
    BatchDownloadRequest,
    DownloadQueueResponse,
    QueueControlResponse
)

downloads_router = APIRouter(prefix="/api/downloads", tags=["Download Manager"])

@downloads_router.get("/queue", response_model=DownloadQueueResponse)
async def get_download_queue():
    tasks = db.list_tasks(limit=100)
    active = sum(1 for t in tasks if t.status == DownloadStatus.DOWNLOADING)
    queued = sum(1 for t in tasks if t.status == DownloadStatus.QUEUED)
    paused = sum(1 for t in tasks if t.status == DownloadStatus.PAUSED)
    completed = sum(1 for t in tasks if t.status == DownloadStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status in (DownloadStatus.FAILED, DownloadStatus.CANCELLED, DownloadStatus.SKIPPED_QUALITY))
    return DownloadQueueResponse(
        active_count=active,
        queued_count=queued,
        paused_count=paused,
        completed_count=completed,
        failed_count=failed,
        tasks=tasks
    )

@downloads_router.post("/queue/pause-all", response_model=QueueControlResponse)
async def pause_all_downloads():
    """Pauses all active and queued downloads."""
    affected = download_manager.pause_all()
    return QueueControlResponse(
        action="pause_all",
        affected_count=affected,
        message=f"Paused {affected} active/queued task(s)."
    )

@downloads_router.post("/queue/resume-all", response_model=QueueControlResponse)
async def resume_all_downloads():
    """Resumes all paused downloads."""
    affected = await download_manager.resume_all()
    return QueueControlResponse(
        action="resume_all",
        affected_count=affected,
        message=f"Resumed {affected} paused task(s)."
    )

@downloads_router.post("/queue/cancel-all", response_model=QueueControlResponse)
async def cancel_all_downloads():
    """Cancels all active, queued, and paused downloads, removing partial .part files."""
    affected = download_manager.cancel_all()
    return QueueControlResponse(
        action="cancel_all",
        affected_count=affected,
        message=f"Cancelled {affected} active/queued task(s)."
    )

@downloads_router.get("/history", response_model=List[Dict[str, Any]])
async def get_download_history():
    return db.get_history(limit=100)

@downloads_router.post("/history/clear")
async def clear_download_history():
    """Clears completed history records from database. Does not delete files on disk."""
    count = db.clear_history()
    return {"status": "success", "cleared_count": count}

@downloads_router.post("/queue/clear-pending")
async def clear_pending_queue():
    """Removes pending tasks from queue without affecting active downloads or completed files."""
    count = db.clear_pending_tasks()
    return {"status": "success", "cleared_count": count}

@downloads_router.post("/queue/clear-failed")
async def clear_failed_queue():
    """Removes failed, cancelled, and skipped tasks from queue view."""
    count = db.clear_failed_tasks()
    return {"status": "success", "cleared_count": count}

@downloads_router.post("/queue/clear-completed")
async def clear_completed_queue():
    """Removes completed tasks from queue view (history and files remain intact)."""
    count = db.clear_completed_tasks()
    return {"status": "success", "cleared_count": count}

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

@downloads_router.post("/{task_id}/pause")
async def pause_download(task_id: str):
    success = download_manager.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or cannot be paused")
    return {"status": "paused", "task_id": task_id}

@downloads_router.post("/{task_id}/resume")
async def resume_download(task_id: str):
    success = download_manager.resume_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or cannot be resumed")
    return {"status": "resumed", "task_id": task_id}

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
