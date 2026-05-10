[deepseek] ~50598 Tokens, 6 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=58370 out=5538 total=63908
## Kritischer Review von P23.OMNI-COUNTER-EIGEN V2

### KRITISCH (muss in V3 raus)

1. **Migration bestehender Tests unzureichend spezifiziert**  
   Der Plan behauptet, bestehende Tests blieben erhalten („Lauscher mit 2-Arg-Lambda bleiben“).  
   **Problem:** Die Tests in `test_omni_cq_signal.py` (z.B. `test_matching_cycle_calls_encoder_transmit_and_emits`, Zeile ~135) erwarten einen *aufsteigenden* Wert (`cq_count == 1` nach erstem TX). V2 liefert aber einen *absteigenden* `remaining`-Wert (10→9…).  
   **Konsequenz:** Diese Tests würden ohne Anpassung fehlschlagen.  
   **Lösung in V3:** Entweder alle alten Tests durch T1–T16 ersetzen (wie in §5 angedeutet) oder die betreffenden Asserts explizit auf `cq_remaining == _cq_target - 1` umschreiben. Der Plan muss klarstellen, welche Tests genau migriert werden und wie.

2. **`_append_three_color` existiert nicht im gegebenen `qso_panel.py`**  
   Im Plan (§3c) wird `_append_three_color` verwendet, aber das Modul kennt nur `_append_colored` und `_append_two_color`.  
   **Der Plan delegiert:** „Wenn nicht existiert: einfach line + ant_label + suffix als ein farbiger Block via `_append_colored` ausgeben — Detail bei der Code-Phase entscheiden“.  
   **Kritik:** Das ist ein Risiko – die Implementierung wird auf die Code-Phase verschoben, ohne dass klar ist, wie die farbliche Darstellung konkret aussieht.  
   **Lösung in V3:** Entweder `_append_three_color` definieren (z.B. zwei `_append_two_color`-Aufrufe) oder den kompletten Text als einen Block mit `_append_colored` ausgeben und die Akzentfarbe des Ant-Labels opfern.

### SOLLTE (Verbesserung empfohlen)

1. **T7: Test der „nur ein Emit“-Garantie fehlt**  
   Der Plan beschreibt T7 „`test_remaining_reaches_zero_triggers_flip_and_reset`“ und erwähnt, dass kein Zwischen-0-emit passieren darf. Es wird aber nicht spezifiziert, **wie** das getestet wird.  
   **Empfehlung:** In V3 ergänzen: Z.B. Spy auf `cq_count_changed` und prüfen, dass der Slot genau 1× aufgerufen wird (nicht 2×). Der Test sollte vor dem Aufruf eine Liste initialisieren und nach dem Slot die Länge asserten.

2. **T14 und T17 – Redundanz klarer adressieren**  
   Der Plan sagt: „T17 entfällt → redundant zu T14“. Das ist in Ordnung, aber die Liste in §5 enthält trotzdem 16 Tests, T17 ist nicht aufgeführt.  
   **Empfehlung:** In §5 explizit erwähnen, dass T17 gestrichen wird und warum. Sonst könnten Entwickler verwirrt sein.

3. **Fallback für `_append_three_color` konkretisieren**  
   Der Plan sagt nur „Detail bei der Code-Phase“.  
   **Empfehlung:** Schon im Plan festlegen, wie der Fallback aussieht. Ein Vorschlag:  
   ```python
   line_and_ant = f"{line}   {ant_label}"
   self._append_colored(line_and_ant, "#FFAA00")
   self._append_colored(suffix, "#FFAA00")  # gleiche Farbe, weil kein separater farblicher Akzent
   ```
   Oder man baut `_append_three_color` neu – aber das sollte im Plan stehen.

### KOENNTE (Optional)

- **`bool(self._cq_tx_even or False)` in `reset_counter_after_measure`** (V2-L8)  
  Ist defensiv sinnvoll, aber die Wahrscheinlichkeit, dass `_cq_tx_even` beim Aufruf `None` ist, ist extrem gering (weil der Counter nur bei aktivem OMNI mit gesetzter Parität resettet wird).  
  **Bewertung:** Harmlos, kann bleiben. KISS wird nicht verletzt.

- **`_OMNI_DEFAULT_TARGET = 10`**  
  Klares Fallback. Kein YAGNI – verteidigt gegen unbekannte Modi. Behalten.

### KISS-Bewertung

**Bestehen:**  
Der Plan ist insgesamt schlank, verzichtet auf unnötige Abstraktionen und Abhängigkeiten. Die Entscheidung, das Signal-Format beizubehalten (`(int, bool)`), ist KISS. Die Mess-Reset-Logik fügt nur eine Methode und einen Aufruf hinzu – minimaler Code.

**Schwächen:**  
- Die unscharfe Spezifikation von `_append_three_color` und der Fallback-Strategie (KRITISCH 2) könnte zu Aufblähung führen, wenn in der Code-Phase doch eine neue Methode gebaut wird.  
- Die fehlende Klarheit zur Testmigration (KRITISCH 1) zwingt entweder zu doppelter Arbeit (alte Tests anpassen) oder zu Redundanz (alle alten Tests ersetzen). Auch das ist kein KISS.

**Gesamt:** Der Plan ist KISS-konform, wenn die beiden kritischen Punkte gelöst werden.
