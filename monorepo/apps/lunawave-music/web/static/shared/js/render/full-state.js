import { getOrInitAudio, syncBrowserAudio, updateMediaSession } from "../audio/playback-sync.js";
import { emit, on } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { renderHeader } from "../ws.js";

export function applyFullState(data) {
    Object.assign(store, data);
    emit("player:position", store.position);
    // Sync browser audio playback rate jika output = browser
    if (store.audio_output === "browser" && typeof getOrInitAudio === "function") {
        const audio = getOrInitAudio();
        if (audio && store.playback_speed) {
            audio.playbackRate = store.playback_speed;
        }
    }
    // Sync speed dropdown ke nilai dari server
    if (dom.ssSpeedSelect && store.playback_speed) {
        dom.ssSpeedSelect.value = store.playback_speed.toFixed(2);
    }
    renderFullState();
    if (store.userRole !== 'portal' && typeof syncBrowserAudio === "function") {
        syncBrowserAudio();
    }
}

export function renderFullState() {
    if (typeof renderHeader === "function") renderHeader();
    emit("now-playing:changed");
    emit("player:progress");
    emit("player:bar-changed");
    emit("radio:changed");
    emit("queue:changed");
    emit("lyrics:changed");
    emit("settings:sheet-changed");
    emit("search:playing-state");
    emit("discover:playing-state");

    // Dynamic Title
    const track = store.current_track;
    if (track) {
        document.title = `${track.title} - ${track.artist}`;
    } else {
        document.title = "LunaWave — Midnight Audio Experience";
    }

    // Media Session (fungsi ada di playback-sync.js)
    if (typeof updateMediaSession === "function") updateMediaSession();
}

export function initFullStateBusSubscriptions() {
    on("state:full", (data) => applyFullState(data));
    on("state:full-render", renderFullState);
}
