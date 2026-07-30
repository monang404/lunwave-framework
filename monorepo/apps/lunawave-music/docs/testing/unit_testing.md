# Unit Testing

> Tabel unit test seluruh layer LunaWave — ~72 file, mirror path 1:1.
> Untuk filosofi dan setup, lihat → [testing_strategy.md](testing_strategy.md)

---

## 8.1 Root

| Kode | Test | Prioritas |
|---|---|---|
| `main.py` | `tests/unit/test_main.py` | Rendah (smoke, fake adapters) |
| `config.py` | `tests/unit/test_config.py` | Tinggi |
| `config_security.py` | `tests/unit/test_config_security.py` | Tinggi |
| `start.py` | — | Manual *(Tkinter entry point)* |

---

## 8.2 core/

Layer paling stabil — pure Python, tidak ada I/O, tidak ada dependency eksternal.

| Kode | Test | Prioritas |
|---|---|---|
| `core/state.py` | `tests/unit/core/test_state.py` | Tinggi |
| `core/event_bus.py` | `tests/unit/core/test_event_bus.py` | Tinggi |
| `core/command_bus.py` | `tests/unit/core/test_command_bus.py` | Tinggi |
| `core/commands.py` | `tests/unit/core/test_commands.py` | Tinggi *(boleh digabung ke test_command_bus.py)* |
| `core/events.py` | `tests/unit/core/test_events.py` | Tinggi |
| `core/ports.py` | `tests/unit/core/test_ports.py` | Rendah *(cukup pastikan semua fakes comply)* |
| `core/security.py` | `tests/unit/core/test_security.py` | Tinggi |
| `core/task_utils.py` | `tests/unit/core/test_task_utils.py` | Sedang *(butuh event loop)* |
| `core/observability.py` | `tests/unit/core/test_observability.py` | Sedang |
| `core/exceptions.py` | `tests/unit/core/test_exceptions.py` | Tinggi |
| `core/log_config.py` | `tests/unit/core/test_log_config.py` | Rendah |
| `core/latency_window.py` | — | Sedang |

**Total: 12 file test**

---

## 8.3 adapters/

Membutuhkan fake socket/HTTP — bukan network asli. Gunakan `FakeAudioPlayer` dan `FakeMediaExtractor` dari `tests/fakes/`.

| Kode | Test | Prioritas |
|---|---|---|
| `adapters/mpv/connection.py` | `tests/unit/adapters/mpv/test_connection.py` | Sedang *(mock unix socket)* |
| `adapters/mpv/ipc.py` | `tests/unit/adapters/mpv/test_ipc.py` | Sedang *(mock JSON-IPC)* |
| `adapters/mpv/observer.py` | `tests/unit/adapters/mpv/test_observer.py` | Sedang *(fake stream → assert publish)* |
| `adapters/ytdlp/searcher.py` | `tests/unit/adapters/ytdlp/test_searcher.py` | Sedang *(mock yt-dlp)* |
| `adapters/ytdlp/resolver.py` | `tests/unit/adapters/ytdlp/test_resolver.py` | Sedang |
| `adapters/ytdlp/downloader.py` | `tests/unit/adapters/ytdlp/test_downloader.py` | Sedang *(mock progress hook)* |

**Total: 6 file test**

---

## 8.4 engine/

Layer paling bernilai — **pure domain logic**, tidak ada I/O langsung. Prioritas tinggi semua.

| Kode | Test | Prioritas |
|---|---|---|
| `engine/command_router.py` | `tests/unit/engine/test_command_router.py` | Tinggi |
| `engine/download_manager.py` | `tests/unit/engine/test_download_manager.py` | Sedang |
| `engine/queue_manager.py` | `tests/unit/engine/test_queue_manager.py` | Tinggi |
| `engine/volume_service.py` | `tests/unit/engine/test_volume_service.py` | Tinggi |
| `engine/radio/prefetcher.py` | `tests/unit/engine/radio/test_prefetcher.py` | Tinggi |
| `engine/radio/artist_selector.py` | `tests/unit/engine/radio/test_artist_selector.py` | Tinggi |
| `engine/radio/track_filter.py` | `tests/unit/engine/radio/test_track_filter.py` | **Tinggi** — akar bug radio |
| `engine/radio/engine.py` | `tests/unit/engine/radio/test_engine.py` | Sedang |
| `engine/playback/controller.py` | `tests/unit/engine/playback/test_controller.py` | Sedang |
| `engine/playback/queue_ops.py` | `tests/unit/engine/playback/test_queue_ops.py` | Tinggi |
| `engine/playback/mode_ops.py` | `tests/unit/engine/playback/test_mode_ops.py` | Tinggi |
| `engine/playback/track_loader.py` | `tests/unit/engine/playback/test_track_loader.py` | Tinggi |
| `engine/radio/artist_bandit.py` | `tests/unit/engine/radio/test_artist_bandit.py` | Sedang |
| `engine/radio/track_interleaver.py` | `tests/unit/engine/radio/test_track_interleaver.py` | Sedang |
| `engine/loudness/analyzer.py` | `tests/unit/engine/loudness/test_analyzer.py` | Tinggi |
| `engine/loudness/gain_calculator.py` | `tests/unit/engine/loudness/test_gain_calculator.py` | Tinggi |
| `engine/loudness/service.py` | — | Sedang |

**Total: 17 file test**

> **Catatan `track_filter.py`:** File ini adalah akar dari bug radio mode.
> Test harus mencakup: filter duplikat, filter track yang baru diputar, filter berdasarkan genre/artist, edge case list kosong.

