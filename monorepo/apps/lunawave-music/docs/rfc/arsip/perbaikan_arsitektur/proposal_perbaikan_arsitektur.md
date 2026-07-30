---
title: Proposal Perbaikan Arsitektur Backend & Frontend — LunaWave
version: 1.0
tanggal: 2026-07-26
status: DRAFT — untuk direview
target rilis: LunaWave (usulan, non-breaking, bertahap per fase)
author: AI audit session (Claude) — atas permintaan pemilik project
scope: core/, server/, engine/, persistence/, web/static/shared/js/
---

# Proposal Perbaikan Arsitektur Backend & Frontend

### Dari "Governance Matang, Desain Internal Bocor" ke Boundary yang Benar-Benar Ditegakkan

> **Ringkasan satu paragraf:** Audit mendalam ke codebase (bukan hanya
> `docs/architecture/`) menemukan bahwa tooling governance LunaWave
> (`architecture_lint.py`, ADR, PATCHLOG) sudah sangat matang di level
> **arah import antar folder**, tetapi tidak menegakkan kualitas desain
> **di dalam** boundary tersebut. Delapan temuan konkret — 4 di backend,
> 4 di frontend — menunjukkan pola berulang: singleton sebagai pengganti
> dependency injection, circular-dependency yang "diselesaikan" dengan
> deferred import, command routing tanpa validasi skema, dan frontend
> state management berbasis mutable global object yang sudah terbukti
> menghasilkan race condition berulang (`FIX-PAUSE-RACE-01`,
> `FIX-RADIO-08`). Proposal ini merinci root cause tiap temuan, desain
> perbaikan dengan sketsa kode, dan rencana rollout 7 fase yang masing-masing
> **independen dan bisa dihentikan** tanpa meninggalkan kode dalam keadaan
> rusak — konsisten dengan aturan "jangan refactor 2 tahap sekaligus dalam
> 1 commit" di `AI_CONTEXT.md`.

---

## 1. Latar Belakang

Audit ini dilakukan dengan membaca kode sumber langsung (bukan mengandalkan
`docs/architecture/overview.md` atau output `doctor.py`, yang keduanya
melaporkan status PASS 100/100 di semua checker). Temuan berikut hanya
muncul setelah membaca isi file `core/command_bus.py`, `core/event_bus.py`,
`server/handlers/websocket.py`, `engine/playback/controller.py`, dan
`web/static/shared/js/{store,ws}.js` baris per baris, serta menjalankan
`grep` struktural terhadap pola import di 27 file backend.

Kesimpulan utama: **checker yang ada (`architecture_lint.py`) hanya
memvalidasi bahwa `engine` tidak meng-import `server`, dsb. — bukan
_bagaimana_ kedua sisi saling berkomunikasi di dalam boundary yang sudah
benar itu.** Empat dari delapan temuan di bawah ini lolos dari semua
checker yang ada karena secara teknis tidak melanggar arah import,
meski secara desain problematik.

## 2. Kondisi Saat Ini (As-Is) — Temuan Audit

| # | Area | Temuan | Lokasi | Lolos checker? |
|---|---|---|---|---|
| A | Backend | `CommandBus`/`EventBus` module-level singleton, bukan DI | `core/command_bus.py:115`, `core/event_bus.py:159` | Ya |
| B | Backend | 75 deferred import di 27 file — circular-dependency pressure | grep lintas `server/`, `engine/`, `core/`, `persistence/` | Ya |
| C | Backend | WS command dispatch berbasis string set, tanpa validasi skema | `server/handlers/websocket.py:53-85`, `ws_playback.py` | Ya |
| D | Backend | "Circuit breaker" hanya komentar + integer counter, bukan state machine eksplisit | `engine/playback/controller.py:103-109` | Ya |
| E | Frontend | `store.js` adalah plain mutable object, bukan reactive store | `web/static/shared/js/store.js:1-41` | Ya (tidak ada linter state) |
| F | Frontend | Koordinasi lintas-modul lewat `globalThis.*` alih-alih module state | `store.js:57-71`, `ws.js:119-121` | Ya |
| G | Frontend | `ws.js` god-module: transport + parsing + state + DOM + business logic dalam 1 file, 451 baris | `web/static/shared/js/ws.js` | Ya |
| H | Frontend | Halaman monolitik (`index.html` 48K, `admin-logs.html`+`.js` 36K+36K) tanpa komponenisasi | `web/static/pages/` | Ya |

