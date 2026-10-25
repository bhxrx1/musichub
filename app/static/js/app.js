// MusicHub Web Application Client - Milestone 3
let currentAlbum = null;
let queuePollInterval = null;
let currentBrowseCategory = "bollywood-2026";
let currentBrowsePage = 1;
let currentBrowseTotalPages = null;

// DOM Elements
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const resultsGrid = document.getElementById("resultsGrid");
const browseGrid = document.getElementById("browseGrid");
const albumModal = document.getElementById("albumModal");
const modalClose = document.getElementById("modalClose");
const queueTaskList = document.getElementById("queueTaskList");
const queueBadge = document.getElementById("queueBadge");

const browsePagination = document.getElementById("browsePagination");
const browsePrevBtn = document.getElementById("browsePrevBtn");
const browseNextBtn = document.getElementById("browseNextBtn");
const browsePageIndicator = document.getElementById("browsePageIndicator");

const pauseAllBtn = document.getElementById("pauseAllBtn");
const resumeAllBtn = document.getElementById("resumeAllBtn");
const cancelAllBtn = document.getElementById("cancelAllBtn");
const clearPendingBtn = document.getElementById("clearPendingBtn");
const clearCompletedQueueBtn = document.getElementById("clearCompletedQueueBtn");
const clearFailedQueueBtn = document.getElementById("clearFailedQueueBtn");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");

const browseFolderBtn = document.getElementById("browseFolderBtn");
const settingFolderError = document.getElementById("settingFolderError");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");

// Navigation Tabs
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    
    btn.classList.add("active");
    const target = btn.dataset.tab;
    document.getElementById(target).classList.add("active");

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
    fetchBrowseCategory(currentBrowseCategory, 1); // Reset to page 1 on category switch
  });
});

// Real Pagination for Browse Website
async function fetchBrowseCategory(categoryKey, page = 1) {
  currentBrowseCategory = categoryKey;
  currentBrowsePage = page;

  if (browsePrevBtn) browsePrevBtn.disabled = true;
  if (browseNextBtn) browseNextBtn.disabled = true;

  browseGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">Loading ${categoryKey} (page ${page})...</div>`;
  
  try {
    const res = await fetch(`/api/browse/pagalnew/${encodeURIComponent(categoryKey)}?page=${page}`);
    if (!res.ok) throw new Error("Could not load category");
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
    browseGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--danger); padding: 2rem;">Error browsing category: ${err.message}</div>`;
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
  const query = searchInput.value.trim();
  const provider = document.getElementById("providerSelect") ? document.getElementById("providerSelect").value : "";
  resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">Searching ${provider ? provider.toUpperCase() : 'all sources'}...</div>`;
  
  try {
    const url = `/api/search?q=${encodeURIComponent(query)}${provider ? `&provider=${encodeURIComponent(provider)}` : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    renderCards(data.results || [], resultsGrid);
  } catch (err) {
    resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--danger); padding: 2rem;">Search failed: ${err.message}</div>`;
  }
}

searchBtn.addEventListener("click", performSearch);
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") performSearch();
});
if (document.getElementById("providerSelect")) {
  document.getElementById("providerSelect").addEventListener("change", performSearch);
}

