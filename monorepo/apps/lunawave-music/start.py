#!/usr/bin/env python3
"""
Module: start

Purpose:
    GUI entry point that opens the LunaWave Server Manager desktop window.

Inputs:
    None.

Outputs:
    Tkinter ServerManager window.

Side Effects:
    Launches the GUI application; exits with code 1 if tkinter is missing.

CLI:
    python start.py

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - launcher.__main__

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from launcher.__main__ import main

if __name__ == "__main__":
    main()
