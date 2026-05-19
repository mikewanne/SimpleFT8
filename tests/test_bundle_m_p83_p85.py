"""Bundle M (v0.97.54) — P83 Gain-Status-Zeile + P85 ANT2-Win-%.

Mike-Field-Test 19.05.2026: Antennen-Kachel UX-Verbesserungen.

P83 — Status-Zeile mit Verfalls-Counter:
- T1: fresh (>2h) → grün
- T2: fresh (1-2h) → orange
- T3: fresh (≤1h) → rot
- T4: stale → „Re-Mess fällig"
- T5: missing → „nicht kalibriert"
- T6: ant2_calibrated=False → kein ANT2 in Format (Normal-mode-Pattern)

P85 — ANT2-Win-% Median-Glättung:
- T7: cum_total < 4 → „Diversity läuft..." Warmup
- T8: cum_total ≥ 4 → ANT2-Win-% angezeigt
- T9: DX-Mode bleibt unverändert (X DX)
- T10: reset_win_rate_history leert Buffer
"""

import time
from collections import deque
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# P83 Tests — _format_gain_status Verhalten
# ──────────────────────────────────────────────────────────────────────


def _make_mw_with_gain_entry(entry: dict | None, band: str = "20m"):
    """Mock-Setup mit konfigurierbarem _gain_store.get() Result."""
    from ui import mw_radio
    obj = MagicMock()
    obj._gain_store = MagicMock()
    obj._gain_store.get = MagicMock(return_value=entry)
    obj.settings = MagicMock(band=band)
    obj._rx_mode = "diversity"
    return obj


