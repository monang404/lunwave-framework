"""
Module: tests.unit.server.test_connection_manager

Purpose:
    Unit tests for WebSocket connection management.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - server.connection_manager

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import pytest

from server.connection_manager import ConnectionManager


class MockWebSocket:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send_str(self, data):
        if self.fail:
            raise Exception("Connection failed")
        self.sent.append(data)


@pytest.mark.asyncio
async def test_connect_disconnect():
    cm = ConnectionManager()
    ws = MockWebSocket()

    await cm.connect(ws)
    assert ws in cm.active_connections
    assert len(cm.active_connections) == 1

    cm.disconnect(ws)
    assert ws not in cm.active_connections
    assert len(cm.active_connections) == 0


@pytest.mark.asyncio
async def test_connect_records_connected_at():
    """ADR-0010 O3.3: connect() must stamp connected_at for the ws."""
    cm = ConnectionManager()
    ws = MockWebSocket()

    await cm.connect(ws)
    assert ws in cm.connected_at
    assert isinstance(cm.connected_at[ws], float)


@pytest.mark.asyncio
async def test_disconnect_observes_session_duration_and_cleans_up():
    """ADR-0010 O3.3: disconnect() must observe ACTIVE_USER_SESSION_SECONDS
    and remove the ws from connected_at afterward (no leak)."""
    import asyncio

    from core.observability import ACTIVE_USER_SESSION_SECONDS

    cm = ConnectionManager()
    ws = MockWebSocket()

    before = ACTIVE_USER_SESSION_SECONDS._sum.get()

    await cm.connect(ws)
    await asyncio.sleep(0.01)
    cm.disconnect(ws)

    after = ACTIVE_USER_SESSION_SECONDS._sum.get()
    assert after > before
    assert ws not in cm.connected_at


@pytest.mark.asyncio
async def test_disconnect_without_prior_connect_does_not_crash():
    """disconnect() on a ws that was never connect()-ed (e.g. handshake
    failed before manager.connect()) must be a safe no-op, not raise."""
    cm = ConnectionManager()
    ws = MockWebSocket()

    cm.disconnect(ws)  # must not raise
    assert ws not in cm.active_connections


@pytest.mark.asyncio
async def test_broadcast():
    cm = ConnectionManager()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket(fail=True)  # This one will fail and should be removed

    await cm.connect(ws1)
    await cm.connect(ws2)

    await cm.broadcast({"cmd": "test"})

    assert len(ws1.sent) == 1
    assert '{"cmd": "test"}' in ws1.sent[0]

    # ws2 should be disconnected because it raised an exception
    assert ws2 not in cm.active_connections
    assert len(cm.active_connections) == 1


@pytest.mark.asyncio
async def test_broadcast_does_not_misattribute_result_to_concurrently_connected_client():
    """PATCH-2026-07-16-065 regression.

    Bug found: broadcast() built its `results` list against one snapshot of
    active_connections (taken to launch send_str() tasks), but then paired
    those results with a FRESHLY re-fetched `list(self.active_connections)`
    after the `await asyncio.gather(...)`. If the connection list's
    contents/order shift during that await — e.g. a client's own
    ws_handler independently calls disconnect() the moment its socket
    closes, concurrently with a brand-new client connecting — the
    re-fetched list no longer lines up index-for-index with `results`,
    so a send result meant for one ws gets attributed to a different ws.

    Reproduced here: while broadcast() is mid-flight for [ws_a (slow,
    succeeds), ws_b (fails)], ws_b's own handler independently disconnects
    it (simulating its reader loop noticing the close on its own, not via
    broadcast's cleanup) at the same moment a brand new client ws_c
    connects. Before the fix, ws_c — which was never even part of this
    broadcast — ended up wrongly disconnected because of the index
    misalignment between the stale `results` and the re-fetched list.
    """
    import asyncio

    class SlowWebSocket(MockWebSocket):
        def __init__(self, fail=False, delay=0.0):
            super().__init__(fail=fail)
            self.delay = delay

        async def send_str(self, data):
            if self.delay:
                await asyncio.sleep(self.delay)
            await super().send_str(data)

    cm = ConnectionManager()
    ws_a = SlowWebSocket(fail=False, delay=0.05)
    ws_b = SlowWebSocket(fail=True, delay=0.01)
    await cm.connect(ws_a)
    await cm.connect(ws_b)

    async def concurrent_mutation():
        # Timed to land after ws_b's send_str() has already raised
        # (delay=0.01) but before ws_a's finishes (delay=0.05) — i.e.
        # squarely inside broadcast()'s gather() await window.
        await asyncio.sleep(0.02)
        ws_c = SlowWebSocket(fail=False)
        await cm.connect(ws_c)
        # ws_b's own connection handler independently notices the close
        # and disconnects it — a real, common race with broadcast()'s own
        # cleanup of the same ws.
        cm.disconnect(ws_b)
        return ws_c

    _, ws_c = await asyncio.gather(
        cm.broadcast({"cmd": "test"}),
        concurrent_mutation(),
    )

    # ws_b genuinely failed (and was independently disconnected) -> gone.
    assert ws_b not in cm.active_connections
    # ws_a and the newly-connected ws_c never failed -> both must remain.
    assert ws_a in cm.active_connections
    assert ws_c in cm.active_connections
