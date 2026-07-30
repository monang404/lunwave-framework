---
title: Implementasi Plan — Logging LunaWave
status: Draft — siap eksekusi
based_on:
  - LOGGING_STANDARD.md (last_verified 2026-07-22)
  - logging_audit.md (Gap Analysis, 146 file .py, ~17.9k baris)
scope: Seluruh backend Python (server, engine, core, adapters, persistence, services)
---

# Rencana Implementasi Logging LunaWave

> Dokumen ini menerjemahkan `LOGGING_STANDARD.md` (target) dan
> `logging_audit.md` (kondisi saat ini) menjadi urutan kerja konkret:
> file mana disentuh, apa yang berubah, dalam urutan apa, dan bagaimana
> memverifikasi tiap fase selesai. Tidak ada keputusan desain baru di
> sini — semua keputusan (severity, kategori, field, event key) sudah
> final di standar; dokumen ini murni soal *urutan dan mekanisme migrasi*.

---

## 1. Prinsip Migrasi

1. **Infrastruktur dulu, isi kemudian.** Field `category`/`component` dan
   propagasi correlation id butuh satu titik implementasi bersama
   (helper/factory) sebelum 44 file yang logging bisa dimigrasikan satu
   per satu tanpa saling menunggu.
2. **Ikuti baseline yang sudah ada.** `persistence/db.py` dan
   `server/handlers/setup.py` sudah menulis `logger.info("event_key",
   field=value)` — pola ini direplikasi, bukan dirancang ulang.
3. **Non-breaking per commit.** Setiap fase harus meninggalkan aplikasi
   dalam keadaan berjalan normal — tidak ada fase yang butuh "big bang"
   ganti semua 111 call logger sekaligus.
4. **Boundary dan keamanan duluan.** Sesuai audit, G1 (nol logging auth)
   dan G3 (field wajib kosong 100%) adalah blocker yang membuat modul
   lain tidak bisa dianggap sesuai standar walau pesannya sendiri sudah
   rapi — keduanya jadi fase 1–2.
5. **Satu PR = satu modul/domain**, bukan satu PR untuk seluruh 44 file,
   supaya review bisa memverifikasi tiap event key baru terhadap §6
   dan tabel kategori §4 satu per satu.

---

## 2. Fase 0 — Infrastruktur Bersama (prasyarat semua fase lain)

Tanpa fase ini, migrasi modul-per-modul di Fase 2+ akan menghasilkan
pola `category=`/`component=`/`session_id=` yang tidak konsisten antar
file, karena tiap penulis akan menebak sendiri.

### 2.1 Konstanta kategori (§4)

Tambahkan `core/log_categories.py` berisi 14 nilai `category` sebagai
konstanta string (`LC_LIFECYCLE`, `LC_SESSION`, `LC_AUTH`, `LC_COMMAND`,
`LC_EVENT`, `LC_PLAYBACK`, `LC_QUEUE`, `LC_RADIO`, `LC_DOWNLOAD`,
`LC_RESOLVE`, `LC_CACHE`, `LC_PERSISTENCE`, `LC_EXTERNAL`, `LC_SECURITY`,
`LC_SYSTEM`) — daftar tertutup, sesuai §4, supaya salah ketik kategori
tertangkap oleh import error, bukan oleh typo string bebas.

### 2.2 Logger per komponen, bukan per modul (§4, anti-pattern #7)

Ganti pola `structlog.get_logger(__name__)` (dipakai di seluruh 44 file)
dengan `structlog.get_logger(component=<nama_komponen_logis>)` — nilai
`component` mengikuti daftar contoh di §5.1 (`playback.controller`,
`radio.engine`, `ws.auth`, dst.), independen dari path file Python. Ini
satu perubahan mekanis yang menutup G11 sekaligus menyiapkan field
`component` wajib untuk G3.

**Alternatif yang dipertimbangkan dan ditolak:** bind `component` di tiap
call `logger.info(...)` satu per satu — ditolak karena mengulang nilai
yang sama ratusan kali dan gampang tidak sinkron dengan `category` per
kejadian. `get_logger(component=...)` mengikat sekali per modul.

### 2.3 Helper korelasi (§5.2)

Tambahkan `core/log_context.py` dengan tiga fungsi tipis di atas
`structlog.contextvars` yang sudah dipakai `traffic_middleware`:

- `bind_session(session_id: str)` — dipanggil sekali di
  `ConnectionManager.connect()`, sepanjang hidup koneksi WS.
