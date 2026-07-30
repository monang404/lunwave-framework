import { getOrInitAudio } from "../audio/playback-sync.js";
import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { formatTime } from "../utils/format.js";
import { wsSend } from "../ws.js";

export function initProgressEvents() {
    globalThis.isDraggingPb = false;

    function updatePb(e) {
        if (store.userRole !== "admin") return 0;
        const rect = dom.pbProgressTrack.getBoundingClientRect();
        let pct = (e.clientX - rect.left) / rect.width;
        pct = Math.max(0, Math.min(1, pct));
        const dur = store.current_track ? store.current_track.duration : 0;
        if (dom.pbProgressFill) dom.pbProgressFill.style.width = (pct * 100) + "%";
        const thumb = dom.pbProgressTrack.querySelector('.pb-thumb');
        if (thumb) thumb.style.left = (pct * 100) + "%";
        if (dom.pbTimePos) dom.pbTimePos.textContent = formatTime(pct * dur);
        const playerBar = document.getElementById("player-bar");
        if (playerBar) playerBar.style.setProperty("--mini-progress", (pct * 100) + "%");
        return pct;
    }

    if (dom.pbProgressTrack) {
        dom.pbProgressTrack.addEventListener("pointerdown", (e) => {
            if (store.userRole !== "admin") return;
            globalThis.isDraggingPb = true;
            dom.pbProgressTrack.setPointerCapture(e.pointerId);
            updatePb(e);
        });
        dom.pbProgressTrack.addEventListener("pointermove", (e) => {
            if (globalThis.isDraggingPb) updatePb(e);
        });
        dom.pbProgressTrack.addEventListener("pointerup", (e) => {
            if (!globalThis.isDraggingPb) return;
            globalThis.isDraggingPb = false;
            dom.pbProgressTrack.releasePointerCapture(e.pointerId);
            const pct = updatePb(e);
            const dur = store.current_track ? store.current_track.duration : 0;
            if (dur > 0) {
                const targetPos = pct * dur;
                if (store.audio_output === "browser" && typeof getOrInitAudio === "function") {
                    const audio = getOrInitAudio();
                    if (audio && audio.src) {
                        audio.currentTime = targetPos;
                        emit("player:position", targetPos);
                        emit("player:progress");
                    }
                }
                wsSend("seek", { position: targetPos });
            }
        });
        dom.pbProgressTrack.addEventListener("pointercancel", (e) => {
            if (!globalThis.isDraggingPb) return;
            globalThis.isDraggingPb = false;
            try { dom.pbProgressTrack.releasePointerCapture(e.pointerId); } catch { /* best-effort, aman diabaikan */ }
            emit("player:progress");
        });
    }
}
