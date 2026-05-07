"""Tests fuer P1.CACHE-SIMPLE (v0.95.13) — Diversity/Gain-Cache entkoppelt.

Mike-Vision 2026-05-07: Diversity-Cache (Ratio, 60 Min) und Gain-Cache (6h)
komplett entkoppelt. Keine Modal-Wahl-Dialoge fuer Routine-Aktionen.

Logik in `_check_diversity_preset` Dispatch:
- Gain stale  → DXTuneDialog (auto-start, nur Abbruch). Wenn Ratio fresh:
                nach Gain-OK Cache-Reuse statt Phase 3.
- Gain missing → volle Pipeline (Gain + Ratio).
- Gain fresh + Ratio fresh → Cache-Reuse (still).
- Gain fresh + Ratio stale/missing → stille Auto-Ratio-Messung.

Plus Stale-Acceptance bei DXTuneDialog-Cancel:
- Wenn alte Werte vorhanden → laden ohne Pipeline-Restart.
- Wenn nichts da → Diversity deaktivieren.

Whitebox-Tests via Mock-Self (Pattern aus test_diversity_cache_reuse.py).
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Mock-Helper ───────────────────────────────────────────────────────────


def _make_store_mock(*, ratio_valid=True, gain_valid=True,
                     has_ratio_entry=True, has_gain_timestamp=True,
                     ratio="70:30", dominant="A1",
                     gain_age_offset_sec=600, ratio_age_offset_sec=600):
    """Erstellt Mock-Store mit konfiguriertem Verhalten fuer is_valid_*+get."""
    store = MagicMock()
    store.is_valid_ratio = MagicMock(return_value=ratio_valid)
    store.is_valid_gain = MagicMock(return_value=gain_valid)
    store.get_ratio_age_minutes = MagicMock(
        return_value=int(ratio_age_offset_sec / 60))
    store.get_gain_age_minutes = MagicMock(
        return_value=int(gain_age_offset_sec / 60))
    entry = {}
    if has_ratio_entry:
        entry["ratio"] = ratio
        entry["dominant"] = dominant
        entry["ratio_timestamp"] = time.time() - ratio_age_offset_sec
    if has_gain_timestamp:
        entry["gain_timestamp"] = time.time() - gain_age_offset_sec
    store.get = MagicMock(return_value=(entry or None))
    return store


def _make_mw_self(*, store=None, scoring="normal", radio_ip="192.168.1.10",
                  rx_mode="diversity"):
    """Erstellt Mock-self fuer RadioMixin-Methoden."""
    from ui.mw_radio import RadioMixin

    fake_self = MagicMock()
    fake_self.radio = MagicMock()
    fake_self.radio.ip = radio_ip
    fake_self.settings = MagicMock()
    fake_self.settings.band = "40m"
    fake_self.settings.mode = "FT8"
    fake_self._rx_mode = rx_mode

    # Stores setzen
    if scoring == "dx":
        fake_self._dx_store = store
        fake_self._standard_store = None
    else:
        fake_self._standard_store = store
        fake_self._dx_store = None

    # Echte Helper-Methoden statt MagicMock-Auto-Returns — sonst gibt
    # _assess_ratio/_assess_gain einen MagicMock zurueck statt
    # "fresh"/"stale"/"missing" und der Dispatch kollabiert.
    fake_self._get_diversity_store = lambda s: (
        fake_self._dx_store if s == "dx" else fake_self._standard_store
    )
    fake_self._assess_ratio = lambda b, m, s: RadioMixin._assess_ratio(fake_self, b, m, s)
    fake_self._assess_gain = lambda b, m, s: RadioMixin._assess_gain(fake_self, b, m, s)

    # Diversity-Controller
    fake_self._diversity_ctrl = MagicMock()
    fake_self._diversity_ctrl.scoring_mode = scoring

    # Encoder + Pending-Flags
    fake_self.encoder = MagicMock()
    fake_self.encoder.is_transmitting = False
    fake_self._pending_dx_diversity = False
    fake_self._pending_diversity_scoring = None
    fake_self._pending_ratio_status = None
    return fake_self


# ── 1. _assess_ratio Tests ────────────────────────────────────────────────


def test_assess_ratio_fresh_stale_missing():
    """_assess_ratio liefert "fresh"/"stale"/"missing" je nach Store-State."""
    from ui.mw_radio import RadioMixin

    # fresh: is_valid_ratio True
    fresh = _make_mw_self(store=_make_store_mock(ratio_valid=True))
    assert RadioMixin._assess_ratio(fresh, "40m", "FT8", "normal") == "fresh"

    # stale: is_valid_ratio False, aber Eintrag mit ratio-Feld vorhanden
    stale = _make_mw_self(store=_make_store_mock(
        ratio_valid=False, has_ratio_entry=True))
    assert RadioMixin._assess_ratio(stale, "40m", "FT8", "normal") == "stale"

    # missing: kein store
    no_store = _make_mw_self(store=None)
    assert RadioMixin._assess_ratio(no_store, "40m", "FT8", "normal") == "missing"

    # missing: Eintrag ohne ratio-Feld
    empty = _make_mw_self(store=_make_store_mock(
        ratio_valid=False, has_ratio_entry=False))
    assert RadioMixin._assess_ratio(empty, "40m", "FT8", "normal") == "missing"


def test_assess_gain_fresh_stale_missing():
    """_assess_gain liefert "fresh"/"stale"/"missing" je nach Store-State."""
    from ui.mw_radio import RadioMixin

    fresh = _make_mw_self(store=_make_store_mock(gain_valid=True))
    assert RadioMixin._assess_gain(fresh, "40m", "FT8", "normal") == "fresh"

    stale = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=True))
    assert RadioMixin._assess_gain(stale, "40m", "FT8", "normal") == "stale"

    no_store = _make_mw_self(store=None)
    assert RadioMixin._assess_gain(no_store, "40m", "FT8", "normal") == "missing"

    empty = _make_mw_self(store=_make_store_mock(
        gain_valid=False, has_gain_timestamp=False, has_ratio_entry=False))
    assert RadioMixin._assess_gain(empty, "40m", "FT8", "normal") == "missing"


# ── 2. _check_diversity_preset Dispatch Tests ─────────────────────────────


def test_check_preset_dispatch_gain_stale_opens_dialog():
    """Gain stale → _start_dx_tuning + _pending_ratio_status gesetzt."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(
        ratio_valid=True, gain_valid=False, has_gain_timestamp=True)
    fake_self = _make_mw_self(store=store)

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    assert fake_self._pending_ratio_status == "fresh"
    assert fake_self._pending_diversity_scoring == "normal"