def test_p83_t1_fresh_green_more_than_2h():
    """T1: >2h verbleibend → grün (#44CC44)."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 3 * 3600,  # 3h alt → 3h verbleibend
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "ANT1(G10) + ANT2(G20)" in html
    assert "noch 3h" in html
    assert "#44CC44" in html  # grün


def test_p83_t2_fresh_orange_1_to_2h():
    """T2: 1-2h verbleibend → orange (#FFAA00)."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 4.5 * 3600,  # 4.5h alt → 1.5h frei
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "noch" in html
    assert "#FFAA00" in html  # orange


def test_p83_t3_fresh_red_under_1h():
    """T3: ≤1h verbleibend → rot (#FF3333)."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 5.5 * 3600,  # 5.5h alt → 0.5h frei
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "#FF3333" in html  # rot
    # h gerundet auf 1 (max(1, round(0.5)) = 1)
    assert "noch 1h" in html


def test_p83_t4_stale_re_mess_faellig():
    """T4: ≥6h alt → „Re-Mess fällig" rot."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 8 * 3600,  # 8h alt
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "Re-Mess fällig" in html
    assert "#FF3333" in html


def test_p83_t5_missing_nicht_kalibriert():
    """T5: kein Entry → „nicht kalibriert · G10 (Std)" grau."""
    from ui import mw_radio
    obj = _make_mw_with_gain_entry(None)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "nicht kalibriert" in html
    assert "G10" in html  # Default-Gain für 20m
    assert "#888" in html


def test_p83_t6_normal_mode_no_ant2():
    """T6: Normal-Mode (rx_mode='normal') zeigt NUR ANT1, kein ANT2."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 3 * 3600,
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "normal")
    assert "ANT1(G10)" in html
    assert "ANT2" not in html  # Normal = nur ANT1


def test_p83_t6b_diversity_mode_ant2_not_calibrated():
    """T6b: ant2_calibrated=False → kein ANT2 anzeigen (Normal-Migration)."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 0,
        "ant2_calibrated": False,
        "gain_timestamp": time.time() - 3 * 3600,
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "ANT1(G10)" in html
    assert "ANT2" not in html  # ant2 nicht echt kalibriert


def test_p83_t6c_migration_marker_ts_zero():
    """T6c: gain_timestamp=0.0 (Migration-Marker) → wie missing behandeln."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 0,
        "ant2_calibrated": False,
        "gain_timestamp": 0.0,
    }
    obj = _make_mw_with_gain_entry(entry)
    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")
    assert "nicht kalibriert" in html


# ──────────────────────────────────────────────────────────────────────
# P85 Tests — Win-Rate-History Logik
# ──────────────────────────────────────────────────────────────────────


def test_p85_t7_warmup_diversity_laeuft():
    """T7: cum_total < 4 → „Diversity läuft..." Warmup-Anzeige."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import control_panel as cp_mod
    cp = cp_mod.ControlPanel()
    # 1 Vergleich, cum_total=2 → < 4 → Warmup
    cp.update_diversity_counts(
        a1_count=5, a2_count=5,
        scoring_mode="normal",
        ant2_wins=1, total_compared=2,
    )
    assert "läuft" in cp._a1_count_label.text()
    assert cp._a2_count_label.text() == ""


def test_p85_t8_win_rate_anzeige_nach_warmup():
    """T8: cum_total ≥ 4 → ANT2-Win-% angezeigt."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import control_panel as cp_mod
    cp = cp_mod.ControlPanel()
    # 3 Zyklen mit insgesamt 6 Vergleichen, 4 ANT2-wins
    cp.update_diversity_counts(
        a1_count=3, a2_count=3, scoring_mode="normal",
        ant2_wins=2, total_compared=3,
    )
    cp.update_diversity_counts(
        a1_count=3, a2_count=3, scoring_mode="normal",
        ant2_wins=1, total_compared=2,
    )
    cp.update_diversity_counts(
        a1_count=3, a2_count=3, scoring_mode="normal",
        ant2_wins=1, total_compared=1,
    )
    # cum_wins=4, cum_total=6 → 67%
    assert "ANT2-Win 67%" in cp._a1_count_label.text()
    assert cp._a2_count_label.text() == ""


def test_p85_t9_dx_mode_unveraendert():
    """T9: DX-Mode bleibt bei „X DX" weak-counts."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import control_panel as cp_mod
    cp = cp_mod.ControlPanel()
    cp.update_diversity_counts(
        a1_count=5, a2_count=5, scoring_mode="dx",
        ant2_wins=4, total_compared=8,  # diese werden im DX ignoriert
        a1_weak_count=2, a2_weak_count=3,
    )
    assert "DX" in cp._a1_count_label.text()
    assert "02 DX" in cp._a1_count_label.text()
    assert "03 DX" in cp._a2_count_label.text()
    # Win-% wird im DX-Mode NICHT angezeigt
    assert "Win" not in cp._a1_count_label.text()


def test_p85_t10_reset_win_rate_history():
    """T10: reset_win_rate_history leert Buffer."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import control_panel as cp_mod
    cp = cp_mod.ControlPanel()
    # Buffer füllen
    cp.update_diversity_counts(
        a1_count=3, a2_count=3, scoring_mode="normal",
        ant2_wins=2, total_compared=3,
    )
    assert len(cp._win_rate_history) == 1
    cp.reset_win_rate_history()
    assert len(cp._win_rate_history) == 0


def test_p85_t11_zero_counts_double_dash():
    """T11: a1+a2 = 0 → „--" anzeigen (Diversity läuft nicht / kein Decode)."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import control_panel as cp_mod
    cp = cp_mod.ControlPanel()
    cp.update_diversity_counts(
        a1_count=0, a2_count=0, scoring_mode="normal",
        ant2_wins=0, total_compared=0,
    )
    assert "--" in cp._a1_count_label.text()


# ──────────────────────────────────────────────────────────────────────
# Bonus — _update_gain_status_display existiert und ruft setText
# ──────────────────────────────────────────────────────────────────────


def test_p83_t_bonus_update_gain_status_display():
    """Helper-Methode existiert, ruft dx_info.setText mit HTML."""
    from ui import mw_radio
    entry = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": time.time() - 1800,  # 30 Min alt
    }
    obj = _make_mw_with_gain_entry(entry)
    obj.control_panel = MagicMock()
    # _format_gain_status muss echter Helper sein, nicht MagicMock-Auto.
    obj._format_gain_status = lambda b, m: mw_radio.RadioMixin._format_gain_status(obj, b, m)
    mw_radio.RadioMixin._update_gain_status_display(obj)
    obj.control_panel.dx_info.setText.assert_called_once()
    call_arg = obj.control_panel.dx_info.setText.call_args[0][0]
    assert "<span" in call_arg  # HTML-Format


def test_app_version_bundle_m():
    import main
    # P82 (v0.97.55) bumpt weiter — Bundle M-Baseline bleibt ≥0.97.54.
    assert main.APP_VERSION >= "0.97.54"
