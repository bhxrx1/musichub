from pathlib import Path
from typing import Optional
from ..config import settings
from .security import sanitize_filename, assert_safe_audio_extension, SecurityError

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
        bitrate_kbps: int,
        track_num: Optional[int] = None,
        extension: str = ".mp3"
    ) -> Path:
        """Constructs safe, structured Windows folder hierarchy:
        <download_dir>/<Artist>/<Album>/<01 - Title [320k].mp3>
        """
        assert_safe_audio_extension(extension)
        
        safe_artist = sanitize_filename(artist or "Unknown Artist")
        safe_album = sanitize_filename(album or "Single")
        
        num_prefix = f"{track_num:02d} - " if track_num is not None else ""
        raw_filename = f"{num_prefix}{track_title} [{bitrate_kbps}k]{extension}"
        safe_filename = sanitize_filename(raw_filename)
        
        target_dir = self.base_dir / safe_artist / safe_album
        target_file = target_dir / safe_filename
        
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

storage = StorageManager()
