"""
Module: launcher.gui_qt.widgets.console

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.console.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.console UI.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    GUI Thread only.
"""

import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from launcher.gui_qt import theme


class Console(QWidget):
    # This signal acts as a thread-safe boundary. Background threads emit this,
    # and the Qt event loop marshals it to the main thread's _on_log_signal slot.
    log_signal = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            Console {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"border-bottom: 1px solid {theme.BORDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 14, 0)
        header_layout.setSpacing(8)

        # Title
        icon_path = Path(__file__).parent.parent / "icons" / "terminal.svg"
        if icon_path.exists():
            lbl_icon = QLabel()
            pixmap = QPixmap(13, 13)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", theme.TEXT_3)
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter)
            painter.end()
            lbl_icon.setPixmap(pixmap)
            header_layout.addWidget(lbl_icon)

        lbl_title = QLabel("CONSOLE")
        lbl_title.setFixedWidth(70)
        lbl_title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {theme.TEXT_3}; border: none;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addSpacing(6)

        self.lbl_count = QLabel("0 lines")
        self.lbl_count.setProperty("class", "mono")
        self.lbl_count.setStyleSheet(
            f"font-size: 10.5px; color: {theme.TEXT_3}; background-color: {theme.BG_ELEVATED}; padding: 1px 7px; border-radius: 9px; border: none;"
        )
        header_layout.addWidget(self.lbl_count)
        header_layout.addStretch()

        # Clear Button
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: none;
                border: none;
                color: {theme.TEXT_3};
                font-size: 11.5px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {theme.TEXT_1};
            }}
        """)
        self.btn_clear.clicked.connect(self.clear_log)
        header_layout.addWidget(self.btn_clear)

        layout.addWidget(header)

        # Body (QPlainTextEdit)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                color: {theme.TEXT_1};
                border: none;
                padding: 12px 14px;
                font-size: 11.5px;
                line-height: 1.85;
            }}
        """)

        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)

        layout.addWidget(self.text_edit)

        self.line_count = 0

        # Wire thread-safe signal
        self.log_signal.connect(self._on_log_signal)

    def append_log(self, msg: str, tag: str = "", is_end: bool = False):
        """Thread-safe interface for appending logs."""
        self.log_signal.emit(msg, tag, is_end)

    @Slot(str, str, bool)
    def _on_log_signal(self, msg: str, tag: str, is_end: bool):
        # Auto-tag logic ported from log_view.py
        if tag == "":
            low_msg = msg.lower()
            if (
                "error" in low_msg
                or "failed" in low_msg
                or "cannot" in low_msg
                or "timeout" in low_msg
            ):
                tag = "err"
            elif (
                "ok" in low_msg
                or "ready" in low_msg
                or "listening" in low_msg
                or "cleared" in low_msg
                or "created" in low_msg
            ):
                tag = "ok"
            elif (
                "starting" in low_msg
                or "stopping" in low_msg
                or "restarting" in low_msg
                or "killing" in low_msg
            ):
                tag = "accent"

        color = theme.TEXT_1
        if tag == "ok":
            color = theme.SUCCESS
        elif tag == "err":
            color = theme.DANGER
        elif tag == "accent":
            color = theme.ACCENT
        elif tag == "dim":
            color = theme.TEXT_3

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        ts_text = f"[{ts}] "

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Apply timestamp formatting
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(theme.TEXT_3))
        cursor.insertText(ts_text, fmt)

        # Apply message formatting
        fmt.setForeground(QColor(color))
        cursor.insertText(msg + ("\n" if not is_end else ""), fmt)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        self.line_count += 1
        self.lbl_count.setText(f"{self.line_count} lines")

    def clear_log(self):
        self.text_edit.clear()
        self.line_count = 0
        self.lbl_count.setText("0 lines")
