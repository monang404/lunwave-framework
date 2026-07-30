import { emit as bus } from "../../bus.js";
import { dom } from "../../dom.js";
import { store } from "/framework/static/js/core/store.js";

export function handleSystemMessage(msg) {
    switch (msg.type) {
        case "log":
            bus("toast:log", { message: msg.data });
            break;
        case "error":
            bus("toast:log", { message: "Error: " + msg.data });
            bus("discover:search-error");
            break;
        case "download_progress": {
            const prevProgress = store.download_progress;
            store.download_progress = msg.data;
            bus("player:bar-changed");
            bus("settings:sheet-changed");

            if (prevProgress == null || prevProgress >= 1.0) {
                if (msg.data >= 0 && msg.data < 1.0) {
                    bus("toast:log", { message: "⬇ Mulai mengunduh lagu..." });
                }
            }
            if (msg.data >= 1.0 && prevProgress !== 1.0) {
                bus("toast:log", { message: "✅ Unduhan selesai! Tersedia di Tersimpan Lokal" });
                setTimeout(() => {
                    store.download_progress = null;
                    bus("player:bar-changed");
                }, 3000);
            }
            break;
        }
        case "cache_size":
            if (dom.ssCacheSub) {
                const mb = (msg.data.size_bytes / (1024 * 1024)).toFixed(2);
                dom.ssCacheSub.textContent = mb + " MB";
            }
            break;
        case "cache_cleared":
            if (dom.ssCacheSub) dom.ssCacheSub.textContent = "0.00 MB";
            break;
    }
}
