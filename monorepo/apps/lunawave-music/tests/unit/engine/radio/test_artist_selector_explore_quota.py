import pytest

from core.state import AppState
from engine.radio.artist_selector import ArtistSelector


@pytest.mark.asyncio
async def test_artist_selector_explore_quota_cleanup():
    """
    Test untuk memastikan eksplorasi artis (random sample setelah bandit)
    masih berjalan dengan benar meskipun tanpa EXPLORE_QUOTA import,
    karena explore quota di artist_selector dihitung secara implisit
    (max_artists - bandit_count).
    """

    class MockArtists:
        def __init__(self):
            self.conn = True

        async def get_all_artists(self):
            return ["A", "B", "C", "D", "E"]

        async def get_reward_stats(self):
            return {}

    class MockLibrary:
        def __init__(self):
            self.conn = True

        async def get_random_songs(self, limit, exclude_ids, artists, max_per_artist):
            # Cukup kembalikan artists list
            class DummyTrack:
                def __init__(self, artist):
                    self.artist = artist
                    self.video_id = f"vid_{artist}"
                    self.title = f"Title {artist}"
                    self.duration = 200

            return [DummyTrack(a) for a in (artists or [])]

    state = AppState()
    selector = ArtistSelector(MockArtists(), MockLibrary(), state)
    await selector.ensure_artists_loaded()

    # gather_batch harusnya menghasilkan artis gabungan dari bandit dan explore (random)
    # ARTISTS_PER_BATCH default = 4, BANDIT_QUOTA = 3
    # Sehingga 1 slot tersisa untuk explore.
    batch = await selector.gather_batch()

    # Jika berjalan dengan baik, ia akan mengembalikan track yang berasosiasi
    # dengan artis tersebut. Kita cek set artist-nya.
    artists_in_batch = {t.artist for t in batch}

    assert (
        len(artists_in_batch) == 4
    ), f"Harus memilih 4 artis (3 bandit + 1 explore), tapi dapat {len(artists_in_batch)}"