function renderCards(items, targetContainer) {
  if (items.length === 0) {
    targetContainer.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">No songs or albums found on this page.</div>`;
    return;
  }

  targetContainer.innerHTML = items.map(item => {
    const cover = item.artwork_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop";
    const yearBadge = item.year ? `<span class="tag-year">${item.year}</span>` : "";
    const typeBadge = item.item_type === "album" ? `[Album - ${item.track_count || 0} Tracks]` : `[Single Song]`;
    const providerBadge = item.provider === "pagalnew" 
      ? `<span style="background:#0284c7; color:white; border-radius:4px; padding:2px 6px; font-size:0.75rem; font-weight:600;">PagalNew</span>`
      : `<span style="background:#64748b; color:white; border-radius:4px; padding:2px 6px; font-size:0.75rem; font-weight:600;">Mock</span>`;

    return `
      <div class="music-card" onclick="openItemDetails('${item.provider}', '${item.id}', '${item.item_type}', '${item.album_id || item.id}')">
        <img class="card-cover" src="${cover}" alt="${item.title}" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop'" />
        <div class="card-body">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.25rem;">
            <div class="card-title">${item.title}</div>
            ${providerBadge}
          </div>
          <div class="card-artists">${item.artists.join(", ") || "Various Artists"}</div>
          <div class="card-meta">
            <span>${typeBadge}</span>
            ${yearBadge}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Album Details & Inspector Modal
async function openItemDetails(provider, id, itemType, albumId) {
  try {
    const targetAlbumId = itemType === "album" ? id : albumId;
    const res = await fetch(`/api/albums/${provider}/${targetAlbumId}`);
    if (!res.ok) throw new Error("Could not load complete album metadata");
    
    currentAlbum = await res.json();
    displayAlbumModal(currentAlbum);
  } catch (err) {
    alert("Failed to load album: " + err.message);
  }
}

function displayAlbumModal(album) {
  document.getElementById("modalTitle").innerText = album.title;
  document.getElementById("modalArtists").innerText = `Artists: ${album.artists.join(", ") || "N/A"}`;
  document.getElementById("modalComposer").innerText = `Composer: ${album.composer || "N/A"}`;
  document.getElementById("modalStarcast").innerText = album.starcast && album.starcast.length ? `Starcast: ${album.starcast.join(", ")}` : "";
  document.getElementById("modalYear").innerText = `Year: ${album.year || "N/A"}`;
  document.getElementById("modalCover").src = album.artwork_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop";

  const tracklistTbody = document.getElementById("tracklistTbody");
  tracklistTbody.innerHTML = album.tracks.map((track, idx) => {
    const qualities = track.qualities.map(q => `<span style="font-size:0.75rem; background:var(--bg-tertiary); padding:2px 5px; border-radius:3px; margin-right:3px;">${q.bitrate_kbps}k</span>`).join("");
    return `
      <tr>
        <td style="width: 30px;"><input type="checkbox" class="track-select-box" value="${track.id}" checked /></td>
        <td>${idx + 1}</td>
        <td><b>${track.title}</b><div style="font-size:0.8rem; color:var(--text-muted);">${track.artists.join(", ")}</div></td>
        <td>${qualities || '<span style="color:var(--text-muted); font-size:0.8rem;">Auto 320k</span>'}</td>
        <td>
          <button class="btn-secondary" style="padding: 0.25rem 0.5rem;" onclick="downloadSingleTrack('${track.id}')">Download</button>
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

document.getElementById("selectAllCheckbox").addEventListener("change", (e) => {
  document.querySelectorAll(".track-select-box").forEach(cb => cb.checked = e.target.checked);
  updateBatchCount();
});

modalClose.addEventListener("click", () => albumModal.classList.remove("active"));
albumModal.addEventListener("click", (e) => {
  if (e.target === albumModal) albumModal.classList.remove("active");
});

// Single Track Download
async function downloadSingleTrack(trackId) {
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
    alert("Error: " + err.message);
  }
}

// Batch Download
document.getElementById("batchDownloadBtn").addEventListener("click", async () => {
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
    
    document.querySelector('[data-tab="tab-queue"]').click();
  } catch (err) {
    alert("Batch download error: " + err.message);
  }
});

// Queue Fetching & Real-time Progress
async function fetchQueue() {
  try {
    const res = await fetch("/api/downloads/queue");
    const data = await res.json();

    document.getElementById("statActive").innerText = data.active_count;
    document.getElementById("statQueued").innerText = data.queued_count;
    document.getElementById("statPaused").innerText = data.paused_count || 0;
    document.getElementById("statCompleted").innerText = data.completed_count;
    document.getElementById("statFailed").innerText = data.failed_count;

    const totalInFlight = data.active_count + data.queued_count;
    queueBadge.innerText = totalInFlight;
    queueBadge.style.display = totalInFlight > 0 ? "inline-block" : "none";

    // Update global buttons disabled state
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
  if (tasks.length === 0) {
    queueTaskList.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem;">Download queue is empty.</div>`;
    return;
  }

  queueTaskList.innerHTML = tasks.map(t => {
    const progress = t.total_bytes > 0 ? ((t.downloaded_bytes / t.total_bytes) * 100).toFixed(1) : 0;
    const mbDownloaded = (t.downloaded_bytes / (1024 * 1024)).toFixed(2);
    const mbTotal = (t.total_bytes / (1024 * 1024)).toFixed(2);
    const speedKb = (t.speed_bps / 1024).toFixed(0);
    const etaStr = t.eta_seconds != null ? `${t.eta_seconds.toFixed(0)}s remaining` : "";

    let actionButtons = "";
    if (["QUEUED", "DOWNLOADING"].includes(t.status)) {
      actionButtons += `<button class="btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="pauseTask('${t.task_id}')">Pause</button>`;
      actionButtons += `<button class="btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem; color: #f87171;" onclick="cancelTask('${t.task_id}')">Cancel</button>`;
    } else if (t.status === "PAUSED") {
      actionButtons += `<button class="btn-primary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="resumeTask('${t.task_id}')">Resume</button>`;
      actionButtons += `<button class="btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem; color: #f87171;" onclick="cancelTask('${t.task_id}')">Cancel</button>`;
    } else if (["FAILED", "CANCELLED"].includes(t.status)) {
      actionButtons += `<button class="btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="retryTask('${t.task_id}')">Retry</button>`;
    }

    const errorDetails = t.error_message ? `<div style="font-size:0.8rem; color:#f87171; margin-top:4px;">${t.error_message}</div>` : "";

    return `
      <div class="task-card">
        <div class="task-header">
          <div>
            <span class="task-title">${t.title}</span>
            <span style="font-size: 0.85rem; color: var(--text-muted); margin-left: 0.5rem;">(${t.artist} — ${t.album_title})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.4rem;">
            <span class="status-pill status-${t.status}">${t.status}</span>
            ${actionButtons}
          </div>
        </div>
        <div class="progress-container">
          <div class="progress-bar" style="width: ${progress}%;"></div>
        </div>
        <div class="task-details">
          <span>${progress}% (${mbDownloaded} MB / ${mbTotal > 0 ? mbTotal : "?"} MB)</span>
          <span>${t.status === "DOWNLOADING" ? `${speedKb} KB/s — ${etaStr}` : `${t.selected_bitrate} kbps`}</span>
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
    showToast(data.message || "Paused active/queued downloads");
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
    if (!confirm("Are you sure you want to cancel all active, queued, and paused downloads?\nCompleted files and history will NOT be deleted.")) return;
    const res = await fetch("/api/downloads/queue/cancel-all", { method: "POST" });
    const data = await res.json();
    showToast(data.message || "Cancelled all active/queued downloads");
    fetchQueue();
  });
}

// Queue Maintenance Controls
if (clearPendingBtn) {
  clearPendingBtn.addEventListener("click", async () => {
    if (!confirm("Remove all pending/queued tasks? Active and completed downloads will not be affected.")) return;
    const res = await fetch("/api/downloads/queue/clear-pending", { method: "POST" });
    const data = await res.json();
    showToast(`Cleared ${data.cleared_count} pending tasks`);
    fetchQueue();
  });
}

if (clearCompletedQueueBtn) {
  clearCompletedQueueBtn.addEventListener("click", async () => {
    if (!confirm("Clear completed tasks from the queue view? Your files on disk remain safe.")) return;
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
  tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading history...</td></tr>`;
  try {
    const res = await fetch("/api/downloads/history");
    const items = await res.json();
    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No completed downloads yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map(h => `
      <tr>
        <td><b>${h.title}</b></td>
        <td>${h.artist}</td>
        <td>${h.album_title}</td>
        <td>${h.bitrate_kbps} kbps</td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${h.file_path}</td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger);">Failed to load history: ${err.message}</td></tr>`;
  }
}

if (clearHistoryBtn) {
  clearHistoryBtn.addEventListener("click", async () => {
    if (!confirm("Clear download history records? Note: Downloaded files on disk will NOT be deleted.")) return;
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
    document.getElementById("settingDownloadDir").value = cfg.download_dir;
    document.getElementById("settingPagalnewUrl").value = cfg.pagalnew_base_url || "https://pagalnew.com";
    document.getElementById("settingConcurrency").value = cfg.max_concurrent_downloads;
    document.getElementById("settingConcurrencyVal").innerText = cfg.max_concurrent_downloads;
    document.getElementById("settingStrict320k").checked = cfg.strict_320kbps;

    // Diagnostics
    const diagRes = await fetch("/api/diagnostics/providers");
    const diagData = await diagRes.json();
    const diagTbody = document.getElementById("diagTbody");
    diagTbody.innerHTML = diagData.map(d => `
      <tr>
        <td><b>${d.provider_name}</b> (${d.provider_id})</td>
        <td><span style="color:${d.healthy ? 'var(--success)' : 'var(--danger)'};">● ${d.healthy ? 'Healthy' : 'Offline'}</span></td>
        <td>${d.latency_ms != null ? `${d.latency_ms} ms` : 'N/A'}</td>
        <td style="font-size:0.85rem; color:var(--text-muted);">${d.message}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Settings error:", err);
  }
}

if (browseFolderBtn) {
  browseFolderBtn.addEventListener("click", async () => {
    browseFolderBtn.disabled = true;
    browseFolderBtn.innerText = "Opening Picker...";
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
        // User closed or cancelled dialog
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

document.getElementById("settingConcurrency").addEventListener("input", (e) => {
  document.getElementById("settingConcurrencyVal").innerText = e.target.value;
});

// Toast notification helper
function showToast(msg) {
  const toast = document.createElement("div");
  toast.innerText = msg;
  toast.style.cssText = "position: fixed; bottom: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 8px; font-weight: 600; box-shadow: 0 4px 6px rgba(0,0,0,0.3); z-index: 9999; transition: opacity 0.3s;";
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// Initial bootstrap
window.addEventListener("DOMContentLoaded", () => {
  performSearch();
  fetchQueue();
  queuePollInterval = setInterval(fetchQueue, 1500);
});
