import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from launcher.gui_qt.main_window import ServerManagerQt


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_initialization(qapp):
    # Test that the main window initializes without crashing
    window = ServerManagerQt()
    assert window.windowTitle() == "LunaWave — Server Manager"

    # Check widgets exist
    assert window.hero is not None
    assert window.console is not None
    assert window.toolbar is not None

    # Check default state
    assert window.hero.input_port.text() != ""
    assert window.hero.lbl_state.text() == "Stopped"


def test_signal_marshaling(qapp, qtbot):
    window = ServerManagerQt()
    qtbot.addWidget(window)

    # Emit signal from "background"
    with qtbot.waitSignal(window.sig_log, timeout=1000):
        window.sig_log.emit("Test log message", "ok", True)

    # Check if console received it
    assert "Test log message" in window.console.text_edit.toPlainText()
