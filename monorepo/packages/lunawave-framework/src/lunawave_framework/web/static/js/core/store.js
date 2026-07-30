
export function createStore() {
    return {
        status: "IDLE",
        playback_mode: "QUEUE",
        audio_output: "browser",
        userRole: "portal", // "portal" | "client" | "admin"
        adminUsername: "",
        adminPassword: "",
        current_track: null,
        position: 0,
        volume: 80,
        playback_speed: 1.0,
        loop_mode: "off",
        crossfade_enabled: false,
        loudness_normalization_enabled: false,
        sponsorblock_active: false,
        queue: [],
        radio_queue: [],
        history_count: 0,
        lyrics_lines: [],
        lyrics_index: 0,
        lyrics_offset: 0,
        active_tab: "home",
        error_msg: null,
        is_online: true,
        download_progress: null,
        discover_recent: [],
        discover_favorites: [],
        discover_cached: [],
        discover_for_you: [],
        discover_unheard: [],
        discover_genre_affinity_genre: null,
        discover_genre_affinity_artists: [],
        discover_taste_spectrum: [],
        search_results: [],
        server_ts: 0,
        _pendingToggleTarget: null,
        _toggleSentAt: 0
    };
}

const listeners = new Map();
const wildcardListeners = new Set();

function notify(key, value, oldValue) {
    if (listeners.has(key)) {
        for (const callback of listeners.get(key)) {
            callback(value, oldValue);
        }
    }
    for (const callback of wildcardListeners) {
        callback(key, value, oldValue);
    }
}

function createReactiveStore(initial) {
    return new Proxy(initial, {
        set(target, key, value) {
            const oldValue = target[key];
            if (oldValue === value) {
                return true;
            }
            target[key] = value;
            notify(key, value, oldValue);
            return true;
        }
    });
}

export const store = createReactiveStore(createStore());

export function onStoreChange(key, callback) {
    if (!listeners.has(key)) {
        listeners.set(key, new Set());
    }
    listeners.get(key).add(callback);
    return () => listeners.get(key).delete(callback);
}

export function onAnyStoreChange(callback) {
    wildcardListeners.add(callback);
    return () => wildcardListeners.delete(callback);
}

// FIX-PAUSE-RACE-01: sebelumnya ws.js dan playback-sync.js masing-masing pakai
// globalThis.lastToggleTime dengan grace-window waktu TETAP yang beda (1200ms di
// ws.js, 1500ms di playback-sync.js) buat nolak update status dari server yang
// datang telat setelah user toggle play/pause. Dua angka beda untuk konsep yang
// sama itu sendiri sudah jadi celah, dan begitu RTT jaringan lebih lama dari
// grace-window-nya (jaringan jelek), progress message basi yang masih bawa
// status LAMA tetap ditelan mentah-mentah -> menimpa balik status yang baru saja
// di-set user -> audio ikut kebalik (lihat FIX-RADIO-08 di ws.js). Solusinya:
// lacak status APA yang sedang ditunggu konfirmasinya (pendingToggleTarget),
// bukan cuma "berapa lama sejak klik". Update dari server yang KONTRADIKTIF
// dengan target itu ditolak selama masih menunggu -- bukan berdasar timer statis
// yang gampang jebol di jaringan lambat.
export const PENDING_TOGGLE_TIMEOUT_MS = 8000; // safety-valve: cegah macet permanen kalau command toggle kita sendiri hilang di jalan

export function markPendingToggle(target) {
    store._pendingToggleTarget = target;
    store._toggleSentAt = Date.now();
}

// matchStatus: status yang mau dicek apakah masih "ditunggu konfirmasinya".
// Return true kalau kita masih dalam masa tunggu utk toggle ke status itu (grace aktif).
export function isPendingToggleActive(matchStatus) {
    if (!store._pendingToggleTarget) return false;
    if (Date.now() - (store._toggleSentAt || 0) > PENDING_TOGGLE_TIMEOUT_MS) {
        store._pendingToggleTarget = null; // safety-valve: anggap command kita hilang, jangan tunggu selamanya
        return false;
    }
    return store._pendingToggleTarget === matchStatus;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { createStore, store, markPendingToggle, isPendingToggleActive, PENDING_TOGGLE_TIMEOUT_MS, onStoreChange, onAnyStoreChange };
}