---

## 8.5 persistence/

Gunakan **in-memory SQLite** (`:memory:`) via fixture `db` dari `conftest.py` — murah, cepat, tidak perlu cleanup.

| Kode | Test | Prioritas |
|---|---|---|
| `persistence/db.py` | `tests/unit/persistence/test_db.py` | Sedang |
| `persistence/track_repo.py` | `tests/unit/persistence/test_track_repo.py` | Tinggi |
| `persistence/session_repo.py` | `tests/unit/persistence/test_session_repo.py` | Tinggi |
| `persistence/artist_repo.py` | `tests/unit/persistence/test_artist_repo.py` | Tinggi |
| `persistence/genre_repo.py` | `tests/unit/persistence/test_genre_repo.py` | Tinggi |
| `persistence/library_repo.py` | `tests/unit/persistence/test_library_repo.py` | Tinggi |
| `cache/resolver.py` | `tests/unit/cache/test_resolver.py` | Sedang |

**Total: 7 file test**

---

## 8.6 server/

Layer wiring — sebagian besar `Sedang` karena membutuhkan WebSocket/HTTP mock.

| Kode | Test | Prioritas |
|---|---|---|
| `server/app.py` | `tests/unit/server/test_app.py` | Rendah *(smoke: route terdaftar)* |
| `server/middleware.py` | `tests/unit/server/test_middleware.py` | Tinggi |
| `server/serializers.py` | `tests/unit/server/test_serializers.py` | Tinggi |
| `server/connection_manager.py` | `tests/unit/server/test_connection_manager.py` | Sedang |
| `server/handlers/auth.py` | `tests/unit/server/handlers/test_auth.py` | Sedang |
| `server/handlers/http.py` | `tests/unit/server/handlers/test_http.py` | Sedang |
| `server/handlers/event_listeners.py` | `tests/unit/server/handlers/test_event_listeners.py` | Sedang |
| `server/handlers/websocket.py` | `tests/unit/server/handlers/test_websocket.py` | Sedang |
| `server/handlers/ws_playback.py` | `tests/unit/server/handlers/test_ws_playback.py` | Sedang |
| `server/handlers/ws_queue.py` | `tests/unit/server/handlers/test_ws_queue.py` | Sedang |
| `server/handlers/ws_discovery.py` | `tests/unit/server/handlers/test_ws_discovery.py` | Sedang |
| `server/handlers/ws_download.py` | `tests/unit/server/handlers/test_ws_download.py` | Sedang |
| `server/broadcast_service.py` | `tests/unit/server/test_broadcast_service.py` | Sedang |
| `services/stream_prefetch.py` | `tests/unit/services/test_stream_prefetch.py` | Sedang |

**Total: 14 file test**

---

## 8.7 services/, plugins/, launcher/

| Kode | Test | Prioritas |
|---|---|---|
| `services/discover_service.py` | `tests/unit/services/test_discover_service.py` | Tinggi |
| `plugins/lyrics_fetcher.py` | `tests/unit/plugins/test_lyrics_fetcher.py` | Sedang *(mock HTTP)* |
| `plugins/lyrics_parser.py` | `tests/unit/plugins/test_lyrics_parser.py` | Tinggi *(pure parsing LRC)* |
| `plugins/lyrics_sync.py` | `tests/unit/plugins/test_lyrics_sync.py` | Tinggi |
| `plugins/notifications.py` | `tests/unit/plugins/test_notifications.py` | Sedang |
| `plugins/sponsorblock.py` | `tests/unit/plugins/test_sponsorblock.py` | Sedang *(mock HTTP)* |
| `launcher/process.py` | `tests/unit/launcher/test_process.py` | Sedang *(mock subprocess)* |
| `launcher/network.py` | `tests/unit/launcher/test_network.py` | Tinggi |
| `launcher/updater.py` | `tests/unit/launcher/test_updater.py` | Rendah *(masih stub)* |
| `launcher/gui/app.py` | — | Manual *(Tkinter lifecycle)* |
| `launcher/gui/ui_builder.py` | — | Manual *(Tkinter widget builder)* |
| `launcher/gui/status_panel.py` | `tests/unit/launcher/gui/test_status_panel.py` | Rendah |
| `launcher/gui/log_panel.py` | `tests/unit/launcher/gui/test_log_panel.py` | Rendah |
| `launcher/gui/dep_checker.py` | `tests/unit/launcher/gui/test_dep_checker.py` | Tinggi *(mock `shutil.which`)* |
| `automation/export_to_sqlite.py` | `tests/unit/automation/test_export_to_sqlite.py` | Opsional |

**Total: 13 file test (+ 2 Manual, 1 Opsional)**

---

## Ringkasan

| Layer | File Test | Catatan |
|---|---|---|
| Root | 3 | + 1 Manual |
| core/ | 12 | Pure logic, prioritas tinggi semua |
| adapters/ | 6 | Butuh fake socket/HTTP |
| engine/ | 17 | Layer paling bernilai |
| persistence/ | 7 | In-memory SQLite |
| server/ | 14 | WebSocket/HTTP mock |
| services/plugins/launcher/ | 13 | + 2 Manual, 1 Opsional |
| **Total** | **~72** | |

---

## Referensi Terkait

- Filosofi & fakes → [testing_strategy.md](testing_strategy.md)
- Integration tests → [integration_testing.md](integration_testing.md)
- Frontend tests → [frontend_testing.md](frontend_testing.md)
- Konfigurasi coverage → [../devops/tooling.md](../devops/tooling.md)
