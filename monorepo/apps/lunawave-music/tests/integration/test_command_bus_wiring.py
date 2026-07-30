"""
Module: tests.integration.test_command_bus_wiring

Purpose:
    RFC docs/rfc/perbaikan_arsitektur/07_command_bus_dependency_injection.yaml,
    task P07-T6: verify that exactly ONE CommandBus instance is alive across
    the whole wiring path -- the instance that engine.command_router.CommandRouter
    registers handlers on must be IDENTICAL (`is`, not `==`) to the instance
    server.handlers.context.get_command_bus(request) returns for a request
    against the app produced by server.app.create_app().

    This is the most critical regression test for the CommandBus DI
    migration: if it fails, there are silently two different CommandBus
    instances (commands registered on one, executed on the other), which
    surfaces at runtime as "No handler registered for command" even though
    CommandRouter appeared to register successfully at startup.

Responsibilities:
    - Wire a minimal-but-real CommandBus + CommandRouter + create_app() app,
      without needing real mpv/yt-dlp subprocesses (unlike the heavier
      fixtures in tests/integration/conftest.py), so this test never skips.

Depends on:
    - core.command_bus
    - engine.command_router
    - server.app
    - server.handlers.context

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.command_bus import CMD_VOLUME_UP, CommandBus
from engine.command_router import CommandRouter
from server.app import COMMAND_BUS, create_app
from server.handlers.context import get_command_bus


class _FakeRequest:
    """Minimal stand-in for aiohttp.web.Request -- get_command_bus() only
    ever does `request.app[COMMAND_BUS]`, so a bare `.app` attribute is
    sufficient and avoids spinning up a real HTTP server for this check."""

    def __init__(self, app):
        self.app = app


def test_single_command_bus_instance_across_router_and_accessor():
    """
    Skenario: CommandRouter meregister command_bus yang sama dengan yang
    di-DI ke create_app() -- get_command_bus(request) HARUS mengembalikan
    instance identik (is), bukan cuma instance yang setara.
    """
    command_bus = CommandBus()

    mock_playback_controller = MagicMock()
    mock_playback_controller.state = MagicMock()
    mock_volume_service = MagicMock()

    # CommandRouter registers every CMD_* handler onto this exact instance.
    router = CommandRouter(mock_playback_controller, mock_volume_service, command_bus=command_bus)
    assert router._command_bus is command_bus

    mock_ytdlp = MagicMock()
    mock_repos = MagicMock()
    mock_repos.conn = MagicMock()

    app = create_app(mock_playback_controller, mock_ytdlp, mock_repos, command_bus)

    # Identity check via the AppKey directly...
    assert app[COMMAND_BUS] is command_bus

    # ...and via the accessor every WS handler actually uses.
    fake_request = _FakeRequest(app)
    assert get_command_bus(fake_request) is command_bus

    # Functional proof, not just identity: a command registered by
    # CommandRouter on `command_bus` must be executable through the exact
    # same instance obtained via get_command_bus(request).
    assert CMD_VOLUME_UP in command_bus._handlers
    resolved_bus = get_command_bus(fake_request)
    assert CMD_VOLUME_UP in resolved_bus._handlers


@pytest.mark.asyncio
async def test_command_registered_by_router_executes_through_accessor_bus():
    """Kirim command lewat instance yang diperoleh dari get_command_bus() --
    handler yang didaftarkan CommandRouter di instance yang SAMA harus
    terpanggil. Ini regresi paling fatal kalau sampai ada 2 instance
    CommandBus berbeda yang tidak sinkron."""
    command_bus = CommandBus()

    mock_playback_controller = MagicMock()
    mock_playback_controller.state = MagicMock()
    mock_volume_service = MagicMock()
    mock_volume_service._on_volume_up = AsyncMock()

    CommandRouter(mock_playback_controller, mock_volume_service, command_bus=command_bus)

    mock_ytdlp = MagicMock()
    mock_repos = MagicMock()
    mock_repos.conn = MagicMock()
    app = create_app(mock_playback_controller, mock_ytdlp, mock_repos, command_bus)

    fake_request = _FakeRequest(app)
    resolved_bus = get_command_bus(fake_request)

    # If this were two different CommandBus instances, execute() would raise
    # "No handler registered for command" here instead of reaching the mock.
    await resolved_bus.execute(CMD_VOLUME_UP)

    mock_volume_service._on_volume_up.assert_called_once()
