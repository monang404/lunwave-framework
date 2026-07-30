import { dom } from "../dom.js";
import { playSearchTrack } from "../render/search.js";
import { escapeHtml } from "../utils/format.js";
import { wsSend } from "../ws.js";

export function initSearchInputEvents() {
    const searchClearBtn = document.getElementById("search-clear-btn");
    if (searchClearBtn) {
        searchClearBtn.addEventListener("click", () => {
            dom.searchInput.value = "";
            searchClearBtn.style.display = "none";
            dom.searchInput.dispatchEvent(new Event("input"));
            dom.searchInput.focus();
        });
    }

    const searchHeader = document.getElementById("search-header");
    if (searchHeader && dom.searchInput) {
        const updateSearchHeaderCollapse = () => {
            const hasValue = !!dom.searchInput.value.trim();
            const isFocused = document.activeElement === dom.searchInput;
            if (hasValue || isFocused) {
                searchHeader.classList.add("collapsed");
            } else {
                searchHeader.classList.remove("collapsed");
            }
        };
        dom.searchInput.addEventListener("input", updateSearchHeaderCollapse);
        dom.searchInput.addEventListener("focus", updateSearchHeaderCollapse);
        dom.searchInput.addEventListener("blur", updateSearchHeaderCollapse);
        updateSearchHeaderCollapse();
    }

    let searchTimer = null;
    let lastSearchQuery = "";

    const STORAGE_KEY = "lunawave_search_history";
    function getSearchHistory() {
        try {
            return JSON.parse(globalThis.safeStorage.get(STORAGE_KEY)) || [];
        } catch {
            return [];
        }
    }
    function saveSearchHistory(query) {
        if (!query) return;
        try {
            let history = getSearchHistory();
            history = history.filter(q => q.toLowerCase() !== query.toLowerCase());
            history.unshift(query);
            if (history.length > 10) history = history.slice(0, 10);
            globalThis.safeStorage.set(STORAGE_KEY, JSON.stringify(history));
        } catch (e) {
            console.warn("Failed to save search history:", e);
        }
    }

    function renderSearchHistory() {
        if (!dom.searchHistoryContainer || !dom.searchHistoryList) return;
        const history = getSearchHistory();
        if (history.length === 0 || dom.searchInput.value.trim()) {
            dom.searchHistoryContainer.style.display = "none";
            return;
        }
        dom.searchHistoryContainer.style.display = "block";
        dom.searchHistoryList.innerHTML = history.map(q => `
            <div class="search-history-item" style="padding: 10px; border-radius: 8px; background: var(--bg-elevated); cursor: pointer; display: flex; align-items: center; gap: 10px;" data-query="${escapeHtml(q)}">
                <i class="ti ti-history" style="color: var(--text-3);"></i>
                <span style="color: var(--text-1); font-size: 14px;">${escapeHtml(q)}</span>
            </div>
        `).join("");
    }

    if (dom.searchHistoryList) {
        dom.searchHistoryList.addEventListener("click", (e) => {
            const item = e.target.closest(".search-history-item");
            if (item) {
                const q = item.dataset.query;
                dom.searchInput.value = q;
                dom.searchInput.dispatchEvent(new Event("input"));
                dom.searchInput.focus();

                if (searchTimer) clearTimeout(searchTimer);
                lastSearchQuery = q;
                dom.searchMsg.innerHTML = '<span class="spinner"></span> Mencari...';
                dom.searchMsg.style.display = "block";
                dom.searchHistoryContainer.style.display = "none";
                dom.searchResults.style.display = "none";
                wsSend("search", { query: q });
            }
        });
    }

    if (dom.searchHistoryClear) {
        dom.searchHistoryClear.addEventListener("click", () => {
            globalThis.safeStorage.remove(STORAGE_KEY);
            renderSearchHistory();
        });
    }

    if (dom.searchInput) {
        dom.searchInput.addEventListener("focus", () => {
            if (!dom.searchInput.value.trim()) {
                renderSearchHistory();
                dom.searchMsg.style.display = "none";
            }
        });

        dom.searchInput.addEventListener("input", (e) => {
            if (searchClearBtn) searchClearBtn.style.display = e.target.value ? "block" : "none";
            const q = e.target.value.trim();
            if (searchTimer) clearTimeout(searchTimer);
            if (!q) {
                dom.searchMsg.textContent = "Ketik nama lagu atau artis";
                dom.searchMsg.style.display = "block";
                dom.searchResults.innerHTML = "";
                dom.searchResults.style.display = "none";
                lastSearchQuery = "";
                renderSearchHistory();
                return;
            }
            dom.searchHistoryContainer.style.display = "none";
            if (q !== lastSearchQuery) {
                lastSearchQuery = q;
                searchTimer = setTimeout(() => {
                    dom.searchMsg.innerHTML = '<span class="spinner"></span> Mencari...';
                    dom.searchMsg.style.display = "block";
                    dom.searchResults.style.display = "none";
                    saveSearchHistory(q);
                    wsSend("search", { query: q });
                }, 500);
            }
        });

        dom.searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const q = e.target.value.trim();
                if (q) {
                    if (searchTimer) clearTimeout(searchTimer);
                    lastSearchQuery = q;
                    dom.searchMsg.innerHTML = '<span class="spinner"></span> Mencari...';
                    dom.searchMsg.style.display = "block";
                    dom.searchHistoryContainer.style.display = "none";
                    dom.searchResults.style.display = "none";
                    saveSearchHistory(q);
                    wsSend("search", { query: q });
                }
            }
        });
    }

    if (dom.searchResults) {
        dom.searchResults.addEventListener("click", (e) => {
            const item = e.target.closest(".sr-item");
            if (item && item.dataset.searchTrackStr) {
                try {
                    const track = JSON.parse(item.dataset.searchTrackStr);
                    if (typeof playSearchTrack === "function") playSearchTrack(track);
                } catch (err) {
                    console.error("Invalid track data", err);
                }
            }
        });
    }
}
