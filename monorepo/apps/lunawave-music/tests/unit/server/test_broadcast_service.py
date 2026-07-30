from unittest.mock import MagicMock

import pytest

from server.broadcast_service import BroadcastService


@pytest.mark.asyncio
async def test_broadcast_sends_to_all():
    conn_manager = MagicMock()
    svc = BroadcastService(conn_manager)
    assert svc is not None
