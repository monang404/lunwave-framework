"""
Module: server.handlers.event_listeners

Purpose:
    Subscribe to domain events from the EventBus and forward them as
    WebSocket broadcasts via BroadcastService.

Responsibilities:
    - Bridge all relevant DomainEvents to connected WebSocket clients.
    - Trigger stream URL pre-fetch on TrackStartedEvent.

Depends on:
    - core.events
    - core.task_utils
    - server.serializers
    - server.broadcast_service
    - services.stream_prefetch

Subscribes to:
    TrackStartedEvent, TrackProgressEvent, QueueUpdatedEvent,
    LyricsUpdatedEvent, DownloadCompleteEvent, LogMessageEvent,
    TrackPauseChangedEvent, DownloadProgressEvent

Publishes:
    None

Thread Safety:
    Worker thread (async closures subscribed at startup).
"""

import asyncio

import structlog

from core.events import (
    DownloadCompleteEvent,
    DownloadProgressEvent,
    LogMessageEvent,
    LyricsUpdatedEvent,
    QueueUpdatedEvent,
    TrackPauseChangedEvent,
    TrackProgressEvent,
    TrackStartedEvent,
)
from core.log_categories import LC_LIFECYCLE
from core.task_utils import safe_create_task
from server.broadcast_service import BroadcastService
from services.stream_prefetch import StreamPrefetchService

logger = structlog.get_logger(component="server.event_listeners")


def setup_event_listeners(
    playback_controller,
    prefetch_service: StreamPrefetchService,
    broadcast_service: BroadcastService,
):
    async def _on_track_started(event: TrackStartedEvent):
        state = playback_controller.state
        _next = None
        if state.queue:
            _next = state.queue[0]
        elif state.radio_queue:
            _next = state.radio_queue[0]
        if _next and _next.video_id:
            safe_create_task(
                prefetch_service.prefetch_stream_url(_next.video_id),
                name=f"prefetch_next_{_next.video_id}",
            )

        await broadcast_service.broadcast_state(state)

    async def _on_track_progress(event: TrackProgressEvent):
        # Throttle sudah ditangani di sumber (mpv_controller, 1 Hz).
        await broadcast_service.broadcast_progress(
            event.position, playback_controller.state.status.name
        )

    async def _on_queue_updated(event: QueueUpdatedEvent):
        await broadcast_service.broadcast_state(playback_controller.state)

    async def _on_lyrics_updated(event: LyricsUpdatedEvent):
        await broadcast_service.broadcast_lyrics(playback_controller.state)

    async def _on_download_complete(event: DownloadCompleteEvent):
        await broadcast_service.broadcast_state(playback_controller.state)
        if event.track:
            safe_create_task(
                playback_controller.resolver.db.upsert_track(
                    event.track, local_path=event.track.local_path
                ),
                name="upsert_dl_track",
            )
            # Broadcast updated discover data to refresh cached list
            from server.serializers import track_to_dict
            from services.discover_service import DiscoverService

            ds = DiscoverService(playback_controller.resolver.db.discover)
            # 4 query independent — jalankan bersamaan, bukan berurutan
            recent, cached, featured_artists, featured_genres = await asyncio.gather(
                ds.get_recent(15),
                ds.get_cached(15),
                ds.get_featured_artists(100),
                ds.get_featured_genres(100),
            )
            await broadcast_service.manager.broadcast(
                {
                    "type": "discover_data",
                    "data": {
                        "recent": [track_to_dict(t) for t in recent],
                        "cached_tracks": [track_to_dict(t) for t in cached],
                        "featured_artists": featured_artists,
                        "featured_genres": featured_genres,
                    },
                }
            )

    async def _on_log_message(event: LogMessageEvent):
        msg = event.message
        playback_controller.state.error_msg = msg
        await broadcast_service.broadcast_log(msg)

    async def _on_pause_changed(event: TrackPauseChangedEvent):
        await broadcast_service.broadcast_progress(
            playback_controller.state.position, playback_controller.state.status.name
        )

    async def _on_download_progress(event: DownloadProgressEvent):
        await broadcast_service.broadcast_download_progress(event.progress)

    bus = playback_controller.bus
    bus.subscribe(TrackStartedEvent, _on_track_started)
    bus.subscribe(TrackProgressEvent, _on_track_progress)
    bus.subscribe(QueueUpdatedEvent, _on_queue_updated)
    bus.subscribe(LyricsUpdatedEvent, _on_lyrics_updated)
    bus.subscribe(DownloadCompleteEvent, _on_download_complete)
    bus.subscribe(LogMessageEvent, _on_log_message)
    bus.subscribe(TrackPauseChangedEvent, _on_pause_changed)
    bus.subscribe(DownloadProgressEvent, _on_download_progress)
    logger.info("event_subscriptions_registered", category=LC_LIFECYCLE)
