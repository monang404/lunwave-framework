# ADR-0003: Hexagonal Architecture dengan typing.Protocol sebagai Ports

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave bergantung pada komponen eksternal yang sulit ditest: MPV (media player), yt-dlp (network calls), sistem file, dan subprocess. Tanpa abstraksi, unit test tidak bisa ditulis tanpa menjalankan MPV asli dan melakukan request jaringan nyata. Dua pendekatan dipertimbangkan: (1) mock langsung di test via `unittest.mock`; (2) hexagonal architecture — define interface (Port), buat implementasi asli (Adapter) dan implementasi palsu (Fake).

## Keputusan

Gunakan **hexagonal architecture** dengan `typing.Protocol` di `core/ports.py` sebagai definisi Port. Implementasi asli ada di `adapters/`, implementasi palsu untuk test ada di `tests/fakes/`.

## Alasan

Mock via `unittest.mock` mengikat test ke implementasi detail — perubahan nama method atau signature di adapter langsung break test meski behavior tidak berubah. Protocol sebagai interface yang eksplisit memberikan contract yang jelas: setiap Fake harus implement method yang sama, dan Python static type checker (mypy) bisa memverifikasi compliance. Ini juga memaksa dependency direction yang benar — `core/` tidak boleh import `adapters/`, hanya sebaliknya.

## Konsekuensi

- `core/ports.py` adalah satu-satunya tempat interface didefinisikan
- Semua external dependency harus diakses lewat Port, bukan langsung
- `tests/fakes/` berisi implementasi Port untuk test — reusable di seluruh test suite
- Dependency direction dijaga via `.importlinter`: `core/` tidak boleh import `adapters/`
- Proyek personal ini mendapat manfaat utama: seluruh domain logic bisa ditest tanpa MPV atau network

## Referensi

- Port definitions: `core/ports.py`
- Adapters: `adapters/mpv/`, `adapters/ytdlp/`
- Fakes: `tests/fakes/`
- Dependency rules: `docs/architecture/dependency_rules.md`
- Lihat juga: ADR-0001 (MPV IPC), ADR-0004 (CommandBus)
