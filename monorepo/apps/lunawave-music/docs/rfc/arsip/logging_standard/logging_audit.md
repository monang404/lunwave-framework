---
title: LunaWave Logging Audit
status: Final — Gap Analysis
scope: Seluruh backend Python (146 file .py di luar tests/scratch/.cache, ~17.9k baris)
audited_against: LOGGING_STANDARD.md (last_verified 2026-07-22)
---

# Logging Audit — LunaWave vs LOGGING_STANDARD.md

## 1. Ringkasan Eksekutif

Implementasi logging saat ini **mendahului** standar dan tidak comply
padanya di hampir semua dimensi wajib (§3–§7). Infrastruktur teknis sudah
solid (`structlog` + `QueueHandler`/`QueueListener`, rotating file,
`req_id` per-HTTP-request via `contextvars` — lihat `core/log_config.py`,
`server/middleware/traffic.py`, ADR-0010) — tapi **isi tiap baris log**
(field, kategori, severity, message key) sepenuhnya belum mengikuti
kontrak §5–§6. Dua modul (`persistence/db.py`, `server/handlers/setup.py`)
sudah menulis dalam gaya yang sesuai standar (event key snake_case +
kwargs) dan menjadi **referensi pola yang benar** untuk migrasi modul lain.

Statistik kunci:

| Metrik | Nilai |
|---|---|
| File yang logging (`get_logger`/`getLogger`) | 44 dari 146 file .py |
| Total call `logger.error` / `logger.warning` / `logger.info` / `logger.debug` | 45 / 26 / 30 / 10 |
| Call `logger.critical(...)` di seluruh codebase | **0** |
| Call dengan f-string tersisip nilai dinamis ke pesan | **71** dari ~111 call (64%) |
| Call yang menyertakan field `category=` | **0** |
| Call yang menyertakan field `component=` | **0** |
| Call yang menyertakan `session_id=`/`request_id=`/`correlation_id=` | **0** (hanya `req_id` HTTP via contextvars, tidak menjangkau WS command/radio/download) |
| Modul yang sudah memenuhi §5–§6 (event key + kwargs) | 2: `persistence/db.py`, `server/handlers/setup.py` |
| Logging di `server/handlers/auth.py` (login, rate-limit, sesi) | **0 baris** |

## 2. Metodologi

Audit dilakukan dengan pembacaan `LOGGING_STANDARD.md` penuh, lalu
pemeriksaan statis seluruh sumber Python (`grep`/manual review) terhadap
tiap pasal standar: severity (§3), kategori (§4), structured field (§5),
message convention (§6), kewajiban logging (§7), larangan noise (§8),
serta anti-pattern (§12). Modul infrastruktur (`core/log_config.py`,
`core/command_bus.py`, `core/event_bus.py`) dan modul domain representatif
di tiap boundary (mpv, yt-dlp, SQLite, WebSocket auth, radio, download)
diperiksa satu per satu.

## 3. Temuan per Pasal Standar

### 3.1 Severity (§3) — **Tidak sesuai**

- `CRITICAL` tidak pernah dipakai (0 dari ~111 call), padahal kegagalan
  bind port (`server/app.py:114-115`, `site.start()` tanpa try/except
  sama sekali) dan kegagalan migrasi DB fatal saat boot adalah kandidat
  eksplisit §3 CRITICAL.
- Sebagian besar kegagalan boundary yang **tertangani via fallback**
  dicatat sebagai ERROR, bukan WARNING — mis. `adapters/ytdlp/resolver.py:88-100`
  (bot-check → retry player client fallback yang akhirnya berhasil, tetap
  memicu jalur `_log.error` bila fallback juga gagal, tapi retry pertama
  yang seharusnya WARNING sudah benar; kasus lain seperti
  `adapters/mpv/observer.py:148` — "MPV reconnect gagal setelah semua
  percobaan" — ini justru CRITICAL menurut definisi §3 karena playback
  inti mati total, saat ini hanya ERROR).
- `engine/playback/failure_ops.py:82,91` mencatat kegagalan track tunggal
  sebagai ERROR (benar), tapi baris 65 (video permanen tidak tersedia,
  skip tanpa retry) sudah benar sebagai WARNING.

**Verdict:** level dipilih ad-hoc per penulis kode, bukan dari tabel §3.
`CRITICAL` sama sekali belum diimplementasikan.

### 3.2 Kategori (§4) — **Tidak diimplementasikan (0%)**

