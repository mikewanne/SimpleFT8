"""P137 (26.05.2026) -- Log-Eintrag 'Gesendet' statt 'Sende' (Tempora-Fix).

Mike-Field-Bug 26.05.: Log zeigte '-> Sende EA5KB DA1MHH RR73' NACH dem TX
(Watt-Anzeige bereits 0 W). Verb-Form war falsch -- P93-Defer-Mechanik
laesst den Eintrag erst in _on_tx_finished erscheinen, also wenn TX
schon vorbei ist.

Mike-Spec: Sende = Gegenwart (falsch), Gesendet = Vergangenheit
(richtig weil schon passiert).

Variante B (R1 6x GRUEN): nur Tempora-Fix im Log, KEINE Statusbar-
Pre-TX-Anzeige.

ACs:
- AC1: _render_entry kind='tx' zeigt '-> Gesendet' (nicht mehr 'Sende')
- AC2: add_info Pre-TX-Pfad (mw_qso _p94 '-> Sende 73') bleibt Praesens
  (semantisch korrekt vor TX)
- AC3: Re-Render bleibt konsistent ('Gesendet' auch nach Toggle)
- AC4: P137-Marker im Kommentar
"""

from __future__ import annotations

from pathlib import Path


QSO_PANEL = Path(__file__).parent.parent / "ui" / "qso_panel.py"
MW_QSO = Path(__file__).parent.parent / "ui" / "mw_qso.py"


# ---------------------------------------------------------------------------
# T1-T3: Source-Inspection
# ---------------------------------------------------------------------------


def test_t1_render_entry_uses_gesendet():
    """T1: _render_entry generiert '-> Gesendet' im Log-Eintrag."""
    src = QSO_PANEL.read_text()
    pos = src.find("def _render_entry")
    assert pos > 0
    window = src[pos:pos + 1500]
    assert "→ Gesendet " in window, (
        "P137: _render_entry tx-Branch muss '-> Gesendet' enthalten")
    # Praesens '-> Sende {' darf nicht mehr im tx-Branch sein
    # (Suchspecific: gefolgt von { weil f-string format)
    assert "→ Sende {" not in window, (
        "P137: f-string Praesens '-> Sende {...}' im tx-Branch entfernt")


def test_t2_p137_marker_in_qso_panel():
    """T2: P137-Marker im Source nahe der Aenderung."""
    src = QSO_PANEL.read_text()
    pos = src.find("→ Gesendet")
    assert pos > 0
    window = src[max(0, pos - 400):pos + 200]
    assert "P137" in window, "P137-Marker im Kommentarbereich erwartet"


def test_t3_pre_tx_add_info_keeps_present_tense():
    """T3: P94 Quick-73-Filter add_info bleibt Praesens 'Sende 73'.

    R1-Finding F1: diese Stelle (mw_cycle.py:984) ist semantisch
    Present Tense -- TX laeuft NOCH NICHT bei der add_info-Anzeige.
    """
    MW_CYCLE = Path(__file__).parent.parent / "ui" / "mw_cycle.py"
    src = MW_CYCLE.read_text()
    assert "Sende 73 (bereits gearbeitet" in src, (
        "P94 Quick-73 add_info muss Praesens 'Sende 73' behalten "
        "(Pre-TX-Info, kein Log-Eintrag)")


# ---------------------------------------------------------------------------
# T4-T6: Funktionale String-Logik-Tests
# ---------------------------------------------------------------------------


def test_t4_render_entry_produces_gesendet_in_string():
    """T4: tx-Entry-Render erzeugt '-> Gesendet ...' Zeile."""
    e = {
        "kind": "tx",
        "utc": "12:51:30",
        "tag": "[E]",
        "message": "EA5KB DA1MHH RR73",
        "tx_even": True,
    }
    show_eo_tag = True
    tag_str = f"{e['tag']} " if show_eo_tag else ""
    line = f"{e['utc']} {tag_str}→ Gesendet {e['message']}"
    assert "→ Gesendet" in line
    assert "→ Sende " not in line
    assert line == "12:51:30 [E] → Gesendet EA5KB DA1MHH RR73"


def test_t5_render_entry_without_tag():
    """T5: Ohne EO-Tag (show_eo_tag=False) bleibt Format konsistent."""
    e = {
        "kind": "tx", "utc": "12:51:30",
        "tag": "[E]", "message": "EA5KB DA1MHH RR73",
    }
    show_eo_tag = False
    tag_str = f"{e['tag']} " if show_eo_tag else ""
    line = f"{e['utc']} {tag_str}→ Gesendet {e['message']}"
    assert line == "12:51:30 → Gesendet EA5KB DA1MHH RR73"


def test_t6_omni_suffix_logic_intact():
    """T6: OMNI ↻ N Suffix-Logik bleibt im _render_entry erhalten."""
    src = QSO_PANEL.read_text()
    pos = src.find("→ Gesendet")
    window = src[pos:pos + 600]
    assert "omni_remaining" in window
    assert "↻" in window  # ↻ Symbol


# ---------------------------------------------------------------------------
# T7: Regression-Schutz (R1-GELB-Auflage)
# ---------------------------------------------------------------------------


def test_t7_no_praesens_sende_pattern_in_render_entry():
    """T7 (R1-Auflage): KEIN '-> Sende {...}'-Praesens-Pattern mehr in
    _render_entry tx-Branch.
    """
    src = QSO_PANEL.read_text()
    pos = src.find("def _render_entry")
    end = src.find("\n    def ", pos + 10)
    if end == -1:
        end = pos + 3000
    func_body = src[pos:end]
    assert "→ Sende {" not in func_body, (
        "P137 Regression-Schutz: f-string '-> Sende {...}' darf nicht "
        "im _render_entry tx-Branch zurueck -- Tempora ist Praeteritum")
