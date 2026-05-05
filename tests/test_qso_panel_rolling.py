"""P1.16: QSO-Panel 5-Min-Rolling-Window."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch
from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_panel():
    _ensure_app()
    from ui.qso_panel import QSOPanel
    return QSOPanel()


def test_qso_panel_block_timestamps_appended():
    panel = _make_panel()
    initial = len(panel._block_timestamps)
    panel._append_colored("test", "#FFF")
    assert len(panel._block_timestamps) == initial + 1


def test_qso_panel_two_color_timestamp_appended():
    """T1: _append_two_color setzt auch Timestamp."""
    panel = _make_panel()
    initial = len(panel._block_timestamps)
    panel._append_two_color("a", "#F00", "b", "#0F0")
    assert len(panel._block_timestamps) == initial + 1


def test_qso_panel_auto_trim_by_age():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(10):
        with patch('ui.qso_panel.time.time', return_value=base + i * 60):
            panel._append_colored(f"test{i}", "#FFF")
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) <= 5


def test_qso_panel_trim_below_threshold():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(4):
        with patch('ui.qso_panel.time.time', return_value=base + i):
            panel._append_colored(f"old{i}", "#FFF")
    before = len(panel._block_timestamps)
    with patch('ui.qso_panel.time.time', return_value=base + 1000):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) == before


def test_qso_panel_clear_resync():
    panel = _make_panel()
    for i in range(10):
        panel._append_colored(f"x{i}", "#FFF")
    panel.log_view.clear()
    panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._block_timestamps) <= panel.log_view.document().blockCount()


def test_qso_panel_scroll_at_bottom_preserved():
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(20):
        with patch('ui.qso_panel.time.time', return_value=base + i * 30):
            panel._append_colored(f"line{i}", "#FFF")
    sb = panel.log_view.verticalScrollBar()
    sb.setValue(sb.maximum())
    bottom_before = sb.value()
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    # Nach Trim wieder am (neuen) Bottom oder mindestens nicht stark abgewichen
    assert sb.value() >= bottom_before - 5 or sb.value() == sb.maximum()
