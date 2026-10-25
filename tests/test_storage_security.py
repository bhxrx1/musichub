import pytest
from pathlib import Path
from app.services.security import (
    validate_download_url,
    sanitize_filename,
    assert_safe_audio_extension,
    SecurityError
)
from app.services.storage import StorageManager

def test_ssrf_validation_allowed_and_blocked():
    allowed_domains = {"pagalnew.com", "localhost", "testserver"}

    # Allowed exact and subdomain
    assert validate_download_url("https://pagalnew.com/download.mp3", allowed_domains) is True
    assert validate_download_url("https://320.pagalnew.com/file.mp3", allowed_domains) is True
    assert validate_download_url("http://localhost:8000/stream.mp3", allowed_domains) is True

    # Blocked foreign domains
    with pytest.raises(SecurityError, match="SSRF violation"):
        validate_download_url("https://attacker.com/steal.mp3", allowed_domains)

    with pytest.raises(SecurityError, match="SSRF violation"):
        validate_download_url("https://evil-pagalnew.com/fake.mp3", allowed_domains)

    # Prohibited scheme
    with pytest.raises(SecurityError, match="Prohibited protocol scheme"):
        validate_download_url("file:///C:/Windows/System32/cmd.exe", allowed_domains)

def test_sanitize_filename_windows():
    # Strips illegal characters: < > : " / \ | ? *
    unsafe = 'Song: "The Best?" <Remix>*|/\\'
    safe = sanitize_filename(unsafe)
    for bad_char in '<>:"/\\|?*':
        assert bad_char not in safe

    # Reserved Windows device names
    assert sanitize_filename("CON.mp3").startswith("_")
    assert sanitize_filename("AUX").startswith("_")
    assert sanitize_filename("NUL.mp3").startswith("_")

def test_reject_executable_extensions():
    # Audio extensions must pass
    assert_safe_audio_extension("song.mp3")
    assert_safe_audio_extension("music.flac")
    assert_safe_audio_extension("track.m4a")

    # Executable extensions must raise SecurityError
    for dangerous in ["trojan.exe", "script.bat", "run.ps1", "code.sh", "library.dll"]:
        with pytest.raises(SecurityError, match="Prohibited executable or script extension"):
            assert_safe_audio_extension(dangerous)

def test_storage_manager_path_traversal_defense(tmp_path: Path):
    storage = StorageManager(base_download_dir=tmp_path)
    
    # Normal safe path resolution
    resolved = storage.resolve_track_path(
        artist="Arijit Singh",
        album="Awarapan 2",
        track_title="Yeh Awarapan",
        bitrate_kbps=320,
        track_num=1
    )
    assert str(resolved).startswith(str(tmp_path))
    assert resolved.name.endswith(".mp3")
    assert "Awarapan 2" in str(resolved)
