/**
 * log-tail.js
 * Domain: append/render baris log individual + navigasi filter dari matrix cell
 */
import { fetchTail } from "/framework/static/js/core/transport.js";

const logContainer = document.getElementById('logContainer');
const autoScrollCheckbox = /** @type {HTMLInputElement} */ (document.getElementById('autoScrollCheckbox'));
const grpToggle = /** @type {HTMLInputElement} */ (document.getElementById('grpToggle'));
const filterLevel = /** @type {HTMLSelectElement} */ (document.getElementById('filterLevel'));
const filterCategory = /** @type {HTMLSelectElement} */ (document.getElementById('filterCategory'));

let currentLogs = [];
let isGrouped = grpToggle ? grpToggle.checked : true;

if (grpToggle) {
    grpToggle.addEventListener('change', () => {
        isGrouped = grpToggle.checked;
        renderLogs();
    });
}

export function navigateToLiveTail(cat, level) {
    /** @type {HTMLElement} */
    (document.querySelector('.tab-btn[data-tab="log"]')).click();
    filterCategory.value = cat;
    filterLevel.value = level;
    fetchTail(true);
}

export function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

export function formatFields(fields) {
    if (!fields || Object.keys(fields).length === 0) return "";
    const parts = [];
    for (const [k, v] of Object.entries(fields)) {
        if (k !== "category") {
            parts.push(`${k}=${v}`);
        }
    }
    if (parts.length === 0) return "";
    return `(${escapeHtml(parts.join(", "))})`;
}

function metaHtml(l) {
    const parts = [];
    if (l.status !== undefined) parts.push(`<span class="${l.status < 400 ? 'ok' : 'err'}">${l.status}</span>`);
    if (l.dur !== undefined) parts.push(`${l.dur}`);
    if (l.req) parts.push(`req=${l.req}`);
    if (l.video_id) parts.push(`video=${l.video_id}`);
    if (l.uid) parts.push(`uid=${l.uid}`);
    if (l.ip) parts.push(`ip=${l.ip}`);

    // Fallback to remaining fields
    if (l.fields) {
        for (const [k, v] of Object.entries(l.fields)) {
            if (!['category', 'component', 'status', 'duration', 'req_id', 'video_id', 'uid', 'ip'].includes(k)) {
                parts.push(`${k}=${v}`);
            }
        }
    }
    return parts.join('  ·  ');
}

