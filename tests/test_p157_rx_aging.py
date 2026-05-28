"""P157 (28.05.2026) — RX-Liste Aging-Bug (drei Ursachen).

Mike-Field-Bug: In der Empfangsliste stehen "uralte" Stationen (bis ~17 Min),
man ruft eine Station an, die nicht mehr aktiv ist. Mike-Hypothese: "vielleicht
senden die noch CQ und wir aktualisieren nur die Uhrzeit nicht."

Drei diagnostizierte Ursachen:

- Bug 1: remove_stale() hat genau EINEN Aufrufer (accumulate_stations), und der
  laeuft nur bei vorhandenen Decodes. Wird das Band still (leere Slots), wird
  nie gealtert → tote Stationen kleben fest. Fix: zentraler Aging-Schritt in
  _on_cycle_decoded fuer leere Slots.
- Bug 2: _slot_start_ts (Quelle der UTC-Spalte + Zeit-Sortierung) wurde beim
  Wiederhoeren nicht aktualisiert → Anzeige zeigte Erst-Sichtung. Fix:
  _slot_start_ts in accumulate_stations beim Wiederhoeren mit-aktualisieren.
- Bug 3: _last_heard (Aging-relevant) wurde nur bei Inhalts-Aenderung gesetzt →
  eine aktiv sendende Station mit stabilem SNR + identischem Text altert raus.
  Fix: _last_heard beim Wiederhoeren IMMER setzen.

DeepSeek-R1 (V4-pro) hat die Diagnose bestaetigt + Bug 3 mitgefunden.
Umsetzung KISS (Variante b, kein API-Bruch, kein neuer Zustand).
"""

from __future__ import annotations

import time
from pathlib import Path

from core.station_accumulator import accumulate_stations, remove_stale
from core.message import parse_ft8_message


MW_CYCLE_SRC = (Path(__file__).resolve().parent.parent
                / "ui" / "mw_cycle.py").read_text()
RX_PANEL_SRC = (Path(__file__).resolve().parent.parent
                / "ui" / "rx_panel.py").read_text()


def _on_cycle_decoded_body() -> str:
    """Source-Slice von _on_cycle_decoded (bis zur naechsten Methode)."""
    pos = MW_CYCLE_SRC.find("def _on_cycle_decoded(self, messages: list):")
    assert pos > 0, "_on_cycle_decoded nicht gefunden"
    end = MW_CYCLE_SRC.find("\n    def ", pos + 1)
    return MW_CYCLE_SRC[pos:end if end > 0 else pos + 4000]


def _handler_body(name: str) -> str:
    import re
    m = re.search(rf"def {name}\(self,.*?(?=\n    def )", MW_CYCLE_SRC, re.S)
    assert m is not None, f"{name} nicht gefunden"
    return m.group(0)


# ── Bug 2: _slot_start_ts wird beim Wiederhoeren aktualisiert ────────────────

def test_bug2_slot_start_ts_updated_on_rehear():
    """Bug 2: Wiederhoeren einer bekannten Station aktualisiert _slot_start_ts.

    Vorher blieb es die Erst-Sichtung → UTC-Spalte (bevorzugt _slot_start_ts)
    zeigte alte Zeit obwohl die Station gerade aktiv ist.
    """
    stations: dict = {}
    m1 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    m1._slot_start_ts = 1000.0
    accumulate_stations(stations, [m1], set(), antenna="A1")
    assert stations["R3EDI"]._slot_start_ts == 1000.0

    # Wieder gehoert, neuer Slot (geaenderter SNR → changed-Pfad)
    m2 = parse_ft8_message("CQ R3EDI KO82", snr=-12, freq_hz=1000, dt=0.1)
    m2._slot_start_ts = 1015.0
    accumulate_stations(stations, [m2], set(), antenna="A1")
    assert stations["R3EDI"]._slot_start_ts == 1015.0, (
        "P157 Bug2: _slot_start_ts muss auf letzte Hoerzeit aktualisiert werden")


def test_bug2_slot_start_ts_updated_even_without_content_change():
    """Bug 2 (haerter): auch ohne Inhalts-/SNR-Aenderung wird _slot_start_ts
    aktualisiert — das Update steht VOR der change-Pruefung."""
    stations: dict = {}
    m1 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    m1._slot_start_ts = 1000.0
    accumulate_stations(stations, [m1], set(), antenna="A1")

    # Identischer Re-Decode (gleicher SNR + Text), nur neuer Slot
    m2 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    m2._slot_start_ts = 1015.0
    accumulate_stations(stations, [m2], set(), antenna="A1")
    assert stations["R3EDI"]._slot_start_ts == 1015.0, (
        "P157 Bug2: _slot_start_ts-Update muss vor der change-Pruefung stehen")


def test_slot_start_ts_none_defensive():
    """Defensive: msg ohne _slot_start_ts ueberschreibt existing._slot_start_ts
    NICHT mit None (Fallback-Fall)."""
    stations: dict = {}
    m1 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    m1._slot_start_ts = 1000.0
    accumulate_stations(stations, [m1], set(), antenna="A1")

    m2 = parse_ft8_message("CQ R3EDI KO82", snr=-12, freq_hz=1000, dt=0.1)
    # m2 hat KEIN _slot_start_ts (dynamisches Attribut, nicht gesetzt)
    accumulate_stations(stations, [m2], set(), antenna="A1")
    assert stations["R3EDI"]._slot_start_ts == 1000.0, (
        "P157: None-defensiv — alter Wert bleibt erhalten")


