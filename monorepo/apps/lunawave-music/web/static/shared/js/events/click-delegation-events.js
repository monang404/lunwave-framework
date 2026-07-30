import { unlockBrowserAudio } from "../audio/playback-sync.js";
import { emit } from "../bus.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

/** @param {HTMLElement} srItem */
function handleSrItemActivate(srItem) {
    const trackStr = srItem.dataset.trackStr || srItem.dataset.searchTrackStr;
    if (!trackStr) return;
    try {
        const track = JSON.parse(trackStr);
        if (store.userRole === "admin") {
            if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
            wsSend("play_track", track);
        } else {
            emit("toast:log", { message: "Hanya admin yang bisa memutar musik" });
        }
    } catch (err) { console.error(err); }
}

export function initClickDelegationEvents() {
    document.addEventListener("click", (e) => {
        // PATCH-2026-07-24-225: `e.target` bertipe EventTarget (tidak punya
        // .closest), tapi di DOM nyata klik selalu berasal dari sebuah
        // Element -- cast sekali di sini. Hasil `.closest()` sendiri di-cast
        // ke HTMLElement per pemanggilan karena overload generic `.closest()`
        // untuk selector string (bukan nama tag) selalu balik `Element`
        // (bukan tipe caller-nya), padahal `.dataset` butuh HTMLElement.
        const target = /** @type {Element} */ (e.target);

        // 1. Clicks on 3-dots button (.sr-more-btn)
        const moreBtn = /** @type {HTMLElement | null} */ (target.closest(".sr-more-btn"));
        if (moreBtn) {
            const item = /** @type {HTMLElement | null} */ (moreBtn.closest(".sr-item"));
            if (item) {
                const trackStr = item.dataset.trackStr || item.dataset.searchTrackStr;
                if (trackStr) {
                    try {
                        const track = JSON.parse(trackStr);
                        emit("search:action-modal-open", track);
                    } catch (err) { console.error(err); }
                }
            }
            return;
        }

        // 2. Clicks on the sr-item row itself -> Play track
        const srItem = /** @type {HTMLElement | null} */ (target.closest(".sr-item"));
        if (srItem) {
            handleSrItemActivate(srItem);
            return;
        }

        // 3. Clicks on fav-card or disc-card
        const card = /** @type {HTMLElement | null} */ (target.closest(".disc-card, .fav-card, .search-result-item"));
        if (card && card.dataset.vid) {
            let track = null;
            if (card.classList.contains("search-result-item") && card.dataset.searchTrackStr) {
                track = JSON.parse(card.dataset.searchTrackStr);
            } else {
                const vid = card.dataset.vid;
                // find in store lists
                const lists = [
                    store.discover_recent || [],
                    store.discover_cached || [],
                    store.queue || []
                ];
                for (const list of lists) {
                    track = list.find(t => t.video_id === vid);
                    if (track) break;
                }
            }
            if (track) emit("search:action-modal-open", track);
            return;
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const target = /** @type {Element} */ (e.target);
        const srItem = /** @type {HTMLElement | null} */ (target.closest(".sr-item"));
        if (srItem) {
            e.preventDefault();
            handleSrItemActivate(srItem);
        }
    });
}
