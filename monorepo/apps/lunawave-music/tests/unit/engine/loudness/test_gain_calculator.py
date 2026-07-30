from engine.loudness.gain_calculator import build_af_filter, compute_gain_db


def test_compute_gain_db_within_limits():
    gain = compute_gain_db(
        measured_lufs=-20.0, target_lufs=-14.0, max_boost_db=10.0, max_cut_db=15.0
    )
    assert gain == 6.0


def test_compute_gain_db_exceeds_max():
    gain = compute_gain_db(measured_lufs=-25.0, target_lufs=-14.0, max_boost_db=5.0)
    assert gain == 5.0


def test_compute_gain_db_exceeds_min():
    gain = compute_gain_db(measured_lufs=-8.0, target_lufs=-14.0, max_boost_db=10.0, max_cut_db=2.0)
    assert gain == -2.0


def test_compute_gain_db_zero_when_none():
    gain = compute_gain_db(None, target_lufs=-14.0)
    assert gain == 0.0


def test_build_af_filter():
    assert build_af_filter(6.0) == "lavfi=[volume=6.00dB,alimiter=limit=-1dB:level=disabled]"
    assert build_af_filter(-2.5) == "lavfi=[volume=-2.50dB,alimiter=limit=-1dB:level=disabled]"
    assert build_af_filter(0.0) == "lavfi=[volume=0.00dB,alimiter=limit=-1dB:level=disabled]"


def test_compute_gain_db_true_peak_clamp():
    """True peak clamp prevents gain that would cause the track to clip."""
    # Track is quiet (-22 LUFS), would normally get +8 dB boost,
    # but true peak is already -2 dBTP — so max safe gain = -1 - (-2) = +1 dB.
    gain = compute_gain_db(measured_lufs=-22.0, true_peak_dbtp=-2.0)
    assert gain == 1.0  # Not +8, clamped by true peak headroom


def test_compute_gain_db_no_true_peak_uses_static_clamp():
    """Without true_peak info, only static clamp applies (backward compat)."""
    gain = compute_gain_db(measured_lufs=-22.0, true_peak_dbtp=None)
    assert gain == 8.0  # MAX_BOOST_DB


def test_compute_gain_db_true_peak_safe_no_clamp():
    """If true peak is low enough, true-peak clamp doesn't restrict anything."""
    # Track is quiet (-20 LUFS), wants +6 dB; true peak is -10 dBTP.
    # Max safe gain = -1 - (-10) = +9 dB — no restriction from true peak.
    gain = compute_gain_db(measured_lufs=-20.0, true_peak_dbtp=-10.0, max_boost_db=10.0)
    assert gain == 6.0
