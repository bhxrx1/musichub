// MusicHub Web Application Client - Final Master Upgrade
let currentAlbum = null;
let currentTrack = null;
let currentSongBitrate = 320;
let queuePollInterval = null;
let currentBrowseCategory = "bollywood-2026";
let currentBrowsePage = 1;
let currentBrowseTotalPages = null;

// DOM Elements
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const searchClearInputBtn = document.getElementById("searchClearInputBtn");
const searchClearAllBtn = document.getElementById("searchClearAllBtn");
const providerSelect = document.getElementById("providerSelect");
const resultsGrid = document.getElementById("resultsGrid");
const resultsCount = document.getElementById("resultsCount");
const browseGrid = document.getElementById("browseGrid");

// Modals
const albumModal = document.getElementById("albumModal");
const modalClose = document.getElementById("modalClose");
const songModal = document.getElementById("songModal");
const songModalClose = document.getElementById("songModalClose");
const songCancelBtn = document.getElementById("songCancelBtn");
const songDownloadBtn = document.getElementById("songDownloadBtn");

// Queue Elements
const queueTaskList = document.getElementById("queueTaskList");
const queueBadge = document.getElementById("queueBadge");
const pauseAllBtn = document.getElementById("pauseAllBtn");
const resumeAllBtn = document.getElementById("resumeAllBtn");
const cancelAllBtn = document.getElementById("cancelAllBtn");
const clearPendingBtn = document.getElementById("clearPendingBtn");
const clearCompletedQueueBtn = document.getElementById("clearCompletedQueueBtn");
const clearFailedQueueBtn = document.getElementById("clearFailedQueueBtn");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");

// Browse Elements
const browsePagination = document.getElementById("browsePagination");
const browsePrevBtn = document.getElementById("browsePrevBtn");
const browseNextBtn = document.getElementById("browseNextBtn");
const browsePageIndicator = document.getElementById("browsePageIndicator");

// Settings Elements
const browseFolderBtn = document.getElementById("browseFolderBtn");
const settingFolderError = document.getElementById("settingFolderError");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const settingConcurrency = document.getElementById("settingConcurrency");
const settingConcurrencyVal = document.getElementById("settingConcurrencyVal");

// Navigation Tabs
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    
    btn.classList.add("active");
    const target = btn.dataset.tab;
    const targetPane = document.getElementById(target);
    if (targetPane) targetPane.classList.add("active");

    if (target === "tab-browse") {
      fetchBrowseCategory(currentBrowseCategory, currentBrowsePage);
    } else if (target === "tab-queue") {
      fetchQueue();
    } else if (target === "tab-history") {
      fetchHistory();
    } else if (target === "tab-settings") {
      fetchSettings();
    }
  });
});

// Category Chips for Browse Website
document.querySelectorAll(".chip-btn").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip-btn").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    currentBrowseCategory = chip.dataset.category;
    fetchBrowseCategory(currentBrowseCategory, 1);
  });
});

// Real Pagination for Browse Website
async function fetchBrowseCategory(categoryKey, page = 1) {
  currentBrowseCategory = categoryKey;
  currentBrowsePage = page;

  if (browsePrevBtn) browsePrevBtn.disabled = true;
  if (browseNextBtn) browseNextBtn.disabled = true;

  browseGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">Loading category: ${categoryKey} (page ${page})...</div>`;
  
  try {
    const res = await fetch(`/api/browse/pagalnew/${encodeURIComponent(categoryKey)}?page=${page}`);
    if (!res.ok) throw new Error("Could not load category items");
    const data = await res.json();
    
    renderCards(data.items || [], browseGrid);

    if (browsePagination) {
      browsePagination.style.display = "flex";
      currentBrowseTotalPages = data.total_pages;

      const pageText = data.total_pages
        ? `Page ${data.current_page} of ${data.total_pages}`
        : `Page ${data.current_page}`;
      browsePageIndicator.innerText = pageText;

      browsePrevBtn.disabled = !data.has_prev;
      browseNextBtn.disabled = !data.has_next;
    }
  } catch (err) {
    browseGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--status-failed); padding: 3rem;">Error loading category: ${err.message}</div>`;
  }
}

if (browsePrevBtn) {
  browsePrevBtn.addEventListener("click", () => {
    if (currentBrowsePage > 1) {
      fetchBrowseCategory(currentBrowseCategory, currentBrowsePage - 1);
      window.scrollTo({ top: browseGrid.offsetTop - 80, behavior: "smooth" });
    }
  });
}

