"""P1.16 / P95: QSO-Panel 5-Min-Rolling-Window.

P95 (v0.97.67): _block_timestamps entfernt. _entries ist neue SOT
(enthält ts pro Entry). _auto_trim_by_age trimmt _entries und ruft
_rerender_all. Tests umgestellt auf neue API.
"""
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


def test_qso_panel_entry_appended_on_add_tx():
    """P95: add_tx fügt einen Eintrag in _entries hinzu."""
    panel = _make_panel()
    initial = len(panel._entries)
    panel.add_tx("CQ DA1MHH JO31", tx_even=True,
                 slot_start_ts=1_000_000.0)
    assert len(panel._entries) == initial + 1
    assert panel._entries[-1]["kind"] == "tx"
    assert panel._entries[-1]["message"] == "CQ DA1MHH JO31"


def test_qso_panel_entry_appended_on_add_rx():
    """P95: add_rx fügt einen Eintrag in _entries hinzu."""
    panel = _make_panel()
    initial = len(panel._entries)
    panel.add_rx("DA1MHH 9A4AA -10", tx_even=False,
                 slot_start_ts=1_000_000.0, ant_label="(ANT2 ↑6 dB)")
    assert len(panel._entries) == initial + 1
    assert panel._entries[-1]["kind"] == "rx"
    assert panel._entries[-1]["ant_label"] == "(ANT2 ↑6 dB)"


def test_qso_panel_auto_trim_by_age():
    """P95: alte _entries (älter als max_age_s) werden entfernt."""
    panel = _make_panel()
    base = 1_000_000.0
    # 10 Einträge im Abstand 60s
    for i in range(10):
        with patch('ui.qso_panel.time.time', return_value=base + i * 60):
            panel.add_info(f"test{i}")
    # Trim mit Cutoff 600s — alle vor base+300 sollten raus
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    # max 5 verbleibend (Mindest-Schwelle = 5 für Trim-Ausführung)
    assert len(panel._entries) <= 5


def test_qso_panel_trim_below_threshold():
    """P95: < 5 alte Einträge → kein Trim (Anti-Flicker)."""
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(4):
        with patch('ui.qso_panel.time.time', return_value=base + i):
            panel.add_info(f"old{i}")
    before = len(panel._entries)
    with patch('ui.qso_panel.time.time', return_value=base + 1000):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert len(panel._entries) == before


def test_qso_panel_rerender_after_trim():
    """P95: nach Trim rendert log_view nur die verbleibenden Einträge."""
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(10):
        with patch('ui.qso_panel.time.time', return_value=base + i * 60):
            panel.add_info(f"test{i}")
    blocks_before = panel.log_view.document().blockCount()
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    blocks_after = panel.log_view.document().blockCount()
    assert blocks_after < blocks_before


def test_qso_panel_scroll_at_bottom_preserved():
    """P95: Scroll-Position am Bottom bleibt am (neuen) Bottom nach Trim."""
    panel = _make_panel()
    base = 1_000_000.0
    for i in range(20):
        with patch('ui.qso_panel.time.time', return_value=base + i * 30):
            panel.add_info(f"line{i}")
    sb = panel.log_view.verticalScrollBar()
    sb.setValue(sb.maximum())
    bottom_before = sb.value()
    with patch('ui.qso_panel.time.time', return_value=base + 600):
        panel._auto_trim_by_age(max_age_s=300.0)
    assert sb.value() >= bottom_before - 5 or sb.value() == sb.maximum()
