let ws = null;
let appendLogBatchCallback = null;
export function setAppendLogBatch(cb) { appendLogBatchCallback = cb; }
let isPolling = false;
let pollTimer = null;

const connBanner = document.getElementById('connBanner');
const filterLevel = /** @type {HTMLSelectElement} */ (document.getElementById('filterLevel'));
const filterCategory = /** @type {HTMLSelectElement} */ (document.getElementById('filterCategory'));
const filterSearch = /** @type {HTMLInputElement} */ (document.getElementById('filterSearch'));

export async function fetchTail(clearFirst = false) {
    try {
        const limit = 200;
        const level = filterLevel.value;
        const category = filterCategory.value;
        const q = filterSearch.value;

        const params = new URLSearchParams();
        params.append('limit', String(limit));
        if (level) params.append('level', level);
        if (category) params.append('category', category);
        if (q) params.append('q', q);

        const token = localStorage.getItem('metricsToken') || '';
        const headers = token ? {'X-Metrics-Token': token} : {};

        const res = await fetch(`/api/logs/tail?${params.toString()}`, { headers });
        if (!res.ok) {
            if (res.status === 403) {
                // Try to prompt for token
                const promptToken = prompt("Metrics token required (localhost bypassing failed):");
                if (promptToken) {
                    localStorage.setItem('metricsToken', promptToken);
                    return fetchTail(clearFirst);
                }
            }
            throw new Error('Failed to fetch tail');
        }

        const data = await res.json();
        if (data.logs) {
            if (appendLogBatchCallback) appendLogBatchCallback(data.logs, clearFirst);
        }
    } catch (e) {
        console.error("Tail fetch error:", e);
    }
}
export async function fetchHealth() {
    try {
        const res = await fetch('/health');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('ind-db').className = 'status-indicator ' + (data.db === 'connected' ? 'ok' : 'error');
            document.getElementById('ind-mpv').className = 'status-indicator ' + (data.mpv === 'connected' ? 'ok' : 'warn');
            document.getElementById('val-uptime').textContent = `Uptime: ${data.uptime_seconds || 0}s`;
            document.getElementById('val-mem').textContent = `Mem: ${data.memory_mb || 0}MB`;
            document.getElementById('val-conn').textContent = `WS: ${data.active_connections || 0}`;
        }
    } catch (e) {
        console.error("Health fetch error:", e);
    }
}
export function fallbackToPolling() {
    if (!isPolling) {
        isPolling = true;
        connBanner.style.display = 'block';
        connBanner.textContent = 'Live tail via WS tidak tersedia (butuh admin login). Beralih ke mode polling.';
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(() => fetchTail(false), 2000);
    }
}
export function connectWs(onMessage) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${window.location.host}/ws?page=${encodeURIComponent(window.location.pathname)}`);

    ws.onopen = () => {
        connBanner.style.display = 'none';
        isPolling = false;
        if (pollTimer) clearInterval(pollTimer);

        const adminToken = localStorage.getItem('lunawave_session_token');
        if (adminToken) {
            ws.send(JSON.stringify({
                type: "cmd",
                action: "auth",
                data: { token: adminToken }
            }));
        } else {
            // No admin token, WS log_tail will likely be rejected.
            // Try anyway, it will trigger error fallback.
            ws.send(JSON.stringify({
                type: "cmd",
                action: "log_tail",
                data: { action: "subscribe" }
            }));
        }
    };

    ws.onmessage = (evt) => {
        try {
            const data = JSON.parse(evt.data);
            onMessage(data);
        } catch (e) {
            console.error("WS parse error:", e);
        }
    };

    ws.onclose = () => {
        ws = null;
        fallbackToPolling();
    };
}

export function sendOverWs(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
    }
}
export function disconnectWs() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "cmd", action: "log_tail", data: { action: "unsubscribe" } }));
        ws.close();
    }
}
