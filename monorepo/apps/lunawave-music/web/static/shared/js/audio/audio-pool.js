import { initVisualizer, resumeVisualizerLoop, startFakeBeatLoop } from "./visualizer.js";
import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { isPendingToggleActive, markPendingToggle, store } from "/framework/static/js/core/store.js";
import { syncLocalLyrics, wsSend } from "../ws.js";
import { _updateMediaSessionState } from "./media-session.js";
import { syncBrowserAudio, _fadeIntervals, activeAudioIndex, resetLastLoadedVideoId } from "./playback-sync.js";

export const audioPool = [new Audio(), new Audio()];
export let audioUnlocked = false;
let _unlocking = false;
let audioCtx = null;

export let analyser = null;
export let dataArray = null;

// PATCH-2026-07-24-223: `analyser`/`dataArray` dulu cuma dideklarasikan
// `= null` dan tidak pernah diisi (lihat FIXME lama di visualizer.js), jadi
// startVisualizerLoop() di sana selalu no-op dan fallback ke startFakeBeatLoop.
// _initAnalyser() menghubungkan kedua elemen <audio> di audioPool lewat
// AnalyserNode, sekali per sesi (createMediaElementSource cuma boleh
// dipanggil sekali per elemen -- panggilan kedua akan throw). Analyser HARUS
// disambung balik ke ctx.destination, karena createMediaElementSource
// memutus rute audio->speaker default; tanpa .connect(ctx.destination) audio
// akan bisu total.
// eslint-disable-next-line no-unused-vars
function _initAnalyser(ctx) {
    if (analyser) return; // sudah pernah di-init, jangan connect dua kali
    try {
        analyser = ctx.createAnalyser();
        analyser.fftSize = 64;
        analyser.smoothingTimeConstant = 0.8;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.connect(ctx.destination);
        audioPool.forEach((audio) => {
            const source = ctx.createMediaElementSource(audio);
            source.connect(analyser);
        });
    } catch (e) {
        console.warn("[audio] gagal inisialisasi analyser, fallback ke fake beat loop:", e);
        analyser = null;
        dataArray = null;
    }
}

export function getOrInitAudio() {
    return audioPool[activeAudioIndex];
}

function initAudioPool() {
    audioPool.forEach((audio, idx) => {
        audio.preload = "auto";
        audio.onerror = () => {
            const err = audio.error;
            if (!err) return;
            if (err.code === 1) return;
            if (err.code === 4 && audio.src.includes("data:audio")) return;
            const errMsg = err.message || ("code " + err.code);
            if (errMsg.includes("Empty src") || !audio.getAttribute("src")) return;
            console.warn("Browser audio error:", err.code, errMsg);
            emit("toast:log", { message: "⚠️ Audio stream info: " + errMsg });
        };
        audio.addEventListener("timeupdate", () => {
            if (idx !== activeAudioIndex) return;
            if (store.userRole === "client" || store.audio_output === "browser") {
                if (!globalThis.isDraggingPb) {
                    emit("player:position", audio.currentTime);
                }
                if (typeof syncLocalLyrics === "function") syncLocalLyrics();
            }
        });
        audio.addEventListener("pause", () => {
            if (idx !== activeAudioIndex) return;
            _updateMediaSessionState("paused");
            if (globalThis._mediaSessionHandling || globalThis.audioBlocked || audio.ended) return;
            const _inUIGrace = isPendingToggleActive("PAUSED");
            if (!_inUIGrace && store.status === "PLAYING") {
                console.log("[audio] Native pause (headset/OS), syncing to server...");
                if (store.userRole === "admin") {
                    store.status = "PAUSED";
                    markPendingToggle("PAUSED");
                    emit("player:btn-changed");
                    emit("now-playing:changed");
                    if (typeof wsSend === "function") wsSend("toggle_pause");
                }
            }
        });
        audio.addEventListener("play", () => {
            if (idx !== activeAudioIndex) return;
            _updateMediaSessionState("playing");
            if (globalThis._mediaSessionHandling || globalThis.audioBlocked) return;
            const _inUIGrace = isPendingToggleActive("PLAYING");
            if (!_inUIGrace && store.status !== "PLAYING") {
                console.log("[audio] Native play (headset/OS), syncing to server...");
                if (store.userRole === "admin") {
                    store.status = "PLAYING";
                    markPendingToggle("PLAYING");
                    emit("player:clock-reset");
                    emit("player:btn-changed");
                    emit("now-playing:changed");
                    if (typeof wsSend === "function") wsSend("toggle_pause");
                }
            }
        });
    });
}
initAudioPool();

// PATCH-ANDROID-AUDIO-01
globalThis.audioBlocked = false;

