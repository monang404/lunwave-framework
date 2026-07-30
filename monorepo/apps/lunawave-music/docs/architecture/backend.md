# Backend Architecture

← [architecture/overview.md](overview.md)

---

## Peta Modul Python

Setiap modul di bawah memiliki **satu tanggung jawab**. Kolom *Testable* menandai apakah file dapat di-unit-test tanpa mock berat.

---

### `core/` — Pure Domain (tidak ada import eksternal)

| File | Tanggung Jawab | Testable |
|---|---|---|
| `state.py` | Single source of truth state aplikasi | ✅ |
| `event_bus.py` | Pub/sub internal, async event dispatch | ✅ |
| `command_bus.py` | Entry point semua aksi user, dispatch ke handler | ✅ |
| `commands.py` | Konstanta `CMD_*` dipisah dari `command_bus` | ✅ |
| `events.py` | Konstanta `EVENT_*` | ✅ |
| `ports.py` | `Protocol` Python untuk semua adapter eksternal | ✅ |
| `security.py` | PBKDF2 password hash, SHA-256 token hash, constant-time verify | ✅ |
| `task_utils.py` | Asyncio task helper (cancel, create safely) | ✅ |
| `observability.py` | Metrics, tracing stubs | ✅ |
| `exceptions.py` | Hierarki exception domain | ✅ |
| `log_config.py` | Setup logging (structlog / stdlib) | ⚠️ side-effect |
| `latency_window.py` | Adaptive prefetch metric window | ✅ |

> `core/` tidak boleh mengimport apapun di luar `core/`.
> Lihat → [architecture/dependency_rules.md](dependency_rules.md)

---

### `adapters/` — Bridge ke Sistem Eksternal

#### `adapters/mpv/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `connection.py` | Connect, reconnect, close socket IPC | ✅ (fake socket) |
| `ipc.py` | Send command, pending futures, response parsing | ✅ |
| `observer.py` | Event loop MPV → publish ke `event_bus` | ✅ |
| `__init__.py` | Facade `MpvController` | ✅ |

> Alasan pilih IPC atas subprocess → [ADR-0001](../adr/0001-mpv-ipc-over-subprocess.md)

#### `adapters/ytdlp/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `searcher.py` | `search(query) → List[TrackInfo]` | ✅ (fake extractor) |
| `resolver.py` | `get_stream_url(video_id) → str` | ✅ |
| `downloader.py` | `download_mp3(url) + progress_hook` | ✅ |
| `__init__.py` | Facade `YtDlpClient` | ✅ |

---

### `engine/` — Domain Logic (orchestration)

#### `engine/` root

| File | Tanggung Jawab | Testable |
|---|---|---|
| `command_router.py` | Map CMD_* ke handler di engine layer | ✅ |
| `download_manager.py` | Antrian download, progress tracking | ✅ |
| `queue_manager.py` | `QueueMode` — mode lanjutan saat track selesai (normal/radio/shuffle) | ✅ |
| `volume_service.py` | Set/get volume via port | ✅ |

#### `engine/playback/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `controller.py` | Slim orchestrator: play, pause, skip, stop ⚠️ FREEZE | ✅ |
| `queue_controller.py` | `_on_queue_*` / `_advance_to_next` — operasi queue & auto-advance | ✅ |
| `queue_ops.py` | Operasi queue level-rendah (add/remove/reorder/select) | ✅ |
| `mode_ops.py` | Mode switching: `set_crossfade`, `set_speed`, `set_loop` | ✅ |
| `settings_controller.py` | `set_mode`, `set_output`, `set_sponsorblock`, `set_loudness_normalization`, `radio_randomize`, `lyrics_offset` | ✅ |
| `track_loader.py` | Resolve URL (cache → yt-dlp) dan load ke player | ✅ |
| `crossfade.py` | Crossfade fade-in/fade-out via MPV volume ramping | ✅ |
| `track_ended_ops.py` | Penanganan saat track selesai diputar | ✅ |
| `failure_ops.py` | Penanganan gagal load / error track | ✅ |

