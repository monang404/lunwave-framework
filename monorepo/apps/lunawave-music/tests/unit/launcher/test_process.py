import subprocess
import sys
from unittest.mock import MagicMock, patch

from lunawave_framework.core.lifecycle.process import ServerProcess, kill_process_by_name, kill_process_tree


def test_kill_process_tree():
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "win32"):
        with patch("lunawave_framework.core.lifecycle.process.subprocess.run") as mock_run:
            kill_process_tree(1234)
            mock_run.assert_called_once_with(
                ["taskkill", "/F", "/T", "/PID", "1234"], stdout=-3, stderr=-3
            )


def test_kill_process_by_name():
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "linux"):
        with patch("lunawave_framework.core.lifecycle.process.subprocess.run") as mock_run:
            kill_process_by_name("mpv")
            mock_run.assert_called_once_with(["pkill", "-f", "mpv"], stdout=-3, stderr=-3)


def test_server_process_start():
    with patch("lunawave_framework.core.lifecycle.process.subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        sp = ServerProcess("/fake/cwd", 8080)
        proc = sp.start()

        assert proc == mock_process
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == [sys.executable, "main.py"]
        assert kwargs["cwd"] == "/fake/cwd"
        assert kwargs["env"]["LUNAWAVE_PORT"] == "8080"


def test_server_process_stop():
    with patch("lunawave_framework.core.lifecycle.process.kill_process_tree") as mock_kpt:
        sp = ServerProcess("/fake/cwd", 8080)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # is_running -> True
        mock_proc.pid = 999
        sp.process = mock_proc

        sp.stop()

        mock_kpt.assert_called_once_with(999)
        mock_proc.wait.assert_called_once()


# ---------------------------------------------------------------------------
# P4-T1c (temuan #9): except/pass di launcher/process.py diklasifikasikan
# "best-effort cleanup" dan diberi logging debug-level. Test di bawah ini
# memicu tiap except-block yang diubah untuk memastikan (a) tetap fail-safe
# (tidak pernah melempar), dan (b) logger.debug terpanggil sesuai ekspektasi.
# ---------------------------------------------------------------------------


def _capture_debug(monkeypatch):
    import lunawave_framework.core.lifecycle.process as process_module

    calls = []
    monkeypatch.setattr(
        process_module.logger, "debug", lambda event, **kw: calls.append((event, kw))
    )
    return calls


def test_kill_process_tree_win32_failure_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "win32"):
        with patch("lunawave_framework.core.lifecycle.process.subprocess.run", side_effect=OSError("taskkill missing")):
            kill_process_tree(1234)  # must not raise
    assert [event for event, _ in calls] == ["kill_process_tree_failed"]


def test_kill_process_tree_unix_both_fallbacks_fail_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "linux"):
        with patch("lunawave_framework.core.lifecycle.process.os.killpg", side_effect=ProcessLookupError(), create=True):
            with patch("lunawave_framework.core.lifecycle.process.os.kill", side_effect=ProcessLookupError(), create=True):
                kill_process_tree(1234)  # must not raise
    assert [event for event, _ in calls] == ["kill_process_tree_failed"]


def test_kill_process_by_name_win32_failure_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "win32"):
        with patch("lunawave_framework.core.lifecycle.process.subprocess.run", side_effect=OSError("taskkill missing")):
            kill_process_by_name("mpv")  # must not raise
    assert [event for event, _ in calls] == ["kill_process_by_name_failed"]


def test_kill_process_by_name_unix_failure_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.process.sys.platform", "linux"):
        with patch("lunawave_framework.core.lifecycle.process.subprocess.run", side_effect=OSError("pkill missing")):
            kill_process_by_name("mpv")  # must not raise
    assert [event for event, _ in calls] == ["kill_process_by_name_failed"]


def test_pipe_stdout_failure_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    sp = ServerProcess("/fake/cwd", 8080)

    class _BoomStdout:
        def __iter__(self):
            raise OSError("pipe broke")

    mock_proc = MagicMock()
    mock_proc.stdout = _BoomStdout()
    sp.process = mock_proc

    logged = []
    sp.on_log = lambda msg, **kw: logged.append(msg)

    sp._pipe_stdout()  # must not raise

    assert [event for event, _ in calls] == ["pipe_stdout_failed"]
    assert logged == ["── process ended ──"]  # end-of-process callback still fires


def test_stop_force_kill_failure_is_fail_safe_and_logged(monkeypatch):
    calls = _capture_debug(monkeypatch)
    with patch("lunawave_framework.core.lifecycle.process.kill_process_tree"):
        sp = ServerProcess("/fake/cwd", 8080)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # is_running -> True
        mock_proc.pid = 999
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="main.py", timeout=6)
        mock_proc.kill.side_effect = OSError("already reaped")
        sp.process = mock_proc

        sp.stop()  # must not raise

    assert [event for event, _ in calls] == ["force_kill_failed"]