def test_check_preset_dispatch_gain_missing_full_pipeline():
    """Gain missing → volle Pipeline (Gain + Ratio), _pending_dx_diversity=True."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(
        ratio_valid=False, gain_valid=False,
        has_ratio_entry=False, has_gain_timestamp=False)
    fake_self = _make_mw_self(store=store)

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._start_dx_tuning.assert_called_once()
    assert fake_self._pending_dx_diversity is True
    assert fake_self._pending_diversity_scoring == "normal"


def test_check_preset_dispatch_both_fresh_cache_reuse_silent():
    """Gain fresh + Ratio fresh → Cache-Reuse, kein DXTuneDialog, kein Toast."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(ratio_valid=True, gain_valid=True)
    fake_self = _make_mw_self(store=store)
    # Wir erwarten dass _try_diversity_cache_reuse aufgerufen wird;
    # Mock-Methode damit wir den Aufruf verifizieren koennen.
    fake_self._try_diversity_cache_reuse = MagicMock(return_value=True)

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._try_diversity_cache_reuse.assert_called_once_with(
        "40m", "FT8", "normal")
    fake_self._start_dx_tuning.assert_not_called()


def test_check_preset_dispatch_ratio_stale_gain_fresh_auto_remeasure():
    """Ratio stale + Gain fresh → stille Auto-Ratio-Messung via _enable_diversity."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(
        ratio_valid=False, gain_valid=True, has_ratio_entry=True)
    fake_self = _make_mw_self(store=store)

    RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    fake_self._enable_diversity.assert_called_once()
    kwargs = fake_self._enable_diversity.call_args.kwargs
    assert kwargs.get("scoring_mode") == "normal"
    fake_self._start_dx_tuning.assert_not_called()


# ── 3. _on_dx_tune_accepted: pending_ratio_status-Pfad ────────────────────


def test_dx_tune_accepted_with_pending_ratio_fresh_uses_cache():
    """Pending-Ratio-Status="fresh" nach Gain-OK → Cache-Reuse statt Phase 3."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(ratio_valid=True, gain_valid=True)
    fake_self = _make_mw_self(store=store, scoring="normal")
    # DX-Tune-Dialog mit Result
    dialog = MagicMock()
    dialog.get_results = MagicMock(return_value={
        "best_ant": "ANT1",
        "ant1_gain": 12,
        "ant2_gain": 18,
        "best_gain": 12,
        "ant1_avg": -10.0,
        "ant2_avg": -12.0,
    })
    fake_self._dx_tune_dialog = dialog
    fake_self._gain_scoring_mode = "stations"
    fake_self._pending_ratio_status = "fresh"
    fake_self._pending_diversity_scoring = "normal"
    fake_self._pending_dx_diversity = False
    fake_self._try_diversity_cache_reuse = MagicMock(return_value=True)
    # Settings methods
    fake_self.settings.save_dx_preset = MagicMock()
    fake_self.settings.save_normal_preset = MagicMock()
    fake_self.control_panel = MagicMock()

    RadioMixin._on_dx_tune_accepted(fake_self)

    # Cache-Reuse muss aufgerufen worden sein, _enable_diversity NICHT direkt
    fake_self._try_diversity_cache_reuse.assert_called_once_with(
        "40m", "FT8", "normal")
    # _pending_ratio_status MUSS reset sein (Leak-Schutz)
    assert fake_self._pending_ratio_status is None