#### `engine/radio/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `engine.py` | Orchestrator radio mode, export `RadioMode` | ✅ |
| `prefetcher.py` | Prefetch track berikutnya di background | ✅ |
| `artist_selector.py` | `gather_batch()` — pilih artis lewat bandit + ambil lagu | ✅ |
| `artist_bandit.py` | Thompson Sampling reward tracking | ✅ |
| `track_interleaver.py` | Interleave lagu antar-artis agar tidak menumpuk per-artis | ✅ |
| `track_filter.py` | Filter duplikat, recently-played, blacklist — **akar bug radio mode** | ✅ ⚠️ |
| `radio_config.py` | Konstanta: `BANDIT_QUOTA`, `EXPLORE_QUOTA`, `ARTISTS_PER_BATCH`, `ARTISTS_QUICK` | ✅ |

#### `engine/loudness/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `analyzer.py` | Eksekusi `ffprobe` untuk mengukur EBU R128 (LUFS) | ✅ |
| `gain_calculator.py` | Hitung gain (dB) dan filter `af` MPV | ✅ |
| `service.py` | Orchestrator pipeline normalisasi kenyaringan | ✅ |

---

### `bootstrap/` — Startup Wiring

| File | Tanggung Jawab | Testable |
|---|---|---|
| `power.py` | `acquire_wake_lock()` — cegah Android matikan proses saat layar mati | ✅ |
| `maintenance.py` | Periodic cleanup: expired sessions, cache, dll. | ✅ |
| `startup_tasks.py` | Daftarkan & jalankan semua background task saat startup | ✅ |
| `services.py` | Inisialisasi services opsional (lyrics, sponsorblock) | ✅ |

---

### `persistence/` — Data Access

| File | Tanggung Jawab | Testable |
|---|---|---|
| `db.py` | Inisialisasi SQLite, connection pool | ✅ (in-memory) |
| `schema.sql` | DDL SQLite — single source of truth skema DB | — |
| `track_repo.py` | CRUD track (metadata, play count, favorite, local path) | ✅ |
| `session_repo.py` | CRUD session auth — token disimpan sebagai SHA-256 hash | ✅ |
| `admin_account_repo.py` | Akun admin tunggal (Fitur B / login_redesign) | ✅ |
| `artist_repo.py` | CRUD artis, reward bandit record | ✅ |
| `genre_repo.py` | CRUD genre & lagu per-genre | ✅ |
| `library_repo.py` | Query random songs untuk radio seed (bandit-aware) | ✅ |
| `discover_repo.py` | Query personalisasi tab Discover (for_you, taste_spectrum, dll.) | ✅ |
| `discover_enrich.py` | `enrich_artists()` — batch enrichment cover+genre untuk discover | ✅ |
| `stream_cache.py` | `CacheResolver` + `ResolverDbCompat` — resolve & cache URI playback | ✅ |
| `__init__.py` | `Repositories` — container 1 koneksi + semua repo domain | ✅ |

> Alasan SQLite atas JSON cache → [ADR-0002](../adr/0002-sqlite-over-json-cache.md)
> Detail skema & query → [backend/persistence.md](../backend/persistence.md)

---

### `cache/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `resolver.py` | Waterfall resolve: local path → stream_cache → yt-dlp | ✅ |
| `mp3/` | Folder penyimpanan file MP3 yang diunduh | — |

Detail → [backend/caching.md](../backend/caching.md)

---

### `server/` — API Layer

#### `server/` root

| File | Tanggung Jawab | Testable |
|---|---|---|
| `app.py` | aiohttp app factory, web.AppKey constants, route registration | ✅ |
| `middleware.py` | Rate limit check | ✅ |
| `serializers.py` | State → dict serialization | ✅ |
| `connection_manager.py` | Registry koneksi WS aktif (connect/disconnect/broadcast) | ✅ |
| `broadcast_service.py` | Subscribe event_bus → broadcast state ke semua WS clients | ✅ |

#### `server/handlers/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `__init__.py` | Typed accessors `get_repos()`, `get_state()`, `get_manager()`, dll. | ✅ |
| `auth.py` | Login WS handler, token verify/issue, rate limit per IP | ✅ |
| `http.py` | HTTP endpoints: `/`, `/admin`, `/health`, `/metrics` | ✅ |
| `setup.py` | Initial Setup handler — buat admin_account pertama kali | ✅ |
| `audio_stream_handler.py` | Streaming audio `/api/stream/{video_id}` | ✅ |
| `event_listeners.py` | Subscribe event bus → trigger broadcast | ✅ |
| `websocket.py` | Origin check (CSWSH), lifecycle WS, routing ke sub-handler | ✅ |
| `ws_playback.py` | Handle cmd play/pause/skip/seek/volume/speed/loop/crossfade/sleep | ✅ |
| `ws_queue.py` | Handle cmd queue add/remove/reorder | ✅ |
| `ws_discovery.py` | Handle cmd search/discover/get_artist_detail | ✅ |
| `ws_download.py` | Handle cmd download/delete_download | ✅ |
| `ws_cache.py` | Handle cmd get_cache_size / clear_cache | ✅ |

