import { on } from "../bus.js";
import { dom } from "../dom.js";
import { buildSrThumbHtml, playSearchTrack, showActionModal } from "./search.js";
import { formatTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";

// Quick Search Discover — rendering (T-A8).
// Mirror ringan render/search.js (bangun .sr-item yang sama, reuse di semua
// breakpoint), tapi toggle antara mode rekomendasi personalisasi (default) dan
// mode hasil pencarian. 5 state: Initial, Loading, Empty, No result, Error.
//
// Dipanggil dari:
// - web/static/js/events/discover-search-events.js (T-A7): enterDiscoverSearchLoading(),
//   exitDiscoverSearchMode()
// - web/static/js/ws.js: case "discover_search_results" -> renderDiscoverSearchResults(),
//   case "error" -> handleDiscoverSearchError() (hanya render inline kalau mode aktif)
//
// Elemen diakses via dom.* (registrasi T-A9, lihat dom.js).

let _discoverSearchActive = false;

// Blok rekomendasi personalisasi (bukan discover-artists/discover-genres/discover-cached
// yang merupakan bagian terpisah, di luar cakupan "personalisasi" — lihat dod T-A8).
function getDiscoverPersonalizationEls() {
    return {
        tasteBlock: dom.tasteBlock,
        filterBar: dom.filterBar,
        filterScopeHint: dom.filterScopeHint,
        forYouLabelRow: dom.rowForYouLabel,
        forYouRow: dom.rowForYou,
        genreAffinityLabelRow: dom.rowGenreAffinityLabel,
        genreAffinityRow: dom.rowGenreAffinity,
        unheardLabelRow: dom.rowUnheardLabel,
        unheardRow: dom.rowUnheard,
    };
}

function setDiscoverPersonalizationVisible(visible) {
    const els = getDiscoverPersonalizationEls();
    Object.keys(els).forEach((key) => {
        const el = els[key];
        if (el) el.style.display = visible ? "" : "none";
    });
}

function resetDiscoverSearchStatusAndResults() {
    const statusEl = dom.discoverSearchStatus;
    const resultsEl = dom.discoverSearchResults;
    if (statusEl) {
        statusEl.innerHTML = "";
        statusEl.style.display = "none";
    }
    if (resultsEl) {
        resultsEl.innerHTML = "";
        resultsEl.style.display = "none";
    }
}

// State: Loading — dipanggil dari events file tepat sebelum wsSend('discover_search', ...).
// eslint-disable-next-line no-unused-vars -- dipertahankan untuk konsistensi signature caller (discover-search-events.js), tidak lagi dipakai di body sejak _discoverSearchLastQuery dihapus (S2.2)
export function enterDiscoverSearchLoading(query) {
    _discoverSearchActive = true;
    setDiscoverPersonalizationVisible(false);

    const statusEl = dom.discoverSearchStatus;
    const resultsEl = dom.discoverSearchResults;
    if (resultsEl) {
        resultsEl.innerHTML = "";
        resultsEl.style.display = "none";
    }
    if (statusEl) {
        statusEl.innerHTML = '<span class="spinner"></span> Mencari...';
        statusEl.style.display = "block";
    }
}

// State: Empty — query dikosongkan, balik ke rekomendasi personalisasi tanpa reload.
export function exitDiscoverSearchMode() {
    _discoverSearchActive = false;
    setDiscoverPersonalizationVisible(true);
    resetDiscoverSearchStatusAndResults();
}

// State: No result / hasil ada — dipanggil dari ws.js case "discover_search_results".
export function renderDiscoverSearchResults(results) {
    if (!_discoverSearchActive) return; // respon basi: query sudah diganti/dikosongkan

    const statusEl = dom.discoverSearchStatus;
    const resultsEl = dom.discoverSearchResults;
    if (!resultsEl) return;

    if (!results || results.length === 0) {
        resultsEl.innerHTML = "";
        resultsEl.style.display = "none";
        if (statusEl) {
            statusEl.textContent = "Tidak ditemukan hasil.";
            statusEl.style.display = "block";
        }
        return;
    }

    if (statusEl) {
        statusEl.innerHTML = "";
        statusEl.style.display = "none";
    }
    resultsEl.innerHTML = "";
    resultsEl.style.display = "flex";

    results.forEach((track) => {
        const item = document.createElement("div");
        item.className = "sr-item";
        item.dataset.videoId = track.video_id;
        item.dataset.searchTrackStr = JSON.stringify(track);

        const thumb = document.createElement("div");
        thumb.className = "sr-thumb";
        thumb.innerHTML = typeof buildSrThumbHtml === "function" ? buildSrThumbHtml(track) : "";

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
        duration.textContent = typeof formatTime === "function" ? formatTime(track.duration) : "";

        const moreBtn = document.createElement("button");
        moreBtn.className = "sr-more-btn";
        moreBtn.innerHTML = '<i class="ti ti-dots-vertical"></i>';
        moreBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            if (typeof showActionModal === "function") showActionModal(track);
        });

        item.appendChild(thumb);
        item.appendChild(info);
        item.appendChild(duration);
        item.appendChild(moreBtn);

        item.addEventListener("click", () => {
            if (typeof playSearchTrack === "function") playSearchTrack(track);
        });

        resultsEl.appendChild(item);
    });

    if (typeof globalThis.loadLazyCovers === "function") globalThis.loadLazyCovers();
}

// State: Error — dipanggil dari ws.js case "error" umum, hanya render inline kalau
// Quick Search Discover sedang aktif (di luar itu cukup toast generik seperti biasa).
export function handleDiscoverSearchError() {
    if (!_discoverSearchActive) return;
    const statusEl = dom.discoverSearchStatus;
    const resultsEl = dom.discoverSearchResults;
    if (resultsEl) {
        resultsEl.innerHTML = "";
        resultsEl.style.display = "none";
    }
    if (statusEl) {
        statusEl.textContent = "Terjadi kesalahan saat mencari. Coba lagi.";
        statusEl.style.display = "block";
    }
}

export function initDiscoverSearchBusSubscriptions() {
    on("discover:search-results", (results) => renderDiscoverSearchResults(results));
    on("discover:search-error", handleDiscoverSearchError);
    on("discover:search-loading-enter", (query) => enterDiscoverSearchLoading(query));
    on("discover:search-loading-exit", exitDiscoverSearchMode);
}