- `bind_request(request_id: str)` — dipanggil di titik masuk
  `CommandBus.execute()` per eksekusi command.
- `bind_correlation(correlation_id: str)` — dipanggil di titik masuk
  alur yang menyeberang banyak task terjadwal (siklus radio, download
  yang punya progress hook di executor terpisah).

Ketiganya wrapper tipis atas `structlog.contextvars.bind_contextvars`/
`unbind_contextvars`, mengikuti pola yang sudah terbukti benar di
`server/middleware/traffic.py` (req_id). Fungsi-fungsi ini **wajib**
dipanggil oleh task async yang dijadwalkan terpisah (`asyncio.create_task`)
dengan meneruskan id yang sudah ada — bukan membuat context baru — untuk
menutup anti-pattern #9.

### 2.4 Penanda "CRITICAL belum pernah dipakai"

Tidak butuh helper baru — `logger.critical(...)` sudah tersedia dari
`structlog.stdlib.BoundLogger`. Yang dibutuhkan hanya disiplin memilih
level ini di titik yang tepat (lihat Fase 2).

**Acceptance criteria Fase 0:**
- `core/log_categories.py` dan `core/log_context.py` ada, punya test unit
  (bind/unbind simetris, tidak bocor antar task asyncio).
- Tidak ada perubahan behavior di modul lain — fase ini murni penyediaan
  alat, belum dipakai.

---

## 3. Fase 1 — Keamanan (G1, Kritis)

**Target file:** `server/handlers/auth.py` (0 baris log saat ini).

Tambahkan logging pada titik-titik berikut, semua `category=LC_AUTH`,
`component="ws.auth"`:

| Titik kode | Event | Level | Field |
|---|---|---|---|
| Verifikasi token sukses (baris ~74–79) | `auth_token_verified` | INFO | `client_ip` |
| Rate-limit terpicu, ≥5 percobaan (baris ~90–101) | `auth_rate_limited` | WARNING | `client_ip`, `attempt_count` |
| Login sukses via password (baris ~120–130) | `auth_login_succeeded` | INFO | `client_ip` |
| Login gagal — password/username salah (baris ~131–140) | `auth_login_rejected` | INFO | `client_ip`, `reason="invalid_credentials"` |
| Sesi token dibuat (`sessions.create_session`) | `auth_session_created` | INFO | `client_ip` |

Catatan kepatuhan §11.8/§12.1: **jangan pernah** menulis `token`,
`password`, atau `stored_hash` sebagai field — hanya `client_ip` dan
metadata non-rahasia. `auth_login_rejected` memakai level INFO (bukan
WARNING) karena satu percobaan gagal adalah kejadian normal yang
diharapkan terjadi sesekali (§3 INFO); baru jadi WARNING pada baris
`auth_rate_limited` ketika ambang batas terlampaui.

**Target file kedua:** `core/security.py` — tidak perlu logging tambahan
(fungsi hash/verify murni, hasil sudah tercermin di `auth.py`).

**Acceptance criteria:** setiap percobaan login (sukses/gagal) dan
setiap rate-limit menghasilkan tepat satu baris log; nol kemunculan
`password`/token mentah di `lunawave.log` (diverifikasi lewat grep test).

---

## 4. Fase 2 — Field Wajib & Severity (G2, G3 — Kritis)

### 4.1 Terapkan `component`/`category` ke seluruh 44 file yang logging

Mekanis, mengikuti §2.2: ganti `get_logger(__name__)` →
`get_logger(component=...)`, lalu tambahkan `category=LC_*` yang sesuai
di tiap call `logger.*` berdasarkan tabel §4 (bukan berdasarkan nama
file — lihat catatan `resolve` vs `radio` di §4 standar).

Urutan file (dari yang paling sedikit call logger ke yang paling
banyak, agar pola tervalidasi di file kecil dulu):
1. `persistence/discover_repo.py` (7 call, semua `logger.error`)
2. `engine/download_manager.py` (2 call)
3. `engine/playback/failure_ops.py` (3 call)
4. `adapters/mpv/observer.py` (5 call)
5. `adapters/ytdlp/resolver.py` (5 call)
6. `server/connection_manager.py` (3 call)
7. `core/command_bus.py`, `core/event_bus.py`
8. Sisa 37 file lain, per domain (playback → queue → cache → security → system)

### 4.2 Perbaikan severity yang salah kaprah (G7)

