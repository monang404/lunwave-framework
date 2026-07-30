import { getOrInitAudio, initAudio, syncBrowserAudio, unlockBrowserAudio } from "../../shared/js/audio/playback-sync.js";
import { initDOM } from "../../shared/js/dom.js";
import { renderLyrics } from "../../shared/js/render/lyrics.js";
import { renderNowPlaying, syncPlayerStateAttr } from "../../shared/js/render/now-playing.js";
import { store } from "/framework/static/js/core/store.js";
import { formatTime } from "../../shared/js/utils/format.js";

// client.js
store.userRole = "client";

// Client mode NEVER sends commands to the server. Ini cuma jaring pengaman
// tambahan di frontend -- boundary keamanan yang sebenarnya ada di backend
// (server/handlers/websocket.py::handle_ws_message mewajibkan require_auth()
// untuk semua action selain auth/logout/setup_admin, dan halaman ini tidak
// pernah mengirim action "auth"). wsSend tetap harus ada di sini karena
// playback-sync.js (dipakai bersama dengan halaman admin) memanggilnya di
// beberapa titik (mis. saat lagu selesai / crossfade), dan tanpa fungsi ini
// terdefinisi, pemanggilan tsb akan throw ReferenceError yang menghentikan
// eksekusi kode setelahnya (termasuk sinkronisasi audio & lirik).
// Identitas chat per-browser, DI-GENERATE sistem (bukan diketik user) dan
// TIDAK bergantung ke IP request.remote -- lihat PATCH client_uid chat.
// request.remote rusak sebagai kunci segmentasi begitu server diakses lewat
// reverse proxy (Nginx/Cloudflare Tunnel/ngrok, semua direkomendasikan di
// README) karena semua client eksternal akan terlihat sebagai satu IP yang
// sama (IP si proxy) -- chat history antar user yang berbeda bisa bocor
// saling ketuker. client_uid disimpan sekali di localStorage per browser,
// dikirim di setiap command chat, dan itu yang jadi kunci identitas asli.
function getClientUid() {
    const KEY = "lunawave_chat_client_uid";
    let uid = window.safeStorage ? window.safeStorage.get(KEY) : localStorage.getItem(KEY);
    if (!uid) {
        uid = (crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2)));
        if (window.safeStorage) window.safeStorage.set(KEY, uid);
        else localStorage.setItem(KEY, uid);
    }
    return uid;
}

function wsSend(action, data) {
    // Hanya izinkan command chat untuk client mode (Client tidak bisa kontrol playback)
    if (action === "send_chat" || action === "get_chat_history") {
        const payload = Object.assign({ client_uid: getClientUid() }, data || {});
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
            window.ws.send(JSON.stringify({ type: "cmd", action, data: payload }));
        }
    }
}

// Function yang sama persis dengan yang ada di ws.js, untuk memastikan
// sinkronisasi highlight lirik lokal berjalan mulus di antara jeda interval dari server
function syncLocalLyrics() {
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
            if (typeof renderLyrics === "function") renderLyrics();
        }
    }
}

// showLogToast asli (di render/toast.js) menyentuh dom.logToast, yang tidak
// ada di client.html. Override jadi console.log supaya playback-sync.js
// (mis. saat ada error stream audio) tidak throw saat memanggilnya.
// eslint-disable-next-line no-unused-vars -- dimaksudkan sebagai override shadow untuk global showLogToast (lihat komentar di atas), TAPI belum pernah benar-benar di-assign ke window.showLogToast di file ini. Dibiarkan sesuai scope mekanis eslint-cleanup; TIDAK diperbaiki wiring-nya di sini karena itu perubahan behavior. Lihat Notes PATCHLOG task S2.2.
function showLogToast(msg) {
    console.log("Toast:", msg);
}

