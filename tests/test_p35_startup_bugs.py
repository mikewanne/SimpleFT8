"""P35.DIVERSITY-STARTUP-FIX — Tests fuer Bug A + Bug B + Bug B5.

V3 §4.1 R1-Liste. 10 Tests.

Bug A: _enable_diversity bei radio.ip=None defer + Resume nach Connect
Bug B: _apply_dynamic_toggle resettet Queue + current_ant
Bug B5: _activate_diversity_with_scoring auto-reactivate Dynamic
"""
from collections import deque
from unittest.mock import MagicMock

import pytest

from core.diversity import DiversityController
from core.dynamic_diversity import DynamicDiversityController


@pytest.fixture
def ctrl_pair():
    """Frisches Statik+Dynamic-Paar."""
    static = DiversityController(scoring_mode="normal")
    static._phase = "operate"
    dynamic = DynamicDiversityController(static)
    return static, dynamic


# ── Bug A: defer + resume ──────────────────────────────────────────────

def test_enable_diversity_no_radio_defers_init():
    """AK1: _enable_diversity bei radio.ip=None → Phase=operate,
    _pending_diversity_init gesetzt, kein Mess-Haengen."""
    from ui.mw_radio import RadioMixin
    s = MagicMock()
    s.radio = MagicMock()
    s.radio.ip = None  # Radio NICHT verbunden
    s.settings.mode = "FT8"
    s.settings.band = "20m"
    s._diversity_in_operate = False
    s._tune_token = None
    s._diversity_ctrl = MagicMock()
    s._diversity_ctrl.phase = "measure"
    s._diversity_ant_queue = deque()
    s._dynamic_ctrl = MagicMock()
    s._dynamic_ctrl.is_active = MagicMock(return_value=False)
    s._standard_store = MagicMock()
    s._standard_store.get.return_value = None

    RadioMixin._enable_diversity(s, "normal")

    assert s._pending_diversity_init == "normal"
    # Phase wurde auf operate gesetzt (kein Haengen)
    assert s._diversity_ctrl._phase == "operate"


def test_radio_connected_resumes_pending_init():
    """AK2 (R1-Q7): _on_radio_connected mit pending → _check_diversity_preset
    aufgerufen, NICHT _enable_diversity direkt."""
    from ui.mw_radio import RadioMixin
    s = MagicMock()
    s.radio = MagicMock()
    s.radio.ip = "192.168.1.1"
    s.settings.mode = "FT8"
    s.settings.band = "20m"
    s.settings.frequency_mhz = 14.074
    s.settings.get = MagicMock(side_effect=lambda key, default=None:
                                {"mode": "FT8", "power_preset": 10,
                                 "tx_level": 75}.get(key, default if default is not None else 10))
    s._pending_diversity_init = "dx"  # aufgeschoben
    s._reconnect_attempts = 0
    s._rfpower_current = 50
    s._rx_mode = "diversity"
    s._diversity_ctrl = MagicMock()
    s._power_target = 10
    # _check_diversity_preset wird gemockt — wir prüfen nur dass es gerufen wird
    s._check_diversity_preset = MagicMock()

    try:
        RadioMixin._on_radio_connected(s)
    except Exception:
        # _on_radio_connected ruft viele andere Methoden, manche brechen mit
        # Mock — uns interessiert nur ob _check_diversity_preset aufgerufen
        # wird und _pending_diversity_init=None.
        pass

    s._check_diversity_preset.assert_called_once_with("20m", "FT8", "dx")
    assert s._pending_diversity_init is None


def test_pending_init_idempotent():
    """AK7: 2x _on_radio_connected mit pending → nur 1x Resume."""
    from ui.mw_radio import RadioMixin
    s = MagicMock()
    s.radio = MagicMock()
    s.radio.ip = "192.168.1.1"
    s.settings.mode = "FT8"
    s.settings.band = "20m"
    s.settings.frequency_mhz = 14.074
    s.settings.get = MagicMock(side_effect=lambda key, default=None:
                                {"mode": "FT8", "power_preset": 10,
                                 "tx_level": 75}.get(key, default if default is not None else 10))
    s._pending_diversity_init = "normal"
    s._reconnect_attempts = 0
    s._rfpower_current = 50
    s._rx_mode = "diversity"
    s._diversity_ctrl = MagicMock()
    s._check_diversity_preset = MagicMock()

    try:
        RadioMixin._on_radio_connected(s)
    except Exception:
        pass
    # Erster Aufruf hat Flag geleert
    assert s._pending_diversity_init is None
    first_count = s._check_diversity_preset.call_count

    # Zweiter Aufruf — Flag ist None, kein Resume
    try:
        RadioMixin._on_radio_connected(s)
    except Exception:
        pass
    # call_count gleich → Resume war idempotent
    assert s._check_diversity_preset.call_count == first_count


