"""P79 (v0.97.51) — UI-Bundle Tests.

Coverage:
- T1-T6: qso_panel.add_info Auto-Detect Symbol→Farbe.
- T7: _SYMBOL_COLORS Konvention-Lock.
- T8: mw_tx.py Text-Erweiterung Source-Level.
- T9: mw_radio._show_calibration_done Modal weg (Source-Level).
- T10/T11: _show_calibration_done ruft add_info mit korrektem Text.
- T12: add_info("⚠") Symbol-only Edge-Case (R1-F7 GELB).
"""

import inspect
import os
import re
from unittest.mock import MagicMock

import pytest

# Qt-Smoke: offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui import qso_panel as qp_mod
from ui.qso_panel import QSOPanel, _SYMBOL_COLORS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def panel(qapp):
    p = QSOPanel()
    return p


# ── T1-T6: add_info Auto-Detect ──────────────────────────────


def test_t1_warn_symbol_gets_orange(panel):
    """⚠-Praefix wird in #FFAA00 gerendert, Rest in #666666."""
    panel._append_two_color = MagicMock()
    panel._append_colored = MagicMock()
    panel.add_info("⚠ SWR zu hoch")
    panel._append_two_color.assert_called_once_with(
        "       ⚠", "#FFAA00",
        " SWR zu hoch", "#666666"
    )
    panel._append_colored.assert_not_called()


def test_t2_check_symbol_gets_green(panel):
    """✓-Praefix wird in #44FF44 gerendert."""
    panel._append_two_color = MagicMock()
    panel.add_info("✓ Kalibrierung 20m gespeichert")
    panel._append_two_color.assert_called_once_with(
        "       ✓", "#44FF44",
        " Kalibrierung 20m gespeichert", "#666666"
    )


def test_t3_cross_symbol_gets_red(panel):
    """✗-Praefix wird in #FF4444 gerendert."""
    panel._append_two_color = MagicMock()
    panel.add_info("✗ Timeout XYZ")
    panel._append_two_color.assert_called_once_with(
        "       ✗", "#FF4444",
        " Timeout XYZ", "#666666"
    )


def test_t4_hourglass_symbol_gets_cyan(panel):
    """⏳-Praefix wird in #44BBFF gerendert."""
    panel._append_two_color = MagicMock()
    panel.add_info("⏳ Warteliste: A, B, C")
    panel._append_two_color.assert_called_once_with(
        "       ⏳", "#44BBFF",
        " Warteliste: A, B, C", "#666666"
    )


def test_t5_normal_info_stays_gray(panel):
    """Text ohne Symbol → heutiges Verhalten, alles #666666."""
    panel._append_colored = MagicMock()
    panel._append_two_color = MagicMock()
    panel.add_info("CQ-Modus gestartet")
    panel._append_colored.assert_called_once_with(
        "       CQ-Modus gestartet", "#666666"
    )
    panel._append_two_color.assert_not_called()


def test_t6_empty_text_silent_return(panel):
    """Empty-Guard (R1-F4): leerer Text → kein Append."""
    panel._append_colored = MagicMock()
    panel._append_two_color = MagicMock()
    panel.add_info("")
    panel._append_colored.assert_not_called()
    panel._append_two_color.assert_not_called()


# ── T7: Konvention-Lock ──────────────────────────────────────


def test_t7_symbol_colors_convention():
    """_SYMBOL_COLORS hat genau die 4 erwarteten Symbole + Hex-Farben.

    Schutz gegen Drift — wenn jemand ein Symbol hinzufuegt, muss er
    auch diesen Test anpassen und damit den Reviewer involvieren.
    """
    assert set(_SYMBOL_COLORS.keys()) == {"⚠", "✓", "✗", "⏳"}
    assert _SYMBOL_COLORS["⚠"] == "#FFAA00"
    assert _SYMBOL_COLORS["✓"] == "#44FF44"
    assert _SYMBOL_COLORS["✗"] == "#FF4444"
    assert _SYMBOL_COLORS["⏳"] == "#44BBFF"


# ── T8: mw_tx.py Text-Erweiterung (Source-Level) ────────────


