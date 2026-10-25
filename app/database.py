import sqlite3
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from .config import settings
from .models.domain import DownloadTask, DownloadStatus, Album, Track

class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.database_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS download_tasks (
                task_id TEXT PRIMARY KEY,
                track_id TEXT NOT NULL,
                album_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album_title TEXT NOT NULL,
                selected_bitrate INTEGER NOT NULL,
                download_url TEXT NOT NULL,
                target_file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                total_bytes INTEGER DEFAULT 0,
                downloaded_bytes INTEGER DEFAULT 0,
                speed_bps REAL DEFAULT 0,
                eta_seconds REAL,
                error_message TEXT,
                retries_left INTEGER DEFAULT 3,
                track_number INTEGER DEFAULT 1,
                total_tracks INTEGER,
                year INTEGER,
                composer TEXT,
                genre TEXT,
                artwork_url TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON download_tasks(status);

            CREATE TABLE IF NOT EXISTS download_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                track_id TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album_title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                bitrate_kbps INTEGER NOT NULL,
                completed_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cached_albums (
                album_id TEXT,
                provider TEXT,
                title TEXT NOT NULL,
                year INTEGER,
                artist TEXT,
                data_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (album_id, provider)
            );
            """)

            # Safe migrations for existing databases
            for col_def in [
                ("track_number", "INTEGER DEFAULT 1"),
                ("total_tracks", "INTEGER"),
                ("year", "INTEGER"),
                ("composer", "TEXT"),
                ("genre", "TEXT"),
                ("artwork_url", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE download_tasks ADD COLUMN {col_def[0]} {col_def[1]};")
                except sqlite3.OperationalError:
                    pass

    # --- Download Task Operations ---
    def save_task(self, task: DownloadTask) -> None:
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO download_tasks (
                task_id, track_id, album_id, provider, title, artist, album_title,
                selected_bitrate, download_url, target_file_path, status,
                total_bytes, downloaded_bytes, speed_bps, eta_seconds, error_message,
                retries_left, track_number, total_tracks, year, composer, genre, artwork_url,
                created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                status=excluded.status,
                total_bytes=excluded.total_bytes,
                downloaded_bytes=excluded.downloaded_bytes,
                speed_bps=excluded.speed_bps,
                eta_seconds=excluded.eta_seconds,
                error_message=excluded.error_message,
                retries_left=excluded.retries_left,
                track_number=excluded.track_number,
                total_tracks=excluded.total_tracks,
                year=excluded.year,
                composer=excluded.composer,
                genre=excluded.genre,
                artwork_url=excluded.artwork_url,
                updated_at=excluded.updated_at,
                completed_at=excluded.completed_at
            """, (
                task.task_id, task.track_id, task.album_id, task.provider, task.title,
                task.artist, task.album_title, task.selected_bitrate, task.download_url,
                task.target_file_path, task.status.value, task.total_bytes,
                task.downloaded_bytes, task.speed_bps, task.eta_seconds, task.error_message,
                task.retries_left, task.track_number, task.total_tracks, task.year,
                task.composer, task.genre, task.artwork_url,
                task.created_at, task.updated_at, task.completed_at
            ))

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM download_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_tasks(self, limit: int = 100) -> List[DownloadTask]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM download_tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._row_to_task(r) for r in rows]

    def get_pending_tasks(self) -> List[DownloadTask]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM download_tasks WHERE status IN (?, ?) ORDER BY created_at ASC",
                (DownloadStatus.QUEUED.value, DownloadStatus.DOWNLOADING.value)
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def delete_task(self, task_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM download_tasks WHERE task_id = ?", (task_id,))
            return cursor.rowcount > 0

    def clear_pending_tasks(self) -> int:
        """Removes queued tasks without cancelling active downloads."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM download_tasks WHERE status = ?", (DownloadStatus.QUEUED.value,))
            return cursor.rowcount

    def clear_completed_tasks(self) -> int:
        """Removes completed tasks from download queue view (does not delete history or files)."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM download_tasks WHERE status = ?", (DownloadStatus.COMPLETED.value,))
            return cursor.rowcount

    def clear_failed_tasks(self) -> int:
        """Removes failed, cancelled, and skipped tasks from download queue view."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM download_tasks WHERE status IN (?, ?, ?)",
                (DownloadStatus.FAILED.value, DownloadStatus.CANCELLED.value, DownloadStatus.SKIPPED_QUALITY.value)
            )
            return cursor.rowcount

    def record_completed_history(self, task: DownloadTask) -> None:
        with self.get_connection() as conn:
            conn.execute("""
            INSERT OR IGNORE INTO download_history (
                task_id, track_id, title, artist, album_title, file_path, file_size_bytes, bitrate_kbps, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.track_id, task.title, task.artist, task.album_title,
                task.target_file_path, task.downloaded_bytes, task.selected_bitrate,
                task.completed_at or time.time()
            ))

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM download_history ORDER BY completed_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def clear_history(self) -> int:
        """Clears completed history records from database. Never deletes downloaded files."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM download_history")
            return cursor.rowcount

    # --- Cache Album Operations ---
    def cache_album(self, album: Album) -> None:
        with self.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO cached_albums (album_id, provider, title, year, artist, data_json, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                album.id, album.provider, album.title, album.year,
                ", ".join(album.artists), album.model_dump_json(), time.time()
            ))

    def get_cached_album(self, provider: str, album_id: str) -> Optional[Album]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT data_json FROM cached_albums WHERE provider = ? AND album_id = ?",
                (provider, album_id)
            ).fetchone()
            if row:
                return Album.model_validate_json(row["data_json"])
            return None

    def _row_to_task(self, row: sqlite3.Row) -> DownloadTask:
        # Check if optional columns exist in row keys
        keys = row.keys()
        return DownloadTask(
            task_id=row["task_id"],
            track_id=row["track_id"],
            album_id=row["album_id"],
            provider=row["provider"],
            title=row["title"],
            artist=row["artist"],
            album_title=row["album_title"],
            selected_bitrate=row["selected_bitrate"],
            download_url=row["download_url"],
            target_file_path=row["target_file_path"],
            status=DownloadStatus(row["status"]),
            total_bytes=row["total_bytes"],
            downloaded_bytes=row["downloaded_bytes"],
            speed_bps=row["speed_bps"] or 0.0,
            eta_seconds=row["eta_seconds"],
            error_message=row["error_message"],
            retries_left=row["retries_left"],
            track_number=row["track_number"] if "track_number" in keys else 1,
            total_tracks=row["total_tracks"] if "total_tracks" in keys else None,
            year=row["year"] if "year" in keys else None,
            composer=row["composer"] if "composer" in keys else None,
            genre=row["genre"] if "genre" in keys else "Bollywood",
            artwork_url=row["artwork_url"] if "artwork_url" in keys else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

db = Database()
