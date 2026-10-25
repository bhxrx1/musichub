# MusicHub — Music Discovery & Download Manager

MusicHub is a desktop-friendly music discovery and batch download application built with Python 3.12+, FastAPI, SQLite, Mutagen, and a responsive frontend.

---

## Key Features

- **Unified Search:** Search across movies/albums, singers, composers, song titles, and release years.
- **Dedicated Browse Website with Real Pagination:**
  - Real multi-page pagination (Previous, Next, Current Page indicator, and total page limits).
  - Explores categories: **Bollywood 2026**, **Bollywood 2025**, **Bollywood Trending**, **Hindi Pop / Indipop**, **Punjabi Mp3**, **Haryanvi**, and **Bhojpuri**.
  - Dynamic page transitions with automatic page reset upon category switching.
  - Transparent fallback handling for websites restricting direct iframe embedding via `X-Frame-Options: SAMEORIGIN, DENY`.
  - 1-click album inspection to fetch the complete album tracklist, metadata, and start single-track or batch downloads.
- **Native Windows Folder Picker & Path Validation:**
  - **Browse Folder** button launches a genuine Windows folder picker dialog (`tkinter` with fallback to PowerShell `System.Windows.Forms.FolderBrowserDialog`).
  - Strict validation of chosen download directories: requires absolute Windows paths, verifies write permissions using probe files, and prevents reserved DOS device names (`CON`, `PRN`, `AUX`, `NUL`, etc.).
  - Fallback-resilient: users can paste or type arbitrary absolute paths directly if native GUI dialogs are unavailable in their environment.
  - Changes to the root download directory take effect immediately for all subsequent downloads without moving or deleting existing downloaded files.
- **Global Queue Controls (Pause All, Resume All, Cancel All):**
  - **⏸ Pause All:** Safely halts active network streams, prevents queued tasks from starting, marks tasks as `PAUSED`, and preserves `.part` files on disk.
  - **▶ Resume All:** Seamlessly resumes all paused downloads from partial progress via HTTP Range requests without re-downloading existing bytes or launching duplicate workers.
  - **⏹ Cancel All:** Requests confirmation, stops active network transfers and queued tasks, cleanly removes partial `.part` files, and prevents tasks from being accidentally restarted. Completed MP3 files and history records are preserved.
  - Individual task controls to pause, resume, cancel, or retry downloads.
- **Album-Based Folder Organisation:**
  - Files are saved directly into `<download_dir>/<Album Title>/<Clean Song Title.mp3>`.
  - No singer or composer subfolders, ensuring all songs from an album remain grouped together.
  - Clean filenames without track-number prefixes, bitrate suffixes (e.g. `[320k]`), or website branding.
  - Automatic duplicate filename collision handling (e.g., `Title (1).mp3`).
  - Strict Windows invalid filename character sanitisation and path traversal guards.
- **Embedded ID3v2.3 Metadata & Front-Cover Artwork:**
  - Embeds standard ID3v2.3 tags using Mutagen:
    - **TIT2**: Song Title
    - **TPE1**: Track Artist / Singers
    - **TALB**: Album Name
    - **TPE2**: Album Artist
    - **TRCK**: Track Number / Total Tracks
    - **TDRC**: Release Year
    - **TCOM**: Music Director / Composer
    - **TCON**: Genre
    - **APIC**: Original high-resolution Front-Cover Artwork (type 3, `image/jpeg` or `image/png`)
  - **Zero Audio Re-encoding:** Audio bitstreams are strictly preserved bit-for-bit without lossy recompression.
  - **Atomic Writing & Validation:** Writes metadata to a temporary `.tagging` file, validates ID3 headers, and atomically swaps it over the destination file.
- **Audio Quality Policy:**
  - Prefers verified 320 kbps when explicitly available from the source.
  - Transparent fallback to lower bitrates (e.g. 128 kbps) with clear labeling.
  - Optional **Strict 320 kbps Mode** to automatically skip unconfirmed or lower-quality audio.
- **Resumable Batch Downloads:**
  - Supports HTTP Range requests to pause and resume partial `.part` downloads seamlessly.
  - Bounded retries with exponential backoff on transient network drops.
  - Clean cancellation and partial file cleanup.
- **Queue Maintenance & History Controls:**
  - Independent queue controls: **Clear Pending**, **Clear Completed**, and **Clear Failed** tasks.
  - **Clear History** control to wipe historical download logs without deleting downloaded audio files on disk.
  - Confirmation modals before destructive queue/history operations.
- **Configurable Concurrency & Storage:**
  - Configurable download directory in Settings.
  - Polite download concurrency limits with asynchronous semaphores.
  - Persistent SQLite database (WAL mode) with automatic migration for new schema fields.
- **Configurable Provider Settings:**
  - Centralized `pagalnew_base_url` in Settings, allowing mirror domain updates while keeping SSRF protection dynamically in sync.
- **Security & Integrity:**
  - Whitelist-based SSRF (Server-Side Request Forgery) protection on download domains.
  - Windows path sanitization & directory traversal mitigation.
  - Rejection of executable and script extensions.

---

## Windows Setup & Launch Guide

### Prerequisites
- Windows 10 / 11
- Python 3.12+ (tested & verified on Python 3.14.0)
- Tkinter (standard in standard Python Windows installers) or PowerShell (for the native folder picker dialog)

### 1. Open PowerShell and Navigate to the Project

```powershell
cd C:\Users\Bharat\.gemini\antigravity\scratch\musichub
```

*(Recommended: Set this folder as your active workspace in your IDE).*

### 2. (Optional) Create and Activate Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run Automated Tests