Detail per temuan ada di §3 (backend) dan §4 (frontend).

## 3. Backend — Root Cause & Desain Perbaikan

### A. Singleton `CommandBus`/`EventBus` vs. pola DI yang sudah dipakai untuk `AppState`

**Bukti kontradiksi internal:** `server/app.py` sudah benar menerapkan DI
untuk `AppState`, `PlaybackController`, `Repositories` lewat `web.AppKey`
(baris 51-61) — pola yang secara eksplisit dipilih untuk *"eliminate
NotAppKeyWarning"* dan konsisten dengan `AI_CONTEXT.md` §Batasan teknis.
Tapi `command_bus = CommandBus()` dan `bus = EventBus()` tetap
module-level singleton yang di-import langsung oleh siapa pun
(`from core.command_bus import command_bus`), termasuk oleh
`engine/playback/controller.py` dan seluruh `server/handlers/ws_*.py`.

**Konsekuensi yang sudah termanifestasi:**
1. `CommandBus.reset()` (command_bus.py:57-61) harus ada semata-mata
   supaya test bisa jalan berulang tanpa `RuntimeError: Command 'X' is
   already registered` — tanda test isolation dipaksa lewat method
   khusus, bukan lewat instansiasi baru per test.
2. Tidak mungkin menjalankan dua `PlaybackController` independen dalam
   satu proses Python (mis. untuk future multi-room/multi-device
   playback) karena keduanya akan register command name yang sama ke
   singleton yang sama → `RuntimeError` langsung di baris kedua register.
3. `EventBus` instance yang sebenarnya dipakai runtime adalah
   `playback_controller.bus` (lihat `event_listeners.py:131`,
   `bus = playback_controller.bus`) — **bukan** `core.event_bus.bus`
   singleton itu sendiri. Artinya ada dua "sumber kebenaran" EventBus
   yang berpotensi membingungkan: singleton module-level yang jarang
   dipakai langsung, vs. instance yang di-pass eksplisit via
   constructor `PlaybackController(bus=..., ...)`. `EventBus` sendiri
   sudah didesain instantiable (bukan pure-static class) — tinggal
   `CommandBus` yang masih bocor lewat singleton.

**Desain yang diusulkan:**

```python
# core/command_bus.py — TIDAK ada lagi module-level instance
class CommandBus:
    ...  # implementasi tidak berubah

# server/app.py — command_bus jadi bagian dari AppKey, sama seperti STATE
COMMAND_BUS: web.AppKey[CommandBus] = web.AppKey("command_bus", CommandBus)

def create_app(playback_controller, ytdlp, repos, command_bus: CommandBus):
    ...
    app[COMMAND_BUS] = command_bus
```

```python
# server/handlers/__init__.py — tambah accessor, pola sama seperti get_state()
def get_command_bus(request) -> CommandBus:
    return request.app[COMMAND_BUS]
```

```python
# server/handlers/ws_playback.py — command_bus di-pass sebagai parameter,
# bukan di-import sebagai singleton
async def handle_playback_command(action: str, data: dict, command_bus: CommandBus):
    if action == "play_track":
        track = dict_to_track(data)
        if track:
            await command_bus.execute(CMD_PLAY_TRACK, track)
    ...
```

`websocket.py` tinggal `command_bus = get_command_bus(request)` sekali di
`ws_handler()`, lalu diteruskan ke semua `handle_*_command()`. Ini
**murni mechanical refactor** (ubah singleton import → parameter
passing) — tidak mengubah 1 baris pun logika command itu sendiri, jadi
risiko regresi rendah, tapi menyentuh banyak file (`ws_playback.py`,
`ws_queue.py`, `ws_discovery.py`, `ws_download.py`, `ws_cache.py`,
`ws_chat.py`, `websocket.py`, `event_listeners.py`, `main.py`,
`bootstrap/services.py`) — perlu 1 sesi khusus, tidak digabung task lain.

**Manfaat konkret:** `CommandBus.reset()` bisa dihapus (test cukup
instansiasi `CommandBus()` baru per test), dan membuka jalan (bukan
mengimplementasikan sekarang) untuk multi-instance kalau suatu saat
dibutuhkan — tanpa itu pun, kode jadi eksplisit soal dependency-nya,
sesuai prinsip yang sudah dipilih project untuk `AppState`.

