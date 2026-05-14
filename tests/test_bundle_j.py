#!/usr/bin/env python3
"""Tests fuer Bundle J (v0.97.27) — Connect-Modal-Branding + Help-Dialog +
RX-Label + Intent-Klausel.

T1   ConnectStatus-Footer mit Version + MIT
T2   SimpleHelpDialog baseline (MinSize 700x600, QTextBrowser)
T3   SimpleHelpDialog markdown=True rendert ohne Sternchen
T4   _make_info_btn ruft show_simple_help (statt QMessageBox)
T5   _show_bandpilot_help ruft show_simple_help mit markdown=True
T6   _antenna_pref_label Diversity ANT2 mit delta → "(RX: ANT2 ↑X.X dB)"
T7   _antenna_pref_label Diversity ANT2 ohne delta → "(RX: ANT2)"
T7b  _antenna_pref_label Diversity ANT2 mit delta=0.0 → "(RX: ANT2)" (F5)
T8   _antenna_pref_label Diversity ANT1 → "(ANT1)" ohne RX-Prefix
T9   Intent-Klausel im Hardware-Disclaimer (Substring 'persoenlichen Gebrauch')
"""

import os
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── T1 ConnectStatus-Footer ─────────────────────────────────────────


def test_t1_connect_status_footer_version_mit(qapp):
    """Footer-Label existiert + Format 'SimpleFT8 v{X.Y.Z} · MIT License'."""
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.27")
    try:
        assert hasattr(dlg, "_footer_label")
        assert isinstance(dlg._footer_label, QLabel)
        text = dlg._footer_label.text()
        # Format exakt: "SimpleFT8 v{APP_VERSION} · MIT License"
        assert re.match(r"^SimpleFT8 v\d+\.\d+\.\d+ · MIT License$", text), (
            f"Unerwartetes Footer-Format: {text!r}"
        )
        assert "0.97.27" in text
        # Setzt 'MIT License' am Ende (Substring-Schutz)
        assert text.endswith("· MIT License")
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t1b_connect_status_footer_empty_version(qapp):
    """Default-Wert app_version='' soll keinen Crash erzeugen — '?' als Fallback."""
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog()  # ohne app_version
    try:
        text = dlg._footer_label.text()
        assert "SimpleFT8 v?" in text
        assert "MIT License" in text
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


def test_t1c_connect_status_dialog_size_grown_for_footer(qapp):
    """Bundle J: FixedSize 352×176 → 352×196 fuer Footer-Platz."""
    from ui.connect_status_dialog import ConnectStatusDialog

    dlg = ConnectStatusDialog(app_version="0.97.27")
    try:
        assert dlg.minimumHeight() >= 196, f"Hoehe zu klein: {dlg.minimumHeight()}"
        assert dlg.maximumHeight() == 196
    finally:
        dlg._tick_timer.stop()
        dlg.deleteLater()


# ── T2/T3 SimpleHelpDialog baseline + markdown ─────────────────────


def test_t2_simple_help_dialog_baseline(qapp):
    """SimpleHelpDialog: min 700×600, QTextBrowser-Child, plain text."""
    from ui.simple_help_dialog import SimpleHelpDialog

    dlg = SimpleHelpDialog(None, "Test-Titel", "Hallo Mike")
    try:
        assert dlg.windowTitle() == "Test-Titel"
        assert dlg.minimumWidth() >= 700
        assert dlg.minimumHeight() >= 600
        assert dlg._browser is not None
        assert dlg._browser.toPlainText().strip() == "Hallo Mike"
        # Resizable: kein FixedSize
        assert dlg.maximumWidth() > 700  # nicht eingefroren
        # Close-Button existiert
        assert hasattr(dlg, "_btn_close")
        assert dlg._btn_close.text() == "Schließen"
    finally:
        dlg.deleteLater()


def test_t3_simple_help_dialog_markdown_renders_bold(qapp):
    """markdown=True: '**bold**' rendert ohne Sternchen im PlainText."""
    from ui.simple_help_dialog import SimpleHelpDialog

    dlg = SimpleHelpDialog(None, "Markdown", "Das ist **wichtig**", markdown=True)
    try:
        text = dlg._browser.toPlainText()
        assert "wichtig" in text
        # Markdown rendert ohne Sternchen
        assert "**wichtig**" not in text
    finally:
        dlg.deleteLater()


def test_t3b_window_modality(qapp):
    """SimpleHelpDialog: WindowModal (nicht ApplicationModal — Decoder laeuft weiter)."""
    from ui.simple_help_dialog import SimpleHelpDialog

    dlg = SimpleHelpDialog(None, "X", "Y")
    try:
        assert dlg.windowModality() == Qt.WindowModality.WindowModal
    finally:
        dlg.deleteLater()


# ── T4/T5 settings_dialog ruft show_simple_help ─────────────────────


def test_t4_make_info_btn_calls_show_simple_help(qapp):
    """_make_info_btn Lambda ruft show_simple_help statt QMessageBox.information."""
    from ui.settings_dialog import _make_info_btn

    btn = _make_info_btn("Mein Hint-Text")
    with patch("ui.settings_dialog.show_simple_help") as mock_help:
        btn.click()
    assert mock_help.called, "show_simple_help wurde nicht aufgerufen"
    args, kwargs = mock_help.call_args
    # Args: (parent, title, hint) — Position-Args
    assert "Mein Hint-Text" in args
    btn.deleteLater()


