"""
Module: tests.integration.test_websocket_flow

Purpose:
    IT-01: Test end-to-end WebSocket communication.
    Connect -> Auth -> Dispatch command -> Receive broadcast state.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import pytest

from server.app import REPOS


@pytest.mark.asyncio
async def test_websocket_flow(app_client):
    """
    IT-01: WebSocket Flow
    Skenario: Connect → auth → command play → state broadcast
    """
    # 1. Connect WS
    repos = app_client.app[REPOS]
    from core.security import hash_password

    pwd_hash = hash_password("test-admin-password-not-a-secret")
    await repos.conn.execute(
        "INSERT INTO admin_account (username, password_hash) VALUES (?, ?)", ("admin", pwd_hash)
    )
    await repos.conn.commit()

    ws = await app_client.ws_connect("/ws")

    # 2. Auth handshake
    await ws.send_json(
        {
            "type": "cmd",
            "action": "auth",
            "data": {"username": "admin", "password": "test-admin-password-not-a-secret"},
        }
    )

    # Assert auth success
    while True:
        auth_resp = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
        if auth_resp.get("type") == "auth_status":
            assert auth_resp["data"]["success"] is True
            break

    # Flush any initial state broadcasts that happen right after connect
    while True:
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
        except TimeoutError:
            break

    # 3. Send Play command
    # Kita butuh URL pendek dan aman untuk test MPV.
    # Dispatch play via WS
    await ws.send_json(
        {
            "type": "cmd",
            "action": "play_track",
            "id": "req-2",
            "data": {"video_id": "jNQXAC9IVRw", "title": "Me at the zoo"},
        }
    )

    # 4. Tunggu state update dari broadcast
    received_track_started = False
    for _ in range(30):  # max 3 detik
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=0.5)
            if msg.get("type") == "state":
                state_data = msg["data"]
                if state_data.get("status") in ["LOADING", "PLAYING"]:
                    received_track_started = True
                    # Assert state structure
                    assert "current_track" in state_data
                    assert "position" in state_data
                    break
        except TimeoutError:
            continue

    assert (
        received_track_started
    ), "Did not receive state with loading/playing status after sending play command"

    await ws.close()
