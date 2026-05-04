[deepseek] ~32681 Tokens, 3 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=37114 out=6511 total=43625
# V2 Self-Review – Senior-Reviewer Analyse

## Executive Summary

Das Review bestätigt alle 5 Befunde als valide. Zwei zusätzliche Lücken wurden identifiziert. Die KISS-Lösung ist ausreichend, **sofern sie auf `_on_rx_mode_changed` erweitert wird** und der Bandpilot-Pending-Mechanismus nach Lock-Ende implementiert wird (optional, aber empfohlen).

---

## A) Lock-Coverage

### Befund 1 (Bandwechsel-Race) – **KRITISCH**
✅ **Bestätigt.**  
Der Race ist real und tritt bei jedem Bandwechsel während aktiver Mess-Phase auf.  
**Schweregrad:** KRITISCH, weil:
- Daten werden in falsches Band-Bucket geschrieben (40m-Score landet in 20m-Bucket)
- Antennen-Ratio wird basierend auf kontaminierten Daten berechnet
- Effekt bleibt bis zur nächsten vollständigen Neueinmessung erhalten (15–30 Min)
- Selbst 1 von 10 Bandwechseln reicht aus, um die Langzeit-Statistik zu verzerren

**Fix:** Mike's KISS-Früh-Return in `_on_band_changed`.

### Befund 2 (Mode-Wechsel) – **MITTEL**
✅ **Bestätigt, aber geringere Auswirkung.**  
`_on_mode_changed` ruft **kein** `reset()` auf → der Phase-Check bleibt intakt.  
Das Problem:  
- `set_mode()` ändert die Zykluszeit (z.B. FT8 15s → FT4 7.5s)
- **Laufende Slots** haben unterschiedliche Timing → Decode-Daten können asynchron ankommen
- Ein Mode-Wechsel während der Mess-Phase kann `_measure_step` inkonsistent machen (Antennen-Pattern bricht ab)

**Schweregrad:** Mittel, weil:
- Ohne `reset()` bleibt die Phase korrekt
- Aber die Zyklus-Zeit-Änderung kann zu verschobenen `_on_cycle_decoded`-Aufrufen führen
- `_pop_diversity_queue()` bekommt dann evtl. einen falschen `was_phase`-Wert

