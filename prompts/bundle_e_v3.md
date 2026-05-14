# Bundle E — V3 (Compact-fest, finale Marschrute)

**Datum:** 2026-05-14 morgens
**Status:** V3 final — geht in Code
**Pre:** V1+V2+R1 in `prompts/bundle_e_*.md`

---

## 1. Ziel

Refactor Bundle-D-Filter zu **TX-Slot-Lock** (Mike-Korrektur SmartSDR-
Style). User klickt EVEN → TX nur in Even-Slot. Persistiert in Settings.
Lock greift NUR im Normal-Modus (in Diversity Buttons unsichtbar, Lock-
Wirkung deaktiviert).

**Version:** 0.97.21 → 0.97.22

---

## 2. R1-verbindliche Entscheidungen

| Q | Entscheidung |
|---|---|
| Q1 Hunt-Mismatch | Ignorieren + `add_info` Hinweis |
| Q2 Auto-Hunt | `select_next` filtert + 1-Zyklus-Pause bei leerem Pool |
| Q3 Restart | Lock-State unverändert |
| Q4 UI-Indikator | Tooltip auf Buttons reicht (KISS) |
| Q5 OMNI | Diversity-only, Lock entfällt |
| Q6 Helper-Ort | `core/qso_state.py` (alle Pfade greifen drauf zu) |
| Q7 Mid-TX | Läuft durch, nächster Slot folgt Lock |

---

## 3. 16 ACs (final)

### Rollback Bundle-D Filter-Code
- **AC1** `ui/rx_panel.py`: `_slot_filter` State **entfernen**.
- **AC2** `ui/rx_panel.py`: `apply_slot_filter()` Methode **entfernen**.
- **AC3** `ui/rx_panel.py`: `_row_should_hide` Slot-Check **entfernen**.
- **AC4** `ui/main_window.py`: Connect `qso_panel.slot_filter_changed →
  rx_panel.apply_slot_filter` durch neuen Lock-Connect ersetzen.

### Settings-API
- **AC5** Neuer Key `tx_slot_lock` ∈ {"none", "even", "odd"}, Default
  `"none"`, in `config/settings.py`. Helper `get_tx_slot_lock()` +
  `set_tx_slot_lock(lock)` mit defensivem Filter.

### QSO-Panel Signal-Refactor
- **AC6** Signal `slot_filter_changed` → `tx_slot_lock_changed`
  (Namen ändern, Werte gleich: "none"/"even"/"odd").
- **AC7** `_on_slot_btn_clicked` emittet jetzt `tx_slot_lock_changed`.
- **AC8** Neue Methode `set_tx_slot_lock_buttons(lock: str)` — setzt
  Buttons aus Settings-Wert (für App-Start + Modus-Wechsel zurück
  Normal).
- **AC9** `reset_slot_filter` → entfernt (Lock persistiert, kein Reset).
  Bei Diversity nur `set_slot_buttons_visible(False)`.

### Helper-Funktion in qso_state.py (R1-S3)
- **AC10** Modul-Funktion `resolve_tx_slot(their_even, lock_status,
  rx_mode)`:
  - `lock_status="none"` ODER `rx_mode != "normal"` → wirkt wie heute
    (Hunt: `not their_even`, CQ: `None`)
  - `lock_status="even"`+`rx_mode="normal"`:
    - CQ-Pfad (their_even=None) → `True`
    - Hunt mit kompatibler Station (their_even=False) → `True`
    - Hunt mit Mismatch (their_even=True) → `None` (Caller blockt)
  - `lock_status="odd"` analog.

### TX-Pfade nutzen Helper
- **AC11** `_send_cq` (qso_state.py:184-186): `tx_even` mit Helper
  aufgelöst.
- **AC12** `_on_station_clicked` (mw_qso.py:200-205): Helper-Aufruf,
  bei `None` → `qso_panel.add_info("Klick ignoriert: Slot-Lock=X,
  Station sendet in Y, Antwort wäre in Z")` + `return`.
- **AC13** `_on_tx_slot_for_partner` (mw_qso.py:70-74): analog AC12.
- **AC14** OMNI: kein Patch (Diversity-only).

### Auto-Hunt (R1-S2)
- **AC15** `core/auto_hunt.py.select_next`: Lock-Filter, bei leerem
  Pool returnt None statt zufällige Station.

