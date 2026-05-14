# Bundle E — V2 Self-Review

V1: `prompts/bundle_e_v1.md`. Selfcheck VOR R1.

---

## A. Was V1 richtig macht

- Trennung Bundle-D (A/B/D/E bleibt) vs. C (Refactor) klar
- 4 TX-Pfade aus R1-Recherche eingearbeitet
- AC1-AC14 spezifisch
- Hunt-Mismatch-Verhalten thematisiert (V1-Q1)

---

## B. Übersehene Probleme / Risiken

### B1 — `_send_cq()` setzt `encoder.tx_even = None` heute

Wenn ich AC7 implementiere („Lock!=none → `tx_even = (lock=='even')`")
muss ich an genau der Stelle einsetzen wo `tx_even=None` heute steht.
Aber: was passiert wenn `_send_cq` während eines bereits laufenden
QSO gerufen wird (z.B. retry)? Lock muss gleich bleiben — also nicht
nur in `_send_cq` sondern überall wo CQ-Pfad TX-Slot setzt.

→ R1 fragen: zentraler Setter-Wrapper sinnvoll? `set_tx_even_with_lock()`
Helper auf Encoder?

### B2 — `_on_station_clicked` und `_on_tx_slot_for_partner` haben
identische Logik

Beide Pfade setzen `encoder.tx_even = not their_even`. Lock-Check
muss in beiden. Duplikat-Risiko: wenn ich nur eines patche, der
andere bleibt durch.

→ Helper-Funktion `_apply_tx_slot_with_lock(their_even) -> Optional[bool]`
in `RadioMixin` oder `QSOMixin`. Wenn returnt `None` → mismatch
gemerkt → Caller blocked.

### B3 — Was bedeutet `tx_even = None` bei Encoder?

Aus R1-Recherche: „None = nächster beliebiger Slot". Heißt: wenn Lock
„none" aktiv, behält der Standard-Pfad `None` ohne Lock. OK.

Aber: wenn Lock=„even" und ich rufe CQ → `tx_even = True`. Wenn dann
mid-CQ User Lock auf „none" zurücksetzt → was passiert mit dem
laufenden Encoder? Es ist evtl. schon im Even-Slot fixiert.

→ R1 fragen: Lock-Wechsel mid-CQ — wirkt sofort oder erst beim
nächsten TX-Trigger? KISS: erst beim nächsten.

### B4 — RX-Filter-Rollback nicht vollständig?

Bundle-D-Code in `ui/rx_panel.py`:
- `_slot_filter: str = "both"` (Z.~80) raus
- `apply_slot_filter(filter)` Methode raus
- `_row_should_hide` Slot-Check raus
- DT-Helper `_format_dt` BLEIBT (Bundle-D-B)

Plus in `ui/main_window.py`:
- `qso_panel.slot_filter_changed.connect(rx_panel.apply_slot_filter)`
  → ändern zu `qso_panel.tx_slot_lock_changed.connect(self._on_tx_slot_lock_changed)`

Plus `ui/mw_radio.py`:
- `qso_panel.reset_slot_filter()` → `qso_panel.reset_tx_slot_lock()` ?
  ODER reset-Logik ist nicht mehr nötig weil Lock persistiert?

→ V2 Klärung: Bei Diversity-Wechsel KEIN Reset des Lock-State, nur
Buttons visuell ausblenden. Bei Rückkehr zu Normal → State aus
Settings wiederhergestellt. AC5/AC6 V1 stimmen, aber `mw_radio` Code
muss anders aussehen (kein reset_slot_filter mehr).

### B5 — OMNI-CQ + Lock-State

OMNI-CQ ist Diversity-only (heute schon). UI-Buttons-Container ist
in Diversity ausgeblendet. ABER: in Settings könnte Lock="even" stehen
(weil User in Normal-Modus gesetzt + dann Modus gewechselt).

OMNI hat eigenen `_cq_tx_even` der nichts vom Lock weiß. OK weil
OMNI nur in Diversity läuft.

→ Klar dass OMNI vom Lock unberührt ist. Bestätigen via R1.

### B6 — Auto-Hunt

Auto-Hunt wählt Stationen aus dem Hunt-Pool. Wenn Lock aktiv:
- Variante A: `select_next` filtert Stations mit kompatiblem Slot
- Variante B: select_next ignoriert Lock, Klick wird dann gleich
  blockiert wie manueller Klick (AC8)

Variante B ist KISS aber führt zu „Auto-Hunt-Klick wird blocked" →
Auto-Hunt versucht es wieder → blocked → Loop?

Variante A ist sauberer: Lock-bewusste Selection.

→ R1 entscheiden.

### B7 — Tests-Strategie

Bundle-D-Tests T6/T7 (RXPanel apply_slot_filter) und T8 (QSOPanel
slot_filter_changed) müssen angepasst werden auf neuen Signal-Namen
+ neuer Semantik. T9 (visibility) + T10 (reset) bleiben gültig
(nur Methoden-Namen ändern). T11 (Slot-Progress-Bar) bleibt.

Neue Tests:
- Settings get/set_tx_slot_lock defensive
- Normal-CQ-Pfad mit Lock: encoder.tx_even gesetzt
- Hunt mit Lock-Mismatch: blocked + add_info getriggert

### B8 — Was wenn User Lock="even" hat und der Encoder gerade Mid-
TX in Odd-Slot ist?

Bei manueller Lock-Änderung mid-TX:
- Aktuelle TX läuft durch (kann nicht abgebrochen werden mid-TX)
- Nächster Slot wird gemäß neuem Lock-State gewählt

→ KISS, Tests T13 (mid-TX-Wechsel): encoder.is_transmitting=True →
Lock-Toggle hat keine sofortige Wirkung, erst beim nächsten Slot.
Niedrig-Prio.

### B9 — UI-Feedback bei aktivem Lock

V1 sagte: kein extra Indikator (Q4). Aber: wenn User Lock=„even"
hat und ne Station im Even-Slot klickt und der Klick wird stumm
ignoriert — er weiß nicht warum.

Verbesserung: `add_info("Klick ignoriert: Station Y sendet im
Even-Slot, mit aktivem Even-Lock kann nicht in Odd geantwortet
werden")`. Konkret + verständlich.

### B10 — Persistierung: Save bei jedem Klick?

V1-AC3: persistiert via `set_tx_slot_lock(lock) + save()` bei jedem
Signal-Emit. Bei wechselndem Klicken sind das 2-3 Saves. settings.save
ist atomar (tempfile+replace) → sicher. Aber langsam? Nein, ist
schnell. OK.

---

## C. Korrigierte Architektur (V2 final)

```
config/settings.py
  + DEFAULT "tx_slot_lock": "none"
  + get_tx_slot_lock() -> str
  + set_tx_slot_lock(str) defensiv

ui/qso_panel.py
  - slot_filter_changed Signal raus
  + tx_slot_lock_changed = Signal(str)  # "none"|"even"|"odd"
  - reset_slot_filter() raus
  + set_tx_slot_lock_buttons(lock) → Buttons aus Settings laden
  Klick-Logik in _on_slot_btn_clicked emittet jetzt
    tx_slot_lock_changed("even"|"odd"|"none")

ui/rx_panel.py
  - _slot_filter State raus
  - apply_slot_filter() raus
  - _row_should_hide Slot-Check raus
  + _format_dt bleibt (Bundle-D-B)

ui/main_window.py
  In _connect_signals:
    - rx_panel.apply_slot_filter Connect raus
    + qso_panel.tx_slot_lock_changed.connect(self._on_tx_slot_lock_changed)
  + _on_tx_slot_lock_changed(lock):
    + self.settings.set_tx_slot_lock(lock) + save()
  Bei App-Start nach _setup_ui:
    + self.qso_panel.set_tx_slot_lock_buttons(self.settings.get_tx_slot_lock())

ui/mw_radio.py
  In _on_rx_mode_changed:
    - qso_panel.reset_slot_filter() raus
    + bei mode=normal: qso_panel.set_tx_slot_lock_buttons(
        self.settings.get_tx_slot_lock())
    Visibility bleibt: set_slot_buttons_visible(mode == "normal")

ui/mw_qso.py / core/qso_state.py (Helper)
  + _resolve_tx_slot(their_even: Optional[bool]) -> Optional[bool]
    """Berechnet encoder.tx_even unter Berücksichtigung des Lock-Status.

    their_even: None=CQ-Pfad, True/False=Hunt-Pfad (their_even).
    Returns: True/False für tx_even ODER None wenn Lock kollidiert
    (Caller muss QSO blockieren).
    """
    lock = settings.get_tx_slot_lock()
    if lock == "none":
        return None if their_even is None else not their_even
    target = (lock == "even")
    if their_even is None:
        return target  # CQ-Pfad: TX in Lock-Slot
    # Hunt: prüfen ob Lock erlaubt
    desired = not their_even  # wir antworten Gegentakt
    if desired != target:
        return None  # Mismatch — Klick blockieren
    return target

  In _on_station_clicked (Hunt):
    Vor encoder.tx_even setzen:
      slot = _resolve_tx_slot(their_even)
      if slot is None:
        qso_panel.add_info("Klick ignoriert: Slot-Lock=...")
        return
      encoder.tx_even = slot

  In _send_cq:
    encoder.tx_even = _resolve_tx_slot(None)
    # None wenn Lock="none", True/False wenn Lock aktiv

  In _on_tx_slot_for_partner (CQ-Reply):
    Wie Hunt.

core/auto_hunt.py
  In select_next:
    + filter Stationen nach Lock-Kompatibilität wenn Lock aktiv
    (R1-Q2 Variante A)
```

---

## D. Offene Fragen für R1 (Q1-Q7)

- **Q1 (V1) Hunt-Mismatch:** Klick ignorieren + add_info. V2-Vorschlag:
  Variante A. R1 OK?
- **Q2 (V1) Auto-Hunt bei Lock:** select_next filtert. V2 Variante A.
  R1 bestätigen.
- **Q3 (V1) Restart-State:** unverändert. R1 OK.
- **Q4 (V1) Visueller Indikator:** Tooltip auf Buttons reicht.
- **Q5 (V1) OMNI:** Diversity-only, Lock entfällt. R1 OK.
- **Q6 NEU (V2 B1+B2):** Zentraler Helper `_resolve_tx_slot(their_even)`
  in QSOMixin oder QSOState. R1: wo gehört der hin?
- **Q7 NEU (V2 B8)** Mid-TX-Lock-Wechsel: erste Implementation lässt
  laufenden TX durch, nächster Slot ist Lock. R1 OK?

---

## E. Tests V2 (T1-T11)

- T1 Settings get_tx_slot_lock Default
- T2 Settings set defensiv
- T3 QSOPanel Signal Emission
- T4 _resolve_tx_slot Helper für 6 Kombinationen (Lock × their_even)
- T5 Hunt-Klick mit Lock-Mismatch: blocked + add_info aufgerufen
- T6 Normal-CQ mit Lock: encoder.tx_even gesetzt
- T7 RXPanel apply_slot_filter existiert NICHT mehr (Rollback-Check)
- T8 QSOPanel slot_filter_changed Signal existiert NICHT mehr
- T9 Mode-Wechsel: Lock-State über Settings persistiert
- T10 Auto-Hunt: select_next filtert bei Lock
- T11 Settings save bei Lock-Change (mock + assert called)
