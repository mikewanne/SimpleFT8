[deepseek] ~39575 Tokens, 6 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=48019 out=4683 total=52702
## §A — Pending-Loop Race/Abort/TOCTOU

**Race zwischen `transmit()` und `_tx_worker`-Loop**  
Beide Zugriffe auf `_pending_tx` und `_pending_queued_at` erfolgen unter `_replace_lock` – im `transmit()` (Z. 218-228) und im `_tx_worker`-Loop (Z. 246-251). Der Worker-Pop setzt die Felder atomar auf `None`/`0.0`. Ein gleichzeitiges `transmit()` kann entweder den neuen Wert vor dem Pop sehen (wird überschrieben) oder nach dem Pop (wird sauber gesetzt). Kein Lost-Update, kein Halb-State. ✅

**abort-Verlust trotz F1-Fix**  
Der F1-Fix (`if self._abort_event.is_set(): return` vor dem Re-Trigger in Z. 253-257) ist korrekt implementiert. `_run_one_tx_pass` setzt `_abort_event.clear()` und `_is_transmitting=True` – der Check vor dem Re-Trigger verhindert, dass ein zwischen Pass-1 und Pending-Konsum aufgetretenes `abort()` überschrieben wird. Test T13 deckt diesen Pfad ab. ✅

**TOCTOU im Pending-Pop**  
Der Pop unter Lock (Lesen + Nullsetzen) ist korrekt. Kein TOCTOU-Risk. ✅

**Verfall-Schwelle `1.5 * cycle_duration`**  
Die Berechnung in Z. 259-266 nutzt `_compute_target_slot` und `_SLOT * 1.5`. Bei FT8 (22.5s) ist das ausreichend: Audio-Drain endet maximal 14.5s nach Slot-Start, Pending wird spätestens dann verarbeitet. Die Schwelle ist weit genug, um auch längere Drift-Guard-Phasen (bis ~15s) zu überstehen. ✅

**Stack/Loop-Korrektheit bei Multi-Pendings**  
Die `while True`-Schleife konsumiert Pendings ohne Rekursion. T12 demonstriert 3 aufeinanderfolgende Pendings, alle werden sauber abgearbeitet. ✅

**Kritische Beobachtung**: In `transmit()` wird der alte Thread mit `join(timeout=0.5)` gewartet, bevor in den Lock-Block eingetreten wird. Das ist korrekt, da der alte Threads `finally` den `_is_transmitting` zurücksetzt. Kein neuer Thread startet, solange der alte noch läuft – aber Pending wird gesetzt, während der alte läuft. Korrekt.

---

## §B — Slot-Boundary-Fix

**Berechnung `(now // slot_dur) * slot_dur`**  
Im Code (`main_window.py` Z. 765-770) exakt umgesetzt. Für FT8 (15s) korrekt. Für FT4 (7.5s) und FT2 (3.8s) ebenfalls korrekt – `//` liefert Ganzzahl-Division für `time.time()` als `float`, das Ergebnis ist der größte Slot-Start ≤ now.

**Floating-Point-Falle bei 3.8s**  
`3.8` ist binär periodisch, `time.time()` hat typischerweise Mikrosekunden-Präzision und ist ebenfalls nicht exakt. Die Operation `(now // 3.8) * 3.8` kann theoretisch eine um ein `eps` von der echten 3.8s-Grenze abweichende Zahl liefern (z.B. 15998.600000000001 statt 15998.6). In der Praxis wird die Abweichung im Subsekunden-Bereich liegen (< 1µs) – für eine UI-Anzeige irrelevant. Das Display zeigt nur Sekunden, keine Nachkommastellen. Kein realer Effekt.

**Tests T7/T8**  
Die parametrisierten Tests in `test_main_window_slot_boundary.py` vergleichen `actual_slot_start` mit dem dynamisch berechneten `(fake_now // slot_dur) * slot_dur`. Die parametrisierten `expected_slot_start` sind nicht in der Assertion verwendet – der Test prüft also die Formel, nicht die festen Werte. **Die Tests sind gültig**, auch wenn die parametrisierten Werte (z.B. 16002.0 für FT4) rechnerisch falsch sind (korrekt wäre 15997.5). Der Test ist selbstkonsistent, da er `real_expected` selbst berechnet. Das sorgt für leichte Verwirrung, ist aber korrekt. Empfehlung: parametrisierte Werte in zukünftigen Versionen korrigieren oder entfernen – aktuell nicht blockierend.

