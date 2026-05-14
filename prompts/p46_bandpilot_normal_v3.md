# P46 — Bandpilot Normal-Reintegration (V3, 13.05.2026)

**Status:** V3 nach R1-Findings 8/10 — alle 4 R1-Findings uebernommen, bereit fuer Code.

**R1-Bilanz V2-Review:**
- F1 KRITISCH: P35-Bug-E-Tests muessen geloescht/umgeschrieben — **uebernommen** (loeschen)
- F2 SOLLTE: Doppelaufruf `_apply_normal_mode` in `_set_rx_mode_direct` — **uebernommen** (refactor)
- F3 SOLLTE: TX-pending-Konsistenz-Check nur Band, nicht Modus — **uebernommen** (current ins pending-Tupel)
- F4 KOENNTE: Test current=normal + rec=None — **uebernommen** (T7)

---

## 1. Was Mike will (unveraendert)

Bandpilot soll seit 12.05.2026 alle 3 Modi vergleichen (Normal + Diversity_Normal + Diversity_DX), nicht nur Diversity-Modi. P35-Bug-E von 11.05.2026 wird zurueckgenommen.

## 2. Code-Aenderungen (V3, R1-bereinigt)

### Maßnahme A — `_maybe_apply_bandpilot` Normal-Skip entfernen

`ui/mw_radio.py:774-779`:
```python
# P35 Bug E (Mike-Diagnose 11.05.): Bandpilot ueberschreibt
# Mike's manuelle Normal-Entscheidung NIE. Bandpilot's Aufgabe ist
# NUR zwischen Diversity-Standard und Diversity-DX zu waehlen —
# ob Mike ueberhaupt Diversity will, entscheidet Mike selbst.
if current == "normal":
    return False
```

→ **Block streichen** (R1-Empfehlung uebernommen).

### Maßnahme B — `_apply_bandpilot_auto` Normal-Target-Block entfernen

`ui/mw_radio.py:811-816`:
```python
# P35 Bug E: Bandpilot empfiehlt NIE Normal. Defensive — sollte
# durch Recommender-Logik schon abgedeckt sein, aber falls dort
# Normal als Top-1 erscheint (z.B. wenige Diversity-Daten):
# Mike-Regel "Normal ist Mike's Entscheidung" enforced.
if target == "normal":
    return False
```

→ **Block streichen** (R1-Empfehlung uebernommen).

### Maßnahme C — `_set_rx_mode_direct` Doppelaufruf-Refactor (R1-F2)

**Problem:** Bei `target == "normal"` und `_rx_mode == "diversity"`:
- Z.728 `self._disable_diversity()` ruft intern `_apply_normal_mode()` + setzt `_rx_mode = "normal"` + `control_panel.set_rx_mode("normal")`
- Z.729-731 macht **danach genau dasselbe nochmal** (`_rx_mode = "normal"`, `_apply_normal_mode()`, `set_rx_mode("normal")`)

**V3-Fix:** Wenn `_rx_mode == "diversity"` → `_disable_diversity()` macht ALLES, danach nur noch UI-only (btn_diversity-Text, freq_hist).

Neuer Code:
```python
if target == "normal":
    if self._rx_mode == "diversity":
        self._disable_diversity()
        # _disable_diversity setzt bereits _rx_mode="normal" +
        # _apply_normal_mode() + control_panel.set_rx_mode("normal")
    else:
        # Aktuell schon normal aber _set_rx_mode_direct wurde
        # trotzdem aufgerufen (z.B. UI-Re-Sync): nochmal absichern
        self._rx_mode = "normal"
        self._apply_normal_mode()
        self.control_panel.set_rx_mode("normal")
    # UI-only — _disable_diversity setzt diese beiden NICHT
    self.control_panel.btn_diversity.setText("DIVERSITY")
    self.control_panel._freq_hist.setVisible(False)
```

### Maßnahme D — TX-pending-Konsistenz mit current (R1-F3)

