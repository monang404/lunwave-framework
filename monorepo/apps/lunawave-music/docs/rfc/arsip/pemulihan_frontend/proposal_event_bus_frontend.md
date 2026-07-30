---
title: Proposal Event Bus Frontend — Memutus Circular Dependency ws.js / audio / render / events
version: 1.0
tanggal: 2026-07-25
status: DRAFT — menunggu persetujuan user
target rilis: LunaWave (usulan, non-breaking, eksekusi bertahap per hub)
---

# Proposal Event Bus Frontend
### Gambaran akhir dulu, eksekusi bertahap kemudian

> **Ringkasan satu paragraf:** Backend LunaWave sudah punya `core/event_bus.py`
> (pub/sub `EventBus` berbasis `DomainEvent`) supaya modul `engine/`,
> `server/`, `adapters/` tidak saling `import` langsung. Frontend belum
> punya padanannya — `audio/playback-sync.js`, `ws.js`, dan
> `events/index.js` saling memanggil fungsi render secara langsung ke
> segala arah, menghasilkan 65 circular-dependency warning (+ 18 warning
> render↔events terpisah yang polanya sama) yang sudah diinvestigasi
> tuntas di `04_sesi4_circular_deps.yaml` dan `05_sesi5_render_events.yaml`.
> Dokumen ini adalah **RFC yang diminta di sesi 5** — bukan RFC baru dari
> nol, tapi kelanjutan resmi yang menutup syarat "RFC tertulis + approval
> eksplisit" yang jadi prasyarat sebelum sesi itu boleh dieksekusi.
> Dokumen ini menetapkan **desain akhir yang utuh** (kontrak `bus.js`,
> katalog event, file mana yang berubah) supaya tidak ada keputusan
> arsitektur baru yang dadakan di tengah eksekusi — tapi eksekusinya
> sendiri tetap dipecah per hub, sesuai pola governance project ini
> (satu sesi = satu unit kerja yang bisa di-checkpoint & di-rollback
> sendiri).

---

## 1. Latar Belakang

- **Kenapa sekarang:** saat menyelesaikan bug "audio browser bisu total"
  (`PATCH-2026-07-25-231`), akar masalahnya ada di `audio/playback-sync.js`
  — salah satu dari 3 hub circular-dependency terbesar (11 edge). File
  ini padat tanggung jawab: kontrol audio, render UI, DAN kirim pesan
  websocket, semua saling impor langsung. Bug kemarin bukan disebabkan
  oleh circular dependency-nya secara langsung, tapi kepadatan
  tanggung-jawab di file yang sama itulah yang bikin efek samping
  (Web Audio API menyambung ke elemen `<audio>` yang tainted) tidak
  kelihatan lewat review kode biasa.
- **Dasar RFC ini:** `docs/rfc/pemulihan_frontend/05_sesi5_render_events.yaml`
  (scope resmi: render↔events 18 warning + circular-dependencies 65
  warning, total 83), `04_sesi4_circular_deps.yaml` (data mentah 67 edge
  + diagnosis 3 hub utama), pola implementasi: `core/event_bus.py` +
  `core/ports.py` (backend, hexagonal — **bukan** pola yang dipakai di
  sini, lihat §7 kenapa).

## 2. Kondisi Saat Ini (As-Is)

| Hub | Edge terlibat | Peran |
|---|---|---|
| `ws.js` | 17 | Diimpor semua modul render/events untuk `wsSend` (legitimate). Mengimpor BALIK hampir semua modul `render/*` untuk render ulang UI setelah pesan WS masuk (masalahnya). |
| `events/index.js` | 15 | Hub inisialisasi semua `events/*.js` (legitimate, bootstrap). Mengimpor balik `audio/playback-sync.js`, `services/auth.js`, `render/discover-personalize.js`, `ws.js`. |
| `audio/playback-sync.js` | 11 | Engine audio. Mengimpor `render/player.js`, `render/now-playing.js`, `render/queue.js`, `render/radio-hero-moon.js`, `render/toast.js`, `ws.js` untuk update UI setelah event audio (masalahnya). Diimpor balik oleh `render/player.js`, `services/auth.js`, `events/index.js`, `events/settings-events.js`, `render/full-state.js`, `ws.js` untuk kontrol (`getOrInitAudio`, `syncBrowserAudio`, dst — legitimate). |
| Hub sekunder | 6–7 masing² | `render/search.js`, `render/full-state.js`, `events/settings-events.js` — pola sama, skala lebih kecil. |

