[deepseek] ~14556 Tokens, 3 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=18459 out=2893 total=21352
# Review V2 – Block 2 Kalibrier-Pipeline-Optimierung

## 1. Schwellen-Werte 4 dB / 50 % / 15 %

**Fazit:** Konservativ, aber fachlich begründet – akzeptabel für einen ersten Adaptiv-Stop.

- **4 dB SNR-Differenz**: In der Praxis sind Slot-to-Slot-Schwankungen bei gutem Band 1–2 dB. 4 dB entspricht der doppelten typischen Streuung. WSJT-X-Nutzer erleben ähnliche Werte. Könnte in sehr ruhigen Bedingungen (DX) etwas hoch sein, aber das ist okay – lieber kein Stop als falscher Stop.  
- **50 % Stations-Differenz**: Basierend auf Ihrer Begründung ±20 % Streuung pro Slot → 50 % ist konservativ. Falls ein Slot viele Stationen hat (z. B. 25 vs. 16), wäre Δ=36 %; ohne Stop, dann zwei Runden. Auch okay.  
- **15 % (Phase 3)**: 2× der normalen Schwelle (8 %). Ein ähnliches Verhältnis wie in Phase 2. Allerdings: Bei 8 % entscheidet das System auf 70:30, bei 15 % für Stop ist das konservativ. Ein Feldtest könnte zeigen, dass 12 % auch sicher wäre.

**Empfehlung:** Behalten – mit Monitoring-Log (delta_snr, delta_stations) für spätere Tuning-Möglichkeit.

---

## 2. FT4/FT2-Edge-Case – akzeptabel?

**Ja, akzeptabel.**  
- FT8 macht >99 % der Nutzung aus. Die Optimierung für FT8 ist wirtschaftlich.  
- FT4/FT2-User haben kürzere Slots – die absolute Zeitersparnis durch Adaptiv-Stop wäre ohnehin geringer (z. B. 30 s statt 60 s). Der Aufwand für separate Pattern/Logik lohnt nicht.  
- Die Regel `len(m1)==len(m2)` als Pre-Condition verhindert inkorrekte Stops bei unbalancierten Samples. Das ist KISS und robust.

**Aber:** Dokumentieren Sie das explizit im Code-Kommentar oder in der Doku, damit später kein Entwickler verwirrt ist, warum FT4 nicht profitiert.

---

## 3. Pre-Conditions Adaptiv-Stop – vollständig?

**Phase 2 (4 Bedingungen):**

- `self._step == 4` – korrekt (nach Runde 1, alle 4 Buckets mindestens 1 Wert).  
- Alle 4 Buckets non-empty + non-None – wichtig. Fehlt: auch prüfen, dass `_phase_data[key]` wirklich mindestens einen gültigen SNR-Wert enthält, nicht nur None-Marker? In Ihrem Code werden None-Marker separat gespeichert (`append(None)` bei Overload). Die Bedingung `non-None` ist durch `_has_overload(key) == False` abgedeckt. Gut.  
- Kein Overload – richtig.  
- Mindestens 5 Stationen pro Bucket – verhindert Mess-Streuungs-Falsch-Stop. Das entspricht `MIN_MEASURE_STATIONS`.  

**Fehlt IMO:** Eine Prüfung, dass überhaupt genug Daten für die Top5-Avg vorhanden sind (`len(clean) >= 5`)? In Ihrem `_top5_avg()` wird `sorted(clean, reverse=True)[:5]` berechnet – wenn nur 1 Wert da ist, wird trotzdem ein Average zurückgegeben. Die Pre-Condition `5 Stationen` stellt sicher, dass mindestens 5 SNR-Werte vorliegen. Das ist ausreichend, da jeder Zyklus mehrere Stationen liefern kann (z. B. 15 Stationen in einem Zyklus). Aber hypothetisch: Wenn ein Bucket in Runde 1 genau 5 Stationen hat, ist das okay.  

**Phase 3 (3 Bedingungen):**

- `_measure_step == _early_stop_at` (2/3) – ok.  
- `len(m1) >= 2` und `len(m2) >= 2` – die Implementation setzt `_early_stop_min_per_ant = max(2, self._early_stop_at // 3)`, was für FT8 = 2 ergibt. Richtig.  
- `peak > 1.0` – kopiert aus `_evaluate()`, verhindert Division durch Null.

**Ergänzung:** Fehlt eine `cancel`-Prüfung in Phase 3 analog zu Phase 2? In der Beschreibung steht, `record_measurement` wird nur aufgerufen, wenn nicht gecancelled – aber der Code-Referenz in `core/diversity.py` fehlt die Cancel-Prüfung. Sollte analog: `if self._cancelled: return` (wenn DiversityController ein `_cancelled`-Flag bekäme). Das ist aber vielleicht nicht Teil des aktuellen Designs. Für initialen Commit okay.

---

## 4. Cache-Reuse-Kopplung (R1.4)

**Empfehlung:** Adaptiv-Stop-Ratios **nicht** in PresetStore-Cache sichern.  
- Begründung: Adaptiv-Stop liefert ein Ergebnis mit weniger Messdaten (2/3 der Zyklen). Das Ratio könnte zufällig etwas abweichen – und wenn es über Stunden wiederverwendet wird, summiert sich der Fehler.  
- Sicheres Verhalten: Nur vollständige Messungen (alle 6 Zyklen) in den Cache. Bei Adaptiv-Stop wird das Ratio nur für den aktuellen Betrieb verwendet, aber nicht persistiert.  
- Ein Log-Eintrag (z. B. `[Diversity] Adaptiv-Stop, nicht gecached`) erhöht Transparenz.