`_apply_bandpilot_auto` Z.826:
```python
self._bandpilot_pending = (band, utc_hour, rec, target)
```
→ wird zu:
```python
current = self._current_rx_mode_string()
self._bandpilot_pending = (band, utc_hour, rec, target, current)
```

`_on_bandpilot_tx_finished` Z.846-857:
```python
pending_band, _utc_hour, _rec, target = pending
```
→ wird zu:
```python
pending_band, _utc_hour, _rec, target, pending_current = pending
```

Plus neuer Konsistenz-Check nach Band-Check:
```python
current_now = self._current_rx_mode_string()
if current_now != pending_current:
    print(f"[Bandpilot] Pending verworfen — Modus zwischenzeitlich "
          f"manuell geaendert ({pending_current} → {current_now})")
    return
```

### Maßnahme E — Tests anpassen

**Zu löschen** (R1-F1 KRITISCH):
- `test_bandpilot_skips_when_current_is_normal` — testet alte Skip-Logik die geloescht wird
- `test_bandpilot_rejects_normal_target` — testet alten Defensive-Block der geloescht wird

Diese Funktionalitaeten werden in `test_p46_bandpilot_normal.py` ABGEDECKT durch T1 (current=normal → switch wird ausgefuehrt) + T2 (target=normal → switch wird ausgefuehrt).

**Zu aktualisieren:**
Bestehende 4 Tests in `test_mw_radio_bandpilot.py` haben Kommentare wie „P35 Bug E (Mike 11.05.): Bandpilot ueberschreibt Normal NIE. Test: current=diversity_normal (statt normal) damit Bandpilot wirkt." Diese Workaround-Begründungen sind nach P46 veraltet.

→ Kommentare **entfernen** (Workaround-Hinweis raus). Test-Code bleibt funktional, ist nicht mehr Workaround sondern reale Use-Cases.

### Maßnahme F — Neue Tests `test_p46_bandpilot_normal.py` (R1-erweitert)

7 Tests (T1-T6 wie V1 + T7 R1-F4):

| T# | Test | Erwartung |
|---|---|---|
| T1 | `test_auto_normal_to_diversity_dx` (current=normal, top1=diversity_dx, switch) | `_set_rx_mode_direct("diversity_dx")` aufgerufen |
| T2 | `test_auto_diversity_dx_to_normal` (current=diversity_dx, top1=normal, switch) | `_set_rx_mode_direct("normal")` aufgerufen — **vorher von P35-Bug-E geblockt!** |
| T3 | `test_auto_normal_no_change` (current=normal, top1=normal, no_change) | Keine Aenderung, kein Toast |
| T4 | `test_manual_normal_to_other` (current=normal, top1=diversity_normal) | Dialog aufgerufen |
| T5 | `test_manual_other_to_normal` (current=diversity_dx, top1=normal, User waehlt normal) | `_set_rx_mode_direct("normal")` aufgerufen |
| T6 | `test_auto_normal_target_tx_pending` (TX laeuft, target=normal) | Pending tuple gespeichert mit current; tx_finished triggert Wechsel |
| T7 | **R1-F4 NEU:** `test_normal_insufficient_data` (current=normal, rec=None) | `_show_bandpilot_insufficient_data` aufgerufen, kein Wechsel |

### Maßnahme G — TX-pending-Race-Test (R1-F3)

T8 ZUSAETZLICH:
| T# | Test | Erwartung |
|---|---|---|
| T8 | `test_tx_pending_discarded_when_user_changed_mode` (TX laeuft, target=normal, pending gespeichert, dann User wechselt manuell auf diversity_normal, tx_finished feuert) | Pending verworfen, kein Wechsel zu normal |

## 3. Akzeptanzkriterien (V3)

