"""tests/unit/core/test_events.py — mirrors core/events.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from music.domain.events import (
    DomainEvent,
    DownloadCompleteEvent,
    DownloadProgressEvent,
    LogMessageEvent,
    LyricsUpdatedEvent,
    QueueUpdatedEvent,
    TrackDurationEvent,
    TrackEndedEvent,
    TrackPauseChangedEvent,
    TrackProgressEvent,
    TrackStartedEvent,
)
from music.domain.state import TrackInfo


def test_all_events_are_domain_events():
    events = [
        TrackStartedEvent(),
        TrackEndedEvent(),
        TrackProgressEvent(),
        TrackDurationEvent(),
        QueueUpdatedEvent(),
        LyricsUpdatedEvent(),
        DownloadCompleteEvent(),
        DownloadProgressEvent(),
        LogMessageEvent(),
        TrackPauseChangedEvent(),
    ]
    for event in events:
        assert isinstance(event, DomainEvent)


def test_track_started_event_defaults_and_payload():
    assert TrackStartedEvent().track is None
    track = TrackInfo(video_id="1", title="t", artist="a", duration=1)
    assert TrackStartedEvent(track=track).track is track


def test_track_ended_event_default_reason_is_empty_string():
    assert TrackEndedEvent().reason == ""
    assert TrackEndedEvent(reason="skipped").reason == "skipped"


def test_track_progress_and_duration_event_defaults():
    assert TrackProgressEvent().position == 0.0
    assert TrackProgressEvent(position=12.5).position == 12.5
    assert TrackDurationEvent().duration == 0.0
    assert TrackDurationEvent(duration=200.0).duration == 200.0


def test_download_events_defaults():
    assert DownloadCompleteEvent().track is None
    assert DownloadProgressEvent().progress == 0.0
    assert DownloadProgressEvent(progress=0.5).progress == 0.5


def test_log_message_event_default_and_payload():
    assert LogMessageEvent().message == ""
    assert LogMessageEvent(message="hi").message == "hi"


def test_track_pause_changed_event_defaults_to_false():
    assert TrackPauseChangedEvent().is_paused is False
    assert TrackPauseChangedEvent(is_paused=True).is_paused is True


def test_events_are_dataclasses_with_equality_by_value():
    assert TrackEndedEvent(reason="x") == TrackEndedEvent(reason="x")
    assert TrackEndedEvent(reason="x") != TrackEndedEvent(reason="y")
