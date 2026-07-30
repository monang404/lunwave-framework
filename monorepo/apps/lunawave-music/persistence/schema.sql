PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS tracks (
    video_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    artist       TEXT,
    duration     INTEGER,
    view_count   INTEGER,
    thumbnail    TEXT,
    local_path   TEXT,           -- NULL if not downloaded
    stream_url   VARCHAR(2048),  -- cached URL, can expire
    stream_url_ts INTEGER,       -- Unix timestamp when URL was fetched
    play_count   INTEGER DEFAULT 0,
    last_played  INTEGER,        -- Unix timestamp
    is_favorite  INTEGER DEFAULT 0, -- 1 if liked, 0 otherwise
    loudness_lufs REAL,          -- NULL = belum dianalisis; integrated loudness (LUFS)
    true_peak_dbtp REAL,         -- NULL = belum dianalisis; true peak (dBTP), dari ffmpeg loudnorm
    last_position REAL DEFAULT 0.0, -- position resume
    unavailable  INTEGER DEFAULT 0, -- 1 jika video sudah dikonfirmasi hilang/private/diblokir permanen
    unavailable_reason TEXT,        -- pesan error asli yt-dlp saat ditandai unavailable
    created_at   INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_local_path ON tracks(local_path) WHERE local_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_last_played ON tracks(last_played DESC);
CREATE INDEX IF NOT EXISTS idx_play_count ON tracks(play_count DESC) WHERE play_count > 0;
CREATE INDEX IF NOT EXISTS idx_stream_url_ts ON tracks(stream_url_ts);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);

-- Fitur B (login_redesign): satu-satunya sumber kebenaran kredensial admin.
-- Diisi lewat alur Initial Setup (server/handlers/setup.py), bukan auto-generate.
CREATE TABLE IF NOT EXISTS admin_account (
    username TEXT UNIQUE,
    password_hash TEXT,
    created_at INTEGER
);

-- Artists untuk Radio Mode seed
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL,
    kategori TEXT,
    tahun_aktif TEXT,
    reward_alpha INTEGER DEFAULT 1,
    reward_beta INTEGER DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_artists_nama ON artists(nama);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_genre TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS artist_genres (
    artist_id INTEGER,
    genre_id INTEGER,
    PRIMARY KEY (artist_id, genre_id),
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);

-- youtube_id is unique per-artist (not globally): collaborations/duets
-- legitimately belong to more than one artist's popular-song list, and the
-- radio exclusion/prefetch logic already keys off video_id itself, not the
-- (artist_id, video_id) pair, so allowing the same video under multiple
-- artist rows is safe.
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER,
    judul TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE (artist_id, youtube_id)
);

CREATE INDEX IF NOT EXISTS idx_artists_kategori ON artists(kategori);
CREATE INDEX IF NOT EXISTS idx_songs_youtube_id ON songs(youtube_id);

CREATE INDEX IF NOT EXISTS idx_songs_artist_id ON songs(artist_id);

-- Migration untuk kolom-kolom yang ditambahkan bertahap dikelola di persistence/__init__.py
-- via loop ALTER TABLE dengan try/except yang mengabaikan "duplicate column name".
-- Jangan tambahkan ALTER TABLE di sini — executescript() tidak punya error handling
-- dan akan crash dengan OperationalError jika kolom sudah ada di DB lama.

-- FTS5 Tables for Discover Quick Search
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    video_id UNINDEXED,
    title,
    artist
);

CREATE TRIGGER IF NOT EXISTS tracks_fts_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, video_id, title, artist) VALUES (new.rowid, new.video_id, new.title, new.artist);
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_ad AFTER DELETE ON tracks BEGIN
    DELETE FROM tracks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_au AFTER UPDATE OF video_id, title, artist ON tracks BEGIN
    UPDATE tracks_fts SET video_id = new.video_id, title = new.title, artist = new.artist WHERE rowid = old.rowid;
END;

CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
    song_id UNINDEXED,
    title,
    artist
);

CREATE TRIGGER IF NOT EXISTS songs_fts_ai AFTER INSERT ON songs BEGIN
    INSERT INTO songs_fts(rowid, song_id, title, artist)
    SELECT new.id, new.youtube_id, new.judul, a.nama FROM artists a WHERE a.id = new.artist_id;
END;

CREATE TRIGGER IF NOT EXISTS songs_fts_ad AFTER DELETE ON songs BEGIN
    DELETE FROM songs_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS songs_fts_au AFTER UPDATE OF judul, artist_id, youtube_id ON songs BEGIN
    UPDATE songs_fts
    SET title = new.judul,
        song_id = new.youtube_id,
        artist = (SELECT nama FROM artists WHERE id = new.artist_id)
    WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS artists_fts_au AFTER UPDATE OF nama ON artists BEGIN
    UPDATE songs_fts SET artist = new.nama WHERE rowid IN (SELECT id FROM songs WHERE artist_id = new.id);
END;

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_name TEXT NOT NULL,
    message TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    client_uid TEXT,
    client_ip TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
-- idx_chat_messages_client_uid SENGAJA TIDAK di sini: pada DB lama (pre-client_uid),
-- kolom client_uid belum ada saat CREATE TABLE IF NOT EXISTS di atas di-skip (tabel
-- sudah ada), sehingga CREATE INDEX pada kolom yang belum ada bikin executescript()
-- crash SEBELUM migrasi ALTER TABLE ADD COLUMN client_uid (persistence/__init__.py)
-- sempat jalan. Index ini dipindah ke loop migrasi, dijalankan SETELAH ALTER TABLE-nya.
