"""
Module: lunawave_framework.core.storage.db

Purpose:
    Manages the SQLite database connection lifecycle and initialization.
    Generic: knows nothing about what tables the schema it's given
    contains (see ADR 0014 -- the app owns its schema.sql, this class
    just runs it).

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from pathlib import Path

import aiosqlite
import structlog

from lunawave_framework.core.logging.log_categories import LC_PERSISTENCE

logger = structlog.get_logger(component="persistence.db")


class DatabaseConnection:
    """Handle koneksi SQLite saja. Tidak tahu domain (track, artist, dll.)."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self):
        return self._conn

    async def init(self, schema_path: Path):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = await aiosqlite.connect(self.db_path)  # type: ignore
            self._conn.row_factory = aiosqlite.Row  # type: ignore
            await self._conn.execute("PRAGMA journal_mode=WAL")  # type: ignore
            await self._conn.execute("PRAGMA synchronous=NORMAL")  # type: ignore
            with open(schema_path, encoding="utf-8") as f:
                schema_sql = f.read()
            await self._conn.executescript(schema_sql)  # type: ignore
        except Exception as e:
            logger.critical(
                "db_init_failed",
                category=LC_PERSISTENCE,
                db_path=str(self.db_path),
                error_type=type(e).__name__,
                error=str(e),
            )
            raise
        await self._migrate_songs_unique_constraint()
        await self._backfill_fts5_if_needed()

    async def _migrate_songs_unique_constraint(self) -> None:
        """PATCH-2026-07-16-048: `songs.youtube_id` used to be globally UNIQUE,
        which silently dropped collaboration/duet tracks for every artist
        after the first one encountered on import. This migrates any
        pre-existing DB to a composite UNIQUE(artist_id, youtube_id), which
        keeps per-artist uniqueness (no dupes within one artist's list) while
        letting the same video appear under multiple artists. No-op on a
        fresh DB, since schema.sql already creates the new constraint."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("DB not initialised — call init() first")
        try:
            async with conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='songs'"
            ) as cursor:
                row = await cursor.fetchone()
        except Exception as e:
            logger.error("songs_migration_check_failed", category=LC_PERSISTENCE, error=str(e))
            return

        if not row or "youtube_id TEXT NOT NULL" in row[0]:
            # Table doesn't exist yet, or already has the new (non-globally-unique) schema.
            return

        logger.info(
            "songs_migration_starting",
            category=LC_PERSISTENCE,
            reason="global_unique_youtube_id_detected",
        )
        try:
            await conn.execute("ALTER TABLE songs RENAME TO songs_old_migration")
            await conn.execute(
                """
                CREATE TABLE songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist_id INTEGER,
                    judul TEXT NOT NULL,
                    youtube_id TEXT NOT NULL,
                    duration INTEGER DEFAULT 0,
                    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
                    UNIQUE (artist_id, youtube_id)
                )
                """
            )
            await conn.execute(
                "INSERT INTO songs (id, artist_id, judul, youtube_id, duration) "
                "SELECT id, artist_id, judul, youtube_id, duration FROM songs_old_migration"
            )
            await conn.execute("DROP TABLE songs_old_migration")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_songs_youtube_id ON songs(youtube_id)"
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_songs_artist_id ON songs(artist_id)")
            await conn.commit()
            logger.info("songs_migration_completed", category=LC_PERSISTENCE)
        except Exception as e:
            await conn.rollback()
            logger.error(
                "songs_migration_failed",
                category=LC_PERSISTENCE,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _backfill_fts5_if_needed(self) -> None:
        """PATCH-2026-07-22: Backfill FTS5 tables with existing data on first run
        after schema update, ensuring older dbs get indexed."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("DB not initialised — call init() first")
        try:
            async with conn.execute("SELECT COUNT(*) FROM tracks") as cursor:
                tracks_count = (await cursor.fetchone() or (0,))[0]
            async with conn.execute("SELECT COUNT(*) FROM tracks_fts") as cursor:
                tracks_fts_count = (await cursor.fetchone() or (0,))[0]

            async with conn.execute("SELECT COUNT(*) FROM songs") as cursor:
                songs_count = (await cursor.fetchone() or (0,))[0]
            async with conn.execute("SELECT COUNT(*) FROM songs_fts") as cursor:
                songs_fts_count = (await cursor.fetchone() or (0,))[0]

            if (tracks_count > 0 and tracks_fts_count == 0) or (
                songs_count > 0 and songs_fts_count == 0
            ):
                logger.info("fts5_backfill_starting", category=LC_PERSISTENCE)
                await conn.execute("DELETE FROM tracks_fts")
                await conn.execute(
                    "INSERT INTO tracks_fts(rowid, video_id, title, artist) "
                    "SELECT rowid, video_id, title, artist FROM tracks"
                )
                await conn.execute("DELETE FROM songs_fts")
                await conn.execute(
                    "INSERT INTO songs_fts(rowid, song_id, title, artist) "
                    "SELECT s.id, s.youtube_id, s.judul, a.nama FROM songs s JOIN artists a ON a.id = s.artist_id"
                )
                await conn.commit()
                logger.info("fts5_backfill_completed", category=LC_PERSISTENCE)
        except Exception as e:
            await conn.rollback()
            logger.error(
                "fts5_backfill_failed",
                category=LC_PERSISTENCE,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def close(self):
        if self._conn:
            # Simpan referensi thread worker SEBELUM close(), karena setelah
            # close() self._conn sudah None.
            worker_thread = getattr(self._conn, "_thread", None)
            await self._conn.close()
            self._conn = None

            # ROOT-CAUSE-FIX (zombie thread): aiosqlite.Connection.close()
            # menganggap selesai begitu future dari stop() ter-resolve, tapi
            # future itu di-resolve via call_soon_threadsafe() DI DALAM worker
            # thread, SEBELUM thread itu sendiri sempat break dari loop-nya
            # (lihat _connection_worker_thread: set_result dulu baru cek
            # sentinel & break). Jadi ada window kecil di mana close() sudah
            # return tapi OS thread masih hidup -- inilah yang bikin
            # '_connection_worker_thread' nyangkut jadi zombie non-daemon
            # thread di akhir test run dan memicu force-exit CI.
            # Join eksplisit di sini memberi jaminan nyata bahwa thread sudah
            # benar-benar terminate sebelum close() return ke caller.
            # PATCH-2026-07-16-001: sleep(0.01) tidak menjamin apa-apa --
            # cuma menunda, bukan menunggu. join() asli (di thread terpisah
            # via to_thread agar tidak block event loop) adalah satu-satunya
            # cara memastikan thread benar-benar selesai.
            if worker_thread is not None and worker_thread.is_alive():
                import asyncio

                await asyncio.to_thread(worker_thread.join, timeout=1.0)
