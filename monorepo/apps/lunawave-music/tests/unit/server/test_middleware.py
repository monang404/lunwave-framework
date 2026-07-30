"""
Module: tests.unit.server.test_middleware

Purpose:
    Unit tests for server middleware and request processing.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - server.middleware

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import pytest

from server.middleware import check_rate_limit


class MockManager:
    def __init__(self):
        self.rl_lock = asyncio.Lock()
        self.command_history = {}


@pytest.mark.asyncio
async def test_check_rate_limit():
    manager = MockManager()
    ip = "127.0.0.1"

    # Send 30 commands
    for i in range(30):
        assert await check_rate_limit(manager, ip, i) is True

    # 31st command should fail
    assert await check_rate_limit(manager, ip, 30) is False

    # Wait 61 seconds for the first command to expire
    # now = 61
    # First command was at t=0, so now-t = 61 > 60 -> should be filtered out
    # Only 28 commands remain (t=1..28)
    assert await check_rate_limit(manager, ip, 61) is True

    # Test with new IP to ensure deque defaults correctly
    ip2 = "192.168.1.2"
    assert await check_rate_limit(manager, ip2, 100) is True