if (browseNextBtn) {
  browseNextBtn.addEventListener("click", () => {
    fetchBrowseCategory(currentBrowseCategory, currentBrowsePage + 1);
    window.scrollTo({ top: browseGrid.offsetTop - 80, behavior: "smooth" });
  });
}

// Search Execution
async function performSearch() {
  const query = searchInput ? searchInput.value.trim() : "";
  const provider = providerSelect ? providerSelect.value : "";
  
  resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 4rem;">Searching ${provider ? provider.toUpperCase() : 'all sources'}...</div>`;
  if (resultsCount) resultsCount.innerText = "";

  try {
    const url = `/api/search?q=${encodeURIComponent(query)}${provider ? `&provider=${encodeURIComponent(provider)}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Search request failed (${res.status})`);
    const data = await res.json();
    const items = data.results || [];

    if (resultsCount) {
      resultsCount.innerText = `Found ${items.length} ${items.length === 1 ? 'item' : 'items'}`;
    }
    renderCards(items, resultsGrid);
  } catch (err) {
    resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--status-failed); padding: 3rem;">Search failed: ${err.message}</div>`;
  }
}

if (searchBtn) searchBtn.addEventListener("click", performSearch);
if (searchInput) {
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performSearch();
  });
}
if (providerSelect) {
  providerSelect.addEventListener("change", performSearch);
}

// Search Input Clear Button
if (searchClearInputBtn) {
  searchClearInputBtn.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.focus();
  });
}

// Search Clear All Button (Scope strictly limited to transient query/results view)
if (searchClearAllBtn) {
  searchClearAllBtn.addEventListener("click", () => {
    searchInput.value = "";
    resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">Search cleared. Enter a song title, movie, singer, or director above to discover music.</div>`;
    if (resultsCount) resultsCount.innerText = "";
    showToast("Search view cleared.");
  });
}

