"""
Module: lunawave_framework.core.lifecycle.dep_checker

Purpose:
    Utility to verify required system dependencies before launching the application.

Responsibilities:
    - Base class for domain-specific dependency checkers.
"""

import socket

import structlog

logger = structlog.get_logger(component="framework.lifecycle.dep_checker")


class DependencyChecker:
    def check_dependencies(self) -> tuple[list[str], bool]:
        """
        Returns:
            - list[str]: missing python packages
            - bool: whether required system binaries are present
        """
        return [], True

    def check_port(self, host: str, port: int) -> bool:
        """
        Returns True if the port is currently IN USE (occupied), False otherwise.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex((host, int(port))) == 0
        except Exception:
            return False