Field `category` tidak eksis di satu baris log pun. Tidak ada mapping ke
14 kategori standar (`lifecycle`, `session`, `auth`, `command`, `event`,
`playback`, `queue`, `radio`, `download`, `resolve`, `cache`,
`persistence`, `external`, `security`, `system`). Nama logger saat ini
memakai `__name__` module Python (mis. `structlog.get_logger(__name__)`),
yang menurut §4 justru pola yang eksplisit dilarang (anti-pattern #7:
kategori tidak boleh mengikuti nama modul).

### 3.3 Structured Field (§5) — **Tidak sesuai, mayoritas gagal field wajib**

- Field wajib §5.1 (`timestamp`, `level`, `event`) otomatis terisi oleh
  `structlog`/`file_renderer`, tapi `category` dan `component` **tidak
  pernah diset secara eksplisit** — dua dari lima field wajib kosong di
  100% baris log.
- Field korelasi §5.2 (`session_id`, `request_id`, `correlation_id`) tidak
  pernah dipropagasi ke task domain. Satu-satunya mekanisme korelasi yang
  ada (`req_id` via `structlog.contextvars`, `server/middleware/traffic.py`)
  hanya mengikat siklus hidup satu request HTTP — **tidak diteruskan** ke
  eksekusi command via `CommandBus` (`core/command_bus.py`), ke sesi
  WebSocket (`server/connection_manager.py`), maupun ke siklus radio/
  download yang berjalan di task terpisah. Ini melanggar §5.2 secara
  langsung ("wajib dibawa ke setiap log ... termasuk task background").
- Nilai dinamis (video_id, durasi, jumlah retry) hampir selalu disisipkan
  ke kalimat lewat f-string alih-alih jadi field terpisah — 71 dari ~111
  call logger memakai f-string di pesan (lihat §3.5 di bawah). Ini
  melanggar §5 Prinsip Desain #3 ("Data di field, bukan di kalimat").
- Dua modul patuh penuh: `persistence/db.py` (mis. baris 79, 105, 108 —
  `logger.info("songs_migration_starting", reason=...)`,
  `logger.error("songs_migration_failed", error=str(e), error_type=...)`)
  dan `server/handlers/setup.py` (baris 130, 181, 214). Pola ini harus
  jadi baseline migrasi modul lain.

### 3.4 Message Convention / Event Key (§6) — **Tidak sesuai (mayoritas)**

- Vocabulary event key standar (`track_load_started`, `track_load_succeeded`,
  `radio_artist_selected`, `download_started`, `auth_login_rejected`, dst.)
  **tidak ditemukan sama sekali** di codebase — dikonfirmasi lewat
  pencarian literal, nol hasil kecuali sebagai contoh di
  `LOGGING_STANDARD.md` itu sendiri.
- Contoh pelanggaran nyata dan lokasinya:
  - `engine/playback/controller.py:362-363`: `f"Ignoring skip: requested {data['video_id']} != current {...}"` — kalimat naratif dengan nilai dinamis tersisip, bukan event key stabil.
  - `server/connection_manager.py:55,80`: `f"WebSocket connected. Total clients: {len(...)}"` — kalimat, bukan key; jumlah klien seharusnya field (`client_count`), event seharusnya `ws_connected`/`ws_disconnected`.
  - `adapters/mpv/observer.py:133,142,148`: kalimat campur Inggris/Indonesia ("mpv observer loop ended - connection lost.", "MPV berhasil reconnect.") — tidak stabil sebagai key dan tidak konsisten bahasa.
  - `persistence/discover_repo.py:94,121,164,203`: `f"Error getting {X}: {e}"` berulang di 4 fungsi berbeda dengan pola sama — kandidat konsolidasi ke satu event key (`discover_query_failed`) + field `query_type`.
- Bahasa campur Indonesia/Inggris dalam event message tanpa pola tetap
  (`"Gagal memulihkan playback..."` vs `"Failed to play track..."` di file
  yang sama, `engine/playback/failure_ops.py:82` vs `:91`) — melanggar §6
  ("event key selalu Bahasa Inggris").

### 3.5 Kapan Logging Wajib (§7) — **Gap signifikan di titik-titik boundary kritis**

