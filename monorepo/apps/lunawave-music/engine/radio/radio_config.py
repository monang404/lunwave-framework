"""
Module: engine.radio.radio_config

Purpose:
    Common utilities and shared logic for the radio engine components.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.task_utils

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import asyncio

from core.task_utils import safe_create_task

# Konstanta Radio
MAX_TRACK_DURATION = 600  # 10 menit
TRACKS_PER_ARTIST_TARGET = 3
ARTISTS_PER_BATCH = 4
BANDIT_QUOTA = 3
EXPLORE_QUOTA = 1
ARTISTS_QUICK = 2
SEED_LIMIT = 2

# Bug #5 fix: naikkan semaphore dari 2 → 4 agar search lebih paralel
RADIO_SEARCH_SEM = asyncio.Semaphore(4)


def track_task(task_set: set, coro, name: str):
    task = safe_create_task(coro, name=name)
    task.add_done_callback(task_set.discard)
    task_set.add(task)
    if task.done():
        task_set.discard(task)
    return task
