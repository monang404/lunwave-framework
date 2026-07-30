import json

import pytest

from server.connection_manager import ConnectionManager
from server.handlers.ws_chat import handle_chat_command


class MockWebSocket:
    def __init__(self):
        self.sent = []

    async def send_str(self, data):
        self.sent.append(data)


class MockChatRepo:
    def __init__(self):
        self.messages = []

    async def get_recent_messages(self, client_uid=None):
        return [m for m in self.messages if m.get("client_uid") == client_uid]

    async def add_message(self, sender, message, is_admin, client_uid=None, client_ip=None):
        msg = {"sender": sender, "message": message, "client_uid": client_uid, "is_admin": is_admin}
        self.messages.append(msg)
        return msg


class MockRepos:
    def __init__(self):
        self.chat = MockChatRepo()


@pytest.mark.asyncio
async def test_chat_idor_get_history():
    manager = ConnectionManager()
    repos = MockRepos()
    wsA = MockWebSocket()
    wsB = MockWebSocket()

    # WS A binds to uid-A
    await handle_chat_command(
        "get_chat_history", {"client_uid": "uid-A"}, wsA, repos, manager, False, "127.0.0.1"
    )
    assert manager.client_uids[wsA] == "uid-A"

    # WS B binds to uid-B
    await handle_chat_command(
        "get_chat_history", {"client_uid": "uid-B"}, wsB, repos, manager, False, "127.0.0.1"
    )
    assert manager.client_uids[wsB] == "uid-B"

    # WS B tries to get uid-A's history
    wsB.sent.clear()
    await handle_chat_command(
        "get_chat_history", {"client_uid": "uid-A"}, wsB, repos, manager, False, "127.0.0.1"
    )

    # Harus ditolak dengan pesan error PermissionError yang dicatch
    assert len(wsB.sent) == 1
    err_resp = json.loads(wsB.sent[0])
    assert err_resp["type"] == "error"
    assert "tidak valid" in err_resp["message"]
    assert manager.client_uids[wsB] == "uid-B"


@pytest.mark.asyncio
async def test_chat_idor_send_chat():
    manager = ConnectionManager()
    repos = MockRepos()
    wsA = MockWebSocket()

    # WS A binds to uid-A and sends
    await handle_chat_command(
        "send_chat",
        {"client_uid": "uid-A", "message": "hello", "sender_name": "A"},
        wsA,
        repos,
        manager,
        False,
        "127.0.0.1",
    )
    assert len(repos.chat.messages) == 1
    assert repos.chat.messages[0]["client_uid"] == "uid-A"

    # WS A tries to send with uid-B
    await handle_chat_command(
        "send_chat",
        {"client_uid": "uid-B", "message": "hacked", "sender_name": "A"},
        wsA,
        repos,
        manager,
        False,
        "127.0.0.1",
    )

    # Harusnya ditolak
    assert len(repos.chat.messages) == 1  # Tidak bertambah
    assert (
        len(wsA.sent) == 1
    )  # Broadcast pertama gak ada karena ga di active_connections, ini cuma error message
    err_resp = json.loads(wsA.sent[0])
    assert err_resp["type"] == "error"


@pytest.mark.asyncio
async def test_admin_behavior_unchanged():
    manager = ConnectionManager()
    repos = MockRepos()
    wsAdmin = MockWebSocket()

    # Admin membalas ke uid-A
    await handle_chat_command(
        "send_chat",
        {"target_uid": "uid-A", "message": "hello admin", "sender_name": "Admin"},
        wsAdmin,
        repos,
        manager,
        True,
        "127.0.0.1",
    )
    assert len(repos.chat.messages) == 1
    assert repos.chat.messages[0]["client_uid"] == "uid-A"

    # Admin membaca history uid-B
    await handle_chat_command(
        "get_chat_history", {"target_uid": "uid-B"}, wsAdmin, repos, manager, True, "127.0.0.1"
    )
    # Gak ada error, bisa bypass check
    assert manager.client_uids.get(wsAdmin) is None  # Admin ga bind client_uid-nya sendiri