**Prinsip yang sudah disepakati di `05_sesi5_render_events.yaml`** (dipakai
sebagai aturan desain, bukan diulang investigasi):

> Arah `render/events → ws.js/playback-sync` untuk **MEMERINTAH**
> (`wsSend`, `getOrInitAudio`, `syncBrowserAudio`, dst.) boleh **tetap**
> jadi import langsung — itu bukan sumber masalah. Yang bermasalah
> HANYA arah `ws.js/playback-sync → render/*` untuk **MERENDER**.

## 3. Desain Akhir yang Diusulkan (To-Be) — gambaran utuh

### 3.1 Modul baru: `web/static/shared/js/bus.js`

```js
// bus.js — pub/sub minimal, tanpa DOM API, testable tanpa browser.
const listeners = new Map(); // event name (string) -> Set<handler>

export function on(event, handler) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(handler);
}

export function off(event, handler) {
    listeners.get(event)?.delete(handler);
}

export function emit(event, payload) {
    listeners.get(event)?.forEach((handler) => {
        try {
            handler(payload);
        } catch (e) {
            console.error(`[bus] handler untuk "${event}" gagal:`, e);
        }
    });
}
```

Padanan minimal dari `core/event_bus.py`, disederhanakan karena tidak
butuh: `async`/concurrent dispatch (DOM event synchronous, tidak ada I/O
network di titik emit), `WeakMethod` (halaman cuma sekali load per
sesi, tidak ada lifecycle subscribe/unsubscribe berulang seperti
room/koneksi di server), maupun tipe `DomainEvent` (event name string
sudah cukup untuk skala 1 halaman).

### 3.2 Prinsip migrasi (berlaku di SEMUA hub, tidak berubah per tahap)

1. Modul "bawah" (`audio/playback-sync.js`, `ws.js`) **tidak lagi**
   `import` fungsi render langsung. Ganti jadi `bus.emit("nama-event", payload)`
   di titik yang sama persis.
2. Modul `render/*` `bus.on("nama-event", handler)` saat bootstrap
   (dipanggil dari `initEvents()`/`init()` di `main.js`, **bukan** saat
   modul di-import) — supaya urutan tidak bergantung urutan import.
3. Arah sebaliknya (render/events memanggil `wsSend`, `getOrInitAudio`,
   dst. di `ws.js`/`playback-sync.js`) **tetap** import langsung — lihat
   §2, ini bukan sumber masalah.
4. Regenerate `npx depcruise` setelah **tiap hub**, bukan sekali di
   akhir — supaya penurunan warning bisa diverifikasi bertahap.

### 3.3 Katalog event — Hub 1: `audio/playback-sync.js` (Tahap pertama)

Ini yang paling detail karena jadi tahap eksekusi pertama (lihat §4).

| Titik panggil saat ini | Diganti jadi | Subscriber (bus.on saat bootstrap) |
|---|---|---|
| `renderPlayBtn()` | `bus.emit("player:btn-changed")` | `render/player.js` |
| `renderPlayerBar()` | `bus.emit("player:bar-changed")` | `render/player.js` |
| `resetAnchorClock()`, `setPositionAnchor()`, `startProgressClock()`, `stopProgressClock()` | `bus.emit("player:clock", {action, value})` | `render/player.js` |
| `renderNowPlaying()` | `bus.emit("now-playing:changed")` | `render/now-playing.js` |
| `renderQueue()` | `bus.emit("queue:changed")` | `render/queue.js` |
| `setRadioHeroAnimState(on)` | `bus.emit("radio-hero:anim", {on})` | `render/radio-hero-moon.js` |
| `showLogToast(msg)` | `bus.emit("toast:log", {message: msg})` | `render/toast.js` |
| `syncLocalLyrics()` (dari `ws.js`) | `bus.emit("lyrics:sync-local")` | `ws.js` (subscribe balik — lihat catatan di bawah) |
| `wsSend(...)` (dari `ws.js`) | **TETAP** import langsung | — (arah MEMERINTAH, legitimate per §2) |

**Catatan `syncLocalLyrics`:** ini satu-satunya simbol dari `ws.js` yang
sifatnya render-ish (bukan command), jadi ikut dipindah ke bus meski
sumbernya `ws.js`, bukan modul `render/*`. `wsSend` dari file yang sama
tetap direct import karena itu perintah, bukan render call. Efeknya:
edge `audio/playback-sync.js -> ws.js` **tidak hilang total** dari
graph (karena `wsSend` tetap diimpor) — lihat peringatan realistis di
§3.5.