// Render Music Cards (Albums vs Standalone Songs)
function renderCards(items, targetContainer) {
  if (items.length === 0) {
    targetContainer.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 4rem;">No songs or albums found. Try another search query or category.</div>`;
    return;
  }

  targetContainer.innerHTML = items.map(item => {
    const cover = item.artwork_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop";
    const yearBadge = item.year ? `<span class="card-year-badge">${item.year}</span>` : "";
    
    const isAlbum = item.item_type === "album";
    const typeLabel = isAlbum ? `Album • ${item.track_count || 0} Tracks` : `Single Song`;
    const typeClass = isAlbum ? `card-type-album` : `card-type-song`;
    const providerBadgeClass = item.provider === "pagalnew" ? "provider-pagalnew" : "provider-mock";
    const providerBadge = `<span class="provider-mini-badge ${providerBadgeClass}">${item.provider}</span>`;

    const artistsDisplay = (item.artists && item.artists.length) ? item.artists.join(", ") : "Various Artists";
    const safeTitle = (item.title || "Untitled").replace(/'/g, "&#39;");
    const safeAlbumTitle = (item.album_title || "").replace(/'/g, "&#39;");

    return `
      <div class="music-card" onclick="openItemDetails('${item.provider}', '${item.id}', '${item.item_type}', '${item.album_id || ''}', '${safeAlbumTitle}')">
        <div class="card-cover-container">
          <img class="card-cover" src="${cover}" alt="${safeTitle}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop'" />
          <span class="card-type-overlay ${typeClass}">${typeLabel}</span>
        </div>
        <div class="card-body">
          <div class="card-title" title="${safeTitle}">${safeTitle}</div>
          <div class="card-artists" title="${artistsDisplay}">${artistsDisplay}</div>
          <div class="card-meta">
            ${providerBadge}
            ${yearBadge}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Router: Open Modal according to item type (Album vs Standalone Track)
async function openItemDetails(provider, id, itemType, albumId, albumTitleHint) {
  if (itemType === "track") {
    await openTrackModal(provider, id, albumId, albumTitleHint);
  } else {
    await openAlbumModal(provider, id);
  }
}

// Open Album Inspector Modal
async function openAlbumModal(provider, albumId) {
  try {
    const res = await fetch(`/api/albums/${provider}/${encodeURIComponent(albumId)}`);
    if (!res.ok) throw new Error("Could not load album metadata from provider");
    
    currentAlbum = await res.json();
    displayAlbumModal(currentAlbum);
  } catch (err) {
    alert("Failed to load album details: " + err.message);
  }
}

function displayAlbumModal(album) {
  document.getElementById("modalAlbumTitle").innerText = album.title;
  document.getElementById("modalArtists").innerText = `Artists: ${album.artists.join(", ") || "N/A"}`;
  document.getElementById("modalComposer").innerText = album.composer ? `Composer: ${album.composer}` : "";
  document.getElementById("modalStarcast").innerText = album.starcast && album.starcast.length ? `Starcast: ${album.starcast.join(", ")}` : "";
  document.getElementById("modalYear").innerText = album.year ? `Release Year: ${album.year}` : "";
  document.getElementById("modalCover").src = album.artwork_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop";

  const tracklistTbody = document.getElementById("tracklistTbody");
  tracklistTbody.innerHTML = album.tracks.map((track, idx) => {
    const qualities = track.qualities.map(q => `<span style="font-size:0.75rem; background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:4px; margin-right:4px;">${q.bitrate_kbps}k</span>`).join("");
    return `
      <tr>
        <td style="width: 38px;"><input type="checkbox" class="track-select-box" value="${track.id}" checked /></td>
        <td style="width: 38px; color: var(--text-muted);">${idx + 1}</td>
        <td>
          <div style="font-weight: 600; color: var(--text-pure);">${track.title}</div>
          <div style="font-size: 0.8rem; color: var(--text-secondary);">${track.artists.join(", ")}</div>
        </td>
        <td>${qualities || '<span style="color:var(--text-muted); font-size:0.8rem;">Auto 320k</span>'}</td>
        <td style="text-align: right;">
          <button class="btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" onclick="downloadSingleTrackFromAlbum('${track.id}')">Download</button>
        </td>
      </tr>
    `;
  }).join("");

  updateBatchCount();
  albumModal.classList.add("active");

  document.querySelectorAll(".track-select-box").forEach(cb => {
    cb.addEventListener("change", updateBatchCount);
  });
}

function updateBatchCount() {
  const selected = document.querySelectorAll(".track-select-box:checked").length;
  document.getElementById("batchDownloadBtn").innerText = `Download Selected (${selected})`;
}

const selectAllCb = document.getElementById("selectAllCheckbox");
if (selectAllCb) {
  selectAllCb.addEventListener("change", (e) => {
    document.querySelectorAll(".track-select-box").forEach(cb => cb.checked = e.target.checked);
    updateBatchCount();
  });
}

if (modalClose) modalClose.addEventListener("click", () => albumModal.classList.remove("active"));
if (albumModal) {
  albumModal.addEventListener("click", (e) => {
    if (e.target === albumModal) albumModal.classList.remove("active");
  });
}

// Single Track Download from inside Album Modal
async function downloadSingleTrackFromAlbum(trackId) {
  if (!currentAlbum) return;
  const strict320k = document.getElementById("strict320kModal").checked;
  const preferredBitrate = parseInt(document.getElementById("qualitySelectModal").value, 10);

  try {
    const res = await fetch("/api/downloads/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: currentAlbum.provider,
        album_id: currentAlbum.id,
        track_id: trackId,
        bitrate: preferredBitrate,
        strict_320k: strict320k
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Download failed");
    }
    showToast("Track enqueued for download!");
    fetchQueue();
  } catch (err) {
    alert("Download error: " + err.message);
  }
}

// Batch Download from Album Modal
const batchDownloadBtn = document.getElementById("batchDownloadBtn");
if (batchDownloadBtn) {
  batchDownloadBtn.addEventListener("click", async () => {
    if (!currentAlbum) return;
    const selectedTrackIds = Array.from(document.querySelectorAll(".track-select-box:checked")).map(cb => cb.value);
    if (selectedTrackIds.length === 0) {
      alert("Please select at least one track to download.");
      return;
    }

    const strict320k = document.getElementById("strict320kModal").checked;
    const preferredBitrate = parseInt(document.getElementById("qualitySelectModal").value, 10);

    try {
      const res = await fetch("/api/downloads/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: currentAlbum.provider,
          album_id: currentAlbum.id,
          track_ids: selectedTrackIds,
          preferred_bitrate: preferredBitrate,
          strict_320k: strict320k
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Batch download failed");
      }
      albumModal.classList.remove("active");
      showToast(`Enqueued ${selectedTrackIds.length} tracks for download!`);
      
      const queueTabBtn = document.querySelector('[data-tab="tab-queue"]');
      if (queueTabBtn) queueTabBtn.click();
    } catch (err) {
      alert("Batch download error: " + err.message);
    }
  });
}

// Open Standalone Song Inspector Modal
async function openTrackModal(provider, trackId, albumId, albumTitleHint) {
  try {
    const res = await fetch(`/api/tracks/${provider}/${encodeURIComponent(trackId)}`);
    if (!res.ok) throw new Error("Could not load track metadata from provider");
    
    currentTrack = await res.json();
    if (!currentTrack.album_title && albumTitleHint) {
      currentTrack.album_title = albumTitleHint;
    }
    displaySongModal(currentTrack);
  } catch (err) {
    alert("Failed to load track details: " + err.message);
  }
}

function displaySongModal(track) {
  document.getElementById("songModalTitle").innerText = track.title;
  document.getElementById("songModalArtists").innerText = `Artists: ${track.artists.join(", ") || "N/A"}`;
  
  const albumInfo = track.album_title || "Single / Non-Album Release";
  document.getElementById("songModalAlbum").innerText = `Release / Album: ${albumInfo}`;
  document.getElementById("songModalComposer").innerText = track.composer ? `Composer: ${track.composer}` : "";
  
  const coverUrl = track.artwork_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop";
  document.getElementById("songModalCover").src = coverUrl;

  // Build Bitrate selection pills
  const qualitiesCluster = document.getElementById("songQualitiesList");
  qualitiesCluster.innerHTML = "";

  const availableBitrates = (track.qualities && track.qualities.length)
    ? track.qualities.map(q => q.bitrate_kbps)
    : [320, 128];

  // Set default preferred bitrate to 320 if available, else first
  currentSongBitrate = availableBitrates.includes(320) ? 320 : availableBitrates[0];

  availableBitrates.forEach(bitrate => {
    const pill = document.createElement("button");
    pill.className = `quality-pill-btn ${bitrate === currentSongBitrate ? 'active' : ''}`;
    pill.innerText = `${bitrate} kbps ${bitrate === 320 ? '(HD)' : ''}`;
    pill.addEventListener("click", () => {
      document.querySelectorAll(".quality-pill-btn").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentSongBitrate = bitrate;
    });
    qualitiesCluster.appendChild(pill);
  });

  songModal.classList.add("active");
}

if (songModalClose) songModalClose.addEventListener("click", () => songModal.classList.remove("active"));
if (songCancelBtn) songCancelBtn.addEventListener("click", () => songModal.classList.remove("active"));
if (songModal) {
  songModal.addEventListener("click", (e) => {
    if (e.target === songModal) songModal.classList.remove("active");
  });
}

// Download Standalone Song
if (songDownloadBtn) {
  songDownloadBtn.addEventListener("click", async () => {
    if (!currentTrack) return;
    const strict320k = document.getElementById("songStrict320k") ? document.getElementById("songStrict320k").checked : false;

    try {
      songDownloadBtn.disabled = true;
      songDownloadBtn.innerHTML = "Enqueuing...";

      const res = await fetch("/api/downloads/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: currentTrack.provider,
          album_id: currentTrack.album_id && currentTrack.album_id !== "unknown" ? currentTrack.album_id : null,
          album_title: currentTrack.album_title || null,
          track_id: currentTrack.id,
          bitrate: currentSongBitrate,
          strict_320k: strict320k
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start download");
      }

      songModal.classList.remove("active");
      showToast(`Enqueued "${currentTrack.title}" for download!`);
      fetchQueue();

      const queueTabBtn = document.querySelector('[data-tab="tab-queue"]');
      if (queueTabBtn) queueTabBtn.click();
    } catch (err) {
      alert("Download Error: " + err.message);
    } finally {
      if (songDownloadBtn) {
        songDownloadBtn.disabled = false;
        songDownloadBtn.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          Download Track
        `;
      }
    }
  });
}

