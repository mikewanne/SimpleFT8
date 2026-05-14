# Bundle E — TX-Slot-Lock (Refactor von Bundle-D RX-Filter)

**Datum:** 2026-05-14 morgens (nach Bundle-D Mike-Korrektur)
**Status:** V1
**Trigger:** Mike: „ich hatte mich falsch ausgedrückt — ich will nicht
Stationen filtern, sondern TX-Slot festlegen (SmartSDR-Style)".

---

## 1. Ziel

User klickt EVEN-Button → SimpleFT8 sendet NUR in Even-Slots, hört
im Odd-Slot. Andersrum für Odd. Lock-Status persistiert in Settings,
gilt nur im Normal-Modus, in Diversity ausgeblendet (wie Bundle-D
schon implementiert).

**Was Bundle-D bleibt:**
- Settings-Block-Padding (A) ✓
- DT-Vorzeichen-Entfernung (B) ✓
- Buttons-UI im QSO-Panel (C) ✓ (Signal/Logik bleibt fast gleich)
- Diversity-Mode Verstecken/Reset (D) ✓
- Slot-Progress-Bar Statusbar (E) ✓

**Was geändert wird:**
- RX-Filter-Logik in `rx_panel.py` (`_slot_filter` + `apply_slot_filter`
  + `_row_should_hide`-Erweiterung) → **zurück**
- Stattdessen: TX-Slot-Lock in `encoder.tx_even` einhängen
- Settings-Persistierung `tx_slot_lock` ∈ {"none", "even", "odd"}

---

## 2. R1-Recherche eingearbeitet

**4 TX-Pfade setzen `encoder.tx_even`:**

| Pfad | Datei:Zeile | Setter | Lock-Anwendung |
|------|-------------|--------|----------------|
| Normal CQ | `core/qso_state.py:184-186` | `tx_even = None` | bei Lock!="none" → `tx_even = (lock=="even")` |
| Hunt-Klick | `ui/mw_qso.py:200-205` | `tx_even = not their_even` | wenn != lock → block + Hinweis |
| CQ-Reply | `ui/mw_qso.py:70-74` | wie Hunt | wie Hunt |
| OMNI | `core/omni_cq.py:79+216` | `_cq_tx_even = is_even` | OMNI ist Diversity-only → Lock entfällt (Normal-only) |

**Hunt-Mismatch:** wenn User Station klickt deren Slot mit Lock kollidiert →
Klick wird ignoriert + Tooltip-Hinweis im QSO-Panel.

---

## 3. ACs (V1)

- **AC1** Settings-Key `tx_slot_lock` ∈ {"none", "even", "odd"},
  Default `"none"`, in `config/settings.py` mit Helper `get_tx_slot_lock`
  + `set_tx_slot_lock` (defensive).
- **AC2** QSOPanel Buttons emittet jetzt `tx_slot_lock_changed(str)`
  (statt `slot_filter_changed`). Werte siehe AC1.
- **AC3** Persistiert via Signal-Hook in `main_window` →
  `settings.set_tx_slot_lock(lock) + save()`.
- **AC4** Bei App-Start Normal-Modus: Settings-Wert geladen, Buttons
  entsprechend gecheckt.
- **AC5** Bei Diversity-Modus: Buttons ausgeblendet (Bundle-D AC11 bleibt).
  Lock-State bleibt aber im Settings (nur UI versteckt).
- **AC6** Bei Modus-Wechsel zurück auf Normal: Lock aus Settings
  wiederhergestellt, Buttons gecheckt.
- **AC7** Normal-CQ-Pfad (`_send_cq`): wenn Lock!="none", setze
  `encoder.tx_even = (lock=="even")` statt `None`.
- **AC8** Hunt-Pfad (`_on_station_clicked`): vor `start_qso()` validieren
  ob Gegentakt-zur-Station mit Lock kompatibel. Bei Mismatch: Klick
  wird ignoriert + Hinweis im QSO-Panel `add_info` Methode.
- **AC9** CQ-Reply (`_on_tx_slot_for_partner`): analog AC8.
- **AC10** OMNI-CQ: nicht betroffen (Diversity-only, Lock-UI entfällt).
- **AC11** Auto-Hunt (`core/auto_hunt.py`): geht über Hunt-Pfad →
  Mismatch-Stationen werden via AC8-Validation gefiltert. R1-Frage:
  soll Auto-Hunt im Lock-Modus inkompatible Stationen überspringen?
