[deepseek] ~16073 Tokens, 2 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=18958 out=5793 total=24751
## R1-Diskussion: Mess-Statistik bei dünner Decoder-Dichte

### 1. Ist Median über Slot-Stations-Anzahl bei dünner Dichte ein gutes Score?

**Klarheit:** Klar – die Analyse zeigt, dass der Median über diskrete Slot-Werte ∈ {0,1,2} bei FT2 kaum Auflösung bietet. Der Median ist entweder 0, 1 oder 2, und eine echte Differenz von z.B. 0,3 Stationen pro Slot wird nicht zuverlässig abgebildet.

**Empfehlung:**  
Wechsel von **reiner Stationsanzahl** zu einem **SNR-basierten Score**.  
Statt pro Slot nur `station_count` zu speichern, sollten alle **SNR-Werte** der dekodierten Stationen (oder zumindest deren Summe / Median) akkumuliert werden.  
- SNR-Werte sind kontinuierlich (typisch -20…-5 dB), geben also weitaus mehr statistische Power.  
- Auch bei nur 1–2 Stationen pro Slot liefern die SNR-Werte einen sinnvollen Durchschnitt.  
- Die Änderung verbessert nicht nur FT2, sondern auch FT8/FT4, da SNR eine feinere Metrik als die reine Anzahl ist.  
- Implementierung: Statt `self._measurements[ant].append(float(station_count))` könnte man z.B. die Summe aller `(snr + 30)` über die Dekodes des Slots anhängen (oder den Median der SNR). Der `score`-Parameter in `record_measurement` wird bereits mit `sum(snr+30)` berechnet, aber aktuell nicht verwendet. Man könnte diesen Wert direkt nutzen: `self._measurements[ant].append(score)` – das wäre eine minimale Code-Änderung (Nutzung des vorhandenen `score`-Werts). Dadurch wird aus einem diskreten Slot-Wert eine kontinuierliche Gleitkommazahl, die den SNR-Bereich abdeckt.

**KISS-Bewertung:**  
Sehr einfach – lediglich die Zeile `self._measurements[ant].append(float(station_count))` durch `self._measurements[ant].append(float(score))` ersetzen. `score` ist bereits vorhanden und bei dekodierten Stationen > 0. Für leere Slots bleibt `score=0`. Das erhält die Median-Berechnung, aber auf kontinuierlichen Werten. Die `peak <= 1.0`-Schwelle muss ggf. an SNR-Skala angepasst werden (z.B. `peak <= 5.0`). Kein neuer Code-Flow, voll KISS.

---

### 2. Sollte SCORING-MODE für FT4/FT2 anders sein?

**Klarheit:** Klar – der aktuelle `dx`-Modus zählt schwache Stationen (SNR < -10), was bei 1–2 Stationen pro Slot noch spärlicher ist. Sinnvoller wäre ein einheitlicher SNR-basierter Ansatz ohne Modus-Unterscheidung für FT4/FT2.

**Empfehlung:**  
Für alle Modi (FT8/FT4/FT2) sollte der **gleiche SNR-basierte Score** verwendet werden. Der `scoring_mode`("normal" vs "dx") kann entfallen oder vereinheitlicht werden – z.B. ein Modus "snr" statt "normal". Die separate Zählung von `dx_weak_count` ist dann obsolet, da SNR ohnehin die Qualität abbildet.  
Praktisch: `record_measurement` speichert immer den `score` (Summe(snr+30)). Das ist robust gegen geringe Stationenzahlen und liefert auch bei FT2 brauchbare Werte.

**KISS-Bewertung:**  
Die Änderung ist minimal (s.o.), der `scoring_mode` kann als deprecated markiert oder auf einen identischen Pfad umgestellt werden. Keine zusätzliche Komplexität.

---

### 3. _MULT für MEASURE_CYCLES – behalten oder weg?

**Klarheit:** Klar – Mike’s Beispiel zeigt, dass auch 24 Slots bei FT2 statistisch noch grenzwertig sind, aber mehr Slots helfen nicht linear. Dennoch bringen 12 Slots pro Antenne mehr Robustheit als 3.

**Empfehlung:**  
**Option b beibehalten** (`_MULT = 1/2/4` für FT8/FT4/FT2).  
Begründung:  
- Die Zeitinvestition ist bei FT2 gering (3,8 s/Zyklus → 24 Zyklen = 91 s), also akzeptabel.  
- Mehr Datenpunkte glätten die diskrete Verteilung, auch wenn die Basis 0/1/2 bleibt. Mit dem SNR-basierten Score (Frage 1) wird dieser Effekt noch verstärkt, da die Werte jetzt kontinuierlich sind.  
- Option a (alle 6 Slots) würde FT2 mit nur 3 Werten pro Antenne bestrafen und die statistische Power weiter reduzieren.  
- Option c (adaptive Anzahl) ist zu komplex für den Gewinn – wir bräuchten einen Sollwert "mindestens N SNR-Werte", was erst nach der Messung feststellbar ist.

