"""
Module: server.serializers

Purpose:
    Convert between AppState/TrackInfo domain objects and JSON-serializable
    dicts for WebSocket message payloads.

Responsibilities:
    - Serialize a TrackInfo or full AppState to a plain dict.
    - Deserialize an incoming dict payload into a TrackInfo instance.

Depends on:
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from core.state import AppState, AudioOutput, TrackInfo


def track_to_dict(track: TrackInfo | None) -> dict | None:
    if not track:
        return None
    return {
        "video_id": track.video_id,
        "title": track.title,
        "artist": track.artist,
        "duration": track.duration,
        "thumbnail": track.thumbnail,
        "is_cached": bool(track.local_path),
        "view_count": track.view_count,
        "is_favorite": bool(getattr(track, "is_favorite", 0)),
        "play_count": getattr(track, "play_count", None),
        "last_played": getattr(track, "last_played", None),
        "loudness_lufs": getattr(track, "loudness_lufs", None),
        "true_peak_dbtp": getattr(track, "true_peak_dbtp", None),
    }


def state_to_dict(state: AppState, include_lyrics: bool = True) -> dict:
    """include_lyrics=False dipakai untuk broadcast periodik yang tidak butuh
    payload lirik penuh — lirik sudah/akan dikirim lewat message "lyrics" terpisah.
    Default True dipertahankan untuk initial snapshot saat client baru connect."""
    data = {
        "status": state.status.name,
        "playback_mode": state.playback_mode.name,
        "current_track": track_to_dict(state.current_track),
        "position": state.position,
        "duration": state.duration,
        "volume": state.volume,
        "playback_speed": getattr(state, "playback_speed", 1.0),
        "loop_mode": getattr(state, "loop_mode", "off"),
        "crossfade_enabled": getattr(state, "crossfade_enabled", False),
        "audio_output": getattr(state, "audio_output", AudioOutput.DEVICE).value,
        "sponsorblock_active": state.sponsorblock_active,
        "loudness_normalization_enabled": getattr(state, "loudness_normalization_enabled", False),
        "queue": [track_to_dict(t) for t in state.queue],
        "radio_queue": [track_to_dict(t) for t in state.radio_queue],
        "history_count": len(state.history),
        "lyrics_index": state.lyrics_index,
        "lyrics_offset": state.lyrics_offset,
        "active_tab": state.active_tab,
        "error_msg": state.error_msg,
        "is_online": state.is_online,
        "download_progress": state.download_progress,
    }
    if include_lyrics:
        data["lyrics_lines"] = list(state.lyrics_lines)
        data["lyrics_timestamps"] = list(state.lyrics_timestamps)
    return data


def dict_to_track(data: dict) -> TrackInfo | None:
    video_id = data.get("video_id")
    if not video_id:
        return None
    return TrackInfo(
        video_id=video_id,
        title=data.get("title", "Unknown"),
        artist=data.get("artist", "Unknown"),
        duration=int(data.get("duration", 0)),
        thumbnail=data.get("thumbnail"),
        local_path=data.get("local_path"),
        stream_url=data.get("stream_url"),
        view_count=data.get("view_count"),
        is_favorite=int(data.get("is_favorite", False)),
    )
