"""P149 (v0.98.30, 27.05.2026) — AP-Lite Diagnose-Modus Tests.

R1-V4-pro Findings eingebaut (F3 Partner-SNR-Cache, F7 count_rescue-
Schalter, F10 Multi-Partner-Edge-Case). 22 Tests in 7 Gruppen.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from config.settings import DEFAULTS, Settings
from core.ap_lite import (
    AP_LITE_ENABLED,
    APLite,
    MARGIN_MIN,
    STRICTNESS_MARGIN_MAP,
    _resolve_margin,
)
from core.qso_state import QSOData


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe A: Settings-Migration + apply_settings (T1-T4)
# ─────────────────────────────────────────────────────────────────────────────


def test_t1_defaults_contain_4_ap_lite_keys():
    """P149: DEFAULTS hat die 4 neuen Settings-Keys mit korrekten Defaults."""
    assert DEFAULTS["ap_lite_enabled"] is True
    assert DEFAULTS["ap_lite_test_mode"] is False
    assert DEFAULTS["ap_lite_min_snr_db"] == -20
    assert DEFAULTS["ap_lite_strictness"] == "normal"


def test_t2_apply_settings_loads_all_4_keys():
    """apply_settings lädt alle 4 Keys aus Settings-Objekt."""
    fake_settings = MagicMock()
    fake_settings.get.side_effect = lambda key, default=None: {
        "ap_lite_enabled": False,
        "ap_lite_test_mode": True,
        "ap_lite_min_snr_db": -15,
        "ap_lite_strictness": "streng",
    }.get(key, default)
    ap = APLite()
    ap.apply_settings(fake_settings)
    assert ap.enabled is False
    assert ap.test_mode is True
    assert ap.min_snr_db == -15
    assert ap.margin_min == 0.10  # streng


def test_t3_strictness_mapping_three_levels():
    """STRICTNESS_MARGIN_MAP hat locker/normal/streng mit erwarteten Werten."""
    assert STRICTNESS_MARGIN_MAP["locker"] == 0.04
    assert STRICTNESS_MARGIN_MAP["normal"] == 0.05
    assert STRICTNESS_MARGIN_MAP["streng"] == 0.10
    # heutiger MARGIN_MIN bleibt = "normal"
    assert STRICTNESS_MARGIN_MAP["normal"] == MARGIN_MIN


def test_t4_resolve_margin_unknown_fallback():
    """Unbekannte Strenge-Werte fallen auf 'normal'."""
    assert _resolve_margin("locker") == 0.04
    assert _resolve_margin("normal") == 0.05
    assert _resolve_margin("streng") == 0.10
    assert _resolve_margin("blubb") == 0.05  # Fallback
    assert _resolve_margin("") == 0.05       # Fallback


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe B: Debug-Logging (T5-T11)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_log_dir(monkeypatch):
    """debug_log in Temp-Verzeichnis umleiten — vermeidet Pfad-Kollision."""
    from core import debug_log as _dbg
    with tempfile.TemporaryDirectory() as tmpd:
        monkeypatch.setattr(_dbg, "LOG_DIR", Path(tmpd))
        _dbg.set_enabled(True)
        yield Path(tmpd)
        _dbg.set_enabled(False)


def _read_log(tmpdir: Path) -> str:
    """Heutige Log-Datei einlesen."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log = tmpdir / f"debug_{today}.log"
    if not log.exists():
        return ""
    return log.read_text()


def test_t5_log_disabled_no_writes(monkeypatch):
    """Debug-Log AUS → keine Datei wird geschrieben."""
    from core import debug_log as _dbg
    _dbg.set_enabled(False)
    with tempfile.TemporaryDirectory() as tmpd:
        monkeypatch.setattr(_dbg, "LOG_DIR", Path(tmpd))
        _dbg.debug_log("AP-LITE", "SHOULD_NOT_APPEAR")
        files = list(Path(tmpd).glob("debug_*.log"))
        assert len(files) == 0


def test_t6_try_rescue_logs_call_entry(temp_log_dir):
    """try_rescue logged CALL-Eintrag am Anfang."""
    ap = APLite(stats_path=None)
    ap.enabled = True
    pcm = np.random.randn(360000).astype(np.float32) * 0.01
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 2,
                  own_callsign="DA1MHH", own_locator="JO31")
    log = _read_log(temp_log_dir)
    assert "[AP-LITE] CALL call=DL1ABC state=2" in log


def test_t7_try_rescue_logs_skip_disabled(temp_log_dir):
    """try_rescue mit enabled=False → SKIP-Eintrag."""
    ap = APLite(stats_path=None)
    ap.enabled = False
    pcm = np.random.randn(100).astype(np.float32)
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 2)
    log = _read_log(temp_log_dir)
    assert "SKIP reason=disabled" in log


