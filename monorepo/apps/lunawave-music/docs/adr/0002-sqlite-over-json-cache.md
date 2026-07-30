# ADR-0002: SQLite sebagai Persistence Layer, Bukan File JSON

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave perlu menyimpan data yang persisten: library track, session autentikasi, artist database (~2.500 entri dari Wikidata), dan cache URL stream. Opsi yang dipertimbangkan: (1) file JSON — sederhana, mudah dibaca; (2) SQLite — database relasional embedded, tidak butuh server.

## Keputusan

Gunakan **SQLite** via `aiosqlite` untuk semua persistence. Tidak ada file JSON untuk data yang perlu di-query.

## Alasan

JSON tidak mendukung query — untuk mencari track berdasarkan artist, genre, atau menghindari duplikat di radio mode, seluruh file harus di-load ke memory dan di-filter di Python. Dengan ~2.500 artist dan library yang bisa berkembang, ini tidak scalable. SQLite mendukung query terindeks, transaksi, dan berjalan in-process tanpa server eksternal. `aiosqlite` memungkinkan akses non-blocking dari asyncio event loop.

## Konsekuensi

- Semua repository harus diimplementasikan async via `aiosqlite`
- Schema migration perlu dikelola (saat ini via `schema.sql` yang dijalankan saat init)
- File `data/lunawave.db` harus di-gitignore — ini runtime artifact
- Test persistence layer menggunakan `:memory:` SQLite — cepat, tidak perlu cleanup
- Artist database diimport sekali dari Wikidata CSV ke SQLite via `automation/export_to_sqlite.py`

## Referensi

- Implementasi: `persistence/db.py`, `persistence/track_repo.py`, `persistence/artist_repo.py`
- Test: `tests/unit/persistence/`
- Import script: `automation/export_to_sqlite.py`
