"""
Module: lunawave_framework.core.plugins

Purpose:
    Define the common contract for all background plugins and services.
"""

from typing import Protocol, runtime_checkable

@runtime_checkable
class BasePlugin(Protocol):
    async def start(self) -> None:
        """Start the plugin's background tasks and initialization."""
        ...

    async def cleanup(self) -> None:
        """Gracefully shutdown the plugin, cancel tasks, and free resources."""
        ...
