"""
Module: tests.unit.launcher.test_server_lifecycle

Purpose:
    Unit tests for ServerLifecycle — must pass without `tkinter` importable
    at all, proving the class is genuinely GUI-toolkit-free (T2.5).

Responsibilities:
    - Cover start/stop/restart, port-conflict handling, readiness polling,
      conflict killing, and the dependency check, all via injected
      on_log/on_ready/on_deps_checked callbacks (no widget involved).

Depends on:
    - lunawave_framework.core.lifecycle.server_lifecycle

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (threading.Thread is monkeypatched to run synchronously so
    each test is deterministic).
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch

from lunawave_framework.core.lifecycle.server_lifecycle import ServerLifecycle


def test_module_importable_without_tkinter():
    # Spawn a clean interpreter with tkinter import blocked and try to
    # import lunawave_framework.core.lifecycle.server_lifecycle in it. A shared-process check via
    # sys.modules would be order-dependent (another test file may have
    # already imported launcher.gui.app/tkinter earlier in the same pytest
    # session) and would false-fail; a subprocess gives a clean slate.
    script = (
        "import builtins, sys\n"
        "real_import = builtins.__import__\n"
        "def blocked(name, *a, **k):\n"
        "    if name == 'tkinter' or name.startswith('tkinter.'):\n"
        "        raise ImportError('tkinter blocked for this test')\n"
        "    return real_import(name, *a, **k)\n"
        "builtins.__import__ = blocked\n"
        "import lunawave_framework.core.lifecycle.server_lifecycle\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0, result.stderr


class _ImmediateThread:
    """Stand-in for threading.Thread that runs its target synchronously,
    so tests don't need to sleep/join to observe the result."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _lifecycle(monkeypatch):
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.threading.Thread", _ImmediateThread)
    logs = []
    lc = ServerLifecycle(
        "/fake/base",
        on_log=lambda msg, tag="", is_end=False: logs.append((msg, tag, is_end)),
        cleanup_processes=["mpv"]
    )
    return lc, logs


def test_is_running_false_without_process():
    lc = ServerLifecycle("/fake/base")
    assert lc.is_running() is False


def test_start_noop_when_already_running(monkeypatch):
    lc, _ = _lifecycle(monkeypatch)
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    lc.server_process = mock_proc

    with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.ServerProcess") as mock_sp:
        lc.start(8765)

    mock_sp.assert_not_called()


def test_start_creates_process_when_port_free(monkeypatch):
    lc, logs = _lifecycle(monkeypatch)
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.network.check_port_in_use", lambda port: False)

    mock_proc = MagicMock()
    mock_proc.process.pid = 4242
    mock_proc.is_running.return_value = False  # ends wait_for_ready's loop immediately

    with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.ServerProcess", return_value=mock_proc) as mock_sp:
        with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_by_name") as mock_kill_mpv:
            lc.start(8765)

    mock_kill_mpv.assert_called_once()
    mock_sp.assert_called_once_with("/fake/base", 8765, entry_point='main.py', on_log=lc.on_log)
    mock_proc.start.assert_called_once()
    assert lc.server_process is mock_proc
    assert any("Starting server on port 8765" in m for m, _, _ in logs)


def test_start_kills_conflicting_process_then_starts(monkeypatch):
    lc, logs = _lifecycle(monkeypatch)
    port_checks = iter([True, False])  # in-use, then free after kill
    monkeypatch.setattr(
        "lunawave_framework.core.lifecycle.server_lifecycle.network.check_port_in_use", lambda port: next(port_checks)
    )
    monkeypatch.setattr(
        "lunawave_framework.core.lifecycle.server_lifecycle.network.get_pid_occupying_port", lambda port: 999
    )
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.time.sleep", lambda s: None)

    mock_proc = MagicMock()
    mock_proc.process.pid = 1
    mock_proc.is_running.return_value = False

    with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.ServerProcess", return_value=mock_proc):
        with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_tree") as mock_kpt:
            with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_by_name"):
                lc.start(8765)

    mock_kpt.assert_called_once_with(999)
    assert lc.server_process is mock_proc


