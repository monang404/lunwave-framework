import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.loudness.service import LoudnessService, _is_charging_or_unknown


class TestIsChargingOrUnknown:
    @patch("engine.loudness.service.shutil.which", return_value=None)
    def test_binary_missing_fail_open(self, mock_which):
        assert _is_charging_or_unknown() is True

    @patch("engine.loudness.service.shutil.which", return_value="/usr/bin/termux-battery-status")
    @patch("engine.loudness.service.subprocess.run")
    def test_parse_failure_fail_open(self, mock_run, mock_which):
        mock_result = MagicMock()
        mock_result.stdout = "not json"
        mock_run.return_value = mock_result
        assert _is_charging_or_unknown() is True

    @patch("engine.loudness.service.shutil.which", return_value="/usr/bin/termux-battery-status")
    @patch("engine.loudness.service.subprocess.run")
    def test_discharging_returns_false(self, mock_run, mock_which):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"status": "DISCHARGING", "plugged": "UNPLUGGED"})
        mock_run.return_value = mock_result
        assert _is_charging_or_unknown() is False

    @patch("engine.loudness.service.shutil.which", return_value="/usr/bin/termux-battery-status")
    @patch("engine.loudness.service.subprocess.run")
    def test_charging_returns_true(self, mock_run, mock_which):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"status": "CHARGING", "plugged": "PLUGGED_USB"})
        mock_run.return_value = mock_result
        assert _is_charging_or_unknown() is True

    @patch("engine.loudness.service.shutil.which", return_value="/usr/bin/termux-battery-status")
    @patch("engine.loudness.service.subprocess.run")
    def test_unknown_field_fail_open(self, mock_run, mock_which):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"unexpected_field": True})
        mock_run.return_value = mock_result
        assert _is_charging_or_unknown() is True


@pytest.mark.asyncio
class TestAnalyzeAndStoreChargingGate:
    async def test_skips_when_not_charging(self):
        db = MagicMock()
        db.get_track = AsyncMock(return_value=None)
        service = LoudnessService(db)
        service.analyzer.measure_sync = MagicMock()

        with patch("engine.loudness.service._is_charging_or_unknown", return_value=False):
            await service.analyze_and_store("vid1", "uri1")

        service.analyzer.measure_sync.assert_not_called()

    async def test_proceeds_when_charging(self):
        db = MagicMock()
        db.get_track = AsyncMock(return_value=None)
        db.set_loudness = AsyncMock()
        service = LoudnessService(db)
        measurement = MagicMock(lufs=-14.0, true_peak=-1.0)
        service.analyzer.measure_sync = MagicMock(return_value=measurement)

        with patch("engine.loudness.service._is_charging_or_unknown", return_value=True):
            await service.analyze_and_store("vid1", "uri1")

        service.analyzer.measure_sync.assert_called_once()
        db.set_loudness.assert_awaited_once_with("vid1", -14.0, -1.0)
