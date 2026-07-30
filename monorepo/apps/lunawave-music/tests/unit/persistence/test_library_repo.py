"""
Module: tests.unit.persistence.test_library_repo

Purpose:
    Unit tests for the LibraryRepository class.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - persistence.library_repo

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import pytest

from persistence.library_repo import LibraryRepository


@pytest.mark.asyncio
async def test_get_random_songs_empty(memory_db):
    repo = LibraryRepository(memory_db)
    songs = await repo.get_random_songs()
    assert len(songs) == 0


@pytest.mark.asyncio
async def test_get_random_songs_with_data(memory_db):
    # Insert mock data
    await memory_db.execute("INSERT INTO artists (id, nama) VALUES (1, 'Artist A')")
    await memory_db.execute("INSERT INTO artists (id, nama) VALUES (2, 'Artist B')")

    await memory_db.execute(
        "INSERT INTO songs (youtube_id, judul, artist_id, duration) VALUES ('v1', 'Song 1', 1, 100)"
    )
    await memory_db.execute(
        "INSERT INTO songs (youtube_id, judul, artist_id, duration) VALUES ('v2', 'Song 2', 1, 110)"
    )
    await memory_db.execute(
        "INSERT INTO songs (youtube_id, judul, artist_id, duration) VALUES ('v3', 'Song 3', 2, 120)"
    )
    await memory_db.commit()

    repo = LibraryRepository(memory_db)

    # Test basic get
    songs = await repo.get_random_songs(limit=5)
    assert len(songs) == 3

    # Test exclude_ids
    songs_excluded = await repo.get_random_songs(limit=5, exclude_ids={"v1"})
    assert len(songs_excluded) == 2
    assert all(s.video_id != "v1" for s in songs_excluded)

    # Test max_per_artist
    songs_limited = await repo.get_random_songs(limit=5, max_per_artist=1)
    assert len(songs_limited) == 2  # One from Artist A, one from Artist B
