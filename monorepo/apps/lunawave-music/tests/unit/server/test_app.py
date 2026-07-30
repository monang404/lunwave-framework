"""
Module: server.app

Purpose:
    Unit tests for server.app.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - server.app

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from server.app import (
    CONN,
    MANAGER,
    PLAYBACK_CONTROLLER,
    REPOS,
    SERVER_CLOCK,
    STATE,
    TRACKS,
    YTDLP,
    create_app,
    run_server,
)
from server.middleware.traffic import traffic_middleware


@pytest.fixture
def mock_playback_controller():
    controller = MagicMock()
    controller.state = MagicMock()
    return controller


@pytest.fixture
def mock_ytdlp():
    return MagicMock()


@pytest.fixture
def mock_repos():
    repos = MagicMock()
    repos.conn = MagicMock()
    return repos


def test_create_app_registers_routes_and_services(mock_playback_controller, mock_ytdlp, mock_repos):
    app = create_app(mock_playback_controller, mock_ytdlp, mock_repos, AsyncMock())

    assert isinstance(app, web.Application)

    # Check that services are in app
    assert app[PLAYBACK_CONTROLLER] == mock_playback_controller
    assert app[STATE] == mock_playback_controller.state
    assert app[YTDLP] == mock_ytdlp
    assert app[REPOS] == mock_repos
    assert app[CONN] == mock_repos.conn
    assert app[TRACKS] == mock_repos.tracks
    assert MANAGER in app
    # ADR-0010 O3.2: ServerClock wired via AppKey, traffic middleware registered.
    assert SERVER_CLOCK in app
    assert traffic_middleware in app.middlewares

    # Check that routes are registered
    routes = [
        route.resource.canonical
        for route in app.router.routes()
        if hasattr(route.resource, "canonical")
    ]

    assert "/" in routes
    assert "/admin" in routes
    assert "/ws" in routes
    assert "/api/stream/{video_id}" in routes
    assert "/api/setup-required" in routes
    assert "/health" in routes
    assert "/metrics" in routes


@pytest.mark.asyncio
async def test_run_server_starts_and_cleans_up():
    app = web.Application()

    with (
        patch("server.app.web.AppRunner") as MockAppRunner,
        patch("server.app.web.TCPSite") as MockTCPSite,
    ):
        mock_runner = MockAppRunner.return_value
        mock_runner.setup = AsyncMock()
        mock_runner.cleanup = AsyncMock()

        mock_site = MockTCPSite.return_value
        mock_site.start = AsyncMock()

        # We need to run run_server in a task and then cancel it to simulate shutdown
        task = asyncio.create_task(run_server(app, "127.0.0.1", 8080))

        # Yield to let run_server execute up to the sleep
        await asyncio.sleep(0.01)

        MockAppRunner.assert_called_once_with(app, access_log=None)
        mock_runner.setup.assert_called_once()
        MockTCPSite.assert_called_once_with(mock_runner, "127.0.0.1", 8080)
        mock_site.start.assert_called_once()

        # Cancel the task
        task.cancel()

        # Wait for it to finish cancelling
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Ensure cleanup was called
        mock_runner.cleanup.assert_called_once()