// Keyboard Accessibility: Close Modals on Escape
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (albumModal && albumModal.classList.contains("active")) {
      albumModal.classList.remove("active");
    }
    if (songModal && songModal.classList.contains("active")) {
      songModal.classList.remove("active");
    }
  }
});

// Download Queue Fetching & Real-time Progress
async function fetchQueue() {
  try {
    const res = await fetch("/api/downloads/queue");
    if (!res.ok) return;
    const data = await res.json();

    const statActive = document.getElementById("statActive");
    const statQueued = document.getElementById("statQueued");
    const statPaused = document.getElementById("statPaused");
    const statCompleted = document.getElementById("statCompleted");
    const statFailed = document.getElementById("statFailed");

    if (statActive) statActive.innerText = data.active_count;
    if (statQueued) statQueued.innerText = data.queued_count;
    if (statPaused) statPaused.innerText = data.paused_count || 0;
    if (statCompleted) statCompleted.innerText = data.completed_count;
    if (statFailed) statFailed.innerText = data.failed_count;

    const totalInFlight = data.active_count + data.queued_count;
    if (queueBadge) {
      queueBadge.innerText = totalInFlight;
      queueBadge.style.display = totalInFlight > 0 ? "inline-flex" : "none";
    }

    // Global Queue Toolbar state
    const hasActiveOrQueued = (data.active_count + data.queued_count) > 0;
    const hasPaused = (data.paused_count || 0) > 0;
    const hasAnyInQueue = hasActiveOrQueued || hasPaused;

    if (pauseAllBtn) pauseAllBtn.disabled = !hasActiveOrQueued;
    if (resumeAllBtn) resumeAllBtn.disabled = !hasPaused;
    if (cancelAllBtn) cancelAllBtn.disabled = !hasAnyInQueue;

    renderQueueTasks(data.tasks);
  } catch (err) {
    console.error("Queue fetch error:", err);
  }
}

