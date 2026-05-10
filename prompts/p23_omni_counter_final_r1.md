[deepseek] ~49769 Tokens, 7 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=57023 out=9746 total=66769
## Code-Review P23.OMNI-COUNTER-EIGEN (v0.96.7)

---

### KRITISCH (muss vor Push raus)

**1. Font-Risiko für Symbol `↻` (U+21BB) – fehlender Glyph möglich**

- **Datei:** `ui/qso_panel.py` – `add_tx()`-Methode, Zeile ~63  
- **Problem:**  
  Das Suffix `  ↻{n}` verwendet das Unicode-Symbol `↻` (U+21BB). Die `QTextEdit` im QSO-Panel nutzt den Monospace-Font *Menlo* (Zeile `self.log_view.setFont(QFont("Menlo", 12))`).  
  *Menlo* ist primär auf macOS verfügbar; auf Linux/Windows wird meist ein Fallback-Monospace-Font ohne dieses Zeichen gewählt. Das Symbol wird dann als leeres Quadrat `□` oder gar nicht dargestellt. Die Akzeptanzkriterium A7 („Suffix `  ↻{n}`“) wäre damit visuell verletzt.

- **Begründung:**  
  Der Test `test_qso_panel_add_tx_with_omni_remaining_renders_suffix` prüft `↻7 in toPlainText()` – das liefert True auch bei fehlendem Glyph, weil `toPlainText()` den Unicode-Text unabhängig von der Darstellung zurückgibt. Der Fehler wird also nicht durch Tests abgefangen, ist aber ein echtes UI-Problem.

- **Fix-Vorschlag:**  
  - **Option A:** Suffix auf `  R{n}` (z.B. `↻` → ` R`) ändern – funktioniert in jedem Font.  
  - **Option B:** In der QTextEdit einen Font setzen, der U+21BB garantiert darstellt (z.B. `Segoe UI Symbol` für Windows, `Apple Symbols` für macOS).  
  - **Option C:** Fallback: Nur wenn `omni_remaining` gegeben, `f"  ↻{omni_remaining}"` anhängen, aber zusätzlich einen Cross-Plattform-Fallback-String definieren.

**Empfehlung:**  
Da KISS oberstes Gebot ist, wähle ich **Option A** – ersetze `↻` durch ` R` (oder ` n` / `r`). Die Anforderung A7 ist mit `  R{n}` ebenso erfüllt (klares Suffix für „verbleibende Runden“) und es ist resistenter gegen Font-Probleme.

- **Betroffene Zeilen:**  
  - In `add_tx`: `line = f"{line}  ↻{omni_remaining}"` → `line = f"{line}  R{omni_remaining}"`  
  - In `tests/test_p23_omni_counter.py`, Test T16 + T16b: `"↻7"` → `" R7"` bzw. Assert auf `"R"`.

---

### SOLLTE (Verbesserung empfohlen)

**2. Test T7 – Slot-Parität nach Flip nicht simuliert → Test unvollständig**

- **Datei:** `tests/test_p23_omni_counter.py` – `test_remaining_reaches_zero_triggers_flip_and_reset_with_one_emit`  
- **Problem:**  
  Der Test ruft `on_cycle_start` zehnmal mit **immer gleicher** `fake_time=30.0` (Even-Slot) auf. Nach dem Flip (10. TX) ist `_cq_tx_even=False`, der nächste `on_cycle_start` würde wegen Mismatch **keinen TX** ausführen – das ist beabsichtigt, weil die Schleife abbricht.  
  Der Test ist also **fragil**: Sobald jemand die Logik ändert (z.B. den Flip erst im nächsten Slot ausführt), würde der Test grün bleiben, obwohl das Verhalten falsch ist. Ausserdem enthält der Test einen überflüssigen `if i < target - 1: pass`-Block.

- **Empfehlung:**  
  - Nach jedem Slot prüfen, ob die Parität umgeschaltet wurde und ggf. `fake_time` auf den nächsten passenden Slot setzen (z.B. `return_value` um 15s erhöhen).  
  - Den leeren `if`-Block entfernen.  
  - Alternativ den Test straffen: Nur 2 TXs simulieren, Flip erzwingen und die korrekte Emit-Anzahl und Emit-Werte prüfen (T1-T4 sind bereits für die Targets vorhanden, T7 muss nicht unbedingt 10 TXs prüfen – solange der Pfad bei `remaining==0` getestet wird, reichen 2 TXs aus).

