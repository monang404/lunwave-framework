// bus.js -- pub/sub minimal untuk memutus circular dependency
// antara modul "bawah" (audio, ws) dan modul render.
// Lihat docs/rfc/pemulihan_frontend/proposal_event_bus_frontend.md §3.1
const listeners = new Map();

export function on(event, handler) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(handler);
}

export function off(event, handler) {
    listeners.get(event)?.delete(handler);
}

export function emit(event, payload) {
    listeners.get(event)?.forEach((handler) => {
        try {
            handler(payload);
        } catch (e) {
            console.error(`[bus] handler untuk "${event}" gagal:`, e);
        }
    });
}