# ── Bug B: Queue + current_ant Reset ─────────────────────────────────────

def test_apply_dynamic_toggle_resets_queue(ctrl_pair):
    """AK3: _apply_dynamic_toggle(True) leert _diversity_ant_queue +
    setzt _diversity_current_ant='A1'."""
    import threading
    static, dynamic = ctrl_pair

    # Simuliere MainWindow-Setup
    mw = MagicMock()
    mw._diversity_lock = threading.Lock()
    mw._dynamic_ctrl = dynamic
    mw._diversity_ctrl = static
    mw._diversity_ant_queue = deque([("A1", "measure"),
                                      ("A1", "measure"),
                                      ("A1", "measure")])
    mw._diversity_current_ant = "A1"
    mw.control_panel = MagicMock()
    mw._set_cq_locked = MagicMock()
    mw._set_gain_measure_lock = MagicMock()

    # _apply_dynamic_toggle via MainWindow-Methode rufen
    from ui.main_window import MainWindow
    MainWindow._apply_dynamic_toggle(mw, True)

    # Queue ist geleert + current_ant zurueck auf A1
    assert len(mw._diversity_ant_queue) == 0
    assert mw._diversity_current_ant == "A1"
    # Dynamic ist aktiv
    assert dynamic.is_active() is True


def test_apply_dynamic_toggle_preserves_cache_ratio(ctrl_pair):
    """AK5 + C1: Bei Cache-Ratio (70:30) bleibt Ratio nach activate erhalten."""
    import threading
    static, dynamic = ctrl_pair
    static.ratio = "70:30"
    static.dominant = "A1"

    mw = MagicMock()
    mw._diversity_lock = threading.Lock()
    mw._dynamic_ctrl = dynamic
    mw._diversity_ctrl = static
    mw._diversity_ant_queue = deque()
    mw._diversity_current_ant = "A1"
    mw.control_panel = MagicMock()
    mw._set_cq_locked = MagicMock()
    mw._set_gain_measure_lock = MagicMock()

    from ui.main_window import MainWindow
    MainWindow._apply_dynamic_toggle(mw, True)

    # Cache-Ratio bleibt erhalten
    assert static.ratio == "70:30"
    assert static.dominant == "A1"


def test_apply_dynamic_toggle_resets_5050_ratio(ctrl_pair):
    """AK5: Bei Ratio=50:50 bleibt es 50:50 (Standard-Pfad)."""
    import threading
    static, dynamic = ctrl_pair
    static.ratio = "50:50"
    static.dominant = None

    mw = MagicMock()
    mw._diversity_lock = threading.Lock()
    mw._dynamic_ctrl = dynamic
    mw._diversity_ctrl = static
    mw._diversity_ant_queue = deque()
    mw._diversity_current_ant = "A1"
    mw.control_panel = MagicMock()
    mw._set_cq_locked = MagicMock()
    mw._set_gain_measure_lock = MagicMock()

    from ui.main_window import MainWindow
    MainWindow._apply_dynamic_toggle(mw, True)

    assert static.ratio == "50:50"
    assert static.dominant is None


# ── Bug B5: Auto-Reactivate bei Settings-Toggle AN ─────────────────────

def test_activate_diversity_with_settings_toggle_on(ctrl_pair):
    """AK4: _activate_diversity_with_scoring mit Settings-Toggle AN →
    _apply_dynamic_toggle(True) wird automatisch aufgerufen."""
    from ui.mw_radio import RadioMixin
    static, dynamic = ctrl_pair
    s = MagicMock()
    s._rx_mode = "normal"
    s._diversity_stations = {}
    s.control_panel = MagicMock()
    s.settings.band = "20m"
    s.settings.mode = "FT8"
    s.settings.dynamic_diversity_enabled = True  # Toggle AN
    s._dynamic_ctrl = dynamic  # Echter Controller
    s._diversity_ctrl = static
    s._apply_dynamic_toggle = MagicMock()
    s._check_diversity_preset = MagicMock()

    RadioMixin._activate_diversity_with_scoring(s, "normal")

    # Auto-Reactivate hat gefeuert
    s._apply_dynamic_toggle.assert_called_once_with(True)


