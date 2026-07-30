"""
Module: lunawave_framework.core.lifecycle.server_lifecycle

Purpose:
    Own the server process lifecycle (start/stop/restart, port
    conflict resolution, readiness polling, dependency checks) independent
    of any GUI toolkit.

Responsibilities:
    - Start/stop/restart the backend server subprocess.
    - Detect and resolve TCP port conflicts before starting.
    - Poll for the server becoming reachable after start.
    - Run the environment dependency check.
    - Report everything back to callers via plain callbacks.
"""

import threading
import time
from typing import Callable

from lunawave_framework.core.lifecycle import network, process


class ServerLifecycle:
    def __init__(
        self,
        base_dir,
        on_log=None,
        on_ready=None,
        on_deps_checked=None,
        on_starting=None,
        entry_point="main.py",
        cleanup_processes=None,
        dependency_checker=None,
    ):
        self.base_dir = base_dir
        self.entry_point = entry_point
        self.cleanup_processes = cleanup_processes or []
        self.dependency_checker = dependency_checker
        self.server_process: process.ServerProcess | None = None

        self.on_log = on_log or (lambda msg, tag="", is_end=False: None)
        self.on_ready = on_ready or (lambda port: None)
        self.on_deps_checked = on_deps_checked or (lambda missing, mpv_ok: None)
        self.on_starting = on_starting or (lambda: None)

    # ── Status ────────────────────────────────────────────
    def is_running(self) -> bool:
        return self.server_process is not None and self.server_process.is_running()

    # ── Dependency Checker ──────────────────────────────────
    def run_dependency_check(self):
        def _thread_fn():
            if self.dependency_checker:
                missing, mpv_ok = self.dependency_checker.check_dependencies()
                self.on_deps_checked(missing, mpv_ok)
            else:
                self.on_deps_checked([], True)

        threading.Thread(target=_thread_fn, daemon=True).start()

    # ── Start / stop / restart ───────────────────────────────
    def start(self, port: int):
        if self.is_running():
            return

        # Ensure clean slate for processes
        for p in self.cleanup_processes:
            process.kill_process_by_name(p)

        if network.check_port_in_use(port):
            self.on_log(
                f"Port {port} is in use. Attempting to kill conflicting process...", "accent"
            )
            pid = network.get_pid_occupying_port(port)
            if pid:
                process.kill_process_tree(pid)
                time.sleep(1)
            if network.check_port_in_use(port):
                self.on_log(f"Cannot start: Port {port} is still in use after kill attempt.", "err")
                return

        self.on_starting()
        self.on_log(f"Starting server on port {port}...", "accent")

        self.server_process = process.ServerProcess(
            str(self.base_dir), port, entry_point=self.entry_point, on_log=self.on_log
        )
        try:
            self.server_process.start()
            pid_info = (
                f" — PID {self.server_process.process.pid}"
                if self.server_process.process is not None
                else ""
            )
            self.on_log(f"Server process created{pid_info}", "ok")
            threading.Thread(target=self.wait_for_ready, args=(port,), daemon=True).start()
        except Exception as e:
            self.on_log(f"Failed to start: {e}", "err")

    def wait_for_ready(self, port: int):
        self.on_log("Waiting for server to bind and listen...", "dim")
        start_time = time.time()
        success = False
        while time.time() - start_time < 120:  # wait up to 120 seconds (2 minutes)
            if not self.is_running():
                break
            if network.check_port_in_use(port):
                success = True
                break
            time.sleep(0.5)

        if success:
            self.on_log(f"Server is fully active and listening on port {port}!", "ok")
            self.on_ready(port)
        else:
            if not self.is_running():
                self.on_log("Server process terminated unexpectedly.", "err")
            else:
                self.on_log("Server failed to respond on port in time (120s timeout).", "err")

    def stop(self):
        if not self.is_running():
            return
        self.on_log("Stopping server...", "accent")

        def _do():
            try:
                if self.server_process:
                    self.server_process.stop()
            except Exception as e:
                self.on_log(f"Force killed: {e}", "err")

        threading.Thread(target=_do, daemon=True).start()

    def restart(self, port: int):
        self.on_log("Restarting...", "accent")

        def _do():
            if self.is_running():
                if self.server_process:
                    self.server_process.stop()
            time.sleep(0.8)
            self.start(port)

        threading.Thread(target=_do, daemon=True).start()

    def kill_conflict(self, port: int):
        pid = network.get_pid_occupying_port(port)

        if pid:
            self.on_log(f"Killing process tree using port {port} (PID {pid})...", "accent")
            process.kill_process_tree(pid)
            time.sleep(0.8)
            if not network.check_port_in_use(port):
                self.on_log(f"Port {port} successfully cleared!", "ok")
            else:
                self.on_log(f"Failed to clear port {port}.", "err")
        else:
            self.on_log(f"Cannot identify PID for port {port}.", "err")