export function _showTapToPlayBanner() {
    /** @type {HTMLButtonElement | null} */
    let el = /** @type {HTMLButtonElement | null} */ (document.getElementById('audio-unlock-banner'));
    if (!el) {
        el = document.createElement('button');
        el.id = 'audio-unlock-banner';
        el.type = 'button';
        el.textContent = '\ud83d\udd0a Tap untuk lanjut memutar';
        el.style.cssText = 'position:fixed;left:50%;bottom:90px;transform:translateX(-50%);' +
            'z-index:9999;padding:10px 18px;border-radius:999px;border:none;' +
            'background:var(--accent,#1db954);color:#fff;font-weight:600;font-size:14px;' +
            'box-shadow:0 4px 16px rgba(0,0,0,.35);cursor:pointer;';
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            _hideTapToPlayBanner();
            globalThis.audioUnlocked = true;
            globalThis.audioBlocked = false;

            const audio = getOrInitAudio();
            if (audio && audio.src && !audio.src.startsWith('data:')) {
                _resumeAndPlay(audio);
            } else if (typeof syncBrowserAudio === "function") {
                syncBrowserAudio(true);
            }
        });
        document.body.appendChild(el);
    }
    el.style.display = 'block';
}

export function _hideTapToPlayBanner() {
    const el = document.getElementById('audio-unlock-banner');
    if (el) el.style.display = 'none';
}

export async function _resumeAndPlay(audio) {
    if (audioCtx && audioCtx.state === 'suspended') {
        try { await audioCtx.resume(); } catch (e) { console.warn("[audio] ctx resume failed:", e); }
    }
    try {
        await audio.play();
        console.log("[audio] play() OK");
        globalThis.audioBlocked = false;
        _hideTapToPlayBanner();
        if (typeof startFakeBeatLoop === "function") startFakeBeatLoop();
    } catch (e) {
        console.warn("[audio] play() blocked:", e.name, e.message);
        globalThis.audioBlocked = true;
        _showTapToPlayBanner();
    }
}

document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume().catch(() => { });
        const isBrowser = store && (store.userRole === "client" || store.audio_output === "browser");
        if (isBrowser && store.status === "PLAYING") {
            const audio = getOrInitAudio();
            if (audio.paused && audio.src && !audio.src.startsWith("data:")) {
                _resumeAndPlay(audio);
            }
        }
        if (store.status === "PLAYING") emit("player:clock-start");
        if (typeof resumeVisualizerLoop === "function") resumeVisualizerLoop();
        if (typeof setRadioHeroAnimState === "function" && dom.radioToggleBtn) {
            emit("radio-hero:anim", { on: dom.radioToggleBtn.dataset.on === "true" });
        }
    } else {
        emit("player:clock-stop");
    }
});

export function unlockBrowserAudio(forcePlay) {
    if (audioUnlocked || _unlocking) {
        if (forcePlay && audioUnlocked) syncBrowserAudio(true);
        return;
    }
    _unlocking = true;
    console.log("[audio] unlocking via AudioContext...");

    const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AC) {
        audioUnlocked = true;
        _unlocking = false;
        resetLastLoadedVideoId();
        syncBrowserAudio(forcePlay);
        return;
    }

    const ctx = audioCtx || new AC();

    const doUnlock = () => {
        audioUnlocked = true;
        _unlocking = false;
        console.log("[audio] unlocked, syncing...");
        if (!audioCtx) {
            audioCtx = ctx;
        }
        // PATCH-AUDIO-FIX: _initAnalyser() SENGAJA tidak dipanggil di sini.
        // createMediaElementSource() menyambungkan elemen <audio> pemutar
        // sungguhan ke Web Audio API graph -- begitu itu terjadi, browser
        // membisukan totalnya SECARA DIAM-DIAM (tanpa error) kalau sumber
        // audio dianggap cross-origin/"tainted". Stream kita selalu redirect
        // 302 ke googlevideo.com (server/handlers/audio_stream_handler.py,
        // http_session tidak pernah di-wire ke request.app di app.py), jadi
        // elemen ini SELALU tainted. Efeknya: audio.play() sukses, progress
        // bar jalan, tapi suara nol -- persis bug "audio browser gak muncul
        // sama sekali" pasca refactor. initVisualizer() di bawah otomatis
        // fallback ke startFakeBeatLoop() selama analyser null (lihat
        // visualizer.js), jadi efek visual glow tetap sama seperti 1.5.2.
        if (typeof initVisualizer === "function") initVisualizer();
        resetLastLoadedVideoId();
        syncBrowserAudio(forcePlay);
    };

    if (ctx.state === 'suspended') {
        ctx.resume().then(doUnlock).catch((e) => {
            console.warn("[audio] AudioContext resume failed:", e);
            _unlocking = false;
            audioUnlocked = true;
            resetLastLoadedVideoId();
            syncBrowserAudio(forcePlay);
        });
    } else {
        doUnlock();
    }
}

export function _fadeVolume(audio, targetVolume, durationSec, callback) {
    const steps = 15;
    const intervalMs = (durationSec * 1000) / steps;
    const initialVol = audio.volume;
    const volStep = (targetVolume - initialVol) / steps;
    let stepCount = 0;

    const idx = audioPool.indexOf(audio);
    if (idx !== -1) {
        if (_fadeIntervals[idx]) clearInterval(_fadeIntervals[idx]);
        _fadeIntervals[idx] = setInterval(() => {
            stepCount++;
            let newVol = initialVol + (volStep * stepCount);
            if (newVol < 0) newVol = 0;
            if (newVol > 1) newVol = 1;
            audio.volume = newVol;
            if (stepCount >= steps) {
                clearInterval(_fadeIntervals[idx]);
                _fadeIntervals[idx] = null;
                if (callback) callback();
            }
        }, intervalMs);
    }
}