**Fix:** Früh-Return in `_on_mode_changed` (Mike's Vorschlag) **zwingend**.

### Befund 3 (Reihenfolge in `_enable_diversity`) – **MITTEL** (aber Fix ist trivial)

✅ Bestätigt.  
Das Race-Window in Zeilen 811-813:
```python
self._diversity_ctrl.reset()        # Z.811 ← Bucket geleert
self._set_cq_locked(True)           # Z.812
self._set_gain_measure_lock(True)   # Z.813 ← Lock spaet
```
Ein Slot, der genau zwischen 811 und 813 ankommt, könnte einen Messdatenblock schreiben, der dann durch den `reset()` gelöscht wird → kein Schaden.  
Aber ein Slot, der **nach** `reset()` aber **vor** `_set_gain_measure_lock` startet, kann Daten in ein frisches Board schreiben → kontaminiert die neue Messung.

**Schweregrad:** Mittel, da das Window extrem kurz ist (< 1 µs). Trotzdem: Umkehrung kostet nichts.

**Fix:** Reihenfolge ändern:
```python
self._set_cq_locked(True)
self._set_gain_measure_lock(True)
self._diversity_ctrl.reset()  # Lock vor Reset
```

### D) Mike's KISS-Lösung – **AUSREICHEND mit Ergänzungen**

1. **Band und Mode:** Ja, schützt beide kritischen Pfade.  
2. **RX-Mode-Wechsel fehlt:** `_on_rx_mode_changed` ruft `_disable_diversity()` und `_activate_diversity_with_scoring()` auf. Diese können ebenfalls während einer laufenden Messung aufgerufen werden (z.B. über Bandpilot). **Daher muss `_on_rx_mode_changed` ebenfalls geprüft werden.**  
3. **Programmatische Aufrufe aus Tests:** Tests setzen `_gain_measure_locked` in der Regel nicht → werden nicht blockiert. Das ist erwünscht.  
4. **Settings-Dialog:** `settings.set("band", X)` wird nur im Signal-Wege aufgerufen, der Dialog selbst feuert `_on_band_changed`. Mit Früh-Return blockiert.  
5. **Init-Race-Guard (main_window:705):** Separates Thema, nicht betroffen.

**Notwendige Erweiterung des KISS-Fixes:**

```python
@Slot(str)
def _on_rx_mode_changed(self, mode: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[RX-Mode ignoriert: Pipeline läuft]")
        # UI-Button zurücksetzen
        old_mode = "normal" if self._rx_mode == "normal" else "diversity"
        self.control_panel.set_rx_mode(old_mode)
        return
    # ... rest
```

**Optionaler Bandpilot-Pending-Mechanismus:**
Wenn `_on_band_changed` wegen Lock blockiert wird, aber der Aufruf durch `_maybe_apply_bandpilot` (oder `_on_band_changed` selbst) kam, sollte dieser nach Lock-Ende wiederholt werden.  
Mike's KISS erlaubt das nicht, aber für das Hobby-Szenario ist das akzeptabel (der Bandpilot wird beim nächsten Slot-Ende oder manuell erneut triggern).  
Falls gewünscht:
```python
# In _set_gain_measure_lock
if not locked and getattr(self, '_pending_band_change', None):
    band = self._pending_band_change
    self._pending_band_change = None
    self._on_band_changed(band)
```

---

## B) Befund 4 (Geister-Slots in Operate-Phase)

**Klar/unklar:** Das Szenario ist klar, aber die Auswirkung ist schwächer als angenommen.

- Der Phase-Check in `record_measurement` blockt Daten nach `_phase = "operate"`.  
- Allerdings: Ein Slot, der in der Mess-Phase **gestartet** wurde (`ant_queue.append` mit `was_phase = "measure"`), aber dessen Decode erst nach dem Phase-Wechsel ankommt, wird trotzdem `_handle_diversity_measure` aufrufen.  
- Wenn der Phase-Wechsel **während** des Slots passiert (Adaptiv-Stop oder normales Ende), steht `_phase` bereits auf `"operate"` und `record_measurement` schützt.  
- Wenn der Phase-Wechsel **vor** dem Slot-Ende passiert, wird der Messwert verworfen. Kein Schaden.

**Problematisch:** `station_accumulator` und `_log_stats` laufen unabhängig von der Phase.  
- `station_accumulator` sammelt Stationen aus der Operate-Phase → das ist beabsichtigt.  
- `_log_stats` wird bei `_is_antenna_tuning_active()` pausiert, solange `phase == "measure"`. Nach Phase-Wechsel läuft es wieder.  
→ **Keine Kontamination der Messung.** Die Geister-Daten verschwinden einfach im `record_measurement`-Filter.

**Schweregrad:** **Nicht relevant** für die Antennenentscheidung.  
Für die Statistik kann es zu einer leichten Verzerrung kommen, weil ein Slot, der eigentlich zur Mess-Phase gehörte, nun als Betriebs-Zyklus verbucht wird. Die Anzahl ist minimal (< 1 Slot pro 6 Mess-Slots). Kein Fix nötig.

---

## C) Andere ersichtliche Fehler

### `_on_band_changed` (Z.265-360)
- **Zeile 269:** `self._tune_token = None` – korrekt, schützt vor Callbacks aus altem Tune.  
- **Zeile 294:** `self._diversity_ctrl.on_band_change()` → `reset()` ist korrekt, aber die Reihenfolge (vor Lock) ist das Problem (Befund 3).  
- **Zeile 362-367:** Bandpilot-Check nach `_maybe_apply_bandpilot` → korrekt, nach User-Klick wird Bandpilot geprüft (auch `auto`-Modus).  
- **Fehlende Absicherung:** `self._maybe_apply_bandpilot(band)` könnte selbst `_on_rx_mode_changed` aufrufen, das ebenfalls Race-exponiert ist (s.o.).

### `_on_mode_changed` (Z.199-260)
- **Zeile 207:** `self._diversity_ctrl.set_mode(mode)` – ändert Such-Intervalle, sonst kein Crash.  
- **Zeile 220-223:** `self._check_diversity_preset(band, mode, scoring)` – könnte Pipeline starten mit Tune + Gain-Messung. Das ist asynchron und könnte während der laufenden Dekodierung passieren. Ein Früh-Return blockt das.  
- **Keine `reset()`-Gefahr** → Phase-Check bleibt intakt. Trotzdem sollte Früher-Return erfolgen.

### `_set_gain_measure_lock` (Z.1080-1106)
- **Fehlende Button-Typen:** `btn_diversity` und `btn_normal` werden gesperrt – korrekt.  
- `btn_tune` und `btn_einmessen` sind optional und werden gesperrt – korrekt.  
- **Fehlender Button:** `btn_rx_panel` (RX ON/OFF) sollte gesperrt sein, weil RX OFF während der Messung Antenne zurück auf ANT1 setzen würde.  
  ```python
  if hasattr(self.control_panel, 'btn_rx'):
      self.control_panel.btn_rx.setEnabled(not locked)
  ```
  **Ergänzung empfehlenswert**, aber nicht kritisch.

### `_handle_diversity_measure` (mw_cycle.py:171-208)
- **Z.173:** `if self._phase != "measure": return` – korrekt.  
- **Z.182-185:** Mit `self._diversity_lock` geschützt – korrekt.  
- **Z.193:** Überprüfung `old_phase == "measure" and self._diversity_ctrl.phase == "operate"` → GUI-Lock-Release.  
- **Problem:** Der Lock-Release erfolgt im **gleichen Slot**, in dem `_evaluate` aufgerufen wird. Wenn aber nach `_evaluate` noch ein weiterer Slot mit `was_phase == "measure"` ankommt (weil die Queue noch einen alten Eintrag hat), wird `record_measurement` aufgerufen und blockt sich selbst (Phase-Check). Das ist okay.  
- **Aber:** Der GUI-Lock wird aufgehoben, bevor der letzte "Geister"-Slot verarbeitet ist. Das ist harmlos, weil der Slot selbst keine neuen Locks braucht.  
→ **Keine weiteren Lücken.**

### Weitere Beobachtung: `_on_cycle_start` (Z.240-282)
- **Z.255:** `if self.encoder.is_transmitting: return` – verhindert Antennenwechsel während TX.  
- **Z.244:** `ant_queue.append((self._diversity_current_ant, self._diversity_ctrl.phase))` – hier wird der Phase-Wert zum Zeitpunkt des Startzyklus’ eingefroren. Wenn später `_evaluate` während des Zyklus’ aufgerufen wird (Adaptiv-Stop), stimmt der `was_phase`-Wert nicht mehr. **Das ist die Wurzel des Geister-Slot-Problems (Befund 4).**  
  **Fix:** Statt `self._diversity_ctrl.phase` zu speichern, könnte man ein lokales Flag `_queued_phase` setzen. Aber wie oben beschrieben, filtert `record_measurement` korrekt → nicht notwendig.

---

## D) Test-Strategie

| Test | Beschreibung | Erwartung |
|------|-------------|-----------|
| Unit-Test Bandwechsel-Race | Mock `_set_band` während Pipeline-Lock → Früh-Return | `_on_band_changed` wird nicht ausgeführt |
| Unit-Test Mode-Wechsel-Race | Mock `_set_mode` während Pipeline-Lock → Früh-Return | `_on_mode_changed` wird nicht ausgeführt |
| Unit-Test RX-Mode-Race | Mock `_set_rx_mode` während Pipeline-Lock → Früh-Return | `_on_rx_mode_changed` wird blockiert |
| Integration-Test Slot-In-Flight | Simuliere laufenden Slot (z.B. über `timer.set_current_slot()`) + rufe `_on_band_changed` auf | Keine Daten im neuen Band-Bucket |
| Integration-Test Lock-Release | Nach `_evaluate` wird Lock freigegeben → Bandwechsel möglich | `_on_band_changed` läuft korrekt durch |
| Integration-Test Bandpilot nach Lock | Bandpilot-Aktion während Lock → pending-Variable? (optional) | Bei Lock-Ende wird Bandwechsel wiederholt (nur bei erweiterter Lösung) |

**Wie Slot-In-Flight ohne echten Decoder testen:**  
- `self._diversity_ant_queue` mit einem Tupel `("A2", "measure")` füllen  
- `self._diversity_ctrl._measure_step` auf 1 setzen (damit erwartet wird, dass ein Messwert fehlt)  
- Dann `_on_band_changed` aufrufen → sollte blocken → nach Lock-Aufhebung neuer Aufruf → Queue ist leer (weil `reset()` sie entfernt hat) → ok.

---

## Zusammenfassung der benötigten Code-Änderungen

### 1. `_set_gain_measure_lock` – Flag setzen
```python
def _set_gain_measure_lock(self, locked: bool):
    self._gain_measure_locked = locked  # NEU
    # ... rest + btn_rx absichern
```

### 2. `_on_band_changed` – Früh-Return (Mike's KISS)
```python
@Slot(str)
def _on_band_changed(self, band: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[Bandwechsel ignoriert: Pipeline läuft, bleibe auf {self.settings.band}]")
        self.control_panel._set_band(self.settings.band)  # UI zurücksetzen
        return
    # ...
```

### 3. `_on_mode_changed` – Früh-Return
```python
@Slot(str)
def _on_mode_changed(self, mode: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[Mode ignoriert: Pipeline läuft]")
        self.control_panel._set_mode(self.settings.mode)
        return
    # ...
```

### 4. `_on_rx_mode_changed` – Früh-Return (NEU, wird von Mike's Vorschlag nicht abgedeckt)
```python
@Slot(str)
def _on_rx_mode_changed(self, mode: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[RX-Mode ignoriert: Pipeline läuft]")
        self.control_panel.set_rx_mode("normal" if self._rx_mode == "diversity" else "diversity")
        return
    # ...
```

### 5. `_enable_diversity` – Reihenfolge umkehren (Befund 3)
```python
def _enable_diversity(self, scoring_mode: str = "normal"):
    # ...
    self._set_cq_locked(True)                    # Z.812 nach oben
    self._set_gain_measure_lock(True)             # Z.813 nach oben
    self._diversity_ctrl.reset()                  # Z.811 nach unten
    # ...
```

### 6. Optional: `_on_band_changed` Bandpilot-Pending
```python
_pending_band_change = None  # Klassenattribut

def _on_band_changed(self, band: str):
    if getattr(self, '_gain_measure_locked', False):
        self._pending_band_change = band  # merken
        return
    # ... nach Bandwechsel
    self._pending_band_change = None

def _set_gain_measure_lock(self, locked: bool):
    if not locked and self._pending_band_change:
        band = self._pending_band_change
        self._pending_band_change = None
        QTimer.singleShot(0, lambda: self._on_band_changed(band))  # asynchron
```

---

## Gesamteindruck

V2 des Self-Reviews ist **gut durchdacht und vollständig**. Die Befunde sind korrekt, die KISS-Lösung ist angemessen. Zwei kleine Lücken (RX-Mode und btn_rx) sollten geschlossen werden, um das Lock-Konzept wirklich wasserdicht zu machen. Die Reihenfolgen-Korrektur ist trivial. Der Bandpilot-Pending-Mechanismus ist optional, da im Hobby-Use die manuelle Wiederholung oder der nächste Bandpilot-Trigger ausreicht.

**Empfehlung:**  
- Fix 1–5 als **Must-Have**.
- Fix 6 als **Nice-to-Have**, sofort umsetzbar.
- Test nach D) durchführen.
- Sonstige ersichtliche Fehler im Code der betroffenen Abschnitte (C) sind nicht vorhanden.
