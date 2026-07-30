---
title : LunaWave Project Status
last_verified: 2026-07-27
sprint:
---

# STATUS.md — Kondisi File per Sprint

> Tabel ini adalah satu-satunya source of truth untuk "sudah sampai mana?"
> Update setiap sprint selesai.

## Security & Bug Fixes — Fase 4 Cleanup & Konsistensi (2026-07-27)

Task file `docs/rfc/bug_fix/04_fase4_cleanup_dan_konsistensi.yaml` selesai dieksekusi.

| File | Perubahan |
|---|---|
| `core/security.py` | Hapus dead code `verify_token()`. (P04-T1) |
| `tests/unit/core/test_no_dead_exports.py` (baru) | Pagar otomatis untuk fungsi public di `core/security.py`. |
| `engine/radio/artist_selector.py` | Hapus import `EXPLORE_QUOTA` dan variabel unused `explore_count`. (P04-T2) |
| `engine/volume_service.py` | Selaraskan batas volume backend ke `MAX_VOLUME=100`. (P04-T3) |
| `tests/unit/engine/test_volume_service_max.py` (baru) | Unit test untuk batas volume backend. |
| `server/handlers/ws_download.py` & `websocket.py` | Konfirmasi sebelum menimpa file lokal, cegah overwrite tanpa notifikasi. (P04-T4) |
| `tests/unit/server/handlers/test_ws_download_overwrite.py` (baru) | Unit test konflik download dan konfirmasi overwrite. |
| `engine/playback/crossfade.py` | Restore volume MPV eksplisit ke state.volume saat crossfade diinterupsi. (P04-T5) |
| `tests/unit/engine/playback/test_crossfade_interrupted.py` (baru) | Unit test crossfade interupsi. |
| `*` | Sapuan `ruff` untuk unused variables/imports (`F401, F403, F841`) di seluruh codebase (terutama tes). (P04-T6) |

## RFC Perbaikan Arsitektur — Fase 1-7 (P01-P07): SELESAI, Fase 8 (P08) deferred (2026-07-27)

Task file `docs/rfc/perbaikan_arsitektur/01_circuit_breaker_state_machine.yaml`
(P01-T1 + P01-T2) selesai — PATCH-2026-07-27-241.

| File | Perubahan |
|---|---|
| `engine/playback/circuit_breaker.py` (baru) | `BreakerState` enum (CLOSED/OPEN) + `PlaybackCircuitBreaker` (threshold=3 default) — `record_success()`, `record_failure() -> bool`, `can_advance() -> bool` |
| `engine/playback/controller.py` | `self._retry_count = 0` → `self._breaker = PlaybackCircuitBreaker(threshold=3)`; kedua titik reset (`play_track` sukses, `_on_stop`) pakai `self._breaker.record_success()` |
| `engine/playback/failure_ops.py` | `advance_after_track_failure` pakai `self.controller._breaker.record_failure()` / return value-nya untuk deteksi "baru saja OPEN"; logging `consecutive_failures` baca dari breaker |
| `tests/unit/engine/playback/test_circuit_breaker.py` (baru) | 6 unit test murni untuk `PlaybackCircuitBreaker`, tanpa mock mpv/event bus |
| `tests/unit/engine/playback/test_controller.py` | Assertion `_retry_count == 0` → `controller._breaker.can_advance()` + `_consecutive_failures == 0` |

**Behavior tidak berubah** dari `_retry_count` lama (threshold 3, hardcoded — lihat keputusan `d2` di `00_index_and_decisions.yaml`). Satu penyesuaian teknis dari sketsa proposal §3.D: `record_failure()` hanya mengembalikan `True` pada transisi CLOSED→OPEN (bukan tiap panggilan selama sudah OPEN), sesuai kasus uji wajib task 01 — bukan perubahan keputusan d1-d6, murni penyesuaian mekanis (lihat `deviation_protocol`).

`grep -rn '_retry_count' engine/ tests/` mengembalikan 0 hasil.

**Update audit 2026-07-27 (sesi lanjutan):** Fase 2-7 ternyata SUDAH SELESAI di kode (dikerjakan sesi sebelumnya) tapi P02 dan P07 belum punya entry PATCHLOG sama sekali, dan entry P03 (PATCH-242) tertinggal di status Draft dengan field Tests/Breaking Change/Regression Risk kosong. Diaudit ulang acceptance criteria tiap fase satu per satu terhadap kode aktual (bukan asumsi dari nama file), gap ditutup, PATCHLOG dirapikan:

