"""
Module: server.middleware

Purpose:
    Package for server-side middleware: per-IP WS command rate limiting
    (this file, unchanged) and the aiohttp HTTP traffic middleware added
    in ADR-0010 (server.middleware.traffic).

    This file used to be the standalone module `server/middleware.py`.
    Converted to a package (ADR-0010 session 3) so `traffic.py` could be
    added alongside it without dumping unrelated HTTP middleware logic
    into the WS rate-limit file. Import path `from server.middleware
    import check_rate_limit` is unchanged -- no call site needed updating.

Responsibilities:
    - Track command timestamps per IP in a sliding 60-second window.
    - Reject requests when a client exceeds 30 commands per minute.
    - Re-export traffic_middleware from server.middleware.traffic.

Depends on:
    - server.middleware.traffic

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async; caller must hold manager.rl_lock).
"""

from server.middleware.traffic import traffic_middleware

__all__ = ["check_rate_limit", "traffic_middleware"]


async def check_rate_limit(manager, client_ip: str, now: float) -> bool:
    async with manager.rl_lock:
        from collections import deque

        cmd_history = manager.command_history.get(client_ip, deque())
        while cmd_history and now - cmd_history[0] >= 60:
            cmd_history.popleft()
        if not cmd_history:
            manager.command_history.pop(client_ip, None)
        else:
            manager.command_history[client_ip] = cmd_history
        if len(cmd_history) >= 30:
            return False
        cmd_history.append(now)
        manager.command_history[client_ip] = cmd_history
        return True


async def check_chat_rate_limit(manager, key: str, now: float, limit: int = 10) -> bool:
    """
    Kuota terpisah dari kuota command umum dan dikunci per client_uid/client_ip.
    """
    async with manager.rl_lock:
        from collections import deque

        chat_history = manager.chat_history.get(key, deque())
        while chat_history and now - chat_history[0] >= 60:
            chat_history.popleft()
        if not chat_history:
            manager.chat_history.pop(key, None)
        else:
            manager.chat_history[key] = chat_history
        if len(chat_history) >= limit:
            return False
        chat_history.append(now)
        manager.chat_history[key] = chat_history
        return True
