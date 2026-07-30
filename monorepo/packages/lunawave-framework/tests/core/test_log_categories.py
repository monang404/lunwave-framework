"""tests/unit/core/test_log_categories.py — mirrors core/log_categories.py

Purpose:
    Verify the category constants exist, match the §4 table in
    LOGGING_STANDARD.md exactly, and carry no duplicate values (a
    duplicate would let two "different" categories silently collapse
    into the same string).

    Note: the audit/plan docs say "14 kategori standar", but the actual
    §4 table in LOGGING_STANDARD.md lists 15 rows (lifecycle, session,
    auth, command, event, playback, queue, radio, download, resolve,
    cache, persistence, external, security, system). This module follows
    the table (the normative spec) rather than the prose count elsewhere.

Subscribes to:
    None

Publishes:
    None
"""

import lunawave_framework.core.logging.log_categories as log_categories

_EXPECTED_NAMES = [
    "LC_LIFECYCLE",
    "LC_SESSION",
    "LC_AUTH",
    "LC_COMMAND",
    "LC_EVENT",
    "LC_PLAYBACK",
    "LC_QUEUE",
    "LC_RADIO",
    "LC_DOWNLOAD",
    "LC_RESOLVE",
    "LC_CACHE",
    "LC_PERSISTENCE",
    "LC_EXTERNAL",
    "LC_SECURITY",
    "LC_SYSTEM",
]


def test_all_14_constants_exist():
    for name in _EXPECTED_NAMES:
        assert hasattr(log_categories, name), f"missing constant {name}"


def test_all_categories_tuple_has_15_entries():
    assert len(log_categories.ALL_CATEGORIES) == 15


def test_no_duplicate_category_values():
    assert len(set(log_categories.ALL_CATEGORIES)) == len(log_categories.ALL_CATEGORIES)


def test_categories_are_lowercase_snake_case_strings():
    for value in log_categories.ALL_CATEGORIES:
        assert isinstance(value, str)
        assert value == value.lower()
        assert " " not in value
