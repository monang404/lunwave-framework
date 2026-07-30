"""
Module: engine.playback.play_ops

Purpose:
    Operations class handling the core logic for playing a track.
    Extracted from PlaybackController to maintain a thin orchestrator.

Responsibilities:
    - Managing track loading and transitions.
    - Applying loudness normalization and routing logic.
    - Setting up the correct initial playback state (paused/seeked).

Subscribes to:
    None

Publishes:
    TrackStartedEvent, LogMessageEvent
"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from core.events import LogMessageEvent, TrackStartedEvent
from core.exceptions import BotCheckError, RateLimitedError, VideoUnavailableError
from core.state import AudioOutput, PlayerStatus, TrackInfo
from core.task_utils import safe_create_task

if TYPE_CHECKING:
    from engine.playback.controller import PlaybackController

logger = structlog.get_logger(component="playback.play_ops")


class PlayOps:
    def __init__(self, controller: "PlaybackController"):
        self.controller = controller

    async def play_track(
        self, track: TrackInfo, start_position: float = 0.0, start_paused: bool = False
    ):
        async with self.controller._play_lock:
            if self.controller.state.current_track:
                self.controller.state.history.append(self.controller.state.current_track)
            self.controller.state.current_track = track
            self.controller.state.status = PlayerStatus.LOADING
            self.controller.state.position = start_position
            self.controller.state.duration = float(track.duration)
            self.controller.state.lyrics_lines = []
            self.controller.state.lyrics_index = 0
            self.controller._crossfade_out_triggered = False
            if self.controller._fade_out_task and not self.controller._fade_out_task.done():
                self.controller._fade_out_task.cancel()
            try:
                self.controller._loading = True
                self.controller._last_play_start_ts = asyncio.get_event_loop().time()
                loaded = await self.controller.track_loader.load_track(track)
                uri = loaded.uri
                await self.controller.mpv.play(uri)
                await asyncio.sleep(0.15)

                await self._apply_loudness_and_routing(loaded)

                await self._apply_start_playback_state(start_paused, start_position)
                await self._finalize_play_track_success(track, start_paused)
            except VideoUnavailableError as e:
                self.controller._loading = False
                await self.controller._failure_ops.handle_video_unavailable(track, e)
            except (BotCheckError, RateLimitedError) as e:
                self.controller._loading = False
                await self.controller._failure_ops.handle_bot_check_or_rate_limited(track, e)
            except Exception as e:
                self.controller._loading = False
                await self.controller._failure_ops.handle_generic_error(track, e)

    async def _apply_start_playback_state(self, start_paused: bool, start_position: float):
        if start_paused:
            await self.controller.mpv.pause()
        else:
            await self.controller.mpv.resume()

        if start_position > 0:
            await self.controller.mpv.seek(start_position)

    async def _finalize_play_track_success(self, track: TrackInfo, start_paused: bool):
        self.controller.state.status = PlayerStatus.PAUSED if start_paused else PlayerStatus.PLAYING
        self.controller._breaker.record_success()
        self.controller._loading = False
        await self.controller.bus.publish(TrackStartedEvent(track=track))

        if self.controller.state.duration == 0:
            safe_create_task(self._poll_duration(track), name="poll_duration")

    async def _apply_loudness_and_routing(self, loaded):
        from engine.loudness.gain_calculator import build_af_filter

        self.controller.state.current_track_gain_db = loaded.gain_db

        if getattr(self.controller.state, "loudness_normalization_enabled", False):
            await self.controller.mpv.set_af(build_af_filter(loaded.gain_db))
        else:
            await self.controller.mpv.set_af(build_af_filter(0.0))

        if (
            getattr(self.controller.state, "audio_output", AudioOutput.DEVICE)
            == AudioOutput.BROWSER
        ):
            await self.controller.mpv.set_volume(0)
            await self.controller.bus.publish(
                LogMessageEvent(message="Audio output is browser, mpv silent (volume=0).")
            )
        else:
            if getattr(self.controller.state, "crossfade_enabled", False):
                from engine.playback.crossfade import apply_crossfade_in

                if self.controller._fade_task and not self.controller._fade_task.done():
                    self.controller._fade_task.cancel()
                self.controller._fade_task = safe_create_task(
                    apply_crossfade_in(self.controller.mpv, self.controller.state), name="fade_in"
                )
            else:
                await self.controller.mpv.set_volume(self.controller.state.volume)

    async def _poll_duration(self, track: TrackInfo):
        from engine.playback.track_ended_ops import poll_duration

        await poll_duration(
            self.controller.state,
            self.controller.mpv,
            self.controller.resolver,
            self.controller.bus,
            track,
        )
