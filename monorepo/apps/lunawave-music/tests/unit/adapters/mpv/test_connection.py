"""
Module: adapters.mpv.connection

Purpose:
    Unit tests for adapters.mpv.connection.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - adapters.mpv.connection
    - core.exceptions

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.mpv.connection import MpvConnection
from core.exceptions import MpvConnectionError


@pytest.fixture
def mock_subprocess():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        process_mock = AsyncMock()
        process_mock.terminate = MagicMock()
        process_mock.kill = MagicMock()
        process_mock.wait = AsyncMock()
        mock_exec.return_value = process_mock
        yield mock_exec


@pytest.fixture
def mock_open_pipe_connection():
    with patch(
        "adapters.mpv.connection._open_pipe_connection", new_callable=AsyncMock
    ) as mock_conn:
        reader = AsyncMock()
        writer = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        mock_conn.return_value = (reader, writer)
        yield mock_conn


@pytest.fixture
def mock_open_unix_connection():
    with patch("asyncio.open_unix_connection", new_callable=AsyncMock, create=True) as mock_unix:
        reader = AsyncMock()
        writer = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        mock_unix.return_value = (reader, writer)
        yield mock_unix


@pytest.mark.asyncio
@patch("os.name", "nt")
async def test_mpv_connection_connect_windows(mock_subprocess, mock_open_pipe_connection):
    conn = MpvConnection()

    success = await conn.connect()

    assert success is True
    assert conn.is_connected is True
    assert conn.shutting_down is False
    mock_subprocess.assert_called_once()
    # Polling probe + retry loop: open_pipe_connection dipanggil minimal 1x
    mock_open_pipe_connection.assert_called_with(conn.socket_path)
    assert mock_open_pipe_connection.call_count >= 1


@pytest.mark.asyncio
@patch("os.name", "posix")
@patch("os.path.exists", return_value=True)
async def test_mpv_connection_connect_unix(mock_exists, mock_subprocess, mock_open_unix_connection):
    conn = MpvConnection(socket_path="/tmp/mpv.sock")

    success = await conn.connect()

    assert success is True
    assert conn.is_connected is True
    mock_subprocess.assert_called_once()
    mock_open_unix_connection.assert_called_once_with("/tmp/mpv.sock")


@pytest.mark.asyncio
async def test_mpv_connection_already_connected(mock_subprocess):
    conn = MpvConnection()
    conn.is_connected = True

    success = await conn.connect()

    assert success is True
    mock_subprocess.assert_not_called()


@pytest.mark.asyncio
@patch("os.name", "nt")
async def test_mpv_connection_fails_after_10_attempts(mock_subprocess, mock_open_pipe_connection):
    # Make _open_pipe_connection always fail — baik untuk probe polling maupun retry loop
    mock_open_pipe_connection.side_effect = ConnectionError("Mock error")

    conn = MpvConnection()

    with pytest.raises(MpvConnectionError):
        await conn.connect()

    # Polling: 50 probe attempts + retry loop: 10 attempts = 60 total
    assert mock_open_pipe_connection.call_count == 60
    assert conn.is_connected is False


@pytest.mark.asyncio
@patch("os.name", "nt")
async def test_mpv_connection_disconnect(mock_subprocess, mock_open_pipe_connection):
    conn = MpvConnection()
    await conn.connect()

    assert conn.is_connected is True
    assert conn._writer is not None

    writer_mock = conn._writer
    process_mock = conn._mpv_process

    await conn.disconnect()

    assert conn.is_connected is False
    assert conn.shutting_down is True
    writer_mock.close.assert_called()
    writer_mock.wait_closed.assert_awaited()
    process_mock.terminate.assert_called_once()


@pytest.mark.asyncio
@patch("os.name", "nt")
async def test_windows_polling_exits_early_when_port_ready(
    mock_subprocess, mock_open_pipe_connection
):
    conn = MpvConnection()

    probe_call_count = 0

    async def side_effect_probe(pipe_name):
        nonlocal probe_call_count
        probe_call_count += 1
        if probe_call_count <= 2:
            raise FileNotFoundError("not ready yet")
        reader = AsyncMock()
        writer = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        return reader, writer

    mock_open_pipe_connection.side_effect = side_effect_probe

    success = await conn.connect()

    assert success is True
    assert conn.is_connected is True
    # Probe gagal 2x + probe sukses 1x + koneksi final 1x = 4 total
    assert probe_call_count <= 10


@pytest.mark.asyncio
@patch("os.name", "nt")
async def test_windows_polling_fallthrough_to_retry_loop(mock_subprocess):
    # Semua upaya koneksi gagal — polling exhausted, retry loop juga gagal
    with patch(
        "adapters.mpv.connection._open_pipe_connection", new_callable=AsyncMock
    ) as mock_conn:
        mock_conn.side_effect = FileNotFoundError("never ready")

        conn = MpvConnection()

        with pytest.raises(MpvConnectionError):
            await conn.connect()

        # Polling (50 attempts) + retry loop (10 attempts) = 60 total calls
        assert mock_conn.call_count == 60
