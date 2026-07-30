import { unlockBrowserAudio } from "../audio/playback-sync.js";
import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

export function initActionModalEvents() {
    if (dom.actionPlayNow) {
        dom.actionPlayNow.addEventListener("click", () => {
            if (globalThis.pendingTrack) {
                if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                    unlockBrowserAudio(true);
                }
                wsSend("play_track", globalThis.pendingTrack);
            }
            emit("search:action-modal-close");
        });
    }

    if (dom.actionEnqueue) {
        dom.actionEnqueue.addEventListener("click", () => {
            if (globalThis.pendingTrack) wsSend("queue_add", globalThis.pendingTrack);
            emit("search:action-modal-close");
        });
    }

    if (dom.actionCancel) {
        dom.actionCancel.addEventListener("click", () => {
            emit("search:action-modal-close");
        });
    }

    if (dom.actionDelete) {
        dom.actionDelete.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            if (globalThis.pendingTrack) {
                wsSend("delete_download", globalThis.pendingTrack);
            }
            emit("search:action-modal-close");
        });
    }
}