function processLogFields(log) {
    const l = { ...log, cat: 'unknown', comp: '', evt: log.event || '', fields: log.fields || {} };
    if (log.fields) {
        if (log.fields.category) {
            l.cat = log.fields.category.replace('LC_', '').toLowerCase();
        }
        if (log.fields.component) {
            l.comp = log.fields.component;
        }
    }

    // Parse status and dur from event if it's a traffic log
    const statusMatch = l.evt.match(/status=(\d+)/);
    if (statusMatch) {
        l.status = parseInt(statusMatch[1]);
        l.evt = l.evt.replace(statusMatch[0], '').trim();
    }
    const durMatch = l.evt.match(/dur=(\d+(?:\.\d+)?ms)/);
    if (durMatch) {
        l.dur = durMatch[1];
        l.evt = l.evt.replace(durMatch[0], '').trim();
    }
    const reqMatch = l.evt.match(/req_id=([\w-]+)/);
    if (reqMatch) {
        l.req = reqMatch[1];
        l.evt = l.evt.replace(reqMatch[0], '').trim();
    }
    const videoMatch = l.evt.match(/video_id=([\w-]+)/);
    if (videoMatch) {
        l.video_id = videoMatch[1];
        l.evt = l.evt.replace(videoMatch[0], '').trim();
    }

    // Time to local
    l.displayTime = log.time || '--:--:--';
    if (log.time && /^\d{2}:\d{2}:\d{2}$/.test(log.time)) {
        const [h, m, s] = log.time.split(':');
        const d = new Date();
        d.setUTCHours(parseInt(h, 10), parseInt(m, 10), parseInt(s, 10));
        l.displayTime = d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    return l;
}

function rowHtml(l) {
    return `<div class="row lvl-${l.level}">
        <div class="catbar c-${l.cat}"></div>
        <div class="time" title="UTC: ${l.time}">${l.displayTime}</div>
        <div class="badges"><span class="lvl-pill">${l.level}</span><span class="cat-pill">${l.cat}</span></div>
        <div class="msg">${l.comp ? `<span class="comp">${l.comp}</span>` : ''}<span class="evt">${l.evt}</span></div>
        <div class="meta">${metaHtml(l)}</div>
        <button class="copy" title="Salin" onclick="navigator.clipboard.writeText('[${l.time}] ${l.level} [${l.cat.toUpperCase()}] ${l.comp?l.comp+': ':''}${l.evt}')">
            <i class="ti ti-copy"></i>
        </button>
    </div>`;
}

function groupHtml(sig, items) {
    const first = items[0], last = items[items.length-1];
    const statuses = [...new Set(items.map(i => i.status).filter(x => x !== undefined))];
    const anyErr = statuses.some(s => s >= 400);
    const meta = [
        statuses.length ? `<span class="${anyErr ? 'err' : 'ok'}">${statuses.join('/')}</span>` : ''
    ].filter(Boolean).join('  ·  ');

    const children = items.map(i => `<div class="row lvl-${i.level}" style="border-bottom:1px solid var(--border-1);">
        <div class="catbar c-${i.cat}"></div><div class="time" title="UTC: ${i.time}">${i.displayTime}</div>
        <div class="badges"><span class="lvl-pill">${i.level}</span><span class="cat-pill">${i.cat}</span></div>
        <div class="msg">${i.comp ? `<span class="comp">${i.comp}</span>` : ''}<span class="evt">${i.evt}</span></div>
        <div class="meta">${metaHtml(i)}</div>
    </div>`).join('');

    return `<div class="grp lvl-${first.level}" data-open="0">
        <div class="catbar c-${first.cat}"></div>
        <div class="time">${first.displayTime}–${last.displayTime}</div>
        <div class="badges"><span class="lvl-pill">${first.level}</span><span class="cat-pill">${first.cat}</span></div>
        <div class="msg">${first.comp ? `<span class="comp">${first.comp}</span>` : ''}<span class="evt">${first.evt}</span><span class="count-badge">×${items.length}</span></div>
        <div class="meta">${meta}</div>
        <i class="ti ti-chevron-right chev"></i>
    </div><div class="grp-children">${children}</div>`;
}

function renderEmptyState() {
    logContainer.innerHTML = `
        <div class="empty-state" id="emptyLogState" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-3); text-align:center; min-height:200px;">
            <i class="ti ti-filter-off" style="font-size:32px; margin-bottom:12px; opacity:0.5;"></i>
            <h4 style="color:var(--text-2); margin-bottom:4px;">Tidak ada log yang cocok</h4>
            <span style="font-size:12px; max-width:250px;">Coba longgarkan kategori atau hapus kata kunci pencarian.</span>
        </div>
    `;
}

function renderLogs() {
    if (currentLogs.length === 0) {
        renderEmptyState();
        return;
    }

    if (!isGrouped) {
        logContainer.innerHTML = currentLogs.map(l => rowHtml(l)).join('');
        return;
    }

    const groups = [];
    for (const l of currentLogs) {
        const sig = l.level + '|' + l.cat + '|' + l.comp + '|' + l.evt;
        const lastGrp = groups[groups.length - 1];
        if (lastGrp && lastGrp.sig === sig) {
            lastGrp.items.push(l);
        } else {
            groups.push({ sig, items: [l] });
        }
    }

    logContainer.innerHTML = groups.map(g => g.items.length > 1 ? groupHtml(g.sig, g.items) : rowHtml(g.items[0])).join('');

    logContainer.querySelectorAll('.grp').forEach(g => {
        g.addEventListener('click', () => g.classList.toggle('open'));
    });
}

export function appendLogBatch(logs, clearFirst = false) {
    if (clearFirst) {
        currentLogs = [];
    }

    // Deduplicate incoming batch against themselves and currentLogs using a simple hash logic
    // But since logs are ordered, we just append them. We can use a Map to keep it unique if needed.
    // In our case, we will just add them.
    for (const rawLog of logs) {
        currentLogs.push(processLogFields(rawLog));
    }

    if (currentLogs.length > 5000) {
        currentLogs = currentLogs.slice(-5000);
    }

    renderLogs();

    if (autoScrollCheckbox && autoScrollCheckbox.checked) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}
