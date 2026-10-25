import re
import urllib.parse
from typing import Set
from ..config import settings

FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".msc", ".msi", ".dll", ".scr", ".pif", ".cpl", ".hta",
    ".jar", ".py", ".pyw", ".sh", ".bash"
}

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

class SecurityError(Exception):
    """Raised for SSRF, path traversal, or file security violations."""
    pass

def validate_download_url(url: str, allowed_domains: Set[str] = None) -> bool:
    """SSRF Prevention: Restrict download URLs strictly to configured allowed domains."""
    domains = allowed_domains if allowed_domains is not None else settings.allowed_domains
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SecurityError(f"Prohibited protocol scheme: {parsed.scheme}")
        
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise SecurityError("Invalid URL: missing hostname")
        
        # Check against allowed domains
        is_allowed = False
        for allowed in domains:
            allowed_clean = allowed.lower()
            if hostname == allowed_clean or hostname.endswith("." + allowed_clean):
                is_allowed = True
                break
        
        if not is_allowed:
            raise SecurityError(f"SSRF violation: Host '{hostname}' is not in allowed domain whitelist")
        
        return True
    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"URL validation failed: {str(e)}")

def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Sanitize strings for safe Windows file and folder names."""
    if not name:
        return "unnamed"
    
    # Remove illegal Windows characters: < > : " / \ | ? *
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    clean = clean.strip(". ")
    
    # Check reserved Windows device names
    base_stem = clean.split(".")[0].upper()
    if base_stem in WINDOWS_RESERVED_NAMES:
        clean = f"_{clean}"
        
    if not clean:
        clean = "unnamed"
        
    return clean[:max_length]

def assert_safe_audio_extension(file_path: str) -> None:
    """Never execute or store unsafe executable file formats."""
    lower_path = file_path.lower()
    for bad_ext in FORBIDDEN_EXTENSIONS:
        if lower_path.endswith(bad_ext):
            raise SecurityError(f"Prohibited executable or script extension: '{bad_ext}'")
