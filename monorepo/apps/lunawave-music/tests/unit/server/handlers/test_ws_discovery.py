import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.handlers.ws_discovery import handle_discovery_command


@pytest.mark.asyncio
async def test_handle_discovery_command_search():
    mock_ytdlp = AsyncMock()
    mock_track = MagicMock()
    mock_ytdlp.search.return_value = [mock_track]

    mock_ws = AsyncMock()

    with patch("server.handlers.ws_discovery.track_to_dict", return_value={"title": "Test"}):
        await handle_discovery_command("search", {"query": "Test Query"}, mock_ytdlp, None, mock_ws)

    mock_ytdlp.search.assert_called_once_with("Test Query", max_results=10)
    mock_ws.send_str.assert_called_once()
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["type"] == "search_results"
    assert sent_data["data"] == [{"title": "Test"}]


def _wire_discover_service_mock(mock_ds_instance, **overrides):
    """Wires the standard set of AsyncMock returns for a `discover` gather
    call, so each test only needs to override what it cares about."""
    defaults = dict(
        get_recent=[],
        get_favorites=[],
        get_cached=[],
        get_featured_artists=[],
        get_featured_genres=[],
        get_for_you=[],
        get_unheard=[],
        get_genre_affinity={"genre": None, "artists": []},
        get_taste_spectrum=[],
    )
    defaults.update(overrides)
    for name, value in defaults.items():
        setattr(mock_ds_instance, name, AsyncMock(return_value=value))


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.DiscoverService")
async def test_handle_discovery_command_discover(mock_discover_service):
    mock_ds_instance = mock_discover_service.return_value
    _wire_discover_service_mock(
        mock_ds_instance,
        get_featured_artists=["Artist 1"],
        get_featured_genres=["Pop"],
    )

    mock_db = AsyncMock()
    mock_ws = AsyncMock()

    await handle_discovery_command("discover", {}, None, mock_db, mock_ws)

    mock_ds_instance.get_recent.assert_called_once_with(15)
    mock_ws.send_str.assert_called_once()

    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["type"] == "discover_data"
    assert sent_data["data"]["featured_artists"] == ["Artist 1"]
    assert sent_data["data"]["featured_genres"] == ["Pop"]
    assert sent_data["data"]["favorites"] == []


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.DiscoverService")
async def test_handle_discovery_command_discover_includes_personalization(mock_discover_service):
    """PATCH-2026-07-17-070: discover_data payload sekarang juga bawa
    for_you, unheard, genre_affinity_genre/artists, taste_spectrum."""
    mock_ds_instance = mock_discover_service.return_value
    _wire_discover_service_mock(
        mock_ds_instance,
        get_for_you=[{"nama": "Bandit Fave"}],
        get_unheard=[{"nama": "Fresh Artist"}],
        get_genre_affinity={"genre": "rock", "artists": [{"nama": "Rock Artist"}]},
        get_taste_spectrum=[{"genre": "rock", "pct": 100}],
    )

    mock_db = AsyncMock()
    mock_ws = AsyncMock()

    await handle_discovery_command("discover", {}, None, mock_db, mock_ws)

    mock_ds_instance.get_for_you.assert_called_once_with(15)
    mock_ds_instance.get_unheard.assert_called_once_with(15)
    mock_ds_instance.get_genre_affinity.assert_called_once_with(15)
    mock_ds_instance.get_taste_spectrum.assert_called_once_with()

    sent_data = json.loads(mock_ws.send_str.call_args[0][0])["data"]
    assert sent_data["for_you"] == [{"nama": "Bandit Fave"}]
    assert sent_data["unheard"] == [{"nama": "Fresh Artist"}]
    assert sent_data["genre_affinity_genre"] == "rock"
    assert sent_data["genre_affinity_artists"] == [{"nama": "Rock Artist"}]
    assert sent_data["taste_spectrum"] == [{"genre": "rock", "pct": 100}]


@pytest.mark.asyncio
async def test_handle_discovery_command_discover_search():
    mock_repo = AsyncMock()
    mock_repo.search_tracks.return_value = [
        {
            "video_id": "v1",
            "title": "Song A",
            "artist": "Artist A",
            "duration": 180,
            "thumbnail": "thumb.jpg",
            "local_path": "/cache/v1.mp3",
            "view_count": 100,
            "is_favorite": 1,
        }
    ]
    mock_ws = AsyncMock()

    await handle_discovery_command(
        "discover_search",
        {"query": "Song A", "kategori": "solo", "decade": 1990},
        None,
        mock_repo,
        mock_ws,
    )

    mock_repo.search_tracks.assert_called_once_with("Song A", kategori="solo", decade=1990)
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["type"] == "discover_search_results"
    assert sent_data["data"] == [
        {
            "video_id": "v1",
            "title": "Song A",
            "artist": "Artist A",
            "duration": 180,
            "thumbnail": "thumb.jpg",
            "is_cached": True,
            "view_count": 100,
            "is_favorite": True,
        }
    ]


