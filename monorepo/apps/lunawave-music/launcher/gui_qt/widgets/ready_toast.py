"""
Module: launcher.gui_qt.widgets.ready_toast

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.ready_toast.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.ready_toast UI.

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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from launcher.gui_qt import theme


class ReadyToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ReadyToast {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_STRONG};
                border-radius: 10px;
            }}
        """)
        # We'll use fixed size for the toast as per mockup (300px wide)
        self.setFixedWidth(300)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        # Icon Box
        self.icon_box = QWidget()
        self.icon_box.setFixedSize(30, 30)
        self.icon_box.setAttribute(Qt.WA_StyledBackground, True)
        self.icon_box.setStyleSheet("""
            background-color: rgba(52, 211, 153, 0.12); /* success-dim */
            border-radius: 8px;
        """)
        icon_layout = QVBoxLayout(self.icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel()
        icon_path = Path(__file__).parent.parent / "icons" / "check.svg"
        if icon_path.exists():
            pixmap = QPixmap(15, 15)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.SUCCESS)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            icon_lbl.setPixmap(pixmap)
        icon_layout.addWidget(icon_lbl)

        layout.addWidget(self.icon_box)

        # Body
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(2)

        self.lbl_title = QLabel("Server aktif di port 8765")
        self.lbl_title.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {theme.TEXT_1};")

        lbl_desc = QLabel("Portal login siap diakses. Buka untuk mengelola room.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 11.5px; color: {theme.TEXT_2}; line-height: 1.5;")
        lbl_desc.setContentsMargins(0, 0, 0, 6)

        body_layout.addWidget(self.lbl_title)
        body_layout.addWidget(lbl_desc)

        # Actions
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setAlignment(Qt.AlignLeft)

        btn_open = QPushButton("Buka Login")
        btn_open.setObjectName("primary")
        btn_open.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px; font-weight: 600; padding: 6px 10px; border-radius: 6px;
                background-color: {theme.ACCENT}; color: #1A1206; border: 1px solid {theme.ACCENT};
            }}
            QPushButton:hover {{
                background-color: #FFD98A; border-color: #FFD98A;
            }}
        """)
        btn_open.clicked.connect(self._on_open_clicked)
        actions_layout.addWidget(btn_open)

        btn_close = QPushButton("Tutup")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px; font-weight: 600; padding: 6px 10px; border-radius: 6px;
                background-color: {theme.BG_SURFACE}; color: {theme.TEXT_2}; border: 1px solid {theme.BORDER};
            }}
            QPushButton:hover {{
                color: {theme.TEXT_1}; border-color: {theme.BORDER_STRONG};
            }}
        """)
        btn_close.clicked.connect(self.hide)
        actions_layout.addWidget(btn_close)

        body_layout.addLayout(actions_layout)
        layout.addLayout(body_layout, 1)

        self.port = 8765

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_toast(self, port: int):
        self.port = port
        self.lbl_title.setText(f"Server aktif di port {port}")

        # Ensure it's correctly positioned if parent resizes
        self.adjustSize()
        if self.parentWidget():
            parent_rect = self.parentWidget().rect()
            # Position at bottom right, with some margins
            x = parent_rect.width() - self.width() - 22
            y = parent_rect.height() - self.height() - 22
            self.move(x, max(0, y))

        self.setVisible(True)
        self.raise_()

        # 4.5s auto-dismiss
        self._timer.start(4500)

    def _on_open_clicked(self):
        webbrowser.open(f"http://localhost:{self.port}/admin")
        self.hide()
