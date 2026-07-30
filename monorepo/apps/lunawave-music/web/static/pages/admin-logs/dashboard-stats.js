import { fetchTail } from "/framework/static/js/core/transport.js";

const filterCategory = /** @type {HTMLSelectElement} */ (document.getElementById('filterCategory'));
const globalStatsGrid = document.getElementById('globalStatsGrid');
const levelStatsList = document.getElementById('levelStatsList');
const catStatsList = document.getElementById('catStatsList');
const matrixContainer = document.getElementById('matrixContainer');

// Categories for badge coloring
export const CATEGORY_COLORS = {
    "lifecycle": "#bb86fc",
    "http": "#004d40",
    "session": "#01579b",
    "command": "#b71c1c",
    "playback": "#1b5e20",
    "queue": "#827717",
    "discovery": "#e65100",
    "download": "#3e2723",
    "lyrics": "#880e4f",
    "db": "#4e342e",
    "cache": "#37474f",
    "metrics": "#006064",
    "security": "#b71c1c",
    "app": "#212121",
    "unknown": "#212121"
};
export function getCategoryColor(cat) {
    return CATEGORY_COLORS[cat] || CATEGORY_COLORS["unknown"];
}
export async function fetchStats() {
    try {
        const token = localStorage.getItem('metricsToken') || '';
        const headers = token ? {'X-Metrics-Token': token} : {};
        const res = await fetch('/api/logs/stats', { headers });
        if (!res.ok) throw new Error('Failed to fetch stats');

        const data = await res.json();

        // Populate filterCategory dynamically
        if (data.available_categories && filterCategory.options.length <= 1) {
            const currentValue = filterCategory.value;
            // Clear all except the first "Semua Kategori" option
            while (filterCategory.options.length > 1) {
                filterCategory.remove(1);
            }
            data.available_categories.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                // Title Case: capitalize first letter
                opt.text = cat.charAt(0).toUpperCase() + cat.slice(1);
                filterCategory.add(opt);
            });
            filterCategory.value = currentValue;

            const legend = document.getElementById('legend');
            if (legend) {
                legend.innerHTML = '';
                data.available_categories.forEach(c => {
                    legend.innerHTML += `<span><span class="dot c-${c}"></span>${c}</span>`;
                });
            }
        }

        // Render Global Metrics Grid (Categories)
        globalStatsGrid.innerHTML = '';
        if (data.log_stats && data.log_stats.categories) {
            const sorted = Object.entries(data.log_stats.categories).sort((a, b) => b[1] - a[1]);
            for (const [cat, count] of sorted) {
                const box = document.createElement('div');
                box.className = 'stat-box';
                box.style.cursor = 'pointer';
                box.innerHTML = `
                    <div class="stat-val">${count}</div>
                    <div class="stat-lbl">${cat}</div>
                `;
                box.onclick = () => {
                    filterCategory.value = cat;
                    fetchTail(true);
                };
                globalStatsGrid.appendChild(box);
            }
        }

        // Render Levels
        levelStatsList.innerHTML = '';
        if (data.log_stats && data.log_stats.levels) {
            for (const [lvl, count] of Object.entries(data.log_stats.levels)) {
                levelStatsList.innerHTML += `<li class="category-item"><span class="lvl-${lvl}">${lvl}</span> <span>${count}</span></li>`;
            }
        }

        // Render Top Categories List
        catStatsList.innerHTML = '';
        if (data.log_stats && data.log_stats.categories) {
            const sorted = Object.entries(data.log_stats.categories).sort((a, b) => b[1] - a[1]).slice(0, 5);
            for (const [cat, count] of sorted) {
                const color = getCategoryColor(cat);
                catStatsList.innerHTML += `<li class="category-item"><span style="color:${color}">${cat}</span> <span>${count}</span></li>`;
            }
        }

        // Render Matrix Table
        if (data.log_stats && data.log_stats.matrix) {
            renderMatrix(data.log_stats.matrix);
        }

        // Render System Dashboard
        if (data.system_stats) {
            renderSystemDashboard(data.system_stats, data.log_stats, data.metrics);
        }

        // Render Active Users
        if (data.active_users) {
            renderActiveUsers(data.active_users);
        }

    } catch (e) {
        console.error("Stats fetch error:", e);
    }
}
export function renderMatrix(matrixData) {
    if (!matrixData || Object.keys(matrixData).length === 0) {
        matrixContainer.innerHTML = '<div style="color:var(--text-3); text-align:center; padding: 20px;">Belum ada data log untuk membuat matriks.</div>';
        return;
    }

    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const categories = Object.keys(matrixData).sort();

    let html = '<table class="matrix-table"><thead><tr><th>Kategori</th>';
    levels.forEach(lvl => {
        html += `<th>${lvl}</th>`;
    });
    html += '</tr></thead><tbody>';

    categories.forEach(cat => {
        html += `<tr><td class="cat-name">${cat}</td>`;
        levels.forEach(lvl => {
            const count = matrixData[cat][lvl] || 0;
            if (count > 0) {
                let cellClass = 'cell-info';
                if (lvl === 'WARNING') cellClass = 'cell-warning';
                if (lvl === 'ERROR' || lvl === 'CRITICAL') cellClass = 'cell-error';

                html += `<td class="clickable-cell ${cellClass}" onclick="navigateToLiveTail('${cat}', '${lvl}')">${count}</td>`;
            } else {
                html += `<td class="cell-zero">-</td>`;
            }
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    matrixContainer.innerHTML = html;
}
export function formatDuration(seconds) {
    if (!seconds) return '--';
    const s = Math.floor(seconds);
    if (s < 60) return `${s} detik`;
    const m = Math.floor(s / 60);
    const s2 = s % 60;
    if (m < 60) return `${m}m ${s2}s`;
    const h = Math.floor(m / 60);
    const m2 = m % 60;
    return `${h}j ${m2}m`;
}
export function parseUserAgent(ua) {
    if (!ua) return { os: 'Unknown OS', browser: 'Unknown Browser', icon: 'ti-device-desktop' };

    let os = 'Unknown OS';
    let icon = 'ti-device-desktop';
    if (ua.includes('Windows')) { os = 'Windows'; icon = 'ti-brand-windows'; }
    else if (ua.includes('Mac OS')) { os = 'macOS'; icon = 'ti-brand-apple'; }
    else if (ua.includes('Linux')) { os = 'Linux'; icon = 'ti-brand-ubuntu'; }
    else if (ua.includes('Android')) { os = 'Android'; icon = 'ti-brand-android'; }
    else if (ua.includes('iPhone') || ua.includes('iPad')) { os = 'iOS'; icon = 'ti-device-mobile'; }

    let browser = 'Unknown Browser';
    if (ua.includes('Firefox')) browser = 'Firefox';
    else if (ua.includes('Edg')) browser = 'Edge';
    else if (ua.includes('Chrome')) browser = 'Chrome';
    else if (ua.includes('Safari')) browser = 'Safari';
    else if (ua.includes('Opera') || ua.includes('OPR')) browser = 'Opera';

    return { os, browser, icon };
}
export function getPageName(referer) {
    if (!referer) return 'Unknown Page';
    if (referer.includes('/admin/logs')) return 'Logging Dashboard';
    if (referer.includes('/admin')) return 'Admin Panel';
    if (referer.endsWith('/') || referer.endsWith(':8765') || referer.endsWith('localhost')) return 'Main Player';
    return 'Main Player'; // fallback
}
export function renderSystemDashboard(stats, logStats, metrics) {
    const grid = document.getElementById('sysDashGrid');
    if (!grid) return;

    const cpuPct = stats.cpu_percent !== null ? stats.cpu_percent : null;
    const cpuStr = cpuPct !== null ? `${cpuPct}%` : '--';

    // RAM Usage & Uptime SENGAJA tidak dipakai lagi di sini -- sudah
    // ditampilkan persis di status bar header (val-mem, val-uptime),
    // jadi menampilkannya lagi di sini cuma duplikasi tanpa info baru.
    // Diganti dengan Total Requests & Error count (1 jam terakhir) --
    // dua-duanya sudah ikut ke-fetch di /api/logs/stats (metrics,
    // log_stats.levels) tapi sebelumnya tidak pernah dirender di tab ini.
    const totalReqs = metrics && metrics.http_requests_total !== undefined
        ? metrics.http_requests_total : '--';
    const errorCount = logStats && logStats.levels
        ? (logStats.levels.ERROR || 0) + (logStats.levels.CRITICAL || 0)
        : 0;

    // Progress bar cuma untuk CPU -- satu-satunya angka di sini yang memang
    // persentase asli (0-100). Metrik lain tidak punya "batas atas" yang
    // jujur untuk direpresentasikan sebagai bar, jadi sengaja tidak
    // dipaksakan supaya tidak menyesatkan.
    const cpuBar = cpuPct !== null
        ? `<div class="sys-card-bar"><div class="sys-card-bar-fill" style="width:${Math.min(100, Math.max(0, cpuPct))}%"></div></div>`
        : '';

    const cards = [
        { icon: 'ti-cpu', val: cpuStr, lbl: 'CPU Usage', extra: cpuBar },
        { icon: 'ti-arrow-bar-to-up', val: totalReqs, lbl: 'Total Requests' },
        { icon: 'ti-player-play-filled', val: stats.songs_played || 0, lbl: 'Total Plays' },
        { icon: 'ti-music', val: stats.total_tracks || 0, lbl: 'Total Tracks (Library)' },
        { icon: 'ti-disc', val: stats.total_songs || 0, lbl: 'Total Katalog (Songs)' },
        { icon: 'ti-users-group', val: stats.total_artists || 0, lbl: 'Total Artists' },
        { icon: 'ti-alert-triangle', val: errorCount, lbl: 'Errors (1 Jam)' },
    ];

    grid.innerHTML = cards.map(c => `
        <div class="sys-card">
            <div class="sys-card-icon"><i class="ti ${c.icon}"></i></div>
            <div class="sys-card-body">
                <div class="sys-card-val">${c.val}</div>
                <div class="sys-card-lbl">${c.lbl}</div>
                ${c.extra || ''}
            </div>
        </div>
    `).join('');
}
export function renderActiveUsers(users) {
    const tbody = document.getElementById('activeUsersTbody');
    if (!tbody) return;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-3); padding:var(--s5); display:table-cell;">Tidak ada pengguna aktif</td></tr>';
        return;
    }

    let html = '';
    users.forEach(u => {
        const dev = parseUserAgent(u.user_agent);
        const pageName = getPageName(u.referer);
        html += `
            <tr>
                <td data-label="Alamat IP" style="font-family:monospace; color:var(--accent); font-weight:bold; vertical-align:middle;">
                    <i class="ti ti-network" style="margin-right:8px; opacity:0.7;"></i>${u.ip || 'Unknown'}
                </td>
                <td data-label="Halaman" style="vertical-align:middle;">
                    <span style="background: rgba(255, 204, 0, 0.1); color: var(--accent); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;">
                        ${pageName}
                    </span>
                </td>
                <td data-label="Perangkat" style="vertical-align:middle;">
                    <div class="device-badge">
                        <i class="ti ${dev.icon}"></i> ${dev.os} &bull; ${dev.browser}
                    </div>
                </td>
                <td data-label="Durasi" style="vertical-align:middle;">${formatDuration(u.duration)}</td>
                <td data-label="Status" style="vertical-align:middle;">
                    <span style="display:inline-flex; align-items:center; gap:6px; color:#22c55e; border:1px solid rgba(34,197,94,0.3); padding:4px 10px; border-radius:12px; font-size:11px; font-weight:600;">
                        <span style="width:6px; height:6px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px #22c55e;"></span> Active
                    </span>
                </td>
                <td data-label="Aksi" style="vertical-align:middle; text-align:right;">
                    <!-- Selalu tampilkan bubble chat, JANGAN gated di u.uid: admin harus bisa
                         chat duluan ke client tanpa menunggu client kirim pesan pertama.
                         client.js sudah mengirim client_uid otomatis begitu WS connect
                         (lihat client.js::connectWS -- wsSend("get_chat_history") di
                         window.ws.onopen), jadi u.uid biasanya sudah terisi di poll
                         pertama setelah client terhubung. Untuk celah sangat singkat saat
                         u.uid belum terisi, openChatPanel() (admin-logs.js) menangani ini
                         secara graceful -- panel tetap terbuka dengan status "menunggu
                         koneksi client", bukan tombolnya yang disembunyikan. -->
                    <button class="chat-btn" data-uid="${u.uid || ''}" data-ip="${u.ip || ''}" style="background:var(--bg-elevated); border:1px solid var(--border-2); padding:6px 12px; font-size:12px; border-radius:16px; color:var(--text-2); cursor:pointer; display:inline-flex; align-items:center; gap:6px; position:relative;">
                        <i class="ti ti-message-circle"></i> Chat
                        ${u.uid ? `<span class="chat-badge" id="badge-${u.uid}" style="display:none; position:absolute; top:-6px; right:-6px; background:var(--accent); color:var(--accent-dark); width:16px; height:16px; border-radius:50%; font-size:10px; font-weight:bold; align-items:center; justify-content:center;"></span>` : ''}
                    </button>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;

    // Bind chat buttons (data-uid = client_uid, kunci thread chat --
    // bukan IP, lihat server/handlers/ws_chat.py). Tombol selalu ada
    // sekarang (lihat komentar di atas render-nya) -- data-uid bisa kosong
    // untuk celah singkat sebelum client_uid terisi, ditangani di
    // openChatPanel().
    /** @type {NodeListOf<HTMLElement>} */
    (document.querySelectorAll('.chat-btn')).forEach(btn => {
        btn.addEventListener('click', () => {
            document.dispatchEvent(new CustomEvent('chat:open', {
                detail: { uid: btn.dataset.uid, ip: btn.dataset.ip }
            }));
        });
    });
}
