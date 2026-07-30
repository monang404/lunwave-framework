from launcher import preflight


def test_run_all_ok(monkeypatch, capsys):
    class MockChecker:
        def check_dependencies(self):
            return [], True

        def mpv_version(self):
            return "mpv 0.34.0"

        def check_port(self, host, port):
            return False

    monkeypatch.setattr("launcher.preflight.DependencyChecker", MockChecker)

    # Run
    code = preflight.run("127.0.0.1", 8765)
    assert code == 0
    captured = capsys.readouterr()
    assert "All Python dependencies are satisfied." in captured.out
    assert "MPV detected" in captured.out
    assert "is free" in captured.out


def test_run_some_failed(monkeypatch, capsys):
    class MockChecker:
        def check_dependencies(self):
            return ["aiohttp"], False

        def mpv_version(self):
            return None

        def check_port(self, host, port):
            return True

    monkeypatch.setattr("launcher.preflight.DependencyChecker", MockChecker)

    code = preflight.run("127.0.0.1", 8765)
    assert code == 1
    captured = capsys.readouterr()
    assert "Ada modul yang belum terinstall" in captured.out
    assert "MPV not found" in captured.out
    assert "IN USE" in captured.out


def test_log_result_failure_is_silent_safe(monkeypatch, capsys):
    calls = []

    def mock_info(*args, **kwargs):
        calls.append("info")
        raise RuntimeError("boom")

    monkeypatch.setattr(preflight.logger, "info", mock_info)

    # Must not raise
    preflight.log_result("some_check", "ok")

    assert calls == ["info"]
