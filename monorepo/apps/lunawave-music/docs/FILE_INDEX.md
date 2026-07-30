---
title: LunaWave File Index
last_verified: 2026-07-29
generated: true
note: Isi file ini di-generate otomatis oleh automation/generate_file_index.py — JANGAN edit manual.
---

# FILE_INDEX.md — LunaWave File Inventory

> ⚙️ File ini di-generate otomatis oleh `automation/generate_file_index.py`.
> **Jangan edit manual** — perubahan akan ditimpa saat script dijalankan berikutnya.
> Jalankan `python automation/generate_file_index.py` setelah ada file/class/fungsi yang berubah.
>
> Format per file: File | Fungsi | Class | Function utama | Digunakan oleh | Menggunakan

<!-- BEGIN:GENERATED -->
> **Auto-generated:** 2026-07-29 oleh `automation/generate_file_index.py`  
> **Jangan edit blok ini secara manual** — perubahan akan ditimpa saat script dijalankan ulang.


## Root

**File:** `config.py`  
**Fungsi:** Load and expose all environment-based runtime configuration constants for LunaWave, including paths, ports, and the admin password.  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** `adapters/mpv/connection`, `adapters/ytdlp/downloader`, `adapters/ytdlp/resolver`, `bootstrap/startup_tasks`, `core/log_config`, _15 lainnya_  
**Menggunakan:** —


---

**File:** `main.py`  
**Fungsi:** Bootstrap all LunaWave subsystems and start the async aiohttp web server.  
**Class:** —  
**Function utama:** `run_server()`, `main()`  
**Digunakan oleh:** —  
**Menggunakan:** `config`, `core/log_categories`, `core/log_config`, `bootstrap/maintenance`, `bootstrap/services`, `bootstrap/startup_tasks`


---

**File:** `start.py`  
**Fungsi:** GUI entry point that opens the LunaWave Server Manager desktop window.  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** —  
**Menggunakan:** `launcher/__main__`


---


## core/

**File:** `core/command_bus.py`  
**Fungsi:** Implement a single-writer CommandBus that enforces exactly one handler per command name and records Prometheus metrics for every execution.  
**Class:** `CommandBus`  
**Function utama:** `register()`, `unregister()`  
**Digunakan oleh:** `bootstrap/services`, `engine/command_router`, `engine/download_manager`, `engine/sleep_timer`, `plugins/notifications`, _4 lainnya_  
**Menggunakan:** `core/commands`, `core/log_categories`, `core/log_context`, `core/observability`


---

**File:** `core/commands.py`  
**Fungsi:** Defines all command constants used by the CommandBus. Separated to allow importing without pulling in the entire CommandBus.  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** `core/command_bus`  
**Menggunakan:** —


---

**File:** `core/event_bus.py`  
**Fungsi:** Implement a lightweight async pub/sub EventBus that decouples modules via typed DomainEvents, using weak references for method handlers.  
**Class:** `EventBus`  
**Function utama:** `subscribe()`, `purge_dead_refs()`, `unsubscribe()`  
**Digunakan oleh:** `adapters/mpv/observer`, `bootstrap/services`, `engine/playback/controller`, `engine/volume_service`, `plugins/lyrics_fetcher`, _2 lainnya_  
**Menggunakan:** `core/events`, `core/log_categories`, `core/observability`, `core/task_utils`


---

**File:** `core/events.py`  
**Fungsi:** Define all typed DomainEvent dataclasses for the LunaWave event bus.  
**Class:** `DomainEvent`, `TrackStartedEvent(DomainEvent)`, `TrackEndedEvent(DomainEvent)`, `TrackProgressEvent(DomainEvent)`, `TrackDurationEvent(DomainEvent)`, `QueueUpdatedEvent(DomainEvent)`, `LyricsUpdatedEvent(DomainEvent)`, `DownloadCompleteEvent(DomainEvent)`, `DownloadProgressEvent(DomainEvent)`, `LogMessageEvent(DomainEvent)`, `VolumeChangedEvent(DomainEvent)`, `TrackPauseChangedEvent(DomainEvent)`, `MpvReconnectedEvent(DomainEvent)`  
**Function utama:** —  
**Digunakan oleh:** `adapters/mpv/observer`, `core/event_bus`, `engine/download_manager`, `engine/playback/controller`, `engine/playback/failure_ops`, _14 lainnya_  
**Menggunakan:** `core/state`


---

**File:** `core/exceptions.py`  
**Fungsi:** Define the custom exception hierarchy for LunaWave error conditions.  
**Class:** `YtPlayerError(Exception)`, `MpvConnectionError(YtPlayerError)`, `TrackResolutionError(YtPlayerError)`, `DownloadError(YtPlayerError)`, `VideoUnavailableError(TrackResolutionError)`, `BotCheckError(TrackResolutionError)`, `RateLimitedError(TrackResolutionError)`  
**Function utama:** —  
**Digunakan oleh:** `adapters/mpv/connection`, `adapters/ytdlp/resolver`, `engine/playback/play_ops`, `persistence/stream_cache`, `server/handlers/audio_stream_handler`, _1 lainnya_  
**Menggunakan:** —


---

**File:** `core/latency_window.py`  
**Fungsi:** Rolling window durasi (detik) untuk menghitung percentile ke-n dari N sample terakhir. Dipakai untuk threshold adaptif yang bereaksi ke kondisi jaringan aktual, bukan angka statis.  
**Class:** `LatencyWindow`  
**Function utama:** `record()`, `percentile()`, `sample_count()`  
**Digunakan oleh:** `persistence/stream_cache`  
**Menggunakan:** —


---

