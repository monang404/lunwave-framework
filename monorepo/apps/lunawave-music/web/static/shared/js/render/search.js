import { on } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml, formatTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";
import { wsSend } from "../ws.js";

export function buildSrThumbHtml(track) {
    return `<img class="lazy-cover" data-vid="${escapeHtml(track.video_id || '')}" data-title="${escapeHtml(track.title || '')}" data-artist="${escapeHtml(track.artist || '')}" data-thumb="${escapeHtml(track.thumbnail || '')}" src="" alt=""><div class="thumb-eq-overlay"><div class="eq-anim-icon"><span></span><span></span><span></span></div></div>`;
}

export function renderSearchResults(results) {
    store.search_results = results || [];
    dom.searchResults.innerHTML = "";
    if (!results || results.length === 0) {
        dom.searchMsg.textContent = "Tidak ditemukan hasil.";
        dom.searchMsg.style.display = "block";
        dom.searchResults.style.display = "none";
        return;
    }

    dom.searchMsg.style.display = "none";
    dom.searchResults.style.display = "flex";

    results.forEach((track) => {
        const item = document.createElement("div");
        item.className = "sr-item";
        item.dataset.videoId = track.video_id;
        item.dataset.searchTrackStr = JSON.stringify(track);

        const thumb = document.createElement("div");
        thumb.className = "sr-thumb";
        thumb.innerHTML = buildSrThumbHtml(track);

        const info = document.createElement("div");
        info.className = "sr-info";

        const title = document.createElement("div");
        title.className = "sr-title";
        title.textContent = typeof cleanTrackTitle === "function" ? cleanTrackTitle(track.title) : track.title;

        const meta = document.createElement("div");
        meta.className = "sr-meta";
        let artistName = track.artist || "";
        if (artistName.length > 25) {
            artistName = artistName.substring(0, 22) + "...";
        }
        meta.textContent = artistName;

        info.appendChild(title);
        info.appendChild(meta);

        const duration = document.createElement("div");
        duration.className = "sr-duration";
        duration.textContent = formatTime(track.duration);

        // 3-dots context menu button
        const moreBtn = document.createElement("button");
        moreBtn.className = "sr-more-btn";
        moreBtn.innerHTML = '<i class="ti ti-dots-vertical"></i>';
        moreBtn.addEventListener("click", (e) => {
            e.stopPropagation(); // Prevent playing track
            if (typeof showActionModal === "function") showActionModal(track);
        });

        item.appendChild(thumb);
        item.appendChild(info);
        item.appendChild(duration);
        item.appendChild(moreBtn);

        dom.searchResults.appendChild(item);
    });

    updateSearchPlayingState();
}

export function updateSearchPlayingState() {
    if (!dom.searchResults) return;

    const currentId = store.current_track && store.current_track.video_id;
    const isPlaying = store.status === "PLAYING";

    dom.searchResults.querySelectorAll(".sr-item").forEach((item) => {
        const isCurrent = currentId && item.dataset.videoId === currentId;
        item.classList.toggle("current", !!isCurrent);
        item.classList.toggle("playing", !!(isCurrent && isPlaying));
    });

    if (typeof globalThis.loadLazyCovers === "function") {
        globalThis.loadLazyCovers();
    }
}

export function playSearchTrack(track) {
    if (store.userRole !== "admin" || !track) return;
    wsSend("play_track", track);
}

export function showActionModal(track) {
    globalThis.pendingTrack = track;
    dom.actionTitle.textContent = track.title;
    if (dom.actionDelete) {
        dom.actionDelete.style.display = (track.local_path || track.is_cached) ? 'block' : 'none';
    }
    if (dom.actionSheet) dom.actionSheet.classList.add("open");
    if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
}

export function hideActionModal() {
    if (dom.actionSheet) dom.actionSheet.classList.remove("open");
    if (dom.mainOverlay) dom.mainOverlay.classList.remove("open");
    globalThis.pendingTrack = null;
}

export function initSearchBusSubscriptions() {
    on("search:results", renderSearchResults);
    on("search:playing-state", updateSearchPlayingState);
    on("search:action-modal-open", (track) => showActionModal(track));
    on("search:action-modal-close", hideActionModal);
}
