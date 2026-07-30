"""
Module: tests.unit.adapters.mpv.test_ipc

Purpose:
    Unit tests for MpvIPC — JSON command sending, property get/set,
    pending future management. Uses a fake MpvConnection stub instead
    of a real socket.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - adapters.mpv.ipc

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.mpv.ipc import MpvIPC

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fake_connection(is_connected: bool = True):
    """Return a minimal fake MpvConnection stub."""
    conn = MagicMock()
    conn.is_connected = is_connected
    conn.writer = MagicMock()
    conn.writer.write = MagicMock()
    conn.writer.drain = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# send_command
# ---------------------------------------------------------------------------


class TestSendCommand:
    @pytest.mark.asyncio
    async def test_returns_zero_when_not_connected(self):
        conn = make_fake_connection(is_connected=False)
        ipc = MpvIPC(conn)
        result = await ipc.send_command(["play"])
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_writer_is_none(self):
        conn = make_fake_connection()
        conn.writer = None
        ipc = MpvIPC(conn)
        result = await ipc.send_command(["play"])
        assert result == 0

    @pytest.mark.asyncio
    async def test_sends_json_and_returns_request_id(self):
        conn = make_fake_connection()
        ipc = MpvIPC(conn)

        req_id = await ipc.send_command(["set_property", "pause", True])

        assert req_id == 1
        written = conn.writer.write.call_args[0][0].decode()
        payload = json.loads(written.strip())
        assert payload["command"] == ["set_property", "pause", True]
        assert payload["request_id"] == 1

    @pytest.mark.asyncio
    async def test_increments_request_id_per_call(self):
        conn = make_fake_connection()
        ipc = MpvIPC(conn)

        id1 = await ipc.send_command(["play"])
        id2 = await ipc.send_command(["pause"])
        assert id1 == 1
        assert id2 == 2


# ---------------------------------------------------------------------------
# get_property
# ---------------------------------------------------------------------------


class TestGetProperty:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_connected(self):
        conn = make_fake_connection(is_connected=False)
        ipc = MpvIPC(conn)
        result = await ipc.get_property("volume")
        assert result is None

    @pytest.mark.asyncio
    async def test_resolves_future_with_value(self):
        conn = make_fake_connection()
        ipc = MpvIPC(conn)

        async def _resolve_future():
            await asyncio.sleep(0)
            fut = list(ipc._pending.values())[0]
            fut.set_result(80)

        task = asyncio.create_task(_resolve_future())
        result = await ipc.get_property("volume")
        await task
        assert result == 80

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        conn = make_fake_connection()
        ipc = MpvIPC(conn)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await ipc.get_property("volume")
        assert result is None


# ---------------------------------------------------------------------------
# set_property
# ---------------------------------------------------------------------------


class TestSetProperty:
    @pytest.mark.asyncio
    async def test_delegates_to_send_command(self):
        conn = make_fake_connection()
        ipc = MpvIPC(conn)
        ipc.send_command = AsyncMock(return_value=1)

        await ipc.set_property("volume", 80)

        ipc.send_command.assert_called_once_with(["set_property", "volume", 80])


# ---------------------------------------------------------------------------
# Pending future management
# ---------------------------------------------------------------------------


class TestPendingFutures:
    @pytest.mark.asyncio
    async def test_pop_pending_returns_and_removes_future(self):
        conn = make_fake_connection(is_connected=False)
        ipc = MpvIPC(conn)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        ipc._pending[42] = fut

        result = ipc.pop_pending(42)
        assert result is fut
        assert 42 not in ipc._pending

    @pytest.mark.asyncio
    async def test_pop_pending_returns_none_for_unknown_id(self):
        conn = make_fake_connection(is_connected=False)
        ipc = MpvIPC(conn)
        assert ipc.pop_pending(999) is None

    @pytest.mark.asyncio
    async def test_cancel_all_pending_cancels_and_clears(self):
        conn = make_fake_connection(is_connected=False)
        ipc = MpvIPC(conn)
        loop = asyncio.get_running_loop()

        fut1 = loop.create_future()
        fut2 = loop.create_future()
        ipc._pending[1] = fut1
        ipc._pending[2] = fut2

        ipc.cancel_all_pending()

        assert fut1.cancelled()
        assert fut2.cancelled()
        assert len(ipc._pending) == 0
