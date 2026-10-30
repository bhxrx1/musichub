import os
import re
import time
from pathlib import Path
from typing import Optional
from ..config import settings
from .security import sanitize_filename, assert_safe_audio_extension, SecurityError

def safe_replace_file(src: Path, dst: Path, max_attempts: int = 5, delay: float = 0.05) -> None:
    """Safely and atomically replaces dst with src on Windows and POSIX,
    handling transient file locks, WinError 32, and existing file replacements."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    last_err: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            # os.replace is atomic and replaces dst if it exists
            os.replace(str(src), str(dst))
            return
        except PermissionError as pe:
            last_err = pe
            time.sleep(delay)
        except OSError as oe:
            last_err = oe
            time.sleep(delay)

    # If os.replace still failed after retries, try explicit unlink if dst exists
    if dst.exists():
        try:
            safe_unlink_file(dst, max_attempts=3, delay=delay)
            os.replace(str(src), str(dst))
            return
        except Exception as e:
            last_err = e

    if last_err:
        raise last_err

def safe_unlink_file(path: Path, max_attempts: int = 5, delay: float = 0.05) -> bool:
    """Safely unlinks a file, retrying briefly if locked by a transient OS handle."""
    if not path.exists():
        return True
    for attempt in range(max_attempts):
        try:
            path.unlink()
            return True
        except PermissionError:
            time.sleep(delay)
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(delay)
    return not path.exists()

def clean_song_title(raw_title: str, album_title: Optional[str] = None) -> str:
    """Produces a clean song title for filenames:
    - Strips leading track numbers (e.g., '01 - ', '01. ')
    - Strips bitrate tags (e.g., '[320k]', '(128kbps)')
    - Strips website branding and redundant labels (e.g., '- Pagalnew', 'Mp3 Song')
    - Preserves meaningful title tokens like 'Remix', 'Version', 'Acoustic', etc.
    """
    if not raw_title:
        return "Track"

    # Strip track number prefixes
    clean = re.sub(r"^\s*\d{1,3}\s*[-–.]\s*", "", raw_title)
    
    # Strip bitrate suffixes
    clean = re.sub(r"\s*[\[\(]\s*\d{2,3}\s*k(?:bps)?\s*[\]\)]", "", clean, flags=re.IGNORECASE)
    
    # Strip website branding & redundant song suffixes
    clean = re.sub(r"\s*[-–]\s*(?:Pagalnew|PagalWorld|DjSong|Download|Web|Original).*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*Download\s*Pagalnew.*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*Mp3\s*Songs?.*$", "", clean, flags=re.IGNORECASE)

    # If song title ends with '- <AlbumName>', remove redundant album suffix
    if album_title:
        clean_alb = re.sub(r"\s*Mp3\s*Songs?.*$", "", album_title, flags=re.IGNORECASE).strip()
        if clean_alb and clean.lower().endswith(f" - {clean_alb.lower()}"):
            clean = clean[:-len(f" - {clean_alb}")].strip()

    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or raw_title

def clean_album_title(raw_album: Optional[str]) -> str:
    """Produces clean album folder name."""
    if not raw_album or not raw_album.strip():
        return "Singles"
    clean = re.sub(r"\s*Mp3\s*Songs?(?:\s*Download\s*Pagalnew)?.*$", "", raw_album, flags=re.IGNORECASE).strip()
    return clean or "Singles"

class StorageManager:
    def __init__(self, base_download_dir: Optional[Path] = None):
        self.base_dir = (base_download_dir or settings.download_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def set_download_dir(self, new_dir: Path) -> None:
        self.base_dir = new_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def resolve_track_path(
        self,
        artist: str,
        album: str,
        track_title: str,
        bitrate_kbps: int = 320,
        track_num: Optional[int] = None,
        extension: str = ".mp3",
        disambiguate_if_exists: bool = True
    ) -> Path:
        """Constructs album-based Windows folder hierarchy:
        <download_dir>/<Album>/<Clean Title.mp3>
        
        - All tracks from the same album go into the same album folder.
        - No singer/composer subfolders are created.
        - Track numbers and bitrates are removed from the filename (kept in ID3 tags).
        - Handles duplicate title collisions safely (e.g. 'Title (1).mp3').
        """
        assert_safe_audio_extension(extension)

        safe_album = sanitize_filename(clean_album_title(album))
        target_dir = self.base_dir / safe_album

        base_title = clean_song_title(track_title, album)
        safe_base_title = sanitize_filename(base_title)

        target_file = target_dir / f"{safe_base_title}{extension}"

        # Resolve duplicate filename collisions if the file already exists on disk
        if disambiguate_if_exists and target_file.exists():
            counter = 1
            while target_file.exists():
                target_file = target_dir / f"{safe_base_title} ({counter}){extension}"
                counter += 1

        # Guard against directory traversal
        try:
            resolved_target = target_file.resolve()
            if not str(resolved_target).startswith(str(self.base_dir)):
                raise SecurityError(f"Directory traversal detected: {resolved_target}")
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Path resolution error: {str(e)}")

        target_dir.mkdir(parents=True, exist_ok=True)
        return resolved_target

    def get_partial_path(self, target_file: Path) -> Path:
        """Returns temporary .part path for active/resumable downloads."""
        return target_file.with_name(f"{target_file.name}.part")

    def get_tagging_path(self, target_file: Path) -> Path:
        """Returns temporary .tagging path for atomic ID3 operations."""
        return target_file.with_name(f"{target_file.name}.tagging")

storage = StorageManager()
