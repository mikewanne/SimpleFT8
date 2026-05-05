[deepseek] ~35771 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=39795 out=5448 total=45243
## Bewertung von Mike's Vorschlag (v0.94)

### A) KALIBRIEREN-Button erweitern (Punkt 1)

**1. Logisch sinnvoll?**  
Ja. Der Code in `_on_dx_tune_accepted` hat bereits einen Diversity-Pfad, der `_enable_diversity` aufruft – aber nur wenn `_pending_dx_diversity` gesetzt ist. Beim direkten Kalibrieren-Klick wird dieses Flag nicht gesetzt, daher läuft nur Phase 2. Mike's Idee ergänzt genau diese Lücke: `_handle_dx_tuning` sollte je nach `_rx_mode` das passende Flag und `_pending_diversity_scoring` setzen, damit der vorhandene Code die komplette Pipeline (Gain + Phase 3) durchläuft. Das ist UX-technisch einwandfrei: ein Klick → vollständige Kalibrierung für den aktiven Modus.

**2. Code-Komplexität:** Minimal.  
Man muss in `_handle_dx_tuning` etwa drei Zeilen ergänzen:
```python
if self._rx_mode == "diversity":
    scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
    self._pending_dx_diversity = True
    self._pending_diversity_scoring = scoring
    gain_scoring = "snr" if scoring == "dx" else "stations"
    self._start_dx_tuning(scoring_mode=gain_scoring)
else:
    self._start_dx_tuning(scoring_mode=gain_scoring)
```
Das ist Wiederverwendung des existierenden `_pending_*`-Mechanismus – clean, kein neues Flag nötig.

**3. Edge-Case: Klick während laufender Phase 2**  
Bereits durch `_set_gain_measure_lock(True)` geschützt. Der Button ist deaktiviert. Kein Problem.

**4. Edge-Case: Modus-Wechsel während Phase 2**  
Ebenfalls durch Lock geblockt (`_gain_measure_locked`). Zustimmung.

**5. Timer-Reset**  
`_enable_diversity` ruft `reset()` auf, das `_last_measured_at` auf 0 setzt. Nach erfolgreicher Phase 3 wird in `_evaluate` der Timer aktualisiert. Explizites Setzen ist nicht nötig – bereits korrekt.

**Fazit Punkt 1:** Klar Ja. Geringer Aufwand, großer UX-Wert.

---

### B) Stats-Bug Phase 2 (Bug A)

**6. Fix-Strategie mit `_dx_tune_dialog is not None`**  
Ist sauber und minimalinvasiv. Der Dialog wird während Phase 2 gesetzt und nach Abschluss/Abbruch auf `None` gesetzt. `_is_antenna_tuning_active` gibt dann `True` zurück, und `_log_stats` blockt. Keine Race-Condition, da `_dx_tune_dialog` im GUI-Thread gesetzt/verändert wird (gleicher Thread wie `_log_stats`-Aufruf). Also ja, das ist die beste Lösung.

**7. Alternative `_rx_mode = "dx_tuning"`**  
Würde bedeuten, dass `_rx_mode` während Phase 2 den Wert `"dx_tuning"` annimmt. Das müsste man in `_on_cycle_decoded` berücksichtigen (dort wird nach `"normal"` und `"diversity"` verzweigt; momentan fällt der Code bei unbekanntem `_rx_mode` in `_handle_dx_tune_mode` – das ist ein glücklicher Umstand, aber kein sauberes Design). Nachteil: viele andere Stellen referenzieren `self._rx_mode` (z.B. im GUI-State, Settings), die dann unerwartet `"dx_tuning"` sehen. Invasiver und fehleranfälliger. Daher: Mikes Vorschlag vorziehen.

