# Routing

← [frontend/ui_architecture.md](ui_architecture.md) | [Blueprint.md](../Blueprint.md)

---

## Dua Jenis Routing di Frontend

| Jenis | Arah | File |
|---|---|---|
| **WS Message Routing** | Server → Client | `ws.js` |
| **Event Routing** | User → Server | `events/index.js` + `events/*.js` |

---

## WS Message Routing (Server → Client)

`ws.js` menerima semua pesan masuk dan mendistribusikan ke render function yang tepat.

```javascript
// ws.js
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)

  switch (msg.type) {
    case 'full_state':
      applyFullState(msg)
      renderFullState(store)           // render/full-state.js
      break

    case 'state':
      applyPartialState(msg)
      if (msg.playback)  renderPlayer(store.playback)
      if (msg.queue)     renderQueue(store.queue)
      if (msg.radio)     renderRadioTab(store.radio)
      break

    case 'lyric_line':
      renderLyricLine(msg)             // render/lyrics.js
      break

    case 'download_progress':
      applyDownloadUpdate(msg)
      renderDownloadStatus(store.downloads)
      break

    case 'search_results':
      store.ui.searchResults = msg.results
      renderSearch(msg.results)        // render/search.js
      break

    case 'discover_results':
      renderDiscoverTab(msg.results)   // render/discover-tab.js
      break

    case 'error':
      showToast(msg.message, 'error')  // utils/toast.js
      break

    default:
      console.warn('Unknown message type:', msg.type)
  }
}
```

### Prinsip WS Routing

- `ws.js` hanya routing — tidak ada logic render di dalamnya
- Setiap `type` punya handler tunggal — tidak ada kondisi bercabang dalam satu handler
- Error tidak di-throw — selalu `showToast()` ke user

---

## Event Routing (User → Server)

User action dari DOM dikirim sebagai command WS ke server.

### Mount Point (`events/index.js`)

```javascript
// events/index.js
import { mountTransportEvents }       from './transport-events.js'
import { mountProgressEvents }         from './progress-events.js'
import { mountQueueEvents }            from './queue-events.js'
import { mountSearchEvents }           from './search-input-events.js'
import { mountLyricsEvents }           from './lyrics-events.js'
import { mountSettingsEvents }         from './settings-events.js'
import { mountActionModalEvents }      from './action-modal-events.js'
import { mountClickDelegationEvents }  from './click-delegation-events.js'
import { mountKeyboardShortcutEvents } from './keyboard-shortcut-events.js'

export function mountAllEvents() {
  mountTransportEvents()
  mountProgressEvents()
  mountQueueEvents()
  mountSearchEvents()
  mountLyricsEvents()
  mountSettingsEvents()
  mountActionModalEvents()
  mountClickDelegationEvents()
  mountKeyboardShortcutEvents()
}
```

Dipanggil sekali dari `main.js` setelah DOM ready.

---

### Transport Events (`transport-events.js`)

```javascript
// Peta: DOM element → WS command
const TRANSPORT_MAP = {
  '#btn-play':      () => ws.send({ cmd: 'pause' }),          // toggle
  '#btn-skip-next': () => ws.send({ cmd: 'skip_next' }),
  '#btn-skip-prev': () => ws.send({ cmd: 'skip_prev' }),
  '#btn-stop':      () => ws.send({ cmd: 'stop' }),
  '#btn-mute':      () => ws.send({ cmd: 'set_volume', payload: { volume: 0 } }),
}
```

---

### Progress Events (`progress-events.js`)

Seek bar memerlukan handling khusus — drag state harus dikelola agar tidak konflik dengan position ticker.

```javascript
let isSeeking = false

progressBar.addEventListener('mousedown', () => {
  isSeeking = true
  stopPositionTicker()       // jangan update posisi saat drag
})

progressBar.addEventListener('mouseup', (e) => {
  const position = computeSeekPosition(e)
  ws.send(JSON.stringify({ cmd: 'seek', payload: { position } }))
  isSeeking = false
  startPositionTicker()
})

// Touch events untuk mobile
progressBar.addEventListener('touchstart', ...)
progressBar.addEventListener('touchend', ...)
```

---

### Click Delegation (`click-delegation-events.js`)

Untuk list item yang di-render secara dinamis (queue, search results), listener dipasang di parent container — bukan per item.

```javascript
// Delegasi di queue list
dom.queueList.addEventListener('click', (e) => {
  const item = e.target.closest('[data-video-id]')
  if (!item) return

  const videoId = item.dataset.videoId

  if (e.target.matches('.btn-remove')) {
    const index = parseInt(item.dataset.index)
    ws.send(JSON.stringify({ cmd: 'queue_remove', payload: { index } }))
    return
  }

  if (e.target.matches('.btn-play-now')) {
    ws.send(JSON.stringify({ cmd: 'play', payload: { video_id: videoId } }))
    return
  }
})
```

---

### Keyboard Shortcuts (`keyboard-shortcut-events.js`)

```javascript
const SHORTCUTS = {
  ' ':           () => ws.send({ cmd: 'pause' }),             // Space = toggle pause
  'ArrowRight':  () => seekRelative(+10),                     // +10 detik
  'ArrowLeft':   () => seekRelative(-10),                     // -10 detik
  'ArrowUp':     () => adjustVolume(+5),                      // volume +5
  'ArrowDown':   () => adjustVolume(-5),                      // volume -5
  'm':           () => toggleMute(),
  'l':           () => toggleLyrics(),
  'n':           () => ws.send({ cmd: 'skip_next' }),
}

document.addEventListener('keydown', (e) => {
  // Jangan intercept jika focus di input/textarea
  if (e.target.matches('input, textarea, [contenteditable]')) return
  SHORTCUTS[e.key]?.()
})
```

---

## Queue Drag & Drop (`queue-events.js`)

Reorder queue menggunakan native drag & drop API.

```javascript
// State drag
let dragSrcIndex = null

function onDragStart(e) {
  dragSrcIndex = parseInt(e.currentTarget.dataset.index)
  e.currentTarget.classList.add('dragging')
}

function onDrop(e) {
  const dropIndex = parseInt(e.currentTarget.dataset.index)
  if (dragSrcIndex === dropIndex) return

  ws.send(JSON.stringify({
    cmd: 'queue_reorder',
    payload: { from: dragSrcIndex, to: dropIndex }
  }))
  // Store & render akan diupdate saat server broadcast queue_updated
}
```

---

## Search Debounce (`search-input-events.js`)

```javascript
let searchTimer = null

dom.searchInput.addEventListener('input', (e) => {
  clearTimeout(searchTimer)

  const query = e.target.value.trim()
  store.ui.searchQuery = query

  if (query.length < 2) return  // minimum 2 karakter

  searchTimer = setTimeout(() => {
    ws.send(JSON.stringify({ cmd: 'search', payload: { query } }))
  }, 300)  // debounce 300ms
})
```

---

## Dokumen Terkait

- [frontend/state_management.md](state_management.md) — Bagaimana state diupdate setelah routing
- [frontend/ui_architecture.md](ui_architecture.md) — Render functions yang dipanggil setelah routing
- [backend/api.md](../backend/api.md) — Format command WS yang dikirim ke server