- **AC12** RX-Panel Filter-Logik **komplett zurückgebaut**:
  - `_slot_filter` State raus
  - `apply_slot_filter` Methode raus
  - `_row_should_hide` Slot-Check raus
- **AC13** `main_window._connect_signals` Connect-Line ändern:
  vorher `qso_panel.slot_filter_changed → rx_panel.apply_slot_filter`,
  jetzt `qso_panel.tx_slot_lock_changed → _on_tx_slot_lock_changed`
  (Settings save + state update).
- **AC14** Slot-Progress-Bar in Statusbar bleibt unverändert.

---

## 4. R1-Fragen (Q1-Q5)

- **Q1** Hunt-Mismatch: Klick ignorieren mit Tooltip ODER Klick
  überschreibt Lock temporär (für dieses QSO)? V1-Vorschlag: ignorieren
  (sicher, Mike kann Lock manuell abschalten wenn er wechseln will).
- **Q2** Auto-Hunt bei Lock: überspringen oder gleich verhalten wie
  Hunt (Klick wird ignoriert)? V1-Vorschlag: select_next() prüft Slot,
  überspringt Mismatch.
- **Q3** Bei App-Start mit Lock="even": Was wenn Slot-Lock und
  current_band+mode haben gespeicherten `_was_cq=True` Status? KISS:
  Lock gilt immer, Restart-State irrelevant.
- **Q4** Visueller Hinweis: Wenn Lock aktiv, soll im Slot-Progress-Bar
  oder anderswo ein Indikator zeigen dass Lock aktiv? V1-Vorschlag:
  Tooltip auf den Lock-Buttons genügt.
- **Q5** Edge-Case OMNI-CQ Start mit Normal-Modus-Lock: OMNI ist
  Diversity-only — wenn User in Normal-Modus klickt OMNI → bricht ab
  (heute schon) → Lock irrelevant. Bestätigen.

---

## 5. Tests (T1-T9)

- T1 Settings get_tx_slot_lock Default "none"
- T2 Settings set_tx_slot_lock defensive Filter (nur "none"/"even"/"odd")
- T3 QSOPanel Signal `tx_slot_lock_changed` Emission
- T4 Normal-CQ-Pfad mit Lock="even" → encoder.tx_even = True
- T5 Hunt mit Lock="even", their_even=False → Klick erlaubt (Gegentakt=True passt)
- T6 Hunt mit Lock="even", their_even=True → Klick BLOCKED
- T7 Mode-Wechsel: Lock-Settings überleben, UI aktualisiert sich
- T8 RXPanel Filter-Logik vollständig zurückgebaut (apply_slot_filter
  existiert nicht mehr)
- T9 Bundle-D Tests T6-T8 entfernen/ersetzen

---

## 6. Atomare Commits

| # | Commit | Files | LOC |
|---|--------|-------|-----|
| C1 | Rollback Filter-Code in rx_panel | `ui/rx_panel.py` (revert C3) | -50 |
| C2 | Settings tx_slot_lock API | `config/settings.py` | +30 |
| C3 | QSOPanel Signal-Rename + Persist | `ui/qso_panel.py`, `ui/main_window.py` | ~40 |
| C4 | Normal-CQ Lock-Anwendung | `core/qso_state.py`/`ui/mw_qso.py` | ~15 |
| C5 | Hunt-Validierung + Hinweis | `ui/mw_qso.py` | ~30 |
| C6 | Tests Bundle E | `tests/test_bundle_e.py` NEU + Bundle-D-Tests anpassen | +200 / -80 |
| C7 | APP_VERSION 0.97.22 + Doku | main.py + HISTORY/HANDOFF/CLAUDE/TODO/Memory | — |

---

## 7. Field-Test (für Mike)

- F1 Normal-Modus: EVEN klicken → grün, ODD aus.
- F2 CQ rufen → TX feuert nur in Even-Slots.
- F3 Station Y klicken, Y sendet in Even (their_tx_even=True) → Klick
  ignoriert + Hinweis im QSO-Panel.
- F4 Station Y klicken, Y sendet in Odd → QSO startet normal, TX in Even.
- F5 ODD klicken → wechselt, EVEN aus.
- F6 Beide aus klicken → Lock=„none", TX in beliebigem Slot.
- F7 App neu starten → letzter Lock-State wiederhergestellt.
- F8 Modus → Diversity: Buttons weg, Lock weiter persistiert in Settings.
- F9 Modus zurück Normal: Lock wieder UI-aktiv.
