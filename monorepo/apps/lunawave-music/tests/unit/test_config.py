"""
Module: tests.unit.test_config

Purpose:
    Unit tests for application configuration and environment variables.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.security

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import pytest

"""tests/unit/test_config.py — mirrors config.py

config.py runs all of its logic at *module import time*, keyed off env
vars (BASE_DIR resolution, admin password auto-generation, socket path
validation), and Python caches modules in sys.modules — so re-importing
it inside the test process after mutating os.environ does NOT re-run
that logic.

Every scenario below therefore runs `config.py` in a fresh subprocess
with a controlled environment, and reads back results either via stdout
markers or via files config.py writes to BASE_DIR. This also keeps each
scenario's stdout (including the auto-generated-password banner) fully
isolated from pytest's own captured output.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def run_config_snippet(
    code: str, env_overrides: dict, tmp_path: Path
) -> subprocess.CompletedProcess:
    """Run a short Python snippet, after `import config`, in a subprocess
    with only the given env vars set (plus what's needed to import config)."""
    env = {"PATH": __import__("os").environ.get("PATH", ""), "PYTHONPATH": str(REPO_ROOT)}
    env.update(env_overrides)
    env.setdefault("LUNAWAVE_BASE", str(tmp_path))
    full_code = "import config\n" + code
    return subprocess.run(
        [sys.executable, "-c", full_code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_base_dir_resolves_from_lunawave_base_env_var(tmp_path):
    result = run_config_snippet("print(config.BASE_DIR)", {"LUNAWAVE_ADMIN_PASS": "x"}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path)


def test_base_dir_falls_back_to_legacy_yt_player_base_env_var(tmp_path):
    result = run_config_snippet(
        "print(config.BASE_DIR)",
        {"YT_PLAYER_BASE": str(tmp_path), "LUNAWAVE_ADMIN_PASS": "x"},
        tmp_path,
    )
    # explicitly don't set LUNAWAVE_BASE for this one
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "YT_PLAYER_BASE": str(tmp_path),
        "LUNAWAVE_ADMIN_PASS": "x",
    }
    result = subprocess.run(
        [sys.executable, "-c", "import config\nprint(config.BASE_DIR)"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path)


def test_cache_dir_and_db_path_are_derived_from_base_dir(tmp_path):
    result = run_config_snippet(
        "print(config.CACHE_DIR); print(config.DB_PATH)",
        {"LUNAWAVE_ADMIN_PASS": "x"},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(tmp_path / "cache" / "mp3")
    assert lines[1] == str(tmp_path / "data" / "lunawave.db")


def test_download_dir_is_derived_from_base_dir_and_distinct_from_cache_dir(tmp_path):
    # Regression: the Settings UI's "Ukuran Cache" used to read CACHE_DIR
    # (cache/mp3), which is emptied right after every download finishes, so
    # it always showed 0.00 MB even with files present in downloads/.
    result = run_config_snippet(
        "print(config.DOWNLOAD_DIR); print(config.DOWNLOAD_DIR == config.CACHE_DIR)",
        {"LUNAWAVE_ADMIN_PASS": "x"},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(tmp_path / "downloads")
    assert lines[1] == "False"


def test_default_volume_falls_back_to_80(tmp_path):
    result = run_config_snippet(
        "print(config.DEFAULT_VOLUME)", {"LUNAWAVE_ADMIN_PASS": "x"}, tmp_path
    )
    assert result.stdout.strip() == "80"


def test_default_volume_reads_env_override(tmp_path):
    result = run_config_snippet(
        "print(config.DEFAULT_VOLUME)",
        {"LUNAWAVE_ADMIN_PASS": "x", "YT_PLAYER_VOLUME": "45"},
        tmp_path,
    )
    assert result.stdout.strip() == "45"


def test_web_host_and_port_defaults(tmp_path):
    result = run_config_snippet(
        "print(config.WEB_HOST); print(config.WEB_PORT)",
        {"LUNAWAVE_ADMIN_PASS": "x"},
        tmp_path,
    )
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "0.0.0.0"
    assert lines[1] == "8765"


def test_web_port_reads_legacy_ytgui_port_env_var(tmp_path):
    result = run_config_snippet(
        "print(config.WEB_PORT)",
        {"LUNAWAVE_ADMIN_PASS": "x", "YTGUI_PORT": "9000"},
        tmp_path,
    )
    assert result.stdout.strip() == "9000"


def test_admin_username_default_and_legacy_fallback(tmp_path):
    result = run_config_snippet(
        "print(config.ADMIN_USERNAME)", {"LUNAWAVE_ADMIN_PASS": "x"}, tmp_path
    )
    assert result.stdout.strip() == "admin"

    result = run_config_snippet(
        "print(config.ADMIN_USERNAME)",
        {"LUNAWAVE_ADMIN_PASS": "x", "YTGUI_ADMIN_USER": "root"},
        tmp_path,
    )
    assert result.stdout.strip() == "root"


@pytest.mark.skipif(__import__("os").name == "nt", reason="Windows uses named pipes for MPV_SOCKET")
def test_mpv_socket_defaults_inside_base_dir_cache_sockets(tmp_path):
    result = run_config_snippet("print(config.MPV_SOCKET)", {"LUNAWAVE_ADMIN_PASS": "x"}, tmp_path)
    assert result.returncode == 0, result.stderr
    socket_path = Path(result.stdout.strip())
    assert socket_path.parent == (tmp_path / "cache" / "sockets").resolve()


@pytest.mark.skipif(__import__("os").name == "nt", reason="Windows uses named pipes for MPV_SOCKET")
def test_mpv_socket_outside_base_dir_is_rejected_and_falls_back(tmp_path):
    outside = "/tmp/definitely-outside-base-dir.sock"
    result = run_config_snippet(
        "print(config.MPV_SOCKET)",
        {"LUNAWAVE_ADMIN_PASS": "x", "LUNAWAVE_SOCKET": outside},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    socket_path = Path(result.stdout.strip())
    # Must NOT be the untrusted path, and must live back inside BASE_DIR.
    assert str(socket_path) != outside
    assert socket_path.parent == (tmp_path / "cache" / "sockets").resolve()
    assert "di luar BASE_DIR" in result.stderr


def test_admin_password_override_is_none_when_no_env_var_set(tmp_path):
    """T-B14.1: no more auto-generation. Without an env var override,
    config.py must not create any file and must not print any password."""
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "LUNAWAVE_BASE": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-c", "import config\nprint(config.ADMIN_PASSWORD_OVERRIDE)"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "None"
    assert "PASSWORD ADMIN GENERATED" not in result.stdout
    assert not (tmp_path / "cache" / "admin_password.txt").exists()


def test_config_no_longer_exposes_legacy_auto_generate_symbols(tmp_path):
    """T-B14.1: IS_PASSWORD_AUTO_GENERATED and the legacy ADMIN_PASSWORD
    name (config.ADMIN_PASSWORD, read directly by verification logic) must
    both be gone -- admin_account (SQLite) is the only source of truth."""
    result = run_config_snippet(
        "print(hasattr(config, 'IS_PASSWORD_AUTO_GENERATED'))\n"
        "print(hasattr(config, 'ADMIN_PASSWORD'))",
        {},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines == ["False", "False"]


def test_running_config_twice_without_env_var_never_writes_a_cache_file(tmp_path):
    """Regression for the removed mechanism: repeated imports/restarts with
    no override set must stay a pure no-op on disk."""
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "LUNAWAVE_BASE": str(tmp_path),
    }
    code = "import config\n"
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
    assert not (tmp_path / "cache" / "admin_password.txt").exists()


def test_admin_password_override_from_ytgui_admin_pass_plaintext_gets_hashed(tmp_path):
    result = run_config_snippet(
        "print(config.ADMIN_PASSWORD_OVERRIDE)",
        {"YTGUI_ADMIN_PASS": "plaintext-secret"},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("pbkdf2:sha256:")


def test_admin_password_override_from_ytgui_admin_pass_already_hashed_is_kept_as_is(tmp_path):
    from core.security import hash_password

    pre_hashed = hash_password("already-hashed-secret")
    result = run_config_snippet(
        "print(config.ADMIN_PASSWORD_OVERRIDE)",
        {"YTGUI_ADMIN_PASS": pre_hashed},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == pre_hashed


def test_admin_password_override_from_lunawave_admin_pass_plaintext_gets_hashed(tmp_path):
    """LUNAWAVE_ADMIN_PASS is the primary/preferred env var (LUNAWAVE_*
    supersedes the legacy YTGUI_* names throughout config.py), so it must
    be hashed exactly like YTGUI_ADMIN_PASS."""
    result = run_config_snippet(
        "print(config.ADMIN_PASSWORD_OVERRIDE)",
        {"LUNAWAVE_ADMIN_PASS": "plaintext-secret"},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("pbkdf2:sha256:")


def test_admin_password_override_from_lunawave_admin_pass_already_hashed_is_kept_as_is(tmp_path):
    from core.security import hash_password

    pre_hashed = hash_password("already-hashed-secret")
    result = run_config_snippet(
        "print(config.ADMIN_PASSWORD_OVERRIDE)",
        {"LUNAWAVE_ADMIN_PASS": pre_hashed},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == pre_hashed


def test_lunawave_admin_pass_takes_precedence_over_ytgui_admin_pass(tmp_path):
    result = run_config_snippet(
        "print(config.ADMIN_PASSWORD_OVERRIDE)",
        {"LUNAWAVE_ADMIN_PASS": "new-var-wins", "YTGUI_ADMIN_PASS": "old-var-loses"},
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    from core.security import verify_password

    assert verify_password("new-var-wins", result.stdout.strip()) is True
    assert verify_password("old-var-loses", result.stdout.strip()) is False


@pytest.mark.skipif(
    __import__("os").name == "nt", reason="WinError 10106 on test environment subprocess"
)
def test_auth_handler_imports_cleanly_with_lunawave_admin_pass_set(tmp_path):
    """End-to-end regression check for the same bug: the actual consumer
    module must import without raising."""
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "LUNAWAVE_BASE": str(tmp_path),
        "LUNAWAVE_ADMIN_PASS": "some-password",
    }
    result = subprocess.run(
        [sys.executable, "-c", "import server.handlers.auth\nprint('import-ok')"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
