"""
Module: launcher.gui_qt.widgets.quicklinks

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.quicklinks.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.quicklinks UI.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    GUI Thread only.
"""

import webbrowser
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from launcher.gui_qt import theme


class QuickLinks(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.base_port = 8765

        self.btn_client = self._make_chip(
            "Client Portal", "box", "/"
        )  # Usually box/globe? We have 'box' and 'smartphone' but I'll use box as a fallback, wait, mockup uses box for Client Portal.
        self.btn_admin = self._make_chip("Admin Console", "key", "/admin")
        self.btn_health = self._make_chip("System Health", "activity", "/health")
        self.btn_metrics = self._make_chip("Metrics", "bar-chart", "/metrics")

        layout.addWidget(self.btn_client)
        layout.addWidget(self.btn_admin)
        layout.addWidget(self.btn_health)
        layout.addWidget(self.btn_metrics)
        layout.addStretch()

    def _make_chip(self, text: str, icon_name: str, route: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("chip")
        btn.setFixedHeight(28)
        btn.setStyleSheet(f"""
            QPushButton#chip {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 14px;
                color: {theme.TEXT_2};
                font-weight: 600;
                font-size: 12px;
                padding: 0 13px 0 10px;
            }}
            QPushButton#chip:hover {{
                border-color: {theme.BORDER_STRONG};
                color: {theme.TEXT_1};
                background-color: {theme.BG_ELEVATED_2};
            }}
        """)

        icon_path = Path(__file__).parent.parent / "icons" / f"{icon_name}.svg"
        if icon_path.exists():
            pixmap = QPixmap(13, 13)
            from PySide6.QtGui import QColor, Qt

            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.TEXT_3)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()

            # TODO: Handle hover color change (to ACCENT) via event filter or QIcon modes if needed.
            # For now static color is acceptable for MVP.

            btn.setIcon(QIcon(pixmap))

        btn.clicked.connect(lambda: webbrowser.open(f"http://localhost:{self.base_port}{route}"))
        return btn

    def set_base_port(self, port: int):
        self.base_port = port
