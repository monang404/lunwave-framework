# Frontend Architecture

← [architecture/overview.md](overview.md) | [Blueprint.md](../Blueprint.md)

---

## Filosofi Frontend

LunaWave menggunakan **vanilla JS tanpa framework** secara sengaja.

Alasan lengkap → [ADR-0006](../adr/0006-vanilla-js-over-framework.md)

Ringkasannya:
- Proyek ini adalah music player — DOM-nya stabil, bukan aplikasi CRUD kompleks
- Tidak ada build step (Webpack, Vite, dll.) = tidak ada dependency drift
- PWA offline-first lebih mudah dikontrol tanpa virtual DOM

---

## Peta Modul JavaScript

> **Update 2026-07-24 (PATCH-2026-07-24-220):** Entry point per-halaman sudah
> dipindah keluar dari `web/static/shared/js/` ke folder halamannya masing-masing.
> Modul di bawah `web/static/shared/js/` (termasuk `store.js`, `dom.js`, `ws.js`,
> `audio/`, `render/`, `events/`, `services/`, `utils/`, `platform/`) tetap
> shared dan tidak pindah -- hanya 4 file entry point berikut yang pindah:

| Entry point | Lokasi baru | Dipakai oleh |
|---|---|---|
| `main.js` | `web/static/pages/app/main.js` | `pages/app/index.html` |
| `client.js` | `web/static/pages/client/client.js` | `pages/client/client.html` |
| `chat.js` | `web/static/pages/client/chat.js` | `pages/client/client.html` |
| `admin-logs.js` | `web/static/pages/admin-logs/admin-logs.js` | `pages/admin-logs/admin-logs.html` |

Semua import relatif di keempat file itu mengarah balik ke shared module lewat
`../../shared/js/...js`. Tidak ada backward-compat alias di lokasi lama --
seluruh caller (HTML, `server/handlers/http.py`, `server/handlers/log_dashboard.py`)
sudah diverifikasi ikut update di patch yang sama.

`chat.css` (dipakai khusus `client.html`, tidak shared) pindah bersamaan ke
`web/static/pages/client/chat.css` -- bukan cuma JS, satu-satunya CSS yang
entry-only mengikuti pola yang sama.

### Root (`web/static/shared/js/`)

| File | Tanggung Jawab | Baris (saat ini) |
|---|---|---|
| `config.js` | Konstanta URL, timeout, feature flags | ~30 |
| `store.js` | State global client-side | ~90 |
| `dom.js` | Selector cache, DOM helpers | ~80 |
| `portal.js` | Login portal logic | ~60 |
| `ws.js` | WebSocket lifecycle + routing pesan masuk | ~190 (slim) |

> `main.js` (init: mount listeners, connect WS, check auth) bukan lagi di sini
> sejak PATCH-2026-07-24-220 — pindah ke `pages/app/main.js` (lihat tabel
> Entry Point di atas), karena isinya entry-only untuk `pages/app/index.html`,
> bukan modul shared.

### `js/audio/`

| File | Tanggung Jawab |
|---|---|
| `playback-sync.js` 🆕 | Sinkronisasi `<audio>` element dengan state server |
| `visualizer.js` 🆕 | Canvas visualizer (opsional, bisa disabled) |

> Dipecah dari `audio.js` yang sebelumnya merangkap terlalu banyak.

**Exception circular-dependency terdokumentasi:** `audio/playback-sync.js`
dan `audio/visualizer.js` saling impor (live binding `analyser`/`dataArray`)
secara sengaja sejak PATCH-2026-07-24-223, supaya visualizer selalu
melihat nilai `analyser` terkini tanpa re-passing manual. Ini
terdeteksi sebagai circular-dependency warning oleh depcruise, dan
SENGAJA DIBIARKAN (bukan lupa diperbaiki) karena refactor ke
parameter-passing berisiko meregresi behavior real-time audio untuk
manfaat yang kecil. Lihat investigasi lengkap di
docs/rfc/frontend_refactor/ sesi 4.

### `js/events/`

| File | Tanggung Jawab |
|---|---|
| `index.js` | Mount semua event listener, entry point |
| `queue-events.js` | Drag/drop, reorder, hapus dari queue |
| `lyrics-events.js` | Toggle lirik, scroll sync |
| `settings-events.js` | Buka/tutup settings sheet, save preference |
| `transport-events.js` 🆕 | Play/pause/skip button handler |
| `progress-events.js` 🆕 | Seek bar: drag, click, release |
| `search-input-events.js` 🆕 | Debounce input, trigger search |
| `action-modal-events.js` 🆕 | Confirm/cancel modal actions |
| `click-delegation-events.js` 🆕 | Event delegation untuk list item dinamis |
| `keyboard-shortcut-events.js` 🆕 | Keyboard shortcut global |

> Semua dipecah dari `player-events.js` yang sebelumnya >300 baris.

### `js/render/`

| File | Tanggung Jawab |
|---|---|
| `player.js` | Render player bar (progress, controls, metadata) |
| `now-playing.js` | Render panel now-playing |
| `lyrics.js` | Render & highlight lirik sinkron |
| `search.js` | Render search result cards |
| `queue.js` | Render queue list |
| `discover-tab.js` 🆕 | Render discover tab (mix, trending) |
| `radio-tab.js` 🆕 | Render radio mode UI |
| `full-state.js` 🆕 | Render ulang full state setelah WS reconnect |
| `toast.js` 🆕 | Tampilkan toast notification (connection toast, log toast) |