**File:** `core/log_categories.py`  
**Fungsi:** Closed set of `category` constants for structured logging, per the §4 table in docs/rfc/logging_standard/LOGGING_STANDARD.md (15 rows; the audit/implementation-plan docs say "14 kategori standar" but the actual table has 15 -- this module follows the table, the normative spec, not the prose count). Category groups log lines by *domain of the event*, never by the Python module/file that emitted them (see §4 anti-pattern #7).  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** `adapters/mpv/connection`, `adapters/mpv/ipc`, `adapters/mpv/observer`, `adapters/ytdlp/resolver`, `bootstrap/maintenance`, _41 lainnya_  
**Menggunakan:** —


---

**File:** `core/log_config.py`  
**Fungsi:** Configure structlog and stdlib logging with an async queue handler, rotating file output, and per-handler rendering (plain file, optional auto-colored console).  
**Class:** —  
**Function utama:** `file_renderer()`, `console_renderer()`, `setup_logging()`, `log_session_start()`, `log_session_end()`  
**Digunakan oleh:** `launcher/preflight`, `main`  
**Menggunakan:** `config`


---

**File:** `core/log_context.py`  
**Fungsi:** Thin wrappers over structlog.contextvars for the three correlation fields defined in docs/rfc/logging_standard/LOGGING_STANDARD.md §5.2: session_id (one WebSocket connection), request_id (one Command Bus execution), correlation_id (one flow that crosses separately scheduled asyncio tasks, e.g. a radio cycle triggering a prefetch, or a download whose progress hook runs in a separate task).  
**Class:** —  
**Function utama:** `bind_session()`, `unbind_session()`, `bind_request()`, `unbind_request()`, `bind_correlation()`, `unbind_correlation()`  
**Digunakan oleh:** `core/command_bus`, `engine/download_manager`, `engine/radio/engine`, `engine/radio/prefetcher`, `server/connection_manager`  
**Menggunakan:** `core/log_categories`


---

**File:** `core/log_reader.py`  
**Fungsi:** Provide utilities to parse and tail lunawave.log files for dashboard and observability purposes.  
**Class:** —  
**Function utama:** `parse_line()`, `tail()`, `stats()`  
**Digunakan oleh:** `server/handlers/log_dashboard`, `server/handlers/ws_log_stream`  
**Menggunakan:** `config`


---

**File:** `core/mem_stats.py`  
**Fungsi:** Baca penggunaan RAM (RSS) proses saat ini secara cross-platform tanpa dependency pip baru (tidak pakai psutil — lihat ADR-0010).  
**Class:** —  
**Function utama:** `get_cpu_percent()`, `get_rss_mb()`  
**Digunakan oleh:** `server/handlers/http`  
**Menggunakan:** —


---

**File:** `core/observability.py`  
**Fungsi:** Expose Prometheus metric singletons and an OpenTelemetry tracer for application-wide instrumentation.  
**Class:** —  
**Function utama:** `get_metrics_content()`, `get_counter_value()`  
**Digunakan oleh:** `core/command_bus`, `core/event_bus`, `persistence/stream_cache`, `server/connection_manager`, `server/handlers/http`, _2 lainnya_  
**Menggunakan:** —


---

**File:** `core/ports.py`  
**Fungsi:** Declare Protocol interfaces (ports) for LunaWave's hexagonal architecture.  
**Class:** `AudioPlayerPort(Protocol)`, `MediaExtractorPort(Protocol)`, `StreamResolverPort(Protocol)`, `TrackRepositoryPort(Protocol)`, `SessionRepositoryPort(Protocol)`, `ArtistRepositoryPort(Protocol)`, `LibraryRepositoryPort(Protocol)`, `DiscoverRepositoryPort(Protocol)`, `DatabasePort(TrackRepositoryPort, SessionRepositoryPort, ArtistRepositoryPort, Protocol)`, `LyricsProvider(Protocol)`, `SponsorBlockProvider(Protocol)`  
**Function utama:** `is_connected()`, `cancel_download()`, `db()`, `latency_window()`, `conn()`, `conn()`  
**Digunakan oleh:** `engine/loudness/service`, `engine/playback/controller`, `engine/playback/mode_ops`, `engine/playback/track_loader`, `engine/radio/artist_selector`, _8 lainnya_  
**Menggunakan:** `core/state`


---

**File:** `core/security.py`  
**Fungsi:** Provide PBKDF2-SHA256 password hashing, constant-time verification, and SHA-256 session token hashing.  
**Class:** —  
**Function utama:** `hash_password()`, `verify_password()`, `needs_rehash()`, `hash_token()`  
**Digunakan oleh:** `persistence/session_repo`, `server/handlers/auth`, `server/handlers/setup`, `server/reset_admin_password`  
**Menggunakan:** —


---

**File:** `core/server_clock.py`  
**Fungsi:** Menyimpan waktu mulai server dan menghitung uptime, tanpa dependency apa pun di luar stdlib.  
**Class:** `ServerClock`  
**Function utama:** `init()`, `start_time()`, `uptime_seconds()`  
**Digunakan oleh:** `server/app`  
**Menggunakan:** —


---

**File:** `core/state.py`  
**Fungsi:** Define shared application state dataclasses, enums, and the single mutable AppState object for LunaWave.  
**Class:** `PlayerStatus(Enum)`, `AudioOutput(StrEnum)`, `PlaybackMode(Enum)`, `TrackInfo`, `AppState`  
**Function utama:** —  
**Digunakan oleh:** `adapters/ytdlp/searcher`, `bootstrap/maintenance`, `bootstrap/services`, `bootstrap/startup_tasks`, `core/events`, _32 lainnya_  
**Menggunakan:** —


---

**File:** `core/task_utils.py`  
**Fungsi:** Wrap asyncio.create_task with centralized exception handling to prevent silent background-task crashes.  
**Class:** —  
**Function utama:** `safe_create_task()`  
**Digunakan oleh:** `adapters/mpv/observer`, `bootstrap/maintenance`, `bootstrap/startup_tasks`, `core/event_bus`, `engine/download_manager`, _9 lainnya_  
**Menggunakan:** `core/log_categories`


---


## adapters/

**File:** `adapters/mpv/__init__.py`  
**Fungsi:** High-level MPV controller combining connection, IPC, and event observation.  
**Class:** `MpvController`  
**Function utama:** `is_connected()`  
**Digunakan oleh:** —  
**Menggunakan:** `adapters/mpv/connection`, `adapters/mpv/ipc`, `adapters/mpv/observer`


---

**File:** `adapters/mpv/connection.py`  
**Fungsi:** Manages the raw socket connection to the MPV media player.  
**Class:** `MpvConnection`  
**Function utama:** `reader()`, `writer()`  
**Digunakan oleh:** `adapters/mpv/__init__`  
**Menggunakan:** `config`, `core/exceptions`, `core/log_categories`


---

**File:** `adapters/mpv/ipc.py`  
**Fungsi:** Handles JSON IPC communication and command execution with MPV.  
**Class:** `MpvIPC`  
**Function utama:** `pop_pending()`, `cancel_all_pending()`  
**Digunakan oleh:** `adapters/mpv/__init__`  
**Menggunakan:** `core/log_categories`


---

**File:** `adapters/mpv/observer.py`  
**Fungsi:** Observes and dispatches asynchronous events emitted by the MPV player.  
**Class:** `MpvObserver`  
**Function utama:** —  
**Digunakan oleh:** `adapters/mpv/__init__`  
**Menggunakan:** `core/event_bus`, `core/events`, `core/log_categories`, `core/task_utils`


---

**File:** `adapters/ytdlp/__init__.py`  
**Fungsi:** Unified client for interacting with yt-dlp for search, extraction, and downloading.  
**Class:** `YtDlpClient`  
**Function utama:** `cancel_download()`, `close()`  
**Digunakan oleh:** —  
**Menggunakan:** `adapters/ytdlp/downloader`, `adapters/ytdlp/resolver`, `adapters/ytdlp/searcher`


---

**File:** `adapters/ytdlp/downloader.py`  
**Fungsi:** Handles downloading audio streams using yt-dlp.  
**Class:** `YtDlpDownloader`  
**Function utama:** `cancel_download()`  
**Digunakan oleh:** `adapters/ytdlp/__init__`  
**Menggunakan:** `adapters/ytdlp/ydl_options`, `config`


---

**File:** `adapters/ytdlp/resolver.py`  
**Fungsi:** Resolves direct stream URLs for tracks using yt-dlp.  
**Class:** `YtDlpResolver`  
**Function utama:** `classify_ytdlp_error()`  
**Digunakan oleh:** `adapters/ytdlp/__init__`  
**Menggunakan:** `adapters/ytdlp/ydl_options`, `config`, `core/exceptions`, `core/log_categories`


---

**File:** `adapters/ytdlp/searcher.py`  
**Fungsi:** Performs metadata extraction and search operations via yt-dlp.  
**Class:** `YtDlpSearcher`  
**Function utama:** `_extract_sync()`, `_to_track()`  
**Digunakan oleh:** `adapters/ytdlp/__init__`  
**Menggunakan:** `adapters/ytdlp/ydl_options`, `core/state`


---

**File:** `adapters/ytdlp/ydl_options.py`  
**Fungsi:** Shared utilities and constants for yt-dlp integration.  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** `adapters/ytdlp/downloader`, `adapters/ytdlp/resolver`, `adapters/ytdlp/searcher`  
**Menggunakan:** —


---


## engine/

**File:** `engine/command_router.py`  
**Fungsi:** Register all CMD_* CommandBus handlers, routing each command to the appropriate method on PlaybackController or VolumeService.  
**Class:** `CommandRouter`  
**Function utama:** `_route_sleep()`, `_route()`, `_route_volume()`  
**Digunakan oleh:** `bootstrap/services`  
**Menggunakan:** `core/command_bus`


---

**File:** `engine/download_manager.py`  
**Fungsi:** Handle the CMD_DOWNLOAD command by downloading the current or specified track via yt-dlp and moving it to the downloads/ folder.  
**Class:** `DownloadManager`  
**Function utama:** `_update_progress()`  
**Digunakan oleh:** `bootstrap/services`  
**Menggunakan:** `core/command_bus`, `core/events`, `core/log_categories`, `core/log_context`, `core/state`, `core/task_utils`


---

**File:** `engine/loudness/analyzer.py`  
**Fungsi:** Ukur integrated loudness (LUFS) sebuah track via satu-pass ffmpeg `loudnorm` filter mode measure-only (tidak re-encode, tidak menyimpan file baru).  
**Class:** `LoudnessMeasurement(NamedTuple)`, `LoudnessAnalyzer`  
**Function utama:** `measure_sync()`  
**Digunakan oleh:** `engine/loudness/service`  
**Menggunakan:** `config`, `core/log_categories`


---

**File:** `engine/loudness/gain_calculator.py`  
**Fungsi:** Hitung gain (dB) yang perlu diterapkan ke sebuah track supaya loudness-nya mendekati target, berdasarkan hasil pengukuran integrated loudness (LUFS) dan true peak (dBTP).  
**Class:** —  
**Function utama:** `compute_gain_db()`, `build_af_filter()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `engine/loudness/service.py`  
**Fungsi:** Orkestrasi analisis loudness: cek apakah track sudah pernah diukur, kalau belum -> ukur via LoudnessAnalyzer lalu simpan ke DB.  
**Class:** `LoudnessService`  
**Function utama:** `_is_charging_or_unknown()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/log_categories`, `core/ports`, `engine/loudness/analyzer`


---

**File:** `engine/playback/circuit_breaker.py`  
**Fungsi:** Circuit breaker eksplisit lintas-track untuk PlaybackController -- menggantikan counter integer implisit yang sebelumnya hidup langsung di controller dengan state machine bernama, tanpa mengubah behavior lama sedikit pun.  
**Class:** `BreakerState(Enum)`, `PlaybackCircuitBreaker`  
**Function utama:** `record_success()`, `record_failure()`, `can_advance()`  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** —


---

**File:** `engine/playback/controller.py`  
**Fungsi:** Orchestrate all playback logic: track loading, queue/radio advancement, pause/seek, and mode switching via CommandBus commands.  
**Class:** `PlaybackController`  
**Function utama:** `dispose()`  
**Digunakan oleh:** `engine/playback/__init__`, `server/app`  
**Menggunakan:** `core/event_bus`, `core/events`, `core/log_categories`, `core/ports`, `core/state`, `core/task_utils`, _11 lainnya_


---

**File:** `engine/playback/crossfade.py`  
**Fungsi:** Crossfade helpers untuk transisi halus antar track via MPV volume ramping.  
**Class:** —  
**Function utama:** `apply_crossfade_in()`, `apply_crossfade_out()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/state`


---

**File:** `engine/playback/failure_ops.py`  
**Fungsi:** Menangani semua cabang except dari play_track() saat gagal memutar sebuah track (video tidak tersedia permanen, bot-check/rate-limit YouTube, atau error generik lainnya). Diekstrak dari controller.py (PATCH-2026-07-20-136) agar file controller tetap ramping (di bawah LARGE_FILE_THRESHOLD 500 LOC), sama seperti track_ended_ops.py.  
**Class:** `FailureOps`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/log_categories`, `core/state`, `core/task_utils`


---

**File:** `engine/playback/mode_ops.py`  
**Fungsi:** Handles playback mode switches, such as toggling radio mode or SponsorBlock.  
**Class:** `ModeOps`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/log_categories`, `core/ports`, `core/state`, `engine/radio`


---

**File:** `engine/playback/play_ops.py`  
**Fungsi:** Operations class handling the core logic for playing a track. Extracted from PlaybackController to maintain a thin orchestrator.  
**Class:** `PlayOps`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/exceptions`, `core/state`, `core/task_utils`


---

**File:** `engine/playback/queue_controller.py`  
**Fungsi:** Menangani command CMD_QUEUE_* (select/remove/add/replace/reorder) dan advance-to-next (lanjut ke lagu berikutnya, baik mode QUEUE maupun RADIO). Diekstrak dari PlaybackController (roadmap IMPLEMENTATION_PLAN.md §2.3, task T2.3.1) agar controller.py tetap ramping.  
**Class:** `QueueController`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/state`, `core/task_utils`


---

**File:** `engine/playback/queue_ops.py`  
**Fungsi:** Manages queue operations including adding, removing, and reordering tracks.  
**Class:** `QueueOps`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/state`


---

**File:** `engine/playback/settings_controller.py`  
**Fungsi:** Menangani command CMD_SET_OUTPUT, CMD_SET_SPONSORBLOCK, CMD_SET_LOUDNESS_NORMALIZATION, CMD_SET_MODE, CMD_RADIO_RANDOMIZE, dan CMD_LYRICS_OFFSET. Diekstrak dari PlaybackController (roadmap IMPLEMENTATION_PLAN.md §2.3, task T2.3.2) agar controller.py tetap ramping.  
**Class:** `SettingsController`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/state`, `core/task_utils`


---

**File:** `engine/playback/track_ended_ops.py`  
**Fungsi:** Menangani reaksi terhadap TrackEndedEvent (eof/stop/error) dan polling durasi track yang belum diketahui. Diekstrak dari controller.py agar file controller tetap ramping (di bawah LARGE_FILE_THRESHOLD).  
**Class:** `TrackEndedOps`  
**Function utama:** `poll_duration()`  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/log_categories`, `core/state`, `core/task_utils`


---

**File:** `engine/playback/track_loader.py`  
**Fungsi:** Resolve a track URI and trigger background side-effects (sponsorblock, lyrics fetch, play-count increment) before playback begins.  
**Class:** `LoadedTrack`, `TrackLoader`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/ports`, `core/state`, `core/task_utils`


---

**File:** `engine/queue_manager.py`  
**Fungsi:** Advance playback to the next track in the user queue when called by PlaybackController at track end.  
**Class:** `QueueMode`  
**Function utama:** —  
**Digunakan oleh:** `engine/playback/controller`  
**Menggunakan:** `core/events`, `core/state`


---

**File:** `engine/radio/artist_bandit.py`  
**Fungsi:** Thompson Sampling (Beta-Bernoulli) untuk memilih artis radio berdasarkan histori selesai/skip, dengan eksplorasi otomatis untuk artis yang datanya masih sedikit.  
**Class:** `ArtistStat`  
**Function utama:** `sample_artists()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `engine/radio/artist_selector.py`  
**Fungsi:** Selects and rotates artists intelligently to maintain variety in radio mode.  
**Class:** `ArtistSelector`  
**Function utama:** `reset_rotation()`, `build_exclusion_set()`  
**Digunakan oleh:** `engine/radio/engine`  
**Menggunakan:** `core/log_categories`, `core/ports`, `core/state`, `engine/radio/radio_config`, `engine/radio/track_filter`, `engine/radio/track_interleaver`


---

**File:** `engine/radio/engine.py`  
**Fungsi:** Manages the state and playback progression for the radio mode feature.  
**Class:** `RadioMode`  
**Function utama:** `check_prefetch()`  
**Digunakan oleh:** `engine/radio/__init__`  
**Menggunakan:** `core/events`, `core/log_categories`, `core/log_context`, `core/ports`, `core/state`, `engine/radio/artist_selector`, _2 lainnya_


---

**File:** `engine/radio/prefetcher.py`  
**Fungsi:** Pre-fetches tracks asynchronously to ensure seamless transitions in radio mode.  
**Class:** `RadioPrefetcher`  
**Function utama:** `cancel_tasks()`, `trigger_build_standby()`, `check_prefetch()`  
**Digunakan oleh:** `engine/radio/engine`  
**Menggunakan:** `config`, `core/log_categories`, `core/log_context`, `core/state`, `engine/radio/radio_config`


---

**File:** `engine/radio/radio_config.py`  
**Fungsi:** Common utilities and shared logic for the radio engine components.  
**Class:** —  
**Function utama:** `track_task()`  
**Digunakan oleh:** `engine/radio/artist_selector`, `engine/radio/engine`, `engine/radio/prefetcher`, `engine/radio/track_filter`  
**Menggunakan:** `core/task_utils`


---

**File:** `engine/radio/track_filter.py`  
**Fungsi:** Filter candidate tracks for the radio queue to prevent duplicates, skip recently played tracks, and limit artist dominance.  
**Class:** `TrackFilter`  
**Function utama:** `filter_tracks()`  
**Digunakan oleh:** `engine/radio/artist_selector`  
**Menggunakan:** `core/log_categories`, `core/state`, `engine/radio/radio_config`, `engine/radio/track_interleaver`


---

**File:** `engine/radio/track_interleaver.py`  
**Fungsi:** Interleaves tracks from different artists to create a balanced radio queue.  
**Class:** —  
**Function utama:** `normalize_title()`, `interleave_by_artist()`  
**Digunakan oleh:** `engine/radio/artist_selector`, `engine/radio/track_filter`  
**Menggunakan:** —


---

**File:** `engine/sleep_timer.py`  
**Fungsi:** Handles setting, tracking, and executing a sleep timer to stop playback after a specified duration.  
**Class:** `SleepTimer`  
**Function utama:** —  
**Digunakan oleh:** —  
**Menggunakan:** `core/command_bus`, `core/events`


---

**File:** `engine/volume_service.py`  
**Fungsi:** Handle volume-related commands and apply the correct volume to mpv based on the active audio output mode.  
**Class:** `VolumeService`  
**Function utama:** —  
**Digunakan oleh:** —  
**Menggunakan:** `core/event_bus`, `core/events`, `core/ports`, `core/state`


---


## persistence/

**File:** `persistence/__init__.py`  
**Fungsi:** Package entry point for the persistence layer: builds one DB connection and the six domain repositories that use it. Domain logic itself lives in each `*_repo.py` module (persistence.track_repo, .session_repo, .artist_repo, .genre_repo, .library_repo, .discover_repo) — this module only wires them up.  
**Class:** `Repositories`  
**Function utama:** `conn()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/log_categories`, `persistence/admin_account_repo`, `persistence/artist_repo`, `persistence/chat_repo`, `persistence/db`, `persistence/discover_repo`, _4 lainnya_


---

**File:** `persistence/admin_account_repo.py`  
**Fungsi:** Manages the single admin_account row: the sole source of truth for login credentials under the Fitur B (login_redesign) design. Populated via the Initial Setup flow (server.handlers.setup), never auto-generated.  
**Class:** `AdminAccountRepository`  
**Function utama:** —  
**Digunakan oleh:** `persistence/__init__`, `server/reset_admin_password`  
**Menggunakan:** —


---

**File:** `persistence/artist_repo.py`  
**Fungsi:** Repository for tracking artist statistics and fetching artist-specific tracks.  
**Class:** `ArtistRepository`  
**Function utama:** `conn()`  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `core/log_categories`, `core/state`


---

**File:** `persistence/chat_repo.py`  
**Fungsi:** Repository untuk fitur chat (client <-> admin). Menyimpan dan mengambil pesan chat, disegmentasi per `client_uid` -- BUKAN per `client_ip`.  
**Class:** `ChatRepository`  
**Function utama:** —  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** —


---

**File:** `persistence/db.py`  
**Fungsi:** Manages the SQLite database connection lifecycle and initialization.  
**Class:** `DatabaseConnection`  
**Function utama:** `conn()`  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `config`, `core/log_categories`


---

**File:** `persistence/discover_enrich.py`  
**Fungsi:** Shared batch-enrichment helper for Discover personalization queries. Given a list of artist rows, attach a cover thumbnail and genre tag list to each one using two queries total for the whole batch (never per-artist), so `discover_repo.py` doesn't run into N+1 query fan-out when enriching a page of results.  
**Class:** —  
**Function utama:** `enrich_artists()`  
**Digunakan oleh:** `persistence/discover_repo`  
**Menggunakan:** —


---

**File:** `persistence/discover_repo.py`  
**Fungsi:** Repository for Discover-tab personalization queries: bandit-ranked "Untuk Kamu" artists, "Belum Pernah Kamu Dengar" (unheard) artists, genre taste spectrum, genre affinity, and artist detail lookup.  
**Class:** `DiscoverRepository`  
**Function utama:** `conn()`  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `core/log_categories`, `persistence/discover_enrich`


---

**File:** `persistence/genre_repo.py`  
**Fungsi:** Repository for fetching genre information and tracking genre popularity.  
**Class:** `GenreRepository`  
**Function utama:** —  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `core/log_categories`, `core/state`


---

**File:** `persistence/library_repo.py`  
**Fungsi:** Repository for global library operations such as fetching random songs.  
**Class:** `LibraryRepository`  
**Function utama:** `conn()`  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `core/state`


---

**File:** `persistence/session_repo.py`  
**Fungsi:** Manages authentication session tokens, verifying and cleaning up expired sessions.  
**Class:** `SessionRepository`  
**Function utama:** —  
**Digunakan oleh:** `persistence/__init__`, `server/reset_admin_password`  
**Menggunakan:** `core/security`


---

**File:** `persistence/stream_cache.py`  
**Fungsi:** Resolve the playback URI for a track using a priority-based cache strategy: local file > cached stream URL > fresh yt-dlp extraction.  
**Class:** `ResolverDbCompat`, `CacheResolver`  
**Function utama:** —  
**Digunakan oleh:** —  
**Menggunakan:** `config`, `core/exceptions`, `core/latency_window`, `core/observability`, `core/ports`, `core/state`


---

**File:** `persistence/track_repo.py`  
**Fungsi:** Repository for track metadata, play counts, favorites, and local file paths.  
**Class:** `TrackRepository`  
**Function utama:** —  
**Digunakan oleh:** `persistence/__init__`  
**Menggunakan:** `core/log_categories`, `core/state`


---


## server/

**File:** `server/app.py`  
**Fungsi:** Create and configure the aiohttp web application with all routes, services, and EventBus listeners wired together.  
**Class:** —  
**Function utama:** `create_app()`, `run_server()`  
**Digunakan oleh:** `server/handlers/context`  
**Menggunakan:** `core/command_bus`, `core/log_categories`, `core/ports`, `core/server_clock`, `engine/playback/controller`, `persistence`


---

**File:** `server/broadcast_service.py`  
**Fungsi:** Provide typed broadcast helpers that wrap ConnectionManager to push specific message types to all connected WebSocket clients.  
**Class:** `BroadcastService`  
**Function utama:** —  
**Digunakan oleh:** `server/handlers/event_listeners`  
**Menggunakan:** `core/state`, `server/connection_manager`, `server/serializers`


---

**File:** `server/connection_manager.py`  
**Fungsi:** Manages active WebSocket connections and broadcasts events to connected clients.  
**Class:** `ConnectionManager`  
**Function utama:** `disconnect()`, `bind_client_uid()`  
**Digunakan oleh:** `server/broadcast_service`  
**Menggunakan:** `core/log_categories`, `core/log_context`, `core/observability`, `server/handlers/ws_log_stream`


---

**File:** `server/handlers/audio_stream_handler.py`  
**Fungsi:** Proxy cached/streamed MP3 audio for a track, including range-request support for seeking. Split out of server/handlers/http.py (T3.4) so the streaming/range-request logic isn't bundled with the SPA/health/ metrics endpoints.  
**Class:** —  
**Function utama:** `serve_stream()`  
**Digunakan oleh:** —  
**Menggunakan:** `config`, `core/exceptions`, `core/log_categories`, `server/handlers`


---

**File:** `server/handlers/auth.py`  
**Fungsi:** Handle WebSocket authentication, session token verification, and per-IP login rate limiting.  
**Class:** —  
**Function utama:** `handle_auth()`, `require_auth()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `core/log_categories`, `core/security`


---

**File:** `server/handlers/context.py`  
**Fungsi:** Shared, typed accessors for values stashed on `request.app[...]` by server.app.create_app(). Handlers should use these instead of raw `request.app[KEY]` lookups so the type of each value is explicit (T3.7 — dulu rencana ini ditulis untuk `request.app["db"]`, tapi setelah T2.2 memecah `Database` God Facade, tidak ada lagi key tunggal "db" — sudah jadi beberapa key spesifik: "repos", "tracks", "conn", dst. Accessor di bawah menutupi semua key itu).  
**Class:** —  
**Function utama:** `get_repos()`, `get_tracks_repo()`, `get_conn()`, `get_state()`, `get_manager()`, `get_ytdlp()`  
**Digunakan oleh:** `server/handlers/__init__`, `server/handlers/websocket`  
**Menggunakan:** `core/ports`, `core/state`, `server/app`


---

**File:** `server/handlers/event_listeners.py`  
**Fungsi:** Subscribe to domain events from the EventBus and forward them as WebSocket broadcasts via BroadcastService.  
**Class:** —  
**Function utama:** `setup_event_listeners()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/events`, `core/log_categories`, `core/task_utils`, `server/broadcast_service`, `services/stream_prefetch`


---

**File:** `server/handlers/http.py`  
**Fungsi:** Serve the SPA index, health check, and Prometheus metrics endpoints over HTTP.  
**Class:** —  
**Function utama:** `serve_index()`, `serve_client()`, `health_check()`, `require_local_or_token()`, `serve_metrics()`  
**Digunakan oleh:** `server/handlers/log_dashboard`  
**Menggunakan:** `core/mem_stats`, `core/observability`, `server/handlers`


---

**File:** `server/handlers/log_dashboard.py`  
**Fungsi:** Provide HTTP endpoints for the Logging Dashboard (tail, stats, and HTML).  
**Class:** —  
**Function utama:** `serve_log_dashboard()`, `get_logs_tail()`, `get_logs_stats()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/log_categories`, `core/log_reader`, `core/observability`, `server/handlers/http`


---

**File:** `server/handlers/setup.py`  
**Fungsi:** Handle Initial Setup: creation of the single admin_account row that becomes the sole source of login credentials (Fitur B: login_redesign, lihat decisions K3/K4/K5 di task_breakdown_agent.yaml). Runs before any admin account exists, so it lives outside the normal require_auth gate -- the same way "auth" itself is special-cased in websocket.py.  
**Class:** —  
**Function utama:** `handle_setup_admin()`, `setup_required()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `core/log_categories`, `core/security`, `server/handlers`


---

**File:** `server/handlers/websocket.py`  
**Fungsi:** Handle WebSocket connections, authenticate clients, and dispatch incoming commands to the CommandBus after rate-limit enforcement.  
**Class:** —  
**Function utama:** `check_ws_origin()`, `ws_handler()`, `handle_ws_message()`  
**Digunakan oleh:** —  
**Menggunakan:** `config`, `core/log_categories`, `server/handlers`, `server/handlers/auth`, `server/handlers/context`, `server/handlers/setup`, _10 lainnya_


---

**File:** `server/handlers/ws_cache.py`  
**Fungsi:** WebSocket handler for managing the downloaded MP3 file cache (`DOWNLOAD_DIR`, a.k.a. `cache/mp3/`): reporting its size and clearing it.  
**Class:** —  
**Function utama:** `handle_cache_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `config`, `core/log_categories`


---

**File:** `server/handlers/ws_chat.py`  
**Fungsi:** Handler perintah WebSocket untuk fitur chat (client <-> admin).  
**Class:** —  
**Function utama:** `handle_chat_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `persistence`


---

**File:** `server/handlers/ws_discovery.py`  
**Fungsi:** WebSocket handler for processing discovery and search commands.  
**Class:** —  
**Function utama:** `handle_discovery_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `server/serializers`, `services/discover_service`


---

**File:** `server/handlers/ws_download.py`  
**Fungsi:** WebSocket handler for managing track download requests and status.  
**Class:** —  
**Function utama:** `handle_download_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `core/command_bus`, `core/log_categories`, `server/serializers`, `services/discover_service`


---

**File:** `server/handlers/ws_log_stream.py`  
**Fungsi:** Provide WebSocket handler for live log tailing.  
**Class:** —  
**Function utama:** `handle_log_stream_command()`, `cleanup_log_viewer()`  
**Digunakan oleh:** `server/connection_manager`, `server/handlers/websocket`  
**Menggunakan:** `config`, `core/log_reader`


---

**File:** `server/handlers/ws_playback.py`  
**Fungsi:** WebSocket handler for processing playback control commands.  
**Class:** —  
**Function utama:** `handle_playback_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `core/command_bus`, `core/state`, `server/handlers/ws_schemas`, `server/serializers`


---

**File:** `server/handlers/ws_queue.py`  
**Fungsi:** WebSocket handler for manipulating the current playback queue.  
**Class:** —  
**Function utama:** `handle_queue_command()`  
**Digunakan oleh:** `server/handlers/websocket`  
**Menggunakan:** `core/command_bus`, `core/state`, `server/serializers`


---

**File:** `server/handlers/ws_schemas.py`  
**Fungsi:** Provide strict validation and schema definitions for WebSocket command payloads.  
**Class:** `WsValidationError(Exception)`, `VolumeSetPayload`, `SetSpeedPayload`, `LyricsOffsetPayload`, `SetSleepTimerPayload`  
**Function utama:** `parse()`, `parse()`, `parse()`, `parse()`  
**Digunakan oleh:** `server/handlers/websocket`, `server/handlers/ws_playback`  
**Menggunakan:** —


---

**File:** `server/middleware/__init__.py`  
**Fungsi:** Package for server-side middleware: per-IP WS command rate limiting (this file, unchanged) and the aiohttp HTTP traffic middleware added in ADR-0010 (server.middleware.traffic).  
**Class:** —  
**Function utama:** `check_rate_limit()`, `check_chat_rate_limit()`  
**Digunakan oleh:** —  
**Menggunakan:** `server/middleware/traffic`


---

**File:** `server/middleware/compression.py`  
**Fungsi:** PATCH-UI-PERF-01: aiohttp's `add_static()` serves files as-is with no gzip/deflate and no explicit Cache-Control -- every CSS/JS request pays full uncompressed transfer cost and browsers fall back to heuristic caching. `make_static_handler()` replaces `add_static()` with a handler that:  
**Class:** —  
**Function utama:** `make_static_handler()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `server/middleware/traffic.py`  
**Fungsi:** Centralized aiohttp middleware for HTTP traffic instrumentation (ADR-0010 decision OD-3): assign a short correlation id (req_id) per request, count traffic metrics, and log one summary line per request.  
**Class:** —  
**Function utama:** `traffic_middleware()`  
**Digunakan oleh:** `server/middleware/__init__`  
**Menggunakan:** `core/log_categories`, `core/observability`


---

**File:** `server/reset_admin_password.py`  
**Fungsi:** CLI untuk reset password admin. Dijalankan via: python -m server.reset_admin_password  
**Class:** —  
**Function utama:** `do_reset()`, `main()`  
**Digunakan oleh:** —  
**Menggunakan:** `config`, `core/security`, `persistence/admin_account_repo`, `persistence/session_repo`


---

**File:** `server/serializers.py`  
**Fungsi:** Convert between AppState/TrackInfo domain objects and JSON-serializable dicts for WebSocket message payloads.  
**Class:** —  
**Function utama:** `track_to_dict()`, `state_to_dict()`, `dict_to_track()`  
**Digunakan oleh:** `server/broadcast_service`, `server/handlers/websocket`, `server/handlers/ws_discovery`, `server/handlers/ws_download`, `server/handlers/ws_playback`, _1 lainnya_  
**Menggunakan:** `core/state`


---


## services/

**File:** `services/discover_ranking.py`  
**Fungsi:** Pure scoring/aggregation functions for Discover-tab personalization, split out of persistence.discover_repo.py (T3.3) so the ranking math is unit-testable with plain numbers instead of a real DB, and so it lives in the services layer rather than persistence (which is not allowed to depend on services — see .importlinter).  
**Class:** —  
**Function utama:** `compute_match_pct()`, `build_taste_spectrum()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `services/discover_service.py`  
**Fungsi:** Query the SQLite database to provide discover-page data: recently played tracks, favorites, cached tracks, and featured artists/genres.  
**Class:** `DiscoverService`  
**Function utama:** —  
**Digunakan oleh:** `server/handlers/ws_discovery`, `server/handlers/ws_download`  
**Menggunakan:** `core/ports`, `core/state`, `services`


---

**File:** `services/stream_prefetch.py`  
**Fungsi:** Pre-fetch and cache the stream URL for the next track in the background to reduce playback latency at track transitions.  
**Class:** `StreamPrefetchService`  
**Function utama:** —  
**Digunakan oleh:** `server/handlers/event_listeners`  
**Menggunakan:** `config`, `core/exceptions`, `core/log_categories`, `core/ports`


---


## plugins/

**File:** `plugins/lyrics_fetcher.py`  
**Fungsi:** Fetch synchronized lyrics from lrclib.net and syncedlyrics, then update the active lyric index on each playback progress event.  
**Class:** `LyricsFetcher`  
**Function utama:** `cleanup()`  
**Digunakan oleh:** `bootstrap/services`  
**Menggunakan:** `config`, `core/event_bus`, `core/events`, `core/log_categories`, `core/state`


---

**File:** `plugins/lyrics_parser.py`  
**Fungsi:** Parser for extracting timed lyrics from LRC-formatted text.  
**Class:** `LyricsParser`  
**Function utama:** `parse_lrc()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `plugins/lyrics_sync.py`  
**Fungsi:** Synchronizes lyrics display with current track playback progress.  
**Class:** `LyricsSync`  
**Function utama:** `cleanup()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/events`


---

**File:** `plugins/notifications.py`  
**Fungsi:** Mirror current playback state to an Android MediaStyle notification via termux-notification and relay button presses back via CommandBus.  
**Class:** `TermuxNowPlaying`  
**Function utama:** `_blocking_read_loop()`  
**Digunakan oleh:** `bootstrap/services`  
**Menggunakan:** `config`, `core/command_bus`, `core/event_bus`, `core/events`, `core/log_categories`, `core/state`


---

**File:** `plugins/sponsorblock.py`  
**Fungsi:** Fetch SponsorBlock skip segments for the current video and auto-seek past them during playback.  
**Class:** `SponsorBlockHandler`  
**Function utama:** `cleanup()`  
**Digunakan oleh:** `bootstrap/services`  
**Menggunakan:** `config`, `core/event_bus`, `core/events`, `core/log_categories`, `core/ports`, `core/state`


---


## launcher/

**File:** `launcher/__main__.py`  
**Fungsi:** Entry point for the LunaWave launcher when executed as a package.  
**Class:** —  
**Function utama:** `main()`  
**Digunakan oleh:** `start`  
**Menggunakan:** —


---

**File:** `launcher/dep_checker.py`  
**Fungsi:** Utility to verify required system dependencies before launching the application.  
**Class:** `DependencyChecker`  
**Function utama:** `check_dependencies()`, `check_port()`, `mpv_version()`  
**Digunakan oleh:** `launcher/preflight`  
**Menggunakan:** —


---

**File:** `launcher/gui_qt/main_window.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.main_window.  
**Class:** `ServerManagerQt(QMainWindow)`  
**Function utama:** `server_port()`, `resizeEvent()`, `closeEvent()`  
**Digunakan oleh:** —  
**Menggunakan:** `launcher`, `launcher/gui_qt`, `launcher/gui_qt/widgets/conflict_banner`, `launcher/gui_qt/widgets/console`, `launcher/gui_qt/widgets/info_bars`, `launcher/gui_qt/widgets/quicklinks`, _5 lainnya_


---

**File:** `launcher/gui_qt/theme.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.theme.  
**Class:** —  
**Function utama:** —  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `launcher/gui_qt/widgets/conflict_banner.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.conflict_banner.  
**Class:** `ConflictBanner(QWidget)`  
**Function utama:** `set_conflict()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/console.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.console.  
**Class:** `Console(QWidget)`  
**Function utama:** `append_log()`, `clear_log()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/info_bars.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.info_bars.  
**Class:** `AdminBar(QWidget)`, `EnvironmentBar(QWidget)`  
**Function utama:** `set_status()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/quicklinks.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.quicklinks.  
**Class:** `QuickLinks(QWidget)`  
**Function utama:** `set_base_port()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/ready_toast.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.ready_toast.  
**Class:** `ReadyToast(QWidget)`  
**Function utama:** `show_toast()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/status_hero.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.status_hero.  
**Class:** `StateRing(QWidget)`, `StatusHero(QWidget)`  
**Function utama:** `getBorderScale()`, `setBorderScale()`, `getBorderOpacity()`, `setBorderOpacity()`, `getRotationAngle()`, `setRotationAngle()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/titlebar.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.titlebar.  
**Class:** `TitleBar(QWidget)`  
**Function utama:** `mousePressEvent()`, `mouseMoveEvent()`, `mouseReleaseEvent()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/gui_qt/widgets/toolbar.py`  
**Fungsi:** PySide6 GUI component for launcher.gui_qt.widgets.toolbar.  
**Class:** `Toolbar(QWidget)`  
**Function utama:** `set_enabled_map()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher/gui_qt`


---

**File:** `launcher/network.py`  
**Fungsi:** Provide cross-platform utilities to detect TCP port availability and identify the PID currently occupying a port.  
**Class:** —  
**Function utama:** `check_port_in_use()`, `get_pid_occupying_port()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `launcher/preflight.py`  
**Fungsi:** Unified preflight check for LunaWave to be called by both start.sh and start.bat.  
**Class:** —  
**Function utama:** `print_info()`, `print_ok()`, `print_warn()`, `print_err()`, `log_result()`, `run()`  
**Digunakan oleh:** —  
**Menggunakan:** `core/log_categories`, `core/log_config`, `launcher/dep_checker`


---

**File:** `launcher/process.py`  
**Fungsi:** Manage OS-level lifecycle for the LunaWave server and mpv processes from the desktop launcher.  
**Class:** `ServerProcess`  
**Function utama:** `kill_process_tree()`, `kill_mpv()`, `start()`, `is_running()`, `stop()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---

**File:** `launcher/server_lifecycle.py`  
**Fungsi:** Own the LunaWave server process lifecycle (start/stop/restart, port conflict resolution, readiness polling, dependency checks) independent of any GUI toolkit.  
**Class:** `ServerLifecycle`  
**Function utama:** `is_running()`, `run_dependency_check()`, `start()`, `wait_for_ready()`, `stop()`, `restart()`  
**Digunakan oleh:** `launcher/gui_qt/main_window`  
**Menggunakan:** `launcher`


---

**File:** `launcher/updater.py`  
**Fungsi:** Stub module reserved for future OTA update checking and release info retrieval in the LunaWave launcher.  
**Class:** —  
**Function utama:** `check_for_updates()`, `get_release_info()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---


## data/

**File:** `data/export_to_sqlite.py`  
**Fungsi:** Export artist, genre, and song data from a JSON file into a SQLite DB.  
**Class:** —  
**Function utama:** `create_tables()`, `main()`  
**Digunakan oleh:** —  
**Menggunakan:** —


---


## bootstrap/

**File:** `bootstrap/maintenance.py`  
**Fungsi:** Stage 3 of application startup: schedule the periodic DB maintenance loop and the MPV connection watchdog as background tasks. Extracted from main.py's `main()` (T2.4) without changing call order. Also schedules the ADR-0010 periodic `[STATUS]` summary log.  
**Class:** —  
**Function utama:** `db_maintenance()`, `schedule_db_maintenance()`, `mpv_watchdog()`, `start_mpv_watchdog()`, `status_log_task()`, `schedule_status_log()`  
**Digunakan oleh:** `main`  
**Menggunakan:** `bootstrap/services`, `core/log_categories`, `core/state`, `core/task_utils`


---

**File:** `bootstrap/power.py`  
**Fungsi:** Acquire a PARTIAL wake-lock via `termux-wake-lock` on startup so the Android/HyperOS scheduler is less likely to freeze the server process when the screen turns off. This is a secondary, best-effort layer — the primary mitigation is the manual OS-level setup documented in docs/CONSTRAINTS.md (Autostart, battery saver exemption, recent-apps lock), since custom OEM power policies (HyperOS/MIUI) can ignore the standard Android wake-lock/notification APIs entirely.  
**Class:** —  
**Function utama:** `acquire_wake_lock()`  
**Digunakan oleh:** `bootstrap/startup_tasks`  
**Menggunakan:** `core/log_categories`


---

**File:** `bootstrap/services.py`  
**Fungsi:** Stage 1 of application startup: open the DB, connect core adapters (MPV, yt-dlp), and wire every domain service used by the rest of the app (resolver, playback controller, radio, volume, sleep timer, etc). Extracted from main.py's `main()` (T2.4, section "1-6" of the original God Function) without changing call order.  
**Class:** `BootstrapContext`  
**Function utama:** `init_core_services()`  
**Digunakan oleh:** `bootstrap/maintenance`, `bootstrap/startup_tasks`, `main`  
**Menggunakan:** `adapters/mpv`, `adapters/ytdlp`, `core/command_bus`, `core/event_bus`, `core/log_categories`, `core/state`, _6 lainnya_


---

**File:** `bootstrap/startup_tasks.py`  
**Fungsi:** Stage 2 of application startup: kick off the background tasks that must not block the web server from listening — connectivity polling, the initial MPV connect, and resuming the last-played track. Extracted from main.py's `main()` (T2.4) without changing call order.  
**Class:** —  
**Function utama:** `check_connectivity()`, `run_startup_checks()`  
**Digunakan oleh:** `main`  
**Menggunakan:** `bootstrap/power`, `bootstrap/services`, `config`, `core/log_categories`, `core/state`, `core/task_utils`


---


## 📋 Checklist Dokumentasi Docstring

**117/117** file `.py` sudah punya docstring modul terstruktur (`Purpose:` / `Subscribes to:` / `Publishes:`). Berikut yang belum:


_(semua file sudah terdokumentasi 🎉)_

<!-- END:GENERATED -->

---

**File:** launcher/gui_qt/main_window.py
**Fungsi:** PySide6 GUI component for main_window.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/theme.py
**Fungsi:** PySide6 GUI component for theme.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/conflict_banner.py
**Fungsi:** PySide6 GUI component for conflict_banner.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/console.py
**Fungsi:** PySide6 GUI component for console.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/info_bars.py
**Fungsi:** PySide6 GUI component for info_bars.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/quicklinks.py
**Fungsi:** PySide6 GUI component for quicklinks.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/ready_toast.py
**Fungsi:** PySide6 GUI component for ready_toast.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/status_hero.py
**Fungsi:** PySide6 GUI component for status_hero.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/titlebar.py
**Fungsi:** PySide6 GUI component for titlebar.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme

---

**File:** launcher/gui_qt/widgets/toolbar.py
**Fungsi:** PySide6 GUI component for toolbar.
**Class:** —
**Function utama:** —
**Digunakan oleh:** launcher/__main__, launcher/gui_qt/main_window
**Menggunakan:** launcher/gui_qt/theme