| Lokasi | Level saat ini | Level benar | Alasan |
|---|---|---|---|
| `adapters/mpv/observer.py:148` (`"MPV reconnect gagal setelah semua percobaan"`) | ERROR | **CRITICAL** | Playback inti mati total, bukan satu operasi — sesuai definisi §3 CRITICAL |
| `adapters/ytdlp/resolver.py:88` (bot-check → retry pertama) | sudah WARNING | tetap WARNING | Retry yang akhirnya berhasil = kondisi tertangani |
| `adapters/ytdlp/resolver.py:100` (fallback player client juga gagal) | ERROR | tetap ERROR | Operasi (resolve satu video_id) gagal total, proses lain tetap jalan |

### 4.3 Tambahkan CRITICAL di titik yang belum ada sama sekali (G2)

| Lokasi | Event | Level | Konteks |
|---|---|---|---|
| `server/app.py`, `run_server()` sekitar `await site.start()` (baris ~113–114, saat ini tanpa try/except) | `server_bind_failed` | CRITICAL | Bungkus `site.start()` dengan try/except; gagal bind port = proses tidak bisa melayani permintaan apa pun |
| `persistence/db.py`, `DatabaseConnection.init()` — kegagalan `executescript(schema_sql)` atau `aiosqlite.connect` | `db_init_failed` | CRITICAL | DB tidak bisa dibuka/migrasi saat boot = fitur inti mati total |
| MPV init awal (titik pertama koneksi IPC ke MPV saat startup, bukan reconnect saat runtime) | `mpv_initial_connect_failed` | CRITICAL | Berbeda dari `observer.py:148` (reconnect runtime) — ini kegagalan di startup, fitur playback tidak pernah hidup sama sekali |

**Acceptance criteria Fase 2:** grep `category=` dan `component=` di
`lunawave.log` menunjukkan 100% baris punya keduanya; minimal 3 event
CRITICAL baru muncul di test kegagalan yang disengaja (port terpakai,
DB path tidak bisa ditulis, MPV binary tidak ada).

---

## 5. Fase 3 — Korelasi Async (G4, Tinggi)

Terapkan helper Fase 0 (§2.3) di titik masuk masing-masing alur:

| Alur | Titik pemasangan | Field |
|---|---|---|
| Sesi WebSocket | `ConnectionManager.connect()` (`server/connection_manager.py`) | `session_id` — generate sekali per koneksi (mis. `secrets.token_hex(4)`, sama seperti pola `req_id` di `traffic.py`) |
| Eksekusi command | `CommandBus.execute()` (`core/command_bus.py`) | `request_id` — baru per eksekusi |
| Siklus radio | Titik mulai siklus di `engine/radio/engine.py` | `correlation_id` — diteruskan eksplisit ke `engine/radio/prefetcher.py` saat prefetch dijadwalkan sebagai task terpisah |
| Download | Titik mulai di `engine/download_manager.py` | `correlation_id` — diteruskan ke progress hook yang jalan di executor terpisah |

Karena `session_id` sudah aktif sepanjang koneksi WS, `request_id` yang
dibuat `CommandBus.execute()` otomatis muncul **bersama** `session_id`
di setiap baris log command (contextvars bertumpuk, tidak saling
menimpa) — ini yang dimaksud §5.2 "field korelasi wajib dibawa ke
setiap log sepanjang alur".

**Acceptance criteria:** satu eksekusi command dari klien WS tunggal
menghasilkan log yang semuanya berbagi `session_id` yang sama dan
`request_id` yang sama; satu siklus radio yang memicu prefetch di task
terpisah menghasilkan log prefetcher dengan `correlation_id` yang identik
dengan log radio engine yang memicunya (bukan `correlation_id` baru).

---

## 6. Fase 4 — Event Key & Structured Field (G5, Tinggi)

Ganti seluruh 71 call f-string/kalimat naratif menjadi `event` key
snake_case + field kwargs, per §6. Vocabulary event key baru yang
diusulkan (melengkapi contoh yang sudah ada di standar):