---

### `services/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `discover_service.py` | Logic discover: recent, favorites, for_you, taste_spectrum, artist_detail, dll. | ✅ |
| `stream_prefetch.py` | Prefetch URL stream sebelum dibutuhkan (after EVENT_TRACK_CHANGED) | ✅ |

---

### `plugins/`

Plugin mengimplementasikan port dari `core/ports.py`. Tidak ada dependency ke `engine/` atau `server/`.

| File | Tanggung Jawab | Testable |
|---|---|---|
| `lyrics_fetcher.py` | Implements `LyricsProvider` — fetch LRC dari LRCLIB | ✅ (fake provider) |
| `lyrics_parser.py` | Parse format LRC / SRT → `List[LyricLine]` | ✅ |
| `lyrics_sync.py` | Subscribe `EVENT_POSITION_CHANGED` → publish `EVENT_LYRIC_LINE` | ✅ |
| `notifications.py` | Desktop notification via port (Termux MediaStyle) | ✅ |
| `sponsorblock.py` | Skip sponsor segment via SponsorBlock API | ✅ |

---

### `launcher/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `process.py` | Start/stop server process | ✅ |
| `network.py` | Cek port tersedia, resolve host | ✅ |
| `updater.py` | Update checker (stub) | ✅ |

#### `launcher/gui/`

| File | Tanggung Jawab | Testable |
|---|---|---|
| `app.py` | Tkinter app, event loop | Manual QA |
| `ui_builder.py` | Widget builder | Manual QA |
| `status_panel.py` | Panel status server | ✅ (logic) |
| `log_panel.py` | Panel log output | ✅ (logic) |
| `dep_checker.py` | Cek dependensi saat startup | ✅ |
| `__init__.py` | Facade | — |

---

### `automation/`

| File | Tanggung Jawab |
|---|---|
| `doctor.py` | Orchestrator health check — agregasi semua checker ke satu dashboard |
| `run_all.py` | Jalankan semua generator + doctor.py sekaligus |
| `find_owner.py` | Lookup ownership modul/class/fungsi |
| `context_pack.py` | Konteks lengkap file/fitur (ownership + deps + events + test + patchlog) |
| `repo_map.py` | Generate `docs/DEPENDENCY_GRAPH.json` (import graph) |
| `call_graph.py` | Visualisasi call graph antar fungsi |
| `event_graph.py` | Audit event pub/sub — dead & ghost events |
| `hotspot.py` | Identifikasi file dengan churn git tinggi |
| `impact.py` | Analisis dampak potensial perubahan sebuah file |
| `test_locator.py` | Temukan test file untuk modul tertentu |
| `patchlog.py` | CLI `add`/`verify` entry PATCHLOG.md (format field-based) |
| `architecture_lint.py` | Validasi import boundary antar layer |
| `generate_file_index.py` | Generate `docs/FILE_INDEX.md` |
| `generate_report.py` | Update statistik `docs/REPORT.md` |
| `verify_docs.py` | Thin CLI wrapper → `verify_docs/` package |
| `verify_security.py` | Cek .gitignore credential & DB files |
| `verify_structure.py` | Cek file besar & pending items |
| `verify_docs/` | Package: helpers, checks_docs, checks_coverage, checks_files, render |
| `shared/` | Package: check_result, skip_dirs, generated_block |

---

## Dokumen Terkait

- [architecture/dependency_rules.md](dependency_rules.md) — Aturan arah import
- [backend/services.md](../backend/services.md) — Detail engine & services
- [backend/persistence.md](../backend/persistence.md) — Detail SQLite & repositories
- [backend/api.md](../backend/api.md) — HTTP & WebSocket API endpoints
- [backend/caching.md](../backend/caching.md) — Cache resolver
- [testing/unit_testing.md](../testing/unit_testing.md) — Tabel unit test per modul
