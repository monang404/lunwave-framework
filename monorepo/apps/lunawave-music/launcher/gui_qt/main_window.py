"""
Module: launcher.gui_qt.main_window

Purpose:
    PySide6 GUI component for launcher.gui_qt.main_window.

Responsibilities:
    - Render and manage launcher.gui_qt.main_window UI.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    GUI Thread only.
"""

import os
import sys
import webbrowser
from pathlib import Path

import structlog
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from launcher import network
from launcher.gui_qt import theme
from launcher.gui_qt.widgets.conflict_banner import ConflictBanner
from launcher.gui_qt.widgets.console import Console
from launcher.gui_qt.widgets.info_bars import AdminBar, EnvironmentBar
from launcher.gui_qt.widgets.quicklinks import QuickLinks
from launcher.gui_qt.widgets.ready_toast import ReadyToast
from launcher.gui_qt.widgets.status_hero import StatusHero
from launcher.gui_qt.widgets.titlebar import TitleBar
from launcher.gui_qt.widgets.toolbar import Toolbar
from launcher.server_lifecycle import ServerLifecycle

logger = structlog.get_logger(component="launcher.gui_qt.main_window")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SERVER_PORT = int(os.environ.get("LUNAWAVE_PORT", os.environ.get("YTGUI_PORT", 8765)))