# ── 4. _on_dx_tune_rejected: Stale-Acceptance ─────────────────────────────


def test_dx_tune_rejected_loads_stale_values():
    """DXTuneDialog-Cancel mit alten Werten → Stale-Acceptance (laden, kein Restart)."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(
        ratio_valid=False, has_ratio_entry=True,
        ratio="50:50", dominant="A2", ratio_age_offset_sec=7200)
    fake_self = _make_mw_self(store=store, scoring="normal")
    fake_self._diversity_ctrl.scoring_mode = "normal"
    fake_self.control_panel = MagicMock()

    RadioMixin._on_dx_tune_rejected(fake_self)

    fake_self._enable_diversity.assert_called_once()
    kwargs = fake_self._enable_diversity.call_args.kwargs
    assert kwargs["cached_ratio"] == "50:50"
    assert kwargs["cached_dominant"] == "A2"
    assert kwargs["scoring_mode"] == "normal"
    # Pipeline darf NICHT restarten
    fake_self._start_dx_tuning.assert_not_called()


def test_dx_tune_rejected_no_values_disables_diversity():
    """DXTuneDialog-Cancel ohne alte Werte → Diversity deaktiviert."""
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(
        ratio_valid=False, has_ratio_entry=False, has_gain_timestamp=False)
    fake_self = _make_mw_self(store=store, scoring="normal")
    fake_self._diversity_ctrl.scoring_mode = "normal"
    fake_self.control_panel = MagicMock()

    RadioMixin._on_dx_tune_rejected(fake_self)

    fake_self._disable_diversity.assert_called_once()
    fake_self._enable_diversity.assert_not_called()


# ── 5. Anti-Regression: keine Modal-Dialoge in Routine-Pfaden ─────────────


def test_no_modal_dialog_in_normal_paths(qapp):
    """P1.CACHE-SIMPLE: Wahl-Dialog "Weiter / Neu messen" darf NICHT mehr
    auftauchen — auch nicht beim "Ratio fresh + Gain fresh"-Pfad.

    Wir patchen QDialog um sicherzustellen dass keine Instanz waehrend
    _check_diversity_preset/_activate_diversity_with_scoring erzeugt wird.
    """
    from unittest.mock import patch
    from ui.mw_radio import RadioMixin

    store = _make_store_mock(ratio_valid=True, gain_valid=True)
    fake_self = _make_mw_self(store=store)
    fake_self._try_diversity_cache_reuse = MagicMock(return_value=True)

    with patch("PySide6.QtWidgets.QDialog") as mock_dialog:
        RadioMixin._check_diversity_preset(fake_self, "40m", "FT8", "normal")

    mock_dialog.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