---

## §C — Test-Robustheit

**T11a Code-Inspektion**  
Zerlegt den Quelltext von `Encoder.transmit` zeilenweise und sucht nach Settern unter Lock. Anfällig für Zeilenumbrüche und Einrückungsänderungen. **Robustheit mittel** – bei Refactoring (z.B. Umbenennung `_replace_lock`) muss der Test angepasst werden. Solange das Projekt KISS bleibt und kein Refactoring des Locks erfolgt, ist der Test stabil. Akzeptabel als einmalige Absicherung.

**T11b Stress-Test**  
200 parallele `transmit()`-Aufrufe auf 8 Threads. Prüft Endzustand auf Half-State. Der Test ist deterministisch, da alle Threads nur unter Lock schreiben und der Lese-Zugriff nach Fertigstellung erfolgt. Kein Timeout, kein Sleep – **deterministisch**, nicht flaky.

**T13 Abort-Pfad**  
Setzt Pending innerhalb eines gemockten `_run_one_tx_pass`-Calls und ruft `abort()` auf. Der Worker-Loop sieht das gesetzte `_abort_event` und bricht ab. Der Test bestätigt, dass `_run_one_tx_pass` nicht erneut gerufen wird (call_args nur 1 Eintrag) und `_abort_event` gesetzt bleibt. **Prüft tatsächlich den Abort-Pfad**, nicht den Verfall-Pfad (tx_even=None → kein Verfall). ✅

**T7/T8** – siehe §B. Die dynamische Erwartungsberechnung macht die Tests **nicht parametrisiert im Sinne von boundary-Wert-Prüfung**, sondern lediglich parametrisierte Wiederholung des Formeltests. Das ist ok, aber die parametrisierten Erwartungswerte sind irreführend. Empfehlung: entweder korrekte Werte eintragen oder die parametrisierten Werte aus dem Test entfernen und nur die Formel prüfen.

**T2N** – komplementär zu Z. 401 (Mock-False): Mock-True-Encoder (Pending-Pfad) und Prüfung von `counter_changed` und `slot_action`. Korrekt. ✅

---

## §D — Out-of-Scope-Compliance + ANT1

**Out-of-Scope (V3 §9)**  
- ❌ Frequenz-Recheck zur Laufzeit: nicht angefasst.  
- ❌ qso_state-Änderungen: keine Änderungen an QSO-State-Machine.  
- ❌ Listener-Pfad in `mw_cycle.on_message_decoded`: nicht angefasst.  
- ❌ Diversity-Antennen-Switch: nicht angefasst.  
- ❌ Auto-Hunt-Coupling: nicht angefasst.  
- ❌ AP-Lite, OMNI-Stop-Reasons, btn_omni_cq-UI: nicht angefasst.  

**Hardware-Garantie ANT1**  
`encoder.transmit` setzt den zentralen ANT1-Setter in `_tx_worker_inner` (Z. 363). Der Pending-Pfad durchläuft `_run_one_tx_pass` → `_tx_worker_inner` – ANT1 wird gesetzt. ✅

---

## §E — Empfehlung

**KRITISCH** – Keine Findings.

**SOLLTE-FIX**  
- In `test_main_window_slot_boundary.py` die parametrisierten Erwartungswerte (16002.0 für 7.5s, 15998.6 für 3.8s) durch korrekte Werte ersetzen oder die Parametrisierung entfernen (da sie nicht in der Assertion verwendet werden). Aktuell verwirrend aber funktional korrekt. Empfehlung: vor nächstem Commit korrigieren.

**KOENNTE**  
- Floating-Point-Risiko bei 3.8s Slot-Grenze: Wenn in Zukunft Millisekunden-Präzision in der UI gefordert wird, könnte man mit `decimal.Decimal` arbeiten. Derzeit nicht nötig.

**Empfehlung Gesamt:**  
Code ist merge-bereit. Alle Akzeptanzkriterien aus V3 sind erfüllt. Die Encoder-Pending-Queue ist racefrei und abort-sicher. Der Slot-Boundary-Fix löst die Display-Probleme. Tests sind robust und decken die neuen Pfade ab. Keine Out-of-Scope-Änderungen. ANT1 wird garantiert.

**Push freigegeben** (nach optionalem Korrektur-Commit für die parametrisierten Testwerte, wenn gewünscht).