| AK | Bedingung | Verifikation |
|---|---|---|
| **AK1** | `mw_radio.py` enthält KEIN `if current == "normal": return False` mehr | grep |
| **AK2** | `mw_radio.py` enthält KEIN `if target == "normal": return False` mehr | grep |
| **AK3** | `_set_rx_mode_direct("normal")` mit `_rx_mode="diversity"` ruft `_apply_normal_mode` GENAU 1× (nicht 2×) | T-Spy oder Manual-Code-Review |
| **AK4** | `_bandpilot_pending`-Tupel ist 5-elementig (band, utc_hour, rec, target, current) | grep + T8 |
| **AK5** | T1-T8 alle grün | pytest |
| **AK6** | Bestehende 2 P35-Bug-E-Tests sind gelöscht | grep |
| **AK7** | Bestehende 4 Workaround-Tests haben aktualisierte Kommentare (keine „P35 Bug E damit" mehr) | grep |
| **AK8** | Volle Test-Suite grün (1227 + ~6 effektiv = ~1233) | pytest |
| **AK9** | P35-Bug-F (App-Start IMMER 20m FT8 Normal) unverändert | Code-Review main_window.__init__ |

## 4. Files

| Datei | Aenderung |
|---|---|
| `ui/mw_radio.py` | Maßnahmen A+B+C+D (4 Edit-Bloecke) |
| `tests/test_mw_radio_bandpilot.py` | 2 Tests loeschen + 4 Tests Kommentare aktualisieren |
| `tests/test_p46_bandpilot_normal.py` NEU | 8 Tests (T1-T8) |
| `main.py` | APP_VERSION 0.97.16 → 0.97.17 |
| `docs/explained/bandpilot_de.md` + `.md` | Falls existiert: Hinweis dass Normal jetzt empfohlen werden kann |
| HISTORY/HANDOFF/CLAUDE/MEMORY/TODO | Standard-Doku-Updates |

## 5. Backup & Commits

**Backup:** `Appsicherungen/2026-05-13_v0.97.16_vor_p46_bandpilot_normal/`
mit `ui/mw_radio.py` + `tests/test_mw_radio_bandpilot.py`.

**Atomare Commits:**
- **C1** `ui/mw_radio.py` — Maßnahmen A+B (Normal-Bloecke streichen)
- **C2** `ui/mw_radio.py` — Maßnahme C (Doppelaufruf-Refactor)
- **C3** `ui/mw_radio.py` — Maßnahme D (TX-pending mit current)
- **C4** `tests/test_mw_radio_bandpilot.py` — 2 Tests loeschen + 4 Kommentar-Updates
- **C5** `tests/test_p46_bandpilot_normal.py` — 8 neue Tests
- **C6** `main.py` — APP_VERSION 0.97.17
- **C7** Doku (HISTORY+HANDOFF+CLAUDE+Memory+TODO+ggf. bandpilot_de.md)

## 6. Risiken

| R | Risiko | Mitigation |
|---|---|---|
| R1 | Bandpilot wechselt User unerwartet von Diversity auf Normal | Mike-Wunsch, bewusst. Auto-Toast 5 Sek warnt. |
| R2 | Mike vergisst P35-Bug-E-Rücknahme | HISTORY+Memory dokumentieren Strategie-Wechsel |
| R3 | P35-Bug-F versehentlich auch zurückgesetzt | AK9 Code-Review |
| R4 | TX-pending-Refactor (Maßnahme D) bricht alte Tests | T6+T8 decken neuen Pfad ab |
| R5 | `_set_rx_mode_direct` Refactor (Maßnahme C) bricht Diversity-Wechsel | bestehende Tests in `test_mw_radio_bandpilot.py` Z.190-220 testen schon Diversity-Wechsel-Pfad |

## 7. Was Final-R1 noch sagen wird

R1 wird vermutlich:
- T-Decken-Bewertung gut (8 Tests, alle Pfade abgedeckt)
- Doppelaufruf-Refactor sauber (R1-F2 erfüllt)
- TX-pending-Konsistenz (R1-F3 erfüllt)
- KOENNTE: eventuell zusätzlicher Test für „Manual-Dialog Cancel bei Normal"
- HINWEIS: Doku-Datei bandpilot_de.md prüfen ob existiert

---

**V3 ist freigegeben für Code-Implementation** (Mike's voll-autonom-Anweisung).