class ServerManagerQt(QMainWindow):
    # Signals for thread-safety
    sig_log = Signal(str, str, bool)
    sig_ready = Signal(int)
    sig_deps_checked = Signal(list, bool)
    sig_starting = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("LunaWave — Server Manager")
        self.resize(880, 720)
        self.setMinimumSize(520, 600)

        # Center on screen
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

        # Load QSS theme
        qss_path = Path(__file__).parent / "theme.qss"
        if qss_path.exists():
            with open(qss_path, encoding="utf-8") as f:
                self.setStyleSheet(f.read())

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.central_widget = QWidget()
        self.central_widget.setObjectName("central_widget")
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setCentralWidget(self.central_widget)

        self._build_ui()

        self._closing = False
        self._explicit_state = None  # to override poll state during transitions (like starting)
        self._conflict_pid = None

        # Initialize Lifecycle
        self.lifecycle = ServerLifecycle(
            BASE_DIR,
            on_log=lambda msg, tag="", is_end=False: self.sig_log.emit(msg, tag, is_end),
            on_ready=self.sig_ready.emit,
            on_deps_checked=self.sig_deps_checked.emit,
            on_starting=self.sig_starting.emit,
        )

        # Wire Signals
        self.sig_log.connect(self.console._on_log_signal)
        self.sig_ready.connect(self.toast.show_toast)
        self.sig_deps_checked.connect(self.env_bar.set_status)
        self.sig_starting.connect(self._on_starting_signal)

        # Polling timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._refresh_status)
        self.poll_timer.start(2000)

        self.lifecycle.run_dependency_check()
        self._refresh_status()

    def _build_ui(self):
        # 1. Custom Title Bar
        self.titlebar = TitleBar(self)
        self.main_layout.addWidget(self.titlebar)

        # Container for the rest of the UI (to preserve margins)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(22, 10, 22, 18)
        content_layout.setSpacing(16)

        self.main_layout.addWidget(content_widget)

        # 1.5 Content Header (LunaWave Title)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_icon = QLabel()
        icon_path = Path(__file__).parent / "icons" / "moon.svg"
        if icon_path.exists():
            from PySide6.QtGui import QPainter, QPixmap
            from PySide6.QtSvg import QSvgRenderer

            pixmap = QPixmap(28, 28)
            from PySide6.QtGui import Qt

            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.ACCENT)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            lbl_icon.setPixmap(pixmap)
        header_layout.addWidget(lbl_icon)

        title_vlayout = QVBoxLayout()
        title_vlayout.setSpacing(0)

        lbl_main_title = QLabel("LunaWave")
        lbl_main_title.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {theme.TEXT_1}; letter-spacing: 0.02em;"
        )
        lbl_sub_title = QLabel("Server Manager")
        lbl_sub_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {theme.TEXT_3};")

        title_vlayout.addWidget(lbl_main_title)
        title_vlayout.addWidget(lbl_sub_title)

        header_layout.addLayout(title_vlayout)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        content_layout.addSpacing(6)

        # 2. Status Hero
        self.hero = StatusHero()
        self.hero.input_port.setText(str(SERVER_PORT))
        self.hero.port_changed.connect(self._on_port_changed)
        content_layout.addWidget(self.hero)

        # 2.5. Toolbar
        self.toolbar = Toolbar()
        self.toolbar.start_clicked.connect(self._on_start)
        self.toolbar.stop_clicked.connect(self._on_stop)
        self.toolbar.restart_clicked.connect(self._on_restart)
        self.toolbar.open_clicked.connect(self._on_open)
        self.toolbar.logs_clicked.connect(self._on_open_dashboard)
        content_layout.addWidget(self.toolbar)

        # 3. Conflict Banner
        self.banner = ConflictBanner()
        self.banner.kill_requested.connect(self._on_kill_conflict)
        content_layout.addWidget(self.banner)

        # 4. Info Bars
        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)
        self.admin_bar = AdminBar()
        self.admin_bar.reset_password_clicked.connect(self._on_reset_password)
        self.env_bar = EnvironmentBar()
        info_layout.addWidget(self.admin_bar)
        info_layout.addWidget(self.env_bar)
        content_layout.addLayout(info_layout)

        # 5. Quick Links
        self.quicklinks = QuickLinks()
        self.quicklinks.set_base_port(SERVER_PORT)
        content_layout.addWidget(self.quicklinks)

        # 6. Console
        self.console = Console()
        content_layout.addWidget(self.console)

        # 7. Toast (Overlay, parent=self)
        self.toast = ReadyToast(self)

    def _on_port_changed(self, port: int):
        self.quicklinks.set_base_port(port)
        self._refresh_status()

    def server_port(self) -> int:
        try:
            return int(self.hero.input_port.text())
        except ValueError:
            return 8765

    @Slot()
    def _on_starting_signal(self):
        self._explicit_state = "starting"
        self._refresh_status()

    def _refresh_status(self):
        if self._closing:
            return

        port = self.server_port()
        running = self.lifecycle.is_running()

        if self._explicit_state == "starting" and not running:
            # We are waiting for the thread to actually spin up the process
            self.hero.set_state("starting")
            self.hero.set_port_editable(False)
            self.hero.set_stats("—", "—")
            self.banner.setVisible(False)
            self.toolbar.set_enabled_map(
                {"start": False, "stop": True, "restart": False, "open": False, "logs": False}
            )
            return

        # If we got here and running is True, or starting finished (failed/succeeded)
        self._explicit_state = None

        if running:
            self.hero.set_state("running")
            self.hero.set_port_editable(False)
            pid = "—"
            if self.lifecycle.server_process and self.lifecycle.server_process.process:
                pid = str(self.lifecycle.server_process.process.pid)
            self.hero.set_stats(pid, "Aktif")
            self.banner.setVisible(False)
            self.toolbar.set_enabled_map(
                {"start": False, "stop": True, "restart": True, "open": True, "logs": True}
            )
        else:
            in_use = False
            conflict_pid = None
            if network.check_port_in_use(port):
                in_use = True
                conflict_pid = network.get_pid_occupying_port(port)

            if in_use:
                self.hero.set_state("conflict")
                self.hero.set_port_editable(True)
                self.hero.set_stats("—", "—")
                self._conflict_pid = conflict_pid
                self.banner.set_conflict(port, conflict_pid)
                self.banner.setVisible(True)
                self.toolbar.set_enabled_map(
                    {"start": False, "stop": False, "restart": False, "open": True, "logs": False}
                )
            else:
                self.hero.set_state("stopped")
                self.hero.set_port_editable(True)
                self.hero.set_stats("—", "—")
                self.banner.setVisible(False)
                self.toolbar.set_enabled_map(
                    {"start": True, "stop": False, "restart": False, "open": False, "logs": False}
                )

    def _on_start(self):
        self.lifecycle.start(self.server_port())

    def _on_stop(self):
        self.lifecycle.stop()
        self._refresh_status()

    def _on_restart(self):
        self.lifecycle.restart(self.server_port())

    def _on_open(self):
        webbrowser.open(f"http://localhost:{self.server_port()}")

    def _on_open_dashboard(self):
        webbrowser.open(f"http://localhost:{self.server_port()}/admin/logs")

    def _on_reset_password(self):
        # As per the previous refactor in auth_panel.py, resetting password just opens the browser
        webbrowser.open(f"http://localhost:{self.server_port()}/admin/reset-password")

    def _on_kill_conflict(self):
        self.lifecycle.kill_conflict(self.server_port())
        self._refresh_status()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.show_toast(self.toast.port)  # Repositions it

    def closeEvent(self, event: QCloseEvent):
        self._closing = True
        self.poll_timer.stop()
        if self.lifecycle.is_running():
            try:
                self.lifecycle.server_process.stop()
            except Exception as e:
                logger.debug("shutdown_stop_failed", error=str(e))
        event.accept()