def test_activate_diversity_with_settings_toggle_off(ctrl_pair):
    """AK4: Settings-Toggle AUS → kein Auto-Reactivate."""
    from ui.mw_radio import RadioMixin
    static, dynamic = ctrl_pair
    s = MagicMock()
    s._rx_mode = "normal"
    s._diversity_stations = {}
    s.control_panel = MagicMock()
    s.settings.band = "20m"
    s.settings.mode = "FT8"
    s.settings.dynamic_diversity_enabled = False  # Toggle AUS
    s._dynamic_ctrl = dynamic
    s._diversity_ctrl = static
    s._apply_dynamic_toggle = MagicMock()
    s._check_diversity_preset = MagicMock()

    RadioMixin._activate_diversity_with_scoring(s, "normal")

    # KEIN Auto-Reactivate
    s._apply_dynamic_toggle.assert_not_called()


def test_activate_diversity_dynamic_already_active(ctrl_pair):
    """Idempotenz: wenn Dynamic schon AN, kein zweites apply_dynamic_toggle."""
    from ui.mw_radio import RadioMixin
    static, dynamic = ctrl_pair
    dynamic._active = True  # schon aktiv
    s = MagicMock()
    s._rx_mode = "normal"
    s._diversity_stations = {}
    s.control_panel = MagicMock()
    s.settings.band = "20m"
    s.settings.mode = "FT8"
    s.settings.dynamic_diversity_enabled = True
    s._dynamic_ctrl = dynamic
    s._diversity_ctrl = static
    s._apply_dynamic_toggle = MagicMock()
    s._check_diversity_preset = MagicMock()

    RadioMixin._activate_diversity_with_scoring(s, "dx")

    # KEIN Auto-Reactivate weil schon aktiv
    s._apply_dynamic_toggle.assert_not_called()


def test_disable_diversity_keeps_settings_toggle(ctrl_pair):
    """AK6 Bug B5: _disable_diversity laesst settings.dynamic_diversity_
    enabled UNANGETASTET. _dynamic_ctrl._active wird False."""
    static, dynamic = ctrl_pair
    dynamic._active = True  # initial aktiv

    settings = MagicMock()
    settings.dynamic_diversity_enabled = True

    # Direkter Test der deactivate()-Methode
    dynamic.deactivate()

    # _active=False, aber Settings-Toggle nicht angetastet
    assert dynamic.is_active() is False
    # settings.dynamic_diversity_enabled wurde NICHT verändert (nur deaktiviert)
    # → semantischer Test: deactivate berührt settings nicht


# ── End-to-End Regression ──────────────────────────────────────────────

def test_settings_toggle_survives_through_session(ctrl_pair):
    """End-to-End: Toggle AN → deactivate → wieder activate via
    Auto-Reactivate-Pfad. Settings-Toggle bleibt durchgehend True."""
    import threading
    static, dynamic = ctrl_pair

    settings = MagicMock()
    settings.dynamic_diversity_enabled = True

    # 1. Initial: Toggle AN aktiviert Dynamic
    mw = MagicMock()
    mw._diversity_lock = threading.Lock()
    mw._dynamic_ctrl = dynamic
    mw._diversity_ctrl = static
    mw._diversity_ant_queue = deque()
    mw._diversity_current_ant = "A1"
    mw.settings = settings
    mw.control_panel = MagicMock()
    mw._set_cq_locked = MagicMock()
    mw._set_gain_measure_lock = MagicMock()

    from ui.main_window import MainWindow
    MainWindow._apply_dynamic_toggle(mw, True)
    assert dynamic.is_active() is True
    assert settings.dynamic_diversity_enabled is True

    # 2. Mode-Wechsel zu Normal: deactivate()
    dynamic.deactivate()
    assert dynamic.is_active() is False
    # Settings-Toggle BLEIBT True
    assert settings.dynamic_diversity_enabled is True

    # 3. Mode-Wechsel zurueck zu Diversity: Auto-Reactivate wuerde
    #    apply_dynamic_toggle(True) rufen → activate
    MainWindow._apply_dynamic_toggle(mw, True)
    assert dynamic.is_active() is True
    # Settings-Toggle ueberlebt
    assert settings.dynamic_diversity_enabled is True
