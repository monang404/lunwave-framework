# ADR-0010: Observability Baseline — Log Traceable, Traffic/Uptime, RAM Cross-Platform

**Status:** Accepted
**Date:** 2026-07-22

---

## Konteks

LunaWave sudah punya fondasi observability parsial: `structlog` dengan
`simple_renderer` (single-line, file + console), dan Prometheus metrics
dasar (`COMMAND_COUNT`, `COMMAND_LATENCY`, `EVENT_COUNT`,
`ACTIVE_WEBSOCKETS`, `RESOLVE_LATENCY`) yang diekspos di `/metrics`, serta
`/health` yang cuma melaporkan status DB dan mpv.

Yang belum ada: uptime server, uptime per sesi user aktif, ringkasan traffic
HTTP/WS yang mudah ditrace manusia, dan penggunaan RAM proses. Ada juga
riwayat kegagalan implementasi serupa sebelumnya, disebabkan dua hal:

1. **Karakter/tool yang tidak portable** antara Termux (Android) dan
   Windows — mis. ANSI escape yang bocor ke file log, atau tool CLI
   (`tput`, `/proc`, dll.) yang hanya ada di salah satu platform.
2. **Dependency berat untuk baca RAM** (`psutil`) yang gagal di-install di
   Termux karena butuh compile native tanpa build tools yang memadai.

## Keputusan

1. **Log ke file selalu plain ASCII**, tanpa ANSI escape apa pun. Warna di
   console **auto-detect** murni dari `sys.stdout.isatty()` (+ cek `TERM`
   tidak `dumb`/kosong) — **tidak ada env var atau flag manual** untuk
   menyalakan/mematikan warna. Default aman = tanpa warna kalau ragu.
2. **Correlation id** (`req_id` pendek) di-attach ke tiap request HTTP dan
   sesi WebSocket lewat `structlog.contextvars`, supaya satu alur request
   bisa di-`grep` dari baris pertama sampai terakhir di `lunawave.log`.
3. **Traffic metrics** (request count, bytes in/out, WS message count)
   dikumpulkan di satu middleware aiohttp tunggal
   (`server/middleware/traffic.py`), bukan tersebar di banyak handler.
4. **Uptime** disimpan di modul kecil dependency-free `core/server_clock.py`
   (`start_time` + `uptime_seconds`), dipakai di `/health` dan log ringkasan
   periodik.
5. **Durasi sesi user aktif** dicatat di `ConnectionManager` (`connected_at`
   per WS), di-log saat disconnect, dan diekspos sebagai histogram
   Prometheus baru.
6. **RAM dibaca tanpa dependency baru.** Modul `core/mem_stats.py`:
   - Linux/Termux → baca `VmRSS` dari `/proc/self/status` (selalu ada,
     kernel Linux Android).
   - Windows → `ctypes` + `psapi.GetProcessMemoryInfo` (API bawaan OS, tidak
     perlu install apa pun).
   - Platform lain / gagal baca → kembalikan `None`, ditampilkan sebagai
     `n/a`, **tidak pernah** melempar exception ke pemanggil.
7. Semua akses platform-specific mengikuti pola yang sudah ada di repo
   (`sys.platform == "win32"` di `launcher/process.py`,
   fail-open + `shutil.which()` di `plugins/notifications.py`): dibungkus
   try/except, no-op aman kalau tidak didukung.

## Alasan

Pendekatan ini secara langsung menghindari dua akar penyebab kegagalan
sebelumnya: tidak ada dependency baru yang butuh compile (RAM), dan tidak
ada mekanisme kosmetik (warna) yang butuh dikonfigurasi manual per
platform — semuanya auto-detect dan fail-safe ke opsi paling polos/aman.

## Konsekuensi

- File baru: `core/server_clock.py`, `core/mem_stats.py`,
  `server/middleware/traffic.py`.
- File dimodifikasi: `core/log_config.py`, `core/observability.py`,
  `server/app.py`, `server/connection_manager.py`,
  `server/handlers/http.py`.
- Tidak menyentuh `engine/playback/controller.py`,
  `server/handlers/websocket.py` (isi internal), atau
  `web/static/index.html`.
- Tidak menambah env var baru untuk fitur ini.
- Menambah 1 background task periodik (ringkasan status ke log) — perlu
  dipastikan berhenti bersih saat shutdown (ikuti pola task lain di
  `bootstrap/`).

## Referensi

- Dokumen RFC: `docs/rfc/observability_logging/observability_logging.md`
- Rencana Kerja: `docs/rfc/observability_logging/task_breakdown_observability.yaml`
