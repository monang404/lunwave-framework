import { _fadeIntervals, getOrInitAudio, syncBrowserAudio, unlockBrowserAudio } from "../audio/playback-sync.js";
import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "../render/navigation.js";
import { closeMainOverlay } from "./settings-events.js";
import { markPendingToggle, store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

export function initTransportEvents() {
    if (dom.pbTrackInfo) {
        dom.pbTrackInfo.addEventListener("click", () => {
            if (store.active_tab !== "home" && typeof switchTab === "function") {
                switchTab("home");
            }
        });
    }

    dom.btnPlay.addEventListener("click", () => {
        if (store.userRole === "admin") {
            const wantsPlay = store.status !== "PLAYING";
            store.status = wantsPlay ? "PLAYING" : "PAUSED";
            markPendingToggle(wantsPlay ? "PLAYING" : "PAUSED");
            if (wantsPlay) emit("player:clock-reset");
            emit("player:btn-changed");
            emit("now-playing:changed");
            emit("queue:changed");
            if (wantsPlay && store.audio_output === "browser" && typeof syncBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
            wsSend("toggle_pause");
        }
    });

    dom.btnNext.addEventListener("click", () => {
        if (store.userRole === "admin") {
            const data = {};
            if (store.current_track && store.current_track.video_id) {
                data.video_id = store.current_track.video_id;
            }
            store.status = "LOADING";
            emit("now-playing:changed");
            emit("player:bar-changed");
            if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
            wsSend("next", data);
        }
    });

    dom.btnPrev.addEventListener("click", () => {
        if (store.userRole === "admin") {
            store.status = "LOADING";
            emit("now-playing:changed");
            emit("player:bar-changed");
            if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
            wsSend("prev");
        }
    });

    if (dom.btnRepeat) {
        dom.btnRepeat.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            const currentMode = store.loop_mode || "off";
            const modeCycle = { "off": "track", "track": "queue", "queue": "off" };
            wsSend("set_loop", { mode: modeCycle[currentMode] });
        });
    }

    if (dom.btnStop) {
        dom.btnStop.addEventListener('click', () => {
            if (store.userRole === 'admin') wsSend('stop');
        });
    }

    if (dom.volSlider) {
        globalThis.isDraggingVol = false;
        dom.volSlider.addEventListener("input", () => {
            globalThis.isDraggingVol = true;
            if (typeof _fadeIntervals !== "undefined") {
                _fadeIntervals.forEach((interval, idx) => {
                    if (interval) {
                        clearInterval(interval);
                        _fadeIntervals[idx] = null;
                    }
                });
            }
            store.volume = parseInt(dom.volSlider.value);
            if (dom.pbVolLabel) dom.pbVolLabel.textContent = store.volume + "%";
            if (store.audio_output === "browser" && typeof getOrInitAudio === "function") {
                const audio = getOrInitAudio();
                if (audio) audio.volume = Math.max(0, Math.min(1, store.volume / 100));
            }
        });
        dom.volSlider.addEventListener("change", () => {
            if (store.userRole === "admin") {
                wsSend("volume_set", { volume: store.volume });
            }
            globalThis.isDraggingVol = false;
        });
    }

    if (dom.btnDownload) {
        dom.btnDownload.addEventListener("click", () => {
            if (dom.settingsSheet) dom.settingsSheet.classList.remove("open");
            if (typeof closeMainOverlay === "function") closeMainOverlay();
            if (store.userRole === "admin") wsSend("download");
        });
    }

    if (dom.radioToggleBtn) {
        dom.radioToggleBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            if (store.status === "LOADING") return;
            const newMode = store.playback_mode === "RADIO" ? "QUEUE" : "RADIO";
            store.playback_mode = newMode;
            emit("radio:changed");
            emit("queue:changed");
            wsSend("set_mode", { mode: newMode });
        });
    }

    if (dom.radioRandomizeBtn) {
        dom.radioRandomizeBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            store.radio_queue = [];
            store.current_track = null;
            store.status = "LOADING";
            emit("player:position", 0);
            emit("radio:changed");
            emit("queue:changed");
            emit("now-playing:changed");
            globalThis.scrollTo({ top: 0, behavior: "smooth" });
            if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
            wsSend("radio_randomize", { seed_artist: null });
        });
    }

    if (dom.outputToggleBtn) {
        dom.outputToggleBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            const newOutput = store.audio_output === "browser" ? "device" : "browser";
            if (newOutput === "browser" && typeof unlockBrowserAudio === "function") unlockBrowserAudio();
            wsSend("set_output", { output: newOutput });
        });
    }
}
