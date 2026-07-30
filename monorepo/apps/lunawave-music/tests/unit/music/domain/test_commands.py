"""
Module: core.commands

Purpose:
    Unit tests for core.commands.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - core.commands

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import music.domain.commands as cmds


def test_commands_are_unique_strings():
    command_values = []

    # Introspect module attributes that start with CMD_
    for name in dir(cmds):
        if name.startswith("CMD_"):
            val = getattr(cmds, name)
            assert isinstance(val, str)
            command_values.append(val)

    # Check for uniqueness
    assert len(command_values) == len(
        set(command_values)
    ), "There are duplicate command strings in core.commands"