### B. 75 deferred import — circular-dependency yang belum diselesaikan

**Bukti:** `grep -rn "^\s\+from \|^\s\+import "` (di luar
`TYPE_CHECKING`) mengembalikan 75 baris di 27 file produksi. Menelusuri
sampelnya menunjukkan **dua motif berbeda yang bercampur**, dan
keduanya perlu penanganan berbeda:

1. **Motif circular-import asli** — misal
   `server/handlers/websocket.py:231` (`from server.handlers.ws_cache
   import handle_cache_command`) dan `:235` (`ws_chat`) diimpor lokal
   di dalam `handle_ws_message()`, bukan di top-level, kemungkinan besar
   karena `ws_cache.py`/`ws_chat.py` balik mengimpor sesuatu dari
   `server.handlers` package `__init__.py` yang juga dipakai
   `websocket.py` — pola klasik circular import dua arah dalam satu
   package.
2. **Motif test-patchability** — `main.py` mengimpor
   `server.app.create_app` secara lokal di dalam `run_server()`, dengan
   komentar eksplisit *"agar ... tetap bisa di-patch dari test lewat
   `server.app.<nama>`"*. Ini **bukan** circular import, tapi
   penyalahgunaan lazy-import untuk mengakali `unittest.mock.patch`
   yang butuh target berupa atribut modul yang belum di-resolve saat
   import time.

**Root cause struktural motif #1:** `server/handlers/__init__.py`
kemungkinan menjadi *hub* yang diimpor balik oleh submodule-nya sendiri
(`ws_cache`, `ws_chat`, dll. kemungkinan mengimpor helper
`get_state`/`get_manager`/dll. dari `server.handlers`, sementara
`server.handlers.websocket` — bagian dari package yang sama — juga
mengimpor mereka). Solusi yang benar bukan menambah lazy-import baru,
tapi **memecah `server/handlers/__init__.py`** menjadi:
- `server/handlers/context.py` — berisi HANYA accessor
  (`get_state`, `get_manager`, `get_repos`, `get_ytdlp`,
  `get_playback_controller`, dan `get_command_bus` baru dari §A),
  tanpa dependency ke handler manapun.
- `server/handlers/__init__.py` — tetap ada untuk backward-compat
  re-export (`from server.handlers.context import *`), tapi bukan
  tempat logic baru.

Dengan accessor dipindah ke leaf module tanpa dependency balik, seluruh
`ws_*.py` bisa `from server.handlers.context import get_state` di
top-level tanpa risiko circular — menghilangkan kebutuhan deferred
import motif #1 di titik-titik yang sudah diverifikasi.

**Solusi motif #2:** Untuk test-patchability, pola yang benar bukan
deferred-import tapi **dependency injection eksplisit ke fungsi yang
diuji**, atau — kalau memang tidak ingin mengubah signature — pakai
`monkeypatch.setattr(module, "create_app", fake)` dengan
`import server.app as server_app` di level module test, lalu
`server_app.create_app` di-patch sebelum `run_server()` dipanggil. Ini
tetap valid dengan `create_app` diimpor top-level di `main.py`, karena
patch target-nya `server.app.create_app` (atribut modul), bukan
`main.create_app` (nama lokal) — mock target tetap sama persis dengan
yang sudah dipakai test saat ini, jadi test tidak perlu diubah.

**Rencana eksekusi:** audit ke-75 titik ini **tidak** dilakukan sekaligus.
Diusulkan skrip baru `automation/import_audit.py` yang mengklasifikasi
tiap deferred import sebagai `CIRCULAR` atau `PATCHABILITY` (heuristik:
cek apakah target import balik mengimpor modul pemanggil — kalau ya,
`CIRCULAR`; kalau tidak dan ada test yang mem-patch nama itu, `PATCHABILITY`),
lalu hasilnya jadi checklist untuk fase migrasi bertahap (lihat §5 Fase 2).

### C. WS command dispatch tanpa validasi skema