// getCoverArt & cleanTrackTitle TIDAK didefinisikan ulang di sini -- reuse
// versi asli dari utils/cover-art.js (dimuat sebelum file ini di client.html).
// Sebelumnya file ini punya reimplementasi sendiri yang fallback ke
// `/api/thumbnail/{video_id}`, padahal route itu tidak pernah didaftarkan
// di server/app.py -- selalu 404, cover art gagal tampil untuk track yang
// field `thumbnail`-nya bukan URL http penuh.

function updateWSStatus(isOnline) {
    const el = document.getElementById("client-ws-status");
    if (!el) return;
    if (isOnline) {
        el.innerHTML = '<i class="ti ti-wifi"></i> Online';
        el.style.color = 'var(--text-1)';
    } else {
        el.innerHTML = '<i class="ti ti-wifi-off"></i> Offline';
        el.style.color = 'var(--red)';
    }
}

// Server broadcast 3 jenis pesan terpisah lewat /ws (lihat
// server/broadcast_service.py & server/handlers/event_listeners.py):
//   - "state"    : snapshot penuh saat connect, ganti track, atau queue update
//   - "progress" : tick posisi ~1x/detik DAN setiap toggle play/pause
//                  (TrackPauseChangedEvent juga lewat broadcast_progress,
//                  bukan broadcast_state!)
//   - "lyrics"   : index baris lirik berjalan (LyricsUpdatedEvent)
// Versi sebelumnya cuma menangani "state", jadi progress bar & play/pause
// dari Admin tidak pernah ter-update live (cuma ikut waktu reconnect bawa
// snapshot baru), dan lirik beku di baris pertama sejak connect.
function handleServerMessage(data) {
    switch (data.type) {
        case "state":
            Object.assign(store, data.data);
            if (typeof renderNowPlaying === 'function') renderNowPlaying();
            if (typeof renderLyrics === 'function') renderLyrics();
            if (typeof syncBrowserAudio === 'function') syncBrowserAudio();
            break;

        case "progress": {
            const statusChanged = store.status !== data.data.status;
            store.status = data.data.status;
            if (data.data.server_ts) store.server_ts = data.data.server_ts;

            // <audio> browser adalah pemutar sebenarnya di client mode. Kalau
            // dia sudah aktif & jalan, posisi darinya lebih akurat daripada
            // posisi mpv di server (2 jalur stream independen, lihat catatan
            // FIX-POSITION-DRIFT-02 di ws.js) -- jangan ditimpa. Kalau belum
            // aktif (mis. belum di-unlock user / masih loading), pakai
            // posisi server supaya progress bar tidak diam di 0:00.
            const audioEl = typeof getOrInitAudio === 'function' ? getOrInitAudio() : null;
            const audioActive = !!(audioEl && !audioEl.paused && audioEl.src && !audioEl.src.startsWith("data:"));
            if (!audioActive) {
                store.position = data.data.position;
            }

            if (typeof syncPlayerStateAttr === 'function') syncPlayerStateAttr();
            if (statusChanged && typeof renderNowPlaying === 'function') renderNowPlaying();
            // Dipanggil tiap tick (bukan cuma saat statusChanged): kalau audio
            // browser sempat berhenti sendiri (mis. tab di-throttle di
            // background) padahal status di server masih PLAYING, ini yang
            // akan coba resume-kan lagi tanpa perlu refresh manual.
            if (typeof syncBrowserAudio === 'function') syncBrowserAudio();
            break;
        }

        case "lyrics":
            store.lyrics_lines = data.data.lyrics_lines || [];
            store.lyrics_timestamps = data.data.lyrics_timestamps || [];
            store.lyrics_index = data.data.lyrics_index || 0;
            store.lyrics_offset = data.data.lyrics_offset || 0;
            if (typeof renderLyrics === 'function') renderLyrics();
            break;

        case "chat_history":
            if (window.ChatModule) window.ChatModule.onHistory(data.data);
            break;

        case "chat_message":
            if (window.ChatModule) window.ChatModule.onNewMessage(data.data);
            break;

        default:
            break;
    }
}

