"""
Module: lunawave_framework.core.logging.log_reader

Purpose:
    Provide utilities to parse and tail the app's log file for dashboard and
    observability purposes.

Responsibility:
    - Parse raw structlog lines formatted by `core.log_config.file_renderer`.
    - Provide a tail() function to retrieve the most recent N lines with filtering.
    - Provide a stats() function to aggregate log occurrences by level and category.

Depends on:
    - lunawave_framework.core._env (resolves the log file path; see Phase 2
      extraction notes in that module's docstring)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless functions, file read is thread-safe.
"""

import datetime
import re

from lunawave_framework.core._env import resolve_log_path

# Parses lines like: [14:02:10] INFO: event_key (k=v, k2=v2)
LOG_LINE_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] (\w+):\s+(.*?)(?:\s+\((.*)\))?$")


def parse_line(line: str) -> dict:
    """
    Parses a single line of log into a dictionary.
    Returns: { "time": "...", "level": "...", "event": "...", "fields": {...} }
    For unparseable lines (e.g. session banners), level will be "BANNER".
    """
    line = line.strip()
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return {"time": "", "level": "BANNER", "event": line, "fields": {}}

    time_str, level, event, fields_str = match.groups()
    fields = {}
    if fields_str:
        # Simplistic split, assuming values don't contain ", " (comma space).
        parts = fields_str.split(", ")
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                fields[k] = v
            else:
                fields[p] = ""
    return {"time": time_str, "level": level.upper(), "event": event, "fields": fields}


def _get_all_lines() -> list[str]:
    """Reads the app log and its rotated backups in chronological order."""
    log_path = resolve_log_path("app.log")
    suffixes = [".2", ".1", ""]
    lines = []
    for suffix in suffixes:
        p = log_path.with_name(log_path.name + suffix)
        if p.exists():
            with open(p, encoding="utf-8", errors="replace") as f:
                lines.extend(f.readlines())
    return lines


def tail(
    limit: int = 200,
    category: str | None = None,
    level: str | None = None,
    query: str | None = None,
) -> list[dict]:
    """
    Reads the last `limit` lines from the log files matching the given filters.
    Result is chronologically ordered (oldest to newest among the tailed lines).
    """
    lines = _get_all_lines()
    result: list[dict] = []

    level_filter = level.upper() if level else None
    query_filter = query.lower() if query else None

    # Read backwards
    for line in reversed(lines):
        if not line.strip():
            continue

        parsed = parse_line(line)

        # Apply filters
        if level_filter and parsed["level"] != level_filter:
            continue

        if category:
            # Check category field. If it's a banner, it has no fields.
            if parsed["fields"].get("category") != category:
                continue

        if query_filter:
            # Simple substring search in the raw line (case insensitive)
            if query_filter not in line.lower():
                continue

        # Insert at the beginning to maintain chronological order
        result.insert(0, parsed)

        if len(result) >= limit:
            break

    return result


def stats(window_seconds: int = 3600) -> dict:
    """
    Calculates the aggregate count of log lines per level and category
    within the last `window_seconds`.
    """
    lines = _get_all_lines()

    levels_count: dict[str, int] = {}
    categories_count: dict[str, int] = {}
    matrix: dict[str, dict[str, int]] = {}

    try:
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    except AttributeError:
        # Fallback for Python < 3.11
        now = datetime.datetime.utcnow()

    # We don't have dates in the log by default, only HH:MM:SS.
    # To handle window_seconds robustly without full dates, we assume
    # logs are from today, and if the time is strictly in the future,
    # it must be from yesterday.

    for line in reversed(lines):
        if not line.strip():
            continue

        parsed = parse_line(line)
        if parsed["level"] == "BANNER":
            continue

        time_str = parsed["time"]
        if not time_str:
            continue

        try:
            t = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
            log_time = datetime.datetime.combine(now.date(), t)
            if log_time > now:
                log_time -= datetime.timedelta(days=1)

            delta = (now - log_time).total_seconds()
            if delta > window_seconds:
                continue
        except ValueError:
            continue

        # Count levels
        lvl = parsed["level"]
        levels_count[lvl] = levels_count.get(lvl, 0) + 1

        # Count categories
        cat = parsed["fields"].get("category", "unknown")
        categories_count[cat] = categories_count.get(cat, 0) + 1

        # Build matrix
        if cat not in matrix:
            matrix[cat] = {}
        matrix[cat][lvl] = matrix[cat].get(lvl, 0) + 1

    return {"levels": levels_count, "categories": categories_count, "matrix": matrix}
