"""
Module: lunawave_framework.core.lifecycle.network

Purpose:
    Provide cross-platform utilities to detect TCP port availability and
    identify the PID currently occupying a port.

Responsibilities:
    - Probe a port with a non-blocking socket connect attempt.
    - Identify the owning PID via netstat, lsof, fuser, or ss.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import socket
import subprocess
import sys

import structlog

logger = structlog.get_logger(component="framework.lifecycle.network")



def check_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_pid_occupying_port(port: int) -> int | None:
    if sys.platform == "win32":
        # Klasifikasi: best-effort cleanup. Ini murni untuk menampilkan PID
        # yang menempati port di UI -- gagal parse netstat tidak boleh
        # menggagalkan startup, cuma UI menampilkan "Unknown PID".
        try:
            output = subprocess.check_output(["netstat", "-aon"], shell=False, text=True)
            for line in output.splitlines():
                if "TCP" in line.upper():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        local_addr = parts[1]
                        pid = parts[-1]
                        if (
                            (local_addr.endswith(f":{port}") or local_addr.endswith(f"]:{port}"))
                            and pid.isdigit()
                            and pid != "0"
                        ):
                            return int(pid)
        except Exception as e:
            logger.debug("port_owner_lookup_failed", platform="win32", tool="netstat", error=str(e))
    else:
        try:
            output = subprocess.check_output(
                ["lsof", "-t", "-i", f":{port}"], shell=False, text=True
            )
            pids = output.strip().split()
            if pids:
                return int(pids[0])
        except Exception:
            try:
                output = subprocess.check_output(["fuser", f"{port}/tcp"], shell=False, text=True)
                parts = output.strip().split()
                if parts:
                    return int(parts[-1])
            except Exception:
                # Klasifikasi: best-effort cleanup. Fallback terakhir (lsof
                # -> fuser -> ss) semuanya gagal -- UI cukup menampilkan
                # "Unknown PID", tapi debug log membantu tahu tool mana yang
                # tidak tersedia di sistem ini.
                try:
                    output = subprocess.check_output(
                        ["ss", "-lptn", f"sport = :{port}"], shell=False, text=True
                    )
                    import re

                    m = re.search(r"pid=(\d+)", output)
                    if m:
                        return int(m.group(1))
                except Exception as e:
                    logger.debug(
                        "port_owner_lookup_failed", platform="unix", tool="ss", error=str(e)
                    )
    return None
