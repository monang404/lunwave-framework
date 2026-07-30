# Folder Structure

← [architecture/overview.md](overview.md)

Legenda: **✅** tidak berubah · **🆕** file/folder baru · **🔧** opsional

---

## Backend

```
lunawave/
├── main.py                              wiring saja, ~80 baris
├── config.py                            config murni (env vars, path, konstanta)
├── start.py                             ✅
├── start.sh                             ✅
├── start.bat                            ✅
├── requirements.txt
├── requirements-dev.txt                 🆕 pytest, ruff, mypy, bandit, pip-audit, import-linter
├── pyproject.toml                       🆕 [tool.coverage] [tool.mypy] [tool.bandit] [tool.ruff]
├── .importlinter                        🆕 aturan arah dependency
│
├── core/
│   ├── state.py                         ✅
│   ├── event_bus.py                     ✅
│   ├── command_bus.py                   ✅
│   ├── commands.py                      🆕 konstanta CMD_* dipisah dari command_bus
│   ├── events.py                        ✅
│   ├── ports.py                         ✅
│   ├── security.py                      ✅ PBKDF2 password hash + SHA-256 token hash
│   ├── task_utils.py                    ✅
│   ├── observability.py                 ✅
│   ├── exceptions.py                    ✅
│   ├── log_config.py                    ✅
│   └── latency_window.py                🆕 adaptive prefetch metric window
│
├── adapters/                            🆕 adapter ke sistem eksternal
│   ├── mpv/
│   │   ├── connection.py                🆕 connect/reconnect/close socket
│   │   ├── ipc.py                       🆕 send command, pending futures
│   │   ├── observer.py                  🆕 event loop → publish ke bus
│   │   └── __init__.py                  🆕 facade MpvController
│   └── ytdlp/
│       ├── searcher.py                  🆕 search(query) → TrackInfo
│       ├── resolver.py                  🆕 get_stream_url(video_id)
│       ├── downloader.py                🆕 download_mp3 + progress hook
│       └── __init__.py                  🆕 facade YtDlpClient
│
├── engine/
│   ├── command_router.py                ✅
│   ├── download_manager.py              ✅
│   ├── queue_manager.py                 ✅ (hanya QueueMode — operasi queue di playback/)
│   ├── volume_service.py                ✅
│   ├── radio/                           🆕 pecahan radio_engine.py
│   │   ├── engine.py                    orchestrator, export RadioMode
│   │   ├── prefetcher.py
│   │   ├── artist_selector.py
│   │   ├── artist_bandit.py             🆕 thompson sampling bandit
│   │   ├── track_interleaver.py         🆕
│   │   ├── track_filter.py              akar bug radio mode ⚠️
│   │   ├── radio_config.py              konstanta BANDIT_QUOTA, EXPLORE_QUOTA, dll.
│   │   └── __init__.py
│   ├── loudness/                        🆕 EBU R128 loudness normalization
│   │   ├── analyzer.py                  🆕 ffprobe → LUFS measurement
│   │   ├── gain_calculator.py           🆕 hitung gain & MPV af filter
│   │   ├── service.py                   🆕 orchestrator pipeline
│   │   └── __init__.py                  🆕
│   └── playback/
│       ├── controller.py                slim orchestrator ⚠️ FREEZE
│       ├── queue_ops.py                 🆕 operasi queue level-rendah
│       ├── queue_controller.py          🆕 queue add/remove/reorder/select + auto-advance
│       ├── mode_ops.py                  🆕 set_crossfade/speed/loop
│       ├── settings_controller.py       🆕 set_mode/output/sponsorblock/loudness/radio_randomize/lyrics_offset
│       ├── track_loader.py              ✅ resolve URL (cache→yt-dlp) + load ke player
│       ├── crossfade.py                 🆕 fade in/out via MPV volume ramping
│       ├── track_ended_ops.py           🆕 penanganan saat track selesai diputar
│       ├── failure_ops.py               🆕 penanganan gagal load / error track
│       └── __init__.py
│
├── bootstrap/                           🆕 wiring startup di luar main.py
│   ├── power.py                         🆕 acquire_wake_lock() (Termux / Android)
│   ├── maintenance.py                   🆕 periodic cleanup task (session, cache)
│   ├── startup_tasks.py                 🆕 daftarkan & jalankan semua background task
│   └── services.py                      🆕 inisialisasi services optional (lyrics, sponsorblock)
│
├── persistence/                         🆕 pecahan cache/db.py
│   ├── db.py                            DatabaseConnection — koneksi SQLite, init schema, migrasi
│   ├── schema.sql                       DDL — single source of truth skema DB
│   ├── track_repo.py
│   ├── session_repo.py                  menyimpan SHA-256 hash token (bukan raw token)
│   ├── admin_account_repo.py            🆕 akun admin tunggal (Fitur B)
│   ├── artist_repo.py
│   ├── genre_repo.py
│   ├── library_repo.py
│   ├── discover_repo.py                 🆕 query personalisasi tab Discover
│   ├── discover_enrich.py               🆕 batch enrichment cover+genre
│   ├── stream_cache.py                  🆕 CacheResolver + DB compat (pindahan cache/)
│   └── __init__.py                      Repositories — container 1 koneksi + semua repo domain
│
├── cache/
│   ├── resolver.py                      ✅ waterfall: local path → stream_cache → yt-dlp
│   └── mp3/                             ✅ folder MP3 yang didownload
│
├── server/
│   ├── app.py                           ✅ aiohttp app factory, web.AppKey constants
│   ├── middleware.py                    ✅
│   ├── serializers.py                   ✅
│   ├── connection_manager.py            🆕 registry koneksi WS aktif (cut dari websocket.py)
│   ├── broadcast_service.py             🆕 push state ke semua WS (T2.7: di server/, bukan services/)
│   └── handlers/
│       ├── __init__.py                  typed accessors get_repos/get_state/get_manager/dll.
│       ├── auth.py                      ✅ login, rate limit, token issue
│       ├── http.py                      ✅ HTTP: /, /health, /metrics
│       ├── setup.py                     🆕 Initial Setup handler (buat admin_account)
│       ├── audio_stream_handler.py      🆕 streaming audio via /api/stream/{video_id}
│       ├── event_listeners.py           ✅
│       ├── websocket.py                 slim: Origin check (CSWSH) + lifecycle + routing
│       ├── ws_playback.py               🆕
│       ├── ws_queue.py                  🆕
│       ├── ws_discovery.py              🆕
│       ├── ws_download.py               🆕
│       └── ws_cache.py                  🆕 get_cache_size / clear_cache
│
├── services/
│   ├── discover_service.py              ✅ wrapper DiscoverRepository, personalisasi tab Discover
│   └── stream_prefetch.py               🆕 prefetch URL stream sebelum dibutuhkan
│
├── plugins/
│   ├── lyrics_fetcher.py                🆕 pecahan lyrics.py — fetch dari LRCLIB
│   ├── lyrics_parser.py                 🆕 parse LRC/SRT → List[LyricLine]
│   ├── lyrics_sync.py                   🆕 sync lirik via EventBus
│   ├── notifications.py                 ✅ Termux MediaStyle notification
│   └── sponsorblock.py                  ✅ skip sponsor segments
│
├── launcher/
│   ├── __main__.py                      entrypoint GUI launcher
│   ├── process.py                       ✅ start/stop server process
│   ├── network.py                       ✅ cek port, resolve host
│   ├── updater.py                       ✅ (stub)
│   └── gui/                             🆕 pecahan gui.py monolitik
│       ├── app.py
│       ├── ui_builder.py
│       ├── status_panel.py
│       ├── log_panel.py
│       ├── dep_checker.py
│       └── __init__.py
│
├── automation/
│   ├── doctor.py                        orchestrator health check (aggregasi semua checker)
│   ├── run_all.py                       entry point semua generator + checks
│   ├── find_owner.py                    lookup ownership modul/class/fungsi
│   ├── context_pack.py                  konteks lengkap file/fitur sekaligus
│   ├── repo_map.py                      generate DEPENDENCY_GRAPH.json
│   ├── call_graph.py                    visualisasi call graph fungsi
│   ├── event_graph.py                   audit event pub/sub (dead/ghost events)
│   ├── hotspot.py                       identifikasi file dengan churn tinggi
│   ├── impact.py                        analisis dampak perubahan file
│   ├── test_locator.py                  temukan test untuk modul tertentu
│   ├── patchlog.py                      CLI add/verify entry PATCHLOG.md
│   ├── architecture_lint.py             validasi import boundary
│   ├── generate_file_index.py           generate FILE_INDEX.md
│   ├── generate_report.py               update statistik REPORT.md
│   ├── verify_docs.py                   thin CLI → verify_docs/
│   ├── verify_security.py               cek .gitignore credential & DB
│   ├── verify_structure.py              cek file besar & pending items
│   ├── verify_docs/                     package: helpers, checks_*, render
│   └── shared/                          package: check_result, skip_dirs, generated_block
│
├── data/
│   ├── artists_enriched.json            ✅  data statis, source of truth artis
│   └── lunawave.db                      ✅  file database runtime (di-gitignore)
│
├── scratch/                             di luar arsitektur — biarkan
│
└── docs/                                ← dokumentasi hub
```