| Fase | Task file | PATCHLOG | Status |
|---|---|---|---|
| P01 | `01_circuit_breaker_state_machine.yaml` | PATCH-241 | Merged |
| P02 | `02_ws_command_schema_validation.yaml` | PATCH-246 (ditulis retroaktif sesi ini) | Merged |
| P03 | `03_handlers_context_import_cleanup.yaml` | PATCH-242 (diperbaiki sesi ini: Draft→Merged, Tests diisi) | Merged |
| P04 | `04_frontend_reactive_store.yaml` | PATCH-243 | Merged |
| P05 | `05_frontend_globalthis_migration.yaml` | PATCH-244 | Merged |
| P06 | `06_ws_module_split.yaml` | PATCH-245 | Merged |
| P07 | `07_command_bus_dependency_injection.yaml` | PATCH-247 (ditulis retroaktif sesi ini; +test integrasi P07-T6 yang sebelumnya belum ada + rapikan import `server/app.py`) | Merged |
| P08 | `08_backlog_deferred.yaml` | — | Deferred by design (keputusan `d5`, butuh RFC terpisah untuk `index.html`/`admin-logs.*`) |

Gap konkret yang ditemukan & ditutup sesi ini: `tests/integration/test_command_bus_wiring.py` (identity check CommandBus tunggal, wajib per P07-T6) belum ada — dibuat sekarang, 2 test, tidak butuh mpv/yt-dlp jadi tidak skip. Full suite backend: **812 passed, 6 skipped**. Full suite frontend (`npx vitest run`): **691 passed**. `python automation/doctor.py`: PASS 100/100 di semua 5 checker.

Seluruh rencana RFC `perbaikan_arsitektur` (kecuali P08 yang memang sengaja ditunda) kini selesai dan terdokumentasi.

## Observability Baseline: log traceable, traffic/uptime/RAM, /health, [STATUS] periodik (2026-07-22)

ADR-0010 **Accepted**. Lima sesi (task_breakdown_observability.yaml) selesai:

| File | Perubahan |
|---|---|
| `core/mem_stats.py` (baru) | `get_rss_mb()` — RSS cross-platform tanpa dependency baru (proc/self/status di Linux/Termux, ctypes+psapi di Windows, `None` fail-safe) |
| `core/server_clock.py` (baru) | `ServerClock` — uptime server berbasis `time.monotonic()` |
| `core/observability.py` | +5 metric Prometheus: `HTTP_REQUESTS_TOTAL`, `HTTP_BYTES_TOTAL`, `WS_MESSAGES_TOTAL` (dideklarasikan, belum di-wiring — tidak ada task yang menugaskannya), `PROCESS_RSS_MB`, `ACTIVE_USER_SESSION_SECONDS` |
| `core/log_config.py` | Split `file_renderer` (plain)/`console_renderer` (auto-color via `isatty()`, tanpa env var), correlation id (`structlog.contextvars`), `log_session_start()`/`log_session_end()` (banner sesi) |
| `server/middleware/traffic.py` (baru, `server/middleware.py` → package) | Middleware terpusat: req_id per request, `HTTP_REQUESTS_TOTAL`/`HTTP_BYTES_TOTAL` |
| `server/app.py` | AppKey `SERVER_CLOCK`, registrasi `traffic_middleware` |
| `server/connection_manager.py` | `connected_at` per WS, durasi sesi ke `ACTIVE_USER_SESSION_SECONDS` saat disconnect |
| `server/handlers/http.py` | `/health` +`uptime_seconds`, `memory_mb`, `active_connections` (fail-safe per field) |
| `bootstrap/maintenance.py` | `status_log_task()`/`schedule_status_log()` — baris `[STATUS]` ke log tiap 15 menit, refresh `PROCESS_RSS_MB` |
| `main.py` | `schedule_status_log()` dijadwalkan di `main()`; `log_session_start()`/`log_session_end()` di-wiring di `run_server()` (gap dari sesi 2, ditemukan & di-fix sebelum sesi 5 — lihat PATCH-2026-07-22-174) |

`server/handlers/websocket.py`, `engine/playback/controller.py`, `web/static/index.html` tidak disentuh (locked_files_global dihormati). Tidak ada env var atau dependency pip baru.

