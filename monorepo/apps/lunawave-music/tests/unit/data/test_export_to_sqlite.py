import sqlite3
from unittest.mock import MagicMock, patch

from data.export_to_sqlite import create_tables, main


def test_create_tables():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    create_tables(cursor)

    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "artists" in tables
    assert "genres" in tables
    assert "artist_genres" in tables
    assert "songs" in tables
    conn.close()


def test_collaboration_song_kept_for_all_artists():
    """PATCH-2026-07-16-048 regression: a song shared by multiple artists
    (e.g. a duet) must be importable under every owning artist, not just
    the first one encountered — youtube_id is unique per-artist, not global."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    create_tables(cursor)

    cursor.execute(
        "INSERT INTO artists (id, nama, kategori, tahun_aktif) VALUES (1, 'Peterpan', 'Band', '2000')"
    )
    cursor.execute(
        "INSERT INTO artists (id, nama, kategori, tahun_aktif) VALUES (2, 'NOAH', 'Band', '2012')"
    )

    for artist_id in (1, 2):
        cursor.execute(
            "INSERT OR IGNORE INTO songs (artist_id, judul, youtube_id, duration) VALUES (?, ?, ?, ?)",
            (artist_id, "Separuh Aku", "tstwxIh6xJw", 240),
        )

    cursor.execute("SELECT artist_id FROM songs WHERE youtube_id = 'tstwxIh6xJw'")
    owning_artists = {row[0] for row in cursor.fetchall()}
    assert owning_artists == {1, 2}, (
        "Collaboration song was dropped for one of its artists — "
        "youtube_id constraint is not per-artist"
    )
    conn.close()


@patch("data.export_to_sqlite.os.path.exists", return_value=True)
@patch("data.export_to_sqlite.open", create=True)
@patch("data.export_to_sqlite.json.load")
@patch("data.export_to_sqlite.sqlite3.connect")
def test_export_to_sqlite_main(mock_connect, mock_json_load, mock_open, mock_exists):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.rowcount = 1

    mock_json_load.return_value = {
        "artists": [
            {
                "id": 1,
                "nama": "Test Artist",
                "kategori": "Solo",
                "tahun_aktif": "2020",
                "genre": ["Pop"],
                "lagu_populer": [
                    {"judul": "Test Song", "youtube_id": "vid123", "durasi_detik": 120}
                ],
            }
        ]
    }

    main()

    assert mock_cursor.execute.call_count > 0
    mock_conn.commit.assert_called_once()
