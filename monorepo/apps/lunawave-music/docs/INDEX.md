---
title : LunaWave Documentation Index
last_verified: 2026-07-22
sprint: Phase 8 (selesai) + Hardening
status: current
---

## Quick Navigation

1. `AI_CONTEXT.md` → **baca ini dulu** — constraints, alur kerja AI, automation
2. `STATUS.md` → kondisi per-file & sprint target
3. `PATCHLOG.md` → perubahan terakhir
4. `REPORT.md` → analisis, temuan, statistik (auto-generated)
5. `FILE_INDEX.md` → inventaris file (auto-generated, jangan edit manual)
6. `architecture/folder_structure.md` → detail struktur setiap folder dan penggunaannya
7. `architecture/overview.md` → arsitektur impian, target desain, dan blueprint
8. `adr/` → Architecture Decision Records

# Untuk AI Agent

## Baca urutan ini sebelum kerja:
1. `docs/AI_CONTEXT.md` — **wajib pertama**, berisi constraints, batasan, dan alur kerja lengkap
2. `docs/STATUS.md` — kondisi per-file & sprint target
3. `docs/PATCHLOG.md` — 2-3 entri terakhir
4. Jalankan `python automation/find_owner.py <nama_file_atau_class>` — orientasi modul yang relevan
5. Baru sentuh source code

> ⚙️ `FILE_INDEX.md` dan blok statistik `REPORT.md` adalah **auto-generated** — jangan edit manual.
> Jalankan `python automation/generate_file_index.py` atau `run_all.py` setelah ada perubahan kode.

## Setelah selesai kerja:
1. Jalankan `python automation/doctor.py` — satu perintah untuk semua health check
2. Jalankan `python automation/generate_file_index.py` — jika ada file/class/fungsi yang berubah
3. Jalankan `python automation/generate_report.py` — jika ada penambahan/penghapusan file
   *(atau `python automation/run_all.py` untuk jalankan semua sekaligus)*
4. Catat entry ke `docs/PATCHLOG.md` via `python automation/patchlog.py add` (format field-based wajib)
5. Update `docs/STATUS.md` jika kondisi file berubah

## ⚠️ Danger Zones — hati-hati ekstra:
| File | Kenapa Berbahaya | Instruksi |
|------|-----------------|-----------|
| `engine/playback/controller.py` | Closure kompleks, referensi silang | Jangan refactor tanpa sprint plan |
| `server/handlers/websocket.py` | Logic handshake + routing — restricted file | Jangan pecah tanpa persetujuan eksplisit |
| `data/artists_enriched.json` | ~185KB JSON statis, sumber truth artis | Jangan modifikasi manual |

## ❌ Yang TIDAK BOLEH dilakukan AI:
- Jangan ganti aiohttp ke framework lain (FastAPI, dll)
- Jangan tambah JS framework apapun di frontend
- Jangan ganti SQLite ke database lain
- Jangan refactor 2 tahap sekaligus dalam 1 commit




# LunaWave — Project Knowledge Base Index

> **Last Scan:** 2026-07-22
> **Source:** Source code + `docs/architecture/folder_structure.md`

---

## Tujuan Project

LunaWave adalah **pemutar musik berbasis YouTube** yang berjalan sebagai server lokal (aiohttp + asyncio), diakses via browser mobile/desktop. Audio diputar oleh MPV melalui IPC socket. Dirancang untuk Termux (Android) sebagai host utama, dengan dukungan Windows. Sebelumnya dikenal sebagai *YT Termux Player / bagas.fm / ytgui*.

Fitur utama: Radio autoplay (Thompson Sampling bandit), Queue mode, SponsorBlock, lirik real-time (LRCLIB), smart caching MP3, EBU R128 loudness normalization, portal Admin/Client dengan Initial Setup. Arsitektur EventBus sudah menyiapkan fondasi multi-room untuk pengembangan mendatang (belum aktif — lihat ADR-0005).

---

## Entry Point Aplikasi

| Jalur | File | Keterangan |
|-------|------|------------|
| **Backend utama** | `main.py` | `asyncio.run(main())` — inisialisasi semua komponen, lalu menjalankan web server |
| **GUI launcher** | `start.py` → `launcher/__main__.py` | Tkinter wrapper; fallback headless ke `main.py` |
| **Shell (Linux/Termux)** | `start.sh` | Bash launcher dengan env var setup |
| **Shell (Windows)** | `start.bat` | Batch launcher |

---

## Struktur Folder Utama