---

## Test

```
tests/
├── conftest.py                          fixture bersama: event loop, temp SQLite
├── fakes/
│   ├── fake_audio_player.py             AudioPlayerPort
│   ├── fake_media_extractor.py          MediaExtractorPort
│   ├── fake_lyrics_provider.py          LyricsProvider
│   └── fake_sponsorblock_provider.py    SponsorBlockProvider
├── unit/
│   ├── test_main.py
│   ├── test_config.py
│   ├── core/                            (11 file)
│   ├── adapters/
│   │   ├── mpv/                         (3 file)
│   │   └── ytdlp/                       (3 file)
│   ├── engine/
│   │   ├── test_command_router.py
│   │   ├── test_download_manager.py
│   │   ├── test_queue_manager.py
│   │   ├── test_volume_service.py
│   │   ├── radio/                       (4 file — test_track_filter.py prioritas tertinggi)
│   │   └── playback/                    (4 file)
│   ├── persistence/                     (6 file)
│   ├── cache/
│   │   └── test_resolver.py
│   ├── server/
│   │   ├── test_app.py
│   │   ├── test_middleware.py
│   │   ├── test_serializers.py
│   │   ├── test_connection_manager.py
│   │   └── handlers/                    (8 file)
│   ├── services/
│   │   └── test_discover_service.py
│   └── plugins/                         (5 file)
├── integration/
│   ├── test_websocket_flow.py
│   ├── test_playback_flow.py
│   ├── test_radio_flow.py
│   └── test_download_flow.py
└── frontend/                            opsional, prioritas rendah
    ├── utils/
    │   └── format.test.js
    ├── store.test.js
    └── ws-routing.test.js
```