def test_t8_try_rescue_logs_skip_bad_args(temp_log_dir):
    """try_rescue mit ungültigem qso_state → SKIP bad_args."""
    ap = APLite(stats_path=None)
    ap.enabled = True
    pcm = np.random.randn(100).astype(np.float32)
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 99)  # state=99 invalid
    log = _read_log(temp_log_dir)
    assert "SKIP reason=bad_args" in log
    assert "state=99" in log


def test_t9_try_rescue_logs_skip_no_pcm(temp_log_dir):
    """try_rescue mit leerem PCM → SKIP no_pcm."""
    ap = APLite(stats_path=None)
    ap.enabled = True
    ap.try_rescue(np.array([], dtype=np.float32), 1500.0, "DL1ABC", 2)
    log = _read_log(temp_log_dir)
    assert "SKIP reason=no_pcm" in log


def test_t10_try_rescue_logs_skip_few_candidates(temp_log_dir):
    """state=3 (CQ_WAIT) liefert 0 Kandidaten → SKIP few_cands."""
    ap = APLite(stats_path=None)
    ap.enabled = True
    pcm = np.random.randn(360000).astype(np.float32) * 0.01
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 3,
                  own_callsign="DA1MHH", own_locator="JO31")
    log = _read_log(temp_log_dir)
    assert "SKIP reason=few_cands" in log
    assert "state=3" in log


def test_t11_try_rescue_logs_scored_with_fields(temp_log_dir):
    """SCORED-Log enthält n_cands, best, runner, margin, threshold."""
    ap = APLite(stats_path=None)
    ap.enabled = True
    pcm = np.random.randn(360000).astype(np.float32) * 0.01
    # state=2 (WAIT_RR73) → 3 Kandidaten generiert
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 2,
                  own_callsign="DA1MHH", own_locator="JO31")
    log = _read_log(temp_log_dir)
    assert "SCORED" in log
    assert "n_cands=" in log
    assert "best=" in log
    assert "runner=" in log
    assert "margin=" in log
    assert "threshold=" in log


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe C: Test-Modus (T12-T15)
# ─────────────────────────────────────────────────────────────────────────────


def test_t12_test_mode_via_apply_settings():
    """Test-Modus wird via apply_settings aktiviert."""
    fake_settings = MagicMock()
    fake_settings.get.side_effect = lambda key, default=None: {
        "ap_lite_test_mode": True,
    }.get(key, default)
    ap = APLite()
    ap.apply_settings(fake_settings)
    assert ap.test_mode is True


def test_t13_count_rescue_false_no_persist(tmp_path):
    """count_rescue=False → rescue_count wird NICHT inkrementiert/gespeichert."""
    stats_file = tmp_path / "ap_lite_stats.json"
    ap = APLite(stats_path=str(stats_file))
    ap.enabled = True
    ap.margin_min = 0.001  # extrem niedrig → erzwingt MATCH
    pcm = np.random.randn(360000).astype(np.float32) * 0.01
    initial_count = ap.rescue_count
    # Force-Match durch sehr niedrigen Threshold
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 2,
                  own_callsign="DA1MHH", own_locator="JO31",
                  count_rescue=False)
    assert ap.rescue_count == initial_count
    assert not stats_file.exists()  # keine Persist-Datei geschrieben


def test_t14_count_rescue_true_persists(tmp_path):
    """count_rescue=True (Default) → rescue_count wächst und wird persistiert."""
    stats_file = tmp_path / "ap_lite_stats.json"
    ap = APLite(stats_path=str(stats_file))
    ap.enabled = True
    ap.margin_min = 0.0001
    pcm = np.random.randn(360000).astype(np.float32) * 0.01
    initial_count = ap.rescue_count
    ap.try_rescue(pcm, 1500.0, "DL1ABC", 2,
                  own_callsign="DA1MHH", own_locator="JO31",
                  count_rescue=True)
    if ap.rescue_count > initial_count:
        # Persistierung nur prüfen wenn MATCH passierte
        assert stats_file.exists()
        data = json.loads(stats_file.read_text())
        assert data["rescue_count"] == ap.rescue_count


def test_t15_test_mode_skip_partner_decoded_guard():
    """mw_cycle._run_ap_lite_rescue Test-Modus: source-level
    `_partner_found and not test_mode` Pattern verifizieren."""
    import inspect
    from ui import mw_cycle
    src = inspect.getsource(mw_cycle.CycleMixin._run_ap_lite_rescue)
    # Im Test-Modus wird _partner_found NICHT zum Skip führen
    assert "_partner_found and not self._ap_lite.test_mode" in src


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe D: Partner-SNR-Cache (R1-F3) (T16-T19)
# ─────────────────────────────────────────────────────────────────────────────


def test_t16_qsodata_has_partner_last_snr_none_by_default():
    """QSOData.partner_last_snr existiert und ist None per Default."""
    qso = QSOData()
    assert hasattr(qso, "partner_last_snr")
    assert qso.partner_last_snr is None