function renderQueueTasks(tasks) {
  if (!queueTaskList) return;
  if (tasks.length === 0) {
    queueTaskList.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 4rem;">The download queue is currently empty.</div>`;
    return;
  }

  queueTaskList.innerHTML = tasks.map(t => {
    const progress = t.total_bytes > 0 ? ((t.downloaded_bytes / t.total_bytes) * 100).toFixed(1) : 0;
    const mbDownloaded = (t.downloaded_bytes / (1024 * 1024)).toFixed(2);
    const mbTotal = (t.total_bytes / (1024 * 1024)).toFixed(2);
    const speedKb = (t.speed_bps / 1024).toFixed(0);
    const etaStr = t.eta_seconds != null ? `${t.eta_seconds.toFixed(0)}s left` : "";

    let actionButtons = "";
    if (["QUEUED", "DOWNLOADING"].includes(t.status)) {
      actionButtons += `<button class="btn-secondary" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="pauseTask('${t.task_id}')">Pause</button>`;
      actionButtons += `<button class="btn-secondary btn-danger" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="cancelTask('${t.task_id}')">Cancel</button>`;
    } else if (t.status === "PAUSED") {
      actionButtons += `<button class="btn-primary" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="resumeTask('${t.task_id}')">Resume</button>`;
      actionButtons += `<button class="btn-secondary btn-danger" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="cancelTask('${t.task_id}')">Cancel</button>`;
    } else if (["FAILED", "CANCELLED"].includes(t.status)) {
      actionButtons += `<button class="btn-secondary" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="retryTask('${t.task_id}')">Retry</button>`;
    }

    const errorDetails = t.error_message ? `<div style="font-size:0.8rem; color:#F87171; margin-top:6px; background: rgba(248,113,113,0.1); padding: 4px 8px; border-radius: 4px;">${t.error_message}</div>` : "";

    return `
      <div class="task-card">
        <div class="task-header">
          <div>
            <div class="task-title">${t.title}</div>
            <div class="task-sub">${t.artist} • ${t.album_title || 'Single'}</div>
          </div>
          <div class="task-actions">
            <span class="status-pill status-${t.status}">${t.status}</span>
            ${actionButtons}
          </div>
        </div>
        <div class="progress-container">
          <div class="progress-bar" style="width: ${progress}%;"></div>
        </div>
        <div class="task-details">
          <span>${progress}% (${mbDownloaded} MB / ${mbTotal > 0 ? mbTotal : '—'} MB)</span>
          <span>${t.status === "DOWNLOADING" ? `${speedKb} KB/s • ${etaStr}` : `${t.selected_bitrate} kbps`}</span>
        </div>
        ${errorDetails}
      </div>
    `;
  }).join("");
}