**KISS-Bewertung:**  
Beibehalten ist einfachste Wartung. Keine Änderung nötig.

---

### 4. MIN_MEASURE_STATIONS für FT4/FT2?

**Klarheit:** Klar – die feste Schwelle 5 blockiert bei FT2 oft den Start der Messung. Das ist ein Bug, denn die Messung sollte auch mit 1–2 Stationen starten können (die Auswertung fällt dann auf 50:50 zurück, wenn die Daten nicht ausreichen).

**Empfehlung:**  
Entferne `MIN_MEASURE_STATIONS` ganz oder setze sie modusabhängig auf 1 (FT2), 2 (FT4), 5 (FT8).  
Besser: **Entferne den Guard vollständig**. Die `can_measure`-Abfrage (die aktuell entscheidet, ob die Mess-Phase startet) sollte immer `True` liefern. Die eigentliche Entscheidung über die Brauchbarkeit des Ergebnisses liegt in `_evaluate` (dort `peak <= 1.0` → 50:50).  
- Vorteil: Einfachster Code, keine Fallunterscheidung nach Modus.  
- Nachteil: Bei völlig leeren Bändern (0 Stationen) wird trotzdem gemessen – 6 Slots Verschwendung. Das ist vernachlässigbar.

**KISS-Bewertung:**  
Entfernen der Bedingung ist minimale Änderung (eine Zeile streichen). Deutlich KISS-freundlicher als eine modusabhängige Tabelle.

---

### 5. Pragmatik: Was passiert wenn FT2 30 Min keine 5 Stationen hat?

**Klarheit:** Klar – aktuell wird dann keine Messung gestartet, das System bleibt auf dem letzten Pattern (50:50 oder gespeichertem Wert). Nach 1h Auto-Refresh wird der Versuch wiederholt. Das ist akzeptabel, aber suboptimal, weil nie gemessen wird, wenn das Band dauerhaft schwach besetzt ist.

**Empfehlung:**  
Mit der Streichung von `MIN_MEASURE_STATIONS` (Punkt 4) startet die Messung immer, auch bei 1–2 Stationen. Das System sammelt dann über 24 Slots einige Dutzend SNR-Werte und fällt ggf. auf 50:50 zurück, kann aber bei systematischen Unterschieden auch eine Tendenz erkennen.  
- Keine zusätzliche Fallback-Logik nötig.  
- Das Auto-Refresh nach 1h bleibt bestehen.

**KISS-Bewertung:**  
Keine zusätzliche Änderung – die Lösung aus Punkt 4 erledigt das automatisch.

---

### 6. Mike's Hobby-Use-Case: Lohnt sich FT4/FT2-Optimierung?

**Klarheit:** Klar – Mike nutzt fast nur FT8, FT4/FT2 sind selten. Aus Aufwands-/Nutzensicht wäre es legitim, FT4/FT2 einfach auf 50:50 zu setzen und keine Messung zu machen. Allerdings sind die vorgeschlagenen Änderungen (SNR-basierter Score, Streichen des Guards) so minimal, dass sie auch FT8 verbessern und keine Sonderlogik für FT4/FT2 erfordern.

**Empfehlung:**  
**Keine separate Behandlung** – die allgemeinen Verbesserungen (Score auf SNR, Wegfall der Mindeststationszahl) gelten für alle Modi. FT4/FT2 profitieren passiv, ohne dass spezielle Fallback-Pfade nötig sind. Das ist der KISS-Weg: eine einheitliche, robuste Messlogik für alle Modi.

**KISS-Bewertung:**  
Maximal KISS – wir führen keine modusabhängigen Zweige ein, sondern verbessern den Kernalgorithmus. FT4/FT2 laufen dann einfach mit, erhalten aber keine zusätzliche Komplexität.

---

## Klare Empfehlung für den Refactor-Plan

1. **Score umstellen:** In `record_measurement` den vorhandenen `score` (Summe(snr+30)) statt `station_count` speichern. → Einzeiler-Änderung, kontinuierliche Werte.
2. **`MIN_MEASURE_STATIONS` entfernen:** `can_measure` immer `True` zurückgeben lassen. → Einzeiler-Änderung, Messung startet auch bei wenigen Stationen.
3. **`_MULT` beibehalten:** Keine Änderung an `MEASURE_CYCLES` – mehr Datenpunkte helfen.
4. **`scoring_mode` vereinheitlichen:** Der `dx`-Modus kann entfallen, da der SNR-Score beide Aspekte abdeckt. → Optional, aber empfohlen für Konsistenz.

Diese Änderungen sind minimal (2 Zeilen Core-Code), erfordern keine neuen Strukturen und verbessern die Messstatistik bei FT2/FT4 deutlich, ohne FT8 zu beeinträchtigen. Sie sind voll KISS-konform und lassen sich in den bestehenden Refactor-Plan integrieren.