**Bukti:** `handle_playback_command()` di `ws_playback.py` melakukan
`data.get("volume", 80)` lalu `int(vol)` tanpa try/except lokal — kalau
client mengirim `{"volume": "abc"}`, `ValueError` baru tertangkap di
except generik `websocket.py:240-248`, yang mengirim `str(e)` mentah ke
client (`"invalid literal for int() with base 10: 'abc'"`) — pesan
error implementasi Python bocor ke UI, bukan pesan domain yang berarti.
Pola serupa berulang di `set_speed`, `lyrics_offset`, `set_sleep_timer`,
dll. — total 19 command playback + 6 command queue tanpa skema
terpusat.

**Desain yang diusulkan** — command schema registry berbasis
`dataclass`/`TypedDict` per command, divalidasi **sebelum** masuk
`command_bus.execute()`:

```python
# server/handlers/ws_schemas.py (baru)
from dataclasses import dataclass

class WsValidationError(Exception):
    """Pesan siap-tampil untuk client, terpisah dari internal exception."""

@dataclass
class VolumeSetPayload:
    volume: int

    @classmethod
    def parse(cls, data: dict) -> "VolumeSetPayload":
        raw = data.get("volume", 80)
        try:
            vol = int(raw)
        except (TypeError, ValueError):
            raise WsValidationError("Nilai volume harus berupa angka.")
        if not 0 <= vol <= 100:
            raise WsValidationError("Volume harus antara 0-100.")
        return cls(volume=vol)
```

```python
# server/handlers/ws_playback.py — pemanggilan jadi eksplisit gagal-cepat
elif action == "volume_set":
    payload = VolumeSetPayload.parse(data)
    await command_bus.execute(CMD_VOLUME_SET, {"volume": payload.volume})
```

```python
# server/handlers/websocket.py — WsValidationError ditangani terpisah
# dari Exception generik, supaya pesannya memang dimaksudkan utk user
except WsValidationError as e:
    await ws.send_str(json.dumps({"type": "error", "data": str(e)}))
except Exception as e:
    ...  # existing generic handler, log internal detail, pesan generik ke client
```

Ini **tidak** mengganti `aiohttp` atau menambah library validasi berat
(Pydantic dkk) sesuai batasan "tidak boleh ganti framework" — cukup
`dataclass` stdlib. Migrasi dilakukan **command per command**, dimulai
dari yang paling sering menerima input numerik user (`volume_set`,
`set_speed`, `lyrics_offset`, `set_sleep_timer`) karena itu yang paling
rawan `ValueError` mentah bocor ke client.

### D. Circuit breaker implisit → state machine eksplisit

**Bukti:** komentar di `controller.py:103-109` menjelaskan bahwa
`_retry_count` berfungsi sebagai "circuit breaker LINTAS-TRACK", tapi
implementasinya hanya integer yang di-increment/reset di
`failure_ops.py`. Semantik penting (kapan berhenti total, kapan reset)
hanya hidup di komentar — kalau kontributor baru mengubah
`failure_ops.py` tanpa membaca komentar di file lain (`controller.py`),
perilaku circuit-breaker bisa rusak diam-diam tanpa test yang
menegaskan invariant-nya secara eksplisit.

**Desain yang diusulkan:**

```python
# engine/playback/circuit_breaker.py (baru)
from enum import Enum, auto

class BreakerState(Enum):
    CLOSED = auto()   # normal, boleh advance ke track berikutnya
    OPEN = auto()     # berhenti total, tidak boleh advance otomatis

class PlaybackCircuitBreaker:
    """Circuit breaker lintas-track: menghitung kegagalan play_track
    BERTURUT-TURUT (track apapun), bukan retry per-track yang sama.
    Dibuka (OPEN) setelah `threshold` kegagalan beruntun."""

    def __init__(self, threshold: int = 3):
        self._threshold = threshold
        self._consecutive_failures = 0
        self.state = BreakerState.CLOSED

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self.state = BreakerState.CLOSED

    def record_failure(self) -> bool:
        """Return True jika breaker baru saja OPEN akibat kegagalan ini."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self.state = BreakerState.OPEN
            return True
        return False

    def can_advance(self) -> bool:
        return self.state is BreakerState.CLOSED
```

`PlaybackController` tinggal punya `self._breaker =
PlaybackCircuitBreaker(threshold=3)` menggantikan `self._retry_count`,
dan `failure_ops.py` memanggil `self.controller._breaker.record_failure()`
alih-alih increment manual. Perilaku identik dengan sebelumnya, tapi
sekarang:
- Nama (`BreakerState.OPEN`) menjelaskan diri sendiri tanpa perlu baca
  komentar panjang.
