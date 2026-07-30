"""
Module: lunawave_framework.core.kernel.task_utils

Purpose:
    Wrap asyncio.create_task with centralized exception handling to prevent
    silent background-task crashes.

Responsibilities:
    - Catch and log any unhandled exceptions in background coroutines.
    - Invoke an optional on_error callback and handle CancelledError cleanly.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Thread-safe (safe to call from any asyncio context).
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from lunawave_framework.core.logging.log_categories import LC_LIFECYCLE

logger = structlog.get_logger(component="core.task_utils")


def safe_create_task(
    coro: Coroutine[Any, Any, Any],
    name: str = "",
    on_error: Callable[[Exception], Any] | None = None,
) -> asyncio.Task:
    """
    Membungkus pembuatan asyncio.Task dengan penanganan error terpusat
    sehingga exception tidak menjadi 'Task exception was never retrieved'
    yang menyebabkan silent crash.
    """

    coro_started = False

    async def _wrap_coro():
        nonlocal coro_started
        coro_started = True
        try:
            await coro
        except asyncio.CancelledError:
            # CancelledError adalah exception normal saat task di-cancel
            pass
        except Exception as e:
            logger.error(
                "background_task_failed",
                category=LC_LIFECYCLE,
                task_name=name,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            if on_error:
                try:
                    if asyncio.iscoroutinefunction(on_error):
                        await on_error(e)
                    else:
                        on_error(e)
                except Exception as inner_e:
                    logger.error(
                        "background_task_on_error_callback_failed",
                        category=LC_LIFECYCLE,
                        task_name=name,
                        error_type=type(inner_e).__name__,
                        error=str(inner_e),
                        exc_info=True,
                    )

    task = asyncio.create_task(_wrap_coro(), name=name)

    def _cleanup_coro(t):
        if not coro_started and hasattr(coro, "close"):
            coro.close()

    task.add_done_callback(_cleanup_coro)
    return task
