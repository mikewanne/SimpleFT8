"""P161: Toggle-Sortierung im RX-Header (Wechselschalter).

Klick auf einen Spaltenkopf sortiert; erneuter Klick auf dieselbe Spalte kippt
die Richtung (▾ absteigend / ▴ aufsteigend). Neue Spalte → Default-Richtung.
Stationen ohne bekannte Entfernung ("-" km) bleiben immer unten (Sentinel nur
für dist, DeepSeek-R1 F2).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from core.message import FT8Message

from ui.rx_panel import (
    RXPanel, COL_UTC, COL_DB, COL_LAND, COL_KM, _DEFAULT_REVERSE,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _mk(caller="DL1ABC", snr=-10, utc="120000"):
    """CQ-Message von `caller`. field1=CQ → caller-Property = field2."""
    m = FT8Message(
        raw=f"CQ {caller} JO31", field1="CQ", field2=caller, field3="JO31",
        snr=snr, freq_hz=1000, dt=0.0,
    )
    m._utc_display = utc
    m._slot_start_ts = float(utc)  # HHMMSS als Float-Pseudo-Timestamp
    return m


def _make_panel(qapp):
    return RXPanel(my_call="DA1MHH", my_grid="JO31")


def _add(p, msg):
    p.add_message(msg)


def _callers(p):
    """Caller-Reihenfolge der sichtbaren Tabelle (oben → unten)."""
    out = []
    for r in range(p.table.rowCount()):
        it = p.table.item(r, COL_UTC)
        if it is None:
            continue
        m = it.data(Qt.ItemDataRole.UserRole)
        if m is not None:
            out.append(m.caller)
    return out


def _set_dist(p, dists: dict):
    """dist_km pro Caller setzen (geo-Lookup liefert für Test-Calls 0)."""
    for r in range(p.table.rowCount()):
        it = p.table.item(r, COL_UTC)
        m = it.data(Qt.ItemDataRole.UserRole)
        if m and m.caller in dists:
            it.setData(Qt.ItemDataRole.UserRole + 2, dists[m.caller])


# ── Richtung / Toggle ────────────────────────────────────────────────

def test_toggle_flips_reverse(qapp):
    p = _make_panel(qapp)
    p._on_header_clicked(COL_DB)
    assert p._sort_reverse is True        # snr Default = absteigend
    p._on_header_clicked(COL_DB)
    assert p._sort_reverse is False       # gleiche Spalte → gekippt
    p._on_header_clicked(COL_DB)
    assert p._sort_reverse is True        # nochmal → wieder absteigend


def test_first_click_uses_default_reverse(qapp):
    # snr/dist/country sind beim Start NICHT aktiv (Default-Modus ist "time")
    # → erster Klick setzt deren Default-Richtung.
    for col, mode in [(COL_DB, "snr"), (COL_KM, "dist"), (COL_LAND, "country")]:
        p = _make_panel(qapp)
        p._on_header_clicked(col)
        assert p._sort_reverse == _DEFAULT_REVERSE[mode], mode


def test_utc_first_click_is_toggle_since_default_active(qapp):
    # UTC ist beim Start schon der aktive Modus ("time", rev=True). Ein Klick
    # darauf ist daher ein Toggle (älteste oben), KEIN Default-Set.
    p = _make_panel(qapp)
    assert p._sort_mode == "time" and p._sort_reverse is True
    p._on_header_clicked(COL_UTC)
    assert p._sort_reverse is False        # gekippt
    p._on_header_clicked(COL_UTC)
    assert p._sort_reverse is True         # wieder neueste oben


def test_new_column_resets_to_default(qapp):
    p = _make_panel(qapp)
    p._on_header_clicked(COL_DB)    # snr, rev=True
    p._on_header_clicked(COL_DB)    # rev=False
    p._on_header_clicked(COL_LAND)  # neue Spalte → country Default rev=False
    assert p._sort_mode == "country"
    assert p._sort_reverse is False
    p._on_header_clicked(COL_UTC)   # neue Spalte → time Default rev=True
    assert p._sort_reverse is True


# ── tatsächliche Sortier-Reihenfolge ─────────────────────────────────

def test_snr_ascending_and_descending(qapp):
    p = _make_panel(qapp)
    for c, s, u in [("AA", -10, "120000"), ("BB", -5, "120100"), ("CC", -20, "120200")]:
        _add(p, _mk(c, s, u))
    p._on_header_clicked(COL_DB)   # rev=True: höchste oben → BB(-5),AA(-10),CC(-20)
    assert _callers(p) == ["BB", "AA", "CC"]
    p._on_header_clicked(COL_DB)   # rev=False: niedrigste oben → CC,AA,BB
    assert _callers(p) == ["CC", "AA", "BB"]


def test_dist_unknown_stays_bottom_ascending(qapp):
    p = _make_panel(qapp)
    for c, s, u in [("AA", -10, "120000"), ("BB", -5, "120100"), ("CC", -20, "120200")]:
        _add(p, _mk(c, s, u))
    _set_dist(p, {"AA": 1000, "BB": 0, "CC": 500})
    p._sort_mode = "dist"
    p._sort_reverse = False          # aufsteigend (nächste oben)
    p._set_sort("dist")
    # CC(500), AA(1000), dann BB(unbekannt=0) ganz unten
    assert _callers(p) == ["CC", "AA", "BB"]


def test_dist_descending_unknown_still_bottom(qapp):
    p = _make_panel(qapp)
    for c, s, u in [("AA", -10, "120000"), ("BB", -5, "120100"), ("CC", -20, "120200")]:
        _add(p, _mk(c, s, u))
    _set_dist(p, {"AA": 1000, "BB": 0, "CC": 500})
    p._sort_mode = "dist"
    p._sort_reverse = True           # absteigend (fernste oben)
    p._set_sort("dist")
    # AA(1000), CC(500), BB(0=unbekannt) unten
    assert _callers(p) == ["AA", "CC", "BB"]


# ── Stabilität über Cycle-Rebuilds ───────────────────────────────────

def test_reapply_keeps_direction(qapp):
    p = _make_panel(qapp)
    for c, s, u in [("AA", -10, "120000"), ("BB", -5, "120100")]:
        _add(p, _mk(c, s, u))
    p._on_header_clicked(COL_DB)   # rev=True
    p._on_header_clicked(COL_DB)   # rev=False
    assert p._sort_reverse is False
    p.reapply_sort()               # läuft pro Cycle — darf Richtung NICHT resetten
    assert p._sort_reverse is False
    assert p._sort_mode == "snr"


# ── Header-Pfeil ─────────────────────────────────────────────────────

def test_header_arrow_reflects_direction(qapp):
    p = _make_panel(qapp)
    p._on_header_clicked(COL_DB)   # rev=True → ↓
    assert "↓" in p.table.horizontalHeaderItem(COL_DB).text()
    p._on_header_clicked(COL_DB)   # rev=False → ↑
    assert "↑" in p.table.horizontalHeaderItem(COL_DB).text()
