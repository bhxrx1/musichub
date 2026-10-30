import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
import httpx
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TALB,
    TPE2,
    TRCK,
    TDRC,
    TCOM,
    TCON,
    APIC,
    ID3NoHeaderError,
)

from ..models.domain import Track, Album
from .security import validate_download_url, SecurityError
from .storage import clean_song_title, clean_album_title, safe_replace_file, safe_unlink_file

class MetadataError(Exception):
    """Raised when ID3 metadata tagging or validation fails."""
    pass

class MetadataService:
    def __init__(self):
        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 MusicHub/1.2"
        )

    async def fetch_artwork_bytes(self, artwork_url: Optional[str]) -> Tuple[Optional[bytes], str]:
        """Asynchronously retrieves album artwork at highest available resolution.
        Returns (image_bytes, mime_type) or (None, '') on failure.
        Never throws or halts the download if artwork fails.
        """
        if not artwork_url:
            return None, ""

        try:
            validate_download_url(artwork_url)
        except SecurityError as se:
            print(f"[Metadata] Artwork URL rejected by SSRF guard: {se}")
            return None, ""

        try:
            async with httpx.AsyncClient(headers={"User-Agent": self._user_agent}, follow_redirects=True, timeout=8.0) as client:
                resp = await client.get(artwork_url)
                if resp.status_code == 200 and resp.content:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "png" in content_type:
                        mime = "image/png"
                    elif "webp" in content_type:
                        mime = "image/webp"
                    else:
                        mime = "image/jpeg"
                    return resp.content, mime
                else:
                    print(f"[Metadata] Artwork fetch returned HTTP {resp.status_code}")
                    return None, ""
        except Exception as e:
            print(f"[Metadata] Non-fatal error retrieving artwork ({artwork_url}): {e}")
            return None, ""

    def apply_id3_metadata(
        self,
        file_path: Path,
        track: Track,
        album: Optional[Album] = None,
        cover_bytes: Optional[bytes] = None,
        cover_mime: str = "image/jpeg"
    ) -> bool:
        """Applies verified ID3v2.3 tags and embedded artwork.
        
        Preserves original audio bitstream without re-encoding.
        Uses an atomic copy-modify-replace workflow so interrupted operations
        cannot corrupt completed audio files.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Target file not found: {file_path}")

        # 1. Create temporary working file for atomic modification
        tagging_file = file_path.with_name(f"{file_path.name}.tagging")
        shutil.copyfile(file_path, tagging_file)

        try:
            # 2. Initialise or load ID3 tag set
            try:
                tags = ID3(str(tagging_file))
            except ID3NoHeaderError:
                tags = ID3()

            # Clean and distinct metadata concepts
            clean_title = clean_song_title(track.title, album.title if album else None)
            album_title = clean_album_title(album.title if album else track.album_id)

            # TIT2: Track Title
            tags.setall("TIT2", [TIT2(encoding=3, text=clean_title)])

            # TPE1: Track Artist / Lead Singer(s) (prefer track-specific singers)
            track_singers = track.artists if track.artists else (album.artists if album else ["Unknown Artist"])
            tags.setall("TPE1", [TPE1(encoding=3, text=[", ".join(track_singers)])])

            # TALB: Album Title
            tags.setall("TALB", [TALB(encoding=3, text=album_title)])

            # TPE2: Album Artist (compilation or album-level credit)
            album_artist = ", ".join(album.artists) if album and album.artists else ", ".join(track_singers)
            tags.setall("TPE2", [TPE2(encoding=3, text=[album_artist or "Various Artists"])])

            # TRCK: Track Number
            if track.track_number is not None:
                total_str = f"/{len(album.tracks)}" if album and album.tracks else ""
                track_val = f"{track.track_number}{total_str}"
                tags.setall("TRCK", [TRCK(encoding=3, text=track_val)])

            # TDRC: Release Year
            year_val = None
            if album and album.year:
                year_val = str(album.year)
            if year_val:
                tags.setall("TDRC", [TDRC(encoding=3, text=year_val)])

            # TCOM: Music Director / Composer
            composer_val = track.composer or (album.composer if album else None)
            if composer_val:
                tags.setall("TCOM", [TCOM(encoding=3, text=composer_val)])

            # TCON: Genre (when supported by source)
            genre_val = (album.language if album and album.language else "Bollywood")
            if genre_val:
                tags.setall("TCON", [TCON(encoding=3, text=genre_val)])

            # APIC: Front Cover Artwork (Picture type 3)
            if cover_bytes and len(cover_bytes) > 0:
                tags.delall("APIC")
                tags.add(APIC(
                    encoding=3,
                    mime=cover_mime,
                    type=3,  # Front cover
                    desc="Cover",
                    data=cover_bytes
                ))

            # 3. Save as ID3v2.3 for maximum desktop and media player compatibility
            tags.save(str(tagging_file), v2_version=3)

            # 4. Validate output by reopening and reading back tags
            verification = ID3(str(tagging_file))
            if not verification.get("TIT2"):
                raise MetadataError("ID3 validation failed: TIT2 header missing")

            # 5. Atomically replace final file with verified tagged file
            safe_replace_file(tagging_file, file_path)
            return True

        except Exception as e:
            # Clean up working file on failure
            safe_unlink_file(tagging_file)
            raise MetadataError(f"Failed to apply metadata: {e}")

metadata_service = MetadataService()
