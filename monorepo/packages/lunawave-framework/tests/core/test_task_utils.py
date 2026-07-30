"""tests/unit/core/test_task_utils.py — mirrors core/task_utils.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import asyncio

from lunawave_framework.core.kernel.task_utils import safe_create_task


async def test_safe_create_task_runs_coroutine_to_completion():
    result = {}

    async def work():
        result["ran"] = True

    task = safe_create_task(work(), name="t1")
    await task
    assert result["ran"] is True


async def test_safe_create_task_swallows_exception_without_crashing_loop():
    async def boom():
        raise ValueError("kaboom")

    task = safe_create_task(boom(), name="t2")
    # Should not raise, and should not leave the exception "unretrieved".
    await task
    assert task.exception() is None


async def test_safe_create_task_invokes_on_error_callback_sync():
    captured = []

    def on_error(exc):
        captured.append(exc)

    async def boom():
        raise RuntimeError("bad thing")

    task = safe_create_task(boom(), name="t3", on_error=on_error)
    await task
    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)


async def test_safe_create_task_invokes_on_error_callback_async():
    captured = []

    async def on_error(exc):
        captured.append(exc)

    async def boom():
        raise RuntimeError("bad thing")

    task = safe_create_task(boom(), name="t4", on_error=on_error)
    await task
    assert len(captured) == 1


async def test_safe_create_task_on_error_callback_failure_does_not_propagate():
    def broken_on_error(exc):
        raise KeyError("callback itself is broken")

    async def boom():
        raise RuntimeError("original")

    task = safe_create_task(boom(), name="t5", on_error=broken_on_error)
    # Must not raise even though on_error itself raises.
    await task


async def test_safe_create_task_handles_cancellation_quietly():
    started = asyncio.Event()

    async def long_running():
        started.set()
        await asyncio.sleep(10)

    task = safe_create_task(long_running(), name="t6")
    await started.wait()
    task.cancel()
    # Should complete without raising CancelledError out of the wrapper.
    await asyncio.wait_for(task, timeout=1)
    assert task.cancelled() is False  # wrapper swallows it internally


async def test_safe_create_task_returns_an_asyncio_task_with_name():
    async def noop():
        pass

    task = safe_create_task(noop(), name="named-task")
    assert isinstance(task, asyncio.Task)
    assert task.get_name() == "named-task"
    await task
