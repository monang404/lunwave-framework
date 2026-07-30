"""
Module: launcher.preflight

Purpose:
    Unified preflight check for LunaWave to be called by both start.sh and start.bat.

Depends on:
    - launcher.dep_checker
    - core.log_config

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only.
"""

import argparse
import sys

import structlog

from core.log_categories import LC_LIFECYCLE
from core.log_config import setup_logging
from launcher.dep_checker import DependencyChecker

logger = structlog.get_logger(component="preflight")

# Color constants
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"


def print_info(msg: str):
    print(f"{CYAN}[*]{RESET} {msg}")


def print_ok(msg: str):
    print(f"    {GREEN}[+]{RESET} {msg}")


def print_warn(msg: str):
    print(f"\n{YELLOW}[!] WARNING: {msg}{RESET}\n")


def print_err(msg: str):
    print(f"    {RED}[-]{RESET} {msg}")


def log_result(check: str, result: str):
    # Klasifikasi: SENGAJA TETAP SILENT (bukan best-effort biasa). Blok ini
    # membungkus logger.info(...) itu sendiri -- kalau logging gagal di
    # sini, memanggil logger lagi di except berisiko gagal dengan cara yang
    # sama (atau lebih buruk, rekursi/exception baru) tanpa menambah info
    # yang berguna. print_* di run() sudah memberi feedback ke user via
    # terminal terlepas dari sukses/gagalnya baris log ini.
    try:
        logger.info("preflight_check", category=LC_LIFECYCLE, check=check, result=result)
    except Exception:
        # Logging gagal dibiarkan (lihat klasifikasi di atas)
        pass


def run(host: str, port: int) -> int:
    # Setup logging as early as possible
    try:
        setup_logging()
    except Exception as e:
        print_warn(f"Failed to setup logging: {e}")

    checker = DependencyChecker()
    exit_code = 0

    # 1. Dependency check
    print_info("Checking Python Dependencies...")
    missing, mpv_ok_flag = checker.check_dependencies()
    if missing:
        print_err("Ada modul yang belum terinstall.")
        print_err(f"Missing: {', '.join(missing)}")
        print_err("Jalankan: pip install -r requirements.txt")
        print_warn("Some dependencies are missing.")
        log_result("python_dependencies", "missing")
        exit_code = 1
    else:
        print_ok("All Python dependencies are satisfied.")
        log_result("python_dependencies", "ok")

    # 2. MPV version check
    print_info("Verifying MPV Installation...")
    mpv_ver = checker.mpv_version()
    if mpv_ver:
        print_ok(f"MPV detected ({mpv_ver}).")
        log_result("mpv_installation", "ok")
    else:
        print_err("MPV not found in system PATH or failed to get version!")
        print_err("Termux : pkg install mpv")
        print_err("Debian : sudo apt install mpv")
        print_err("Arch   : sudo pacman -S mpv")
        log_result("mpv_installation", "missing")
        exit_code = 1

    # 3. Port check
    print_info(f"Checking Port {port} on {host}...")
    port_in_use = checker.check_port(host, port)
    if port_in_use:
        print_err(f"Port {port} is currently IN USE by another process.")
        print_warn("Server might fail to start if port cannot be bound.")
        log_result("port_check", "in_use")
        exit_code = 1
    else:
        print_ok(f"Port {port} is free.")
        log_result("port_check", "free")

    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LunaWave Preflight Check")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to check port binding")
    parser.add_argument("--port", type=int, default=8765, help="Port to check binding")
    args = parser.parse_args()

    sys.exit(run(args.host, args.port))
