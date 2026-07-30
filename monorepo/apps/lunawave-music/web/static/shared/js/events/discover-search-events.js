import { dom } from "../dom.js";
import { emit } from "../bus.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

// Quick Search Discover — event handling (T-A7).
// Mirror pola web/static/js/events/search-input-events.js (debounce 500ms,
// tombol clear/reset), tapi target #tab-discover, action WS "discover_search"
// (BUKAN "search" — itu live YouTube search), lihat T-A3/server/handlers/ws_discovery.py.
//
// Catatan scope T-A7: hanya event wiring + trigger request. Rendering 5 state
// (Initial/Loading/Empty/No result/Error) & transisi balik ke rekomendasi
// personalisasi adalah scope T-A8 (web/static/js/render/discover-search.js).
// Elemen diakses via dom.* (registrasi T-A9, lihat dom.js).

export function initDiscoverSearchEvents() {
    const input = dom.discoverSearchInput;
    if (!input) return; // markup T-A5 belum ada di halaman ini

    const clearBtn = dom.discoverSearchClearBtn;
    const filterRow = dom.discoverSearchFilterRow;
    const kategoriToggle = dom.discoverSearchKategoriToggle;
    const decadeBtn = dom.discoverSearchDecadeBtn;
    const decadeContainer = dom.discoverSearchDecadeContainer;
    const decadeChips = dom.discoverSearchDecadeChips;

    let debounceTimer = null;
    let activeKategori = "all";
    let activeDecade = "all";

    // getDecade() didefinisikan di render/discover-personalize.js. Fallback lokal
    // dijaga supaya file ini tidak diam-diam gagal kalau urutan <script> berubah.
    function resolveDecade(year) {
        if (typeof globalThis.getDecade === "function") return globalThis.getDecade(year);
        if (!year) return null;
        const y = parseInt(year, 10);
        if (isNaN(y)) return null;
        return Math.floor(y / 10) * 10;
    }

    // Opsi dekade (K2): diturunkan dari data personalisasi yang sudah dimuat
    // (store.discover_for_you/genre_affinity_artists/unheard), pola sama persis
    // dengan buildDecadeChips() di filter-bar Discover existing. Tidak ada query
    // atau kolom skema baru.
    function buildDecadeOptions() {
        if (!decadeChips) return;
        const decadesSet = new Set();
        const allArtists = [].concat(
            (globalThis.store && store.discover_for_you) || [],
            (globalThis.store && store.discover_genre_affinity_artists) || [],
            (globalThis.store && store.discover_unheard) || []
        );
        allArtists.forEach((a) => {
            const dec = resolveDecade(a.tahun_aktif);
            if (dec) decadesSet.add(dec);
        });
        const decades = [...decadesSet].sort((a, b) => a - b);
        const items = [
            `<button class="custom-dropdown-item${activeDecade === "all" ? " active" : ""}" data-value="all">Semua Era</button>`,
        ].concat(
            decades.map(
                (d) =>
                    `<button class="custom-dropdown-item${activeDecade === String(d) ? " active" : ""}" data-value="${d}">${d}an</button>`
            )
        );
        decadeChips.innerHTML = items.join("");
    }

    function resetFilters() {
        activeKategori = "all";
        activeDecade = "all";
        if (kategoriToggle) {
            kategoriToggle.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
            const allBtn = kategoriToggle.querySelector('[data-kategori="all"]');
            if (allBtn) allBtn.classList.add("active");
        }
        if (decadeBtn) decadeBtn.innerHTML = 'Semua Era <i class="ti ti-chevron-down"></i>';
        buildDecadeOptions();
    }

    function showFilterRow(show) {
        if (filterRow) filterRow.style.display = show ? "" : "none";
    }

    function sendSearch(query) {
        emit("discover:search-loading-enter", query);
        wsSend("discover_search", { query: query, kategori: activeKategori, decade: activeDecade });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            input.value = "";
            clearBtn.style.display = "none";
            showFilterRow(false);
            resetFilters();
            // Query kosong: balik ke rekomendasi personalisasi tanpa round-trip
            // ke server. Transisi tampilan ditangani render/discover-search.js (T-A8).
            emit("discover:search-loading-exit");
            input.focus();
        });
    }

    input.addEventListener("input", (e) => {
        const raw = e.target.value;
        const trimmed = raw.trim();
        if (clearBtn) clearBtn.style.display = raw ? "block" : "none";
        showFilterRow(!!trimmed);

        if (debounceTimer) clearTimeout(debounceTimer);

        if (!trimmed) {
            resetFilters();
            emit("discover:search-loading-exit");
            return;
        }

        debounceTimer = setTimeout(() => {
            sendSearch(trimmed);
        }, 500);
    });

    input.addEventListener("keydown", (e) => {
        // Cegah semua keydown di kolom search ini bubble ke document (di mana
        // events/keyboard-shortcut-events.js listen untuk shortcut global
        // seperti Space=toggle_pause, L=lyrics overlay, N/B/S/M/R, dst).
        // Search box wajib terisolasi penuh dari state player -- lihat
        // AI_CONTEXT.md/PATCHLOG fix Bug#1 & Bug#2 Quick Search Discover.
        e.stopPropagation();

        if (e.key !== "Enter") return;
        const trimmed = input.value.trim();
        if (!trimmed) return;
        if (debounceTimer) clearTimeout(debounceTimer);
        sendSearch(trimmed);
    });

    if (kategoriToggle) {
        kategoriToggle.addEventListener("click", (e) => {
            const btn = e.target.closest("button");
            if (!btn) return;
            kategoriToggle.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            activeKategori = btn.dataset.kategori || "all";
            const trimmed = input.value.trim();
            if (trimmed) sendSearch(trimmed);
        });
    }

    if (decadeBtn && decadeContainer) {
        decadeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            decadeContainer.classList.toggle("open");
        });
        document.addEventListener("click", () => {
            decadeContainer.classList.remove("open");
        });
    }

    if (decadeChips) {
        decadeChips.addEventListener("click", (e) => {
            const btn = e.target.closest(".custom-dropdown-item");
            if (!btn) return;
            decadeChips.querySelectorAll(".custom-dropdown-item").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            activeDecade = btn.dataset.value;
            if (decadeBtn) decadeBtn.innerHTML = `${btn.textContent} <i class="ti ti-chevron-down"></i>`;
            const trimmed = input.value.trim();
            if (trimmed) sendSearch(trimmed);
        });
    }

    buildDecadeOptions();
}
