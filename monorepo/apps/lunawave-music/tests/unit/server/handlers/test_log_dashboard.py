"""
Module: tests.unit.server.handlers.test_log_dashboard

Purpose:
    Unit tests for server.handlers.log_dashboard.

Responsibility:
    - Test get_logs_tail filtering and JSON response.
    - Test get_logs_stats format.
    - Test access protection for both tail and stats.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web

from server.handlers.log_dashboard import get_logs_stats, get_logs_tail, serve_log_dashboard


@pytest.fixture
def mock_request():
    req = MagicMock()
    req.remote = "127.0.0.1"
    req.headers = {}
    req.query = {}
    req.app = {}
    return req


@pytest.mark.asyncio
async def test_serve_log_dashboard_returns_file_response(mock_request):
    with patch("server.handlers.log_dashboard.STATIC_DIR", Path("/fake/static")):
        with patch("server.handlers.log_dashboard.web.FileResponse") as mock_file_response:
            mock_resp = MagicMock()
            mock_resp.headers = {}
            mock_file_response.return_value = mock_resp

            resp = await serve_log_dashboard(mock_request)

            mock_file_response.assert_called_once_with(
                Path("/fake/static/pages/admin-logs/admin-logs.html")
            )
            assert resp.headers["Cache-Control"] == "no-cache"


@pytest.mark.asyncio
async def test_get_logs_tail_returns_json(mock_request):
    mock_request.query = {"limit": "50", "category": "LC_APP", "level": "INFO", "q": "test"}
    with patch("server.handlers.log_dashboard.tail") as mock_tail:
        mock_tail.return_value = [{"msg": "test log"}]

        resp = await get_logs_tail(mock_request)

        mock_tail.assert_called_once_with(limit=50, category="LC_APP", level="INFO", query="test")
        import json

        body = json.loads(resp.body)
        assert body == {"logs": [{"msg": "test log"}]}


@pytest.mark.asyncio
async def test_get_logs_stats_returns_json(mock_request):
    mock_request.query = {"window": "7200"}
    with patch("server.handlers.log_dashboard.stats") as mock_stats:
        mock_stats.return_value = {"LC_APP": {"INFO": 5}}
        with patch("server.handlers.log_dashboard.get_counter_value") as mock_get_counter:
            mock_get_counter.side_effect = [100.0, 50.0]

            resp = await get_logs_stats(mock_request)

            mock_stats.assert_called_once_with(window_seconds=7200)
            import json

            import core.log_categories

            body = json.loads(resp.body)
            assert body == {
                "log_stats": {"LC_APP": {"INFO": 5}},
                "metrics": {"http_requests_total": 100.0, "command_count": 50.0},
                # mock_request tidak menyediakan app[REPOS]/app[MANAGER] dkk
                # (AppKey), jadi blok try di get_logs_stats() gagal di awal
                # dan jatuh ke default kosong -- ini bukan bug endpoint,
                # cuma fixture mock_request yang tidak lengkap. Nilai default
                # ini yang sebelumnya tidak diekspektasikan test (stale sejak
                # system_stats/active_users ditambahkan).
                "system_stats": {},
                "active_users": [],
                "available_categories": list(core.log_categories.ALL_CATEGORIES),
            }


@pytest.mark.asyncio
async def test_log_dashboard_forbids_external_without_token(mock_request):
    mock_request.remote = "192.168.1.5"
    mock_request.headers = {}

    resp1 = await serve_log_dashboard(mock_request)
    assert isinstance(resp1, web.HTTPForbidden)

    resp2 = await get_logs_tail(mock_request)
    assert isinstance(resp2, web.HTTPForbidden)

    resp3 = await get_logs_stats(mock_request)
    assert isinstance(resp3, web.HTTPForbidden)


@pytest.mark.asyncio
async def test_log_dashboard_allows_external_with_valid_token(mock_request, monkeypatch):
    monkeypatch.setenv("LUNAWAVE_METRICS_TOKEN", "s3cr3t-token")
    mock_request.remote = "192.168.1.5"
    mock_request.headers = {"X-Metrics-Token": "s3cr3t-token"}

    with patch("server.handlers.log_dashboard.web.FileResponse"):
        resp = await serve_log_dashboard(mock_request)
        assert not isinstance(resp, web.HTTPForbidden)
