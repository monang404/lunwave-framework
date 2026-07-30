"""tests/unit/core/test_event_bus.py

Phase 3 note: the EventBus mechanism tests moved to
packages/lunawave-framework/tests/core/test_event_bus.py (using local test
fixture events instead of the app's LogMessageEvent/QueueUpdatedEvent, since
the framework's own tests must not import from music.domain). This file
just confirms the app-repo shim (core/event_bus.py) re-exports the exact
same classes/singleton as the framework module -- no copy, no divergence.
"""

from core.event_bus import EventBus, bus
from lunawave_framework.core.kernel.event_bus import EventBus as _FrameworkEventBus
from lunawave_framework.core.kernel.event_bus import bus as _framework_bus


def test_shim_event_bus_is_the_framework_event_bus_class():
    assert EventBus is _FrameworkEventBus


def test_shim_bus_is_the_same_singleton_instance():
    assert bus is _framework_bus
