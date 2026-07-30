"""
Module: launcher.__main__

Purpose:
    Entry point for the LunaWave launcher when executed as a package.

Inputs:
    None (no CLI arguments).

Outputs:
    Tkinter ServerManager GUI window.

Side Effects:
    Opens the desktop GUI; exits with code 1 if tkinter is unavailable.

CLI:
    python -m launcher

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import sys


def main():
    try:
        from pathlib import Path

        import PySide6  # noqa: F401
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication

        from launcher.gui_qt.main_window import ServerManagerQt

        # Windows taskbar icon fix
        if sys.platform == "win32":
            import ctypes

            myappid = "lunawave.server.manager.1"
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        app = QApplication(sys.argv)

        icon_path = Path(__file__).parent / "gui_qt" / "icons" / "app_icon.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        manager = ServerManagerQt()
        manager.show()
        sys.exit(app.exec())
    except ImportError:
        print(
            "GUI not available (no PySide6). Please run `python main.py` directly or use `start.sh` on headless environments like Termux.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
