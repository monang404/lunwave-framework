# Persistence

← [architecture/backend.md](../architecture/backend.md) | [Blueprint.md](../Blueprint.md)

---

## Gambaran Umum

LunaWave menyimpan data di **SQLite** via `persistence/`. Domain tidak mengakses database secara langsung — semua lewat repository yang mengimplementasikan interface dari `core/ports.py`.

Alasan pilih SQLite atas JSON cache → [ADR-0002](../adr/0002-sqlite-over-json-cache.md)

---

## Struktur `persistence/`

```
persistence/
├── db.py                  DatabaseConnection — koneksi SQLite mentah, init schema, migrasi songs.youtube_id
├── schema.sql              DDL — single source of truth skema database
├── track_repo.py           TrackRepository — metadata track, play count, favorite, local path
├── session_repo.py         SessionRepository — session token autentikasi
├── admin_account_repo.py   AdminAccountRepository — akun admin tunggal (Fitur B, login_redesign)
├── artist_repo.py          ArtistRepository — statistik artis, lagu per-artis, reward bandit
├── genre_repo.py            GenreRepository — genre & lagu per-genre
├── library_repo.py         LibraryRepository — query random songs untuk library/radio seed
├── discover_repo.py        DiscoverRepository — query personalisasi tab Discover
├── discover_enrich.py      enrich_artists() — batch enrichment cover+genre, dipakai discover_repo
├── stream_cache.py         CacheResolver + ResolverDbCompat — resolve URI playback, cache
└── __init__.py             Repositories — container 1 koneksi + 7 repo domain (bukan facade)
```