- Invariant bisa ditest langsung sebagai unit (`test_circuit_breaker.py`)
  terpisah dari `PlaybackController` yang berat mock-nya, tanpa perlu
  setup mpv/event bus sama sekali.
- Threshold (3) jadi parameter eksplisit, bukan angka ajaib
  tersembunyi di percabangan `except`.

## 4. Frontend — Root Cause & Desain Perbaikan

Batasan tetap dihormati penuh: **tidak menambah framework JS**. Semua
solusi di bawah murni JavaScript native (ES modules, `Proxy`, custom
event target) — tidak ada React/Vue/dsb., konsisten dengan
`AI_CONTEXT.md` dan ADR-0006.

### E. `store.js` — plain object → reactive store minimal

**Bukti konkret dampaknya:** komentar `FIX-PAUSE-RACE-01` di
`store.js:43-55` sendiri mengakui bahwa sebelumnya `ws.js` dan
`playback-sync.js` **masing-masing menyimpan `globalThis.lastToggleTime`
dengan grace-window berbeda** (1200ms vs 1500ms) untuk konsep yang
sama — persis jenis bug yang muncul ketika state tidak punya satu
sumber kebenaran yang reactive, sehingga tiap modul konsumen terpaksa
menyimpan salinan/derivasi state-nya sendiri secara manual.

**Desain yang diusulkan** — `Proxy`-based store dengan subscription
granular, tanpa mengubah *shape* data (field yang sama persis), supaya
migrasi bisa dilakukan bertahap per-consumer:

```javascript
// web/static/shared/js/store.js — versi baru
const listeners = new Map(); // key: field name, value: Set<callback>
const wildcardListeners = new Set(); // dipanggil utk SEMUA perubahan

function notify(key, value, oldValue) {
    (listeners.get(key) || []).forEach(fn => fn(value, oldValue));
    wildcardListeners.forEach(fn => fn(key, value, oldValue));
}

function createReactiveStore(initial) {
    return new Proxy(initial, {
        set(target, key, value) {
            const oldValue = target[key];
            if (oldValue === value) return true; // no-op, jangan notify kalau tidak berubah
            target[key] = value;
            notify(key, value, oldValue);
            return true;
        }
    });
}

export const store = createReactiveStore(createStore());

export function onStoreChange(key, callback) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(callback);
    return () => listeners.get(key).delete(callback); // unsubscribe fn
}
```

**Poin krusial:** `store.status = "PLAYING"` di kode existing manapun
**tetap jalan tanpa perubahan** — `Proxy` transparan terhadap syntax
assignment biasa. Yang berubah hanya: modul yang butuh tahu perubahan
field tertentu **bisa subscribe langsung ke field itu**
(`onStoreChange("status", handler)`) alih-alih menebak lewat
`bus("player:btn-changed")` generik yang dipanggil manual di banyak
tempat berbeda (lihat `ws.js:313-326`, empat `bus(...)` dipanggil
manual setiap `handleServerMessage` case `"progress"`).

Ini **tidak** menghapus `bus.js` (event bus custom yang sudah ada) —
`onStoreChange` melengkapi untuk perubahan *state*, sementara `bus.js`
tetap dipakai untuk *event* murni (klik tombol, dsb.) yang bukan
perubahan state tersimpan.

### F. `globalThis.*` sebagai kanal koordinasi implisit → state eksplisit di store

Menyambung §E, `pendingToggleTarget`/`toggleSentAt`/`audioBlocked`
seharusnya jadi field store biasa, bukan `globalThis`:

```javascript
// store.js — tambahkan sebagai field asli, bukan globalThis
function createStore() {
    return {
        ...,
        _pendingToggleTarget: null,
        _toggleSentAt: 0,
    };
}

export function markPendingToggle(target) {
    store._pendingToggleTarget = target;
    store._toggleSentAt = Date.now();
}

export function isPendingToggleActive(matchStatus) {
    if (!store._pendingToggleTarget) return false;
    if (Date.now() - store._toggleSentAt > PENDING_TOGGLE_TIMEOUT_MS) {
        store._pendingToggleTarget = null;
        return false;
    }
    return store._pendingToggleTarget === matchStatus;
}
```

