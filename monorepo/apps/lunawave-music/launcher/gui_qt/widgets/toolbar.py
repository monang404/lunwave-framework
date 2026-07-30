"""
Module: launcher.gui_qt.widgets.toolbar

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.toolbar.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.toolbar UI.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    GUI Thread only.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from launcher.gui_qt import theme


class Toolbar(QWidget):
    start_clicked = Signal()
    stop_clicked = Signal()
    restart_clicked = Signal()
    open_clicked = Signal()
    logs_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_start = self._make_btn("Start", "play", "primary")
        self.btn_stop = self._make_btn("Stop", "square", "danger-outline")
        self.btn_restart = self._make_btn("Restart", "rotate-ccw", None)
        self.btn_open = self._make_btn("Open Portal", "external-link", None)
        self.btn_logs = self._make_btn("Logs", "terminal", None)

        self.btn_start.clicked.connect(self.start_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_restart.clicked.connect(self.restart_clicked.emit)
        self.btn_open.clicked.connect(self.open_clicked.emit)
        self.btn_logs.clicked.connect(self.logs_clicked.emit)

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_restart)
        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_logs)

    def _make_btn(self, text: str, icon_name: str, object_name: str | None) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        if object_name:
            btn.setObjectName(object_name)

        icon_path = Path(__file__).parent.parent / "icons" / f"{icon_name}.svg"
        if icon_path.exists():
            # Color is tricky because it depends on state/theme.
            # We'll use a neutral text color or currentColor replacing based on button type
            color = theme.TEXT_2
            if object_name == "primary":
                color = "#1A1206"
            elif object_name == "danger-outline":
                color = theme.DANGER

            pixmap = QPixmap(15, 15)
            pixmap.fill(QColor(0, 0, 0, 0))  # transparent
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", color)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            btn.setIcon(QIcon(pixmap))

        return btn

    def set_enabled_map(self, states: dict[str, bool]):
        if "start" in states:
            self.btn_start.setEnabled(states["start"])
        if "stop" in states:
            self.btn_stop.setEnabled(states["stop"])
        if "restart" in states:
            self.btn_restart.setEnabled(states["restart"])
        if "open" in states:
            self.btn_open.setEnabled(states["open"])
        if "logs" in states:
            self.btn_logs.setEnabled(states["logs"])
