"""
Module: engine.loudness.analyzer

Purpose:
    Ukur integrated loudness (LUFS) sebuah track via satu-pass ffmpeg
    `loudnorm` filter mode measure-only (tidak re-encode, tidak menyimpan file
    baru).

Responsibilities:
    - Jalankan ffmpeg sebagai subprocess di thread executor.
    - Parse output JSON dari stderr ffmpeg untuk ambil `input_i`.
    - Fail-safe: kembalikan None (bukan raise) kalau ffmpeg gagal/timeout,
      supaya caller tidak pernah menganggap ini kritikal terhadap playback.

Depends on:
    - config

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Dipanggil dari event loop, kerja berat didelegasikan ke ThreadPoolExecutor
    milik caller (lihat LoudnessService).
"""

import json
import os
import re
import shutil
import subprocess

import structlog

from config import LOUDNESS_ANALYZE_TIMEOUT_SEC
from core.log_categories import LC_EXTERNAL

logger = structlog.get_logger(component="playback.loudness_analyzer")

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.DOTALL)


from typing import NamedTuple


class LoudnessMeasurement(NamedTuple):
    """Result of a loudness analysis pass."""

    lufs: float  # integrated loudness (LUFS)
    true_peak: float  # true peak in dBTP (0.0 = 0dBFS ceiling)


class LoudnessAnalyzer:
    """measure_sync(uri) -> LoudnessMeasurement | None.

    Returns both integrated LUFS *and* true peak (dBTP) so callers can apply
    headroom-safe gain without a separate analysis pass.
    Caller must invoke via run_in_executor — this is blocking.
    """

    def measure_sync(self, uri: str) -> "LoudnessMeasurement | None":
        """Dipanggil lewat run_in_executor -- BLOCKING, jangan panggil langsung
        dari event loop."""
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            uri,
            "-af",
            "loudnorm=print_format=json",
            "-f",
            "null",
            "-",
        ]
        if os.name != "nt":
            prefix = []
            if shutil.which("nice"):
                prefix += ["nice", "-n", "10"]
            if shutil.which("ionice"):
                prefix += ["ionice", "-c2", "-n7"]
            if prefix:
                cmd = prefix + cmd
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=LOUDNESS_ANALYZE_TIMEOUT_SEC,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            logger.debug(
                "loudness_analysis_timeout",
                category=LC_EXTERNAL,
                uri=uri,
            )
            return None
        except OSError as e:
            logger.error(
                "ffmpeg_spawn_failed",
                category=LC_EXTERNAL,
                error_type=type(e).__name__,
                error=str(e),
            )
            return None

        match = _JSON_BLOCK_RE.search(result.stderr)
        if not match:
            logger.debug(
                "loudness_analysis_no_json_output",
                category=LC_EXTERNAL,
                uri=uri,
            )
            return None

        try:
            data = json.loads(match.group(0))
            lufs = float(data["input_i"])
            # input_tp is already computed by ffmpeg at zero extra cost.
            # -inf string (silence) is treated as a very low peak (no clipping risk).
            raw_tp = data.get("input_tp", "-inf")
            true_peak = float(raw_tp) if raw_tp != "-inf" else -120.0
            return LoudnessMeasurement(lufs=lufs, true_peak=true_peak)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "loudness_analysis_json_parse_failed",
                category=LC_EXTERNAL,
                error_type=type(e).__name__,
                error=str(e),
            )
            return None
