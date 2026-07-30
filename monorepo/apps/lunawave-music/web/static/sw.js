// ── Service Worker — LunaWave ──
// Strategy: stale-while-revalidate untuk static assets (/static/*),
// network-first untuk HTML shell routes, network-only untuk API/WS.
//
// PATCH-UI-PERF-01: SW lama pakai cache-first murni untuk SEMUA GET,
// termasuk /, /admin, /admin/logs -- begitu ke-cache sekali, user tidak
// pernah lihat update lagi sampai CACHE_VERSION di-bump manual. Ini akar
// masalah kenapa sesi sebelumnya sampai perlu killswitch (unregister SW +
// clear cache tiap load) di index.html. Fix sebenarnya: pisahkan strategi
// -- static assets tetap cache-first-ish tapi selalu revalidate di
// background (stale-while-revalidate), sedangkan HTML shell routes pakai
// network-first supaya perubahan server langsung kelihatan, dengan cache
// cuma sebagai fallback offline.
const CACHE_VERSION = 'lunawave-20260728-swr-v4';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const SHELL_ROUTES = new Set(['/', '/admin', '/admin/logs']);

// Assets yang di-cache saat install
const PRECACHE_ASSETS = [
    // ── App shell routes (server-rendered, bukan file statis) ──
    '/',
    '/admin',
    '/admin/logs',

    '/static/manifest.json',

    // ── Icons ──
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',

    // ── Fonts (self-hosted, dipakai radio-hero.css) ──
    '/static/media/fonts/fraunces/fraunces-latin-500-italic.woff2',
    '/static/media/fonts/space-grotesk/space-grotesk-latin-400-normal.woff2',
    '/static/media/fonts/space-grotesk/space-grotesk-latin-500-normal.woff2',
    '/static/media/fonts/space-grotesk/space-grotesk-latin-600-normal.woff2',

    // ── Vendor (self-hosted, offline-safe) ──
    '/static/shared/css/vendor/tabler-icons.min.css',
    '/static/media/fonts/vendor/tabler-icons.woff2',
    '/static/media/fonts/vendor/tabler-icons.woff',
    '/static/media/fonts/vendor/tabler-icons.ttf',

    // ── CSS: Base ──
    '/static/shared/css/tokens.css',
    '/static/shared/css/portal.css',
    '/static/shared/css/base/reset.css',
    '/static/shared/css/base/typography.css',
    '/static/shared/css/base/animations.css',

    // ── CSS: Layout ──
    '/static/shared/css/layout/app-shell.css',
    '/static/shared/css/layout/nav.css',
    '/static/shared/css/layout/grid.css',

    // ── CSS: Components ──
    '/static/shared/css/components/player-bar.css',
    '/static/shared/css/components/player-controls.css',
    '/static/shared/css/components/cards.css',
    '/static/shared/css/components/lyrics.css',
    '/static/shared/css/components/queue.css',
    '/static/shared/css/components/search.css',
    '/static/shared/css/components/settings-sheet.css',
    '/static/shared/css/components/toasts.css',
    '/static/shared/css/components/radio-hero.css',
    '/static/shared/css/components/discover-cards.css',
    '/static/shared/css/components/discover-search.css',

    // ── CSS: Platform ──
    '/static/shared/css/platform/mobile.css',
    '/static/shared/css/platform/desktop.css',
    '/static/shared/css/platform/tablet.css',
    '/static/shared/css/platform/landscape.css',
    '/static/shared/css/platform/safe-area.css',

    // ── CSS: Base (utilities.css ditambahkan PATCH-UI-PERF-01) ──
    '/static/shared/css/base/utilities.css',

    // ── CSS: Page-specific ──
    '/static/pages/client/chat.css',

    // ── JS: Core ──
    '/framework/static/js/core/store.js',
    '/static/shared/js/dom.js',
    '/static/shared/js/ws.js',
    '/static/shared/js/portal.js',
    '/static/shared/js/config.js',
    // PATCH-UI-PERF-01: bus.js & render/navigation.js sudah lama ada di
    // codebase (dipakai main.js/init) tapi ketinggalan dari precache list
    // ini -- verifikasi ulang terhadap isi disk menemukan keduanya hilang.
    '/static/shared/js/bus.js',
    '/static/shared/js/render/navigation.js',

    // ── JS: Utils ──
    '/static/shared/js/utils/format.js',
    '/static/shared/js/utils/cover-art.js',

    // ── JS: Events ──
    '/static/shared/js/events/index.js',
    '/static/shared/js/events/action-modal-events.js',
    '/static/shared/js/events/click-delegation-events.js',
    '/static/shared/js/events/discover-search-events.js',
    '/static/shared/js/events/drag-scroll-events.js',
    '/static/shared/js/events/keyboard-shortcut-events.js',
    '/static/shared/js/events/lyrics-events.js',
    '/static/shared/js/events/progress-events.js',
    '/static/shared/js/events/queue-events.js',
    '/static/shared/js/events/search-input-events.js',
    '/static/shared/js/events/settings-events.js',
    '/static/shared/js/events/transport-events.js',

    // ── JS: Render ──
    '/static/shared/js/render/player.js',
    '/static/shared/js/render/search.js',
    '/static/shared/js/render/lyrics.js',
    '/static/shared/js/render/queue.js',
    '/static/shared/js/render/now-playing.js',
    '/static/shared/js/render/discover-tab.js',
    '/static/shared/js/render/discover-search.js',
    '/static/shared/js/render/discover-personalize.js',
    '/static/shared/js/render/radio-tab.js',
    '/static/shared/js/render/radio-hero-moon.js',
    '/static/shared/js/render/full-state.js',
    '/static/shared/js/render/toast.js',

    // ── JS: Services ──
    '/static/shared/js/services/auth.js',

    // ── JS: Platform ──
    '/static/shared/js/platform/keyboard.js',
    '/static/shared/js/platform/touch.js',
    '/static/shared/js/platform/viewport.js',

    // ── JS: Audio ──
    '/static/shared/js/audio/playback-sync.js',
    '/static/shared/js/audio/visualizer.js',
    // PATCH-UI-PERF-01: sama seperti bus.js/navigation.js di atas -- hilang
    // dari precache list sebelumnya meski dipakai (media-session.js untuk
    // Media Session API/lockscreen controls, audio-pool.js untuk playback).
    '/static/shared/js/audio/media-session.js',
    '/static/shared/js/audio/audio-pool.js',

    // ── JS: WebSocket transport & message handlers ──
    // PATCH-UI-PERF-01: seluruh folder ws/ (router, transport, dan semua
    // message-handlers) ketinggalan dari precache list -- ini yang paling
    // krusial karena tanpanya koneksi realtime (status player, chat,
    // discover) tidak akan bisa jalan sama sekali kalau app dibuka offline
    // sebelum pernah online sekali.
    '/framework/static/js/core/transport.js',
    '/framework/static/js/core/router.js',
    '/static/shared/js/ws/message-handlers/auth-messages.js',
    '/static/shared/js/ws/message-handlers/chat-messages.js',
    '/static/shared/js/ws/message-handlers/discover-messages.js',
    '/static/shared/js/ws/message-handlers/playback-messages.js',
    '/static/shared/js/ws/message-handlers/system-messages.js',

    // ── JS: Page entry points ──
    '/static/pages/app/main.js',
    '/static/pages/client/client.js',
    '/static/pages/client/chat.js',
    '/static/pages/admin-logs/admin-logs.js',
    // PATCH-UI-PERF-01: sisa panel admin-logs yang juga ketinggalan.
    '/static/pages/admin-logs/admin-chat-panel.js',
    '/static/pages/admin-logs/admin-ws-transport.js',
    '/static/pages/admin-logs/dashboard-stats.js',
    '/static/pages/admin-logs/log-tail.js',
];