**Verifikasi manual:** dijalankan `python main.py` (host/port lokal, tanpa TERM/tty — mensimulasikan kondisi non-interaktif ala Termux): banner `SESSION START/END` muncul di `lunawave.log`, tidak ada byte escape ANSI, `/health` mengembalikan `memory_mb`/`uptime_seconds` terisi (bukan `null`), shutdown bersih tanpa task tersisa. Jalur Windows (`ctypes`+`psapi`) tervalidasi lewat unit test dengan mock (tidak ada mesin Windows di lingkungan verifikasi ini).

## Security Hardening: session token hashing, CSWSH, web.AppKey (2026-07-22)

Tiga isu keamanan & teknis diperbaiki sekaligus (PATCH-2026-07-22-166):

| File | Perubahan |
|---|---|
| `core/security.py` | Tambah `hash_token()` (SHA-256) + `verify_token()` (constant-time) |
| `persistence/session_repo.py` | Semua DB ops pakai `hash_token(token)` — raw token tidak pernah menyentuh DB |
| `server/handlers/websocket.py` | Tambah `check_ws_origin()` — tolak handshake cross-origin (CSWSH) sebelum `ws.prepare()` |
| `server/app.py` | Deklarasi 7 `web.AppKey` constants — eliminasi `NotAppKeyWarning` |
| `server/handlers/__init__.py` | Import + pakai AppKey constants dari `server.app` |

**Catatan:** Setelah restart server, sesi lama (plaintext token) otomatis invalid — user perlu login ulang sekali. Ini perilaku yang benar.

## Fix Thompson Sampling dilution (2026-07-22)

Radio mode Thompson Sampling fix:
- Dilusi personalisasi (cuma 25% lagu dari artis bandit) sudah diperbaiki.
- Memperkenalkan `BANDIT_QUOTA` (3) dan `EXPLORE_QUOTA` (1) untuk memisah logikanya.
- Optimasi SQL (full table scan menjadi query ter-filter oleh in-list artis).

| File | Perubahan |
|---|---|
| `engine/radio/radio_config.py` | Tambah konstanta `BANDIT_QUOTA` & `EXPLORE_QUOTA`. |
| `engine/radio/artist_selector.py` | Ubah `gather_batch` untuk request `k` artis dari bandit. |
| `persistence/library_repo.py` | Optimasi CTE menggunakan `WHERE a.nama IN (...)` bila ada filter artis. |
| `tests/unit/engine/radio/test_artist_selector.py` | Update mock `get_random_songs` signature. |

## perf_background_battery_survival (2026-07-21)

Battery/background-survival fixes (server mati & baterai boros saat layar
mati) — PERF-1..4, 6, 7 dari temuan.md. PERF-5 (broadcast progress
per-visibility) **deferred — future work, butuh sign-off terpisah** (lihat
`docs/rfc/performa/task_breakdown_perf.yaml` blok `future_work` / F1.1).

| File | Perubahan |
|---|---|
| `plugins/notifications.py` | `--ongoing` + `--priority high` di notifikasi now-playing (PERF-1) |
| `persistence/db.py` | `PRAGMA synchronous=NORMAL` setelah `journal_mode=WAL` (PERF-7) |
| `bootstrap/power.py` (baru) | `acquire_wake_lock()` fail-safe (PERF-2) |
| `bootstrap/startup_tasks.py` | wiring `acquire_wake_lock()` sebagai background task |
| `web/static/js/audio/playback-sync.js` | titik kontrol tunggal visibilitychange (PERF-3) |
| `web/static/js/audio/visualizer.js` | guard `document.hidden` self-terminating (PERF-3) |
| `web/static/js/render/radio-hero-moon.js` | guard `document.hidden` di stepCycle/stepTween (PERF-3) |
| `web/static/js/ws.js` | exponential backoff reconnect + listener visibility terpisah (PERF-4) |
| `engine/loudness/analyzer.py` | wrapper `nice`/`ionice` untuk ffmpeg (PERF-6) |
| `engine/loudness/service.py` | charging-gate untuk analisis loudness (PERF-6) |
| `adapters/ytdlp/__init__.py` | `os.setpriority` low-priority worker thread (PERF-6) |
| `docs/CONSTRAINTS.md` | dokumentasi setup manual HyperOS/MIUI (PERF-2) |
