"""P1-Bundle1: P1.12 + P1.15 statische Tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_p1_12_btn_remeasure_removed():
    """P1.12: btn_remeasure muss entfernt sein."""
    _ensure_app()
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    assert not hasattr(cp, 'btn_remeasure')


def test_p1_15_no_arrow_call_in_status():
    """P1.15: → {their_call}-Setzung in main_window.py darf nicht existieren."""
    src = (Path(__file__).parent.parent / "ui" / "main_window.py").read_text()
    assert "→ {their_call}" not in src


def test_p1_12_remeasure_signal_removed():
    """P1.12: remeasure_clicked Signal-Definition raus."""
    src = (Path(__file__).parent.parent / "ui" / "control_panel.py").read_text()
    assert "remeasure_clicked = Signal()" not in src


def test_p1_12_handler_removed():
    """P1.12: _on_diversity_remeasure Methode raus."""
    src = (Path(__file__).parent.parent / "ui" / "mw_radio.py").read_text()
    assert "_on_diversity_remeasure" not in src
