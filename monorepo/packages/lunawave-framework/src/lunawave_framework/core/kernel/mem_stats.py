"""
Module: lunawave_framework.core.kernel.mem_stats

Purpose:
    Baca penggunaan RAM (RSS) proses saat ini secara cross-platform tanpa
    dependency pip baru (tidak pakai psutil — lihat ADR-0010).

Responsibilities:
    - Linux/Termux: parse VmRSS dari /proc/self/status.
    - Windows: baca lewat ctypes + psapi.GetProcessMemoryInfo (API OS bawaan).
    - Platform lain / kegagalan apa pun: kembalikan None, tidak pernah raise.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Thread-safe (read-only, tidak ada shared state).
"""

import subprocess
import sys


def get_cpu_percent() -> float | None:
    """
    Mengembalikan penggunaan CPU secara cross-platform.
    Untuk Windows menggunakan wmic, untuk Linux akan None.
    """
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "loadpercentage"], shell=False, text=True
            )
            lines = out.strip().split("\n")
            if len(lines) > 1:
                return float(lines[-1].strip())
        except Exception:
            pass
    return None


def get_rss_mb() -> float | None:
    """
    Mengembalikan RSS (Resident Set Size) proses saat ini dalam MB.

    Selalu fail-safe: kalau platform tidak didukung atau pembacaan gagal
    dengan alasan apa pun, kembalikan None (bukan exception).
    """
    try:
        if sys.platform == "win32":
            return _get_rss_mb_windows()
        return _get_rss_mb_proc()
    except Exception:
        return None


def _get_rss_mb_proc() -> float | None:
    """Baca VmRSS dari /proc/self/status (Linux, termasuk Termux/Android)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # Format: "VmRSS:	   12345 kB"
                    if len(parts) >= 2:
                        kb = float(parts[1])
                        return round(kb / 1024, 2)
        return None
    except Exception:
        return None


def _get_rss_mb_windows() -> float | None:
    """Baca RSS via wmic process get WorkingSetSize (Windows, no install)."""
    try:
        import os
        import subprocess

        out = subprocess.check_output(
            [
                "wmic",
                "process",
                "where",
                f"processid={os.getpid()}",
                "get",
                "WorkingSetSize",
            ],
            shell=False,
            text=True,
        )
        lines = out.strip().split("\n")
        if len(lines) > 1:
            bytes_val = float(lines[-1].strip())
            return round(bytes_val / (1024 * 1024), 2)
    except Exception:
        pass
    return None