File yang berubah di tahap ini: `audio/playback-sync.js` (emit),
`render/player.js`, `render/now-playing.js`, `render/queue.js`,
`render/radio-hero-moon.js`, `render/toast.js` (tambah `bus.on(...)` di
fungsi init masing², dipanggil dari bootstrap), `bus.js` (baru).

### 3.4 Katalog event — Hub 2 & 3 (`ws.js`, `events/index.js`) — kerangka, detail final saat tahapnya tiba

`ws.js` (17 edge) dan `events/index.js` (15 edge) memakai **prinsip yang
sama persis** (§3.2), tapi katalog event presisinya akan di-finalisasi
tepat sebelum tahap itu dieksekusi — bukan karena arsitekturnya belum
jelas, tapi karena `04_sesi4` sendiri mewajibkan `npx depcruise`
di-regenerate setelah tiap hub selesai, dan hasil Tahap 1 bisa mengubah
sebagian edge di `ws.js` (karena `ws.js` salah satu importer
`playback-sync.js`). Kerangka yang **sudah pasti**:

- `ws.js -> render/discover-personalize.js, render/discover-search.js, render/discover-tab.js, render/full-state.js, render/player.js, render/radio-tab.js, render/search.js` → semua jadi `bus.emit(...)` per jenis pesan WS (`state`, `progress`, `lyrics`, dst — granularitas persis mengikuti `handleServerMessage()`/`case` yang sudah ada di `ws.js` sekarang, bukan 1 event generik "ws:message").
- `ws.js -> render/discover-personalize.js` (`handleArtistDetail`), `ws.js -> services/auth.js` (`applyRoleUI`, `logout`) → dievaluasi kasus per kasus saat tahap ini: sebagian mungkin lebih tepat masuk kategori "command" (auth logout bisa dibilang bukan render), keputusan detailnya ditulis di task-breakdown Tahap 2, bukan didikte dari sini.
- `events/index.js -> render/discover-personalize.js` (`initDiscoverFilterEvents`) — ini fungsi INIT (bootstrap wiring), bukan render-call reaktif, kemungkinan besar **tetap** direct import (analog §2), perlu dikonfirmasi saat Tahap 3.

### 3.5 Target realistis — bukan 0 warning

Sama seperti exception `playback-sync.js<->visualizer.js` yang sudah
diterima di Sesi 4 (bukan silent-fix, didokumentasikan di
`.dependency-cruiser.js`), migrasi ini **tidak akan menghasilkan 0
circular-dependency warning**. `depcruise` mendeteksi cycle di level
file, bukan level simbol/arah panggilan — jadi pasangan file yang tetap
punya edge command-direction legitimate (mis. `render/player.js` tetap
`import { getOrInitAudio } from "playback-sync.js"` DAN
`playback-sync.js` tetap punya *beberapa* edge balik yang legitimate
seperti `wsSend`) kemungkinan **masih terdeteksi** sebagai warning oleh
tool, walau secara desain sudah benar satu-arah untuk MERENDER.

**Definisi "selesai" yang jujur untuk proposal ini:** semua edge
"lower layer memanggil render langsung" (yang sebelumnya dikonfirmasi
sebagai akar masalah di §2) hilang dan diganti `bus.emit`/`bus.on`.
Sisa warning yang murni representasi command-direction legitimate
didokumentasikan sebagai exception di `.dependency-cruiser.js`, sama
seperti pola kasus visualizer — bukan target yang dipaksa jadi 0 lewat
tambal-sulam.

## 4. Rencana Eksekusi Bertahap (tidak berubah dari usulan sebelumnya, sekarang formal)

| Tahap | Hub | Edge | File utama yang disentuh | Prasyarat |
|---|---|---|---|---|
| 1 | `audio/playback-sync.js` | 11 | Lihat §3.3 | `bus.js` dibuat di tahap ini |
| 2 | `ws.js` | 17 | Katalog difinalisasi saat mulai (§3.4) | Tahap 1 selesai + `depcruise` di-regenerate |
| 3 | `events/index.js` | 15 | Katalog difinalisasi saat mulai (§3.4) | Tahap 2 selesai + `depcruise` di-regenerate |
| 4 | Hub sekunder (`render/search.js`, `render/full-state.js`, `events/settings-events.js`) | 6–7 masing² | TBD saat tahapnya tiba | Tahap 1–3 selesai |
| 5 | render↔events cross-import murni (18 warning sisa di luar 3 hub di atas) | 18 | TBD | Tahap 1–4 selesai |