| Kewajiban §7 | Status |
|---|---|
| §7.1 Boundary eksternal (MPV, yt-dlp, SQLite, API pihak ketiga) | Sebagian — hanya jalur gagal yang tercatat (biasanya ERROR), jalur sukses/awal panggilan nyaris tidak ada (`duration_ms` tidak pernah dicatat di boundary manapun) |
| §7.2 Titik masuk/keluar alur bisnis utama (command, event, sesi WS, siklus radio, download) | **Gagal** — `core/command_bus.py:75` hanya log saat exception; tidak ada log command diterima/sukses. `engine/radio/engine.py` tidak ada log mulai/selesai siklus radio. `engine/download_manager.py` tidak ada `download_started`/`download_completed` (hanya warning/error) |
| §7.3 Exception yang ditangkap & tidak diteruskan mentah | Sebagian — banyak titik sudah log di `except`, tapi lihat §3.6 (duplikasi lapisan) |
| §7.4 Perubahan state signifikan (mode, loudness, crossfade) | Tidak ditemukan logging di jalur pengaturan (`engine/playback/failure_ops.py`, `_on_set_mode`, dsb. tanpa log) |
| §7.5 Retry/fallback/degradasi | Ada, tapi level salah kaprah (lihat §3.1) dan pesan naratif (lihat §3.4) |
| §7.6 Kejadian keamanan (login, sesi, rate-limit, CSWSH) | **Gagal total** — `server/handlers/auth.py` (149 baris, menangani verifikasi token, PBKDF2, rate-limit 5x/5menit, pembuatan token sesi) **tidak memiliki satu baris logging pun**. Tidak ada jejak login berhasil/gagal, tidak ada jejak IP yang kena rate-limit, tidak ada jejak token sesi dibuat/dicabut |
| §7.7 Lifecycle proses (startup/shutdown/wake-lock) | Sebagian — shutdown tercatat (`main.py:148`), tapi kegagalan bind port saat startup (`server/app.py:114`) tidak dibungkus try/except/log sama sekali |
| §7.8 Task background/terjadwal (loop harus lapor kondisi diam tak wajar) | Sebagian — `adapters/mpv/observer.py` sudah melapor saat loop berhenti (baris 133, 148), tapi `engine/radio/prefetcher.py` dan cache-eviction loop (`bootstrap/startup_tasks.py`) tidak melapor bila loop berhenti tanpa sinyal shutdown |

### 3.6 Kapan Logging Tidak Diperlukan (§8) — **Sebagian dilanggar arah sebaliknya**

- `engine/radio/track_filter.py`: **nol baris logging**. Ini sesuai §8.2
  untuk larangan log per-kandidat, tapi standar tetap mengharapkan satu
  baris **ringkasan agregat** (jumlah kandidat masuk/lolos) yang saat ini
  tidak ada sama sekali — bukan pelanggaran §8, tapi gap terhadap §7.2/
  Best Practice #5 (§11.5).
- Tidak ditemukan pelanggaran nyata "log per-item dalam loop" atau
  "log per-tick progress" — pada aspek ini codebase justru under-logging,
  bukan over-logging. Ini konsisten dengan gambaran umum: developer
  menghindari noise dengan cara tidak logging sama sekali, bukan dengan
  meringkas.

### 3.7 Duplikasi Log Lintas Lapisan (anti-pattern §12.5) — **Ditemukan pola berisiko**

`adapters/ytdlp/resolver.py` mencatat ERROR saat gagal
(baris 74, 88-100, 103, 105) lalu me-raise exception yang sama ke
pemanggil (`engine/playback/track_loader.py`,
`services/stream_prefetch.py:73-80`, `engine/download_manager.py:142`),
yang kemudian **mencatat ERROR/WARNING lagi** untuk exception yang persis
sama tanpa informasi baru — pola log-di-setiap-lapisan yang eksplisit
dilarang §12.5.

### 3.8 Rahasia di Log (§8/§12.1) — **Tidak ditemukan pelanggaran**

Tidak ada baris log yang menulis `password`, `token` mentah, atau hash
kredensial (diperiksa di `server/handlers/auth.py`, `core/security.py`,
`persistence` session-related repo). Ini satu-satunya pasal keamanan yang
100% aman — namun ini kebetulan dari **tidak adanya logging auth sama
sekali** (§3.5, §7.6), bukan hasil desain yang disengaja.

### 3.9 Format Human/Machine Readable (§9–§10) — **Sesuai secara teknis, kosong secara isi**

`core/log_config.py` (`file_renderer`, `console_renderer`) sudah
menghasilkan bentuk `[waktu] LEVEL: event (field=value, ...)` yang cocok
dengan §9, dan struktur data yang mendasari (dict field-value via
`structlog`) sudah cocok dengan §10. Masalahnya murni di **isi field**
(§5.1–§5.3 kosong), bukan di mekanisme rendering.