@pytest.mark.asyncio
async def test_handle_discovery_command_discover_search_no_filters():
    """kategori/decade tidak dikirim -> None, bukan string kosong/'all'."""
    mock_repo = AsyncMock()
    mock_repo.search_tracks.return_value = []
    mock_ws = AsyncMock()

    await handle_discovery_command("discover_search", {"query": "Song"}, None, mock_repo, mock_ws)

    mock_repo.search_tracks.assert_called_once_with("Song", kategori=None, decade=None)


@pytest.mark.asyncio
async def test_handle_discovery_command_discover_search_decade_all_is_none():
    mock_repo = AsyncMock()
    mock_repo.search_tracks.return_value = []
    mock_ws = AsyncMock()

    await handle_discovery_command(
        "discover_search", {"query": "Song", "decade": "all"}, None, mock_repo, mock_ws
    )

    mock_repo.search_tracks.assert_called_once_with("Song", kategori=None, decade=None)


@pytest.mark.asyncio
async def test_handle_discovery_command_discover_search_kategori_all_is_none():
    """Regression: kategori="all" adalah sentinel client-side (chip "Semua"
    default aktif di discover-search-events.js), bukan nilai kategori valid
    di DB (artists.kategori cuma "individu"/"band"). Sebelum fix ini, kategori
    tidak di-exclude seperti decade, jadi search_tracks() dipanggil dengan
    kategori="all" -> filter SQL tidak pernah match apa pun -> 0 hasil selalu,
    walau query & data-nya valid."""
    mock_repo = AsyncMock()
    mock_repo.search_tracks.return_value = []
    mock_ws = AsyncMock()

    await handle_discovery_command(
        "discover_search", {"query": "Ari Lasso", "kategori": "all"}, None, mock_repo, mock_ws
    )

    mock_repo.search_tracks.assert_called_once_with("Ari Lasso", kategori=None, decade=None)


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.track_to_dict")
async def test_handle_discovery_command_discover_search_does_not_use_track_to_dict(
    mock_track_to_dict,
):
    """discover_search return dict row mentah (bukan TrackInfo), jadi
    track_to_dict() -- yang butuh attribute access -- tidak boleh dipanggil
    di branch ini (beda dari action 'search')."""
    mock_repo = AsyncMock()
    mock_repo.search_tracks.return_value = [
        {
            "video_id": "v1",
            "title": "Song A",
            "artist": "Artist A",
            "duration": 180,
            "thumbnail": None,
            "local_path": None,
            "view_count": None,
            "is_favorite": 0,
        }
    ]
    mock_ws = AsyncMock()

    await handle_discovery_command("discover_search", {"query": "Song"}, None, mock_repo, mock_ws)

    mock_track_to_dict.assert_not_called()


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.DiscoverService")
async def test_handle_discovery_command_get_artist_detail(mock_discover_service):
    """NOTE: this action is implemented but currently unreachable through
    the real websocket router — 'get_artist_detail' has not been added to
    DISCOVERY_CMDS in server/handlers/websocket.py yet (governance-gated,
    see PATCHLOG PATCH-2026-07-17-070). This test only covers the handler
    function in isolation, not end-to-end routing."""
    mock_ds_instance = mock_discover_service.return_value
    mock_ds_instance.get_artist_detail = AsyncMock(return_value={"nama": "Artist A"})

    mock_db = AsyncMock()
    mock_ws = AsyncMock()

    await handle_discovery_command(
        "get_artist_detail", {"artist": "Artist A"}, None, mock_db, mock_ws
    )

    mock_ds_instance.get_artist_detail.assert_called_once_with("Artist A")
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["type"] == "artist_detail"
    assert sent_data["data"] == {"nama": "Artist A"}


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.DiscoverService")
async def test_handle_discovery_command_get_artist_detail_blank_artist(mock_discover_service):
    mock_ds_instance = mock_discover_service.return_value
    mock_ds_instance.get_artist_detail = AsyncMock(return_value={"nama": "Should not be called"})

    mock_db = AsyncMock()
    mock_ws = AsyncMock()

    await handle_discovery_command("get_artist_detail", {"artist": "  "}, None, mock_db, mock_ws)

    mock_ds_instance.get_artist_detail.assert_not_called()
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["data"] is None


@pytest.mark.asyncio
@patch("server.handlers.ws_discovery.track_to_dict", side_effect=lambda t: {"title": t})
@patch("server.handlers.ws_discovery.DiscoverService")
async def test_handle_discovery_command_discover_includes_favorites(
    mock_discover_service, mock_track_to_dict
):
    """PATCH-061 regresi: get_favorites() diambil tapi dulu dibuang, tidak masuk payload."""
    mock_ds_instance = mock_discover_service.return_value
    _wire_discover_service_mock(mock_ds_instance, get_favorites=["Favorite Track"])

    mock_db = AsyncMock()
    mock_ws = AsyncMock()

    await handle_discovery_command("discover", {}, None, mock_db, mock_ws)

    mock_ds_instance.get_favorites.assert_called_once_with(15)
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["data"]["favorites"] == [{"title": "Favorite Track"}]
