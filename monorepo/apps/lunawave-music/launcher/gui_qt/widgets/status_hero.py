"""
Module: launcher.gui_qt.widgets.status_hero

Purpose:
    PySide6 GUI component for launcher.gui_qt.widgets.status_hero.

Responsibilities:
    - Render and manage launcher.gui_qt.widgets.status_hero UI.

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

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from launcher.gui_qt import theme


class StateRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)

        self._border_scale = 1.0
        self._border_opacity = 0.0
        self._rotation_angle = 0.0
        self._ring_color = QColor(theme.TEXT_3)
        self._icon_name = "power"

        # Animations
        self._pulse_anim_scale = QPropertyAnimation(self, b"borderScale")
        self._pulse_anim_scale.setDuration(2200)
        self._pulse_anim_scale.setStartValue(0.92)
        self._pulse_anim_scale.setKeyValueAt(0.8, 1.35)
        self._pulse_anim_scale.setEndValue(1.35)
        self._pulse_anim_scale.setLoopCount(-1)

        self._pulse_anim_opacity = QPropertyAnimation(self, b"borderOpacity")
        self._pulse_anim_opacity.setDuration(2200)
        self._pulse_anim_opacity.setStartValue(0.55)
        self._pulse_anim_opacity.setKeyValueAt(0.8, 0.0)
        self._pulse_anim_opacity.setEndValue(0.0)
        self._pulse_anim_opacity.setLoopCount(-1)

        self._spin_anim = QPropertyAnimation(self, b"rotationAngle")
        self._spin_anim.setDuration(1100)
        self._spin_anim.setStartValue(0.0)
        self._spin_anim.setEndValue(360.0)
        self._spin_anim.setLoopCount(-1)

    def getBorderScale(self):
        return self._border_scale

    def setBorderScale(self, scale):
        self._border_scale = scale
        self.update()

    borderScale = Property(float, getBorderScale, setBorderScale)

    def getBorderOpacity(self):
        return self._border_opacity

    def setBorderOpacity(self, opacity):
        self._border_opacity = opacity
        self.update()

    borderOpacity = Property(float, getBorderOpacity, setBorderOpacity)

    def getRotationAngle(self):
        return self._rotation_angle

    def setRotationAngle(self, angle):
        self._rotation_angle = angle
        self.update()

    rotationAngle = Property(float, getRotationAngle, setRotationAngle)

    def set_appearance(self, color_hex: str, icon_name: str, pulse: bool, spin: bool):
        self._ring_color = QColor(color_hex)
        self._icon_name = icon_name

        if pulse:
            self._pulse_anim_scale.start()
            self._pulse_anim_opacity.start()
        else:
            self._pulse_anim_scale.stop()
            self._pulse_anim_opacity.stop()
            self._border_opacity = 0.0

        if spin:
            self._spin_anim.start()
        else:
            self._spin_anim.stop()
            self._rotation_angle = 0.0

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Base ring
        rect = QRectF(3, 3, 40, 40)
        painter.setBrush(QColor(theme.BG_SURFACE))
        painter.setPen(QPen(QColor(theme.BORDER_STRONG), 1))
        painter.drawEllipse(rect)

        # Pulse ring
        if self._border_opacity > 0:
            center = rect.center()
            pulse_radius = 20 * self._border_scale
            pulse_color = QColor(theme.SUCCESS)
            pulse_color.setAlphaF(self._border_opacity)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(pulse_color, 1))
            painter.drawEllipse(center, pulse_radius, pulse_radius)

        # Draw icon
        painter.translate(rect.center())
        painter.rotate(self._rotation_angle)
        painter.translate(-rect.center())

        icon_path = Path(__file__).parent.parent / "icons" / f"{self._icon_name}.svg"
        from PySide6.QtSvg import QSvgRenderer

        if icon_path.exists():
            # Since the SVG uses stroke="currentColor", we need a trick in QPainter
            # Actually QSvgRenderer doesn't respect currentColor out of the box unless we replace it.
            # But wait, QPainter can't easily recolor QSvgRenderer unless we read SVG and replace.
            # For this MVP, we can read SVG string, replace 'currentColor' with hex, and load it.
            with open(icon_path, encoding="utf-8") as f:
                svg_data = f.read().replace("currentColor", self._ring_color.name())
                renderer = QSvgRenderer(svg_data.encode("utf-8"))
                renderer.render(painter, QRectF(13, 13, 20, 20))
        painter.end()


class StatusHero(QWidget):
    port_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("elevated")
        self.setFixedHeight(82)

        # Use QSS for the container styles
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#elevated {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(20)

        # Left side
        left_layout = QHBoxLayout()
        left_layout.setSpacing(14)

        self.state_ring = StateRing()
        left_layout.addWidget(self.state_ring)

        state_copy_layout = QVBoxLayout()
        state_copy_layout.setSpacing(2)
        state_copy_layout.setAlignment(Qt.AlignVCenter)

        self.lbl_state = QLabel("Stopped")
        self.lbl_state.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_1};")
        self.lbl_sub = QLabel("Port 8765 bebas dipakai")
        self.lbl_sub.setStyleSheet(f"font-size: 12.5px; color: {theme.TEXT_2};")

        state_copy_layout.addWidget(self.lbl_state)
        state_copy_layout.addWidget(self.lbl_sub)
        left_layout.addLayout(state_copy_layout)

        layout.addLayout(left_layout)
        layout.addStretch()

        # Right side stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(26)

        # Port
        port_layout = QVBoxLayout()
        port_layout.setSpacing(4)
        lbl_port = QLabel("PORT")
        lbl_port.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {theme.TEXT_3}; letter-spacing: 0.08em;"
        )
        self.input_port = QLineEdit("8765")
        self.input_port.setFixedWidth(52)
        self.input_port.setAlignment(Qt.AlignCenter)
        self.input_port.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER_STRONG};
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
                color: {theme.TEXT_1};
            }}
            QLineEdit:disabled {{
                color: {theme.TEXT_3};
            }}
        """)
        self.input_port.editingFinished.connect(self._on_port_edited)
        port_layout.addWidget(lbl_port)
        port_layout.addWidget(self.input_port)
        stats_layout.addLayout(port_layout)

        # PID
        pid_layout = QVBoxLayout()
        pid_layout.setSpacing(4)
        lbl_pid = QLabel("PID")
        lbl_pid.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {theme.TEXT_3}; letter-spacing: 0.08em;"
        )
        self.val_pid = QLabel("—")
        self.val_pid.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {theme.TEXT_1};")
        self.val_pid.setProperty("class", "mono")
        pid_layout.addWidget(lbl_pid)
        pid_layout.addWidget(self.val_pid)
        stats_layout.addLayout(pid_layout)

        # Uptime
        uptime_layout = QVBoxLayout()
        uptime_layout.setSpacing(4)
        lbl_uptime = QLabel("UPTIME")
        lbl_uptime.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {theme.TEXT_3}; letter-spacing: 0.08em;"
        )
        self.val_uptime = QLabel("—")
        self.val_uptime.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {theme.TEXT_1};")
        self.val_uptime.setProperty("class", "mono")
        uptime_layout.addWidget(lbl_uptime)
        uptime_layout.addWidget(self.val_uptime)
        stats_layout.addLayout(uptime_layout)

        layout.addLayout(stats_layout)

    def _on_port_edited(self):
        try:
            port = int(self.input_port.text())
            self.port_changed.emit(port)
        except ValueError:
            pass

    def set_port_editable(self, editable: bool):
        self.input_port.setEnabled(editable)

    def set_stats(self, pid: str, uptime: str):
        self.val_pid.setText(pid)
        self.val_uptime.setText(uptime)

    def set_state(self, name: str):
        if name == "stopped":
            self.state_ring.set_appearance(theme.TEXT_3, "power", pulse=False, spin=False)
            self.lbl_state.setText("Stopped")
            self.lbl_sub.setText("Port bebas dipakai")
        elif name == "starting":
            self.state_ring.set_appearance(theme.ACCENT, "loader", pulse=False, spin=True)
            self.lbl_state.setText("Starting…")
            self.lbl_sub.setText("Menjalankan proses server")
        elif name == "running":
            self.state_ring.set_appearance(theme.SUCCESS, "check", pulse=True, spin=False)
            self.lbl_state.setText("Running")
            self.lbl_sub.setText("Sehat — merespons normal")
        elif name == "conflict":
            self.state_ring.set_appearance(theme.WARN, "alert-triangle", pulse=False, spin=False)
            self.lbl_state.setText("Conflict")
            self.lbl_sub.setText("Port sudah dipakai proses lain")