# ── Bug 3: aktive Station altert nicht faelschlich raus ──────────────────────

def test_bug3_identical_redecode_refreshes_last_heard():
    """Bug 3: identischer Re-Decode (gleicher SNR + Text) aktualisiert
    _last_heard, sodass eine aktiv sendende Station nicht rausaltert."""
    stations: dict = {}
    m1 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    accumulate_stations(stations, [m1], set(), antenna="A1")

    # Station fast abgelaufen (CQ-Limit 300s)
    stations["R3EDI"]._last_heard = time.time() - 290

    # Identischer Re-Decode — vorher kein _last_heard-Update (kein change)
    m2 = parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    accumulate_stations(stations, [m2], set(), antenna="A1")
    assert time.time() - stations["R3EDI"]._last_heard < 5, (
        "P157 Bug3: identischer Re-Decode muss _last_heard auffrischen")

    # Folge: remove_stale entfernt sie NICHT mehr
    removed = remove_stale(stations, set())
    assert "R3EDI" not in removed, (
        "P157 Bug3: aktive Station darf nach Re-Decode nicht rausaltern")


# ── Regression: messages-Slot altert weiterhin korrekt ───────────────────────

def test_regression_messages_slot_still_ages():
    """Regression: bei vorhandenen Decodes altert accumulate_stations
    weiterhin (remove_stale bleibt am Ende von accumulate_stations)."""
    stations: dict = {}
    m_old = parse_ft8_message("DA1MHH R3EDI -10", snr=-15, freq_hz=1000, dt=0.1)
    accumulate_stations(stations, [m_old], set())
    # alte Station kuenstlich altern (Nicht-CQ: 105s Limit bei FT8)
    stations["R3EDI"]._last_heard = time.time() - 110

    # Neuer Slot mit einer ANDEREN Station → accumulate ruft remove_stale
    m_new = parse_ft8_message("CQ DL9XYZ JO62", snr=-12, freq_hz=1100, dt=0.1)
    accumulate_stations(stations, [m_new], set(), slot_duration_s=15.0)
    assert "R3EDI" not in stations, (
        "Regression: alte Station muss bei messages-Slot weiterhin altern")
    assert "DL9XYZ" in stations


# ── Bug 1: zentraler Aging-Schritt fuer leere Slots (Source-Inspektion) ──────

def test_bug1_remove_stale_imported():
    """Bug 1: remove_stale wird in mw_cycle importiert."""
    assert ("from core.station_accumulator import accumulate_stations, "
            "remove_stale") in MW_CYCLE_SRC


def test_bug1_empty_slot_aging_block_exists():
    """Bug 1: _on_cycle_decoded ruft remove_stale fuer leere Slots."""
    body = _on_cycle_decoded_body()
    assert 'if not messages and self._rx_mode in ("diversity", "normal")' in body, (
        "P157 Bug1: Aging-Block fuer leere Slots fehlt")
    assert "remove_stale(" in body, "remove_stale-Aufruf fehlt im leeren-Slot-Block"
    assert "_rebuild_rx_table(" in body, "Tabellen-Rebuild fehlt im Aging-Block"
    assert "P157" in body, "P157-Doku-Marker fehlt"


def test_bug1_aging_block_after_mode_branch():
    """Bug 1: Aging-Block kommt NACH der Modus-Verzweigung (sonst altern
    frisch akkumulierte Stationen sofort raus)."""
    body = _on_cycle_decoded_body()
    pos_branch = body.find("self._handle_dx_tune_mode(messages)")
    pos_aging = body.find("if not messages and self._rx_mode in")
    assert pos_branch > 0 and pos_aging > 0
    assert pos_branch < pos_aging, (
        "P157: Aging-Block muss NACH der Handler-Verzweigung stehen")


# ── DRY-Helper _rebuild_rx_table ─────────────────────────────────────────────

def test_rebuild_helper_exists():
    """Helper _rebuild_rx_table existiert (DRY-Render-Pfad)."""
    assert "def _rebuild_rx_table(self, stations):" in MW_CYCLE_SRC


def test_both_handlers_use_rebuild_helper():
    """Beide dict-basierten Handler nutzen _rebuild_rx_table statt inline
    setRowCount-Loop."""
    for handler, dict_name in (
        ("_handle_diversity_operate", "self._diversity_stations"),
        ("_handle_normal_mode", "self._normal_stations"),
    ):
        body = _handler_body(handler)
        assert f"_rebuild_rx_table({dict_name})" in body, (
            f"P157: {handler} muss _rebuild_rx_table({dict_name}) nutzen")


def test_rebuild_helper_renders_from_dict():
    """Helper baut Tabelle aus dict.values() + reapply_sort."""
    body = _handler_body("_rebuild_rx_table")
    assert "setRowCount(0)" in body
    assert "stations.values()" in body
    assert "reapply_sort()" in body


# ── rx_panel-Kommentar dokumentiert das neue Verhalten ───────────────────────

def test_rx_panel_comment_updated():
    """rx_panel.py Kommentar erwaehnt P157 + 'zuletzt gehoert'."""
    assert "P157" in RX_PANEL_SRC
    assert "zuletzt" in RX_PANEL_SRC.lower()
