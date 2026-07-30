export function formatTime(secs) {
    if (!secs || secs < 0) return "00:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

export function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function formatDurationLong(secs) {
    if (!secs || secs < 0) return "00:00:00";
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    if (h > 0) {
        return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

export function formatRelativeTime(unixSeconds) {
    if (!unixSeconds) return "";
    const diffSec = Math.floor(Date.now() / 1000) - unixSeconds;
    if (diffSec < 60) return "baru saja";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + " menit lalu";
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return diffHour + " jam lalu";
    const diffDay = Math.floor(diffHour / 24);
    if (diffDay < 30) return diffDay + " hari lalu";
    const diffMonth = Math.floor(diffDay / 30);
    if (diffMonth < 12) return diffMonth + " bulan lalu";
    return Math.floor(diffMonth / 12) + " tahun lalu";
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { formatTime, escapeHtml, formatDurationLong, formatRelativeTime };
}
