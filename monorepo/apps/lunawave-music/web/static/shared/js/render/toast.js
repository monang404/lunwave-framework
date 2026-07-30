// render/toast.js
// Diekstrak dari utils/toast.js (PATCH-2026-07-24, lanjutan recovery frontend).
// Fungsi-fungsi ini menyentuh dom.js (dom.connectionToast/dom.logToast),
// jadi tidak sah tinggal di utils/ (rule dependency-cruiser
// `utils-must-be-leaf`: utils/* wajib jadi leaf, tidak boleh import modul
// shared/js lain). Dipindah ke render/ karena isinya murni update tampilan
// (toast UI), bukan util murni. Fungsi non-DOM (cover art, cleanTrackTitle,
// dll.) tetap di utils/cover-art.js.
import { on } from "../bus.js";
import { dom } from "../dom.js";

export function showConnectionToast(text, type) {
    dom.connectionToast.textContent = text;
    dom.connectionToast.className = "active " + type;
}

export function hideConnectionToast() {
    dom.connectionToast.className = "";
}

let logToastTimer = null;
export function showLogToast(text) {
    dom.logToast.textContent = text;
    dom.logToast.classList.add("active");
    if (logToastTimer) clearTimeout(logToastTimer);
    logToastTimer = setTimeout(() => {
        dom.logToast.classList.remove("active");
    }, 3000);
}

export function initToastBusSubscriptions() {
    on("toast:log", ({ message }) => showLogToast(message));
    on("toast:connection-show", ({ text, type }) => showConnectionToast(text, type));
    on("toast:connection-hide", hideConnectionToast);
}