| File | Event key lama (naratif) | Event key baru | Field baru |
|---|---|---|---|
| `engine/playback/controller.py:362` | `"Ignoring skip: requested {x} != current {y}"` | `skip_ignored_stale` | `requested_video_id`, `current_video_id` |
| `server/connection_manager.py:55` | `"WebSocket connected. Total clients: {n}"` | `ws_connected` | `client_count` |
| `server/connection_manager.py:80` | `"WebSocket disconnected..."` | `ws_disconnected` | `client_count`, `duration_s` |
| `adapters/mpv/observer.py:133` | `"mpv observer loop ended - connection lost."` | `mpv_observer_loop_ended` | `reason="connection_lost"` |
| `adapters/mpv/observer.py:142` | `"MPV berhasil reconnect."` | `mpv_reconnected` | `attempt` |
| `adapters/mpv/observer.py:145` | `"MPV reconnect attempt {n} raised: {e}"` | `mpv_reconnect_attempt_failed` | `attempt`, `error_type`, `error` |
| `persistence/discover_repo.py` (4 fungsi, pola sama) | `"Error getting {X}: {e}"` | `discover_query_failed` | `query_type` (mis. `"bandit_ranked_artists"`, `"unheard_artists"`, `"taste_spectrum"`, `"genre_artists_enriched"`), `error_type`, `error` |
| `engine/playback/failure_ops.py:65` | `"Video permanen tidak tersedia, skip tanpa retry: {e}"` | `track_permanently_unavailable` | `video_id`, `reason` |
| `engine/playback/failure_ops.py:82` | `"Gagal memutar {title} ({type}): {e}"` | `track_play_failed` | `video_id`, `error_type`, `error` |
| `engine/playback/failure_ops.py:91` | `"Failed to play track {title}: {e}"` | `track_play_failed` (konsolidasi dengan baris 82) | sama |
| `core/command_bus.py:75` | `"Command execution error for '{cmd}': {e}"` | `command_execution_failed` | `command_name`, `error_type`, `error` |
| `adapters/ytdlp/resolver.py` (semua baris) | `"get_stream_url failed for {id}: ..."` | `stream_resolve_failed` | `video_id`, `error_type`, `error` |
| `engine/download_manager.py:142` | `"Download error: {e}"` | `download_failed` | `video_id`, `error_type`, `error` |

Catatan G9 (bahasa campur): field `reason`/`error` boleh berisi teks
Indonesia bila itu memang pesan exception domain, tapi **`event` key itu
sendiri selalu Inggris** — `failure_ops.py:82` dan `:91` yang saat ini
punya dua kalimat berbeda (ID vs EN) untuk kejadian yang sama harus
dikonsolidasi jadi satu event key (`track_play_failed`), seperti di
tabel di atas.

**Acceptance criteria:** pencarian literal untuk pola f-string
(`f"..."` yang mengandung `{` di dalam argumen pertama `logger.*`) di
seluruh 44 file bernilai nol.

---

## 7. Fase 5 — Titik Masuk/Keluar Alur Utama (G6, Tinggi)

Tambahkan pasangan log mulai/selesai (§7.2) yang saat ini tidak ada:

| Alur | Event mulai | Event selesai (sukses) | Event selesai (gagal) | Lokasi |
|---|---|---|---|---|
| Command | `command_received` (DEBUG — volume tinggi) | `command_succeeded` (DEBUG) | `command_execution_failed` (ERROR, sudah ada dari Fase 4) | `core/command_bus.py:execute()` |
| Siklus radio | `radio_cycle_started` (INFO) | `radio_cycle_completed` (INFO, dengan ringkasan §11.5: jumlah kandidat masuk/lolos) | `radio_cycle_failed` (ERROR) | `engine/radio/engine.py` |
| Download | `download_started` (INFO) | `download_completed` (INFO, `bytes`, `duration_ms`) | `download_failed` (ERROR, sudah ada) | `engine/download_manager.py` |

Catatan: `command_received`/`command_succeeded` sengaja DEBUG (bukan
INFO) karena volume command bisa tinggi di sesi pemakaian normal (skip,
seek, volume) — sesuai §8.2/§8.3, ini bukan kejadian yang tiap kali
perlu dilihat operator, tapi tetap berguna untuk debugging aktif.

**Target tambahan §7.4 (perubahan state signifikan):** tambahkan log
`playback_mode_changed`, `loudness_normalization_changed`,
`crossfade_changed` di handler `_on_set_mode` dkk. (`engine/playback/`),
level INFO, field nilai baru — saat ini nol logging di jalur ini.

**Target tambahan §7.8 (task background):** `engine/radio/prefetcher.py`
dan cache-eviction loop di `bootstrap/startup_tasks.py` perlu event
`prefetch_loop_stopped_unexpectedly` / `cache_eviction_loop_stopped_unexpectedly`
(ERROR) bila loop berhenti tanpa sinyal shutdown eksplisit — pola sama
seperti yang sudah benar di `adapters/mpv/observer.py:133`.

