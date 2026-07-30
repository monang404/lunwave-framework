"""packages/lunawave-framework/tests/core/test_command_bus.py — mirrors
lunawave_framework/core/kernel/command_bus.py (moved here from
apps/lunawave-music/tests/unit/core/test_command_bus.py in Phase 3 of the
framework extraction; core/command_bus.py in the app repo is now a
backward-compat shim recombining this CommandBus with music.domain.commands,
see docs/adr/0013-core-domain-split.md there).

The original file's `test_command_constants_are_unique_strings` test (which
checked CMD_* domain constants specifically) is NOT migrated here -- it
tested app-domain vocabulary, not the generic mechanism. A trimmed
shim-verification version of it stays in
apps/lunawave-music/tests/unit/core/test_command_bus.py to confirm the
Decision-3 shim recombination (framework CommandBus + music.domain.commands
CMD_* constants) actually works end-to-end.
"""

import asyncio

import pytest

from lunawave_framework.core.kernel.command_bus import CommandBus


def test_register_and_execute_sync_handler():
    bus = CommandBus()
    bus.register("cmd.echo", lambda data: data)
    result = None

    async def run():
        nonlocal result
        result = await bus.execute("cmd.echo", "hello")

    asyncio.run(run())
    assert result == "hello"


async def test_execute_awaits_async_handlers():
    bus = CommandBus()

    async def handler(data):
        return data * 2

    bus.register("cmd.double", handler)
    result = await bus.execute("cmd.double", 21)
    assert result == 42


def test_register_raises_on_duplicate_command():
    bus = CommandBus()
    bus.register("cmd.dup", lambda data: None)
    with pytest.raises(RuntimeError):
        bus.register("cmd.dup", lambda data: None)


def test_unregister_removes_handler():
    bus = CommandBus()
    bus.register("cmd.temp", lambda data: None)
    bus.unregister("cmd.temp")
    # Re-registering after unregister should succeed, not raise duplicate.
    bus.register("cmd.temp", lambda data: None)


def test_unregister_unknown_command_is_a_noop():
    bus = CommandBus()
    bus.unregister("cmd.does.not.exist")  # must not raise


async def test_execute_unknown_command_raises_runtime_error():
    bus = CommandBus()
    with pytest.raises(RuntimeError):
        await bus.execute("cmd.unknown")


async def test_execute_propagates_handler_exceptions():
    bus = CommandBus()

    async def failing(data):
        raise ValueError("handler broke")

    bus.register("cmd.fail", failing)
    with pytest.raises(ValueError):
        await bus.execute("cmd.fail")


async def test_execute_passes_none_data_by_default():
    bus = CommandBus()
    received = []

    async def handler(data):
        received.append(data)

    bus.register("cmd.nodata", handler)
    await bus.execute("cmd.nodata")
    assert received == [None]
