# Testing — Quick Start

> Dokumen ini adalah pintu masuk ke seluruh dokumentasi pengujian LunaWave.
> Untuk filosofi & strategi lengkap, lihat → [testing_strategy.md](testing_strategy.md)

---

## Menjalankan Test

```bash
# Unit tests (tanpa MPV / yt-dlp)
pytest tests/unit/ -v --cov --cov-fail-under=100

# Integration tests (butuh MPV + yt-dlp terinstall)
pytest tests/integration/ -v

# Frontend tests (butuh Node.js + Vitest)
npx vitest run tests/frontend/

# Semua sekaligus (CI mode)
pytest tests/unit/ tests/integration/ -v --cov --cov-fail-under=100
```

---

## Struktur Folder Test

```
tests/
├── conftest.py                   # Fixture bersama: event loop, temp SQLite
├── fakes/
│   ├── fake_audio_player.py      # Implements AudioPlayerPort
│   ├── fake_media_extractor.py   # Implements MediaExtractorPort
│   ├── fake_lyrics_provider.py   # Implements LyricsProvider
│   └── fake_sponsorblock_provider.py
├── unit/
│   ├── test_main.py
│   ├── test_config.py
│   ├── test_config_security.py
│   ├── core/
│   ├── adapters/
│   ├── engine/
│   ├── persistence/
│   ├── server/
│   ├── services/
│   ├── plugins/
│   └── launcher/
├── integration/
│   ├── test_websocket_flow.py
│   ├── test_playback_flow.py
│   ├── test_radio_flow.py
│   └── test_download_flow.py
└── frontend/
    ├── utils/
    │   └── format.test.js
    ├── store.test.js
    └── ws-routing.test.js
```

---

## Dokumentasi Pengujian

| Dokumen | Isi |
|---|---|
| [testing_strategy.md](testing_strategy.md) | Filosofi, prioritas, target coverage, fakes |
| [unit_testing.md](unit_testing.md) | Tabel unit test seluruh layer (~65 file) |
| [integration_testing.md](integration_testing.md) | 4 skenario integration test |
| [frontend_testing.md](frontend_testing.md) | Vitest, format/store/ws-routing |
| [performance_testing.md](performance_testing.md) | Placeholder — future work |

---

## Coverage Target

- **100%** pada semua file dalam scope testable
- File kategori `Manual` di-`omit` **secara eksplisit** di `pyproject.toml` dengan alasan tertulis
- Lihat daftar `omit` lengkap → [testing_strategy.md#coverage-configuration](testing_strategy.md#coverage-configuration)

---

## Referensi Terkait

- Konfigurasi `pyproject.toml` → [../devops/tooling.md](../devops/tooling.md)
- CI pipeline yang menjalankan test → [../devops/ci_cd.md](../devops/ci_cd.md)
- Fake implementations detail → [testing_strategy.md#fakes](testing_strategy.md#fakes)
