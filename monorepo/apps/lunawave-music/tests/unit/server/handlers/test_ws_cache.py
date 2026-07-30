import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from config import DOWNLOAD_DIR
from server.handlers.ws_cache import (
    _clear_cache_sync,
    _get_cache_size_sync,
    handle_cache_command,
)


@pytest.mark.asyncio
async def test_get_cache_size():
    ws = AsyncMock()
    with patch("os.walk") as mock_walk, patch("os.path.getsize") as mock_getsize:
        mock_walk.return_value = [("/downloads", [], ["f1.mp3", "f2.mp3"])]
        mock_getsize.side_effect = [1000, 2000]
        with patch("pathlib.Path.exists", return_value=True):
            await handle_cache_command("get_cache_size", {}, ws, None, None, None)

    ws.send_str.assert_called_once()
    args = ws.send_str.call_args[0][0]
    data = json.loads(args)
    assert data["type"] == "cache_size"
    assert data["data"]["size_bytes"] == 3000


@pytest.mark.asyncio
async def test_get_cache_size_reads_download_dir_not_cache_dir():
    # Regression: this used to read config.CACHE_DIR (cache/mp3), which is
    # emptied right after each download finishes, so the Settings UI stayed
    # stuck at 0.00 MB even with real files sitting in downloads/.
    ws = AsyncMock()
    with patch("os.walk") as mock_walk, patch("os.path.getsize", return_value=100):
        mock_walk.return_value = [(str(DOWNLOAD_DIR), [], ["song.mp3"])]
        with patch("pathlib.Path.exists", return_value=True):
            await handle_cache_command("get_cache_size", {}, ws, None, None, None)

    walked_paths = [call.args[0] for call in mock_walk.call_args_list]
    assert str(DOWNLOAD_DIR) in walked_paths


@pytest.mark.asyncio
async def test_clear_cache():
    ws = AsyncMock()
    manager = AsyncMock()
    with patch("os.walk") as mock_walk, patch("os.remove") as mock_remove:
        mock_walk.return_value = [("/downloads", [], ["f1.mp3", "f2.mp3"])]
        with patch("pathlib.Path.exists", return_value=True):
            await handle_cache_command("clear_cache", {}, ws, None, manager, None)

    assert mock_remove.call_count == 2
    ws.send_str.assert_called_once()
    manager.broadcast.assert_called_once()


import tempfile


def _can_symlink():
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(d, os.path.join(d, "link"), target_is_directory=True)
            return True
        except OSError:
            return False


requires_symlink = pytest.mark.skipif(not _can_symlink(), reason="Requires symlink privileges")


def _make_symlinked_tree(tmp_path):
    """Build: <tmp_path>/download_dir/real_sub/inside.mp3 (real file)
    and <tmp_path>/download_dir/linked_sub -> <tmp_path>/outside (symlink),
    with <tmp_path>/outside/outside.mp3 sitting outside download_dir.
    Returns (download_dir, outside_dir).
    """
    download_dir = tmp_path / "download_dir"
    real_sub = download_dir / "real_sub"
    real_sub.mkdir(parents=True)
    (real_sub / "inside.mp3").write_bytes(b"x" * 111)

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "outside.mp3").write_bytes(b"y" * 222)

    linked_sub = download_dir / "linked_sub"
    os.symlink(outside_dir, linked_sub, target_is_directory=True)

    return download_dir, outside_dir


@requires_symlink
def test_get_cache_size_prunes_symlinked_dirs(tmp_path):
    download_dir, outside_dir = _make_symlinked_tree(tmp_path)

    with patch("server.handlers.ws_cache.DOWNLOAD_DIR", download_dir):
        size = _get_cache_size_sync()

    # Only the file in the real subdirectory should be counted.
    assert size == 111
    # Sanity check the file outside DOWNLOAD_DIR still exists untouched.
    assert (outside_dir / "outside.mp3").exists()


@requires_symlink
def test_clear_cache_does_not_delete_through_symlink(tmp_path):
    download_dir, outside_dir = _make_symlinked_tree(tmp_path)

    with patch("server.handlers.ws_cache.DOWNLOAD_DIR", download_dir):
        _clear_cache_sync()

    # File inside the real subdirectory was removed.
    assert not (download_dir / "real_sub" / "inside.mp3").exists()
    # File reached only via the symlinked subdirectory was NOT removed.
    assert (outside_dir / "outside.mp3").exists()


def test_get_cache_size_no_symlink_regression(tmp_path):
    # No symlinks at all: behavior for the existing normal case is unchanged.
    download_dir = tmp_path / "download_dir"
    sub = download_dir / "sub"
    sub.mkdir(parents=True)
    (sub / "a.mp3").write_bytes(b"a" * 10)
    (sub / "b.mp3").write_bytes(b"b" * 20)

    with patch("server.handlers.ws_cache.DOWNLOAD_DIR", download_dir):
        size = _get_cache_size_sync()

    assert size == 30


def test_clear_cache_no_symlink_regression(tmp_path):
    # No symlinks at all: all files still get deleted as before.
    download_dir = tmp_path / "download_dir"
    sub = download_dir / "sub"
    sub.mkdir(parents=True)
    (sub / "a.mp3").write_bytes(b"a" * 10)
    (sub / "b.mp3").write_bytes(b"b" * 20)

    with patch("server.handlers.ws_cache.DOWNLOAD_DIR", download_dir):
        _clear_cache_sync()

    assert not (sub / "a.mp3").exists()
    assert not (sub / "b.mp3").exists()
