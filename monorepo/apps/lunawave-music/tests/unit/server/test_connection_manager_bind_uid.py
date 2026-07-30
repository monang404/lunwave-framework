"""
Unit tests for ConnectionManager.bind_client_uid
"""

import pytest

from server.connection_manager import ConnectionManager


class MockWebSocket:
    pass


def test_bind_client_uid_idempotent():
    cm = ConnectionManager()
    ws = MockWebSocket()

    cm.bind_client_uid(ws, "uid-A")
    assert cm.client_uids[ws] == "uid-A"

    # Idempotent
    cm.bind_client_uid(ws, "uid-A")
    assert cm.client_uids[ws] == "uid-A"


def test_bind_client_uid_different_uid():
    cm = ConnectionManager()
    ws = MockWebSocket()

    cm.bind_client_uid(ws, "uid-A")
    assert cm.client_uids[ws] == "uid-A"

    with pytest.raises(PermissionError, match="client_uid koneksi ini sudah terikat"):
        cm.bind_client_uid(ws, "uid-B")

    # Tetap uid-A
    assert cm.client_uids[ws] == "uid-A"


def test_bind_client_uid_different_ws():
    cm = ConnectionManager()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    cm.bind_client_uid(ws1, "uid-A")
    cm.bind_client_uid(ws2, "uid-B")

    assert cm.client_uids[ws1] == "uid-A"
    assert cm.client_uids[ws2] == "uid-B"
