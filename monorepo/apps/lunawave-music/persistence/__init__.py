"""
Module: persistence

Purpose:
    Package entry point for the persistence layer: builds one DB connection
    and the six domain repositories that use it. Domain logic itself lives
    in each `*_repo.py` module (persistence.track_repo, .session_repo,
    .artist_repo, .genre_repo, .library_repo, .discover_repo) — this module
    only wires them up.

Responsibilities:
    - `Repositories`: construct the connection + all six repos, expose them
      as plain attributes. It has no delegate methods of its own (that was
      the old `Database` God Facade, removed in PATCH T2.2e) — a consumer
      takes exactly the repo(s) it needs (`repos.tracks`, `repos.discover`,
      ...), not this whole object.

Depends on:
    - persistence.artist_repo
    - persistence.db
    - persistence.discover_repo
    - persistence.genre_repo
    - persistence.library_repo
    - persistence.session_repo
    - persistence.track_repo

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from pathlib import Path

import structlog

from core.log_categories import LC_PERSISTENCE

logger = structlog.get_logger(component="persistence.init")

from persistence.admin_account_repo import AdminAccountRepository
from persistence.artist_repo import ArtistRepository
from persistence.chat_repo import ChatRepository
from persistence.db import DatabaseConnection
from persistence.discover_repo import DiscoverRepository
from persistence.genre_repo import GenreRepository
from persistence.library_repo import LibraryRepository
from persistence.session_repo import SessionRepository
from persistence.track_repo import TrackRepository


class Repositories:
    """Satu koneksi SQLite + enam repo domain. Bukan facade -- tidak ada
    method delegasi (`db.get_track()` dst sudah tidak ada di sini sejak
    PATCH T2.2e). Konsumer inject repo yang relevan langsung, mis.
    `LoudnessService(repos.tracks)`, `DiscoverService(repos.discover)`."""

    def __init__(self, db_path=None):
        from config import DB_PATH

        self._conn_manager = DatabaseConnection(db_path or DB_PATH)
        self.tracks: TrackRepository | None = None
        self.sessions: SessionRepository | None = None
        self.artists: ArtistRepository | None = None
        self.genres: GenreRepository | None = None
        self.library: LibraryRepository | None = None
        self.discover: DiscoverRepository | None = None
        self.admin_account: AdminAccountRepository | None = None
        self.chat: ChatRepository | None = None

    async def init(self):
        schema_path = Path(__file__).parent / "schema.sql"
        await self._conn_manager.init(schema_path)
        # Jalankan migrasi ALTER TABLE (sama seperti cache/db.py lama)
        for sql in [
            "ALTER TABLE tracks ADD COLUMN is_favorite INTEGER DEFAULT 0",
            "ALTER TABLE artists ADD COLUMN click_count INTEGER DEFAULT 0",
            "ALTER TABLE genres ADD COLUMN click_count INTEGER DEFAULT 0",
            "ALTER TABLE artists ADD COLUMN reward_alpha INTEGER DEFAULT 1",
            "ALTER TABLE artists ADD COLUMN reward_beta INTEGER DEFAULT 1",
            "ALTER TABLE tracks ADD COLUMN loudness_lufs REAL",
            "ALTER TABLE tracks ADD COLUMN last_position REAL DEFAULT 0.0",
            "ALTER TABLE tracks ADD COLUMN true_peak_dbtp REAL",  # H-3: true peak dari ffmpeg loudnorm
            # PATCH-2026-07-20-136: video yang dikonfirmasi dihapus/private/
            # diblokir permanen (VideoUnavailableError) -- CacheResolver
            # cek ini duluan sebelum hit yt-dlp lagi (lihat Rule 0 di
            # persistence/stream_cache.py).
            "ALTER TABLE tracks ADD COLUMN unavailable INTEGER DEFAULT 0",
            "ALTER TABLE tracks ADD COLUMN unavailable_reason TEXT",
            "ALTER TABLE chat_messages ADD COLUMN client_ip TEXT",
            # PATCH client_uid chat: client_ip di atas tidak lagi dipakai
            # sebagai kunci segmentasi (rusak di balik reverse proxy) --
            # kolom baru ini yang jadi identitas asli. client_ip masih
            # disimpan untuk audit saja.
            "ALTER TABLE chat_messages ADD COLUMN client_uid TEXT",
            # Index untuk client_uid dipindah ke sini (bukan di schema.sql) karena
            # pada DB lama kolomnya baru ada SETELAH baris ALTER TABLE di atas jalan --
            # kalau index ini ada di schema.sql, executescript() akan crash duluan
            # (lihat catatan di persistence/schema.sql).
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_client_uid ON chat_messages(client_uid)",
        ]:
            try:
                await self._conn_manager.conn.execute(sql)
                await self._conn_manager.conn.commit()
            except Exception as e:
                # "duplicate column" itu NORMAL (migrasi sudah pernah jalan) — jangan di-log sebagai error.
                # Selain itu (disk full, DB corrupt, dll) WAJIB tercatat.
                if "duplicate column" not in str(e).lower():
                    logger.error(
                        "db_migration_failed",
                        category=LC_PERSISTENCE,
                        sql=sql,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
        conn = self._conn_manager.conn
        self.tracks = TrackRepository(conn)
        self.sessions = SessionRepository(conn)
        self.artists = ArtistRepository(conn)
        self.genres = GenreRepository(conn)
        self.library = LibraryRepository(conn)
        self.discover = DiscoverRepository(conn)
        self.admin_account = AdminAccountRepository(conn)
        self.chat = ChatRepository(conn)

    async def close(self):
        await self._conn_manager.close()

    @property
    def conn(self):
        return self._conn_manager.conn
