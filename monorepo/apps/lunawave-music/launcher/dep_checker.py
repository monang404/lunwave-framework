"""
Module: launcher.dep_checker

Purpose:
    Utility to verify required system dependencies before launching the application.
"""

import importlib.util
import shutil
import subprocess
import socket

import structlog

from lunawave_framework.core.lifecycle.dep_checker import DependencyChecker as BaseChecker

logger = structlog.get_logger(component="launcher.dep_checker")


class DependencyChecker(BaseChecker):
    def check_dependencies(self) -> tuple[list[str], bool]:
        deps = {
            "yt-dlp": "yt_dlp",
            "aiosqlite": "aiosqlite",
            "aiohttp": "aiohttp",
            "syncedlyrics": "syncedlyrics",
            "structlog": "structlog",
            "prometheus_client": "prometheus_client",
            "opentelemetry": "opentelemetry",
        }
        missing = []
        for label, import_name in deps.items():
            try:
                spec = importlib.util.find_spec(import_name)
                if spec is None:
                    missing.append(label)
            except Exception:
                missing.append(label)

        mpv_ok = shutil.which("mpv") is not None
        return missing, mpv_ok

    def mpv_version(self) -> str | None:
        """
        Returns the first line of mpv --version output, or None if fail/not found.
        """
        try:
            if shutil.which("mpv") is None:
                return None
            res = subprocess.run(["mpv", "--version"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout:
                return res.stdout.splitlines()[0].strip()
        except Exception as e:
            logger.debug("mpv_version_check_failed", error=str(e))
        return None

