"""
Module: launcher.gui_qt.widgets.info_bars

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.info_bars.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.info_bars UI.

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
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from launcher.gui_qt import theme


def _create_icon(icon_name: str, color_hex: str, size: int = 14) -> QLabel:
    lbl = QLabel()
    icon_path = Path(__file__).parent.parent / "icons" / f"{icon_name}.svg"
    if icon_path.exists():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        with open(icon_path, encoding="utf-8") as f:
            svg_data = f.read().replace("currentColor", color_hex)
            renderer = QSvgRenderer(svg_data.encode("utf-8"))
            renderer.render(painter)
        painter.end()
        lbl.setPixmap(pixmap)
    return lbl


class AdminBar(QWidget):
    reset_password_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AdminBar {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(10)

        # Icon
        layout.addWidget(_create_icon("key", theme.TEXT_3))

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        lbl_title = QLabel("ADMIN")
        lbl_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {theme.TEXT_3}; letter-spacing: 0.07em;"
        )
        lbl_val = QLabel("admin · ••••••••")
        lbl_val.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_2};")
        lbl_val.setProperty("class", "mono")

        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_val)
        layout.addLayout(text_layout, 1)

        # Button
        self.btn_reset = QPushButton("Reset Password")
        self.btn_reset.setObjectName("link")
        self.btn_reset.setStyleSheet(f"""
            QPushButton#link {{
                background: transparent;
                border: none;
                color: {theme.ACCENT};
                font-weight: 600;
                font-size: 11.5px;
                padding: 4px 6px;
                border-radius: 6px;
            }}
            QPushButton#link:hover {{
                background-color: rgba(242, 181, 68, 0.12);
            }}
        """)
        self.btn_reset.clicked.connect(self.reset_password_clicked.emit)
        layout.addWidget(self.btn_reset)


class EnvironmentBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            EnvironmentBar {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(10)

        # Icon
        layout.addWidget(_create_icon("box", theme.TEXT_3))

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        lbl_title = QLabel("ENVIRONMENT")
        lbl_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {theme.TEXT_3}; letter-spacing: 0.07em;"
        )

        # Status layout (Icon + Text)
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(5)
        self.status_layout.setAlignment(Qt.AlignLeft)

        self.status_icon = _create_icon("check", theme.SUCCESS, 13)
        self.lbl_status = QLabel("Python libs · MPV OK")
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {theme.SUCCESS};")

        self.status_layout.addWidget(self.status_icon)
        self.status_layout.addWidget(self.lbl_status)

        text_layout.addWidget(lbl_title)
        text_layout.addLayout(self.status_layout)
        layout.addLayout(text_layout, 1)

    def set_status(self, missing: list[str], mpv_ok: bool):
        if not missing and mpv_ok:
            status_text = "✓ Python Libraries: OK  ·  ✓ MPV Audio Player: OK"
            color = theme.SUCCESS
            icon = "check"
        else:
            parts = []
            if missing:
                parts.append(f"✗ Missing libraries: {', '.join(missing)}")
            else:
                parts.append("✓ Python Libraries: OK")
            if not mpv_ok:
                parts.append("✗ MPV Player missing from PATH")
            else:
                parts.append("✓ MPV Player: OK")
            status_text = "  ·  ".join(parts)
            color = theme.DANGER
            icon = "x"

        self.lbl_status.setText(status_text)
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {color};")

        # Update icon
        new_icon = _create_icon(icon, color, 13)

        # Replace old icon widget
        old_icon = self.status_layout.takeAt(0).widget()
        if old_icon:
            old_icon.deleteLater()
        self.status_layout.insertWidget(0, new_icon)