**8. RX-Panel-Anzeige während Phase 2**  
Aktuell wird in `_on_cycle_decoded` bei `_rx_mode == "normal"` `_handle_normal_mode` aufgerufen, das keine Antenneninfo aus dem Dialog holt. Die korrekte Antenne wird nur in `_handle_dx_tune_mode` gesetzt, der jedoch nur im `elif messages`-Zweig feuert – also nur wenn weder normal noch diversity aktiv ist. Das ist ein Bug: Während Phase 2 wird das RX-Panel mit falscher oder fehlender Antenne befüllt.  
Der Fix wäre ebenfalls minimalistisch: In `_on_cycle_decoded` vor den modusspezifischen Handlern prüfen:
```python
if self._dx_tune_dialog is not None:
    self._handle_dx_tune_mode(messages)
    # Keine weitere Verarbeitung für normal/diversity
    return
```
Das ist kosmetisch, aber einfach umsetzbar. Da Mike's Screenshot den Fehler zeigt, sollte man es mitnehmen. Kein over-engineering.

**Fazit Punkt 2:** Bug A fixen (Ja) mit Dialog-Check, plus optional RX-Panel-Fix (empfehlenswert).

---

### C) 0-Stations-Logging (Mike's Fairness-Frage)

**9. Tatsache:** `log_cycle` filtert nicht auf `station_count == 0`. Bestätigt korrekt. Auch `_log_stats` blockt nicht bei 0 – die Pre-Conditions sind wie beschrieben: warmup, tuning, CQ/QSO. Wenn keine davon blockt, wird auch ein Slot mit 0 Stationen geloggt.

**10. Pre-Conditions fair?**  
Ja. Warmup (6 Zyklen) verhindert Bias direkt nach Bandwechsel. Tuning-Block (neuer Dialog-Check inklusive) verhindert verfälschte Daten während Kalibrierung. CQ/QSO-Block verhindert Verzerrung durch eigenes TX. Keine Asymmetrie zwischen Normal und Diversity: beide werden durch die gleichen Checks blockiert (warmup, tuning, qso). Einzige Ausnahme: während `phase == "measure"` bei Diversity wird `_is_antenna_tuning_active` True → kein Logging. Das ist korrekt, weil nicht alle Antennen gemessen werden.

**11. Asymmetrie-Risiko?**  
Nein. Normal- und Diversity-Logs liegen in getrennten Verzeichnissen (`Statistics/Normal/band/`, `Statistics/Diversity_Normal/band/` etc.). Das Pooled-Mean wird pro Modus separat berechnet. Die unterschiedlichen Slot-Bedingungen (Normal immer A1, Diversity mit A1/A2) sind gewollt und stellen keine statistische Verzerrung dar, weil sie innerhalb des Modus konsistent sind.

**Fazit C:** Mike's Sorge ist unbegründet. Keine Änderung nötig.

---

### D) KISS-Bewertung

**12. Aufwand:**  
- Punkt 1: 5 Zeilen Code, kein Testaufwand (existierender Code).  
- Bug-Fix: 1 Zeile in `_is_antenna_tuning_active`.  
- RX-Panel-Fix: 4 Zeilen im Cycle-Handler.  
Gesamt: < 1h reine Code-Arbeit + kurzer Test. **Definitiv worth it.**  
Datenqualität (Bug-Fix) und UX (Punkt 1) sind zentrale Werte von SimpleFT8.

**13. Was weglassen?**  
Nichts zwingend, aber RX-Panel-Fix hat niedrigste Priorität – kein Datenverlust, nur visuell falsch. Dennoch: da Mike den Fehler dokumentiert hat, sollte er mitgenommen werden (minimaler Aufwand).

---

### Zusammenfassung Empfehlung

| Punkt | Entscheidung | Begründung |
|-------|--------------|------------|
| 1. KALIBRIEREN-Button erweitern | ✅ Ja | UX-Win, Code-Pfad existiert, geringer Aufwand |
| 2. Stats-Bug Phase 2 fixen | ✅ Ja, mit `_dx_tune_dialog`-Check | Datenqualität wichtig, minimalinvasive Lösung |
| 3. 0-Stations-Logging | 🟢 Bereits korrekt | Loggt auch 0, Pre-Conditions fair |
| 4. RX-Panel-Antenne Phase 2 fixen | ✅ Ja (optional, empfohlen) | Kosmetisch aber einfach, verhindert Verwirrung |

**KISS-Gesamtbewertung:** Sehr überschaubar, kein over-engineering. Der Plan ist fertig.
