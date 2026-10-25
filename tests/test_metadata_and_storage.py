import pytest
import shutil
from pathlib import Path
from mutagen.id3 import ID3
import httpx

from app.services.storage import StorageManager, clean_song_title, clean_album_title
from app.services.metadata import MetadataService, metadata_service
from app.models.domain import Track, Album, DownloadTask, DownloadStatus
from app.database import db

# Synthetic minimal valid MP3 frame payload (MPEG-1 Layer 3, 320 kbps, 44.1 kHz)
# Frame sync: 0xFFFB9064 followed by dummy audio payload
SYNTHETIC_MP3_PAYLOAD = b"\xff\xfb\x90\x64" * 100
DUMMY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + (b"\x12" * 40) + b"\xff\xd9"

def create_sample_mp3(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as f:
        # Standard ID3 header + synthetic MP3 frames
        f.write(b"ID3\x03\x00\x00\x00\x00\x00\x00" + SYNTHETIC_MP3_PAYLOAD)
    return destination

def test_album_based_folder_organisation(tmp_path: Path):
    """Verifies that all tracks from an album are saved into <download_dir>/<Album>/<Song.mp3>
    without singer or composer subfolders.
    """
    storage = StorageManager(base_download_dir=tmp_path)
    
    path1 = storage.resolve_track_path(
        artist="Himesh Reshammiya",
        album="Namastey London",
        track_title="Chakna Chakna",
        track_num=1
    )
    path2 = storage.resolve_track_path(
        artist="Rahat Fateh Ali Khan",
        album="Namastey London",
        track_title="Main Jahaan Rahoon",
        track_num=2
    )

    # 1. Both must share the exact same album directory
    assert path1.parent == path2.parent
    assert path1.parent.name == "Namastey London"
    assert path1.parent.parent == tmp_path

    # 2. Filenames must be clean without singer, track number, or bitrate suffixes
    assert path1.name == "Chakna Chakna.mp3"
    assert path2.name == "Main Jahaan Rahoon.mp3"

def test_clean_song_title_rules():
    """Verifies clean filename rules:
    - Removes track number prefixes
    - Removes bitrate suffixes
    - Removes website branding
    - Preserves words like 'Remix', 'Version', 'Acoustic', etc.
    """
    assert clean_song_title("Chakna Chakna") == "Chakna Chakna"
    assert clean_song_title("Chakna Chakna Remix") == "Chakna Chakna Remix"
    assert clean_song_title("01 - Rafta Rafta [320k] - Pagalnew") == "Rafta Rafta"
    assert clean_song_title("05. Kun Faya Kun (320kbps)") == "Kun Faya Kun"
    assert clean_song_title("Tera Mera Rishta (Acoustic Version) Mp3 Song") == "Tera Mera Rishta (Acoustic Version)"
    assert clean_song_title("Yeh Awarapan - Awarapan 2 Mp3 Song", "Awarapan 2") == "Yeh Awarapan"
    assert clean_song_title("Rockstar Theme") == "Rockstar Theme"

def test_duplicate_filename_collision_handling(tmp_path: Path):
    """Verifies safe resolution of duplicate filenames without overwriting."""
    storage = StorageManager(base_download_dir=tmp_path)
    
    # First track
    path1 = storage.resolve_track_path(
        artist="Artist A",
        album="Greatest Hits",
        track_title="Intro",
        track_num=1,
        disambiguate_if_exists=True
    )
    create_sample_mp3(path1)

    # Second track with the identical name in the same album
    path2 = storage.resolve_track_path(
        artist="Artist B",
        album="Greatest Hits",
        track_title="Intro",
        track_num=2,
        disambiguate_if_exists=True
    )
    create_sample_mp3(path2)

    # Third track with identical name
    path3 = storage.resolve_track_path(
        artist="Artist C",
        album="Greatest Hits",
        track_title="Intro",
        track_num=3,
        disambiguate_if_exists=True
    )

    assert path1.name == "Intro.mp3"
    assert path2.name == "Intro (1).mp3"
    assert path3.name == "Intro (2).mp3"
    assert path1 != path2 != path3

def test_id3_tag_writing_and_reopening(tmp_path: Path):
    """Verifies ID3v2.3 tag writing and persistence upon reopening."""
    test_file = create_sample_mp3(tmp_path / "Namastey London" / "Chakna Chakna.mp3")

    track = Track(
        id="trk-101",
        album_id="alb-01",
        provider="pagalnew",
        title="Chakna Chakna",
        artists=["Himesh Reshammiya"],
        composer="Himesh Reshammiya",
        track_number=1,
        qualities=[]
    )
    album = Album(
        id="alb-01",
        provider="pagalnew",
        title="Namastey London",
        year=2007,
        artists=["Himesh Reshammiya", "Rahat Fateh Ali Khan"],
        composer="Himesh Reshammiya",
        language="Bollywood",
        tracks=[track]
    )

    # Apply tags
    metadata_service.apply_id3_metadata(
        file_path=test_file,
        track=track,
        album=album,
        cover_bytes=DUMMY_JPEG,
        cover_mime="image/jpeg"
    )

    # Reopen and inspect with Mutagen ID3
    tags = ID3(str(test_file))

    # Verify ID3 version is 2.3
    assert tags.version[0] == 2
    assert tags.version[1] == 3

    # Check fields
    assert tags.get("TIT2").text == ["Chakna Chakna"]
    assert tags.get("TPE1").text == ["Himesh Reshammiya"]
    assert tags.get("TALB").text == ["Namastey London"]
    assert tags.get("TPE2").text == ["Himesh Reshammiya, Rahat Fateh Ali Khan"]
    assert tags.get("TRCK").text == ["1/1"]
    assert str(tags.get("TDRC").text[0]) == "2007"
    assert tags.get("TCOM").text == ["Himesh Reshammiya"]
    assert tags.get("TCON").text == ["Bollywood"]

    # Verify embedded artwork
    apic_frames = tags.getall("APIC")
    assert len(apic_frames) == 1
    cover = apic_frames[0]
    assert cover.type == 3  # PictureType.COVER_FRONT
    assert cover.mime == "image/jpeg"
    assert cover.data == DUMMY_JPEG

def test_audio_bitstream_payload_not_reencoded(tmp_path: Path):
    """Verifies that ID3 tag injection preserves the original audio bitstream
    without transcoding or re-encoding.
    """
    test_file = create_sample_mp3(tmp_path / "bitstream_test.mp3")
    
    # Record original synthetic MP3 frame bytes
    with open(test_file, "rb") as f:
        original_bytes = f.read()
    assert SYNTHETIC_MP3_PAYLOAD in original_bytes

    track = Track(
        id="trk-bitstream",
        album_id="alb-test",
        provider="mock",
        title="Pure Audio Test",
        artists=["Singer"],
        track_number=1,
        qualities=[]
    )

    metadata_service.apply_id3_metadata(test_file, track)

    # Read back bytes after tagging
    with open(test_file, "rb") as f:
        tagged_bytes = f.read()

    # The audio frame payload must still be bit-for-bit identical inside the file
    assert SYNTHETIC_MP3_PAYLOAD in tagged_bytes

def test_missing_metadata_resilience(tmp_path: Path):
    """Verifies that missing artwork, composer, or year does not fail tagging or corrupt file."""
    test_file = create_sample_mp3(tmp_path / "minimal.mp3")

    track = Track(
        id="trk-min",
        album_id="alb-min",
        provider="mock",
        title="Minimal Track",
        artists=[],
        track_number=None,
        qualities=[]
    )

    # Tag with minimal info and NO cover artwork
    success = metadata_service.apply_id3_metadata(
        file_path=test_file,
        track=track,
        album=None,
        cover_bytes=None
    )
    assert success is True

    tags = ID3(str(test_file))
    assert tags.get("TIT2").text == ["Minimal Track"]
    assert len(tags.getall("APIC")) == 0

def test_interrupted_write_protection(tmp_path: Path, monkeypatch):
    """Verifies that failure during tag writing does not corrupt the completed destination file."""
    test_file = create_sample_mp3(tmp_path / "safe_atomic.mp3")
    with open(test_file, "rb") as f:
        original_content = f.read()

    # Simulate an error during ID3 tag saving
    def fail_save(*args, **kwargs):
        raise OSError("Simulated disk error or write interruption")

    from mutagen.id3 import ID3
    monkeypatch.setattr(ID3, "save", fail_save)

    track = Track(id="t-err", album_id="a-err", provider="mock", title="Error Song", qualities=[])

    with pytest.raises(Exception, match="Failed to apply metadata"):
        metadata_service.apply_id3_metadata(test_file, track)

    # The original file must remain intact and uncorrupted
    assert test_file.exists()
    with open(test_file, "rb") as f:
        assert f.read() == original_content

    # Temporary .tagging file must have been cleaned up
    tagging_file = test_file.with_name(f"{test_file.name}.tagging")
    assert not tagging_file.exists()

@pytest.mark.asyncio
async def test_queue_and_history_control_endpoints(async_client, temp_env):
    """Verifies controls to clear completed/failed history and pending queue tasks."""
    # Seed download tasks with varied statuses
    now = 10000.0
    task_queued = DownloadTask(
        task_id="t-q1", track_id="1", album_id="a", provider="mock",
        title="Queued Song", artist="A", album_title="Alb", selected_bitrate=320,
        download_url="http://test/1", target_file_path="p1", status=DownloadStatus.QUEUED,
        created_at=now, updated_at=now
    )
    task_active = DownloadTask(
        task_id="t-active", track_id="2", album_id="a", provider="mock",
        title="Active Song", artist="A", album_title="Alb", selected_bitrate=320,
        download_url="http://test/2", target_file_path="p2", status=DownloadStatus.DOWNLOADING,
        created_at=now, updated_at=now
    )
    task_done = DownloadTask(
        task_id="t-done", track_id="3", album_id="a", provider="mock",
        title="Done Song", artist="A", album_title="Alb", selected_bitrate=320,
        download_url="http://test/3", target_file_path="p3", status=DownloadStatus.COMPLETED,
        created_at=now, updated_at=now
    )
    task_failed = DownloadTask(
        task_id="t-fail", track_id="4", album_id="a", provider="mock",
        title="Failed Song", artist="A", album_title="Alb", selected_bitrate=320,
        download_url="http://test/4", target_file_path="p4", status=DownloadStatus.FAILED,
        created_at=now, updated_at=now
    )

    db.save_task(task_queued)
    db.save_task(task_active)
    db.save_task(task_done)
    db.save_task(task_failed)
    db.record_completed_history(task_done)

    # 1. Clear pending queue
    res_pending = await async_client.post("/api/downloads/queue/clear-pending")
    assert res_pending.status_code == 200
    assert res_pending.json()["cleared_count"] == 1
    # Active, completed, and failed tasks must still exist
    assert db.get_task("t-q1") is None
    assert db.get_task("t-active") is not None
    assert db.get_task("t-done") is not None

    # 2. Clear failed tasks from queue
    res_failed = await async_client.post("/api/downloads/queue/clear-failed")
    assert res_failed.status_code == 200
    assert res_failed.json()["cleared_count"] == 1
    assert db.get_task("t-fail") is None

    # 3. Clear completed queue tasks
    res_comp = await async_client.post("/api/downloads/queue/clear-completed")
    assert res_comp.status_code == 200
    assert res_comp.json()["cleared_count"] == 1
    assert db.get_task("t-done") is None

    # 4. Clear history records
    history_before = db.get_history()
    assert len(history_before) >= 1
    res_hist = await async_client.post("/api/downloads/history/clear")
    assert res_hist.status_code == 200
    assert len(db.get_history()) == 0