Execute the complete test suite to verify database, providers, download manager, metadata tagging, folder picker, global pause/resume/cancel controls, pagination, and API endpoints:

```powershell
$env:PYTHONPATH="."
pytest -v
```

All 46 unit and integration tests run offline against fixtures without depending on live network conditions.

### 5. Run Live Verification Scripts

To test real-world search, metadata extraction, download streaming, and Mutagen ID3 tagging against live PagalNew:

```powershell
python scripts/run_live_workflow.py
```

To test real-world category browsing, multi-page pagination, and full album tracklist fetching:

```powershell
python scripts/test_live_browse_pagination.py
```

### 6. Launch the Application

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## Project Structure

```
musichub/
├── README.md                          # Documentation and instructions
├── pytest.ini                         # Pytest configuration
├── requirements.txt                   # Dependency definitions (FastAPI, uvicorn, httpx, mutagen, etc.)
├── scripts/
│   ├── run_live_workflow.py           # Live end-to-end download & ID3 tagging test script
│   └── test_live_browse_pagination.py # Live category pagination & tracklist test script
├── app/
│   ├── config.py                      # Application settings & dynamic security whitelists
│   ├── database.py                    # SQLite schema, WAL mode, migrations, repositories
│   ├── models/
│   │   ├── domain.py                  # Album, Track, QualityOption, DownloadTask models
│   │   └── schemas.py                 # API request/response models & pagination schemas
│   ├── providers/
│   │   ├── base.py                    # BaseMusicProvider abstract base class
│   │   ├── mock_provider.py           # Mock provider with realistic catalogue & pagination
│   │   ├── pagalnew_provider.py       # Live PagalNew search, category browse & pagination parser
│   │   └── registry.py                # Multi-provider registry & aggregator
│   ├── services/
│   │   ├── download_manager.py        # Concurrency, pause/resume, cancel all, ETA, state machine
│   │   ├── folder_picker.py           # Windows native folder picker & directory validation service
│   │   ├── metadata.py                # Mutagen ID3v2.3 tagger, atomic writer, bitstream validator
│   │   ├── storage.py                 # Album-based folder hierarchy, clean title rules, safe collisions
│   │   └── security.py                # SSRF domain validation & path sanitization
│   ├── api/
│   │   ├── router.py                  # API route aggregation
│   │   ├── routes_search.py           # Search, browse categories with pagination, album discovery
│   │   ├── routes_downloads.py        # Queue management, pause/resume/cancel all, queue clear
│   │   ├── routes_settings.py         # Config updates, folder picker endpoint, provider diagnostics
│   │   └── routes_mock_cdn.py         # Local audio CDN simulator with HTTP Range support
│   └── static/
│       ├── css/app.css                # Desktop-friendly dark responsive styling & pagination controls
│       ├── js/app.js                  # Frontend SPA client with search, browse, pagination, queue, and settings
│       └── index.html                 # Main interface
└── tests/
    ├── conftest.py                    # Test fixtures & isolated temp environments
    ├── test_providers.py              # Mock provider search & metadata tests
    ├── test_pagalnew_provider.py      # Real PagalNew provider HTML parser tests
    ├── test_quality_policy.py         # 320k preference & strict-mode tests
    ├── test_download_manager.py       # Queue & concurrency tests
    ├── test_folder_picker_and_global_controls.py # Folder picker, pause/resume/cancel, active cancel, pagination tests
    ├── test_metadata_and_storage.py   # Folder hierarchy, clean titles, ID3v2.3, bitstream preservation
    ├── test_resumable_retry.py        # Range resuming & retry exhaustion tests
    ├── test_storage_security.py       # SSRF & path traversal tests
    └── test_api.py                    # End-to-end FastAPI endpoint tests
```

---

## API Summary

### Discovery & Search
- `GET /api/search?q={query}&provider={id}` — Search songs and albums.
- `GET /api/browse/{provider}/{category}?page={page}` — Browse category albums with real multi-page pagination.
- `GET /api/albums/{provider}/{album_id}` — Get album details with full tracklist and singer credits.
- `GET /api/tracks/{provider}/{track_id}` — Get track details and verified bitrates.

### Download Management & Controls
- `GET /api/downloads/queue` — Fetch live queue status, speed, progress, active/queued/paused counts, and ETA.
- `POST /api/downloads/start` — Enqueue single track.
- `POST /api/downloads/batch` — Enqueue batch tracks from an album.
- `POST /api/downloads/queue/pause-all` — Pause all active and queued downloads.
- `POST /api/downloads/queue/resume-all` — Resume all paused downloads from existing progress.
- `POST /api/downloads/queue/cancel-all` — Cancel all active and queued downloads (removes partial files).
- `POST /api/downloads/{task_id}/pause` — Pause a specific download task.
- `POST /api/downloads/{task_id}/resume` — Resume a specific download task.
- `POST /api/downloads/{task_id}/cancel` — Cancel an in-flight download.
- `POST /api/downloads/{task_id}/retry` — Retry a failed download.
- `POST /api/downloads/queue/clear-pending` — Remove pending downloads from queue.
- `POST /api/downloads/queue/clear-completed` — Clear completed downloads from queue.
- `POST /api/downloads/queue/clear-failed` — Clear failed downloads from queue.
- `GET /api/downloads/history` — View completed download history.
- `POST /api/downloads/history/clear` — Clear history records (preserves audio files on disk).

### Settings & Folder Browser
- `GET /api/settings` — Read current application settings.
- `POST /api/settings` — Update settings (download directory with validation, max concurrency, strict 320k mode, `pagalnew_base_url`).
- `POST /api/settings/browse-folder` — Open native Windows folder picker dialog.
- `GET /api/diagnostics/providers` — Check provider latency and health.
