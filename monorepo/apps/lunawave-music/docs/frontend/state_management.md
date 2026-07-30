# State Management

← [frontend/ui_architecture.md](ui_architecture.md) | [Blueprint.md](../Blueprint.md)

---

## Prinsip Dasar

Frontend LunaWave **tidak menyimpan state kanonik**. Server adalah satu-satunya source of truth.

```
Server AppState
      │
      │  WebSocket broadcast
      ▼
store.js  (cerminan, bukan authority)
      │
      │  render functions
      ▼
    DOM
```

Frontend hanya boleh melakukan **optimistic update** sementara menunggu konfirmasi server — dan harus siap di-overwrite oleh state dari server.

---

## `store.js` — Struktur

```javascript
// State lengkap store (flat, bukan nested)
const store = {
  // --- Server state (selalu di-sync dari server via Object.assign) ---
  status: "IDLE",            // "IDLE" | "LOADING" | "PLAYING" | "PAUSED"
  playback_mode: "QUEUE",   // "QUEUE" | "RADIO"
  audio_output: "browser",  // "browser" | "device"
  current_track: null,       // TrackInfo | null
  position: 0,               // detik (float)
  volume: 80,                // 0–100
  playback_speed: 1.0,       // kecepatan putar (0.25–4.0)
  loop_mode: "off",          // "off" | "track" | "queue"
  crossfade_enabled: false,  // boolean
  sponsorblock_active: false,// boolean
  queue: [],                 // TrackInfo[]
  radio_queue: [],           // TrackInfo[]
  history_count: 0,          // jumlah track yang pernah diputar
  lyrics_lines: [],          // string[]
  lyrics_index: 0,           // index baris lirik aktif
  lyrics_offset: 0,          // offset waktu lirik (detik)
  download_progress: null,   // DownloadProgress | null
  error_msg: null,           // string | null
  is_online: true,           // boolean
  server_ts: 0,              // server timestamp

  // --- UI state lokal (tidak dari server, tidak pernah di-overwrite) ---
  userRole: "portal",       // "portal" | "client" | "admin"
  active_tab: "home",        // "home" | "queue" | "search" | "discover"
  search_results: [],
  discover_recent: [],
  discover_cached: [],
}
```

---

## Update Store

Store tidak punya setter khusus — diupdate langsung. Pattern yang digunakan:

```javascript
// Partial update (dari server state broadcast)
function applyPartialState(msg) {
  if (msg.playback)  Object.assign(store.playback, msg.playback)
  if (msg.queue)     store.queue = msg.queue
  if (msg.volume !== undefined) store.volume = msg.volume
  if (msg.mode)      store.mode = msg.mode
  if (msg.downloads) store.downloads = msg.downloads
  if (msg.radio !== undefined) store.radio = msg.radio
}

// Full state update (setelah reconnect)
function applyFullState(msg) {
  store.playback   = msg.playback
  store.queue      = msg.queue
  store.volume     = msg.volume
  store.mode       = msg.mode
  store.radio      = msg.radio
  store.downloads  = msg.downloads
}
```

---

## Optimistic Update

Digunakan untuk feedback instan sebelum server merespons.

```javascript
// events/transport-events.js
async function handlePlayClick(video_id) {
  // 1. Optimistic: ubah UI segera
  store.playback.status = 'playing'
  renderPlayer(store.playback)

  // 2. Kirim ke server
  ws.send(JSON.stringify({ cmd: 'play', payload: { video_id } }))

  // 3. Server akan broadcast state sebenarnya
  // → applyPartialState() akan overwrite jika berbeda
}
```

**Kapan TIDAK melakukan optimistic update:**
- Operasi yang hasilnya tidak bisa diprediksi (search, radio start)
- Operasi yang bisa gagal (download)

---

## State Sync via WebSocket

### Skenario Normal

```
User klik Play
      │
      ▼
ws.send(CMD_PLAY)
      │
      ▼ (server proses ~50ms)
ws.onmessage → {type: "state", playback: {status: "playing", ...}}
      │
      ▼
applyPartialState(msg)
      │
      ▼
renderPlayer(store.playback)
```

### Skenario Reconnect

Koneksi WS putus (network, sleep, timeout). Saat reconnect:

```
ws.onopen (reconnect)
      │
      ▼
Server kirim otomatis: {type: "full_state", ...}
      │
      ▼
applyFullState(msg)
      │
      ▼
renderFullState()   ← render ulang semua panel dari state baru
```

Frontend tidak perlu request full_state secara eksplisit — server selalu kirim otomatis saat koneksi baru.

### Reconnect Strategy

```javascript
let reconnectDelay = 1000   // mulai dari 1 detik

ws.onclose = () => {
  store.ui.isConnected = false
  store.ui.isReconnecting = true
  renderConnectionStatus()

  setTimeout(() => {
    connectWebSocket()
    reconnectDelay = Math.min(reconnectDelay * 2, 30000)  // max 30 detik
  }, reconnectDelay)
}

ws.onopen = () => {
  store.ui.isConnected = true
  store.ui.isReconnecting = false
  reconnectDelay = 1000   // reset
  renderConnectionStatus()
  // full_state akan datang dari server segera setelah ini
}
```

---

## Position Tracking

Posisi playback bergerak setiap detik. Server **tidak** broadcast `position` setiap detik (terlalu banyak traffic). Sebaliknya:

```javascript
// Frontend melakukan local interpolation
let positionTimer = null

function startPositionTicker() {
  positionTimer = setInterval(() => {
    if (store.playback.status === 'playing') {
      store.playback.position += 1
      renderProgressBar(store.playback.position, store.playback.duration)
    }
  }, 1000)
}
```

Server hanya broadcast `position` saat:
- Track mulai diputar (initial sync)
- User seek
- Track selesai

---

## UI State

State UI lokal (`store.ui`) tidak pernah dikirim ke server dan tidak pernah di-overwrite oleh server.

```javascript
// Tab navigation — pure local state
function switchTab(tabName) {
  store.ui.activeTab = tabName
  renderTabVisibility()
}

// Settings sheet
function openSettings() {
  store.ui.settingsOpen = true
  dom.settingsSheet.classList.add('open')
}
```

---

## Dokumen Terkait

- [frontend/routing.md](routing.md) — Bagaimana WS message di-route ke fungsi yang tepat
- [frontend/ui_architecture.md](ui_architecture.md) — Komponen JS yang membaca store
- [backend/api.md](../backend/api.md) — Format state yang diterima dari server
