"""
Module: lunawave_framework.core.bootstrap.lifecycle

Purpose:
    Provide a generic manager for background tasks, startup tasks, and periodic maintenance jobs.
    Handles graceful shutdown, task cancellation, and error reporting.
"""

import asyncio
from typing import Callable, Coroutine, List

import structlog

logger = structlog.get_logger(component="framework.bootstrap.lifecycle")


class LifecycleManager:
    def __init__(self):
        self.tasks: List[asyncio.Task] = []

    def schedule_task(self, coro: Coroutine, name: str) -> asyncio.Task:
        """Schedule a fire-and-forget or long-running background task."""
        from lunawave_framework.core.kernel.task_utils import safe_create_task

        task = safe_create_task(coro, name=name)
        self.tasks.append(task)
        return task

    def schedule_periodic_job(self, coro_func: Callable[[], Coroutine], interval_seconds: int, name: str):
        """Schedule a job to run repeatedly on an interval."""
        async def _loop():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await coro_func()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(
                        "periodic_job_failed",
                        job_name=name,
                        error_type=type(e).__name__,
                        error=str(e),
                    )

        return self.schedule_task(_loop(), name=f"periodic_{name}")

    async def shutdown(self):
        """Cancel all registered tasks and wait for them to finish."""
        import traceback

        total_errors = 0
        for t in self.tasks:
            if t.done() and not t.cancelled():
                exc = t.exception()
                if exc:
                    total_errors += 1
                    logger.error(
                        "background_task_crashed",
                        task_name=t.get_name(),
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    print(f"\n[FATAL ERROR] App crashed due to task failure: {exc}")
                    traceback.print_exception(type(exc), exc, exc.__traceback__)

        for t in self.tasks:
            t.cancel()
        
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        return total_errors
