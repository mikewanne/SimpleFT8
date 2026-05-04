[deepseek] ~37416 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=42986 out=6562 total=49548
**Review des finalen V3-Plans — Zusammenfassung**

Der Plan ist **vollständig, atomar und migrations-sicher**. Die Reihenfolge der Commits ist sinnvoll, die Test-Strategie ausreichend. Keine neuen Features oder Architekturänderungen werden eingeführt. 

---

## 1. Plan-Vollständigkeit

- **Commit 1 (PresetStore):** Alle benötigten API-Änderungen (`is_valid_gain`, `is_valid_ratio`, `save_gain`/`save_ratio` mit separaten Timestamps, Migration in `_load`) sind dokumentiert. Die angehängte `preset_store.py` enthält noch die alte Struktur – die geplanten Änderungen sind klar.
- **Commit 2 (Score + MIN_STATIONS):** `diversity.py` enthält alle betroffenen Zeilen (Z.29, 78-80, 402-407, 436, 503). Die Umstellung von `dx_weak_count`/`station_count` auf `score` ist korrekt beschrieben.
- **Commit 3 (CQ-Lock):** `should_remeasure` wird um `cq_active` erweitert, Logik auf Zeitbasis. Die Aufrufstelle in `mw_cycle.py` (Z.564) und die Ableitung von `cq_active` via `qso_sm.cq_mode` sind angegeben.
- **Commit 4 (Cache-Reuse):** Der Pfad in `_on_band_changed` vor `on_band_change()` wird umfassend beschrieben. Der Toast ist als separate Datei skizziert. Wichtig: der Plan sagt, dass `on_band_change()` **nicht** aufgerufen werden soll, wenn Cache gültig – das ist konsistent mit der gewünschten Überspringung von Phase 3.
- **Commit 5 (OPERATE_CYCLES entfernen):** Alle Dateien und ungefähren Zeilen gelistet. Offene Frage zur Reihenfolge (separat oder in 4) wird unten bewertet.
- **Commit 6 (Tests + Doku):** Ausreichend.

**Keine Lücken festgestellt.**

---

## 2. Reihenfolge der Commits – atomar und brüchig?

1. **Commit 1** – kein Verhaltensänderung, sicher.
2. **Commit 2** – unabhängig.
3. **Commit 3** – führt `_last_measured_at` ein, `OPERATE_CYCLES` bleibt für UI.
4. **Commit 4** – baut auf Commit 1 (`is_valid_ratio`) und Commit 3 (`_last_measured_at`) auf.
5. **Commit 5** – räumt `OPERATE_CYCLES` auf, nachdem alle Logik auf Zeitbasis läuft.
6. **Commit 6** – final.

**Atomar-Brüche:** Keine. Zwischen Commit 3 und 4 gibt es minimale Abhängigkeiten, aber keinen Bruch. 

**Empfehlung zur offenen Frage:** Commit 5 **sollte nach 4** kommen, nicht davor. Wenn man 5 vor 4 macht, müsste man in 4 bereits die zeitbasierte UI-Anzeige implementieren, was unangenehm ist. Die geplante Reihenfolge 3→4→5 ist daher optimal.

---

## 3. Migration-Strategie – tragfähig?

- Alte JSON-Einträge mit `timestamp` werden in `_load()` erkannt und beide neuen Felder (`gain_timestamp`, `ratio_timestamp`) auf den alten Wert gesetzt.
- `save_gain` schreibt nur `gain_timestamp`, `save_ratio` nur `ratio_timestamp`. Das alte `timestamp` bleibt erhalten, wird aber nicht mehr aktualisiert – backwärtskompatibel.
- Neue Caches haben korrekte Felder.
- **Einzige Anmerkung:** In `save_ratio` muss explizit `ratio_timestamp = time.time()` gesetzt werden – der Plan sagt das, die aktuelle Implementierung tut es noch nicht. Wird im Commit 1 ergänzt.

**Strategie vollkommen tragfähig.**

---

## 4. Test-Strategie – ausreichend?

Geplant: ~15–20 neue Tests, 4–5 angepasste Tests. Die Liste deckt alle geänderten Aspekte ab:

- Neuer PresetStore: Migration, getrennte Validity, getrennte Save.
- Score-basierte Messung + MIN_STATIONS entfernt.
- `should_remeasure` mit CQ-Lock und 1h-Frist.
- Cache-Reuse beim Bandwechsel.
- Entfernen von Settings-Optionen.

**Fehlende Tests?** 
- Ein **Integrationstest** für den Fall „Bandwechsel mit gültigem Cache → Phase 3 wird übersprungen + Toast erscheint“ ist als `test_band_change_with_valid_cache_skips_phase3` geplant – das ist ein guter Integrationstest.
- **Toast-Test** könnte schwierig sein (UI), aber nicht kritisch.
- **Edge-Case `_last_measured_at` initial None** (siehe Punkt 5) wird nicht explizit getestet – könnte aber implizit durch `test_should_remeasure_after_1h_triggers` abgedeckt sein, wenn `_last_measured_at` erst nach erstem Evaluate gesetzt wird.

**Insgesamt ausreichend.** Keine weiteren Tests notwendig.

---

## 5. Edge-Cases – V1/V2/R1 bereits abgedeckt?

Die im Plan genannten 6 Edge-Cases (App-Start, Cache 55 Min, Bandpilot, Auto-Hunt, Adaptiv-Stop-Cache, NaN/Inf) sind alle relevant und korrekt bewertet.

**Ein bisher nicht explizit erwähnter Edge-Case:**  
**`_last_measured_at` könnte `None` sein, wenn `should_remeasure` vor dem ersten `_evaluate` aufgerufen wird.**  
Analyse:  
- Nach `reset()` ist `_last_measured_at` nicht gesetzt.  
- `should_remeasure` wird nur in `_on_cycle_start` aufgerufen, wenn `self._diversity_ctrl.phase == "operate"`.  
- Phase wird erst nach `_evaluate` auf "operate" gesetzt.  
- `_evaluate` setzt `_last_measured_at` (laut Plan).  
- Also ist `_last_measured_at` beim ersten relevanten Aufruf immer gesetzt.  

**Fazit: Kein Problem.** Dennoch könnte man defensiv in `should_remeasure` prüfen (`if self._last_measured_at is None: return True`). Das ist aber nicht zwingend nötig – der Plan kann so bleiben.

---

## 6. KISS-Check – kann etwas weggelassen werden?

- `scoring_mode`-API bleibt – **KISS**, keine Entfernung nötig.
- Cache-Reuse ohne Toast? Toast ist Teil der Anforderung (Mike’s Vision). Nicht entfernbar.
- Migration altes `timestamp` gleichzeitig aufbewahren und nicht löschen – **KISS** (backwärtskompatibel, keine Bereinigung nötig).

**Kein entbehrlicher Eintrag identifiziert.**

---

## 7. Empfehlung

Der Plan ist **bereit für Plan-Mode + Code-Implementierung**.  
Es sind keine V4-Iterationen nötig.

**Einziger optionaler Hinweis:**  
Füge in `should_remeasure` eine defensive Prüfung für `None` ein – `if self._last_measured_at is None: return True`.  
Dieser Hinweis ist nicht blockierend, erhöht aber die Robustheit bei unerwarteten Initialisierungsreihenfolgen.

---

**Fazit:** Plan freigegeben zur Umsetzung.
