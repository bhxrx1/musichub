# MusicHub — Music Discovery & Download Manager

MusicHub is a desktop-friendly music discovery and batch download application built with Python 3.12+, FastAPI, SQLite, and a responsive frontend.

---

## Key Features

- **Unified Search:** Search across movies/albums, singers, composers, song titles, and release years.
- **Rich Album Inspector:** Inspect album artwork, tracklists, artists, composers, starcasts, and available audio bitrates.
- **Audio Quality Policy:**
  - Prefers verified 320 kbps when explicitly available from the source.
  - Transparent fallback to lower bitrates (e.g. 128 kbps) with clear labeling.
  - Optional **Strict 320 kbps Mode** to automatically skip unconfirmed or lower-quality audio.
  - Original audio bitstreams are strictly preserved (no artificial upscaling).
- **Resumable Batch Downloads:**
  - Supports HTTP Range requests to pause and resume partial `.part` downloads seamlessly.
  - Bounded retries with exponential backoff on transient network drops.
  - Clean cancellation and partial file cleanup.
- **Configurable Concurrency:** Polite download concurrency limits with asynchronous semaphores.
- **Persistent Storage:** SQLite (WAL mode) for queue states, track cache, and download history.
- **Directory Hierarchy:** Safe Windows file organisation (`<download_dir>/<Artist>/<Album>/<Track [320k].mp3>`).
- **Security & Integrity:**
  - Whitelist-based SSRF (Server-Side Request Forgery) protection on download domains.
  - Windows path sanitization & directory traversal mitigation.
  - Rejection of executable and script extensions.

---

## Windows Setup & Launch Guide

### Prerequisites
- Windows 10 / 11
- Python 3.12+ (verified on Python 3.14.0)

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

Execute the complete test suite to verify database, providers, download manager, and API:

```powershell
pytest -v
```

### 5. Launch the Application

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
├── requirements.txt                   # Dependency definitions
├── app/
│   ├── config.py                      # Application settings & security whitelists
│   ├── database.py                    # SQLite schema, WAL mode, repositories
│   ├── models/
│   │   ├── domain.py                  # Album, Track, QualityOption, DownloadTask models
│   │   └── schemas.py                 # API request/response models
│   ├── providers/
│   │   ├── base.py                    # BaseMusicProvider abstract base class
│   │   ├── mock_provider.py           # Mock provider with realistic catalogue
│   │   └── registry.py                # Multi-provider registry & aggregator
│   ├── services/
│   │   ├── download_manager.py        # Concurrency, resume, retry, ETA, queue state machine
│   │   ├── storage.py                 # File hierarchy, safe path resolution, .part handling
│   │   └── security.py                # SSRF domain validation & path sanitization
│   ├── api/
│   │   ├── router.py                  # API route aggregation
│   │   ├── routes_search.py           # Search and album/track discovery
│   │   ├── routes_downloads.py        # Queue management, single/batch start, cancel, retry
│   │   ├── routes_settings.py         # Config updates & provider health diagnostics
│   │   └── routes_mock_cdn.py         # Local audio CDN simulator with HTTP Range support
│   └── static/
│       ├── css/app.css                # Desktop-friendly dark responsive styling
│       ├── js/app.js                  # Frontend SPA client & real-time queue polling
│       └── index.html                 # Main interface
└── tests/
    ├── conftest.py                    # Test fixtures & isolated temp environments
    ├── test_providers.py              # Provider search & metadata tests
    ├── test_quality_policy.py         # 320k preference & strict-mode tests
    ├── test_download_manager.py       # Queue & concurrency tests
    ├── test_resumable_retry.py        # Range resuming & retry exhaustion tests
    ├── test_storage_security.py       # SSRF & path traversal tests
    └── test_api.py                    # End-to-end FastAPI endpoint tests
```

---

## API Summary

- `GET /api/search?q={query}&provider={id}` — Search songs and albums.
- `GET /api/albums/{provider}/{album_id}` — Get album details with full tracklist.
- `GET /api/downloads/queue` — Fetch live queue status, speed, progress, and ETA.
- `POST /api/downloads/start` — Enqueue single track.
- `POST /api/downloads/batch` — Enqueue batch tracks from an album.
- `POST /api/downloads/{task_id}/cancel` — Cancel an in-flight download.
- `POST /api/downloads/{task_id}/retry` — Retry a failed download.
- `GET /api/downloads/history` — View completed download history.
- `GET /api/diagnostics/providers` — Check provider latency and health.
