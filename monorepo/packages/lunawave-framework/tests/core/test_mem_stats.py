"""tests/unit/core/test_mem_stats.py — mirrors core/mem_stats.py
Purpose:
    Pastikan get_rss_mb() fail-safe di semua platform (tidak pernah raise)
    dan mengembalikan angka masuk akal saat berhasil.

Subscribes to:
    None

Publishes:
    None
"""

import sys
from unittest.mock import mock_open, patch

from lunawave_framework.core.kernel.mem_stats import _get_rss_mb_proc, _get_rss_mb_windows, get_rss_mb


def test_get_rss_mb_never_raises_on_current_platform():
    # Tidak boleh melempar exception apa pun di platform tempat test jalan.
    result = get_rss_mb()
    assert result is None or isinstance(result, float)


def test_get_rss_mb_returns_positive_float_on_linux_proc():
    fake_status = "VmPeak:\t   20000 kB\nVmRSS:\t   12345 kB\nVmData:\t 1000 kB\n"
    with patch("builtins.open", mock_open(read_data=fake_status)):
        result = _get_rss_mb_proc()
    assert result == round(12345 / 1024, 2)


def test_get_rss_mb_proc_returns_none_when_file_missing():
    with patch("builtins.open", side_effect=FileNotFoundError()):
        result = _get_rss_mb_proc()
    assert result is None


def test_get_rss_mb_proc_returns_none_when_vmrss_absent():
    fake_status = "VmPeak:\t   20000 kB\n"
    with patch("builtins.open", mock_open(read_data=fake_status)):
        result = _get_rss_mb_proc()
    assert result is None


def test_get_rss_mb_proc_returns_none_on_malformed_line():
    fake_status = "VmRSS:\t   notanumber kB\n"
    with patch("builtins.open", mock_open(read_data=fake_status)):
        result = _get_rss_mb_proc()
    assert result is None


def test_get_rss_mb_dispatches_to_windows_impl_when_win32():
    with (
        patch.object(sys, "platform", "win32"),
        patch("lunawave_framework.core.kernel.mem_stats._get_rss_mb_windows", return_value=42.0) as mock_win,
    ):
        result = get_rss_mb()
    mock_win.assert_called_once()
    assert result == 42.0


def test_get_rss_mb_returns_none_on_unsupported_platform_or_error():
    # Patch both dispatch targets so that regardless of platform, get_rss_mb()
    # returns None when both internal helpers raise.
    with (
        patch("lunawave_framework.core.kernel.mem_stats._get_rss_mb_proc", side_effect=Exception("boom")),
        patch("lunawave_framework.core.kernel.mem_stats._get_rss_mb_windows", side_effect=Exception("boom")),
    ):
        result = get_rss_mb()
    assert result is None


def test_get_rss_mb_windows_returns_none_if_subprocess_fails():
    # Implementasi _get_rss_mb_windows menggunakan subprocess (wmic),
    # bukan ctypes. Verifikasi bahwa ia fail-safe ketika subprocess gagal
    # dengan alasan apa pun.
    with patch("subprocess.check_output", side_effect=Exception("wmic not found")):
        result = _get_rss_mb_windows()
    assert result is None