**3. Mode-Wechsel-Pfade sollten `stop()` garantieren**

- **Datei:** `core/omni_cq.py`, Zeilen `_get_target`-Logik (nur in `start()` aufgerufen)  
- **Hintergrund:**  
  `start()` liest `timer.mode` um `_cq_target` zu setzen. Wenn der Modus während OMNI-Aktivität wechselt, ohne `stop()` aufzurufen, läuft der Counter mit dem falschen Target weiter.  
  Im gegebenen Code ist zu sehen, dass `_on_tx_started` (mw_qso.py) und `_on_cycle_start` (mw_cycle.py) kein Mode-Check haben – der Target-Wechsel müsste über `stop()` erfolgen.

- **Empfehlung:**  
  - Verifikation, dass `mw_radio.py:212` (Mode-Wechsel-Handler) immer `omni_cq.stop()` aufruft.  
  - Falls nicht bereits geschehen, in MainWindow `_on_mode_changed` und `_on_band_changed` ein `self._omni_cq.stop("mode_change")` einfügen (oder sicherstellen, dass die entsprechenden Mixins dies tun).  
  - Im Sinne von Defense-in-Depth könnte `on_cycle_start` zusätzlich prüfen, ob `mode` sich geändert hat (z.B. durch Vergleich mit `self._last_mode`) – aber das wäre Overengineering.

**4. Test T7 – Emit-Anzahl nach `parity_flipped` nicht geprüft**

- **Aktuell:** Nur `len(captured_flips) == 1` und `captured_flips[0] is False`.  
- **Empfehlung:**  
  Prüfen, dass der `parity_flipped`-Emit **nach** dem letzten `cq_count_changed` mit Wert `target` kommt (z.B. durch Überprüfung der Reihenfolge in `captured_emits` mit einem gemeinsamen Counter). Das erhöht die Testqualität.

---

### KOENNTE (Optional)

**5. Defensiver Check für `_cq_target == 1` in `on_cycle_start`**

- **Kontext:**  
  Falls jemand irgendwann `_cq_target` auf 1 setzt (z.B. durch Bugs oder manuelle Manipulation), würde nach dem Decrement `_cq_remaining==0` zum Flip führen, dann wird `_cq_remaining = _cq_target = 1` gesetzt → nächster TX: decrement auf 0 → erneuter Flip → Endlosschleife (immer 1 TX pro Slot).

- **Lösung:**  
  In `on_cycle_start` nach dem Flip prüfen:  
  ```python
  if self._cq_target < 2:
      self._cq_remaining = 2  # oder stop mit Warnung
  ```
  Ist aber ein sehr unwahrscheinlicher Fall und würde den KISS-Prinzip widersprechen. Daher nur optional.

**6. Doku-Kommentar zu `resume_after_qso` aktualisieren**

- In `core/omni_cq.py` steht `# Mike-Spec: „wenn QSO funktioniert, neuer Slot startet bei TARGET"`.  
  Das ist korrekt. Aber der Parameter `last_was_even` wird ignoriert und sollte im Docstring als „reserviert für zukünftige Nutzung“ markiert werden.

---

### Push-Empfehlung

**Push nach KRITISCH-Fix**  
(KRITISCH #1 muss behoben werden → Suffix von `↻` zu ` R` ändern + Tests anpassen)

Die restlichen SOLLTE- und KOENNTE-Punkte sind nicht blockierend, sollten aber in einem Folge-Sprint adressiert werden.

---

### KISS-Bewertung

Der Code ist insgesamt gut lesbar, die Trennung in `core/omni_cq.py` und UI-Hooks ist sauber. Der Down-Counter ist simpel und die Auto-Flip-Logik prägnant.  
Einzige KISS-Verletzung: Das Font-Symbol `↻` statt einem einfachen ASCII-Zeichen – das ist unnötig exotisch und erzeugt Wartungs- und Portabilitätsaufwand.

**KISS-Note:** 8/10 (Abzug für Font-Auswahl + die redundanten `if`-Blöcke in Test T7).
