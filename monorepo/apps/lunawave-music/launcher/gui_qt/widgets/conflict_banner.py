"""
Module: launcher.gui_qt.widgets.conflict_banner

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.conflict_banner.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.conflict_banner UI.

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
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from launcher.gui_qt import theme


class ConflictBanner(QWidget):
    kill_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            ConflictBanner {
                background-color: rgba(245, 165, 36, 0.14); /* WARN with alpha */
                border: 1px solid rgba(245, 165, 36, 0.35);
                border-radius: 10px;
            }
        """)
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Icon
        self.icon_lbl = QLabel()
        icon_path = Path(__file__).parent.parent / "icons" / "alert-triangle.svg"
        if icon_path.exists():
            from PySide6.QtGui import QColor, QPainter, QPixmap
            from PySide6.QtSvg import QSvgRenderer

            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.WARN)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            self.icon_lbl.setPixmap(pixmap)

        layout.addWidget(self.icon_lbl)

        # Text
        self.text_lbl = QLabel("Port dipakai proses lain.")
        self.text_lbl.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_1};")
        layout.addWidget(self.text_lbl, 1)  # stretch 1

        # Kill Button
        self.btn_kill = QPushButton("Kill Process")
        self.btn_kill.setObjectName("danger-outline")
        self.btn_kill.setFixedHeight(28)
        self.btn_kill.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid rgba(248, 113, 113, 0.4);
                color: {theme.DANGER};
                font-weight: 600;
                font-size: 12px;
                padding: 0 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: rgba(248, 113, 113, 0.12);
                border: 1px solid rgba(248, 113, 113, 0.5);
            }}
        """)

        # Add icon to button
        x_icon_path = Path(__file__).parent.parent / "icons" / "x.svg"
        if x_icon_path.exists():
            from PySide6.QtGui import QIcon, QPainter, QPixmap
            from PySide6.QtSvg import QSvgRenderer

            pixmap = QPixmap(13, 13)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(x_icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.DANGER)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            self.btn_kill.setIcon(QIcon(pixmap))

        self.btn_kill.clicked.connect(self.kill_requested.emit)
        layout.addWidget(self.btn_kill)

    def set_conflict(self, port: int, pid: int | None):
        if pid:
            self.text_lbl.setText(
                f"Port <b>:{port}</b> sedang dipakai oleh <b>PID {pid}</b>. Hentikan proses tersebut."
            )
            self.btn_kill.setText(f"Kill PID {pid}")
        else:
            self.text_lbl.setText(f"Port <b>:{port}</b> sedang dipakai oleh proses lain.")
            self.btn_kill.setText("Kill Port Owner")
