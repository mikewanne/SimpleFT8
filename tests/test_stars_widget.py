"""P1.19: StarsConditionWidget Render-Tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_widget():
    _ensure_app()
    from ui.widgets.stars_widget import StarsConditionWidget
    return StarsConditionWidget()


def test_stars_widget_set_score_renders():
    w = _make_widget()
    w.set_score(3)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 3


def test_stars_widget_tooltip():
    w = _make_widget()
    w.set_score(5, "31 Stationen, Median -10 dB")
    assert w.toolTip() == "31 Stationen, Median -10 dB"


def test_stars_widget_clamping_low():
    """T2: score=0 → 1 Stern aktiv (clamping)."""
    w = _make_widget()
    w.set_score(0)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 1


def test_stars_widget_clamping_high():
    """T2: score=6 → 5 Sterne aktiv (clamping)."""
    w = _make_widget()
    w.set_score(6)
    actives = sum(1 for lbl in w._stars if "#00DDFF" in lbl.styleSheet())
    assert actives == 5
