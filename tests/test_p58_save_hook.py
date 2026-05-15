"""P58 (v0.97.31): SWR-Limit Save-Hook Live-Propagation an Radio.

Bug: Inline-Propagation in `settings_dialog._save_and_close` greift
nicht zur laufenden App. Fix: Setter-Aufruf nach dialog.exec() in
main_window._on_settings_clicked analog zu set_power/tx_audio_level.

T1: Dialog setzt nur settings, KEIN Radio-Call (Bug-Schutz alter Pfad)
T2: main_window-Pfad ruft set_swr_limit nach Save mit radio.ip
T3: radio.ip=None → set_swr_limit NICHT gerufen
T4: Cancel → kein Setter (dialog.exec() returns False)
T5: Connect-Hook in mw_radio.py:179 unverändert (Regression)
T6: Source-Level — alte Inline-Propagation NICHT mehr im Code
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock


# T1: Dialog _save_and_close ruft KEINEN set_swr_limit auf
def test_t1_dialog_save_does_not_call_radio_setter():
    """settings_dialog._save_and_close darf radio.set_swr_limit NICHT
    direkt aufrufen — Live-Propagation passiert nur in main_window."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "settings_dialog.py").read_text()
    # Im _save_and_close-Block darf set_swr_limit nicht stehen
    save_method_start = src.find("def _save_and_close")
    assert save_method_start > 0, "_save_and_close nicht gefunden"
    # Suche bis zum Ende des Constructors oder nächste Top-Level-Def
    save_method_end = src.find("\n    def ", save_method_start + 10)
    if save_method_end < 0:
        save_method_end = len(src)
    method_body = src[save_method_start:save_method_end]
    assert "set_swr_limit" not in method_body, (
        "P58-Regression: _save_and_close darf radio.set_swr_limit "
        "nicht direkt aufrufen — gehört in main_window._on_settings_clicked"
    )


# T2: _on_settings_clicked propagiert swr_limit an Radio
def test_t2_main_window_propagates_swr_limit_after_save():
    """main_window._on_settings_clicked muss nach erfolgreichem
    dialog.exec() radio.set_swr_limit aufrufen — gleicher Pfad wie
    set_power."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text()
    method_start = src.find("def _on_settings_clicked")
    assert method_start > 0
    # Suche bis zur nächsten def auf gleicher Einrückung
    method_end = src.find("\n    def ", method_start + 10)
    method_body = src[method_start:method_end]
    # Muss set_swr_limit aufrufen
    assert "set_swr_limit" in method_body, (
        "P58: main_window._on_settings_clicked muss radio.set_swr_limit "
        "nach dialog.exec() aufrufen (analog zu set_power)"
    )
    # Muss aus settings lesen
    assert 'self.settings.get("swr_limit"' in method_body, (
        "set_swr_limit muss aus settings.get('swr_limit') gespeist werden"
    )


# T3: radio.ip=None Guard — set_swr_limit nicht im ungeschützten Pfad
def test_t3_swr_limit_setter_under_radio_ip_guard():
    """Der set_swr_limit-Aufruf muss unter `if self.radio.ip:` stehen
    damit kein AttributeError bei nicht-verbundenem Radio."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text()
    method_start = src.find("def _on_settings_clicked")
    method_end = src.find("\n    def ", method_start + 10)
    method_body = src[method_start:method_end]
    # Index des Guards und des Setters
    guard_idx = method_body.find("if self.radio.ip:")
    setter_idx = method_body.find("self.radio.set_swr_limit")
    assert guard_idx > 0 and setter_idx > 0
    assert setter_idx > guard_idx, (
        "set_swr_limit muss NACH (und unter) `if self.radio.ip:` stehen"
    )


# T4: Cancel-Pfad — dialog.exec() returns False
def test_t4_cancel_skips_setter():
    """Wenn dialog.exec() False returnt (Cancel/Esc), darf
    set_swr_limit nicht gerufen werden — gewährleistet durch
    `if dialog.exec():` Guard im main_window."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text()
    method_start = src.find("def _on_settings_clicked")
    method_end = src.find("\n    def ", method_start + 10)
    method_body = src[method_start:method_end]
    exec_idx = method_body.find("if dialog.exec():")
    setter_idx = method_body.find("self.radio.set_swr_limit")
    assert exec_idx > 0 and setter_idx > 0
    assert setter_idx > exec_idx, (
        "set_swr_limit muss INNERHALB des `if dialog.exec():` Blocks "
        "stehen — sonst greift Cancel-Pfad nicht"
    )


# T5: Connect-Hook in mw_radio.py:179 unverändert
def test_t5_connect_hook_unchanged():
    """mw_radio _on_radio_connected muss weiterhin set_swr_limit
    aufrufen — Regression-Schutz für App-Start mit persistiertem Wert."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "mw_radio.py").read_text()
    assert 'self.radio.set_swr_limit(self.settings.get("swr_limit"' in src, (
        "Connect-Hook in mw_radio.py muss erhalten bleiben"
    )


# T6: Alte Inline-Propagation NICHT im settings_dialog.py Source
def test_t6_no_inline_propagation_remains():
    """settings_dialog.py darf KEINEN parent.radio.set_swr_limit-Pfad
    mehr enthalten (alter Bug-Pfad raus)."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "settings_dialog.py").read_text()
    assert "parent.radio.set_swr_limit" not in src, (
        "P58: parent.radio.set_swr_limit-Pfad muss aus settings_dialog "
        "raus sein — Live-Propagation läuft jetzt nur in main_window"
    )
