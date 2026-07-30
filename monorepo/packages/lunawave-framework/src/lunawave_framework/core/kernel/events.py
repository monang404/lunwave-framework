"""
Module: lunawave_framework.core.kernel.events

Purpose:
    Base class for all typed domain events dispatched through
    lunawave_framework.core.kernel.event_bus.EventBus. Every concrete event
    (TrackStartedEvent, QueueUpdatedEvent, etc.) is app-domain vocabulary
    and stays in the consuming app (see music.domain.events in the
    lunawave-music app for the concrete example) -- this file holds only
    the shared, empty base.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.

Phase 3 extraction note:
    Framework half of the split proposed in ADR 0013
    (docs/adr/0013-core-domain-split.md) in the app repo.
"""

from dataclasses import dataclass


@dataclass
class DomainEvent:
    """Base class for all domain events."""

    pass