Prefix `_` menandai "internal coordination state", bukan domain state
untuk di-render — konsisten dipakai di semua field serupa
(`_lastToggleTime` dan sejenisnya yang saat ini tersebar sebagai
`globalThis.*` di `ws.js` dan `playback-sync.js`). `globalThis.ws`,
`globalThis.audioBlocked`, `globalThis.ChatModule`,
`globalThis.safeStorage` masing-masing diaudit satu per satu di Fase 4
(§5) — sebagian (`safeStorage`) memang lapisan abstraksi
localStorage yang wajar sebagai util global, sebagian lain
(`pendingToggleTarget`) murni state yang harusnya di store.

### G. `ws.js` god-module → dipecah 3 lapis

**Bukti ukuran & tanggung jawab campur:** `ws.js` 451 baris berisi
(1) transport (`wsConnect`, reconnect backoff, visibilitychange
listener), (2) message router (`handleServerMessage`, switch-case 15+
tipe pesan), (3) mutasi state + panggilan `bus()`, dan (4) manipulasi
DOM langsung (`dom.statusDot.classList.remove("offline")` di
`renderHeader()`, baris 430-447). Empat tanggung jawab berbeda dalam
satu file membuat perubahan kecil di satu aspek (mis. tambah 1 message
type baru) berisiko menyentuh kode reconnect yang sudah stabil.

**Desain yang diusulkan** — split jadi 3 modul, **tanpa mengubah
public API yang dipanggil dari luar** (`wsConnect`, `wsSend` tetap
diekspor dari `ws.js` sebagai re-export, sehingga file lain yang sudah
`import { wsSend } from "./ws.js"` tidak perlu diubah):

```
web/static/shared/js/ws/
├── transport.js     # wsConnect, reconnect backoff, visibilitychange
│                     # TIDAK tahu apa isi pesan — cuma kirim/terima raw JSON
├── router.js         # handleServerMessage: switch-case, tapi tiap case
│                     # HANYA memanggil handler dari message-handlers/*,
│                     # tidak mutasi store langsung di sini
└── message-handlers/
    ├── auth-messages.js       # "auth_status", "setup_status"
    ├── playback-messages.js   # "state", "progress", "lyrics"
    ├── discover-messages.js   # "discover_data", "search_results", dst.
    └── chat-messages.js       # "chat_history", "chat_message"
```

```javascript
// web/static/shared/js/ws/transport.js
import { routeMessage } from "./router.js";

export function wsConnect() {
    // ... logika reconnect PERSIS sama seperti sekarang, tidak berubah
    ws.onmessage = (event) => {
        try {
            routeMessage(JSON.parse(event.data));
        } catch (e) {
            console.error("WS parse error:", e);
        }
    };
}
```

```javascript
// web/static/shared/js/ws/router.js
import { handlePlaybackMessage } from "./message-handlers/playback-messages.js";
import { handleAuthMessage } from "./message-handlers/auth-messages.js";
// ...

const HANDLERS = {
    auth_status: handleAuthMessage,
    setup_status: handleAuthMessage,
    state: handlePlaybackMessage,
    progress: handlePlaybackMessage,
    lyrics: handlePlaybackMessage,
    // ...
};

export function routeMessage(msg) {
    const handler = HANDLERS[msg.type];
    if (handler) handler(msg);
}
```

```javascript
// web/static/shared/js/ws.js — jadi thin re-export, backward-compat
export { wsConnect, wsSend } from "./ws/transport.js";
export { renderHeader } from "./ws/message-handlers/auth-messages.js";
```

Dengan struktur ini, `renderHeader()` (manipulasi DOM) tetap dekat
dengan message handler yang memicunya (auth/connection status), bukan
tercampur dengan logic audio-sync di `playback-messages.js`. Migrasi
dilakukan **case per case** dari switch-case lama ke handler baru — bisa
berhenti kapan saja tanpa merusak case yang belum dipindah, karena
selama migrasi `router.js` bisa punya fallback: case yang belum ada di
`HANDLERS` tetap diproses lewat switch-case lama sampai semuanya
dipindah.

### H. Halaman monolitik (`index.html` 48K, `admin-logs.*` 36K+36K)

