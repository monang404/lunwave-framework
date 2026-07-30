import pytest

from engine.sleep_timer import SleepTimer


class MockBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class MockCommandBus:
    def __init__(self):
        self.executed = []

    async def execute(self, cmd, data=None):
        self.executed.append(cmd)


@pytest.mark.asyncio
async def test_sleep_timer_validation_invalid_type():
    bus = MockBus()
    cmd_bus = MockCommandBus()
    timer = SleepTimer(bus, cmd_bus)

    # invalid type should fallback to 0 (off)
    await timer.set_timer("invalid")
    assert len(bus.published) == 1
    assert "dimatikan" in bus.published[0].message
    assert timer._timer_task is None


@pytest.mark.asyncio
async def test_sleep_timer_validation_none():
    bus = MockBus()
    cmd_bus = MockCommandBus()
    timer = SleepTimer(bus, cmd_bus)

    # None should fallback to 0 (off)
    await timer.set_timer(None)
    assert len(bus.published) == 1
    assert "dimatikan" in bus.published[0].message
    assert timer._timer_task is None


@pytest.mark.asyncio
async def test_sleep_timer_validation_clamp_upper():
    bus = MockBus()
    cmd_bus = MockCommandBus()
    timer = SleepTimer(bus, cmd_bus)

    # 99999 should clamp to 1440
    await timer.set_timer(99999)
    assert len(bus.published) == 1
    assert "1440" in bus.published[0].message
    assert timer._timer_task is not None
    timer._timer_task.cancel()


@pytest.mark.asyncio
async def test_sleep_timer_validation_clamp_lower():
    bus = MockBus()
    cmd_bus = MockCommandBus()
    timer = SleepTimer(bus, cmd_bus)

    # -5 should clamp to 0
    await timer.set_timer(-5)
    assert len(bus.published) == 1
    assert "dimatikan" in bus.published[0].message
    assert timer._timer_task is None
