import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set
import httpx

from ..config import settings
from ..database import db
from ..models.domain import DownloadTask, DownloadStatus, Track, Album, QualityOption
from .security import validate_download_url, SecurityError
from .storage import storage
from .metadata import metadata_service

class DownloadManager:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._pause_events: Dict[str, asyncio.Event] = {}
        self._active_workers: Dict[str, asyncio.Task] = {}
        self._is_global_paused: bool = False
        self._queue_lock = asyncio.Lock()

    @property
    def is_paused(self) -> bool:
        return self._is_global_paused

    def update_concurrency(self, max_concurrent: int) -> None:
        """Dynamically update maximum concurrent downloads."""
        settings.max_concurrent_downloads = max(1, min(max_concurrent, 10))
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)

    async def enqueue_track(
        self,
        track: Track,
        album: Album,
        quality: Optional[QualityOption] = None,
        preferred_bitrate: int = 320,
        strict_320k: bool = False
    ) -> DownloadTask:
        """Enqueue an individual track for download adhering to quality rules."""
        if quality is None:
            quality = track.get_best_quality(prefer_320k=(preferred_bitrate >= 320), strict_320k=strict_320k)

        task_id = str(uuid.uuid4())
        now = time.time()
        
        # Handle strict mode rejection
        if quality is None and strict_320k:
            target_path = storage.resolve_track_path(
                artist=", ".join(track.artists),
                album=album.title,
                track_title=track.title,
                bitrate_kbps=0,
                track_num=track.track_number
            )
            task = DownloadTask(
                task_id=task_id,
                track_id=track.id,
                album_id=album.id,
                provider=track.provider,
                title=track.title,
                artist=", ".join(track.artists),
                album_title=album.title,
                selected_bitrate=0,
                download_url="",
                target_file_path=str(target_path),
                status=DownloadStatus.SKIPPED_QUALITY,
                error_message="Skipped: Strict 320 kbps mode active and no confirmed 320 kbps stream exists.",
                track_number=track.track_number or 1,
                total_tracks=len(album.tracks) if album and album.tracks else None,
                year=album.year,
                composer=track.composer or album.composer,
                genre=album.language or "Bollywood",
                artwork_url=track.artwork_url or album.artwork_url,
                created_at=now,
                updated_at=now
            )
            db.save_task(task)
            return task

        if quality is None:
            raise ValueError(f"No available audio qualities found for track '{track.title}'")

        # Validate SSRF
        validate_download_url(quality.download_url)

        # Resolve album-based file path with clean title
        target_path = storage.resolve_track_path(
            artist=", ".join(track.artists),
            album=album.title,
            track_title=track.title,
            bitrate_kbps=quality.bitrate_kbps,
            track_num=track.track_number
        )

        initial_status = DownloadStatus.PAUSED if self._is_global_paused else DownloadStatus.QUEUED

        task = DownloadTask(
            task_id=task_id,
            track_id=track.id,
            album_id=album.id,
            provider=track.provider,
            title=track.title,
            artist=", ".join(track.artists),
            album_title=album.title,
            selected_bitrate=quality.bitrate_kbps,
            download_url=quality.download_url,
            target_file_path=str(target_path),
            status=initial_status,
            total_bytes=quality.file_size_bytes or 0,
            downloaded_bytes=0,
            retries_left=settings.max_retries,
            track_number=track.track_number or 1,
            total_tracks=len(album.tracks) if album and album.tracks else None,
            year=album.year,
            composer=track.composer or album.composer,
            genre=album.language or "Bollywood",
            artwork_url=track.artwork_url or album.artwork_url,
            created_at=now,
            updated_at=now
        )

        db.save_task(task)
        self._cancel_events[task_id] = asyncio.Event()
        self._pause_events[task_id] = asyncio.Event()

        # If queue is not globally paused, launch background worker
        if not self._is_global_paused:
            worker = asyncio.create_task(self._process_task_safely(task.task_id))
            self._active_workers[task.task_id] = worker

        return task

    async def enqueue_batch(
        self,
        album: Album,
        tracks: List[Track],
        preferred_bitrate: int = 320,
        strict_320k: bool = False
    ) -> List[DownloadTask]:
        """Enqueue multiple tracks in batch."""
        tasks: List[DownloadTask] = []
        for track in tracks:
            t = await self.enqueue_track(
                track=track,
                album=album,
                preferred_bitrate=preferred_bitrate,
                strict_320k=strict_320k
            )
            tasks.append(t)
        return tasks

    def cancel_task(self, task_id: str) -> bool:
        """Cancel an in-flight, queued, or paused download task."""
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()

        task = db.get_task(task_id)
        if task and task.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED):
            task.status = DownloadStatus.CANCELLED
            task.speed_bps = 0.0
            task.eta_seconds = None
            task.updated_at = time.time()
            db.save_task(task)
            
            # Clean up .part file on cancel
            part_path = storage.get_partial_path(Path(task.target_file_path))
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a specific queued or active download."""
        if task_id in self._pause_events:
            self._pause_events[task_id].set()

        task = db.get_task(task_id)
        if task and task.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING):
            task.status = DownloadStatus.PAUSED
            task.speed_bps = 0.0
            task.eta_seconds = None
            task.updated_at = time.time()
            db.save_task(task)
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a specific paused download."""
        task = db.get_task(task_id)
        if not task or task.status != DownloadStatus.PAUSED:
            return False

        task.status = DownloadStatus.QUEUED
        task.speed_bps = 0.0
        task.eta_seconds = None
        task.error_message = None
        task.updated_at = time.time()
        db.save_task(task)

        self._cancel_events[task_id] = asyncio.Event()
        self._pause_events[task_id] = asyncio.Event()

        existing = self._active_workers.get(task_id)
        if existing is None or existing.done():
            worker = asyncio.create_task(self._process_task_safely(task_id))
            self._active_workers[task_id] = worker
        return True

    def pause_all(self) -> int:
        """Pause all active downloads and prevent queued downloads from starting."""
        self._is_global_paused = True
        for pevent in self._pause_events.values():
            pevent.set()

        affected = 0
        with db.get_connection() as conn:
            cur = conn.execute(
                "UPDATE download_tasks SET status = ?, speed_bps = 0, eta_seconds = NULL, updated_at = ? WHERE status IN (?, ?)",
                (DownloadStatus.PAUSED.value, time.time(), DownloadStatus.QUEUED.value, DownloadStatus.DOWNLOADING.value)
            )
            affected = cur.rowcount
        return affected

    async def resume_all(self) -> int:
        """Resume all paused downloads from partial progress and respect concurrency limit."""
        self._is_global_paused = False
        paused_tasks = db.get_tasks_by_status([DownloadStatus.PAUSED])
        affected = 0
        now = time.time()

        for task in paused_tasks:
            task.status = DownloadStatus.QUEUED
            task.speed_bps = 0.0
            task.eta_seconds = None
            task.error_message = None
            task.updated_at = now
            db.save_task(task)
            affected += 1

            self._cancel_events[task.task_id] = asyncio.Event()
            self._pause_events[task.task_id] = asyncio.Event()

            existing = self._active_workers.get(task.task_id)
            if existing is None or existing.done():
                worker = asyncio.create_task(self._process_task_safely(task.task_id))
                self._active_workers[task.task_id] = worker

        return affected

    def cancel_all(self) -> int:
        """Cancel all active and queued tasks, stopping workers cleanly and deleting .part files."""
        for cevent in self._cancel_events.values():
            cevent.set()

        active_tasks = db.get_tasks_by_status([
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PAUSED
        ])
        affected = 0
        now = time.time()

        for task in active_tasks:
            task.status = DownloadStatus.CANCELLED
            task.speed_bps = 0.0
            task.eta_seconds = None
            task.updated_at = now
            db.save_task(task)
            affected += 1

            part_path = storage.get_partial_path(Path(task.target_file_path))
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass

        return affected

    async def _process_task_safely(self, task_id: str) -> None:
        """Wrapper to acquire semaphore and execute download worker."""
        cancel_event = self._cancel_events.setdefault(task_id, asyncio.Event())
        pause_event = self._pause_events.setdefault(task_id, asyncio.Event())

        try:
            async with self.semaphore:
                if cancel_event.is_set():
                    return
                if pause_event.is_set() or self._is_global_paused:
                    task = db.get_task(task_id)
                    if task and task.status not in (DownloadStatus.CANCELLED, DownloadStatus.COMPLETED):
                        task.status = DownloadStatus.PAUSED
                        task.speed_bps = 0.0
                        task.eta_seconds = None
                        task.updated_at = time.time()
                        db.save_task(task)
                    return
                await self._execute_download(task_id, cancel_event, pause_event)
        finally:
            self._active_workers.pop(task_id, None)

    async def _execute_download(
        self,
        task_id: str,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event
    ) -> None:
        task = db.get_task(task_id)
        if not task or task.status in (DownloadStatus.CANCELLED, DownloadStatus.PAUSED):
            return

        final_path = Path(task.target_file_path)
        part_path = storage.get_partial_path(final_path)

        # If file already exists and complete
        if final_path.exists() and task.total_bytes > 0 and final_path.stat().st_size >= task.total_bytes:
            task.status = DownloadStatus.COMPLETED
            task.downloaded_bytes = task.total_bytes
            task.completed_at = time.time()
            task.updated_at = time.time()
            db.save_task(task)
            db.record_completed_history(task)
            return

        task.status = DownloadStatus.DOWNLOADING
        task.updated_at = time.time()
        db.save_task(task)

        attempt = 0
        while attempt <= task.retries_left:
            if cancel_event.is_set():
                task.status = DownloadStatus.CANCELLED
                task.updated_at = time.time()
                db.save_task(task)
                return
            if pause_event.is_set() or self._is_global_paused:
                task.status = DownloadStatus.PAUSED
                task.speed_bps = 0.0
                task.eta_seconds = None
                task.updated_at = time.time()
                db.save_task(task)
                return

            try:
                # Validate URL before connecting
                validate_download_url(task.download_url)

                # Determine existing bytes for HTTP Range Resume
                existing_bytes = part_path.stat().st_size if part_path.exists() else 0
                headers = {
                    "User-Agent": "MusicHub/1.2 (Windows NT 10.0; Win64; x64) DownloadManager"
                }
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"

                timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    async with client.stream("GET", task.download_url, headers=headers) as resp:
                        # Handle 416 Range Not Satisfiable
                        if resp.status_code == 416:
                            existing_bytes = 0
                            if part_path.exists():
                                part_path.unlink()
                            headers.pop("Range", None)
                            async with client.stream("GET", task.download_url, headers=headers) as retry_resp:
                                await self._stream_to_disk(retry_resp, task, part_path, final_path, 0, cancel_event, pause_event)
                                return

                        resp.raise_for_status()

                        # Determine mode and initial bytes
                        if resp.status_code == 206:
                            initial_bytes = existing_bytes
                            content_range = resp.headers.get("Content-Range", "")
                            if "/" in content_range:
                                total_str = content_range.split("/")[-1]
                                if total_str.isdigit():
                                    task.total_bytes = int(total_str)
                        else:
                            initial_bytes = 0
                            content_len = resp.headers.get("Content-Length")
                            if content_len and content_len.isdigit():
                                task.total_bytes = int(content_len)

                        await self._stream_to_disk(resp, task, part_path, final_path, initial_bytes, cancel_event, pause_event)
                        return

            except SecurityError as se:
                task.status = DownloadStatus.FAILED
                task.error_message = f"Security error: {str(se)}"
                task.updated_at = time.time()
                db.save_task(task)
                return
            except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
                attempt += 1
                task.error_message = f"Attempt {attempt}/{settings.max_retries} failed: {type(e).__name__} - {str(e)}"
                task.updated_at = time.time()
                db.save_task(task)

                if attempt > settings.max_retries or cancel_event.is_set():
                    task.status = DownloadStatus.FAILED
                    db.save_task(task)
                    return

                backoff = settings.retry_backoff_factor * (1.5 ** (attempt - 1))
                try:
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(cancel_event.wait()),
                            asyncio.create_task(pause_event.wait())
                        ],
                        timeout=backoff,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for p in pending:
                        p.cancel()
                    if cancel_event.is_set():
                        task.status = DownloadStatus.CANCELLED
                        db.save_task(task)
                        return
                    if pause_event.is_set() or self._is_global_paused:
                        task.status = DownloadStatus.PAUSED
                        db.save_task(task)
                        return
                except asyncio.TimeoutError:
                    pass

    async def _stream_to_disk(
        self,
        resp: httpx.Response,
        task: DownloadTask,
        part_path: Path,
        final_path: Path,
        initial_bytes: int,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event
    ) -> None:
        part_path.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "ab" if initial_bytes > 0 else "wb"

        downloaded = initial_bytes
        last_time = time.time()
        bytes_since_last = 0
        was_interrupted = False

        with open(part_path, file_mode) as f:
            async for chunk in resp.aiter_bytes(chunk_size=settings.chunk_size_bytes):
                if cancel_event.is_set():
                    was_interrupted = True
                    task.status = DownloadStatus.CANCELLED
                    task.speed_bps = 0.0
                    task.eta_seconds = None
                    task.updated_at = time.time()
                    db.save_task(task)
                    break

                if pause_event.is_set() or self._is_global_paused:
                    was_interrupted = True
                    task.status = DownloadStatus.PAUSED
                    task.speed_bps = 0.0
                    task.eta_seconds = None
                    task.downloaded_bytes = downloaded
                    task.updated_at = time.time()
                    db.save_task(task)
                    break

                f.write(chunk)
                downloaded += len(chunk)
                bytes_since_last += len(chunk)

                now = time.time()
                time_diff = now - last_time
                if time_diff >= 0.5:
                    speed = bytes_since_last / time_diff
                    remaining_bytes = max(0, task.total_bytes - downloaded)
                    eta = remaining_bytes / speed if speed > 0 else None

                    task.downloaded_bytes = downloaded
                    task.speed_bps = speed
                    task.eta_seconds = eta
                    task.updated_at = now
                    db.save_task(task)

                    last_time = now
                    bytes_since_last = 0

        # If cancelled, clean up partial file after file handle is closed
        if cancel_event.is_set():
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            return

        if pause_event.is_set() or self._is_global_paused:
            # Preserved .part file on pause
            return

        if was_interrupted:
            return

        # Finished receiving all audio bytes
        if task.total_bytes == 0:
            task.total_bytes = downloaded
        task.downloaded_bytes = downloaded
        task.speed_bps = 0.0
        task.eta_seconds = 0.0

        # --- ID3 Metadata & Artwork Pipeline ---
        try:
            trk_model = Track(
                id=task.track_id,
                album_id=task.album_id,
                provider=task.provider,
                title=task.title,
                artists=[a.strip() for a in task.artist.split(",") if a.strip()],
                composer=task.composer,
                track_number=task.track_number or 1,
                artwork_url=task.artwork_url,
                qualities=[]
            )
            alb_model = Album(
                id=task.album_id,
                provider=task.provider,
                title=task.album_title,
                year=task.year,
                artists=[a.strip() for a in task.artist.split(",") if a.strip()],
                composer=task.composer,
                language=task.genre or "Bollywood",
                artwork_url=task.artwork_url,
                tracks=[]
            )

            cover_bytes, cover_mime = await metadata_service.fetch_artwork_bytes(task.artwork_url)

            metadata_service.apply_id3_metadata(
                file_path=part_path,
                track=trk_model,
                album=alb_model,
                cover_bytes=cover_bytes,
                cover_mime=cover_mime or "image/jpeg"
            )
        except Exception as tag_err:
            print(f"[DownloadManager] Non-fatal ID3 metadata warning for '{task.title}': {tag_err}")

        # Atomic rename .part -> final target file
        if final_path.exists():
            final_path.unlink()
        part_path.rename(final_path)

        task.status = DownloadStatus.COMPLETED
        task.completed_at = time.time()
        task.updated_at = time.time()

        db.save_task(task)
        db.record_completed_history(task)

download_manager = DownloadManager()
