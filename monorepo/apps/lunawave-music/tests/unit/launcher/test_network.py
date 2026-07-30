from unittest.mock import MagicMock, patch

from lunawave_framework.core.lifecycle.network import check_port_in_use, get_pid_occupying_port


def test_check_port_in_use():
    with patch("lunawave_framework.core.lifecycle.network.socket.socket") as mock_socket:
        mock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_instance

        # Test port in use (connect returns 0)
        mock_instance.connect_ex.return_value = 0
        assert check_port_in_use(8080) is True

        # Test port not in use (connect returns non-zero)
        mock_instance.connect_ex.return_value = 111
        assert check_port_in_use(8080) is False


def test_get_pid_occupying_port_win32():
    with patch("lunawave_framework.core.lifecycle.network.sys.platform", "win32"):
        with patch("lunawave_framework.core.lifecycle.network.subprocess.check_output") as mock_check_output:
            # Simulate netstat output
            mock_check_output.return_value = (
                "  TCP    0.0.0.0:8080           0.0.0.0:0              LISTENING       1234\n"
            )
            assert get_pid_occupying_port(8080) == 1234

            mock_check_output.return_value = (
                "  UDP    0.0.0.0:8080           *:*                                    1234\n"
            )
            assert get_pid_occupying_port(8080) is None


def test_get_pid_occupying_port_linux():
    with patch("lunawave_framework.core.lifecycle.network.sys.platform", "linux"):
        with patch("lunawave_framework.core.lifecycle.network.subprocess.check_output") as mock_check_output:
            # Simulate lsof output
            mock_check_output.return_value = "5678\n"
            assert get_pid_occupying_port(8080) == 5678


def test_get_pid_occupying_port_win32_failure_is_fail_safe_and_logged():
    """P4-T1c (temuan #9): win32 netstat except/pass reclassified as
    best-effort with debug-level logging."""
    import lunawave_framework.core.lifecycle.network as network_module

    debug_calls = []
    with patch.object(
        network_module.logger, "debug", lambda event, **kw: debug_calls.append((event, kw))
    ):
        with patch("lunawave_framework.core.lifecycle.network.sys.platform", "win32"):
            with patch("lunawave_framework.core.lifecycle.network.subprocess.check_output") as mock_check_output:
                mock_check_output.side_effect = OSError("netstat not found")
                assert get_pid_occupying_port(8080) is None  # must not raise

    assert [event for event, _ in debug_calls] == ["port_owner_lookup_failed"]


def test_get_pid_occupying_port_unix_all_fallbacks_fail_is_fail_safe_and_logged():
    """P4-T1c (temuan #9): final unix fallback (ss) except/pass reclassified
    as best-effort with debug-level logging, once lsof AND fuser AND ss all
    fail."""
    import lunawave_framework.core.lifecycle.network as network_module

    debug_calls = []
    with patch.object(
        network_module.logger, "debug", lambda event, **kw: debug_calls.append((event, kw))
    ):
        with patch("lunawave_framework.core.lifecycle.network.sys.platform", "linux"):
            with patch("lunawave_framework.core.lifecycle.network.subprocess.check_output") as mock_check_output:
                mock_check_output.side_effect = OSError("no port-lookup tool available")
                assert get_pid_occupying_port(8080) is None  # must not raise

    assert [event for event, _ in debug_calls] == ["port_owner_lookup_failed"]