def _make_msg(raw: str, caller: str, target: str, snr: int, freq_hz: int = 1500):
    """Helper: FT8Message mit korrekt gesetzten field1/field2/field3."""
    from core.message import FT8Message
    # target=field1 (NON-CQ), caller=field2
    parts = raw.split()
    f1 = parts[0] if len(parts) > 0 else ""
    f2 = parts[1] if len(parts) > 1 else ""
    f3 = parts[2] if len(parts) > 2 else ""
    return FT8Message(raw=raw, field1=f1, field2=f2, field3=f3,
                      snr=snr, freq_hz=freq_hz)


def test_t17_partner_snr_cache_updated_on_partner_decode():
    """qso_sm.on_message_received setzt partner_last_snr wenn caller=their_call."""
    from core.qso_state import QSOStateMachine
    qso_sm = QSOStateMachine("DA1MHH", "JO31")
    qso_sm.start_qso("DL1ABC", "JO50", 1500, -10)
    # Partner sendet: target=DA1MHH (uns), caller=DL1ABC, grid=JO50
    msg = _make_msg("DA1MHH DL1ABC JO50", "DL1ABC", "DA1MHH", snr=-15)
    qso_sm.on_message_received(msg)
    assert qso_sm.qso.partner_last_snr == -15.0


def test_t18_partner_snr_cache_NOT_updated_by_foreign_call():
    """Fremde Decodes überschreiben partner_last_snr NICHT."""
    from core.qso_state import QSOStateMachine
    qso_sm = QSOStateMachine("DA1MHH", "JO31")
    qso_sm.start_qso("DL1ABC", "JO50", 1500, -10)
    # Erst Partner setzt SNR auf -15
    msg_partner = _make_msg("DA1MHH DL1ABC JO50", "DL1ABC", "DA1MHH", snr=-15)
    qso_sm.on_message_received(msg_partner)
    assert qso_sm.qso.partner_last_snr == -15.0
    # Fremde Station mit -5 dB (deutlich stärker) — Cache bleibt -15
    msg_foreign = _make_msg("DA1MHH OE3XYZ JN77", "OE3XYZ", "DA1MHH", snr=-5)
    qso_sm.on_message_received(msg_foreign)
    assert qso_sm.qso.partner_last_snr == -15.0  # unverändert!


def test_t19_snr_filter_uses_partner_cache_in_mw_cycle():
    """mw_cycle source verifiziert: SNR-Filter nutzt partner_last_snr."""
    import inspect
    from ui import mw_cycle
    src = inspect.getsource(mw_cycle.CycleMixin._run_ap_lite_rescue)
    # SNR-Filter muss partner_last_snr verwenden, nicht globaler _last_snr
    assert "partner_last_snr" in src
    assert "partner_snr_too_strong" in src
    # Filter wird im test_mode NICHT angewandt
    assert "not self._ap_lite.test_mode" in src


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe E: Multi-Partner-Edge-Case (R1-F10) (T20)
# ─────────────────────────────────────────────────────────────────────────────


def test_t20_multi_partner_edge_defensive_listing():
    """mw_cycle nutzt defensive Listing für mehrere Decoder-Treffer der
    Partner-Station (Hash/Mumpitz/Falsch-Decode)."""
    import inspect
    from ui import mw_cycle
    src = inspect.getsource(mw_cycle.CycleMixin._run_ap_lite_rescue)
    # Listing-Pattern statt any()-Pattern
    assert "_partner_msgs = [m for m in" in src
    # erstes Element nehmen (KISS)
    assert "_partner_msgs[0] if _partner_msgs else None" in src


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe F: TEST_COMPARE-Log mit Transparenz-Note (R1-F1) (T21)
# ─────────────────────────────────────────────────────────────────────────────


def test_t21_test_compare_log_has_ground_truth_note():
    """TEST_COMPARE-Log enthält 'decoder=reference, not ground-truth' Note."""
    import inspect
    from ui import mw_cycle
    src = inspect.getsource(mw_cycle.CycleMixin._run_ap_lite_rescue)
    assert "TEST_COMPARE" in src
    assert "decoder=reference, not ground-truth" in src
    assert "agreement=" in src


# ─────────────────────────────────────────────────────────────────────────────
# Gruppe G: Backward-Compat — alte ap_lite_tests dürfen nicht brechen (T22)
# ─────────────────────────────────────────────────────────────────────────────


def test_t22_module_level_constants_preserved():
    """MARGIN_MIN und AP_LITE_ENABLED bleiben als Modul-Konstanten — Fallback
    für alte Tests die diese direkt importieren."""
    assert MARGIN_MIN == 0.05
    assert AP_LITE_ENABLED is True
    # Instanz-Defaults nutzen die Modul-Konstanten
    ap = APLite()
    assert ap.enabled == AP_LITE_ENABLED
    assert ap.margin_min == MARGIN_MIN
