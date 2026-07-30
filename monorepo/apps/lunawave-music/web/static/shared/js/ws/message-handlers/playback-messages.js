import { _resumeAndPlay, getOrInitAudio, syncBrowserAudio } from "../../audio/playback-sync.js";
import { emit as bus } from "../../bus.js";
import { isPendingToggleActive, store } from "/framework/static/js/core/store.js";

export function handlePlaybackMessage(msg) {
    switch (msg.type) {
        case "state":
            bus("state:full", msg.data);
            break;
        case "progress": {
            const _awaitedTarget = store._pendingToggleTarget;
            const _stillWaitingConfirmation = !!_awaitedTarget && isPendingToggleActive(_awaitedTarget);
            const _inToggleGrace = _stillWaitingConfirmation && msg.data.status !== _awaitedTarget;
            if (_stillWaitingConfirmation && msg.data.status === _awaitedTarget) {
                store._pendingToggleTarget = null;
            }

            let statusChanged = false;
            if (!_inToggleGrace) {
                if (store.status !== msg.data.status) {
                    store.status = msg.data.status;
                    statusChanged = true;
                    if (store.status === "PLAYING") {
                        bus("player:clock-reset");
                    }
                }
            }
            if (msg.data.server_ts) {
                store.server_ts = msg.data.server_ts;
            }

            const _browserAudioEl = (store.audio_output === "browser") ? getOrInitAudio() : null;
            const _browserAudioActive = !!(_browserAudioEl && !_browserAudioEl.paused && _browserAudioEl.src && !_browserAudioEl.src.startsWith("data:"));
            if (store.audio_output !== "browser") {
                bus("player:position", msg.data.position);
            }

            if (store.audio_output === "browser" && store.status === "PLAYING") {
                const audio = _browserAudioEl;
                if (_browserAudioActive) {
                    if (!_inToggleGrace) {
                        const diff = Math.abs(audio.currentTime - msg.data.position);
                        if (diff > 5 && msg.data.position > 2) {
                            audio.currentTime = msg.data.position;
                            bus("player:position", msg.data.position);
                        }
                    }
                } else if (audio.paused && audio.src && !audio.src.startsWith("data:") && audio.readyState >= 2) {
                    if (!globalThis.audioBlocked && typeof _resumeAndPlay === "function") {
                        _resumeAndPlay(audio);
                    }
                }
            }

            bus("player:progress");
            bus("player:btn-changed");
            bus("now-playing:sync-state-attr");
            if (statusChanged) {
                bus("now-playing:changed");
                bus("queue:changed");
                bus("radio:changed");
                bus("search:playing-state");
                bus("discover:playing-state");
            }
            syncBrowserAudio();
            if (typeof syncLocalLyrics === "function") syncLocalLyrics();
            break;
        }
        case "lyrics":
            store.lyrics_lines = msg.data.lyrics_lines || [];
            store.lyrics_timestamps = msg.data.lyrics_timestamps || [];
            store.lyrics_index = msg.data.lyrics_index || 0;
            store.lyrics_offset = msg.data.lyrics_offset || 0;
            store.lyrics_loading = msg.data.lyrics_loading || false;
            bus("lyrics:changed");
            break;
    }
}

export function syncLocalLyrics() {
    if (store.lyrics_timestamps && store.lyrics_timestamps.length > 0) {
        const pos = store.position + (store.lyrics_offset || 0);
        let newIdx = -1;
        for (let i = 0; i < store.lyrics_timestamps.length; i++) {
            if (pos >= store.lyrics_timestamps[i]) {
                newIdx = i;
            } else {
                break;
            }
        }
        newIdx = Math.max(0, newIdx);
        if (store.lyrics_index !== newIdx) {
            store.lyrics_index = newIdx;
            bus("lyrics:changed");
        }
    }
}
