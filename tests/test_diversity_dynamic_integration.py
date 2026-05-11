"""Integration-Tests fuer P34 — DiversityController + DynamicDiversityController.

V3 §3.3 R1-Liste — Test 19-26 + Bonus-Tests.
"""
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from core.diversity import DiversityController
from core.dynamic_diversity import DynamicDiversityController


@pytest.fixture
def ctrl_pair():
    static = DiversityController(scoring_mode="normal")
    static._phase = "operate"
    dynamic = DynamicDiversityController(static)
    return static, dynamic


def test_reset_clears_buffer(ctrl_pair):
    """reset() leert beide Buffer + setzt Ratio 50:50."""
    static, dynamic = ctrl_pair
    dynamic.activate()
    for _ in range(3):
        dynamic.record_slot("A1", 80.0)
        dynamic.record_slot("A2", 40.0)
    assert len(dynamic.buffer_a1) == 3
    static.ratio = "70:30"
    static.dominant = "A1"

    dynamic.reset()

    assert dynamic.buffer_a1 == []
    assert dynamic.buffer_a2 == []
    assert static.ratio == "50:50"
    assert static.dominant is None
    # _active bleibt unangetastet
    assert dynamic.is_active() is True


def test_scoring_mode_change_triggers_reset(ctrl_pair):
    """scoring_mode-Wechsel ueber Callback → Buffer leer + Ratio 50:50."""
    static, dynamic = ctrl_pair
    dynamic.activate()
    for _ in range(3):
        dynamic.record_slot("A1", 100.0)
    assert len(dynamic.buffer_a1) == 3

    # Wechsel triggert Listener-Callback (siehe DiversityController.scoring_mode-setter)
    static.scoring_mode = "dx"

    # Buffer wurde via Callback geleert
    assert dynamic.buffer_a1 == []
    assert dynamic.buffer_a2 == []


def test_scoring_mode_same_value_no_reset(ctrl_pair):
    """Setter auf gleichen Wert → kein Listener-Aufruf, Buffer bleibt."""
    static, dynamic = ctrl_pair
    dynamic.activate()
    dynamic.record_slot("A1", 50.0)

    static.scoring_mode = "normal"  # gleicher Wert

    assert dynamic.buffer_a1 == [50.0]


def test_should_remeasure_false_when_dynamic_active(ctrl_pair):
    """AK12: should_remeasure returnt False wenn Dynamic AN — egal Frist."""
    static, dynamic = ctrl_pair
    static._last_measured_at = time.time() - 86400  # 24h alt
    dynamic.activate()

    assert static.should_remeasure(qso_active=False, cq_active=False) is False


def test_should_remeasure_normal_when_dynamic_inactive(ctrl_pair):
    """Dynamic AUS → normales Verhalten: 24h alt → True."""
    static, dynamic = ctrl_pair
    static._last_measured_at = time.time() - 86400
    # Dynamic nie aktiviert

    assert static.should_remeasure(qso_active=False, cq_active=False) is True


def test_static_evaluate_refactor_keeps_behavior(ctrl_pair):
    """AK1 + AK2: Statische _evaluate() liefert exakt gleiche Ergebnisse
    nach Refactor auf evaluate_ratio Helper.
    """
    static, _dynamic = ctrl_pair
    # Statik-Pattern simulieren: starke ANT1, schwache ANT2
    static._phase = "measure"
    static._measurements = {"A1": [100.0, 100.0, 100.0],
                             "A2": [50.0, 50.0, 50.0]}
    static._measure_step = 6
    static._evaluate()
    assert static.ratio == "70:30"
    assert static.dominant == "A1"
    assert static.phase == "operate"

    # Edge: beide schwach → 50:50
    static._phase = "measure"
    static._measurements = {"A1": [3.0, 3.0], "A2": [4.0, 4.0]}
    static._evaluate()
    assert static.ratio == "50:50"
    assert static.dominant is None


def test_signal_emitted_on_ratio_change(ctrl_pair):
    """ratio_changed_dynamic Signal trifft genau 1× pro Wechsel.

    Test ohne qtbot — Signal.connect ohne Connection-Type triggert
    DirectConnection im Test-Thread (kein QApp-Event-Loop noetig).
    """
    static, dynamic = ctrl_pair
    dynamic.activate()
    signals_received = []
    dynamic.ratio_changed_dynamic.connect(signals_received.append)

    # 5+5 mit klarer Dominanz → Wechsel zu 70:30
    for _ in range(5):
        dynamic.record_slot("A1", 100.0)
    for _ in range(5):
        dynamic.record_slot("A2", 30.0)

    assert "70:30" in signals_received


def test_signal_not_emitted_when_no_change(ctrl_pair):
    """Wenn Ratio gleich bleibt → kein Signal."""
    static, dynamic = ctrl_pair
    dynamic.activate()
    # 5+5 mit Differenz unter Threshold → bleibt 50:50
    for _ in range(5):
        dynamic.record_slot("A1", 100.0)
    for _ in range(5):
        dynamic.record_slot("A2", 96.0)  # 4% diff < 8%

    signals_received = []
    dynamic.ratio_changed_dynamic.connect(signals_received.append)

    # Nochmal Werte rein, Ratio bleibt 50:50 → kein Signal
    dynamic.record_slot("A1", 100.0)
    assert signals_received == []


def test_thread_safety_concurrent_record(ctrl_pair):
    """Threads schreiben parallel → kein Crash, Buffer bleibt konsistent."""
    static, dynamic = ctrl_pair
    dynamic.activate()

    def writer_a1():
        for _ in range(100):
            dynamic.record_slot("A1", 50.0)

    def writer_a2():
        for _ in range(100):
            dynamic.record_slot("A2", 60.0)

    threads = [threading.Thread(target=writer_a1),
               threading.Thread(target=writer_a2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Buffer-Maxlen muss eingehalten sein
    assert len(dynamic.buffer_a1) == 5
    assert len(dynamic.buffer_a2) == 5


def test_settings_toggle_not_persisted(tmp_path, monkeypatch):
    """AK13: Toggle-Wert wird NICHT in settings.json geschrieben."""
    from config.settings import Settings
    # Test-Settings-File in tmp
    monkeypatch.setattr("config.settings.CONFIG_FILE", tmp_path / "config.json")

    settings = Settings()
    assert settings.dynamic_diversity_enabled is False
    settings.dynamic_diversity_enabled = True
    settings.save()

    # Datei lesen — Toggle darf nicht drin sein
    if (tmp_path / "config.json").exists():
        with open(tmp_path / "config.json") as f:
            data = json.load(f)
        assert "_dynamic_enabled" not in data
        assert "dynamic_diversity_enabled" not in data

    # Frische Settings → Default False
    settings2 = Settings()
    assert settings2.dynamic_diversity_enabled is False


def test_deactivate_when_not_active_idempotent(ctrl_pair):
    """deactivate() ohne vorheriges activate() darf nicht crashen."""
    static, dynamic = ctrl_pair
    # _active default False
    dynamic.deactivate()
    assert dynamic.is_active() is False


def test_activate_when_already_active_idempotent(ctrl_pair):
    """Doppelter activate() ist sicher — Buffer wird trotzdem zurueckgesetzt."""
    static, dynamic = ctrl_pair
    dynamic.activate()
    dynamic.record_slot("A1", 70.0)
    assert len(dynamic.buffer_a1) == 1

    dynamic.activate()  # idempotent + leert nochmal
    assert dynamic.buffer_a1 == []
    assert dynamic.is_active() is True