async function cancelTask(taskId) {
  if (!confirm("Are you sure you want to cancel this download?")) return;
  await fetch(`/api/downloads/${taskId}/cancel`, { method: "POST" });
  fetchQueue();
}

async function pauseTask(taskId) {
  await fetch(`/api/downloads/${taskId}/pause`, { method: "POST" });
  fetchQueue();
}

async function resumeTask(taskId) {
  await fetch(`/api/downloads/${taskId}/resume`, { method: "POST" });
  fetchQueue();
}

async function retryTask(taskId) {
  await fetch(`/api/downloads/${taskId}/retry`, { method: "POST" });
  fetchQueue();
}

// Global Queue Controls
if (pauseAllBtn) {
  pauseAllBtn.addEventListener("click", async () => {
    const res = await fetch("/api/downloads/queue/pause-all", { method: "POST" });
    const data = await res.json();
    showToast(data.message || "Paused active and queued downloads");
    fetchQueue();
  });
}

if (resumeAllBtn) {
  resumeAllBtn.addEventListener("click", async () => {
    const res = await fetch("/api/downloads/queue/resume-all", { method: "POST" });
    const data = await res.json();
    showToast(data.message || "Resumed paused downloads");
    fetchQueue();
  });
}

if (cancelAllBtn) {
  cancelAllBtn.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to cancel all active, queued, and paused downloads?\nCompleted files and history records will NOT be deleted.")) return;
    const res = await fetch("/api/downloads/queue/cancel-all", { method: "POST" });
    const data = await res.json();
    showToast(data.message || "Cancelled all in-flight downloads");
    fetchQueue();
  });
}

// Queue Maintenance Controls
if (clearPendingBtn) {
  clearPendingBtn.addEventListener("click", async () => {
    if (!confirm("Remove all pending/queued tasks? Active and completed downloads will not be touched.")) return;
    const res = await fetch("/api/downloads/queue/clear-pending", { method: "POST" });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} pending tasks`);
    fetchQueue();
  });
}

if (clearCompletedQueueBtn) {
  clearCompletedQueueBtn.addEventListener("click", async () => {
    if (!confirm("Clear completed tasks from the queue view? Your downloaded files on disk remain safe.")) return;
    const res = await fetch("/api/downloads/queue/clear-completed", { method: "POST" });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} completed tasks from view`);
    fetchQueue();
  });
}

if (clearFailedQueueBtn) {
  clearFailedQueueBtn.addEventListener("click", async () => {
    if (!confirm("Clear failed and cancelled tasks from the queue view?")) return;
    const res = await fetch("/api/downloads/queue/clear-failed", { method: "POST" });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} failed tasks`);
    fetchQueue();
  });
}

// History Controls
async function fetchHistory() {
  const tbody = document.getElementById("historyTbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 3rem;">Loading download history...</td></tr>`;
  try {
    const res = await fetch("/api/downloads/history");
    const items = await res.json();
    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 3rem;">No completed downloads yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map(h => `
      <tr>
        <td><b>${h.title}</b></td>
        <td>${h.artist}</td>
        <td>${h.album_title || 'Single'}</td>
        <td><span style="font-size:0.78rem; background:rgba(212,175,135,0.15); color:var(--accent-champagne-light); padding:2px 6px; border-radius:4px;">${h.bitrate_kbps} kbps</span></td>
        <td style="font-size:0.8rem; color:var(--text-secondary);">${h.file_path}</td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--status-failed);">Failed to load history: ${err.message}</td></tr>`;
  }
}