// Install: pre-cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                return Promise.all(
                    PRECACHE_ASSETS.map(url =>
                        cache.add(url).catch(err => console.warn('Cache add failed for', url, err))
                    )
                );
            })
            .then(() => self.skipWaiting())
    );
});

// Activate: hapus cache lama
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(key => key !== STATIC_CACHE)
                    .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip WebSocket dan API requests -- selalu network, tidak pernah cache.
    if (url.pathname.startsWith('/ws') || url.pathname.startsWith('/api')) {
        return;
    }
    if (event.request.method !== 'GET') return;

    // HTML shell routes: network-first, fallback ke cache kalau offline.
    // Ini yang bikin update server langsung kelihatan tanpa perlu clear cache.
    if (SHELL_ROUTES.has(url.pathname)) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    if (response.ok) {
                        const cloned = response.clone();
                        caches.open(STATIC_CACHE).then(cache => cache.put(event.request, cloned));
                    }
                    return response;
                })
                .catch(() => caches.match(event.request).then(cached => cached || caches.match('/')))
        );
        return;
    }

    // Static assets (/static/*): stale-while-revalidate -- balas dari cache
    // instan kalau ada, lalu diam-diam fetch ulang & refresh cache di
    // background, jadi load berikutnya sudah dapat versi terbaru tanpa
    // pernah "macet" di versi lama selamanya.
    event.respondWith(
        caches.match(event.request).then(cached => {
            const network = fetch(event.request).then(response => {
                if (response.ok) {
                    const cloned = response.clone();
                    caches.open(STATIC_CACHE).then(cache => cache.put(event.request, cloned));
                }
                return response;
            }).catch(() => cached);
            return cached || network;
        })
    );
});