def test_start_gives_up_when_port_stays_in_use(monkeypatch):
    lc, logs = _lifecycle(monkeypatch)
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.network.check_port_in_use", lambda port: True)
    monkeypatch.setattr(
        "lunawave_framework.core.lifecycle.server_lifecycle.network.get_pid_occupying_port", lambda port: 999
    )
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.time.sleep", lambda s: None)

    with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_tree"):
        with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_by_name"):
            with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.ServerProcess") as mock_sp:
                lc.start(8765)

    mock_sp.assert_not_called()
    assert any("still in use after kill attempt" in m for m, _, _ in logs)


def test_wait_for_ready_calls_on_ready_on_success(monkeypatch):
    ready_ports = []
    lc = ServerLifecycle("/fake/base", on_ready=lambda port: ready_ports.append(port))
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    lc.server_process = mock_proc
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.network.check_port_in_use", lambda port: True)

    lc.wait_for_ready(8765)

    assert ready_ports == [8765]


def test_wait_for_ready_logs_error_when_process_dies(monkeypatch):
    logs = []
    lc = ServerLifecycle(
        "/fake/base", on_log=lambda msg, tag="", is_end=False: logs.append(msg)
    )
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = False
    lc.server_process = mock_proc

    lc.wait_for_ready(8765)

    assert any("terminated unexpectedly" in m for m in logs)


def test_stop_calls_server_process_stop(monkeypatch):
    lc, _ = _lifecycle(monkeypatch)
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    lc.server_process = mock_proc

    lc.stop()

    mock_proc.stop.assert_called_once()


def test_stop_noop_when_not_running(monkeypatch):
    lc, _ = _lifecycle(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.server_lifecycle.threading.Thread") as mock_thread:
        lc.stop()
    mock_thread.assert_not_called()


def test_restart_stops_then_starts(monkeypatch):
    lc, _ = _lifecycle(monkeypatch)
    calls = []
    monkeypatch.setattr(lc, "start", lambda port: calls.append(("start", port)))
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.time.sleep", lambda s: None)

    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    lc.server_process = mock_proc

    lc.restart(8765)

    mock_proc.stop.assert_called_once()
    assert calls == [("start", 8765)]


def test_kill_conflict_success(monkeypatch):
    lc, logs = _lifecycle(monkeypatch)
    monkeypatch.setattr(
        "lunawave_framework.core.lifecycle.server_lifecycle.network.get_pid_occupying_port", lambda port: 555
    )
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.network.check_port_in_use", lambda port: False)
    monkeypatch.setattr("lunawave_framework.core.lifecycle.server_lifecycle.time.sleep", lambda s: None)

    with patch("lunawave_framework.core.lifecycle.server_lifecycle.process.kill_process_tree") as mock_kpt:
        lc.kill_conflict(8765)

    mock_kpt.assert_called_once_with(555)
    assert any("successfully cleared" in m for m, _, _ in logs)


def test_kill_conflict_no_pid_found(monkeypatch):
    lc, logs = _lifecycle(monkeypatch)
    monkeypatch.setattr(
        "lunawave_framework.core.lifecycle.server_lifecycle.network.get_pid_occupying_port", lambda port: None
    )

    lc.kill_conflict(8765)

    assert any("Cannot identify PID" in m for m, _, _ in logs)


def test_run_dependency_check_reports_result(monkeypatch):
    lc, _ = _lifecycle(monkeypatch)
    results = []
    lc.on_deps_checked = lambda missing, mpv_ok: results.append((missing, mpv_ok))

    mock_checker = MagicMock()
    mock_checker.check_dependencies.return_value = (["aiohttp"], False)

    lc.dependency_checker = mock_checker
    lc.run_dependency_check()

    assert results == [(["aiohttp"], False)]
