"""
Module: tests.unit.plugins.test_lyrics_parser

Purpose:
    Unit tests for LRC lyrics parsing logic.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - plugins.lyrics_parser

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from plugins.lyrics_parser import LyricsParser


def test_parse_lrc_standard():
    lrc = """
    [00:12.50]Line 1
    [01:05.00]Line 2
    """
    result = LyricsParser.parse_lrc(lrc)
    assert len(result) == 2
    assert result[0] == (12.5, "Line 1")
    assert result[1] == (65.0, "Line 2")


def test_parse_lrc_no_decimals():
    lrc = """
    [00:12]Line 1
    [01:05]Line 2
    """
    result = LyricsParser.parse_lrc(lrc)
    assert len(result) == 2
    assert result[0] == (12.0, "Line 1")
    assert result[1] == (65.0, "Line 2")


def test_parse_lrc_invalid():
    lrc = """
    [invalid]
    Just text
    [00:10.00] Valid line
    """
    result = LyricsParser.parse_lrc(lrc)
    assert len(result) == 3
    assert result[0] == (0.0, "[invalid]")
    assert result[1] == (0.0, "Just text")
    assert result[2] == (10.0, "Valid line")


def test_parse_lrc_multi_timestamp_chorus_line():
    """PATCH-2026-07-16-001 regression: satu baris LRC bisa punya beberapa
    tag timestamp sekaligus untuk baris yang berulang (mis. chorus), harus
    menghasilkan satu entry per timestamp dengan teks yang sama."""
    lrc = "[00:12.00][00:36.00]Chorus line here"
    result = LyricsParser.parse_lrc(lrc)
    assert result == [(12.0, "Chorus line here"), (36.0, "Chorus line here")]


def test_parse_lrc_skips_metadata_tags():
    """PATCH-2026-07-16-001 regression: tag metadata seperti [ar:Artist]
    atau [ti:Title] tidak boleh dianggap sebagai baris lirik teks biasa."""
    lrc = """
    [ar:Some Artist]
    [ti:Some Title]
    [00:05.00]First real lyric line
    """
    result = LyricsParser.parse_lrc(lrc)
    assert result == [(5.0, "First real lyric line")]
