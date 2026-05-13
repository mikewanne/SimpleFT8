"""Unit-Tests fuer P34 DynamicDiversityController.

15 Tests (V3 §3.1 R1-Liste). Test-File-Konvention: ohne pytest-qt, weil
DynamicDiversityController nur das Signal definiert aber keinen QApp-Kontext
braucht (Signal-Emit ist self-contained mit QueuedConnection erst beim
Connect im GUI-Thread).
"""
import time
from types import SimpleNamespace

import pytest

from core.diversity import DiversityController
from core.dynamic_diversity import DynamicDiversityController


@pytest.fixture
def ctrl_pair():
    """Erzeugt frisches Statik+Dynamic-Paar."""
    static = DiversityController(scoring_mode="normal")
    static._phase = "operate"  # Tests starten direkt im operate-Modus
    dynamic = DynamicDiversityController(static)
    return static, dynamic


def test_init_defaults(ctrl_pair):
    static, dynamic = ctrl_pair
    assert dynamic.is_active() is False
    assert dynamic.buffer_a1 == []
    assert dynamic.buffer_a2 == []


def test_activate_sets_active(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    assert dynamic.is_active() is True
    # P34-Stufe2: dynamic_active-Property entfernt (kein Statik-Hook mehr).


def test_activate_keeps_cache_ratio(ctrl_pair):
    """P35-AK5: Ratio != 50:50 (Cache-Reuse) bleibt nach activate erhalten."""
    static, dynamic = ctrl_pair
    static.ratio = "70:30"
    static.dominant = "A1"
    dynamic.activate()
    # P35-Aenderung: bestehendes Ratio bleibt (vorher P34: 50:50-Reset)
    assert static.ratio == "70:30"
    assert static.dominant == "A1"


def test_activate_resets_5050_ratio(ctrl_pair):
    """P35-AK5: Ratio=50:50 (kein Cache) bleibt 50:50 nach activate."""
    static, dynamic = ctrl_pair
    static.ratio = "50:50"
    static.dominant = None
    dynamic.activate()
    assert static.ratio == "50:50"
    assert static.dominant is None


def test_activate_with_none_ratio_becomes_5050(ctrl_pair):
    """P35-AK5: Ratio=None wird auf 50:50 gesetzt (defensive)."""
    static, dynamic = ctrl_pair
    static.ratio = None
    static.dominant = None
    dynamic.activate()
    assert static.ratio == "50:50"
    assert static.dominant is None


# P34-Stufe2: test_activate_aborts_measure_phase entfernt — measure-Phase
# existiert nicht mehr. test_deactivate_refreshes_remeasure_timestamp
# entfernt — _last_measured_at + 1h-Frist sind weg.


def test_deactivate_keeps_ratio(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    static.ratio = "30:70"  # Simuliere Dynamic-gesetzten Wert
    static.dominant = "A2"
    dynamic.deactivate()
    assert dynamic.is_active() is False
    assert static.ratio == "30:70"  # Ratio bleibt
    assert static.dominant == "A2"


def test_record_slot_a1(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    dynamic.record_slot("A1", 50.0)
    assert dynamic.buffer_a1 == [50.0]
    assert dynamic.buffer_a2 == []


def test_record_slot_inactive_no_op(ctrl_pair):
    static, dynamic = ctrl_pair
    # _active=False → record sollte keinen Effekt haben
    dynamic.record_slot("A1", 50.0)
    assert dynamic.buffer_a1 == []


def test_record_slot_invalid_ant_no_op(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    dynamic.record_slot("XX", 50.0)
    assert dynamic.buffer_a1 == []
    assert dynamic.buffer_a2 == []


def test_buffer_maxlen_fifo(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    for v in [10, 20, 30, 40, 50, 60]:  # 6 Werte → 5 bleiben
        dynamic.record_slot("A1", float(v))
    assert dynamic.buffer_a1 == [20.0, 30.0, 40.0, 50.0, 60.0]
    assert len(dynamic.buffer_a1) == 5


def test_evaluate_not_called_before_full(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    # Nur 4 + 4 Werte
    for _ in range(4):
        dynamic.record_slot("A1", 50.0)
        dynamic.record_slot("A2", 50.0)
    # Ratio darf nicht durch Dynamic gesetzt sein → 50:50 vom activate-Reset
    assert static.ratio == "50:50"
    assert static.dominant is None


def test_evaluate_70_30_when_a1_dominates(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    # 5 ANT1-Werte hoch, 5 ANT2-Werte niedrig
    for _ in range(5):
        dynamic.record_slot("A1", 100.0)
    for _ in range(5):
        dynamic.record_slot("A2", 50.0)
    # rel_diff 50% > 8% → 70:30
    assert static.ratio == "70:30"
    assert static.dominant == "A1"


def test_evaluate_30_70_when_a2_dominates(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    for _ in range(5):
        dynamic.record_slot("A1", 50.0)
    for _ in range(5):
        dynamic.record_slot("A2", 100.0)
    assert static.ratio == "30:70"
    assert static.dominant == "A2"


def test_evaluate_50_50_below_threshold(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    # 5% diff < 8% → 50:50
    for _ in range(5):
        dynamic.record_slot("A1", 100.0)
    for _ in range(5):
        dynamic.record_slot("A2", 95.0)
    assert static.ratio == "50:50"
    assert static.dominant is None


def test_evaluate_50_50_below_min_peak(ctrl_pair):
    static, dynamic = ctrl_pair
    dynamic.activate()
    # Beide unter MIN_PEAK_SCORE=5.0
    for _ in range(5):
        dynamic.record_slot("A1", 4.0)
    for _ in range(5):
        dynamic.record_slot("A2", 2.0)
    assert static.ratio == "50:50"
    assert static.dominant is None