```
lunawave/
├── main.py            Entry point backend
├── config.py          Konfigurasi global & env vars
├── start.py           Bootstrap launcher GUI
├── core/              Primitives: state, bus, events, ports, security, commands
├── adapters/          External system adapters (Hexagonal)
│   ├── mpv/           IPC adapter ke MPV player
│   └── ytdlp/         Wrapper yt-dlp client
├── engine/            Domain logic: radio, playback, queue, loudness
│   ├── playback/      controller + queue_ops + mode_ops + crossfade + dll.
│   ├── radio/         engine + prefetcher + artist_selector + bandit + dll.
│   └── loudness/      EBU R128 normalization pipeline
├── bootstrap/         Startup tasks: power lock, maintenance, wiring services
├── persistence/       Data layer: repositories SQLite (track, library, discover, dll.)
├── server/            HTTP & WebSocket layer (aiohttp)
│   ├── handlers/      auth, http, setup, websocket, ws_*, event_listeners
│   └── broadcast_service.py  Push state ke semua WS clients
├── cache/             resolver.py — waterfall resolve stream URL
├── data/              DB aktif, artists JSON
├── services/          High-level: DiscoverService, StreamPrefetchService
├── plugins/           Opsional: lyrics_fetcher/parser/sync, notifications, sponsorblock
├── launcher/          GUI launcher (Tkinter)
│   └── gui/           pecahan gui: app, ui_builder, status_panel, log_panel, dep_checker
├── web/               Frontend (vanilla JS + CSS)
│   └── static/
│       ├── index.html SPA monolitik
│       ├── js/        main, audio, ws, store, dom, utils + subdirs
│       └── css/       tokens, components, layout, platform, base
├── automation/        Dev utilities & health checkers (doctor, find_owner, patchlog, dll.)
├── scratch/           Dev scratch files
└── docs/              Dokumentasi project ini
```

---

## Modul Utama & Fungsi Singkat

| Modul | Fungsi |
|-------|--------|
| `config.py` | Semua konstanta & env vars (`DB_PATH`, `MPV_SOCKET`, `WEB_PORT`, dll.) |
| `core/state.py` | `AppState`, `TrackInfo`, enums `PlayerStatus`, `PlaybackMode`, `AudioOutput` |
| `core/event_bus.py` | Pub/sub `EventBus` singleton (`bus`) |
| `core/command_bus.py` | Single-writer `CommandBus` + `core/commands.py` |
| `core/events.py` | `DomainEvent` dataclasses (TrackStarted, TrackEnded, dll.) |
| `core/ports.py` | Protocol interfaces: `AudioPlayerPort`, `MediaExtractorPort`, `DatabasePort`, dll. |
| `core/security.py` | PBKDF2 password hash, SHA-256 token hash, constant-time verify |
| `adapters/mpv/` | IPC ke MPV (Unix socket / named pipe): play, pause, seek, volume, reconnect |
| `adapters/ytdlp/` | Wrapper yt-dlp: search, get_stream_url, download_mp3 |
| `engine/radio/engine.py` | Autonomous radio: artist bandit (Thompson Sampling), prefetch, deduplication, standby queue |
| `engine/playback/controller.py` | Orkestrator playback: play, pause, next, prev, seek, mode switch |
| `engine/loudness/service.py` | EBU R128 loudness normalization pipeline (ffprobe → gain calc → MPV af) |
| `bootstrap/startup_tasks.py` | Wiring background services saat startup (power lock, maintenance, dll.) |
| `persistence/` | SQLite via aiosqlite: track, session, admin_account, artist, genre, library, discover, stream_cache |
| `cache/resolver.py` | Resolve stream URL: local path → cache DB → yt-dlp (waterfall) |
| `server/app.py` | aiohttp app factory + runner, web.AppKey constants |
| `server/handlers/websocket.py` | WS lifecycle + Origin validation (CSWSH) + command dispatch |
| `server/handlers/auth.py` | Login WS handler, token issue, rate limit per IP |
| `server/handlers/setup.py` | Initial Setup handler (buat admin_account pertama kali) |
| `server/broadcast_service.py` | Push state/progress/lyrics ke semua WS clients |
| `services/discover_service.py` | Query recent, favorites, artists, genres, personalisasi dari DB |
| `plugins/lyrics_fetcher.py` | Fetch LRC dari lrclib.net |
| `plugins/lyrics_sync.py` | Sync lirik dengan posisi playback via EventBus |
| `plugins/notifications.py` | Termux MediaStyle notification (no-op di luar Termux) |
| `plugins/sponsorblock.py` | Fetch & skip sponsor segments via SponsorBlock API |
| `launcher/gui/app.py` | ServerManager (Tkinter): start/stop server, log viewer, dependency check |

---

## Statistik Project

> Statistik aktual ada di `docs/REPORT.md` §Statistik Project (auto-generated, selalu akurat).
> Angka di bawah ini **tidak diupdate manual** — lihat REPORT.md untuk data terkini.

---

## Cara Membaca Dokumentasi

```
docs/
├── AI_CONTEXT.md         ← Entry point AI — baca ini dulu
├── INDEX.md              ← Orientasi & navigasi (ini)
├── STATUS.md             ← Kondisi per-file & sprint target
├── architecture/folder_structure.md ← Detail struktur setiap folder
├── FILE_INDEX.md         ← Inventaris file (sebagian auto-generated)
├── PATCHLOG.md           ← Riwayat perubahan (append-only)
├── REPORT.md             ← Analisis, temuan, statistik (sebagian auto-generated)
└── adr/                  ← Architecture Decision Records
```