Karena `web/static/pages/app/index.html` masuk daftar "sudah dipindah
tapi bukan dipecah" (lihat `AI_CONTEXT.md` — index.html tidak dipecah
adalah keputusan final sebelumnya, sudah dicabut untuk *lokasi* file
tapi tidak otomatis berarti isinya boleh dipecah bebas), proposal ini
**tidak** mengusulkan pemecahan `index.html` di RFC ini — itu perlu
persetujuan eksplisit terpisah (lihat §6). Yang diusulkan di sini
hanya:
- Audit ukuran: berapa persen dari 48K adalah markup vs. inline
  `<template>`/`<script>` blocks — perlu `view` manual per section
  sebelum diputuskan apakah masalahnya struktural (perlu componentize)
  atau sekadar banyak markup natural untuk aplikasi sekompleks ini.
- **Tidak dieksekusi di RFC ini** — dicatat sebagai item untuk RFC
  terpisah *setelah* Fase 1-4 selesai, supaya tidak menambah 2 refactor
  besar berjalan bersamaan (melanggar aturan governance).

## 5. Rencana Rollout — 7 Fase

Setiap fase independen, bisa dihentikan, dan **wajib** dicatat sebagai
entri terpisah di `docs/PATCHLOG.md` (format v2 field-based, sesuai
`AI_CONTEXT.md`) — tidak digabung jadi satu patch besar.

| Fase | Temuan yang ditutup | Isi | Menyentuh file locked? | Risiko regresi | Effort |
|---|---|---|---|---|---|
| 1 | D | `PlaybackCircuitBreaker` baru + unit test, ganti `_retry_count` | Ya — `controller.py` (izin sudah eksplisit tercatat di komentar `controller.py:96-100` untuk task serupa) | Rendah | Rendah |
| 2 | B | `automation/import_audit.py` baru + klasifikasi 75 titik + pindahkan `server/handlers/context.py` | Tidak (context.py baru, `__init__.py` tetap re-export) | Rendah–sedang | Sedang |
| 3 | C | `ws_schemas.py` baru + migrasi validasi 4 command paling rawan (`volume_set`, `set_speed`, `lyrics_offset`, `set_sleep_timer`) | Tidak | Rendah | Rendah–sedang |
| 4 | A | `CommandBus` jadi `AppKey`, hapus singleton module-level, hapus `reset()` | Ya — `server/handlers/websocket.py` (butuh persetujuan eksplisit sesuai `AI_CONTEXT.md`) | Sedang (menyentuh banyak file sekaligus, meski mekanis) | Sedang–tinggi |
| 5 | E | `store.js` jadi `Proxy`-based, `onStoreChange` baru, field lama tidak berubah nama | Tidak (backward-compat penuh: `store.x = y` tetap jalan) | Rendah | Sedang |
| 6 | F | Migrasi `globalThis.pendingToggleTarget` dkk ke field `_` di store | Tidak | Rendah | Rendah |
| 7 | G | Split `ws.js` → `ws/transport.js` + `ws/router.js` + `ws/message-handlers/*`, migrasi case-per-case | Tidak (re-export tetap dari `ws.js`) | Rendah (fallback ke switch-case lama selama migrasi) | Sedang–tinggi |

Temuan H (§4.H) **sengaja tidak dimasukkan** ke tabel fase — butuh RFC
terpisah dan persetujuan eksplisit sebelum `index.html` disentuh lebih
jauh, sesuai preseden `docs/rfc/arsip/frontend_refactor/`.

**Urutan yang disarankan:** 1 → 3 → 2 → 5 → 6 → 7 → 4. Rasionalnya:
Fase 1 dan 3 paling murni-additive (file baru + swap internal, tanpa
menyentuh banyak caller) sehingga bagus untuk validasi proses RFC ini
dulu dengan risiko terkecil. Fase 4 (singleton → DI) diletakkan
**terakhir** karena paling luas dampaknya (menyentuh hampir semua
`ws_*.py` sekaligus, sesuai catatan risiko di §3.A) — mengerjakannya
setelah Fase 2 (pembersihan `server/handlers/context.py`) akan membuat
Fase 4 lebih mudah karena accessor sudah rapi di satu tempat.

## 6. Non-Negotiable / Governance

- Tidak menambah framework JS (React, Vue, dll.) — seluruh solusi
  frontend murni ES modules + `Proxy` native.
- Tidak mengganti `aiohttp` atau SQLite — validasi command (§3.C) pakai
  `dataclass` stdlib, bukan Pydantic/library baru.