## 4. Tabel Gap — Prioritas Implementasi

| # | Prioritas | Gap | Lokasi Kunci |
|---|---|---|---|
| G1 | **Kritis** | Nol logging keamanan (login, rate-limit, sesi) | `server/handlers/auth.py` (seluruh file) |
| G2 | **Kritis** | `CRITICAL` tidak pernah dipakai; kegagalan fatal (bind port, DB gagal buka saat boot, MPV gagal konek total di awal) tidak dibedakan dari ERROR biasa | `server/app.py:114-115`, startup DB/MPV init |
| G3 | **Kritis** | Field `category` dan `component` tidak pernah diset — kontrak §5.1 gagal di 100% baris log | Seluruh 44 file yang logging |
| G4 | **Tinggi** | Field korelasi (`session_id`/`request_id`/`correlation_id`) tidak dipropagasi ke command bus, WS, radio, download — alur async tidak bisa direkonstruksi | `core/command_bus.py`, `server/connection_manager.py`, `engine/radio/*`, `engine/download_manager.py` |
| G5 | **Tinggi** | 71 call logger memakai f-string/kalimat naratif alih-alih event key + field terstruktur | Tersebar luas — terburuk: `engine/playback/controller.py`, `adapters/mpv/*`, `adapters/ytdlp/resolver.py`, `persistence/discover_repo.py` |
| G6 | **Tinggi** | Titik masuk/keluar alur utama tidak dicatat: command diterima/selesai, siklus radio mulai/selesai, download mulai/selesai | `core/command_bus.py:75`, `engine/radio/engine.py`, `engine/download_manager.py` |
| G7 | **Sedang** | Level salah kaprah pada kegagalan yang sebetulnya CRITICAL (mpv gagal reconnect total) atau seharusnya WARNING (retry yang akhirnya sukses dicatat ERROR) | `adapters/mpv/observer.py:148`, `adapters/ytdlp/resolver.py:88-100` |
| G8 | **Sedang** | Duplikasi log exception yang sama di boundary + pemanggil tanpa informasi baru | `adapters/ytdlp/resolver.py` → `track_loader.py`/`stream_prefetch.py`/`download_manager.py` |
| G9 | **Sedang** | Bahasa event message campur Indonesia/Inggris tanpa pola tetap | `engine/playback/failure_ops.py`, `adapters/mpv/observer.py` |
| G10 | **Rendah** | Task background tanpa jejak "berhenti tak wajar" (prefetcher, cache-eviction loop) | `engine/radio/prefetcher.py`, `bootstrap/startup_tasks.py` |
| G11 | **Rendah** | Nama logger memakai `__name__` modul — pola yang justru dilarang §4/anti-pattern #7 sebagai basis kategori | Seluruh file (`structlog.get_logger(__name__)`) |

## 5. Baseline yang Sudah Benar (jadi acuan pola migrasi)

- `persistence/db.py` (baris 72, 79, 105, 108, 129, 141, 144): event key
  snake_case stabil + field kwargs (`reason`, `error`, `error_type`).
- `server/handlers/setup.py` (baris 130, 181, 214): pola sama, termasuk
  `client_ip` sebagai field kontekstual sesuai §5.3.
- Infrastruktur rendering (`core/log_config.py`) dan korelasi HTTP
  (`server/middleware/traffic.py`) sudah sesuai §9/§10 dan sebagian §5.2 —
  tinggal diperluas cakupannya, tidak perlu dibangun ulang.

## 6. Kesimpulan

Codebase LunaWave punya **fondasi teknis logging yang benar** (structlog,
async queue handler, rotating file, req_id per-HTTP-request) tetapi
**belum ada satu pun baris log yang memenuhi kontrak lima-pertanyaan**
di Ringkasan Kontrak standar (`timestamp`, `level`, `category`, `event`,
`component` + korelasi) secara lengkap. Gap terbesar dan berisiko paling
tinggi adalah nol logging di jalur autentikasi (G1) dan absennya field
`category`/`component`/korelasi di seluruh codebase (G3, G4) — dua hal ini
sebaiknya jadi task pertama pada rencana implementasi berikutnya, karena
keduanya memblokir semua modul lain untuk bisa dianggap "sesuai standar"
walau pesannya sendiri sudah diperbaiki.