> `discover-tab.js` dan `radio-tab.js` dipecah dari `discover.js` yang sebelumnya merangkap dua tab.
> `full-state.js` dipindah dari `ws.js` untuk memisahkan routing dari rendering.
> `toast.js` pindah dari `utils/toast.js` (lihat catatan di `js/utils/` di bawah) —
> bukan pemecahan, dipindah utuh, karena isinya import `dom.js` sehingga tidak
> sah tinggal di `utils/` (rule dependency-cruiser `utils-must-be-leaf`).

### `js/utils/`

| File | Tanggung Jawab |
|---|---|
| `format.js` 🆕 | Format durasi, tanggal, nama artis |
| `cover-art.js` 🆕 | Cover art fetch/cache (iTunes + fallback YT thumbnail), lazy-load observer, `cleanTrackTitle`, `safeStorage` |

> **Update PATCH-2026-07-24 (recovery frontend, lanjutan):** `toast.js` semula
> di sini campur dua tanggung jawab (toast UI berbasis `dom.js` + util murni
> cover art). Dipecah: bagian toast pindah ke `render/toast.js` (lihat di
> atas), bagian util murni jadi `cover-art.js` di sini — supaya `utils/`
> tetap leaf sesuai rule dependency-cruiser `utils-must-be-leaf`.

### `js/services/`

| File | Tanggung Jawab |
|---|---|
| `auth.js` | HTTP request auth, token storage, refresh |

### `js/platform/`

| File | Tanggung Jawab |
|---|---|
| `keyboard.js` | Keyboard shortcut registry |
| `touch.js` | Touch gesture handler (swipe, long-press) |
| `viewport.js` | Viewport size, orientation change handler |

---

## Peta Modul CSS

### Prinsip CSS LunaWave

**Tidak ada refactor CSS besar-besaran.** File CSS yang belum disentuh dan berfungsi dengan baik dibiarkan. Penambahan dilakukan dengan menambah file baru, bukan memecah file yang ada kecuali ada alasan kuat.

Alasan lengkap → [frontend/ui_architecture.md](../frontend/ui_architecture.md)

### Struktur

| Folder/File | Tanggung Jawab |
|---|---|
| `tokens.css` | Design tokens: warna, spacing, radius, font |
| `portal.css` | Style login portal (terpisah dari app) |
| `base/` | Reset, typography, root variables |
| `layout/` | Grid, flex containers, panel layout |
| `platform/` | Mobile-specific, desktop-specific overrides |
| `components/toasts.css` | Toast notification |
| `components/lyrics.css` | Lirik panel & highlight |
| `components/queue.css` | Queue list & drag handle |
| `components/search.css` | Search result cards |
| `components/settings-sheet.css` | Settings bottom sheet |
| `components/player-controls.css` | Player bar: progress, buttons |
| `components/player-bar/` 🔧 | Pecahan `player-controls.css` — *hanya jika cascade bisa dipisah bersih* |
| `components/cards/` 🔧 | Discover & search cards — *prioritas rendah* |
| `vendor/tabler-icons.min.css` | Icon library |
| `vendor/fonts/` | Font files |

> 🔧 = opsional, hanya dikerjakan jika ada alasan nyata.

---

## Strategi CSS Konservatif

```
Tidak diubah:
├── file yang tidak rusak
├── file yang belum disentuh
└── refactor demi estetika semata

Boleh dipecah jika:
├── file > 200 baris
├── cascade bisa dipisah bersih tanpa memecah specificity
└── ada bug yang disebabkan oleh file yang terlalu besar
```

Detail lengkap → [frontend/ui_architecture.md](../frontend/ui_architecture.md)

---

## State Flow Frontend

```
WebSocket Message Masuk
        │
        ▼
    ws.js
  (routing)
        │
        ├──→ render/full-state.js   (full state update)
        ├──→ render/player.js        (playback state)
        ├──→ render/queue.js         (queue update)
        ├──→ render/lyrics.js        (lyric sync)
        └──→ render/discover-tab.js  (discover update)

User Action
        │
        ▼
  events/*.js
        │
        ▼
  store.js (optimistic update, opsional)
        │
        ▼
  WebSocket Send → Server
```

Detail → [frontend/state_management.md](../frontend/state_management.md)

---

## PWA

| File | Tanggung Jawab |
|---|---|
| `manifest.json` | PWA metadata: nama, ikon, display mode, theme color |
| `sw.js` | Service worker: precache, offline fallback, update strategy |
| `icons/icon-192.png` | Ikon PWA 192×192 |
| `icons/icon-512.png` | Ikon PWA 512×512 |

Detail → [frontend/pwa.md](../frontend/pwa.md)

---

## Dokumen Terkait

- [frontend/ui_architecture.md](../frontend/ui_architecture.md) — Detail CSS strategy & component map
- [frontend/state_management.md](../frontend/state_management.md) — store.js & WS state sync
- [frontend/routing.md](../frontend/routing.md) — Event routing & WS message routing
- [frontend/pwa.md](../frontend/pwa.md) — Service worker & manifest
- [testing/frontend_testing.md](../testing/frontend_testing.md) — Frontend test (opsional)
- [ADR-0006](../adr/0006-vanilla-js-over-framework.md) — Kenapa vanilla JS?
