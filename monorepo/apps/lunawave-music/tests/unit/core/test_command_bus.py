"""tests/unit/core/test_command_bus.py

Phase 3 note: the CommandBus mechanism tests moved to
packages/lunawave-framework/tests/core/test_command_bus.py, and the CMD_*
uniqueness check moved to tests/unit/music/domain/test_commands.py (both
testing music.domain.commands directly). What's left here is specific to
this app repo's shim: core/command_bus.py recombines the framework's
generic CommandBus with music.domain.commands' CMD_* constants (ADR 0013,
Decision 3) -- this test exists to catch a regression in that
recombination specifically, which neither of the migrated tests would
catch on their own.
"""

from core.command_bus import CMD_PLAY_TRACK, CMD_QUIT, CommandBus
from lunawave_framework.core.kernel.command_bus import CommandBus as _FrameworkCommandBus


def test_shim_command_bus_is_the_framework_command_bus_class():
    assert CommandBus is _FrameworkCommandBus


def test_shim_reexports_domain_command_constants():
    from core import command_bus as module

    constants = [
        value
        for name, value in vars(module).items()
        if name.startswith("CMD_") and isinstance(value, str)
    ]
    assert len(constants) >= 15
    assert len(constants) == len(set(constants)), "duplicate command name constants"
    assert CMD_PLAY_TRACK == "cmd.play.track"
    assert CMD_QUIT == "cmd.quit"
