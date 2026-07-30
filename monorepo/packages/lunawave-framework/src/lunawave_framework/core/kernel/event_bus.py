"""
Module: lunawave_framework.core.kernel.event_bus

Purpose:
    Implement a lightweight async pub/sub EventBus that decouples modules
    via typed DomainEvents, using weak references for method handlers.

Responsibilities:
    - Subscribe/unsubscribe handlers using WeakMethod to avoid memory leaks.
    - Dispatch events concurrently with per-handler error isolation.

Depends on:
    - lunawave_framework.core.kernel.events (DomainEvent base only --
      concrete event subclasses are app-domain vocabulary and are never
      imported here)
    - lunawave_framework.core.kernel.observability
    - lunawave_framework.core.kernel.task_utils
    - lunawave_framework.core.logging.log_categories

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async publish).
"""

import asyncio
import inspect
import weakref
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

from lunawave_framework.core.kernel.events import DomainEvent
from lunawave_framework.core.kernel.observability import EVENT_COUNT
from lunawave_framework.core.kernel.task_utils import safe_create_task
from lunawave_framework.core.logging.log_categories import LC_EVENT

logger = structlog.get_logger(component="core.event_bus")

E = TypeVar("E", bound=DomainEvent)


class EventBus:
    """
    Lightweight pub/sub using typed DomainEvents.
    Modules do not import each other directly —
    all communication goes through events to prevent circular imports.
    """

    def __init__(self):
        self._subscribers = defaultdict(list)

    # CATATAN PENTING (L-3):
    # Metode class/instance akan disimpan sebagai weak reference.
    # Namun, fungsi biasa, lambda, atau closure akan disimpan sebagai
    # strong reference, yang bisa menyebabkan memory leak jika tidak di-unsubscribe!
    def subscribe(self, event_type: type[E], handler: Callable[[E], Any]):
        # Gunakan weakref untuk method agar tidak memory leak
        if inspect.ismethod(handler):
            ref: Any = weakref.WeakMethod(handler)
        else:
            ref = handler
        self._subscribers[event_type].append(ref)

    def _resolve(self, ref):
        """Resolve ref ke handler asli. Return None jika dead weakref."""
        if isinstance(ref, weakref.ref):
            return ref()
        return ref

    def purge_dead_refs(self):
        """Hapus semua dead weakref dari seluruh subscriber list.
        Dipanggil otomatis dari unsubscribe(). Bisa juga dipanggil
        manual saat room dihancurkan untuk pembersihan menyeluruh.
        """
        for event_type in list(self._subscribers):
            self._subscribers[event_type] = [
                r for r in self._subscribers[event_type] if self._resolve(r) is not None
            ]
            # Hapus key jika list sudah kosong agar dict tidak tumbuh
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    def unsubscribe(self, event_type: type[E], handler: Callable[[E], Any]):
        """Remove a handler from an event, sekaligus bersihkan dead refs."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                r
                for r in self._subscribers[event_type]
                # Buang: (1) dead weakref, (2) ref yang menunjuk ke handler target
                if self._resolve(r) is not None and self._resolve(r) != handler
            ]
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
        # Bersihkan dead ref di semua event_type lain sekalian
        self.purge_dead_refs()

    async def publish(self, event: DomainEvent):
        """Publish event to all subscribers. Exceptions in one handler
        do NOT prevent subsequent handlers from executing (CRITICAL-01 fix)."""
        event_type = type(event)

        # Record Metric
        EVENT_COUNT.labels(event_type=event_type.__name__).inc()

        active_handlers = []
        for ref in list(self._subscribers.get(event_type, [])):
            if isinstance(ref, weakref.ref):
                handler = ref()
                if handler is None:
                    self._subscribers[event_type].remove(ref)  # Cleanup dead reference
                    continue
            else:
                handler = ref
            active_handlers.append(handler)

        # Concurrent dispatch with error boundary
        tasks = []
        for handler in active_handlers:
            if inspect.iscoroutinefunction(handler):

                async def _wrap_handler(h=handler):
                    try:
                        await h(event)
                    except Exception as e:
                        logger.error(
                            "event_handler_failed",
                            category=LC_EVENT,
                            handler_name=getattr(h, "__name__", str(h)),
                            event_type=event_type.__name__,
                            error_type=type(e).__name__,
                            error=str(e),
                            exc_info=True,
                        )

                tasks.append(safe_create_task(_wrap_handler(), name=f"event_{event_type.__name__}"))
            else:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(
                        "event_handler_failed",
                        category=LC_EVENT,
                        handler_name=getattr(handler, "__name__", str(handler)),
                        event_type=event_type.__name__,
                        error_type=type(e).__name__,
                        error=str(e),
                        exc_info=True,
                    )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Singleton
bus = EventBus()
