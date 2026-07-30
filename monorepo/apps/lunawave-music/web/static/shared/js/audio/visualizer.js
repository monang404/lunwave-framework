import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { analyser, dataArray } from "./playback-sync.js";

// PATCH-2026-07-24-223: analyser sekarang benar-benar diisi oleh
// _initAnalyser() di playback-sync.js. Pakai visualizer audio-reactive asli
// kalau analyser tersedia; startFakeBeatLoop() tetap jadi fallback untuk
// browser tanpa Web Audio API (lihat unlockBrowserAudio: AC null → analyser
// tidak pernah di-init).
export function initVisualizer() {
    if (analyser) {
        startVisualizerLoop();
    } else {
        startFakeBeatLoop();
    }
}

// PERF-02: dulu ini rAF loop 60fps yang jalan terus selama PLAYING, padahal
// isinya cuma ngecek "sudah lewat 500ms belum" tiap frame (59 dari 60
// panggilan per detik berakhir `return` tanpa ngapa-ngapain). Ini pola yang
// sama persis dengan progress clock di player.js: rAF dipakai sebagai
// "timer wakeup", bukan buat animasi per-frame beneran. Bedanya di sini
// malah lebih jelas boros karena efeknya cuma pulsa tiap 500ms (bukan
// gerakan kontinu), jadi ganti ke setInterval(500ms) — perilaku & tampilan
// tetap sama persis (glow tetap pakai CSS transition 0.15s/0.4s yang sudah
// ada, gak berubah), tapi main thread gak lagi dibangunin 60x/detik.
let _fakeBeatInterval = null;
export function startFakeBeatLoop() {
    if (_fakeBeatInterval) return;
    const BASE_INTERVAL = 500;
    function beat() {
        if (store.status !== 'PLAYING') {
            if (dom.tabHome) {
                dom.tabHome.style.removeProperty('--beat-glow-opacity');
                dom.tabHome.style.removeProperty('--beat-bg-brightness');
                dom.tabHome.style.removeProperty('--beat-glow-transition');
            }
            if (_fakeBeatInterval) {
                clearInterval(_fakeBeatInterval);
                _fakeBeatInterval = null;
            }
            return;
        }
        if (!dom.tabHome) return;
        dom.tabHome.style.setProperty('--beat-glow-opacity', '0.5');
        dom.tabHome.style.setProperty('--beat-bg-brightness', '0.28');
        dom.tabHome.style.setProperty('--beat-glow-transition', '0.15s');
        setTimeout(() => {
            if (!dom.tabHome) return;
            dom.tabHome.style.setProperty('--beat-glow-opacity', '0.4');
            dom.tabHome.style.setProperty('--beat-bg-brightness', '0.22');
            dom.tabHome.style.setProperty('--beat-glow-transition', '0.4s');
        }, 150);
    }
    _fakeBeatInterval = setInterval(beat, BASE_INTERVAL);
    beat();
}

// PATCH-2026-07-24-223: `analyser`/`dataArray` sekarang diisi oleh
// _initAnalyser() di playback-sync.js (createMediaElementSource dari
// audioPool -> analyser -> ctx.destination), jadi loop di bawah ini sudah
// benar-benar jalan saat analyser tersedia -- bukan dead code lagi.
let _vizRafId = null;
function startVisualizerLoop() {
    if (!analyser || !dom.vinylRecord) return;
    const isBrowser = store.userRole === "client" || store.audio_output === "browser";
    if (!isBrowser || store.status !== "PLAYING" || document.hidden) {
        if (dom.tabHome) {
            dom.tabHome.style.removeProperty('--beat-glow-opacity');
            dom.tabHome.style.removeProperty('--beat-bg-brightness');
            dom.tabHome.style.removeProperty('--beat-glow-transition');
        }
        _vizRafId = null;
        return;
    }
    analyser.getByteFrequencyData(dataArray);
    let bassSum = 0;
    for (let i = 0; i < 10; i++) bassSum += dataArray[i];
    const ratio = (bassSum / 10) / 255;
    if (dom.tabHome) {
        dom.tabHome.style.setProperty('--beat-glow-opacity', (0.4 + ratio * 0.2).toFixed(3));
        dom.tabHome.style.setProperty('--beat-bg-brightness', (0.2 + ratio * 0.1).toFixed(3));
        dom.tabHome.style.setProperty('--beat-glow-transition', ratio > 0.4 ? '0.2s' : '0.4s');
    }
    _vizRafId = requestAnimationFrame(startVisualizerLoop);
}

export function resumeVisualizerLoop() {
    if (!_vizRafId && analyser) startVisualizerLoop();
}
