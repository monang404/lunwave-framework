"""
Module: engine.playback.crossfade

Purpose:
    Crossfade helpers untuk transisi halus antar track via MPV volume ramping.

Responsibilities:
    - Fade-in volume saat track baru mulai (apply_crossfade_in)
    - Fade-out volume saat track mendekati akhir (apply_crossfade_out)

Depends on:
    - core.state
    - core.ports (AudioPlayerPort via mpv instance)

Subscribes to:
    None (dipanggil langsung oleh mode_ops)

Publishes:
    None

Thread Safety:
    Async-safe; tidak ada shared mutable state.
"""

import asyncio

from core.state import AppState, PlayerStatus


async def apply_crossfade_in(mpv, state: AppState):
    """
    Jika terinterupsi (status berubah di tengah proses), volume MPV dikembalikan
    ke state.volume secara eksplisit, supaya pemutaran berikutnya tidak mewarisi
    volume fade parsial yang salah.
    """
    await mpv.set_volume(0)
    steps = 25
    interrupted = False
    for i in range(1, steps + 1):
        await asyncio.sleep(0.2)
        if state.status not in (PlayerStatus.PLAYING, PlayerStatus.LOADING):
            interrupted = True
            break
        vol = int(state.volume * (i / steps))
        await mpv.set_volume(vol)
    if interrupted:
        await mpv.set_volume(state.volume)


async def apply_crossfade_out(mpv, state: AppState):
    """
    Jika terinterupsi (status berubah di tengah proses), volume MPV dikembalikan
    ke state.volume secara eksplisit, supaya pemutaran berikutnya tidak mewarisi
    volume fade parsial yang salah.
    """
    steps = 25
    start_vol = state.volume
    interrupted = False
    for i in range(steps, 0, -1):
        await asyncio.sleep(0.2)
        if state.status not in (PlayerStatus.PLAYING, PlayerStatus.LOADING):
            interrupted = True
            break
        vol = int(start_vol * (i / steps))
        await mpv.set_volume(vol)
    if interrupted:
        await mpv.set_volume(state.volume)
    elif state.status in (PlayerStatus.PLAYING, PlayerStatus.LOADING):
        await mpv.set_volume(0)
