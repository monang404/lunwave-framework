import pytest

from server.connection_manager import ConnectionManager
from server.middleware import check_chat_rate_limit


@pytest.mark.asyncio
async def test_chat_rate_limit_spam():
    manager = ConnectionManager()
    key = "uid-1"
    now = 1000.0

    # Send 10 messages successfully
    for _ in range(10):
        allowed = await check_chat_rate_limit(manager, key, now)
        assert allowed is True

    # 11th message blocked
    allowed = await check_chat_rate_limit(manager, key, now)
    assert allowed is False


@pytest.mark.asyncio
async def test_chat_rate_limit_separate_keys():
    manager = ConnectionManager()
    now = 1000.0

    for _ in range(10):
        await check_chat_rate_limit(manager, "uid-1", now)

    assert await check_chat_rate_limit(manager, "uid-1", now) is False
    assert await check_chat_rate_limit(manager, "uid-2", now) is True


@pytest.mark.asyncio
async def test_chat_rate_limit_sliding_window():
    manager = ConnectionManager()
    key = "uid-1"
    now = 1000.0

    for _ in range(10):
        await check_chat_rate_limit(manager, key, now)

    assert await check_chat_rate_limit(manager, key, now) is False

    # 60s later, it resets
    assert await check_chat_rate_limit(manager, key, now + 61) is True
