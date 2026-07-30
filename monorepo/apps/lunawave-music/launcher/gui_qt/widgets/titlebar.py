"""
Module: launcher.gui_qt.widgets.titlebar

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.titlebar.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.titlebar UI.

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

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from launcher.gui_qt import theme


class TitleBar(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setFixedHeight(38)
        self.setStyleSheet("background: transparent;")

        self._start_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # MacOS style dots
        dot_layout = QHBoxLayout()
        dot_layout.setSpacing(8)

        self.btn_close = self._make_dot("#FF5F56", "#E0443E")
        self.btn_close.clicked.connect(self.parent_window.close)

        self.btn_min = self._make_dot("#FFBD2E", "#DEA123")
        self.btn_min.clicked.connect(self.parent_window.showMinimized)

        self.btn_max = self._make_dot("#27C93F", "#1AAB29")
        # For this app, window isn't really meant to be maximized heavily, but let's allow it or just ignore.
        self.btn_max.clicked.connect(self._toggle_max)

        dot_layout.addWidget(self.btn_close)
        dot_layout.addWidget(self.btn_min)
        dot_layout.addWidget(self.btn_max)

        layout.addLayout(dot_layout)
        layout.addStretch(1)

        # Title (Centered)
        self.lbl_title = QLabel("LunaWave Server Manager")
        self.lbl_title.setStyleSheet(
            f"color: {theme.TEXT_3}; font-size: 11px; font-weight: 600; font-family: 'Inter', sans-serif;"
        )
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        layout.addStretch(1)

        # OS Chip
        self.lbl_chip = QLabel("Termux - HyperOS")
        self.lbl_chip.setStyleSheet(
            f"color: {theme.TEXT_3}; background-color: transparent; border: none; font-size: 10.5px; font-weight: 600;"
        )
        layout.addWidget(self.lbl_chip)

    def _make_dot(self, color: str, hover_color: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(12, 12)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)
        return btn

    def _toggle_max(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._start_pos is not None:
            delta = event.globalPosition().toPoint() - self._start_pos
            self.parent_window.move(self.parent_window.pos() + delta)
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._start_pos = None