if (clearHistoryBtn) {
  clearHistoryBtn.addEventListener("click", async () => {
    if (!confirm("Clear download history database records? Note: Downloaded MP3 files on disk will NOT be deleted.")) return;
    const res = await fetch("/api/downloads/history/clear", { method: "POST" });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} history records`);
    fetchHistory();
  });
}

// Settings & Native Folder Picker
async function fetchSettings() {
  try {
    const res = await fetch("/api/settings");
    const cfg = await res.json();
    const settingDownloadDir = document.getElementById("settingDownloadDir");
    const settingPagalnewUrl = document.getElementById("settingPagalnewUrl");
    const settingStrict320k = document.getElementById("settingStrict320k");

    if (settingDownloadDir) settingDownloadDir.value = cfg.download_dir;
    if (settingPagalnewUrl) settingPagalnewUrl.value = cfg.pagalnew_base_url || "https://pagalnew.com";
    if (settingConcurrency) settingConcurrency.value = cfg.max_concurrent_downloads;
    if (settingConcurrencyVal) settingConcurrencyVal.innerText = cfg.max_concurrent_downloads;
    if (settingStrict320k) settingStrict320k.checked = cfg.strict_320kbps;

    // Diagnostics
    const diagRes = await fetch("/api/diagnostics/providers");
    const diagData = await diagRes.json();
    const diagTbody = document.getElementById("diagTbody");
    if (diagTbody) {
      diagTbody.innerHTML = diagData.map(d => `
        <tr>
          <td><b>${d.provider_name}</b> <span style="color:var(--text-muted); font-size:0.75rem;">(${d.provider_id})</span></td>
          <td><span style="color:${d.healthy ? 'var(--status-completed)' : 'var(--status-failed)'}; font-weight:600;">● ${d.healthy ? 'Operational' : 'Offline'}</span></td>
          <td>${d.latency_ms != null ? `${d.latency_ms} ms` : 'N/A'}</td>
          <td style="font-size:0.82rem; color:var(--text-secondary);">${d.message}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Settings error:", err);
  }
}

if (browseFolderBtn) {
  browseFolderBtn.addEventListener("click", async () => {
    browseFolderBtn.disabled = true;
    browseFolderBtn.innerText = "Opening Folder Dialog...";
    if (settingFolderError) settingFolderError.style.display = "none";

    try {
      const currentVal = document.getElementById("settingDownloadDir").value;
      const res = await fetch("/api/settings/browse-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_path: currentVal })
      });
      const data = await res.json();

      if (data.selected_path) {
        document.getElementById("settingDownloadDir").value = data.selected_path;
        showToast("Folder selected: " + data.selected_path);
      } else if (data.cancelled) {
        // User cancelled dialog
      } else if (!data.available || data.error) {
        if (settingFolderError) {
          settingFolderError.innerText = data.error || "Native folder picker is unavailable. You can enter or paste the path directly.";
          settingFolderError.style.display = "block";
        }
      }
    } catch (err) {
      if (settingFolderError) {
        settingFolderError.innerText = "Error launching folder picker: " + err.message;
        settingFolderError.style.display = "block";
      }
    } finally {
      browseFolderBtn.disabled = false;
      browseFolderBtn.innerText = "📁 Browse Folder";
    }
  });
}

if (saveSettingsBtn) {
  saveSettingsBtn.addEventListener("click", async () => {
    const downloadDir = document.getElementById("settingDownloadDir").value;
    const pagalnewUrl = document.getElementById("settingPagalnewUrl").value;
    const maxConcurrent = parseInt(document.getElementById("settingConcurrency").value, 10);
    const strict320k = document.getElementById("settingStrict320k").checked;

    if (settingFolderError) settingFolderError.style.display = "none";

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          download_dir: downloadDir,
          pagalnew_base_url: pagalnewUrl,
          max_concurrent_downloads: maxConcurrent,
          strict_320kbps: strict320k
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to save settings");
      }
      showToast("Settings updated successfully!");
    } catch (err) {
      if (settingFolderError) {
        settingFolderError.innerText = err.message;
        settingFolderError.style.display = "block";
      } else {
        alert("Error saving settings: " + err.message);
      }
    }
  });
}

if (settingConcurrency) {
  settingConcurrency.addEventListener("input", (e) => {
    if (settingConcurrencyVal) settingConcurrencyVal.innerText = e.target.value;
  });
}

// Toast notification helper
function showToast(msg) {
  const existing = document.querySelectorAll(".musichub-toast");
  existing.forEach(t => t.remove());

  const toast = document.createElement("div");
  toast.className = "musichub-toast";
  toast.innerText = msg;
  toast.style.cssText = "position: fixed; bottom: 24px; right: 24px; background: rgba(30, 26, 23, 0.95); backdrop-filter: blur(12px); color: var(--text-pure); border: 1px solid var(--border-glass-active); padding: 12px 22px; border-radius: 10px; font-weight: 600; font-size: 0.9rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5), 0 0 15px rgba(212,175,135,0.25); z-index: 9999; transition: all 0.25s ease; transform: translateY(0);";
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, 2800);
}

// Initial bootstrap
window.addEventListener("DOMContentLoaded", () => {
  performSearch();
  fetchQueue();
  queuePollInterval = setInterval(fetchQueue, 1500);
});
