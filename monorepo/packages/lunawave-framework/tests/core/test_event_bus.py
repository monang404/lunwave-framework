"""packages/lunawave-framework/tests/core/test_event_bus.py — mirrors
lunawave_framework/core/kernel/event_bus.py (moved here from
apps/lunawave-music/tests/unit/core/test_event_bus.py in Phase 3 of the
framework extraction; core/event_bus.py in the app repo is now just a
backward-compat shim, see docs/adr/0013-core-domain-split.md there).

The original test used the app's LogMessageEvent/QueueUpdatedEvent as test
fixtures. EventBus is a domain-agnostic mechanism, so this version uses two
local DomainEvent subclasses instead -- the framework's own tests must not
import anything from the app's music.domain package.
"""

import gc
from dataclasses import dataclass

from lunawave_framework.core.kernel.event_bus import EventBus
from lunawave_framework.core.kernel.event_bus import bus as singleton_bus
from lunawave_framework.core.kernel.events import DomainEvent


@dataclass
class _FakeEventWithMessage(DomainEvent):
    """Stand-in for the app's LogMessageEvent (a DomainEvent with one field)."""

    message: str = ""


@dataclass
class _FakeEventNoFields(DomainEvent):
    """Stand-in for the app's QueueUpdatedEvent (a fieldless DomainEvent)."""

    pass


class _Listener:
    """Plain object whose bound method is used as a subscriber, so the
    EventBus stores it via weakref.WeakMethod (see L-3 note in source)."""

    def __init__(self):
        self.received = []

    def on_event(self, event):
        self.received.append(event)

    async def on_event_async(self, event):
        self.received.append(event)


async def test_publish_delivers_to_sync_function_subscriber():
    eb = EventBus()
    received = []

    def handler(event):
        received.append(event)

    eb.subscribe(_FakeEventWithMessage, handler)
    await eb.publish(_FakeEventWithMessage(message="hi"))
    assert len(received) == 1
    assert received[0].message == "hi"


async def test_publish_delivers_to_async_function_subscriber():
    eb = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    eb.subscribe(_FakeEventWithMessage, handler)
    await eb.publish(_FakeEventWithMessage(message="async-hi"))
    assert len(received) == 1


async def test_publish_delivers_to_bound_method_subscriber_via_weakref():
    eb = EventBus()
    listener = _Listener()
    eb.subscribe(_FakeEventNoFields, listener.on_event)
    await eb.publish(_FakeEventNoFields())
    assert len(listener.received) == 1


async def test_publish_only_notifies_subscribers_of_matching_event_type():
    eb = EventBus()
    received = []
    eb.subscribe(_FakeEventWithMessage, lambda e: received.append(e))
    await eb.publish(_FakeEventNoFields())
    assert received == []


async def test_publish_with_no_subscribers_does_not_raise():
    eb = EventBus()
    await eb.publish(_FakeEventNoFields())


async def test_one_handler_exception_does_not_block_other_handlers():
    eb = EventBus()
    received = []

    def broken(event):
        raise ValueError("boom")

    def working(event):
        received.append(event)

    eb.subscribe(_FakeEventWithMessage, broken)
    eb.subscribe(_FakeEventWithMessage, working)
    await eb.publish(_FakeEventWithMessage(message="x"))
    assert len(received) == 1


async def test_async_handler_exception_does_not_block_other_handlers():
    eb = EventBus()
    received = []

    async def broken(event):
        raise ValueError("boom")

    async def working(event):
        received.append(event)

    eb.subscribe(_FakeEventWithMessage, broken)
    eb.subscribe(_FakeEventWithMessage, working)
    await eb.publish(_FakeEventWithMessage(message="x"))
    assert len(received) == 1


def test_unsubscribe_removes_handler():
    eb = EventBus()
    listener = _Listener()
    eb.subscribe(_FakeEventNoFields, listener.on_event)
    eb.unsubscribe(_FakeEventNoFields, listener.on_event)
    assert _FakeEventNoFields not in eb._subscribers


def test_unsubscribe_unknown_handler_is_a_noop():
    eb = EventBus()
    eb.unsubscribe(_FakeEventNoFields, lambda e: None)  # must not raise


async def test_dead_weakref_is_pruned_and_not_delivered_to():
    eb = EventBus()
    listener = _Listener()
    eb.subscribe(_FakeEventNoFields, listener.on_event)
    del listener
    gc.collect()
    # Should not raise even though the weakref is dead.
    await eb.publish(_FakeEventNoFields())
    eb.purge_dead_refs()
    assert _FakeEventNoFields not in eb._subscribers


def test_purge_dead_refs_removes_empty_event_type_keys():
    eb = EventBus()
    listener = _Listener()
    eb.subscribe(_FakeEventNoFields, listener.on_event)
    del listener
    gc.collect()
    eb.purge_dead_refs()
    assert _FakeEventNoFields not in eb._subscribers


async def test_multiple_subscribers_all_receive_the_event():
    eb = EventBus()
    counts = {"a": 0, "b": 0}
    eb.subscribe(_FakeEventWithMessage, lambda e: counts.__setitem__("a", counts["a"] + 1))
    eb.subscribe(_FakeEventWithMessage, lambda e: counts.__setitem__("b", counts["b"] + 1))
    await eb.publish(_FakeEventWithMessage())
    assert counts == {"a": 1, "b": 1}


def test_module_level_singleton_bus_is_an_event_bus_instance():
    assert isinstance(singleton_bus, EventBus)
