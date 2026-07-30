# API Reference

← [architecture/backend.md](../architecture/backend.md) | [Blueprint.md](../Blueprint.md)

---

## Gambaran Umum

LunaWave menyediakan dua jalur API:

- **WebSocket** `/ws` — komunikasi real-time dua arah (aksi + state broadcast), **termasuk autentikasi** (lihat [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md))
- **HTTP** — file statis, status, cek kebutuhan setup

Semua aksi user (termasuk login & Initial Setup) dikirim lewat WebSocket
sebagai `cmd`. HTTP hanya untuk bootstrap: load `index.html`, cek
`/api/setup-required`, dan streaming file statis/audio.

Alasan single-channel WS → [ADR-0005](../adr/0005-websocket-single-channel.md)

---

## WebSocket API

### Koneksi

```
ws://localhost:{PORT}/ws
```

Koneksi WS dibuka **tanpa token** — client langsung `connect()` dan
menerima snapshot `state` awal, tidak ada gate token di level koneksi.
Autentikasi terjadi lewat aksi WS setelah koneksi terbuka (lihat
[Autentikasi & Setup](#autentikasi--setup-fitur-b) di bawah). Sebelum
berhasil `auth`, hanya action `auth` dan `setup_admin` yang diterima —
action lain ditolak dengan pesan error `"Akses ditolak. Silakan login
sebagai Admin."` (lihat `require_auth()` di `server/handlers/websocket.py`).

> **CSWSH Protection:** Server memvalidasi header `Origin` saat handshake.
> Browser dari domain lain akan mendapat `HTTP 403` sebelum koneksi WS terbuka.
> Klien non-browser (curl, Termux, Python) yang tidak mengirim `Origin` tetap
> diizinkan connect (lihat `check_ws_origin()` di `websocket.py`).

### Format Pesan — Client → Server (Command)

Semua command dikirim dengan format:

```json
{
  "type": "cmd",
  "action": "nama_action",
  "data": {}
}
```

### Format Pesan — Server → Client (State)

```json
{
  "type": "state | error | auth_status | setup_status | lyric_line | download_progress",
  "data": {}
}
```

---

## WebSocket Commands

### Autentikasi & Setup (Fitur B)

Dikirim sebagai `{"type": "cmd", "action": "...", "data": {...}}` — format
berbeda dari command domain lain (`cmd`/`payload`) karena kedua action ini
harus reachable sebelum `require_auth()`.

| Action | Payload | Keterangan |
|---|---|---|
| `setup_admin` | `{"username": "admin", "password": "..."}` | Buat akun admin (satu kali saja). Ditolak (`success: false`) kalau akun sudah ada. Rate limit 5x/5menit per IP. |
| `auth` | `{"username": "admin", "password": "..."}` atau `{"token": "..."}` | Login dengan kredensial, atau verifikasi token sesi yang sudah ada. Rate limit 5x/5menit per IP untuk percobaan password. Token yang diterima server di-hash SHA-256 sebelum dicari di DB. |
| `logout` | `{"token": "..."}` | Hapus sesi dari DB dan cabut koneksi dari authenticated set. |

Respons dikirim sebagai `setup_status` / `auth_status`:

```json
// setup_admin sukses
{"type": "setup_status", "data": {"success": true}}

// setup_admin gagal (akun sudah ada, input invalid, atau DB error)
{"type": "setup_status", "data": {"success": false, "message": "..."}}

// auth sukses
{"type": "auth_status", "data": {"success": true, "token": "..."}}

// auth gagal
{"type": "auth_status", "data": {"success": false, "message": "Username atau Password salah!"}}
```

Kredensial disimpan di tabel `admin_account` (SQLite), diisi lewat
`setup_admin` — bukan lagi di-generate otomatis atau disimpan sebagai file.
Lihat [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md) untuk alasan
lengkap (tanpa migrasi otomatis dari file password lama, env var override
`LUNAWAVE_ADMIN_PASS` tetap tersedia untuk provisioning non-interaktif).

Untuk mengecek apakah Initial Setup masih diperlukan sebelum menampilkan
form yang tepat (Setup vs Login), client memanggil `GET /api/setup-required`
— lihat [HTTP API](#http-api) di bawah.

### Playback

| Command | Payload | Keterangan |
|---|---|---|
| `play_track` | `{"video_id": "abc123"}` | Mainkan track dari video_id |
| `toggle_pause` | `{}` | Pause/resume toggle |
| `stop` | `{}` | Stop dan reset posisi |
| `next` | `{}` | Skip ke track berikutnya |
| `prev` | `{}` | Kembali ke track sebelumnya |
| `seek` | `{"position": 42.5}` | Seek ke posisi (detik) |
| `volume_set` | `{"volume": 75}` | Set volume (0–**150**) |
| `volume_up` | `{}` | Volume naik (+5) |
| `volume_down` | `{}` | Volume turun (-5) |
| `set_mode` | `{"mode": "QUEUE\|RADIO"}` | Ganti mode playback |
| `set_output` | `{"output": "browser\|device"}` | Ganti output audio |
| `set_loop` | `{"mode": "off\|track\|queue"}` | Set loop mode |
| `set_speed` | `{"speed": 1.5}` | Set kecepatan putar (0.25–4.0) |
| `set_sleep_timer` | `{"minutes": 15}` | Sleep timer (0 = off) |
| `set_crossfade` | `{"enabled": true}` | Toggle crossfade |
| `set_loudness_normalization` | `{"enabled": true}` | Toggle EBU R128 loudness normalization |
| `set_sponsorblock` | `{"enabled": true}` | Toggle SponsorBlock |
| `lyrics_offset` | `{"offset": -0.5}` | Adjust lyrics offset (detik) |

### Queue

| Command | Payload | Keterangan |
|---|---|---|
| `queue_add` | `{"video_id": "abc", "position": null}` | Tambah ke queue (null = akhir) |
| `queue_remove` | `{"index": 2}` | Hapus dari index |
| `queue_reorder` | `{"from_index": 1, "to_index": 3}` | Pindah posisi (drag & drop) |
| `queue_select` | `{"index": 0}` | Mainkan langsung dari posisi queue |
| `enqueue_artist_songs` | `{"artist": "Radiohead"}` | Tambah semua lagu artis ke queue |
| `enqueue_genre_songs` | `{"genre": "Rock"}` | Tambah semua lagu genre ke queue |

### Radio

| Command | Payload | Keterangan |
|---|---|---|
| `radio_randomize` | `{"seed_artist": null}` | Randomize sumber artis radio |

### Download

| Command | Payload | Keterangan |
|---|---|---|
| `download` | `{}` | Download track yang sedang diputar |
| `delete_download` | `{"video_id": "abc123"}` | Hapus file download lokal |

### Search & Discover

| Command | Payload | Keterangan |
|---|---|---|
| `search` | `{"query": "bohemian rhapsody"}` | Cari track via yt-dlp |
| `discover` | `{}` | Dapatkan data discover (for_you, taste_spectrum, dll.) |
| `discover_search` | `{"query": "radiohead"}` | Quick search di database lokal (FTS5) |
| `get_artist_detail` | `{"artist": "Radiohead"}` | Detail artis: lagu, genre, stats bandit |

### Cache

| Command | Payload | Keterangan |
|---|---|---|
| `get_cache_size` | `{}` | Query ukuran folder cache MP3 |
| `clear_cache` | `{}` | Hapus semua file MP3 di cache |

---

## WebSocket State Events

Server broadcast state setelah setiap perubahan yang relevan.

### `state` — State Snapshot (Periodik & Event-driven)

Dikirim setelah setiap perubahan yang relevan. Berisi **state lengkap**.

```json
{
  "type": "state",
  "status": "PLAYING",
  "playback_mode": "QUEUE",
  "current_track": {
    "video_id": "abc123",
    "title": "Creep",
    "artist": "Radiohead",
    "duration": 243,
    "thumbnail": "https://...",
    "is_cached": false,
    "is_favorite": false
  },
  "position": 42.5,
  "duration": 243.0,
  "volume": 80,
  "playback_speed": 1.0,
  "loop_mode": "off",
  "crossfade_enabled": false,
  "audio_output": "browser",
  "sponsorblock_active": false,
  "loudness_normalization_enabled": true,
  "queue": [{"video_id": "def", "title": "Karma Police", ...}],
  "radio_queue": [],
  "history_count": 3,
  "lyrics_index": 12,
  "lyrics_offset": 0,
  "active_tab": "home",
  "error_msg": null,
  "is_online": true,
  "download_progress": null
}
```

### `lyric_line` — Lyric Sync

```json
{
  "type": "lyric_line",
  "line": "I wish I was special",
  "timestamp": 68.4,
  "next_timestamp": 72.1
}
```

### `download_progress`

```json
{
  "type": "download_progress",
  "video_id": "abc123",
  "pct": 63,
  "status": "downloading | done | error"
}
```

### `error`

```json
{
  "type": "error",
  "code": "STREAM_NOT_FOUND | DOWNLOAD_FAILED | RADIO_NO_TRACKS | AUTH_EXPIRED",
  "message": "Deskripsi error untuk display"
}
```

---

## HTTP API

### `GET /api/setup-required`

Dipanggil client saat load, **sebelum** memutuskan tampilkan form Setup
atau form Login. Tidak memerlukan auth.

```json
{ "setup_required": true }
```

### `GET /`, `GET /admin`

Serve `web/static/index.html`. Frontend sendiri yang memutuskan tampilan
(Setup / Login / player) berdasarkan hasil `/api/setup-required` dan status
auth WS — tidak ada redirect server-side ke halaman login terpisah lagi.

### `GET /api/stream/{video_id}`

Stream audio langsung (tanpa download). Proxy ke URL stream yang di-resolve dari yt-dlp.

### `GET /health`

Health check, tidak memerlukan auth.

### `GET /metrics`

Metrics/observability endpoint, tidak memerlukan auth.

---

## Middleware

### Rate Limiting (`server/middleware.py`)

- `check_rate_limit()`: 30 command WS per menit per IP (sliding window),
  ditegakkan di `server/handlers/websocket.py` untuk semua action selain
  `auth`/`setup_admin` (yang punya rate limit sendiri, lihat
  [Autentikasi & Setup](#autentikasi--setup-fitur-b) di atas).

### Autentikasi

Tidak ada lagi middleware token per-HTTP-request atau query-param token di
level koneksi WS (lihat [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md)).
Gate auth ditegakkan per-action di `handle_ws_message()`
(`server/handlers/websocket.py`) via `require_auth(manager, ws)`, yang
mengecek keanggotaan koneksi di `manager.authenticated_connections` —
diisi setelah action `auth` sukses.

### CORS

Dikonfigurasi hanya untuk origin lokal (`localhost`, `127.0.0.1`) karena LunaWave tidak didesain sebagai layanan publik.

---

## Kode Error WebSocket

Sejak Fitur B, koneksi WS tidak lagi ditutup untuk masalah auth (tidak ada
lagi gate token di level koneksi — lihat
[Koneksi](#koneksi) di atas). Kegagalan auth per-action dikirim sebagai
pesan `auth_status`/`setup_status` (`success: false`), bukan penutupan
koneksi.

| Kode | Arti |
|---|---|
| `1000` | Normal closure |
| `1011` | Server error tak terduga |

---

## Dokumen Terkait

- [backend/services.md](services.md) — Handler yang memproses setiap command
- [architecture/data_flow.md](../architecture/data_flow.md) — Sequence diagram request flow
- [frontend/state_management.md](../frontend/state_management.md) — Cara frontend memproses state
- [frontend/routing.md](../frontend/routing.md) — WS message routing di frontend
- [ADR-0005](../adr/0005-websocket-single-channel.md) — Kenapa single channel WS?
- [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md) — Kredensial admin di SQLite, tanpa migrasi otomatis
- [security/threat_model.md](../security/threat_model.md) — Catatan desain kredensial admin (K3)
