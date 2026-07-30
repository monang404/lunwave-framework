"""
Module: tests.unit.persistence.test_discover_repo_search

Purpose:
    Unit tests for DiscoverRepository.search_tracks() (Quick Search
    Discover, persistence/discover_repo.py) — separate file from
    test_discover_repo.py per task breakdown T-A2, so the new method's
    coverage doesn't inflate the existing file.

Responsibilities:
    - Cover: title match, artist match, no match, kategori (Solo/Band,
      K1) filter, decade (K2) filter, and empty/whitespace query.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""


async def _make_artist(db, id, nama, kategori="band", tahun_aktif="2020s"):
    await db.conn.execute(
        "INSERT INTO artists (id, nama, kategori, tahun_aktif) VALUES (?, ?, ?, ?)",
        (id, nama, kategori, tahun_aktif),
    )
    await db.conn.commit()


async def _make_track(db, video_id, title, artist, duration=180):
    await db.conn.execute(
        "INSERT INTO tracks (video_id, title, artist, duration) VALUES (?, ?, ?, ?)",
        (video_id, title, artist, duration),
    )
    await db.conn.commit()


async def _make_song(db, artist_id, judul, youtube_id, duration=180):
    await db.conn.execute(
        "INSERT INTO songs (artist_id, judul, youtube_id, duration) VALUES (?, ?, ?, ?)",
        (artist_id, judul, youtube_id, duration),
    )
    await db.conn.commit()


class TestSearchTracksBasicMatch:
    async def test_matches_by_title(self, db):
        await _make_track(db, "v1", "Bohemian Rhapsody", "Queen")
        await _make_track(db, "v2", "Another Song", "Other Artist")
        result = await db.discover.search_tracks("Bohemian")
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_matches_by_artist(self, db):
        await _make_track(db, "v1", "Some Track", "Queen")
        await _make_track(db, "v2", "Other Track", "Nirvana")
        result = await db.discover.search_tracks("Queen")
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_no_match_returns_empty_list(self, db):
        await _make_track(db, "v1", "Some Track", "Queen")
        result = await db.discover.search_tracks("Nonexistent Query")
        assert result == []

    async def test_query_empty_returns_empty_list_without_error(self, db):
        await _make_track(db, "v1", "Some Track", "Queen")
        assert await db.discover.search_tracks("") == []

    async def test_query_whitespace_only_returns_empty_list(self, db):
        await _make_track(db, "v1", "Some Track", "Queen")
        assert await db.discover.search_tracks("   ") == []

    async def test_no_conn_returns_empty_list(self, db):
        db.discover._conn = None
        assert await db.discover.search_tracks("Queen") == []


class TestSearchTracksKategoriFilter:
    async def test_filters_by_kategori_solo(self, db):
        await _make_artist(db, 1, "Solo Singer", kategori="solo")
        await _make_artist(db, 2, "The Band", kategori="band")
        await _make_track(db, "v1", "Song A", "Solo Singer")
        await _make_track(db, "v2", "Song B", "The Band")

        result = await db.discover.search_tracks("Song", kategori="solo")
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_filters_by_kategori_band(self, db):
        await _make_artist(db, 1, "Solo Singer", kategori="solo")
        await _make_artist(db, 2, "The Band", kategori="band")
        await _make_track(db, "v1", "Song A", "Solo Singer")
        await _make_track(db, "v2", "Song B", "The Band")

        result = await db.discover.search_tracks("Song", kategori="band")
        assert [r["video_id"] for r in result] == ["v2"]

    async def test_track_artist_unmatched_to_any_artist_excluded_when_kategori_filter_active(
        self, db
    ):
        """Sama seperti caveat get_taste_spectrum: track dari artist yang
        tidak match by-name ke tabel artists tidak ikut kehitung begitu
        filter kategori aktif."""
        await _make_track(db, "v1", "Song A", "Unknown Uploader")
        result = await db.discover.search_tracks("Song", kategori="solo")
        assert result == []


class TestSearchTracksCatalogSource:
    """Regression: sebelum fix, search_tracks() cuma query tabel `tracks`
    (cache/history), tidak pernah menyentuh `songs` (katalog kurasi per
    artis yang sama dipakai get_artist_detail()). Efeknya: artis dengan 10
    lagu di katalog tapi baru 1 yang pernah diputar/dicache, search cuma
    nemu 1 -- padahal 9 lainnya memang ada di database."""

    async def test_finds_catalog_song_never_cached_in_tracks(self, db):
        await _make_artist(db, 1, "Wali", kategori="band")
        # 1 track sudah pernah diputar (ada di cache `tracks`)...
        await _make_track(db, "v1", "Cari Jodoh", "Wali")
        # ...tapi 9 lagu lain cuma ada di katalog kurasi `songs`, belum
        # pernah diputar/dicache sama sekali.
        for i in range(2, 11):
            await _make_song(db, 1, f"Lagu Wali {i}", f"song_{i}")

        result = await db.discover.search_tracks("Wali")
        assert len(result) == 10
        video_ids = {r["video_id"] for r in result}
        assert video_ids == {"v1"} | {f"song_{i}" for i in range(2, 11)}

    async def test_catalog_only_song_has_sane_defaults(self, db):
        await _make_artist(db, 1, "Iwan Fals", kategori="solo")
        await _make_song(db, 1, "Bento", "song_bento", duration=240)

        result = await db.discover.search_tracks("Bento")
        assert len(result) == 1
        row = result[0]
        assert row["video_id"] == "song_bento"
        assert row["duration"] == 240
        assert row["local_path"] is None
        assert row["view_count"] is None
        assert row["is_favorite"] == 0
        assert "song_bento" in row["thumbnail"]

    async def test_track_wins_over_song_on_same_video_id(self, db):
        """Kalau video_id yang sama ada di tracks (sudah pernah diputar,
        metadata lengkap) DAN songs (katalog), versi tracks yang dipakai --
        bukan di-duplikasi jadi 2 baris."""
        await _make_artist(db, 1, "Sheila On 7", kategori="band")
        await _make_track(db, "dup1", "Sephia", "Sheila On 7", duration=999)
        await db.conn.execute(
            "UPDATE tracks SET local_path = ?, is_favorite = 1 WHERE video_id = ?",
            ("/cache/dup1.mp3", "dup1"),
        )
        await db.conn.commit()
        await _make_song(db, 1, "Sephia", "dup1", duration=240)

        result = await db.discover.search_tracks("Sephia")
        assert len(result) == 1
        assert result[0]["duration"] == 999
        assert result[0]["local_path"] == "/cache/dup1.mp3"
        assert result[0]["is_favorite"] == 1


class TestSearchTracksTokenizedMatching:
    """Regression: matching sebelumnya LIKE frasa utuh (harus persis
    berurutan). Sekarang tokenized -- tiap kata di-AND kan, urutan bebas."""

    async def test_matches_regardless_of_word_order(self, db):
        await _make_track(db, "v1", "Bento", "Iwan Fals")
        result = await db.discover.search_tracks("Fals Iwan")
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_requires_all_tokens_to_match(self, db):
        await _make_track(db, "v1", "Bento", "Iwan Fals")
        await _make_track(db, "v2", "Other Song", "Iwan Only")
        result = await db.discover.search_tracks("Iwan Fals")
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_full_phrase_match_ranked_above_token_only_match(self, db):
        # v2: frasa utuh "iwan fals" muncul persis di title.
        await _make_track(db, "v2", "Iwan Fals Terbaik", "Various Artists")
        # v1: kedua token match, tapi tersebar (bukan frasa utuh).
        await _make_track(db, "v1", "Fals Menyanyi", "Iwan Solo")

        result = await db.discover.search_tracks("Iwan Fals")
        assert [r["video_id"] for r in result] == ["v2", "v1"]


class TestSearchTracksDecadeFilter:
    async def test_filters_by_decade(self, db):
        await _make_artist(db, 1, "Nineties Artist", tahun_aktif="1990s")
        await _make_artist(db, 2, "Twenties Artist", tahun_aktif="2020s")
        await _make_track(db, "v1", "Song A", "Nineties Artist")
        await _make_track(db, "v2", "Song B", "Twenties Artist")

        result = await db.discover.search_tracks("Song", decade=1990)
        assert [r["video_id"] for r in result] == ["v1"]

    async def test_combined_kategori_and_decade_filter(self, db):
        await _make_artist(db, 1, "Nineties Solo", kategori="solo", tahun_aktif="1990s")
        await _make_artist(db, 2, "Nineties Band", kategori="band", tahun_aktif="1990s")
        await _make_track(db, "v1", "Song A", "Nineties Solo")
        await _make_track(db, "v2", "Song B", "Nineties Band")

        result = await db.discover.search_tracks("Song", kategori="solo", decade=1990)
        assert [r["video_id"] for r in result] == ["v1"]
