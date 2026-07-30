import { routeMessage } from "./router.js";
import { renderHeader } from "/static/shared/js/ws/message-handlers/auth-messages.js";
import { emit as bus } from "/static/shared/js/bus.js";
import { store } from "./store.js";

export let ws = null;
let wsReconnectTimer = null;
let wsTokenRefreshTimer = null;
let wsReconnectDelay = 2000;
const WS_RECONNECT_MAX_DELAY = 30000;

export function wsConnect() {
    const protocol = globalThis.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = protocol + "//" + globalThis.location.host + "/ws?page=" + encodeURIComponent(globalThis.location.pathname);

    bus("toast:connection-show", { text: "Menghubungkan...", type: "connecting" });

    // Tutup koneksi lama jika masih ada (BUG-003: mencegah concurrent connections)
    if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
    }

    ws = new WebSocket(wsUrl);
    globalThis.ws = ws;

    ws.onopen = () => {
        store.is_online = true;
        bus("toast:connection-hide");
        wsReconnectDelay = 2000;
        if (wsReconnectTimer) {
            clearTimeout(wsReconnectTimer);
            wsReconnectTimer = null;
        }

        if (store.userRole === "admin") {
            const token = globalThis.safeStorage.get("lunawave_session_token");
            if (token) {
                wsSend("auth", { token: token });
            }
            const savedOutput = globalThis.safeStorage.get("lunawave_audio_output") || "browser";
            wsSend("set_output", { output: savedOutput });
        } else if (store.userRole === "client") {
            if (store.active_tab === "home" || store.active_tab === "discover") {
                wsSend("discover");
            }
        }

        // Fetch chat history
        wsSend("get_chat_history");

        if (wsTokenRefreshTimer) clearInterval(wsTokenRefreshTimer);
        wsTokenRefreshTimer = setInterval(() => {
            if (store.userRole === "admin" && store.is_online) {
                const token = globalThis.safeStorage.get("lunawave_session_token");
                if (token) wsSend("auth", { token: token });
            }
        }, 3600000);

        renderHeader();
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            routeMessage(msg);
        } catch (e) {
            console.error("WS parse error:", e);
        }
    };

    ws.onclose = () => {
        if (wsTokenRefreshTimer) {
            clearInterval(wsTokenRefreshTimer);
            wsTokenRefreshTimer = null;
        }
        store.is_online = false;
        renderHeader();
        bus("toast:connection-show", { text: "Koneksi terputus. Reconnecting...", type: "disconnected" });
        wsReconnectTimer = setTimeout(wsConnect, wsReconnectDelay);
        wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_RECONNECT_MAX_DELAY);
    };

    ws.onerror = () => {
        ws.close();
    };
}

// Listener visibilitychange TERPISAH khusus reconnect (PD-4) — scope-nya
// beda dari titik kontrol rAF di playback-sync.js (PERF-3): begitu tab
// kembali visible saat ada reconnect timer pending, langsung coba connect
// tanpa menunggu sisa delay backoff. Sebaliknya, saat tab hidden, timer
// yang sudah capped di 30s dibiarkan jalan seperti biasa (tidak perlu
// dipause total).
if (typeof document !== "undefined") {
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && wsReconnectTimer) {
            clearTimeout(wsReconnectTimer);
            wsReconnectTimer = null;
            wsReconnectDelay = 2000;
            wsConnect();
        }
    });
}

export function wsSend(action, data) {
    // FIX-PAUSE-RACE-01 (edge case ditemukan setelah patch awal): kalau ada
    // pendingToggleTarget yang belum dikonfirmasi server (user pause lalu SEBELUM
    // konfirmasi datang langsung next/prev/pilih track lain), status track yang
    // baru (LOADING -> PLAYING) akan salah dianggap "kontradiktif" dengan target
    // basi itu dan ditolak oleh handler "progress" -> UI kelihatan macet di
    // LOADING sampai safety-valve 8 detik habis. Command-command ini mengganti
    // track sepenuhnya, jadi toggle play/pause yang lama sudah tidak relevan --
    // clear di sini (satu titik, berlaku utk semua caller: tombol next/prev,
    // keyboard shortcut, klik track di search/queue, Media Session action).
    // queue_select (klik track di panel Queue) juga termasuk karena sama-sama
    // mengganti track sepenuhnya, sama seperti next/prev/play_track.
    if (action === "next" || action === "prev" || action === "play_track" || action === "queue_select") {
        store._pendingToggleTarget = null;
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "cmd", action, data: data || {} }));
    }
}
