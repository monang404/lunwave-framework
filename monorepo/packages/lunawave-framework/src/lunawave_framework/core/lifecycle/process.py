"""
Module: lunawave_framework.core.lifecycle.process

Purpose:
    Manage OS-level lifecycle for server processes.

Responsibilities:
    - Kill process trees cross-platform (SIGKILL / taskkill).
    - Start a python entrypoint as a subprocess and pipe its stdout.

Depends on:
    None
"""

import os
import subprocess
import sys
import threading
from typing import Callable

import structlog

logger = structlog.get_logger(component="framework.lifecycle.process")


def kill_process_tree(pid: int):
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("kill_process_tree_failed", platform="win32", pid=pid, error=str(e))
    else:
        try:
            import signal

            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                import signal

                os.kill(pid, signal.SIGKILL)
            except Exception as e:
                logger.debug("kill_process_tree_failed", platform="unix", pid=pid, error=str(e))


def kill_process_by_name(process_name: str):
    if sys.platform == "win32":
        process_exe = f"{process_name}.exe" if not process_name.endswith(".exe") else process_name
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", process_exe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("kill_process_by_name_failed", platform="win32", error=str(e))
    else:
        try:
            subprocess.run(
                ["pkill", "-f", process_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.debug("kill_process_by_name_failed", platform="unix", error=str(e))


class ServerProcess:
    def __init__(self, cwd: str, port: int, entry_point: str = "main.py", on_log: Callable | None = None):
        self.cwd = cwd
        self.port = port
        self.entry_point = entry_point
        self.process = None
        self.on_log = on_log

    def start(self) -> subprocess.Popen:
        env = os.environ.copy()
        env["LUNAWAVE_HOST"] = "0.0.0.0"
        env["LUNAWAVE_PORT"] = str(self.port)
        env["YTGUI_HOST"] = "0.0.0.0"
        env["YTGUI_PORT"] = str(self.port)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["preexec_fn"] = os.setsid

        python_exe = sys.executable
        self.process = subprocess.Popen(  # type: ignore
            [python_exe, self.entry_point],
            cwd=self.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            errors="replace",
            encoding="utf-8",
            **kwargs,
        )

        if self.on_log:
            threading.Thread(target=self._pipe_stdout, daemon=True).start()

        return self.process  # type: ignore

    def _pipe_stdout(self):
        try:
            for line in self.process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if self.on_log:
                    self.on_log(line)
        except Exception as e:
            logger.debug("pipe_stdout_failed", error=str(e))
        if self.on_log:
            self.on_log("── process ended ──", is_end=True)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self, wait_timeout=6):
        if not self.is_running():
            return
        kill_process_tree(self.process.pid)
        try:
            self.process.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
            except Exception as e:
                logger.debug("force_kill_failed", pid=self.process.pid, error=str(e))
