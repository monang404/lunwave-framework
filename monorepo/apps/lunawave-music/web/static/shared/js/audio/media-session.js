import { store, markPendingToggle } from "/framework/static/js/core/store.js";
import { emit } from "../bus.js";
import { wsSend } from "../ws.js";
import { unlockBrowserAudio } from "./audio-pool.js";
import { syncBrowserAudio } from "./playback-sync.js";

// Flag untuk mencegah infinite loop antara native audio event dan Media Session handler
// We need to keep a global flag to match playback-sync.js
if (typeof globalThis._mediaSessionHandling === "undefined") {
    globalThis._mediaSessionHandling = false;
}

export function _updateMediaSessionState(state) {
    if (!('mediaSession' in navigator)) return;
    try {
        navigator.mediaSession.playbackState = state; // "playing" | "paused" | "none"
    } catch { /* best-effort, aman diabaikan */ }
}

let _lastMediaSessionVideoId = null;

export function updateMediaSession() {
    if (!('mediaSession' in navigator)) return;
    const track = store.current_track;
    if (!track) {
        _updateMediaSessionState('none');
        navigator.mediaSession.metadata = null;
        _lastMediaSessionVideoId = null;
        return;
    }

    // Perbarui metadata hanya jika lagu berubah
    if (_lastMediaSessionVideoId !== track.video_id) {
        _lastMediaSessionVideoId = track.video_id;
        const coverUrl = track.thumbnail
            ? (track.thumbnail.startsWith('http') ? track.thumbnail : globalThis.location.origin + track.thumbnail)
            : (globalThis.location.origin + '/api/thumbnail/' + track.video_id);

        navigator.mediaSession.metadata = new MediaMetadata({
            title: track.title || 'Unknown',
            artist: track.artist || 'Unknown',
            album: 'LunaWave',
            artwork: [
                { src: coverUrl, sizes: '512x512', type: 'image/jpeg' }
            ]
        });

        // Helper untuk update instan sebelum menunggu respon server
        const _optimisticToggle = (wantsPlay) => {
            if (store.userRole !== "admin") return;
            store.status = wantsPlay ? "PLAYING" : "PAUSED";
            markPendingToggle(wantsPlay ? "PLAYING" : "PAUSED");
            if (wantsPlay) emit("player:clock-reset");
            emit("player:btn-changed");
            emit("now-playing:changed");
            emit("queue:changed");
            if (wantsPlay && store.audio_output === "browser" && typeof syncBrowserAudio === "function") {
                unlockBrowserAudio(true);
            }
        };

        // Pasang action handler — gunakan nama action yang sesuai dengan backend Python
        try {
            navigator.mediaSession.setActionHandler('play', () => {
                if (store.status === "PLAYING") return; // Cegah double toggle jika sudah play
                globalThis._mediaSessionHandling = true;
                _optimisticToggle(true);
                if (typeof wsSend === "function") wsSend("toggle_pause");
                setTimeout(() => { globalThis._mediaSessionHandling = false; }, 300);
            });
            navigator.mediaSession.setActionHandler('pause', () => {
                if (store.status !== "PLAYING") return; // Cegah double toggle jika sudah pause
                globalThis._mediaSessionHandling = true;
                _optimisticToggle(false);
                if (typeof wsSend === "function") wsSend("toggle_pause");
                setTimeout(() => { globalThis._mediaSessionHandling = false; }, 300);
            });
            navigator.mediaSession.setActionHandler('previoustrack', () => {
                if (store.userRole === "admin") {
                    store.status = "LOADING";
                    emit("now-playing:changed");
                    emit("player:bar-changed");
                    const data = (store.current_track && store.current_track.video_id) ? { video_id: store.current_track.video_id } : {};
                    if (typeof wsSend === "function") wsSend("prev", data);
                }
            });
            navigator.mediaSession.setActionHandler('nexttrack', () => {
                if (store.userRole === "admin") {
                    store.status = "LOADING";
                    emit("now-playing:changed");
                    emit("player:bar-changed");
                    const data = (store.current_track && store.current_track.video_id) ? { video_id: store.current_track.video_id } : {};
                    if (typeof wsSend === "function") wsSend("next", data);
                }
            });
            navigator.mediaSession.setActionHandler('seekto', (details) => {
                if (typeof wsSend === "function") wsSend("seek", { position: details.seekTime });
            });
        } catch (e) {
            console.warn("[audio] Media Session API tidak didukung atau error:", e);
        }
    }

    // Selalu sinkronkan status putar/jeda
    _updateMediaSessionState(store.status === "PLAYING" ? "playing" : "paused");
}
