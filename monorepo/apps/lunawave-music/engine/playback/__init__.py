"""
Module: engine.playback

Purpose:
    Re-export PlaybackController as the public interface of the playback
    sub-package.

Responsibilities:
    - Expose PlaybackController at the engine.playback package level.

Depends on:
    - engine.playback.controller

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (re-export only).
"""

from engine.playback.controller import PlaybackController

__all__ = ["PlaybackController"]
