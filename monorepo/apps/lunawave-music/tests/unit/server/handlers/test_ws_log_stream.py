"""
Module: tests.unit.server.handlers.test_ws_log_stream

Purpose:
    Unit tests for server.handlers.ws_log_stream.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from server.handlers.ws_log_stream import (
    _log_tail_tasks,
    cleanup_log_viewer,
    handle_log_stream_command,
)


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture(autouse=True)
def clear_tasks():
    _log_tail_tasks.clear()
    yield
    for ws, task in list(_log_tail_tasks.items()):
        task.cancel()
    _log_tail_tasks.clear()


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(mock_ws):
    with patch("server.handlers.ws_log_stream.BASE_DIR", Path("/fake/dir")):
        # Subscribe
        await handle_log_stream_command("subscribe", mock_ws)
        assert mock_ws in _log_tail_tasks
        task = _log_tail_tasks[mock_ws]
        assert not task.done()

        # Subscribe again (should ignore)
        await handle_log_stream_command("subscribe", mock_ws)
        assert _log_tail_tasks[mock_ws] is task

        # Unsubscribe
        await handle_log_stream_command("unsubscribe", mock_ws)
        assert mock_ws not in _log_tail_tasks
        await asyncio.sleep(0)  # Allow loop to process cancellation
        assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_cleanup_log_viewer(mock_ws):
    with patch("server.handlers.ws_log_stream.BASE_DIR", Path("/fake/dir")):
        await handle_log_stream_command("subscribe", mock_ws)
        assert mock_ws in _log_tail_tasks

        cleanup_log_viewer(mock_ws)
        assert mock_ws not in _log_tail_tasks


@pytest.mark.asyncio
async def test_tail_log_loop(mock_ws, tmp_path):
    log_file = tmp_path / "lunawave.log"
    log_file.write_text("[12:00:00] INFO: old (k=v)\n", encoding="utf-8")

    with patch("server.handlers.ws_log_stream.BASE_DIR", tmp_path):
        await handle_log_stream_command("subscribe", mock_ws)

        # Allow task to open file
        await asyncio.sleep(0.1)

        # Write new line
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("[12:01:00] INFO: new (k=v2)\n")

        # Allow task to read and batch
        await asyncio.sleep(0.6)

        # Check if sent
        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "log_batch"
        assert len(call_args["logs"]) == 1
        assert call_args["logs"][0]["event"] == "new"
        assert call_args["logs"][0]["fields"] == {"k": "v2"}