Tiap tahap: task-breakdown `.yaml` terpisah (format sama seperti
`04_sesi4_circular_deps.yaml`), test regresi manual + otomatis sebelum
dianggap selesai, entry `docs/PATCHLOG.md` sendiri (tidak digabung),
checkpoint zip sebelum & sesudah — **persis pola yang sudah berjalan di
project ini**, tidak ada proses baru yang diperkenalkan.

## 5. Kenapa BUKAN "hexagonal architecture" (koreksi eksplisit)

Backend LunaWave pakai hexagonal (`core/ports.py` — `AudioPlayerPort`,
`MediaExtractorPort`, dst.) untuk mengisolasi domain logic dari
implementasi infrastruktur (mpv vs implementasi lain). Proposal ini
**tidak** memperkenalkan pola port/adapter, tidak mendefinisikan
interface abstrak untuk domain vs infrastruktur, dan tidak mengubah
bagaimana `render/*`/`events/*` mengontrol `ws.js`/`playback-sync.js`
(command-direction tetap direct import, §2). Ini murni pub/sub sempit
untuk satu arah komunikasi yang bermasalah. Jangan disamakan skopnya.

## 6. Non-Negotiable / Governance

- Tidak menambah framework JS — konsisten `AI_CONTEXT.md`.
- Setiap tahap = entry `PATCHLOG.md` terpisah, tidak digabung.
- Dilarang pakai dynamic import untuk akal-akalan lolos linter (sudah
  ditegaskan sejak `05_sesi5_render_events.yaml`).
- `bus.on(...)` WAJIB dipanggil dari fungsi init yang dipanggil
  bootstrap (`main.js`/`initEvents()`), bukan di top-level module scope
  — supaya urutan subscribe tidak bergantung urutan `import`.
- Tiap tahap WAJIB regenerate `npx depcruise` sebelum ditutup, bukan
  ditunda ke akhir semua tahap.
- Regression test manual playback wajib untuk Tahap 1 & 2 (menyentuh
  jalur audio/WS real-time) — bukan cuma `npx eslint`/`vitest` hijau.

## 7. Risiko & Effort per Tahap

| Tahap | Risiko regresi | Effort | Bisa berhenti di sini? |
|---|---|---|---|
| 1. `bus.js` + `playback-sync.js` | Sedang (jalur audio real-time, baru saja ada bug di sini) | Sedang | Ya |
| 2. `ws.js` | Sedang–tinggi (hub terbesar, 17 edge) | Tinggi | Ya |
| 3. `events/index.js` | Sedang | Sedang | Ya |
| 4. Hub sekunder | Rendah | Rendah–sedang | Ya |
| 5. render↔events murni | Rendah | Rendah | Ya |

Tiap tahap independen dan bisa dihentikan tanpa meninggalkan kode dalam
keadaan rusak (constraint yang sama dengan proposal tooling frontend
sebelumnya).

## 8. Keputusan yang Perlu Persetujuan User

1. **Approve desain akhir ini secara keseluruhan** (bus.js + prinsip
   command-vs-render direction + target realistis §3.5) — supaya tidak
   ada keputusan arsitektur baru dadakan di tengah Tahap 2/3/4/5.
2. **Izin mulai Tahap 1** (`bus.js` + migrasi `audio/playback-sync.js`)
   sekarang, atau tunggu dulu?
3. Nama event di §3.3 sudah final, atau ada preferensi penamaan lain
   (mis. prefix per-domain vs per-file)?
4. Tahap 4 & 5 (hub sekunder, render↔events murni) — worth dikerjakan
   sampai situ, atau berhenti setelah Tahap 1–3 (3 hub utama) saja
   cukup?

## Referensi

- `docs/rfc/pemulihan_frontend/05_sesi5_render_events.yaml` — RFC asal,
  prasyarat yang dipenuhi dokumen ini
- `docs/rfc/frontend_refactor/temuan_circular_deps_sesi4.md` +
  `04_sesi4_circular_deps.yaml` — data mentah 67 edge, diagnosis 3 hub
- `core/event_bus.py`, `core/ports.py` — pola pub/sub & hexagonal di
  backend (referensi konsep, bukan pola yang di-copy 1:1 — lihat §5)
- `.dependency-cruiser.js` — rule `circular-dependencies`,
  `no-render-imports-events`, `no-events-imports-render`
- `docs/PATCHLOG.md` PATCH-2026-07-25-231 — bug audio yang jadi trigger
  proposal ini ditulis
