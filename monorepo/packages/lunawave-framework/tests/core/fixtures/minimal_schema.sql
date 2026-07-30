-- Minimal schema for exercising lunawave_framework.core.storage in
-- isolation. This is NOT the app's real schema.sql (see ADR 0014: the
-- framework never ships or owns a schema of its own) -- it's a
-- test-only fixture with just enough shape (tracks/songs/artists +
-- their FTS5 tables, plus sessions/admin_account) to drive
-- DatabaseConnection's schema-agnostic migration and backfill logic
-- without depending on the app repo at all.

PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS tracks (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    video_id UNINDEXED,
    title,
    artist
);

CREATE TRIGGER IF NOT EXISTS tracks_fts_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, video_id, title, artist) VALUES (new.rowid, new.video_id, new.title, new.artist);
END;

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER,
    judul TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    duration INTEGER DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE (artist_id, youtube_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
    song_id UNINDEXED,
    title,
    artist
);

CREATE TRIGGER IF NOT EXISTS songs_fts_ai AFTER INSERT ON songs BEGIN
    INSERT INTO songs_fts(rowid, song_id, title, artist)
    SELECT new.id, new.youtube_id, new.judul, a.nama FROM artists a WHERE a.id = new.artist_id;
END;

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_account (
    username TEXT UNIQUE,
    password_hash TEXT,
    created_at INTEGER
);
