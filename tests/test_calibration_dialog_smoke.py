"""Smoke-Tests fuer _show_calibration_done.

P79 (v0.97.51): Modal-Dialog komplett entfernt. Diese 3 Tests sind
obsolet — die ehemaligen Dialog-Properties (3000ms-Timer, kein OK-Button,
non-modal) sind durch „kein Dialog ueberhaupt" abgeloest. Die neue
Source-Level-Test-Coverage liegt in `test_p79_ui_bundle.py` (T9-T11).

Hier bleibt nur die Fix-G-Coverage fuer DXTuneDialog erhalten.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QPushButton, QLabel,
)


def _ensure_app():
    return QApplication.instance() or QApplication([])


def test_calibration_done_no_dialog_p79():
    """P79: _show_calibration_done erstellt KEINEN QDialog mehr.

    Ersetzt die alten 3 Smoke-Tests (Timer/Button/Modal) — Mike-Wunsch
    18.05.: „seperates info fenster modual weg". Loesung jetzt:
    add_info-Zeile + Statusbar-Echo, kein Dialog.
    """
    _ensure_app()

    from ui.mw_radio import RadioMixin
    from unittest.mock import MagicMock

    mw = QMainWindow()
    mw.qso_panel = MagicMock()
    # statusBar() von QMainWindow ist real verfuegbar — kein Mock noetig
    RadioMixin._show_calibration_done(mw, "20m", 20, 0)

    # KEIN QDialog darf erzeugt worden sein
    dialogs = mw.findChildren(QDialog)
    assert len(dialogs) == 0, (
        f"P79: Dialog-Erzeugung verboten, gefunden: {len(dialogs)}"
    )

    # qso_panel.add_info MUSS aufgerufen worden sein
    mw.qso_panel.add_info.assert_called_once()
    args = mw.qso_panel.add_info.call_args[0]
    assert args[0].startswith("✓ Kalibrierung 20m gespeichert.")


# ── Fix G v0.86 — Falscher Kalibrierungstext im Normal-Modus ─────────────────

def test_dxtune_mode_label_normal_modus():
    """Fix G: DXTuneDialog mit rx_mode='normal' → Titel 'Gain-Messung', kein 'Diversity'."""
    _ensure_app()

    from ui.dx_tune_dialog import DXTuneDialog

    class _FakeRadio:
        ip = ""
        def set_rx_antenna(self, ant): pass
        def set_rfgain(self, g): pass
        def set_tx_antenna(self, ant): pass
        def ptt_off(self): pass

    dlg = DXTuneDialog(_FakeRadio(), "20m", scoring_mode="stations", rx_mode="normal")
    assert dlg._get_mode_label() == "Gain-Messung"
    assert "Gain-Messung" in dlg.windowTitle()
    assert "Diversity" not in dlg.windowTitle()
    dlg.deleteLater()


def test_dxtune_mode_label_diversity_modus():
    """P146 (27.05.2026): DXTuneDialog mit rx_mode='diversity' zeigt
    EINHEITLICH 'Diversity (Standard + DX)' — egal ob scoring_mode
    'stations' oder 'snr'. Begruendung: P80 (v0.97.52) unified Gain-
    Store, eine Kalibrierung gilt fuer beide Modi.

    Vor P146 hingen die Titel an scoring_mode:
    - scoring='stations' -> 'Diversity Standard'
    - scoring='snr'      -> 'Diversity DX'

    Mike-Field-Bug 27.05.: Dialog zeigte 'Standard' obwohl DX-Modus
    aktiv (Asymmetrie zur Antennen-Kachel). Fix: einheitlicher Text.
    """
    _ensure_app()

    from ui.dx_tune_dialog import DXTuneDialog

    class _FakeRadio:
        ip = ""
        def set_rx_antenna(self, ant): pass
        def set_rfgain(self, g): pass
        def set_tx_antenna(self, ant): pass
        def ptt_off(self): pass

    EXPECTED = "Diversity (Standard + DX)"

    dlg_std = DXTuneDialog(_FakeRadio(), "40m", scoring_mode="stations", rx_mode="diversity")
    assert dlg_std._get_mode_label() == EXPECTED, (
        f"P146: stations-Scoring muss '{EXPECTED}' liefern")
    assert EXPECTED in dlg_std.windowTitle()
    dlg_std.deleteLater()

    dlg_dx = DXTuneDialog(_FakeRadio(), "40m", scoring_mode="snr", rx_mode="diversity")
    assert dlg_dx._get_mode_label() == EXPECTED, (
        f"P146: snr-Scoring muss IDENTISCH '{EXPECTED}' liefern "
        "(keine Mode-Unterscheidung mehr im UI-Titel)")
    assert EXPECTED in dlg_dx.windowTitle()
    dlg_dx.deleteLater()


def test_p146_no_separate_diversity_modus_in_title():
    """P146: Der alte mode-spezifische Titel-Text darf NICHT mehr
    vorkommen (Regression-Schutz). Suchen wir in der Quelldatei
    nach den alten Strings."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "ui" / "dx_tune_dialog.py").read_text()
    # _get_mode_label darf nur noch generisch sein
    import re
    m = re.search(
        r"def _get_mode_label\(self\).*?(?=\n    def )",
        src, re.S)
    body = m.group(0)
    assert '"Diversity DX"' not in body, (
        "P146: 'Diversity DX'-Returnwert in _get_mode_label wurde "
        "entfernt (Hardware-Gain ist identisch P80).")
    assert '"Diversity Standard"' not in body, (
        "P146: 'Diversity Standard'-Returnwert wurde entfernt.")
    assert '"Diversity (Standard + DX)"' in body, (
        "P146: neuer einheitlicher Text 'Diversity (Standard + DX)' "
        "muss in _get_mode_label sein.")