Detail testing → [testing/unit_testing.md](../testing/unit_testing.md)

---

## Frontend

```
web/static/
├── index.html                           ✅ tidak dipecah
├── manifest.json                        ✅
├── sw.js                                ✅
│
├── js/
│   ├── config.js                        ✅
│   ├── store.js                         ✅
│   ├── dom.js                           ✅
│   ├── main.js                          ✅
│   ├── portal.js                        ✅
│   ├── ws.js                            slim — routing pesan masuk
│   ├── audio/                           🆕 pecahan audio.js
│   │   ├── playback-sync.js
│   │   └── visualizer.js
│   ├── utils/                           🆕 pecahan utils.js
│   │   ├── format.js
│   │   └── toast.js
│   ├── events/
│   │   ├── index.js                     ✅
│   │   ├── queue-events.js              ✅
│   │   ├── lyrics-events.js             ✅
│   │   ├── settings-events.js           ✅
│   │   ├── transport-events.js          🆕 play/pause/skip handler
│   │   ├── progress-events.js           🆕 seek bar drag/click
│   │   ├── search-input-events.js       🆕 debounce input → search
│   │   ├── action-modal-events.js       🆕 confirm/cancel modal
│   │   ├── click-delegation-events.js   🆕 event delegation list item
│   │   ├── keyboard-shortcut-events.js  🆕 keyboard shortcut global
│   │   └── drag-scroll-events.js        🆕 horizontal drag scroll
│   ├── render/
│   │   ├── player.js                    ✅
│   │   ├── now-playing.js               ✅
│   │   ├── lyrics.js                    ✅
│   │   ├── search.js                    ✅
│   │   ├── queue.js                     ✅
│   │   ├── full-state.js                🆕 pindahan dari ws.js
│   │   ├── discover-tab.js              🆕 render discover tab utama
│   │   ├── discover-personalize.js      🆕 render seksi personalisasi
│   │   ├── discover-search.js           🆕 render discover quick search
│   │   ├── radio-tab.js                 🆕 render radio mode UI
│   │   └── radio-hero-moon.js           🆕 animasi moon hero radio
│   ├── services/
│   │   └── auth.js                      ✅
│   └── platform/
│       ├── keyboard.js                  ✅
│       ├── touch.js                     ✅
│       └── viewport.js                  ✅
│
├── css/
│   ├── portal.css                       ✅
│   ├── tokens.css                       ✅
│   ├── base/                            ✅
│   ├── layout/                          ✅
│   ├── platform/                        ✅
│   └── components/
│       ├── toasts.css                   ✅
│       ├── lyrics.css                   ✅
│       ├── queue.css                    ✅
│       ├── search.css                   ✅
│       ├── settings-sheet.css           ✅
│       ├── player-controls.css          ✅
│       ├── player-bar.css               🆕 player bar layout
│       ├── cards.css                    🆕 base card styles
│       ├── discover-cards.css           🆕 discover-specific cards
│       ├── discover-search.css          🆕 discover quick search
│       └── radio-hero.css               🆕 radio hero moon UI
│   └── vendor/
│       ├── tabler-icons.min.css         ✅
│       └── fonts/                       ✅
│
└── icons/
    ├── icon-192.png                     ✅
    └── icon-512.png                     ✅
```

---

## Root (Open Source)

```
lunawave-main/
├── README.md                            ✅
├── LICENSE                              ✅ MIT
├── CHANGELOG.md                         ✅
├── CONTRIBUTING.md                      ✅
├── SECURITY.md                          ✅
├── .gitignore                           ✅
├── .editorconfig                        ✅
├── .pre-commit-config.yaml              ✅
└── .github/
    ├── workflows/
    │   └── ci.yml
    └── ISSUE_TEMPLATE/
        ├── bug_report.md
        └── feature_request.md
```

---

## Dokumen Terkait

- [architecture/backend.md](backend.md) — Detail tanggung jawab tiap modul backend
- [architecture/frontend.md](frontend.md) — Detail tanggung jawab tiap modul frontend
- [development/project_structure.md](../development/project_structure.md) — Peta risiko perubahan