- Fase 4 (§5) menyentuh `server/handlers/websocket.py`, yang masuk
  daftar **"jangan dipecah dulu tanpa persetujuan eksplisit"** di
  `AI_CONTEXT.md` — meski RFC ini tidak memecah file itu (hanya
  mengubah cara `command_bus` diperoleh di dalamnya), tetap **wajib
  mendapat persetujuan eksplisit sebelum eksekusi**, sesuai preseden
  governance yang sudah berlaku.
- Setiap fase = 1 PATCHLOG entry terpisah (`python automation/patchlog.py
  add --type ... --area ... --title ... --reason ... --files ...
  --root-cause ... --solution ...`), tidak digabung.
- Temuan H (`index.html`, `admin-logs.*`) butuh RFC dan persetujuan
  terpisah — **tidak** bagian dari eksekusi RFC ini.
- Setelah tiap fase: jalankan `python automation/doctor.py`,
  `generate_file_index.py`, dan `generate_report.py` sesuai alur wajib
  `AI_CONTEXT.md` §Alur kerja AI.

## 7. Strategi Testing per Fase

| Fase | Test baru yang wajib ditambah |
|---|---|
| 1 | `tests/engine/playback/test_circuit_breaker.py` — unit murni, tanpa mock mpv/event bus |
| 2 | Tidak ada test baru wajib (refactor internal); pastikan seluruh suite `pytest` existing tetap hijau sebagai regression check |
| 3 | `tests/server/handlers/test_ws_schemas.py` — kasus valid, invalid-type, out-of-range per command yang dimigrasi |
| 4 | Perbarui test yang saat ini memanggil `command_bus.reset()` untuk instansiasi `CommandBus()` baru per test; hapus `reset()` setelah migrasi selesai |
| 5 | `tests/frontend/store-reactive.test.js` — pastikan `onStoreChange` terpanggil saat field berubah, TIDAK terpanggil saat nilai sama (no-op check di `Proxy.set`) |
| 6 | Perluas `tests/frontend/pause-race.test.js` (sudah ada, disebut di RFC frontend_refactor sebelumnya) untuk assert `globalThis.pendingToggleTarget` sudah tidak dipakai sama sekali pasca migrasi |
| 7 | Test per `message-handlers/*.js` baru, terpisah dari test transport — memungkinkan test `playback-messages.js` tanpa perlu mock `WebSocket` sama sekali |

## 8. Keputusan yang Perlu Persetujuan User

1. **Urutan fase** — apakah urutan 1→3→2→5→6→7→4 di §5 disetujui, atau
   ada prioritas lain (mis. Fase 4/singleton dulu karena dianggap
   paling mendesak meski paling berisiko)?
2. **Threshold circuit breaker (Fase 1)** — tetap `3` (nilai existing)
   atau ingin dijadikan configurable lewat `config.py`?
3. **Cakupan command yang divalidasi di Fase 3** — cukup 4 command
   paling rawan dulu, atau langsung seluruh `PLAYBACK_CMDS`/`QUEUE_CMDS`
   (25 command) dalam satu fase?
4. **Persetujuan eksplisit untuk Fase 4** menyentuh
   `server/handlers/websocket.py` — kapan boleh dieksekusi, perlu sesi
   khusus terpisah seperti pola `task_breakdown_radio.yaml`?
5. **Temuan H** — apakah dibuka RFC terpisah sekarang untuk audit isi
   `index.html`/`admin-logs.*`, atau ditunda sampai Fase 1-7 selesai
   semua?

## Referensi

- `AI_CONTEXT.md` — daftar file locked, batasan teknis, alur kerja wajib
- `core/command_bus.py`, `core/event_bus.py` — implementasi singleton saat ini
- `server/app.py:49-61` — pola `web.AppKey` yang jadi acuan Fase 4
- `server/handlers/websocket.py`, `ws_playback.py` — command dispatch & validasi (Fase 3, 4)
- `engine/playback/controller.py:96-109` — komentar circuit breaker & izin eksplisit menyentuh file locked
- `web/static/shared/js/store.js:43-71` — riwayat `FIX-PAUSE-RACE-01`, rujukan utama Fase 5-6
- `web/static/shared/js/ws.js` — target split Fase 7
- `docs/rfc/arsip/frontend_refactor/proposal_frontend_tooling.md` — preseden format & governance RFC frontend sebelumnya
- `docs/PATCHLOG.md` — format v2 field-based untuk pencatatan tiap fase
