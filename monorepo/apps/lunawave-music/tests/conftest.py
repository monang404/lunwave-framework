"""
tests/conftest.py

Shared fixtures for the LunaWave test suite.

Layout mirrors the actual package layout (core/, cache/, engine/, ...),
not the aspirational refactor target described in docs/testing.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import os
import sys
from pathlib import Path

import pytest

_pytest_exit_status = 0


def pytest_sessionfinish(session, exitstatus):
    """Store exit status to use it if we have to force exit."""
    global _pytest_exit_status
    _pytest_exit_status = exitstatus


def pytest_unconfigure(config):
    """
    Called after all tests have finished and coverage is printed.
    If there are zombie non-daemon threads (e.g. from yt-dlp inside ThreadPoolExecutor),
    Python will hang forever on exit. This hook detects them and forces exit.
    """
    import sys
    import threading

    non_daemon_threads = [
        t
        for t in threading.enumerate()
        if not t.daemon and t.ident != threading.current_thread().ident
    ]
    if non_daemon_threads:
        print(
            f"\n[WARNING] Zombie non-daemon threads detected: {non_daemon_threads}. Force exiting to prevent CI hang!",
            file=sys.stderr,
        )
        pass


# Make sure the repo root (parent of tests/) is importable as top-level
# packages: `core`, `cache`, `engine`, `config`, etc.
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# T-B14.1: config.py no longer auto-generates an admin password or writes
# cache/admin_password.txt on import (admin_account in SQLite is now the
# only source of truth, seeded via Initial Setup or, non-default, via
# bootstrap.services._seed_admin_account_from_env — see K4). There is no
# more import-time side effect to suppress here, so we intentionally do
# NOT set LUNAWAVE_ADMIN_PASS by default: doing so would make
# config.ADMIN_PASSWORD_OVERRIDE non-None for the entire test session and
# push every test that boots services down the non-default env-override
# seeding path instead of the default no-op path.
os.environ.setdefault("LUNAWAVE_BASE", str(REPO_ROOT))


@pytest.fixture
def tmp_base_dir(tmp_path, monkeypatch):
    """Isolated BASE_DIR-like tmp directory for tests that touch the filesystem."""
    monkeypatch.setenv("LUNAWAVE_BASE", str(tmp_path))
    return tmp_path


@pytest.fixture
async def db():
    """In-memory SQLite `persistence.Repositories`, migrated and ready to use."""
    from persistence import Repositories

    repos = Repositories(db_path=Path(":memory:"))
    await repos.init()
    yield repos
    await repos.close()


@pytest.fixture
async def memory_db():
    """SQLite in-memory — murah, cepat, tidak meninggalkan file."""
    import aiosqlite

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    schema = (Path(__file__).parent.parent / "persistence" / "schema.sql").read_text(
        encoding="utf-8"
    )
    await conn.executescript(schema)
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
def cleanup_executors(monkeypatch):
    """Automatically track and shutdown ThreadPoolExecutor instances created during tests."""
    from concurrent.futures import ThreadPoolExecutor

    created_executors = []
    original_init = ThreadPoolExecutor.__init__

    def tracked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created_executors.append(self)

    monkeypatch.setattr(ThreadPoolExecutor, "__init__", tracked_init)

    yield

    for exc in created_executors:
        exc.shutdown(wait=False)
