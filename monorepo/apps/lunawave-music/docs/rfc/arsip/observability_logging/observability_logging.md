---
title: LunaWave — RFC Observability Baseline (Log Traceable + Traffic/Uptime + RAM)
last_verified: 2026-07-22
sprint: pasca Hardening — persiapan sprint observability
status: PLANNING — belum ada task yang dieksekusi
---

# observability_logging.md

## Ringkasan

Merapikan output log (`lunawave.log` + console) agar human-readable dan
mudah ditrace, sekaligus menambah monitoring runtime: traffic HTTP/WS,
uptime server, uptime sesi user aktif, dan penggunaan RAM proses. Berlaku
untuk ketiga entrypoint (`start.py`, `start.sh`, `start.bat`) karena
semuanya bermuara ke `python main.py`.

Ini menindaklanjuti percobaan sebelumnya yang gagal karena masalah lintas
platform Termux ↔ Windows (lihat ADR-0010 §Konteks). Prinsip desain di RFC
ini secara eksplisit dirancang untuk menghindari akar masalah itu, bukan
cuma menambah fitur.

## Non-Goals

- **Tidak** menambah dependency baru (tidak ada `psutil`, tidak ada
  `colorama`, dst).
- **Tidak** menambah env var baru.
- **Tidak** mengubah `server/handlers/websocket.py` secara struktural —
  hanya dipakai (baca `connected_at`), tidak dipecah/direfactor.
- **Tidak** mengubah `engine/playback/controller.py`.
- **Tidak** mengubah tampilan `web/static/index.html` — fitur ini murni
  backend + terminal/log, bukan UI baru di web app.

## Keputusan Desain

Lihat ADR-0010 untuk keputusan lengkap. Ringkasan cepat:

| # | Topik | Keputusan |
|---|---|---|
| 1 | Warna log | Auto-detect `isatty()`, tanpa toggle manual, file selalu plain |
| 2 | Correlation id | `structlog.contextvars`, 1 id per request/sesi WS |
| 3 | Traffic | 1 middleware aiohttp terpusat, bukan tersebar di handler |
| 4 | Uptime | `core/server_clock.py` baru, dependency-free |
| 5 | Durasi sesi user | Dicatat di `ConnectionManager`, histogram Prometheus |
| 6 | RAM | `core/mem_stats.py` baru — `/proc` di Linux/Termux, `ctypes`+`psapi` di Windows, `None` kalau gagal |
| 7 | Platform-specific code | Pola `sys.platform == "win32"` + try/except fail-open, konsisten dengan `launcher/process.py` |

## Bentuk Output (contoh)

Console (interaktif, ada warna):
```
[14:02:10] INFO : WebSocket connected client_id=8f2a total=2
[14:02:41] INFO : req_id=a91c GET /api/tracks status=200 dur=42ms
[14:15:10] INFO : [STATUS] uptime=13m aktif=2 req=87 ram=181MB
```

File `lunawave.log` (plain, tanpa ANSI):
```
==== SESSION START pid=41210 host=0.0.0.0 port=8765 2026-07-22T14:02:00 ====
[14:02:10] INFO: WebSocket connected client_id=8f2a total=2
[14:02:41] INFO: req_id=a91c GET /api/tracks status=200 dur=42ms
[14:15:10] INFO: [STATUS] uptime=13m aktif=2 req=87 ram=181MB
```

`/health` (tambahan field):
```json
{
  "status": "ok",
  "db": "connected",
  "mpv": "connected",
  "uptime_seconds": 812,
  "memory_mb": 181.4,
  "active_connections": 2
}
```

## Task Breakdown

Detail eksekusi (file, dependency antar-task, urutan sesi, definition of
done) ada di `task_breakdown_observability.yaml` di folder yang sama.
Ringkasan sesi:

1. **Sesi 0** — baca governance (`AI_CONTEXT.md`, `STATUS.md`, patch
   terakhir), tentukan nomor `PATCH-` berikutnya.
2. **Sesi 1** (paralel) — modul baru dependency-free: `core/mem_stats.py`,
   `core/server_clock.py`.
3. **Sesi 2** — tambah metric Prometheus baru di `core/observability.py`
   (butuh nama gauge/histogram dari sesi 1 sebagai referensi).
4. **Sesi 3** (dedicated, karena wiring `server/app.py` sensitif) —
   middleware traffic + registrasi di `server/app.py` +
   `server/connection_manager.py` (durasi sesi WS).
5. **Sesi 4** — `/health` diperkaya + task periodik `[STATUS]` ke log.
6. **Sesi 5** — finalisasi dokumen: ADR-0010 jadi `Accepted`, update
   `docs/STATUS.md`, jalankan `doctor.py`, patchlog per grup task.

## Verifikasi Wajib Sebelum Merge

- `python automation/doctor.py` tanpa `FAIL` baru.
- Jalankan `start.sh` di Termux (atau simulasi Linux) **dan** `start.bat`
  di Windows minimal sekali masing-masing — cek file `lunawave.log` tidak
  mengandung byte escape ANSI (`grep -P '\x1b\['`) dan `/health` menampilkan
  `memory_mb` bukan `null` di kedua platform (atau `null` yang memang
  ter-fallback wajar, bukan crash).
- Test unit baru untuk `core/mem_stats.py` dan `core/server_clock.py`
  (mirror-path, sesuai aturan testing repo).
