# PWA

← [frontend/ui_architecture.md](ui_architecture.md) | [Blueprint.md](../Blueprint.md)

---

## Gambaran Umum

LunaWave adalah **Progressive Web App (PWA)** yang dapat diinstall di desktop dan mobile. PWA diimplementasikan dengan dua file:

| File | Tanggung Jawab |
|---|---|
| `web/static/manifest.json` | Metadata instalasi: nama, ikon, warna, display mode |
| `web/static/sw.js` | Service worker: precache, offline fallback, update |

---

## `manifest.json`

```json
{
  "name": "LunaWave",
  "short_name": "LunaWave",
  "description": "Personal music player",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0a",
  "theme_color": "#7c6af7",
  "orientation": "any",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### Audit Manifest

Cek periodik yang perlu dilakukan:

- `theme_color` sesuai dengan `--color-accent` di `tokens.css`
- `background_color` sesuai dengan `--color-bg`
- Icon 192 dan 512 ada dan tidak corrupt
- `start_url` valid dan tidak redirect

---

## `sw.js` — Service Worker

### Strategi

LunaWave menggunakan strategi **Cache First** untuk aset statis, **Network Only** untuk API.

```
Request masuk
      │
      ├── Aset statis (JS, CSS, icons)?
      │       └── Cache First → cache hit → return dari cache
      │                       → cache miss → fetch network → simpan ke cache
      │
      ├── WebSocket (/ws)?
      │       └── Bypass service worker (WS tidak bisa di-cache)
      │
      ├── HTTP API (/auth, /status)?
      │       └── Network Only (selalu ke server)
      │
      └── index.html?
              └── Network First → berhasil → return + update cache
                               → gagal (offline) → return dari cache
```

### Precache List

File yang di-precache saat SW install:

```javascript
const PRECACHE_VERSION = 'v1.2.0'
const PRECACHE_URLS = [
  '/',
  '/static/js/main.js',
  '/static/js/store.js',
  '/static/js/dom.js',
  '/static/js/ws.js',
  '/static/css/tokens.css',
  '/static/css/base/reset.css',
  '/static/vendor/tabler-icons.min.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
]
```

**Audit rutin:** pastikan semua file JS/CSS utama masuk ke list ini saat ada file baru ditambahkan.

### Update Strategy

```javascript
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(PRECACHE_VERSION)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())   // aktifkan segera
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== PRECACHE_VERSION)
          .map(key => caches.delete(key))   // hapus cache lama
      )
    ).then(() => self.clients.claim())
  )
})
```

Saat versi baru di-deploy:
1. Ganti `PRECACHE_VERSION` ke versi baru
2. SW baru akan install di background
3. Saat tab ditutup & dibuka ulang → SW baru aktif → cache lama dihapus

### Offline Fallback

Jika user offline dan mengakses halaman yang tidak di-cache:

```javascript
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match('/'))   // fallback ke index.html dari cache
    )
  }
})
```

---

## Icon Generation

Icon PWA di-generate via `automation/generate_icons.py` dari SVG sumber.

```bash
python automation/generate_icons.py
# Output: web/static/icons/icon-192.png, icon-512.png
```

Icon menggunakan `purpose: "any maskable"` — cocok untuk semua platform (Android adaptive icon, iOS, Desktop).

---

## Cara Install LunaWave sebagai PWA

### Desktop (Chrome/Edge)

1. Buka LunaWave di browser
2. Klik ikon install di address bar (atau menu → Install LunaWave)
3. Konfirmasi → app terbuka sebagai window terpisah

### Mobile (Android)

1. Buka di Chrome
2. Banner "Add to Home Screen" muncul otomatis setelah beberapa kunjungan
3. Atau: menu ⋮ → Add to Home Screen

### Mobile (iOS Safari)

1. Buka di Safari
2. Share button → Add to Home Screen

---

## Batasan PWA

| Fitur | Status | Catatan |
|---|---|---|
| Offline playback | ⚠️ Terbatas | Hanya track yang sudah didownload ke `cache/mp3/` |
| Background audio | ✅ | Media Session API + native audio element |
| Push notifications | ❌ Belum | Tidak diimplementasikan |
| File System Access | ❌ | Tidak relevan untuk use case ini |

---

## Media Session API

LunaWave menggunakan **Media Session API** agar kontrol media muncul di lock screen / notification panel.

```javascript
// Diupdate setiap kali track berubah
navigator.mediaSession.metadata = new MediaMetadata({
  title: track.title,
  artist: track.artist,
  artwork: [{ src: track.thumbnail_url, sizes: '96x96', type: 'image/jpeg' }]
})

navigator.mediaSession.setActionHandler('play',         () => ws.send({ cmd: 'pause' }))
navigator.mediaSession.setActionHandler('pause',        () => ws.send({ cmd: 'pause' }))
navigator.mediaSession.setActionHandler('nexttrack',    () => ws.send({ cmd: 'skip_next' }))
navigator.mediaSession.setActionHandler('previoustrack',() => ws.send({ cmd: 'skip_prev' }))
```

---

## Dokumen Terkait

- [frontend/ui_architecture.md](ui_architecture.md) — Struktur JS & CSS keseluruhan
- [devops/release.md](../devops/release.md) — Update `PRECACHE_VERSION` saat release
