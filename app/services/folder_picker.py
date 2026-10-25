import os
import sys
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def validate_directory_path(path_str: str) -> Tuple[bool, str, Optional[Path]]:
    """Validates that a directory path is safe, absolute, accessible, and writable on Windows.
    
    Returns:
        (is_valid, message, resolved_path)
    """
    if not path_str or not path_str.strip():
        return False, "Directory path cannot be empty.", None

    clean_str = path_str.strip().strip('"').strip("'")
    
    try:
        p = Path(clean_str)
    except Exception as e:
        return False, f"Invalid path format: {str(e)}", None

    if not p.is_absolute():
        return False, f"Path must be an absolute Windows path (e.g., C:\\Music or D:\\Downloads). Received: '{clean_str}'", None

    # Check for reserved Windows device names in path parts
    for part in p.parts:
        root_name = part.split(":")[0] if ":" in part else part
        base = root_name.split(".")[0].upper()
        if base in RESERVED_WINDOWS_NAMES:
            return False, f"Path contains reserved Windows device name: '{base}'", None

    # Check for forbidden wildcards in path
    for bad_char in ['*', '?', '<', '>', '|']:
        if bad_char in clean_str:
            return False, f"Path contains illegal character '{bad_char}'.", None

    # Test directory creation / accessibility
    try:
        p.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return False, f"Permission denied creating or accessing directory: '{clean_str}'", None
    except OSError as e:
        return False, f"Cannot access directory '{clean_str}': {str(e)}", None

    if not p.is_dir():
        return False, f"Target path exists but is not a directory: '{clean_str}'", None

    # Test write permissions via temporary probe file
    probe_file = p / f".musichub_write_probe_{uuid.uuid4().hex}.tmp"
    try:
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
    except PermissionError:
        return False, f"Directory is not writable. Please check permissions: '{clean_str}'", None
    except OSError as e:
        return False, f"Write check failed on directory '{clean_str}': {str(e)}", None

    return True, "Directory is valid and writable.", p.resolve()


def _ask_tkinter(initial_dir: Optional[str]) -> Optional[str]:
    """Launch native folder picker via tkinter."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    try:
        root.wm_attributes("-topmost", 1)
    except Exception:
        pass

    init_path = initial_dir if initial_dir and Path(initial_dir).exists() else None
    selected = filedialog.askdirectory(
        initialdir=str(init_path) if init_path else None,
        title="Select MusicHub Download Directory"
    )
    root.destroy()
    return selected.strip() if selected else None


def _ask_powershell(initial_dir: Optional[str]) -> Optional[str]:
    """Launch native folder picker via PowerShell System.Windows.Forms fallback."""
    import subprocess

    init_script = f"$dialog.SelectedPath = '{initial_dir}'; " if initial_dir and Path(initial_dir).exists() else ""
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = 'Select MusicHub Download Directory'; "
        "$dialog.ShowNewFolderButton = $true; "
        + init_script +
        "$result = $dialog.ShowDialog(); "
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }"
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=120
    )
    out = res.stdout.strip()
    return out if out else None


def open_native_folder_picker(initial_dir: Optional[str] = None) -> Dict[str, Any]:
    """Safely opens the native Windows folder picker dialog.
    
    Tries tkinter first; falls back to PowerShell WinForms.
    Returns:
        {
            "selected_path": Optional[str],
            "cancelled": bool,
            "available": bool,
            "error": Optional[str]
        }
    """
    # 1. Try Tkinter
    try:
        path = _ask_tkinter(initial_dir)
        if path:
            return {"selected_path": str(Path(path).resolve()), "cancelled": False, "available": True, "error": None}
        return {"selected_path": None, "cancelled": True, "available": True, "error": None}
    except Exception as tk_err:
        pass

    # 2. Try PowerShell fallback
    try:
        path = _ask_powershell(initial_dir)
        if path:
            return {"selected_path": str(Path(path).resolve()), "cancelled": False, "available": True, "error": None}
        return {"selected_path": None, "cancelled": True, "available": True, "error": None}
    except Exception as ps_err:
        return {
            "selected_path": None,
            "cancelled": False,
            "available": False,
            "error": "Native folder dialog is unavailable in this environment. You can enter or paste the folder path directly."
        }
