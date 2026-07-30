import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";
import {
    audioPool,
    getOrInitAudio,
    unlockBrowserAudio,
    _resumeAndPlay,
    analyser,
    dataArray,
    _fadeVolume,
    _hideTapToPlayBanner,
    _showTapToPlayBanner,
    audioUnlocked
} from "./audio-pool.js";
import { updateMediaSession } from "./media-session.js";

export { getOrInitAudio, unlockBrowserAudio, _resumeAndPlay, analyser, dataArray };
export { updateMediaSession };

const CROSSFADE_DURATION = 5.0; // Edit durasi crossfade di sini (dalam detik)

export let activeAudioIndex = 0;
export let _fadeIntervals = [null, null];
export let _lastLoadedVideoId = null;

export function resetLastLoadedVideoId() {
    _lastLoadedVideoId = null;
}

export function syncBrowserAudio(forcePlay) {
    const isBrowser = store.userRole === "client" || store.audio_output === "browser";

    if (!isBrowser) {
        audioPool.forEach(a => { if (!a.paused) a.pause(); });
        return;
    }

    const track = store.current_track;
    if (!track) {
        audioPool.forEach(a => {
            if (!a.paused) a.pause();
            if (a.hasAttribute("src") && a.src && !a.src.startsWith("data:")) {
                a.removeAttribute("src");
                a.load();
            }
        });
        _lastLoadedVideoId = null;
        return;
    }

    const expectedSrc = globalThis.location.origin + `/api/stream/${track.video_id}`;

    if (_lastLoadedVideoId !== track.video_id) {
        _lastLoadedVideoId = track.video_id;
        globalThis.audioBlocked = false;
        if (typeof _hideTapToPlayBanner === "function") _hideTapToPlayBanner();

        // Switch active audio element
        const prevAudio = audioPool[activeAudioIndex];
        activeAudioIndex = (activeAudioIndex + 1) % 2;
        const audio = audioPool[activeAudioIndex];

        // Crossfade out previous audio if enabled and playing
        if (store.crossfade_enabled && !prevAudio.paused && prevAudio.src && !prevAudio.src.startsWith("data:")) {
            console.log("[audio] crossfade out previous track");
            _fadeVolume(prevAudio, 0, CROSSFADE_DURATION, () => {
                // Cegah OS Android/Chrome mem-pause Media Session secara native
                globalThis._mediaSessionHandling = true;
                prevAudio.pause();
                prevAudio.removeAttribute("src");
                prevAudio.load();

                // Workaround: Jika Chrome Android secara agresif mem-pause activeAudio
                setTimeout(() => {
                    const activeAudio = audioPool[activeAudioIndex];
                    if (store.status === "PLAYING" && activeAudio.paused) {
                        console.log("[audio] Workaround: Resuming active audio paused by OS during crossfade");
                        activeAudio.play().catch(()=>{});
                    }
                    globalThis._mediaSessionHandling = false;
                }, 300);
            });
        } else {
            prevAudio.pause();
            prevAudio.removeAttribute("src");
            prevAudio.load();
        }

        audio.src = expectedSrc;

        let _crossfadeTriggered = false;

        audio.ontimeupdate = () => {
            if (store.crossfade_enabled && audio.duration > 0) {
                const remaining = audio.duration - audio.currentTime;
                if (remaining <= CROSSFADE_DURATION && remaining > 0 && !_crossfadeTriggered) {
                    _crossfadeTriggered = true;
                    console.log("[audio] crossfade overlap triggered");
                    if (store.audio_output === "browser") {
                        wsSend("next", { video_id: track.video_id });
                    }
                }
            }
        };

        audio.onended = () => {
            if (!_crossfadeTriggered || !store.crossfade_enabled) {
                console.log("[radio] track ended, requesting next...");
                if (store.audio_output === "browser") {
                    wsSend("next", { video_id: track.video_id });
                }
            }
        };

        if (!audioUnlocked) {
            audio.oncanplay = null;
            audio.load();
            console.log("[audio] buffering, waiting for user gesture:", track.video_id);
            if (forcePlay || store.status === "PLAYING") {
                globalThis.audioBlocked = true;
                _showTapToPlayBanner();
            }
            return;
        }

        audio.oncanplay = () => {
            audio.oncanplay = null;
            // Hanya seek jika posisi memang untuk lagu ini bukan sisa posisi lagu sebelumnya
            const isResume = store.position > 5 &&
                store.current_track &&
                store.current_track.video_id === track.video_id;
            if (isResume && Math.abs(audio.currentTime - store.position) > 5) {
                audio.currentTime = store.position;
            }
            if (forcePlay || store.status === "PLAYING") {
                console.log("[audio] canplay → play:", track.video_id);
                if (store.crossfade_enabled && !isResume) {
                    audio.volume = 0;
                    _resumeAndPlay(audio);
                    const targetVol = Math.max(0, Math.min(1, (store.volume || 80) / 100));
                    _fadeVolume(audio, targetVol, CROSSFADE_DURATION);
                } else {
                    if (!globalThis.isDraggingVol) {
                        audio.volume = Math.max(0, Math.min(1, (store.volume || 80) / 100));
                    }
                    _resumeAndPlay(audio);
                }
            }
        };
        audio.load();
        return;
    }

    const audio = getOrInitAudio();
    if (!globalThis.isDraggingVol && !_fadeIntervals[activeAudioIndex]) {
        audio.volume = Math.max(0, Math.min(1, (store.volume || 80) / 100));
    }
    if (forcePlay || store.status === "PLAYING") {
        if (audio.paused && audio.src && !audio.src.startsWith("data:") && audioUnlocked) {
            _resumeAndPlay(audio);
        }
    } else {
        audioPool.forEach((a, i) => {
            if (!a.paused) a.pause();
            if (_fadeIntervals[i]) {
                clearInterval(_fadeIntervals[i]);
                _fadeIntervals[i] = null;
            }
        });
    }
}

export function initAudio() {
    document.addEventListener("click", unlockBrowserAudio);
}
