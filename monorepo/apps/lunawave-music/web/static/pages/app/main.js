import { initAudio } from "../../shared/js/audio/playback-sync.js";
import { dom, initDOM } from "../../shared/js/dom.js";
import { initSettingsBusSubscriptions } from "../../shared/js/events/settings-events.js";
import { initEvents } from "../../shared/js/events/index.js";
import { switchTab } from "../../shared/js/render/navigation.js";
import { initSetupCheck } from "../../shared/js/portal.js";
import { initDiscoverPersonalizeBusSubscriptions } from "../../shared/js/render/discover-personalize.js";
import { initDiscoverSearchBusSubscriptions } from "../../shared/js/render/discover-search.js";
import { initDiscoverTabBusSubscriptions } from "../../shared/js/render/discover-tab.js";
import { initFullStateBusSubscriptions } from "../../shared/js/render/full-state.js";
import { initLyricsBusSubscriptions } from "../../shared/js/render/lyrics.js";
import { initNowPlayingBusSubscriptions } from "../../shared/js/render/now-playing.js";
import { initPlayerBusSubscriptions, startProgressClock } from "../../shared/js/render/player.js";
import { initQueueBusSubscriptions } from "../../shared/js/render/queue.js";
import { initRadioHeroBusSubscriptions } from "../../shared/js/render/radio-hero-moon.js";
import { initRadioTabBusSubscriptions } from "../../shared/js/render/radio-tab.js";
import { initSearchBusSubscriptions } from "../../shared/js/render/search.js";
import { initToastBusSubscriptions } from "../../shared/js/render/toast.js";
import { initAuthBusSubscriptions } from "../../shared/js/services/auth.js";
import { store } from "/framework/static/js/core/store.js";
import { wsConnect } from "../../shared/js/ws.js";

(function () {
    "use strict";

    function init() {
        // FIX BUG-1: set data-active-tab SEBELUM DOM diinit supaya CSS selector
        // body:not([data-active-tab="home"]) tidak aktif saat #app pertama muncul.
        // Tanpa ini, player-bar jadi position:absolute dan menutupi navbar.
        document.body.dataset.activeTab = (typeof store !== "undefined" && store.active_tab)
            ? store.active_tab
            : "home";
        initDOM();

        const initTab = document.body.dataset.activeTab;
        if (dom["tab" + initTab.charAt(0).toUpperCase() + initTab.slice(1)]) {
            dom["tab" + initTab.charAt(0).toUpperCase() + initTab.slice(1)].classList.add("active");
        }
        const navBtn = document.querySelector(`.nav-btn[data-tab="${initTab}"]`);
        if (navBtn) {
            navBtn.classList.add("active");
            navBtn.setAttribute("aria-selected", "true");
        }

        // T-B11.1/T-B11.2: initSetupCheck() menggantikan panggilan initPortal()
        // langsung -- keputusan #setup-screen vs #portal-screen sekarang lewat
        // GET /api/setup-required dulu (async), initPortal() dipanggil dari
        // dalamnya kalau setup TIDAK diperlukan (lihat portal.js).
        initSetupCheck();
        initAudio();
        initPlayerBusSubscriptions();
        initNowPlayingBusSubscriptions();
        initQueueBusSubscriptions();
        initRadioHeroBusSubscriptions();
        initToastBusSubscriptions();
        initRadioTabBusSubscriptions();
        initSearchBusSubscriptions();
        initDiscoverTabBusSubscriptions();
        initDiscoverPersonalizeBusSubscriptions();
        initDiscoverSearchBusSubscriptions();
        initFullStateBusSubscriptions();
        initLyricsBusSubscriptions();
        initSettingsBusSubscriptions();
        initAuthBusSubscriptions();
        initEvents();
        // Loop rAF yang gambar progress bar tiap frame lewat interpolasi
        // (lihat render/player.js) — bikin gerakannya mulus terus, gak cuma
        // pas ada event timeupdate/progress baru.
        if (typeof startProgressClock === "function") startProgressClock();
        wsConnect();
    }

    // Alias window.switchTab -- jaga-jaga untuk pemanggilan dari luar graph
    // ES module (mis. inline handler lama atau debugging manual di console).
    // Implementasi asli sekarang di events/index.js (lihat komentar di sana).
    window.switchTab = switchTab;

    document.addEventListener("DOMContentLoaded", init);
})();


// ── Service Worker Registration ──
// PATCH-UI-PERF-01: verified manually by the user via ?sw=1 (reload,
// offline, and update-transition all checked OK) -- now always-on.
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('SW registered:', reg.scope))
            .catch(err => console.warn('SW registration failed:', err));
    });
}

// Manual escape hatch: run `window.__lunawaveKillSW()` in devtools console
// if a registered SW/cache ever misbehaves. Deliberate (you call it), not
// automatic on every load like the old killswitch.
window.__lunawaveKillSW = async function () {
    if ('serviceWorker' in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map(r => r.unregister()));
    }
    if ('caches' in window) {
        const keys = await caches.keys();
        await Promise.all(keys.map(k => caches.delete(k)));
    }
    console.log('[lunawave] SW unregistered + caches cleared. Reload to confirm.');
};
