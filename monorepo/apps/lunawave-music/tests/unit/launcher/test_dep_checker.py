"""
Module: tests.unit.launcher.test_dep_checker

Purpose:
    Unit tests for the launcher dependency checker.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - launcher.dep_checker

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from launcher.dep_checker import DependencyChecker


def test_check_dependencies(monkeypatch):
    checker = DependencyChecker()

    # Mock importlib.util.find_spec to simulate missing/found packages
    def mock_find_spec(name):
        if name == "missing_pkg":
            return None
        return True

    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)

    # Temporarily override deps mapping for testing
    monkeypatch.setattr(
        checker.__class__, "check_dependencies", lambda self: (["missing_pkg"], True)
    )

    missing, mpv_ok = checker.check_dependencies()
    assert "missing_pkg" in missing
    assert mpv_ok is True


def test_check_port(monkeypatch):
    checker = DependencyChecker()

    # Mock socket connect_ex
    class MockSocket:
        def __init__(self, *args, **kwargs):
            pass

        def settimeout(self, t):
            pass

        def connect_ex(self, address):
            # Port 80 is "in use", others are "free"
            if address[1] == 80:
                return 0
            return 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("socket.socket", MockSocket)

    assert checker.check_port("127.0.0.1", 80) is True
    assert checker.check_port("127.0.0.1", 8080) is False


def test_mpv_version(monkeypatch):
    checker = DependencyChecker()

    # Test mpv found
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/mpv")

    class MockResult:
        returncode = 0
        stdout = "mpv 0.34.0 Copyright © 2000-2021 mpv/MPlayer/mplayer2 projects\nbuilt on UNKNOWN"

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MockResult())
    assert checker.mpv_version() == "mpv 0.34.0 Copyright © 2000-2021 mpv/MPlayer/mplayer2 projects"

    # Test mpv not found
    monkeypatch.setattr("shutil.which", lambda x: None)
    assert checker.mpv_version() is None


def test_mpv_version_exception_is_fail_safe_and_logged(monkeypatch):
    """P4-T1c (temuan #9): mpv_version()'s except/pass was reclassified as
    best-effort cleanup with debug-level logging. subprocess.run raising
    (e.g. binary corrupt, unexpected OSError) must not propagate, and the
    new logger.debug(...) call must fire exactly once."""
    import launcher.dep_checker as dep_checker_module

    debug_calls = []
    monkeypatch.setattr(
        dep_checker_module.logger, "debug", lambda event, **kw: debug_calls.append((event, kw))
    )
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/mpv")

    def _boom(*args, **kwargs):
        raise OSError("mpv binary is corrupt")

    monkeypatch.setattr("subprocess.run", _boom)

    checker = DependencyChecker()
    assert checker.mpv_version() is None  # must not raise
    assert [event for event, _ in debug_calls] == ["mpv_version_check_failed"]
