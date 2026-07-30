---
title: Proposal Pemecahan God File & God Class — LunaWave
version: 1.0
tanggal: 2026-07-26
status: DRAFT — untuk direview
target rilis: LunaWave (usulan, non-breaking, bertahap per fase)
author: AI audit session (Claude) — atas permintaan pemilik project
scope: persistence/, engine/playback/, web/static/pages/, web/static/shared/js/audio/
prasyarat: proposal_perbaikan_arsitektur.md (RFC #1) — file 01-07 selesai dieksekusi
melanjutkan: Temuan H (RFC #1, §4.H) — index.html/admin-logs.* yang sengaja
  ditunda di keputusan d5 (00_index_and_decisions.yaml), sekarang diperluas
  jadi RFC utuh untuk seluruh "God file" di codebase, bukan cuma 2 halaman itu.
---

# Proposal Pemecahan God File & God Class — LunaWave

### Dari "Ukuran Besar Karena Kompleksitas Wajar" ke "Ukuran Besar Karena Tanggung Jawab Numpuk" — dan Cara Membedakan Keduanya

> **Ringkasan satu paragraf:** Audit ukuran file (baris kode) + audit isi
> (docstring `Responsibilities:`, jumlah method per class, panjang method
> individual) terhadap seluruh codebase menemukan **5 file/class** yang
> tanggung jawabnya sudah numpuk melewati batas wajar untuk satu file —
> 2 di frontend JS (`admin-logs.js` 878 baris mencampur 4 domain berbeda,
> `playback-sync.js` 499 baris mencampur 5 concern audio), 1 di
> persistence (`discover_repo.py` 446 baris dengan 1 method 140 baris),
> 1 di engine (`controller.py` 468 baris, orkestrator tunggal untuk 28
> command), dan 3 halaman HTML monolitik (898+290+1074 baris). Sama
> pentingnya: proposal ini secara eksplisit **mengecualikan** 2 file lain
> yang awalnya terlihat mencurigakan karena ukurannya (`patchlog.py` 584
> baris, `launcher/gui/ui_builder.py` 353 baris) setelah audit isi
> menunjukkan keduanya **kohesif** — besar karena domainnya memang butuh
> banyak kode, bukan karena tanggung jawab numpuk. Ukuran baris SENDIRI
> bukan sinyal yang cukup; proposal ini memakai 3 sinyal gabungan (lihat
> §2) supaya pemecahan yang diusulkan benar-benar menyelesaikan masalah
> desain, bukan sekadar memotong file jadi lebih kecil secara kosmetik.

---

## 1. Latar Belakang

RFC #1 (`proposal_perbaikan_arsitektur.md`) sudah menutup Temuan A-G dan
sengaja menunda Temuan H (`index.html`/`admin-logs.*`) karena butuh RFC
terpisah (keputusan d5, `00_index_and_decisions.yaml`). Proposal ini
adalah RFC lanjutan itu, tapi cakupannya diperluas: bukan cuma 2 halaman
yang disebut Temuan H, melainkan **audit ulang seluruh codebase** untuk
file/class yang tanggung jawabnya numpuk — sesuai permintaan eksplisit
pemilik project.

## 2. Metodologi — Membedakan "Besar Karena Kompleks" vs "Besar Karena Numpuk"

Ukuran baris kode dipakai sebagai **titik awal pencarian**, bukan
kriteria putus. Tiap kandidat divalidasi dengan 3 sinyal:

1. **Docstring `Responsibilities:`** (konvensi repo ini) — kalau berisi
   ≥3 kelompok tanggung jawab yang secara konseptual tidak berhubungan
   langsung (mis. "serve file" DAN "kirim chat" DAN "render dashboard"),
   itu sinyal god-file. Kalau berisi banyak baris tapi semuanya varian
   dari SATU konsep (mis. "5 jenis query discover", semuanya query
   read-only ke domain yang sama), itu BUKAN otomatis god-file.
2. **Jumlah method per class** dan **panjang method individual** —
   class dengan banyak method pendek (delegasi tipis) berbeda masalahnya
   dari class dengan sedikit method tapi masing-masing raksasa.
3. **Uji "ubah 1 hal, sentuh berapa banyak konsep tak-terkait"** — kalau
   menambah 1 fitur kecil di satu domain (mis. 1 filter log baru)
   mengharuskan baca/paham kode domain lain yang tidak terkait
   (mis. chat panel) di file yang sama, itu bukti konkret coupling
   berlebih, bukan spekulasi.

**Hasil validasi — 2 file DIKECUALIKAN setelah audit isi** (supaya
proposal ini tidak mengulang kesalahan "percaya ukuran baris saja"):

| File | Baris | Kenapa TIDAK masuk Temuan |
|---|---|---|
| `automation/patchlog.py` | 584 | Semua fungsi (parse, verify, render, add_entry, CLI) melayani SATU konsep: manajemen entri PATCHLOG. Besar karena parsing teks + CLI argparse + git integration untuk satu domain, bukan tanggung jawab campur. |
| `launcher/gui/ui_builder.py` | 353 | Satu class `UIBuilder`, kode GUI Tkinter/sejenis yang secara natural verbose (definisi widget + layout). Perlu direview terpisah kalau ada bukti concern non-UI ikut masuk, tapi TIDAK diaudit mendalam di RFC ini karena scope RFC ini dibatasi ke server/engine/persistence/web (lihat header) — dicatat sebagai item observasi, bukan temuan.

## 3. Temuan — 5 God File/Class

| # | Area | Temuan | Lokasi | Bukti konkret |
|---|---|---|---|---|
| I | Frontend | `admin-logs.js` mencampur 4 domain tak-terkait | `web/static/pages/admin-logs/admin-logs.js` (878 baris) | Docstring header hanya bilang "Fetches initial log history and listens to live tailing" — TAPI isinya juga py render dashboard statistik (`renderSystemDashboard`, `renderActiveUsers`, `parseUserAgent`), WS transport khusus halaman ini (`connectWs`, `fallbackToPolling`), dan panel chat admin penuh (`openChatPanel`, `createMsgEl`, `handleIncomingChat`) — dokumentasi sudah basi dibanding isi file. |
| J | Frontend | `playback-sync.js` mencampur 5 concern audio | `web/static/shared/js/audio/playback-sync.js` (499 baris) | Dalam 1 file: audio-pool init (`getOrInitAudio`, `initAudioPool`), UI banner "tap to play" untuk autoplay-policy (`_showTapToPlayBanner`/`_hideTapToPlayBanner`), volume fade (`_fadeVolume`), unlock browser audio (`unlockBrowserAudio`), sync inti (`syncBrowserAudio`, 127 baris), dan MediaSession API (`updateMediaSession`). |
| K | Backend | `DiscoverRepository` — 1 method 140 baris berisi 2 search-path + sorting | `persistence/discover_repo.py:233-372` (`search_tracks`) | Method ini sendiri (140 dari 446 baris file) berisi 2 nested async function (`_fetch_tracks`, `_fetch_songs`) dan 1 nested `_sort_key` — pola "method di dalam method" adalah sinyal method itu sendiri sudah pantas jadi unit terpisah. |
| L | Backend | `PlaybackController.play_track()` — 86 baris dalam orkestrator 468 baris/28 method | `engine/playback/controller.py:215-300` | Class sudah delegasi ke 6 ops-class (`QueueOps`, `ModeOps`, `TrackEndedOps`, `FailureOps`, `QueueController`, `SettingsController`) — pola komposisi SUDAH BENAR. Tapi `play_track()` sendiri masih melakukan load+crossfade-decision+retry+event-publish dalam 1 method 86 baris, belum ikut pola delegasi yang sama. |
| M | Frontend | 3 halaman monolitik tanpa componentisasi | `web/static/pages/app/index.html` (898), `web/static/pages/client/client.html` (290), `web/static/pages/admin-logs/admin-logs.html` (1074) | Lanjutan Temuan H RFC #1 — audit ukuran markup vs `<template>`/inline `<script>` BELUM pernah dilakukan (RFC #1 sengaja menunda ini). |

## 4. Root Cause & Desain Perbaikan per Temuan

### I. `admin-logs.js` → split 4 modul by domain

**Root cause:** File dimulai sebagai "log tailing" murni (sesuai
docstring), lalu fitur ditambah berkali-kali (dashboard stats,
lalu chat admin) ke file yang sama karena sudah "ada di situ", tanpa ada
sinyal otomatis (linter ukuran file, review checklist) yang menandai
titik saat itu sudah bukan lagi "log tailing".

**Desain yang diusulkan** — split by domain, tanpa mengubah
`admin-logs.html` script tag (tetap 1 entrypoint via re-export, pola
sama seperti `ws.js` di RFC #1 file 06):

```
web/static/pages/admin-logs/
├── admin-logs.js              # thin orchestrator: import + wire event listeners saja
├── log-tail.js                # createLogLineElement, appendLogBatch, formatFields,
│                               # getLevelIcon, escapeHtml, navigateToLiveTail
├── dashboard-stats.js         # fetchStats, renderMatrix, renderSystemDashboard,
│                               # renderActiveUsers, parseUserAgent, getPageName,
│                               # formatDuration
├── admin-ws-transport.js      # connectWs, fallbackToPolling, fetchTail, fetchHealth
└── admin-chat-panel.js        # updateBadge, openChatPanel, createMsgEl,
                                # renderChatHistory, handleIncomingChat, formatTime
```

Migrasi **domain-per-domain** (4 langkah independen), masing-masing bisa
dihentikan tanpa merusak domain lain — beda dengan `ws.js` (RFC #1 file
06) yang case message-nya saling terhubung lewat 1 dispatch table, di
sini 4 domain nyaris tidak saling panggil sama sekali (baru diverifikasi
saat eksekusi: cek apakah `handleIncomingChat` memanggil sesuatu dari
`dashboard-stats.js` atau sebaliknya — kalau ada, itu jadi shared util
kecil, bukan alasan menggabung modul).

### J. `playback-sync.js` → split 3 modul by concern

**Root cause:** "Audio playback sync" terasa seperti 1 domain
(makanya semua ditaruh 1 file), padahal sebenarnya 3 concern berbeda
yang kebetulan semuanya menyentuh `<audio>` element: (1) manajemen pool
elemen `<audio>` + unlock autoplay-policy (concern browser API), (2)
sinkronisasi status server↔audio (concern domain playback), (3)
MediaSession API (concern OS-level media control, sepenuhnya independen
dari 2 concern lain).

**Desain yang diusulkan:**

```
web/static/shared/js/audio/
├── playback-sync.js       # THIN: import 2 modul di bawah + syncBrowserAudio
│                            # (concern inti: baca store, putuskan audio mana
│                            # yang harus play/pause/seek — TIDAK tahu detail
│                            # unlock/fade/pool)
├── audio-pool.js          # audioPool, getOrInitAudio, initAudioPool,
│                            # unlockBrowserAudio, _showTapToPlayBanner/
│                            # _hideTapToPlayBanner, _fadeVolume
└── media-session.js       # updateMediaSession, _updateMediaSessionState
```

**Poin krusial (sama seperti `store.js` di RFC #1 file 04):** export
publik yang dipakai file lain (`syncBrowserAudio`, `unlockBrowserAudio`,
`resetLastLoadedVideoId`, `updateMediaSession` — cek dulu semua caller
eksternal sebelum split) HARUS tetap bisa diimpor dari
`playback-sync.js` lewat re-export, supaya caller di luar folder
`audio/` tidak perlu diubah.

### K. `DiscoverRepository.search_tracks()` → extract 3 helper function/method

**Root cause:** Method ini menangani 2 search-path (tracks vs songs)
sekaligus sorting gabungannya dalam 1 scope — nested function di dalam
method adalah tanda method itu sendiri sudah "ingin" jadi unit terpisah
tapi belum diekstrak.

**Desain yang diusulkan** — extract, TANPA mengubah signature publik
`search_tracks()`:

```python
# persistence/discover_repo.py

class DiscoverRepository:
    ...
    async def search_tracks(self, query: str, ...) -> list[dict]:
        tracks = await self._search_tracks_only(query, ...)
        songs = await self._search_songs_only(query, ...)
        return sorted(tracks + songs, key=self._search_sort_key)

    async def _search_tracks_only(self, query: str, ...) -> list[dict]:
        ...  # isi _fetch_tracks() lama, jadi method privat biasa

    async def _search_songs_only(self, query: str, ...) -> list[dict]:
        ...  # isi _fetch_songs() lama

    @staticmethod
    def _search_sort_key(row: dict):
        ...  # isi _sort_key() lama
```

**Manfaat konkret:** `_search_tracks_only` dan `_search_songs_only` bisa
di-unit-test terpisah (mock query DB masing-masing lebih sempit),
dibanding sekarang yang harus mock seluruh `search_tracks()` sekaligus
untuk test 1 search-path saja.

### L. `PlaybackController.play_track()` → extract ke `TrackLoader`/ops class yang sudah ada

**Root cause:** Pola delegasi ke ops-class SUDAH ADA dan benar
(`_queue_ops`, `_mode_ops`, `_track_ended_ops`, `_failure_ops`,
`_queue_controller`, `_settings_controller`) — tapi `play_track()`
sendiri, sebagai method paling sering dipanggil dan paling kompleks
(86 baris), belum ikut pola yang sama.

**Desain yang diusulkan:** verifikasi dulu isi `play_track()` baris
per baris saat eksekusi (JANGAN asumsi struktur dari RFC ini saja —
file locked, risiko tinggi, closure kompleks per `AI_CONTEXT.md`), lalu
pisahkan menjadi urutan pemanggilan ke `self.track_loader` (yang sudah
ada, lihat `TrackLoader` di `__init__`) untuk bagian load+resolve, dan
sisakan di `play_track()` hanya orkestrasi tingkat tinggi (panggil
loader, panggil crossfade-decision, publish event). **Ini task
berisiko PALING TINGGI di seluruh RFC ini** karena closure/state
lifecycle di `controller.py` eksplisit ditandai "risiko tinggi" di
`AI_CONTEXT.md` — perlu test karakterisasi (characterization test)
SEBELUM refactor, bukan sesudah, supaya behavior lama tertangkap dulu
sebagai baseline.

### M. 3 halaman HTML monolitik → audit dulu, componentize kalau perlu

**Root cause:** Belum ada audit ukuran markup-natural vs
`<template>`/inline `<script>` blocks — keputusan componentize atau
tidak SEHARUSNYA menunggu hasil audit ini, bukan diasumsikan duluan.

**Langkah yang diusulkan (audit dulu, BUKAN langsung componentize):**
1. Hitung rasio baris markup HTML murni vs baris di dalam tag
   `<script>`/`<template>` inline per halaman.
2. Untuk `admin-logs.html` (1074 baris) — kemungkinan besar sudah
   banyak berkurang setelah Temuan I dieksekusi (script inline pindah
   ke file .js terpisah), audit ulang SETELAH Temuan I selesai, bukan
   sebelum (urutan dependency, lihat §5).
3. Kalau markup natural (bukan script) yang mendominasi ukuran →
   componentize TIDAK diperlukan, ukuran itu wajar untuk aplikasi
   sekompleks ini (banyak state UI berbeda: home/discover/queue/lyrics/
   dst dalam 1 SPA-like page).
4. Kalau ternyata banyak blok markup berulang (mis. template kartu
   track/artist diulang manual di banyak tempat) → baru componentize
   pakai `<template>` tag native (tanpa framework, sesuai batasan §6
   RFC #1) untuk blok yang repetitif itu saja.

## 5. Rencana Rollout

Fase independen, urutan berdasarkan dependency & risiko (bukan urutan
Temuan I-M):

| Urutan | Temuan | Isi | Depends on | Risiko | Effort |
|---|---|---|---|---|---|
| 1 | K | Extract `search_tracks()` jadi 3 unit lebih kecil | RFC #1 selesai (tidak wajib, tapi disarankan urutan terakhir dulu tervalidasi) | Rendah | Rendah |
| 2 | I | Split `admin-logs.js` jadi 4 modul by domain | Tidak ada | Rendah–sedang | Sedang |
| 3 | J | Split `playback-sync.js` jadi 3 modul by concern | Tidak ada (independen dari #2) | Rendah–sedang | Sedang |
| 4 | M | Audit rasio markup vs script `admin-logs.html` | Setelah #2 selesai (script sudah pindah, audit ulang lebih akurat) | Rendah (murni audit, belum eksekusi) | Rendah |
| 5 | M | Audit rasio markup vs script `index.html`, `client.html` | Tidak ada | Rendah (murni audit) | Rendah |
| 6 | M | Componentize (KONDISIONAL — hanya kalau hasil #4/#5 menunjukkan blok berulang signifikan) | #4, #5 | Sedang–tinggi | Tergantung hasil audit |
| 7 | L | Extract `play_track()` jadi orkestrasi tipis + delegasi ke `TrackLoader` | Karakterisasi test dulu (lihat §4.L) | **Tinggi** (file locked, closure kompleks) | Sedang–tinggi |

**Temuan L sengaja diletakkan TERAKHIR** — sama seperti prinsip RFC #1
(fase berdampak luas/berisiko tinggi di akhir), dan **wajib** test
karakterisasi sebelum refactor dimulai (rekam behavior current
`play_track()` sebagai golden test, baru refactor, baru bandingkan).

## 6. Governance

- Prinsip non-breaking & 1-fase-1-PATCHLOG-entry dari RFC #1 (`AI_CONTEXT.md`)
  berlaku identik di sini — tidak diulang detailnya, lihat RFC #1 §6.
- Temuan L menyentuh `engine/playback/controller.py` (file locked,
  "risiko tinggi, closure kompleks") — governance RFC #1 sudah
  menetapkan pola otorisasi eksplisit untuk file ini (lihat
  `00_index_and_decisions.yaml` meta.authorization); pola yang sama
  berlaku untuk RFC #2 ini kalau pemilik project mengonfirmasi.
- Temuan M langkah 6 (componentize) BERSYARAT pada hasil audit langkah
  4/5 — proposal ini TIDAK mengasumsikan jawabannya duluan, konsisten
  dengan prinsip RFC #1 (jangan refactor tanpa bukti kebutuhan konkret).
- `automation/patchlog.py` dan `launcher/gui/ui_builder.py` DIKECUALIKAN
  dari RFC ini (lihat §2) — kalau pemilik project menemukan bukti
  konkret coupling di kemudian hari, buka temuan baru terpisah, jangan
  dipaksakan masuk RFC ini tanpa bukti.

## 7. Langkah Selanjutnya

Kalau proposal ini disetujui, saya bisa langsung buatkan breakdown
implementasi dalam format `.yaml` per-fase (pola identik RFC #1 —
9 file, `00_index` + task kecil siap eksekusi terurut dependency, tanpa
open question) seperti yang sudah dibuat untuk RFC #1. Beri tahu saja
kalau mau lanjut ke situ, atau kalau ada urutan/keputusan di §5-6 yang
mau diubah dulu.

## Referensi

- `proposal_perbaikan_arsitektur.md` — RFC #1, Temuan H yang jadi titik
  awal RFC ini.
- `00_index_and_decisions.yaml` (RFC #1) — keputusan d5, otorisasi
  menyentuh file locked.
- `web/static/pages/admin-logs/admin-logs.js`, `web/static/shared/js/audio/playback-sync.js`
  — bukti langsung ditemukan lewat `grep` fungsi top-level, bukan asumsi.
- `persistence/discover_repo.py:233-372`, `engine/playback/controller.py:215-300`
  — bukti panjang method lewat pengukuran baris langsung.
- `AI_CONTEXT.md` — daftar file locked (`engine/playback/controller.py`,
  `server/handlers/websocket.py`), alur kerja wajib.
