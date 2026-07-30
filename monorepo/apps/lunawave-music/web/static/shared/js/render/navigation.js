// navigation.js -- switchTab dipindah dari events/index.js (Tahap 3
// event bus, docs/rfc/pemulihan_frontend/09_tahap3_event_bus_events_index.yaml).
// Alasan pindah: fungsi ini murni manipulasi DOM (render/UI), bukan
// logika bootstrap/inisialisasi, tapi sebelumnya tinggal di hub
// events/index.js sehingga jadi sumber 7 circular-dependency edge.
// Dipindah verbatim, TIDAK ada perubahan logika.
import { TABS } from "../config.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

export function switchTab(tab) {
    store.active_tab = tab;
    document.body.dataset.activeTab = tab;

    TABS.forEach((t) => {
        const panel = dom["tab" + t.charAt(0).toUpperCase() + t.slice(1)];
        if (panel) {
            if (t === tab) panel.classList.add("active");
            else panel.classList.remove("active");
        }
    });

    /** @type {NodeListOf<HTMLElement>} */
    (document.querySelectorAll(".nav-btn")).forEach((btn) => {
        if (btn.dataset.tab === tab) {
            btn.classList.add("active");
            btn.setAttribute("aria-selected", "true");
        } else {
            btn.classList.remove("active");
            btn.setAttribute("aria-selected", "false");
        }
    });

    if (tab === "search") {
        setTimeout(() => dom.searchInput.focus(), 100);
    }
    if (tab === "discover" || tab === "home") {
        wsSend("discover");
    }
}
