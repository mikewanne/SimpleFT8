"""P108 (21.05.2026, v0.97.85) — Kommentar-Feld aus QSO-Detail-Overlay entfernen.

Nach P106 (WSJT-X-Minimal ADIF) wird COMMENT nicht mehr exportiert.
Im Overlay (Klick auf Logbuch-Zeile) zeigte das Feld noch alte Werte
(„SimpleFT8 v1.0") — funktionslos, weil Save-Pfad das Widget gar nicht ausliest.

Tests:
- T1: comment_edit-Attribut existiert nicht mehr auf QSODetailOverlay
- T2: load_qso() mit Record (mit + ohne COMMENT) wirft keinen AttributeError
- T3: Save-Pfad ist unverändert — _on_save emittiert _qso_data
- T4: Quelltext referenziert kein „Kommentar"-Label mehr
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_comment_edit_attribute_gone():
    """Source darf comment_edit-Widget nicht mehr anlegen."""
    src = _read("ui/qso_detail_overlay.py")
    assert "self.comment_edit" not in src, (
        "P108: comment_edit-Widget muss entfernt sein")


def test_t2_load_qso_smoke_with_and_without_comment():
    """load_qso() darf weder mit COMMENT noch ohne knallen."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from ui.qso_detail_overlay import QSODetailOverlay

    overlay = QSODetailOverlay()
    # Mit COMMENT
    overlay.load_qso({
        "CALL": "DA1MHH", "QSO_DATE": "20260521", "TIME_ON": "1234",
        "BAND": "20m", "FREQ": "14.074", "MODE": "FT8",
        "RST_SENT": "-12", "RST_RCVD": "-08",
        "GRIDSQUARE": "JN58", "TX_PWR": "10",
        "COMMENT": "SimpleFT8 v1.0",
    })
    # Ohne COMMENT
    overlay.load_qso({
        "CALL": "DG8DBW", "QSO_DATE": "20260521", "TIME_ON": "1245",
        "BAND": "15m", "FREQ": "21.074", "MODE": "FT8",
        "RST_SENT": "-15", "RST_RCVD": "-10",
        "GRIDSQUARE": "JN59", "TX_PWR": "10",
    })
    # Hat kein comment_edit
    assert not hasattr(overlay, "comment_edit")


def test_t3_save_emits_qso_data_unchanged():
    """Save-Pfad emittiert _qso_data, NICHT irgendein Widget-Edit."""
    src = _read("ui/qso_detail_overlay.py")
    m = re.search(r"def _on_save\(self\):.*?(?=\n    def )", src, re.DOTALL)
    assert m, "_on_save nicht gefunden"
    body = m.group(0)
    assert "self._qso_data" in body
    assert "comment_edit" not in body


def test_t4_no_kommentar_label_in_source():
    """Label-Text 'Kommentar:' darf nicht mehr im Source stehen."""
    src = _read("ui/qso_detail_overlay.py")
    assert "Kommentar:" not in src, (
        "P108: 'Kommentar:'-Label muss entfernt sein")