def test_t8_swr_block_text_has_three_options():
    """mw_tx.py:_tune_post_swr_check enthaelt die 3-Optionen-Formulierung."""
    from ui import mw_tx as mt
    src = inspect.getsource(mt.TXMixin._tune_post_swr_check)
    # Pflicht-Substrings
    assert "Antenne pruefen ODER" in src
    assert "SWR-Limit in Einstellungen anpassen" in src
    assert "manueller TUNE zum Freischalten" in src
    # Alte einzelne-Optionen-Formulierung MUSS WEG sein
    assert "nach Antennen-Check" not in src


# ── T9-T11: _show_calibration_done Refactor ─────────────────


def test_t9_show_calibration_done_no_qdialog():
    """_show_calibration_done baut KEIN QDialog mehr.

    R1-F-V2-F4: Source-Level via inspect.getsource (scoped auf Methode),
    nicht raw-file-grep — sonst false positives durch andere QDialogs.
    """
    from ui import mw_radio as mr
    src = inspect.getsource(mr.RadioMixin._show_calibration_done)
    assert "QDialog" not in src
    assert "WindowStaysOnTopHint" not in src
    assert "_close_timer" not in src
    # Pflicht: add_info + statusBar
    assert "self.qso_panel.add_info" in src
    assert "self.statusBar().showMessage" in src


def test_t10_show_calibration_done_normal_mode():
    """Normal-Mode (ant2_g=None) ruft add_info mit ANT1-only-Text."""
    from ui.mw_radio import RadioMixin

    panel = MagicMock()
    statusbar = MagicMock()
    obj = MagicMock(spec=RadioMixin)
    obj.qso_panel = panel
    obj.statusBar = MagicMock(return_value=statusbar)

    RadioMixin._show_calibration_done(obj, "20m", 25, None)

    panel.add_info.assert_called_once_with(
        "✓ Kalibrierung 20m gespeichert. ANT1: 25 dB"
    )
    statusbar.showMessage.assert_called_once_with(
        "✓ Kalibrierung 20m gespeichert. ANT1: 25 dB", 3000
    )


def test_t11_show_calibration_done_diversity_mode():
    """Diversity-Mode (ant2_g gesetzt) ruft add_info mit ANT1+ANT2-Text."""
    from ui.mw_radio import RadioMixin

    panel = MagicMock()
    statusbar = MagicMock()
    obj = MagicMock(spec=RadioMixin)
    obj.qso_panel = panel
    obj.statusBar = MagicMock(return_value=statusbar)

    RadioMixin._show_calibration_done(obj, "40m", 18, 22)

    panel.add_info.assert_called_once_with(
        "✓ Kalibrierung 40m gespeichert. ANT1: 18 dB | ANT2: 22 dB"
    )
    statusbar.showMessage.assert_called_once_with(
        "✓ Kalibrierung 40m gespeichert. ANT1: 18 dB | ANT2: 22 dB", 3000
    )


# ── T12: Edge-Case Symbol-only (R1-F7 GELB) ─────────────────


def test_t12_symbol_only_no_crash(panel):
    """add_info('⚠') (Symbol ohne Rest) crasht nicht und ruft
    _append_two_color mit leerem rest auf.

    Schutz gegen kuenftige Programmier-Fehler die nur das Symbol senden.
    """
    panel._append_two_color = MagicMock()
    panel.add_info("⚠")
    panel._append_two_color.assert_called_once_with(
        "       ⚠", "#FFAA00",
        "", "#666666"
    )


# ── Bonus: APP_VERSION-Bump ─────────────────────────────────


def test_t_bonus_app_version():
    """P82 (v0.97.55) bumpt weiter — P79-Baseline bleibt ≥0.97.51."""
    import main
    assert main.APP_VERSION >= "0.97.51"


# ── Bonus: statusBar-Exception darf nicht propagieren ────────


def test_t_bonus_statusbar_exception_swallowed():
    """Wenn statusBar() wirft (z.B. headless Test), add_info funktioniert trotzdem."""
    from ui.mw_radio import RadioMixin

    panel = MagicMock()
    obj = MagicMock(spec=RadioMixin)
    obj.qso_panel = panel
    obj.statusBar = MagicMock(side_effect=RuntimeError("no statusbar"))

    # Darf nicht crashen
    RadioMixin._show_calibration_done(obj, "20m", 25, None)

    panel.add_info.assert_called_once()
