"""P1.19/P1.21: StarsConditionWidget Render-Tests (RichText-API)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_widget():
    _ensure_app()
    from ui.widgets.stars_widget import StarsConditionWidget
    return StarsConditionWidget()


def _count_active_stars(text: str) -> int:
    """Zaehlt aktive (Gold #FFD700) Sterne im RichText."""
    # active span: <span style="color:#FFD700;">★★★</span>
    if "#FFD700" not in text:
        return 0
    after = text.split("#FFD700")[1]
    inner = after.split(">", 1)[1].split("</span>", 1)[0]
    return inner.count("★")


def test_stars_widget_set_score_renders():
    w = _make_widget()
    w.set_score(3)
    assert _count_active_stars(w.text()) == 3


def test_stars_widget_5_stars():
    w = _make_widget()
    w.set_score(5)
    assert _count_active_stars(w.text()) == 5
    assert w.text().count("★") == 5  # nur 5 aktive, 0 inaktive


def test_stars_widget_1_star():
    w = _make_widget()
    w.set_score(1)
    assert _count_active_stars(w.text()) == 1
    assert w.text().count("★") == 5  # 1 aktiv + 4 inaktiv


def test_stars_widget_tooltip():
    w = _make_widget()
    w.set_score(5, "31 Stationen, Median -10 dB")
    assert w.toolTip() == "31 Stationen, Median -10 dB"


def test_stars_widget_clamping_low():
    """T2: score=0 → 1 Stern aktiv (clamping)."""
    w = _make_widget()
    w.set_score(0)
    assert _count_active_stars(w.text()) == 1


def test_stars_widget_clamping_high():
    """T2: score=6 → 5 Sterne aktiv (clamping)."""
    w = _make_widget()
    w.set_score(6)
    assert _count_active_stars(w.text()) == 5


def test_stars_widget_uses_gold_not_cyan():
    """P1.21 Mike-Frust: Farbe muss Gold #FFD700 sein, nicht Cyan #00DDFF."""
    w = _make_widget()
    w.set_score(3)
    assert "#FFD700" in w.text()
    assert "#00DDFF" not in w.text()
