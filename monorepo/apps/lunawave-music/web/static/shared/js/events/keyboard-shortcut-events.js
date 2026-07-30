import { unlockBrowserAudio } from "../audio/playback-sync.js";
import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "../render/navigation.js";
import { closeMainOverlay } from "./settings-events.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

export function initKeyboardShortcutEvents() {
    document.addEventListener("keydown", (e) => {
        // Guard generik: kalau fokus sedang ada di elemen input teks/textarea/
        // contenteditable APAPUN (search-input lama, discover-search-input
        // baru T-A7, atau input teks lain yang mungkin ditambahkan nanti),
        // shortcut global tidak boleh aktif. Sebelumnya guard ini hardcoded
        // hanya mengecek dom.searchInput, sehingga input baru (mis.
        // discoverSearchInput) tidak pernah ter-exclude -- itulah root cause
        // Bug #1 (space -> toggle_pause + karakter spasi hilang dari query)
        // dan Bug #2 (huruf 'l'/'L' -> lyrics overlay kebuka) di Quick Search
        // Discover. Pola guard generik ini menyamakan file ini dengan
        // platform/keyboard.js yang sudah pakai pendekatan serupa.
        const activeEl = /** @type {HTMLElement | null} */ (document.activeElement);
        const isTypingContext =
            activeEl &&
            (activeEl.tagName === "INPUT" ||
                activeEl.tagName === "TEXTAREA" ||
                activeEl.isContentEditable);

        if (isTypingContext) {
            if (e.key === "Escape") activeEl.blur();
            return;
        }

        switch (e.key) {
            case " ":
                if (store.userRole !== "admin") return;
                e.preventDefault();
                if (store.status !== "PLAYING" && store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                    unlockBrowserAudio(true);
                }
                wsSend("toggle_pause");
                break;
            case "n":
            case "N":
                if (store.userRole !== "admin") return;
                if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                    unlockBrowserAudio(true);
                }
                wsSend("next");
                break;
            case "b":
            case "B":
                if (store.userRole !== "admin") return;
                if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                    unlockBrowserAudio(true);
                }
                wsSend("prev");
                break;
            case "s":
            case "S":
                if (store.userRole !== "admin") return;
                wsSend("stop");
                break;
            case "ArrowUp":
                if (store.userRole !== "admin") return;
                e.preventDefault();
                wsSend("volume_up");
                break;
            case "ArrowDown":
                if (store.userRole !== "admin") return;
                e.preventDefault();
                wsSend("volume_down");
                break;
            case "m":
            case "M":
                if (store.userRole !== "admin") return;
                wsSend("download");
                break;
            case "r":
            case "R": {
                if (store.userRole !== "admin") return;
                if (store.status === "LOADING") break;
                const newMode = store.playback_mode === "RADIO" ? "QUEUE" : "RADIO";
                wsSend("set_mode", { mode: newMode });
                break;
            }
            case "l":
            case "L":
                if (dom.lyricsSheet) {
                    const isOpen = dom.lyricsSheet.classList.contains("open");
                    if (isOpen) {
                        dom.lyricsSheet.classList.remove("open");
                        if (typeof closeMainOverlay === "function") closeMainOverlay();
                    } else {
                        dom.lyricsSheet.classList.add("open");
                        if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
                        emit("lyrics:changed");
                    }
                }
                break;
            case "/":
                e.preventDefault();
                if (typeof switchTab === "function") switchTab("search");
                break;
            case "?":
                if (dom.helpSheet) {
                    if (dom.helpSheet.classList.contains("open")) {
                        dom.helpSheet.classList.remove("open");
                        if (typeof closeMainOverlay === "function") closeMainOverlay();
                    } else {
                        dom.helpSheet.classList.add("open");
                        if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
                    }
                }
                break;
            case "Escape":
                emit("search:action-modal-close");
                if (dom.helpSheet) dom.helpSheet.classList.remove("open");
                if (dom.settingsSheet) dom.settingsSheet.classList.remove("open");
                if (dom.lyricsSheet) dom.lyricsSheet.classList.remove("open");
                if (typeof closeMainOverlay === "function") closeMainOverlay();
                break;
        }
    });
}