**Alternativ:** Wenn Cache-Reuse dennoch gewünscht ist, müsste im PresetStore vermerkt werden, ob die Messung komplett war oder nur ein Early-Stop. Das ist Overhead.

---

## 5. Test-Strategie – 11 neue Tests, reicht das?

**Ja, das reicht für den initialen Commit.**  
- 6 Tests für Phase 2 (Stop-Bedingungen, Nicht-Stop, Overload, Low-Station, Cancel).  
- 5 Tests für Phase 3 (Dominant, Fair, Unbalanced FT4, keine early, full cycles).  
- Zusätzlich vielleicht noch einen Test, der das Zusammenspiel Phase 2 + Phase 3 in einem End-to-End-Szenario prüft? Wäre schön, aber nicht zwingend.  
- Der Test `test_phase2_stop_calls_finish` ist gut (Overprüfung der Seiteneffekte).  

**Fehlt:** Ein Test, der die Dynamik der Schwellenwerte validiert (z. B. 3.9 dB → kein Stop, 4.0 dB → Stop). Das wäre eine Grenzwertbetrachtung. Aber das ist aufwändig und wird durch die `>=`-Logik abgedeckt.

**FT4/FT2-Skalierung** als ein Test mit `monkeypatch` ist ausreichend.

---

## 6. KISS-Bewertung: Properties vs. harte Konstanten

**Properties sind hier okay.**  
- `_early_stop_at` und `_early_stop_min_per_ant` hängen von `MEASURE_CYCLES` ab, das wiederum modusabhängig überschrieben wird (`mw_radio.py` Zeile 798).  
- Harte Konstanten (z. B. `EARLY_STOP_AT_FT8=4`) wären unflexibel und würden bei zukünftigen Modus-Erweiterungen Änderungen an mehreren Stellen erfordern.  
- Die Properties sind einfach (`return int(...)`), keine komplexe Logik. Das ist KISS-konform.  
- Einzige Kritik: `EARLY_STOP_FRACTION = 2/3` als Klassenkonstante ist nicht über alle Modi gleich sinnvoll (FT4/FT2 haben andere Patternstruktur). Da aber ohnehin der Stop nur bei `len(m1)==len(m2)` erfolgt, ist die Fraction für FT4/FT2 fast irrelevant.  

**Fazit:** Behalten.

---

## 7. Reihenfolge atomare Commits

**Vorschlag:**  
1. **C1** – `ROUNDS=3 → 2` (sofortige +60 s Ersparnis, keine Abhängigkeiten)  
2. **C2** – Tests für Phase 2 (Test-First, kann parallel entwickelt werden)  
3. **C3** – Implementierung Phase 2 Adaptiv-Stop  
4. **C4** – Tests für Phase 3 (Test-First)  
5. **C5** – Implementierung Phase 3 Adaptiv-Stop  
6. **C6** – APP_VERSION + Doku-Updates (unabhängig von Tests)  

**Alternative:** C4 und C5 tauschen – wenn C5 implementiert ist, kann man C4-Tests vielleicht besser auf die echte API abstimmen. Aber Test-First ist sauberer.  

**Empfehlung:** C1 → C2 → C3 → C4 → C5 → C6. So bleibt jeder Commit klein und revertierbar.

---

## 8. Sonstiges – was fehlt?

- **Cancel-Behandlung in Phase 3:** Wie in Punkt 3 angemerkt – die `record_measurement` Methode in `core/diversity.py` hat kein `_cancelled`-Flag. Falls der Dialog abgebrochen wird, wird Phase 3 einfach weiterlaufen, bis die Messung fertig ist? Das ist vielleicht gewünscht, aber der Adaptiv-Stop sollte dann nicht triggern. In der Beschreibung von Phase 2 steht `if self._cancelled: return`, für Phase 3 fehlt das. Bitte entweder auch ein Cancel-Flag in DiversityController einbauen oder zumindest dokumentieren, dass Phase 3 nach Cancel nicht unterbrochen wird.  
- **Overload-Marker in Phase 2:** Die `_has_overload(key)` Prüfung in den Pre-Conditions ist korrekt. Aber in `_finish()` wird in Phase 2 `_has_overload(key)` benutzt, um einen Bucket auszuschließen. Falls alle 4 Buckets Overload haben, würde `_finish()` abstürzen? In `_finish()` wird `continue` bei Overload, danach `best_score = None`. Nach der Schleife wird `ant1_avg` als None bleiben → dann `best_ant` basiert auf `None >= None`. Sollte abgesichert werden. Aber das existiert schon in V1. Für Adaptiv-Stop kein neues Problem.  
- **Logging:** Die Print-Logs für Adaptiv-Stop sind hilfreich. Bitte die Logs mit Timestamp versehen, damit sie im line-basierten Debugging einordenbar sind.  
- **Edge-Case Phase 2 Stop nach Cancel:** Wenn der Benutzer genau im Moment des Stop-Checks auf Cancel klickt, könnte eine Race-Condition auftreten. In Qt ist `feed_cycle` thread-safe? Wenn `feed_cycle` im Hauptthread läuft und der Cancel-Button ebenfalls im Hauptthread, ist es synchron. Also kein Problem.  

**Insgesamt:** Eine solide, durchdachte V2. Die Review-Punkte sind adressiert. Meine Empfehlung: **Go für die Umsetzung**, mit kleinen Nachbesserungen (Phase 3 Cancel, Dokumentation FT4/FT2, optional Grenzwert-Tests später).
