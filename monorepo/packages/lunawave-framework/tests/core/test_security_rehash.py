import base64
import hashlib
import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest

from lunawave_framework.core.security.security import PBKDF2_ITERATIONS, hash_password, needs_rehash, verify_password
from server.handlers.auth import handle_auth


def test_needs_rehash():
    # Hash made manually with 100000 -> True
    password = "password"
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    old_hash = f"pbkdf2:sha256:100000${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(key).decode('utf-8')}"
    assert needs_rehash(old_hash) is True

    # Hash made with current hash_password() -> False
    new_hash = hash_password(password)
    assert needs_rehash(new_hash) is False

    # Invalid format -> False
    assert needs_rehash("invalid_hash") is False
    assert needs_rehash("pbkdf2:sha256:invalid$salt$key") is False


@pytest.mark.asyncio
async def test_integration_login_rehashes_old_password():
    # Create old hash
    password = "correct"
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    old_hash = f"pbkdf2:sha256:100000${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(key).decode('utf-8')}"

    account = {"username": "admin", "password_hash": old_hash}

    mgr = MagicMock()
    mgr.rl_lock = MagicMock()
    mgr.rl_lock.__aenter__ = AsyncMock(return_value=None)
    mgr.rl_lock.__aexit__ = AsyncMock(return_value=None)
    mgr.authenticated_connections = set()
    mgr.login_attempts = {}
    mgr.command_history = {}

    db = MagicMock()
    db.sessions = MagicMock()
    db.sessions.create_session = AsyncMock()
    db.admin_account = MagicMock()
    db.admin_account.get_admin_account = AsyncMock(return_value=account)
    db.admin_account.update_password = AsyncMock()

    ws = MagicMock()
    ws.send_str = AsyncMock()

    await handle_auth(
        ws,
        {"username": "admin", "password": "correct"},
        mgr,
        "127.0.0.1",
        db,
        now=1000,
    )

    # Asserts
    assert ws in mgr.authenticated_connections
    db.admin_account.update_password.assert_awaited_once()
    args = db.admin_account.update_password.call_args[0]
    new_hash = args[0]
    assert str(PBKDF2_ITERATIONS) in new_hash
    assert verify_password("correct", new_hash) is True