### Tests (Bundle-D-Tests aktualisieren + neu)
- **AC16** Bundle-D-Tests T6+T7 (RXPanel slot_filter) **löschen** (Code
  ist weg). T8 (Signal-Emit) auf neuen Signalnamen aktualisieren. T9-T11
  bleiben.
  Neue Tests in `tests/test_bundle_e.py`:
  - T1 Settings get/set_tx_slot_lock + defensive
  - T2 `resolve_tx_slot` für 6 Kombinationen
  - T3 QSO-Panel Signal-Rename + Set-Buttons aus Settings
  - T4 Hunt-Mismatch: Helper returnt None → add_info aufgerufen
  - T5 Normal-CQ mit Lock: encoder.tx_even gesetzt
  - T6 Auto-Hunt-Filter: keine kompatible Station → returnt None
  - T7 Mode-Wechsel Diversity: Lock-State bleibt in Settings, Buttons
    ausgeblendet
  - T8 Mode-Wechsel zurück Normal: Buttons aus Settings geladen

---

## 4. Thread-Safety (R1-F1)

R1 forderte `threading.Lock` für `encoder.tx_even`. Realität: Encoder
hat aktuell `self.tx_even = True/False/None` als simples Attribut.
GIL macht atomare Reads/Writes von Single-Reference-Werten safe.

**Pragma-Entscheidung KISS:** `encoder.tx_even` bleibt simples Attribut.
Race-Window ist nur „GUI setzt tx_even" vs „Worker liest tx_even" — in
Python GIL atomar für einzelne Referenzen. Kein zusätzlicher Lock.

Wenn R1-Final hier moniert → Lock einbauen. Für jetzt: keep simple.

---

## 5. Atomare Commits

| # | Commit | Files | LOC |
|---|--------|-------|-----|
| C1 | Rollback Filter in rx_panel | `ui/rx_panel.py` | ~-50 |
| C2 | Settings tx_slot_lock API | `config/settings.py` | +30 |
| C3 | Helper resolve_tx_slot | `core/qso_state.py` | +40 |
| C4 | QSO-Panel Signal-Rename + Set-Buttons | `ui/qso_panel.py` | ~30 |
| C5 | MainWindow Signal-Connect + Init | `ui/main_window.py` | ~25 |
| C6 | TX-Pfade nutzen Helper | `ui/mw_qso.py`, `core/qso_state.py` | ~40 |
| C7 | Auto-Hunt Lock-Filter | `core/auto_hunt.py` | ~20 |
| C8 | Tests | `tests/test_bundle_e.py` NEU + `test_bundle_d.py` Update | +250/-60 |
| C9 | APP_VERSION 0.97.22 + Doku | main.py + HISTORY + HANDOFF + CLAUDE + TODO + Memory | — |

---

## 6. Field-Test (F1-F9 für Mike)

- F1 Normal-Modus, EVEN klicken → orange-Highlight, persist
- F2 CQ rufen mit Even-Lock → TX nur in Even-Slot
- F3 Station X klicken die in Odd sendet → QSO startet (Gegentakt=Even, passt zu Lock)
- F4 Station Y klicken die in Even sendet → Klick ignoriert, `add_info` Hinweis
- F5 ODD klicken → wechselt
- F6 EVEN erneut klicken → uncheck → Lock="none"
- F7 App neu starten → letzter Lock wiederhergestellt
- F8 Modus → Diversity: Buttons weg, Lock in Settings bleibt
- F9 Zurück Normal: Buttons wieder gemäß Settings

---

## 7. Doku-Update

- HISTORY 0.97.22 (Bundle-E Refactor)
- HANDOFF neuer Stand
- CLAUDE Header
- TODO Bundle-D Korrektur vermerken + Bundle-E erledigt
- Memory `project_bundle_e_tx_slot_lock.md`
- Backup `Appsicherungen/2026-05-14_v0.97.21_vor_bundle_e_refactor/`

---

## 8. Compact-Fest-Check
✅ 16 ACs, R1-Findings F1+F2+S1-S4 alle adressiert (F1 KISS-Antwort),
9 atomare Commits, 8 Tests T1-T8, 9 Field-Test-Punkte F1-F9.