def test_v0998_mode_label_removed():
    """v0.99.8: Das mode_label 'Misst gleichzeitig fuer Standard- und
    DX-Modus' (P146) ist beim Verschlanken des Fensters entfallen — es war
    Ballast neben dem doppelten Titel + den drei Fortschritts-Zaehlern. Die
    Modus-Info steht weiter im Fenstertitel (windowTitle, von _get_mode_label).
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "ui" / "dx_tune_dialog.py").read_text()
    assert "Misst gleichzeitig für Standard- und DX-Modus" not in src, (
        "Das mode_label wurde in v0.99.8 entfernt (Fenster verschlankt). "
        "Falls wieder eingebaut: Höhe in __init__ anpassen.")
    # Das Widget-Attribut selbst darf nicht mehr existieren/referenziert werden.
    assert "self.mode_label" not in src


# ── v0.99.8 — Fenster verschlankt (ein Fortschritts-Zähler, kein Doppel-Titel) ──

class _FakeRadioV8:
    ip = ""
    def set_rx_antenna(self, ant): pass
    def set_rfgain(self, g): pass
    def set_tx_antenna(self, ant): pass
    def ptt_off(self): pass


def _make_dialog():
    """DXTuneDialog ohne TUNE-Phase → __init__ ruft _start_step() (Schritt 0)."""
    _ensure_app()
    from ui.dx_tune_dialog import DXTuneDialog
    return DXTuneDialog(_FakeRadioV8(), "20m",
                        scoring_mode="stations", rx_mode="diversity")


def test_v0998_step_label_gerade_format():
    """step_label zeigt das knappe Lebenszeichen 'Gerade: ANT · X dB' statt
    'Runde 1/2 — ANT1 Gain 20 dB'. Schritt 0 = (ANT1, 0 dB)."""
    dlg = _make_dialog()
    txt = dlg.step_label.text()
    assert txt.startswith("Gerade:"), txt
    assert "ANT1" in txt and "0 dB" in txt
    assert "Runde" not in txt and "Schritt" not in txt
    dlg.deleteLater()


def test_v0998_progress_value_counts_running_cycle():
    """Kein 4-vs-5-Widerspruch mehr: der Balkenwert zählt den LAUFENDEN Zyklus
    mit (_step+1). Bei Schritt 0 steht der Wert auf 1."""
    dlg = _make_dialog()
    assert dlg.progress.value() == dlg._step + 1 == 1
    dlg.deleteLater()


def test_v0998_progress_format_has_cycle_and_remaining():
    """Ein Zähler: Balken-Text trägt Zyklus + Restzeit zusammen."""
    dlg = _make_dialog()
    fmt = dlg.progress.format()
    assert "Zyklus 1 / 12" in fmt, fmt
    assert "noch" in fmt and "min" in fmt, fmt
    dlg.deleteLater()


def test_v0998_detail_label_empty_in_normal_run():
    """Im Normalbetrieb ist detail_label leer (frühere 'Schritt 5/12 (5/6 in
    dieser Runde)'-Zeile ist entfallen); es bleibt nur für Warnung/Abschluss."""
    dlg = _make_dialog()
    assert dlg.detail_label.text() == ""
    dlg.deleteLater()


def test_v0998_window_height_compact():
    """Fenster ist deutlich kompakter (war fix 460, jetzt ~360 ohne TUNE)."""
    dlg = _make_dialog()
    assert dlg.height() <= 380, dlg.height()
    dlg.deleteLater()


def test_v0998_removed_widgets_source():
    """time_label + doppeltes Body-Titel-Label sind raus (Source-Inspektion)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "ui" / "dx_tune_dialog.py").read_text()
    assert "self.time_label" not in src
    assert "self._title_label" not in src
    # Die user-sichtbaren Label-Texte sind weg (interne Docstrings, die diese
    # Begriffe technisch korrekt verwenden, dürfen bleiben — daher die genauen
    # Label-Strings prüfen, nicht die Stichworte).
    assert "12 Zyklen interleaved • ANT1" not in src   # gelber Hinweis-Block
    assert "Top-5 SNR-Schnitt pro Kombination" not in src  # alter Results-Header