---

## 8. Fase 6 — Bersihkan Duplikasi Lintas Lapisan (G8, Sedang)

`adapters/ytdlp/resolver.py` mencatat ERROR saat gagal, lalu meneruskan
exception yang sama ke tiga pemanggil berbeda (`track_loader.py`,
`stream_prefetch.py:73-80`, `download_manager.py:142`) yang mencatat
ERROR/WARNING lagi tanpa informasi baru.

**Keputusan:** log hanya di titik final (boundary asal, `resolver.py`),
pemanggil di atasnya **berhenti logging** exception yang sama — cukup
`raise`/propagate. Kekecualian: bila pemanggil menambah konteks baru
yang tidak diketahui `resolver.py` (mis. `download_manager.py` tahu
`video_id` mana yang sedang di-download saat resolve gagal di
tengah-tengah unduhan) — dalam kasus ini pemanggil boleh log ulang
**hanya jika** menambahkan field yang resolver.py sendiri tidak punya,
bukan mengulang pesan yang sama.

Berlaku juga prinsip §11.4 (log sekali per kejadian): pilih titik final
yang paling informatif dengan `retry_count`, diamkan yang lain.

---

## 9. Fase 7 — Housekeeping (G10, Rendah)

- `engine/radio/track_filter.py`: tambahkan **satu** baris ringkasan
  agregat (`radio_filter_completed`, INFO, field `candidates_in`,
  `candidates_out`, `duration_ms`) di akhir filtering — bukan log
  per-kandidat (§8.2 tetap berlaku).
- Verifikasi ulang tidak ada regresi over-logging di hot path (`§8`):
  jalankan smoke test playback normal 10 menit, hitung baris log/menit
  sebelum dan sesudah migrasi — kenaikan signifikan di luar event baru
  yang memang diharapkan (login attempts, command received di DEBUG)
  adalah sinyal ada log yang seharusnya diringkas.

---

## 10. Urutan Eksekusi & Estimasi

| Fase | Isi | Prioritas audit | Blocker bagi fase lain? |
|---|---|---|---|
| 0 | Infrastruktur (`log_categories.py`, `log_context.py`, `get_logger(component=...)`) | — | Ya, wajib duluan |
| 1 | Logging auth (`auth.py`) | G1 Kritis | Tidak |
| 2 | `category`/`component` di 44 file + severity CRITICAL | G2, G3 Kritis | Ya, untuk Fase 3–7 |
| 3 | Korelasi `session_id`/`request_id`/`correlation_id` | G4 Tinggi | Tidak |
| 4 | Event key + field terstruktur (71 call) | G5 Tinggi | Tidak |
| 5 | Titik masuk/keluar alur (`command`, `radio`, `download`) | G6 Tinggi | Tidak |
| 6 | Hapus duplikasi log lintas lapisan | G8 Sedang | Tidak |
| 7 | Ringkasan agregat `track_filter.py` + validasi noise | G10 Rendah | Tidak |

Fase 2 adalah gerbang: begitu selesai, setiap baris log baru yang ditulis
di Fase 3–7 otomatis punya lima field wajib (§5.1) karena
`get_logger(component=...)` + `category=` sudah jadi kebiasaan yang
dipakai di setiap call baru.

---

## 11. Definisi Selesai (Definition of Done) Keseluruhan

Migrasi dianggap selesai ketika, untuk setiap baris log yang diterbitkan
aplikasi:

1. `timestamp`, `level`, `category`, `event`, `component` terisi (Ringkasan
   Kontrak standar, lima pertanyaan).
2. `session_id`/`request_id`/`correlation_id` hadir di setiap baris yang
   memang berada dalam konteks sebuah alur (bukan di banner lifecycle).
3. Nol pola f-string bernilai dinamis di posisi `event`/pesan pertama.
4. `logger.critical` dipakai di ≥3 titik kegagalan startup/proses
   (bind port, init DB, MPV initial connect) sesuai §3.
5. `server/handlers/auth.py` punya jejak lengkap login sukses/gagal,
   rate-limit, dan sesi dibuat — tanpa satu pun nilai rahasia di field
   apa pun.
6. Tidak ada exception yang sama dicatat lebih dari sekali di lapisan
   pemanggil berbeda tanpa informasi baru.
