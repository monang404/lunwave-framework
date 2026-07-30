"""
Module: plugins.lyrics_parser

Purpose:
    Parser for extracting timed lyrics from LRC-formatted text.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread.
"""

import re

_LRC_TAG_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
_LRC_METADATA_RE = re.compile(r"^\[[a-zA-Z]+:.*\]$")


class LyricsParser:
    @staticmethod
    def parse_lrc(lrc_text: str) -> list[tuple[float, str]]:
        result = []
        for line in lrc_text.splitlines():
            line = line.strip()
            if not line or _LRC_METADATA_RE.match(line):
                continue
            tags = list(_LRC_TAG_RE.finditer(line))
            if tags:
                text = line[tags[-1].end() :].strip()
                for m in tags:
                    minutes, seconds = m.groups()
                    timestamp = int(minutes) * 60 + float(seconds)
                    result.append((timestamp, text))
            else:
                result.append((0.0, line))
        return sorted(result, key=lambda x: x[0])
