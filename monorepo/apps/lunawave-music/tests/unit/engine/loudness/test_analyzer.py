import subprocess
from unittest.mock import MagicMock, patch

from engine.loudness.analyzer import LoudnessAnalyzer, LoudnessMeasurement


@patch("engine.loudness.analyzer.subprocess.run")
def test_measure_sync_success(mock_run):
    analyzer = LoudnessAnalyzer()

    mock_result = MagicMock()
    mock_result.stderr = """
    [Parsed_loudnorm_0 @ 0x5555555]
    {
        "input_i" : "-16.5",
        "input_tp" : "-2.0",
        "input_lra" : "4.0",
        "input_thresh" : "-27.0",
        "output_i" : "-14.0"
    }
    """
    mock_run.return_value = mock_result

    result = analyzer.measure_sync("dummy_uri")
    assert isinstance(result, LoudnessMeasurement)
    assert result.lufs == -16.5
    assert result.true_peak == -2.0
    assert mock_run.called


@patch("engine.loudness.analyzer.subprocess.run")
def test_measure_sync_timeout(mock_run):
    analyzer = LoudnessAnalyzer()
    mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)

    result = analyzer.measure_sync("dummy_uri")
    assert result is None


@patch("engine.loudness.analyzer.subprocess.run")
def test_measure_sync_no_json(mock_run):
    analyzer = LoudnessAnalyzer()
    mock_result = MagicMock()
    mock_result.stderr = "No json here"
    mock_run.return_value = mock_result

    result = analyzer.measure_sync("dummy_uri")
    assert result is None


@patch("engine.loudness.analyzer.subprocess.run")
def test_measure_sync_malformed_json(mock_run):
    analyzer = LoudnessAnalyzer()
    mock_result = MagicMock()
    mock_result.stderr = """
    {
        "input_i": "not a float"
    }
    """
    mock_run.return_value = mock_result

    result = analyzer.measure_sync("dummy_uri")
    assert result is None