def test_t5_show_bandpilot_help_calls_show_simple_help_markdown(qapp):
    """_show_bandpilot_help ruft show_simple_help mit markdown=True."""
    from ui.settings_dialog import SettingsDialog
    from config.settings import Settings

    settings = Settings()
    dlg = SettingsDialog(settings)
    try:
        with patch("ui.settings_dialog.show_simple_help") as mock_help:
            dlg._show_bandpilot_help()
        assert mock_help.called, "show_simple_help wurde nicht aufgerufen"
        args, kwargs = mock_help.call_args
        assert kwargs.get("markdown") is True, (
            f"markdown=True fehlt: kwargs={kwargs}"
        )
    finally:
        dlg.deleteLater()


# ── T6-T8 _antenna_pref_label RX-Prefix ─────────────────────────────


class _FakeAntennaPrefs:
    """Minimaler Stub: get_pref(call) → dict | None."""
    def __init__(self, pref_dict):
        self._d = pref_dict

    def get_pref(self, call):
        return self._d


def _stub_mw_qso_self(rx_mode, pref_dict):
    """Stub object mit _rx_mode + _antenna_prefs Attribut fuer
    _antenna_pref_label-Unbound-Aufruf."""
    obj = MagicMock()
    obj._rx_mode = rx_mode
    obj._antenna_prefs = _FakeAntennaPrefs(pref_dict)
    return obj


def test_t6_antenna_pref_label_diversity_ant2_with_delta(qapp):
    """Diversity + best_ant=A2 + delta=6.3 → '(RX: ANT2 ↑6.3 dB)'."""
    from ui.mw_qso import QSOMixin

    self_stub = _stub_mw_qso_self(
        rx_mode="diversity",
        pref_dict={"best_ant": "A2", "delta_db": 6.3},
    )
    result = QSOMixin._antenna_pref_label(self_stub, "DA1ABC")
    assert result == " (RX: ANT2 ↑6.3 dB)", f"Got: {result!r}"


def test_t7_antenna_pref_label_diversity_ant2_no_delta(qapp):
    """Diversity + best_ant=A2 + delta=None → '(RX: ANT2)' ohne Pfeil."""
    from ui.mw_qso import QSOMixin

    self_stub = _stub_mw_qso_self(
        rx_mode="diversity",
        pref_dict={"best_ant": "A2", "delta_db": None},
    )
    result = QSOMixin._antenna_pref_label(self_stub, "DA1ABC")
    assert result == " (RX: ANT2)", f"Got: {result!r}"


def test_t7b_antenna_pref_label_diversity_ant2_delta_zero(qapp):
    """F5: Diversity + best_ant=A2 + delta=0.0 → '(RX: ANT2)' ohne Pfeil."""
    from ui.mw_qso import QSOMixin

    self_stub = _stub_mw_qso_self(
        rx_mode="diversity",
        pref_dict={"best_ant": "A2", "delta_db": 0.0},
    )
    result = QSOMixin._antenna_pref_label(self_stub, "DA1ABC")
    assert result == " (RX: ANT2)", f"Got: {result!r}"


def test_t8_antenna_pref_label_diversity_ant1(qapp):
    """Diversity + best_ant=A1 → '(ANT1)' OHNE RX-Prefix (symmetrisch zu Normal)."""
    from ui.mw_qso import QSOMixin

    self_stub = _stub_mw_qso_self(
        rx_mode="diversity",
        pref_dict={"best_ant": "A1", "delta_db": -1.2},
    )
    result = QSOMixin._antenna_pref_label(self_stub, "DA1ABC")
    assert result == " (ANT1)", f"Got: {result!r}"


def test_t8b_antenna_pref_label_normal_mode_unchanged(qapp):
    """Normal-Modus → '(ANT1)' unveraendert (Bundle J aendert nichts)."""
    from ui.mw_qso import QSOMixin

    self_stub = _stub_mw_qso_self(
        rx_mode="normal",
        pref_dict={"best_ant": "A2", "delta_db": 5.0},  # wird ignoriert
    )
    result = QSOMixin._antenna_pref_label(self_stub, "DA1ABC")
    assert result == " (ANT1)", f"Got: {result!r}"


# ── T9 Intent-Klausel im Disclaimer ─────────────────────────────────


def test_t9_intent_klausel_in_disclaimer():
    """Disclaimer-Text enthaelt 'persoenlichen Gebrauch' Substring."""
    import main as main_module
    import inspect
    src = inspect.getsource(main_module._show_hardware_warning)
    # Sucht den deutschen Wortlaut "persönlichen Gebrauch" im Source
    assert "persönlichen Gebrauch" in src, (
        "Intent-Klausel fehlt im _show_hardware_warning"
    )
    assert "Verifikation" in src, (
        "Intent-Klausel-Wortlaut 'Verifikation' fehlt"
    )


def test_t9b_app_version_bumped():
    """APP_VERSION ist >= 0.97.27 nach Bundle J (Bumps moeglich)."""
    import main as main_module
    parts = main_module.APP_VERSION.split(".")
    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2])
    assert (major, minor, patch) >= (0, 97, 27), (
        f"APP_VERSION {main_module.APP_VERSION} < 0.97.27"
    )
