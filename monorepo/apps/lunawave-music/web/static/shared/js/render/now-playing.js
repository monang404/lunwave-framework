import { on } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { formatTime, formatRelativeTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";

export function renderNowPlaying() {
    const t = store.current_track;

    if (dom.vinylCover) {
        if (t && t.video_id) {
            dom.vinylCover.style.display = "none";
            if (dom.vinylIcon) dom.vinylIcon.style.display = "block";
            globalThis.getCoverArt(t).then(url => {
                if (url && store.current_track && store.current_track.video_id === t.video_id) {
                    dom.vinylCover.src = url;
                    dom.vinylCover.style.display = "block";
                    if (dom.vinylIcon) dom.vinylIcon.style.display = "none";
                    if (typeof globalThis.extractDominantColor === "function" && dom.tabHome) {
                        globalThis.extractDominantColor(dom.vinylCover, (color) => {
                            if (color && color.r !== undefined) {
                                dom.tabHome.style.setProperty("--color-r", color.r);
                                dom.tabHome.style.setProperty("--color-g", color.g);
                                dom.tabHome.style.setProperty("--color-b", color.b);
                            }
                        });
                    }
                }
            });
        } else {
            dom.vinylCover.src = "";
            dom.vinylCover.style.display = "none";
            if (dom.vinylIcon) dom.vinylIcon.style.display = "block";
        }
    }

    if (dom.npThumbIcon && dom.npEqAnim) {
        if (store.status === "PLAYING") {
            dom.npThumbIcon.style.display = "none";
            dom.npEqAnim.style.display = "flex";
            if (dom.vinylRecord) {
                const isBrowser = store.userRole === "client" || store.audio_output === "browser";
                dom.vinylRecord.classList.add(isBrowser ? "visualizer-active" : "playing");
                dom.vinylRecord.classList.remove(isBrowser ? "playing" : "visualizer-active");
            }
        } else {
            dom.npThumbIcon.style.display = "block";
            dom.npEqAnim.style.display = "none";
            if (dom.vinylRecord) {
                dom.vinylRecord.classList.remove("playing");
                dom.vinylRecord.classList.remove("visualizer-active");
            }
        }
    }

    if (dom.homeEqualizer) {
        const hasLyrics = store.lyrics_lines && store.lyrics_lines.length > 0;
        dom.homeEqualizer.style.display = (!hasLyrics && store.status === "PLAYING") ? "flex" : "none";
    }

    if (dom.vinylRecord) {
        if (store.status === "PLAYING") {
            dom.vinylRecord.classList.add("playing");
        } else {
            dom.vinylRecord.classList.remove("playing");
        }
    }

    // PATCH-ANDROID-AUDIO-01: satu-satunya tempat yang nentuin data-player-state,
    // dipanggil juga dari player.js & ws.js (progress tick) supaya nggak
    // ada dua sumber kebenaran yang bisa desync.
    syncPlayerStateAttr();

    if (store.status === "LOADING") {
        dom.npTitle.innerHTML = '<span class="spinner" style="display:inline-block; margin-right:8px; vertical-align:-3px; width:20px; height:20px;"></span> ⏳ Memuat...';
        dom.npArtist.textContent = (t && t.title) ? t.title : "";
    } else if (t && t.title) {
        const cleanedTitle = typeof cleanTrackTitle === "function" ? cleanTrackTitle(t.title) : t.title;
        dom.npTitle.textContent = cleanedTitle.toLowerCase().replace(/(?:^|\s|-)\S/g, function(a) { return a.toUpperCase(); });
        dom.npArtist.textContent = t.artist || "";
    } else {
        dom.npTitle.textContent = "Belum ada lagu yang diputar";
        dom.npArtist.textContent = "Cari lagu untuk memulai";
    }

    if (dom.npDurMeta && t) {
        dom.npDurMeta.textContent = formatTime(t.duration);
    } else if (dom.npDurMeta) {
        dom.npDurMeta.textContent = '';
    }

    renderNowPlayingStats(t);
}

// PATCH-2026-07-27: play_count/last_played (dihitung tiap track_loader.py
// memulai lagu) dan loudness_lufs/true_peak_dbtp (dianalisis via ffprobe,
// fitur EBU R128) sudah dikirim server lewat track_to_dict() tapi
// sebelumnya tidak pernah dirender di mana pun -- data cuma dipakai
// internal (scoring Discover bandit). Ini murni menampilkan apa yang
// sudah ada di objek track, tidak menambah request baru.
function renderNowPlayingStats(t) {
    if (!dom.npStats) return;
    if (!t || !t.video_id) {
        dom.npStats.style.display = "none";
        dom.npStats.textContent = "";
        return;
    }

    const parts = [];
    if (t.play_count) {
        const playedText = t.play_count === 1 ? "1x diputar" : `${t.play_count}x diputar`;
        parts.push(t.last_played ? `${playedText} · terakhir ${formatRelativeTime(t.last_played)}` : playedText);
    }
    if (typeof t.loudness_lufs === "number") {
        parts.push(`🔊 ${t.loudness_lufs.toFixed(1)} LUFS`);
    }

    if (parts.length === 0) {
        dom.npStats.style.display = "none";
        dom.npStats.textContent = "";
    } else {
        dom.npStats.style.display = "block";
        dom.npStats.textContent = parts.join(" · ");
    }
}

// PATCH-ANDROID-AUDIO-01
export function syncPlayerStateAttr() {
    const t = store.current_track;
    if (!t || (!t.video_id && store.status !== "LOADING")) {
        document.body.setAttribute("data-player-state", "IDLE");
    } else {
        document.body.setAttribute("data-player-state", store.status);
    }
}

export function initNowPlayingBusSubscriptions() {
    on("now-playing:changed", renderNowPlaying);
    on("now-playing:sync-state-attr", syncPlayerStateAttr);
}
