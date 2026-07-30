import { appendLogBatch, navigateToLiveTail, formatFields } from "./log-tail.js";
import { fetchStats } from "./dashboard-stats.js";
import { connectWs, fallbackToPolling, fetchTail, fetchHealth, sendOverWs, disconnectWs, setAppendLogBatch } from "/framework/static/js/core/transport.js";
import { handleIncomingChat, renderChatHistory, openChatPanel } from "./admin-chat-panel.js";

setAppendLogBatch(appendLogBatch);

const btnFilter = document.getElementById('btnFilter');
const btnClearFilter = document.getElementById('btnClearFilter');
const btnDownload = /** @type {HTMLButtonElement} */ (document.getElementById('btnDownload'));
const filterLevel = /** @type {HTMLSelectElement} */ (document.getElementById('filterLevel'));
const filterCategory = /** @type {HTMLSelectElement} */ (document.getElementById('filterCategory'));
const filterSearch = /** @type {HTMLInputElement} */ (document.getElementById('filterSearch'));
export function switchTab(name, pushHash = true) {
    document.querySelectorAll('.tab-btn, .bottom-tab-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === name));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + name));
    if (pushHash) history.replaceState(null, '', '#' + name);
}

document.querySelectorAll('.tab-btn, .bottom-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.getAttribute('data-tab')));
});

// Deep link initialization
const initial = (location.hash || '#ringkasan').slice(1);
if (document.getElementById('tab-' + initial)) {
    switchTab(initial, false);
}
// Add keyframes for the pulse animation if not exists
if (!document.getElementById('pulse-anim')) {
    const style = document.createElement('style');
    style.id = 'pulse-anim';
    style.innerHTML = `
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

function handleWsMessage(data) {
    if (data.type === "auth_status") {
        if (data.data && data.data.success) {
            sendOverWs({ type: "cmd", action: "log_tail", data: { action: "subscribe" } });
        } else {
            fallbackToPolling();
        }
    } else if (data.type === "error" && data.data && data.data.includes("Akses ditolak")) {
        fallbackToPolling();
    } else if (data.type === "log_batch" && data.logs) {
                const level = filterLevel.value;
                const category = filterCategory.value;
                const q = filterSearch.value.toLowerCase();

                const filtered = data.logs.filter(log => {
                    if (level && log.level !== level) return false;
                    if (category && (!log.fields || log.fields.category !== category)) return false;
                    if (q && !(log.event.toLowerCase().includes(q) || (log.fields && Object.values(log.fields).join(' ').toLowerCase().includes(q)))) return false;
                    return true;
                });

                if (filtered.length > 0) {
                    appendLogBatch(filtered, false);
                }
    } else if (data.type === "chat_message") {
        handleIncomingChat(data.data);
    } else if (data.type === "chat_history") {
        renderChatHistory(data.data);
    }
}

/** @type {any} */ (window).navigateToLiveTail = navigateToLiveTail;

btnFilter.addEventListener('click', () => {
    fetchTail(true);
});

if (btnClearFilter) {
    btnClearFilter.addEventListener('click', () => {
        filterLevel.value = '';
        filterCategory.value = '';
        filterSearch.value = '';
        fetchTail(true);
    });
}

btnDownload.addEventListener('click', async () => {
    btnDownload.disabled = true;
    btnDownload.textContent = "Mengunduh...";

    try {
        const token = localStorage.getItem('metricsToken') || '';
        const headers = token ? {'X-Metrics-Token': token} : {};
        const res = await fetch(`/api/logs/tail?limit=5000`, { headers });
        if (!res.ok) throw new Error('Failed to fetch logs for download');

        const data = await res.json();
        let textData = "";

        if (data.logs) {
            for (const log of data.logs) {
                if (log.level === "BANNER") {
                    textData += `${log.event}\n`;
                } else {
                    const extra = formatFields(log.fields);
                    textData += `[${log.time}] ${log.level}: ${log.event}${extra ? ' ' + extra : ''}\n`;
                }
            }
        }

        const blob = new Blob([textData], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `lunawave_logs_${new Date().getTime()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        alert("Gagal mengunduh log: " + e.message);
    } finally {
        btnDownload.disabled = false;
        btnDownload.textContent = "Unduh lunawave.log";
    }
});

window.addEventListener('beforeunload', () => {
    disconnectWs();
});

// Global Events
document.addEventListener('chat:open', /** @param {any} e */ (e) => {
    openChatPanel(e.detail.uid, e.detail.ip);
});

// Init
fetchHealth();
fetchStats();
fetchTail(true);
connectWs(handleWsMessage);
setInterval(fetchHealth, 5000);
setInterval(fetchStats, 10000);

// PATCH-2026-07-24-224: file ini sudah dimuat lewat
// <script type="module" src="...">` di admin-logs.html, jadi ini tidak
// mengubah perilaku runtime apapun -- murni penanda modul untuk tsc supaya
// `ws` di file ini (WebSocket log-tail lokal) tidak dianggap redeclare
// terhadap `declare var ws` global di shared/js/global.d.ts (WebSocket app
// utama, konsep berbeda sama sekali).
export {};