function connectWS() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = protocol + "//" + window.location.host + "/ws?page=" + encodeURIComponent(window.location.pathname);
    window.ws = new WebSocket(wsUrl);

    window.ws.onopen = () => {
        updateWSStatus(true);
        // Fetch history on connect
        wsSend("get_chat_history");
    };

    window.ws.onmessage = (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error("Error parsing WS message:", e);
            return;
        }
        // Dipisah dari try/catch parse JSON di atas: kalau sebelumnya
        // handleServerMessage() (dulu handleStateMessage()) throw karena bug
        // di renderer, errornya tertelan diam-diam dengan label yang
        // menyesatkan ("Error parsing WS message"), padahal JSON-nya valid.
        // Ini yang bikin bug home-idle-view/progress/lyrics kemarin nyaris
        // tidak kelihatan di console.
        try {
            handleServerMessage(data);
        } catch (e) {
            console.error("Error handling WS message:", data && data.type, e);
        }
    };

    window.ws.onclose = () => {
        updateWSStatus(false);
        setTimeout(connectWS, 3000);
    };

    window.ws.onerror = () => {
        updateWSStatus(false);
    };
}

// Progress loop for smooth UI rendering (since player.js is not loaded in client.html)
setInterval(() => {
    const posEl = document.getElementById("pb-time-pos");
    const durEl = document.getElementById("pb-time-dur");
    const fillEl = document.getElementById("pb-progress-fill");

    // store.position di-update oleh event "progress"/"state" dari WS, dan
    // (saat audio browser aktif main) oleh event timeupdate di playback-sync.js
    if (posEl && typeof formatTime === 'function') posEl.textContent = formatTime(store.position || 0);
    if (store.current_track && store.current_track.duration) {
        if (durEl && typeof formatTime === 'function') durEl.textContent = formatTime(store.current_track.duration);
        if (fillEl) {
            const pct = Math.min(100, Math.max(0, ((store.position || 0) / store.current_track.duration) * 100));
            fillEl.style.width = pct + "%";
        }
    }

    // Sync local lyrics highlight (no-op kalau ws.js tidak dimuat -- aman,
    // sudah di-guard typeof check)
    if (typeof syncLocalLyrics === 'function') syncLocalLyrics();
}, 200);

function hideAudioCta() {
    const el = document.getElementById('client-audio-cta');
    if (el) el.remove();
}

document.addEventListener("DOMContentLoaded", () => {
    if (typeof initDOM === 'function') initDOM();
    if (typeof initAudio === 'function') initAudio();
    updateWSStatus(false);
    connectWS();

    // Halaman client sengaja tanpa tombol kontrol apa pun, jadi tidak ada
    // interaksi UI yang "gratis" memicu unlock audio browser (beda dengan
    // halaman Admin, di mana klik tombol play/pause dsb sekalian jadi user
    // gesture untuk itu). Tanpa CTA eksplisit ini, unlockBrowserAudio() di
    // playback-sync.js tidak akan pernah terpanggil sampai user tanpa
    // sengaja tap layar -- hasilnya: tidak ada suara, dan banner "tap to
    // play" bawaan juga tidak akan muncul (banner itu cuma muncul SETELAH
    // audio.play() dicoba lalu diblokir, dan percobaan itu sendiri butuh
    // unlock terlebih dulu).
    const ctaBtn = document.getElementById('client-audio-cta');
    if (ctaBtn) {
        ctaBtn.addEventListener('click', () => {
            hideAudioCta();
            if (typeof unlockBrowserAudio === 'function') unlockBrowserAudio(true);
        });
    }
    // Tap di mana pun di halaman juga menghilangkan CTA ini (konsisten
    // dengan listener klik global di playback-sync.js::initAudio() yang
    // sama-sama memakai klik pertama sebagai user gesture).
    document.addEventListener('click', hideAudioCta, { once: true });
});