> **Catatan:** `Database` (God Facade lama dengan method delegasi seperti `db.get_track()`) sudah **dihapus** (`PATCH-2026-07-18-084`, T2.2e). Digantikan `Repositories`, lihat [Inisialisasi Database](#inisialisasi-database) di bawah.

---

## Skema Database

### `tracks`

```sql
CREATE TABLE tracks (
    video_id        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    artist          TEXT,
    duration        INTEGER,
    view_count      INTEGER,
    thumbnail       TEXT,
    local_path      TEXT,             -- NULL jika belum didownload
    stream_url      VARCHAR(2048),    -- URL cache, bisa expire
    stream_url_ts   INTEGER,          -- Unix timestamp saat stream_url di-fetch
    play_count      INTEGER DEFAULT 0,
    last_played     INTEGER,          -- Unix timestamp
    is_favorite     INTEGER DEFAULT 0,
    loudness_lufs   REAL,             -- NULL = belum dianalisis
    true_peak_dbtp  REAL,             -- NULL = belum dianalisis, dari ffmpeg loudnorm
    last_position   REAL DEFAULT 0.0,
    unavailable     INTEGER DEFAULT 0,       -- 1 jika video dikonfirmasi hilang/private/diblokir
    unavailable_reason TEXT,                  -- pesan error asli yt-dlp saat ditandai unavailable
    created_at      INTEGER DEFAULT (strftime('%s','now'))
);
```

### `sessions`

```sql
CREATE TABLE sessions (
    token       TEXT PRIMARY KEY,
    expires_at  INTEGER NOT NULL
);
```

Session token login admin, dibuat oleh `server/handlers/auth.py` setelah `auth` sukses. Bukan session/riwayat pemutaran — untuk itu lihat kolom `last_played`/`play_count` di `tracks`.

> **⚠️ Penting:** Kolom `token` menyimpan **SHA-256 hash** dari raw token (bukan token itu sendiri). Raw token hanya ada di client. Lihat `core.security.hash_token()` dan `PATCH-2026-07-22-166`.

### `admin_account`

```sql
CREATE TABLE admin_account (
    username        TEXT UNIQUE,
    password_hash   TEXT,
    created_at      INTEGER        -- unix timestamp
);
```

Satu-satunya baris di tabel ini adalah source of truth kredensial login
admin (Fitur B: login_redesign) — diisi lewat alur Initial Setup, bukan
di-generate otomatis. `UNIQUE` pada `username` mencegah insert kedua kali
(dipakai sebagai lapis pertahanan terhadap submit ganda saat setup). Lihat
[ADR-0008](../adr/0008-admin-credentials-in-sqlite.md) untuk keputusan
lengkap (tanpa migrasi otomatis dari file password lama, env var override
tetap tersedia).

### `artists`

```sql
CREATE TABLE artists (
    id            INTEGER PRIMARY KEY,
    nama          TEXT NOT NULL,
    kategori      TEXT,
    tahun_aktif   TEXT,
    reward_alpha  INTEGER DEFAULT 1,   -- Thompson Sampling bandit (Sprint 3.3)
    reward_beta   INTEGER DEFAULT 1
);
```

`UNIQUE INDEX idx_artists_nama` mencegah duplikat nama. `reward_alpha`/`reward_beta` dipakai `DiscoverRepository.get_bandit_ranked_artists()` untuk ranking "Untuk Kamu" ala Thompson Sampling.

### `genres`

```sql
CREATE TABLE genres (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_genre  TEXT UNIQUE NOT NULL
);
```

### `artist_genres`

```sql
CREATE TABLE artist_genres (
    artist_id  INTEGER,
    genre_id   INTEGER,
    PRIMARY KEY (artist_id, genre_id),
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);
```

Tabel junction many-to-many artis↔genre.

### `songs`

```sql
CREATE TABLE songs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id   INTEGER,
    judul       TEXT NOT NULL,
    youtube_id  TEXT NOT NULL,
    duration    INTEGER DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE (artist_id, youtube_id)
);
```

Daftar lagu populer per-artis (seed radio mode/discover) — **beda dari
`tracks`**, yang menyimpan track yang benar-benar pernah diputar/didownload
user. `UNIQUE(artist_id, youtube_id)` sengaja per-artis, bukan global,
supaya kolaborasi/duet bisa muncul sah di lebih dari satu daftar artis
(lihat migrasi di `db.py`, `PATCH-2026-07-16-048`).

> **Single Source of Truth:** Skema hanya ada di `persistence/schema.sql`. Tidak ada DDL yang diduplikasi di tempat lain.

---

## Repository API

### `TrackRepository` (`track_repo.py`)

```python
class TrackRepository:
    async def get_track(self, video_id: str) -> TrackInfo | None
    async def upsert_track(self, track: TrackInfo, stream_url: str | None = None, local_path: str | None = None) -> None
    async def update_stream_url_only(self, video_id: str, stream_url: str) -> None
    async def set_local_path(self, video_id: str, local_path: str | None) -> None
    async def increment_play_count(self, video_id: str) -> None
    async def evict_stale_tracks(self) -> int
    async def toggle_favorite(self, video_id: str) -> int
    async def set_loudness(self, video_id: str, lufs: float, true_peak_dbtp: float | None = None) -> None
    async def set_last_position(self, video_id: str, position: float) -> None
```

`upsert_track()` hanya insert/update metadata + cache URL — `INSERT ... ON CONFLICT DO UPDATE`, dengan `stream_url`/`local_path` di-`COALESCE` (tidak menimpa nilai lama dengan `NULL`).

### `SessionRepository` (`session_repo.py`)

```python
class SessionRepository:
    async def create_session(self, token: str, expires_at: int) -> None
        # hash_token(token) sebelum INSERT — raw token tidak pernah masuk DB
    async def verify_session(self, token: str) -> bool
        # query dengan hash_token(token); hapus sesi expired otomatis
    async def extend_session(self, token: str, expires_at: int) -> None
    async def delete_session(self, token: str) -> None
    async def cleanup_sessions(self) -> None    # hapus session yang sudah expired
```

Dikonsumsi oleh `server/handlers/auth.py` untuk login berbasis token, terpisah dari `admin_account` (kredensial) — lihat [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md).

### `AdminAccountRepository` (`admin_account_repo.py`)

Fitur B (login_redesign). Satu-satunya konsumen resmi tabel `admin_account`
— `server/handlers/setup.py` (create) dan `server/handlers/auth.py` (read).
Hashing dilakukan di caller, bukan di repo ini.

```python
class AdminAccountRepository:
    async def create_admin_account(self, username: str, password_hash: str) -> None
    async def get_admin_account(self) -> Row | None
    async def admin_account_exists(self) -> bool
```

### `ArtistRepository` (`artist_repo.py`)

```python
class ArtistRepository:
    async def increment_artist_click(self, artist_name: str) -> None
    async def get_all_artists(self, kategori: str | None = None) -> list[str]
    async def get_artist_songs_strict(self, artist: str, limit: int = 10) -> list[TrackInfo]
    async def record_completion(self, artist_name: str) -> None   # bandit: track selesai diputar
    async def record_skip(self, artist_name: str) -> None         # bandit: track di-skip
    async def get_reward_stats(self) -> dict[str, tuple[float, float]]  # {nama: (alpha, beta)}
```

`record_completion`/`record_skip` meng-update `reward_alpha`/`reward_beta` di tabel `artists` — input untuk ranking bandit Thompson Sampling di `DiscoverRepository.get_bandit_ranked_artists()`.

### `GenreRepository` (`genre_repo.py`)

```python
class GenreRepository:
    async def increment_genre_click(self, genre_name: str) -> None
    async def get_genre_artists(self, genre_name: str, limit: int = 4) -> list[str]
    async def get_genre_songs(self, genre_name: str, ...) -> list[TrackInfo]
```

### `LibraryRepository` (`library_repo.py`)

```python
class LibraryRepository:
    async def get_random_songs(self, ...) -> list[TrackInfo]
```

Query acak dari tabel `songs` — dipakai sebagai seed untuk radio mode / rekomendasi umum, bukan library "lagu yang pernah diputar" (itu ada di `tracks` via `TrackRepository`).

### `DiscoverRepository` (`discover_repo.py`)

Query personalisasi tab Discover (lihat §Discover Tab Personalization di `STATUS.md`).

```python
class DiscoverRepository:
    async def get_bandit_ranked_artists(self, limit: int = 10) -> list[dict]   # "Untuk Kamu"
    async def get_unheard_artists(self, limit: int = 10) -> list[dict]          # "Belum Pernah Kamu Dengar"
    async def get_taste_spectrum(self) -> list[dict]
    async def get_top_genre(self) -> str | None
    async def get_genre_artists_enriched(self, genre_name: str, limit: int = 4) -> list[dict]
    async def search_tracks(self, query: str, ...) -> list[dict]
    async def get_artist_detail(self, nama: str) -> dict | None
```

`get_bandit_ranked_artists`/`get_unheard_artists`/`get_genre_artists_enriched` memanggil `discover_enrich.enrich_artists()` untuk batch-attach cover+genre (no N+1 query).

---

## Inisialisasi Database

### `DatabaseConnection` (`db.py`)

Handle koneksi SQLite mentah saja — tidak tahu domain (track, artist, dll).

```python
class DatabaseConnection:
    def __init__(self, db_path: Path = DB_PATH): ...

    async def init(self, schema_path: Path) -> None:
        # Buat direktori DB jika belum ada, buka koneksi, jalankan schema.sql,
        # lalu jalankan migrasi songs.youtube_id (composite UNIQUE, PATCH-2026-07-16-048)

    async def close(self) -> None:
        # Close koneksi + join worker thread aiosqlite eksplisit
        # (mencegah zombie thread, lihat komentar ROOT-CAUSE-FIX di db.py)
```

### `Repositories` (`__init__.py`)

Package entry point — bangun satu koneksi + tujuh repo domain, tanpa method delegasi (bukan facade).

```python
class Repositories:
    def __init__(self, db_path=None):
        self.tracks: TrackRepository | None = None
        self.sessions: SessionRepository | None = None
        self.artists: ArtistRepository | None = None
        self.genres: GenreRepository | None = None
        self.library: LibraryRepository | None = None
        self.discover: DiscoverRepository | None = None
        self.admin_account: AdminAccountRepository | None = None
        # self.conn — koneksi aiosqlite mentah (dipakai oleh server/handlers di beberapa titik)

    async def init(self) -> None:
        # db_connection.init(schema.sql) lalu jalankan loop ALTER TABLE
        # untuk kolom yang ditambahkan bertahap (is_favorite, reward_alpha/beta,
        # loudness_lufs, last_position, true_peak_dbtp, unavailable, dst -- try/except
        # "duplicate column" diabaikan, error lain di-log), baru instansiasi
        # ketujuh repo di atas dengan koneksi yang sama.

    async def close(self) -> None: ...
```

Konsumen inject repo yang relevan langsung: `LoudnessService(repos.tracks)`, `DiscoverService(repos.discover)`, `AdminAccountRepository` via `repos.admin_account` — bukan `repos` secara keseluruhan.

**Untuk testing:** gunakan `Repositories(db_path=Path(":memory:"))` — database in-memory, dibuat ulang setiap test (lihat fixture `db` di `tests/conftest.py`).

```python
# tests/conftest.py
@pytest.fixture
async def db():
    """In-memory SQLite `persistence.Repositories`, migrated and ready to use."""
    from persistence import Repositories

    repos = Repositories(db_path=Path(":memory:"))
    await repos.init()
    yield repos
    await repos.close()
```

---

## Cache Resolver (`stream_cache.py`)

`CacheResolver` menentukan URI playback dengan prioritas: file lokal → stream URL yang di-cache → resolve baru via yt-dlp. `ResolverDbCompat` adalah adapter tipis (bukan facade baru) yang menggabungkan method `TrackRepository` + `ArtistRepository` + `DiscoverRepository` yang benar-benar dipanggil lewat `resolver.db` di beberapa konsumen lintas-domain (`PlaybackController`, `TrackLoader`, `track_ended_ops`, `event_listeners`).

Detail lengkap → [backend/caching.md](caching.md)

---

## Data Statis — `artists_enriched.json` & `export_to_sqlite.py`

Bukan bagian dari database runtime. File ini adalah **sumber data statis** untuk enrichment artis (genre, nama alternatif, popularitas), dan sekaligus data awal untuk tabel `artists`/`genres`/`artist_genres`/`songs`.

```
data/artists_enriched.json   ← di-commit ke repo, bukan di-gitignore
data/export_to_sqlite.py     ← script satu-kali: JSON -> SQLite (drop+recreate artists/genres/artist_genres/songs)
data/lunawave.db             ← runtime, di-gitignore
```

Format `artists_enriched.json`:
```json
[
  {
    "name": "Radiohead",
    "genres": ["alternative rock", "art rock"],
    "aliases": ["Radiohead"],
    "popularity": 92
  }
]
```

Digunakan oleh `services/discover_service.py` untuk rekomendasi dan `engine/radio/artist_selector.py` untuk mode radio.

---

## Migrasi Skema

Dua jalur migrasi berjalan, keduanya idempotent (aman dijalankan berulang):

1. **`Repositories.init()`** (`__init__.py`) — loop `ALTER TABLE ... ADD COLUMN` untuk kolom baru yang ditambahkan bertahap seiring fitur baru (mis. `is_favorite`, `reward_alpha`/`reward_beta`, `loudness_lufs`). Error `"duplicate column"` diabaikan (berarti migrasi sudah pernah jalan); error lain (disk full, DB corrupt) di-log.
2. **`DatabaseConnection._migrate_songs_unique_constraint()`** (`db.py`) — migrasi terstruktur satu kali dari `songs.youtube_id` yang dulu `UNIQUE` global (drop kolaborasi/duet artis kedua dst) ke `UNIQUE(artist_id, youtube_id)`. No-op di DB baru (`schema.sql` sudah pakai constraint baru).

> **Jangan tambahkan `ALTER TABLE` langsung di `schema.sql`** — `executescript()` tidak punya error handling per-statement dan akan crash `OperationalError` kalau kolom sudah ada di DB lama. Tambahkan lewat loop di `Repositories.init()` (kolom baru) atau migrasi terstruktur seperti `_migrate_songs_unique_constraint` (perubahan constraint/struktur tabel).

Data awal (bukan skema) diimport dari `artists_enriched.json` via `data/export_to_sqlite.py` (jalankan manual, bukan bagian startup).

---

## Testing

Semua repository dapat di-test dengan SQLite in-memory lewat fixture `db` (`Repositories(":memory:")`):

```python
# Contoh: tests/unit/persistence/test_track_repo.py
async def test_upsert_and_get_track_round_trip(db):
    track = make_track()  # TrackInfo(video_id="vid1", title="Title", artist="Artist", duration=200)
    await db.tracks.upsert_track(track, stream_url="https://stream/1", local_path="/mp3/1.mp3")
    result = await db.tracks.get_track("vid1")
    assert result is not None
    assert result.title == "Title"
```

Test → `tests/unit/persistence/`

---

## Dokumen Terkait

- [backend/caching.md](caching.md) — Cache resolver (`CacheResolver`/`ResolverDbCompat`) detail lengkap
- [backend/api.md](api.md) — Action WS `setup_admin`/`auth` yang mengonsumsi `AdminAccountRepository`
- [architecture/domain.md](../architecture/domain.md) — `TrackInfo` domain object
- [architecture/folder_structure.md](../architecture/folder_structure.md) — Lokasi file di repo
- [ADR-0002](../adr/0002-sqlite-over-json-cache.md) — Kenapa SQLite?
- [ADR-0008](../adr/0008-admin-credentials-in-sqlite.md) — Kredensial admin di SQLite, tanpa migrasi otomatis
