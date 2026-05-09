[deepseek] ~54355 Tokens, 7 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=62552 out=5749 total=68301
# R1-Review: V2 Self-Review des OMNI-Redesigns

## Überblick

Der Prompt `P2.OMNI-REDESIGN — V2` ist ein detailliertes Self-Review der V1-Spezifikation mit 15 Lessons Learned. Kernproblem: Ein `DirectConnection`-Race in `_send_cq()` führt dazu, dass der QSO-State trotz OMNI-RX-Filter auf `CQ_CALLING` gesetzt wird – der CQ-Loop stirbt. V2 schlägt eine Flag-basierte Lösung vor (`_omni_skip_state_change`), präzisiert das OMNI-Pause/Resume-Lifecycle und erweitert Tests.

**Gesamteindruck: Sehr gründlich, aber einige kritische offene Punkte.**

---

## 1. L1 Race-Lösung: Variante B (Flag-Pattern) – Race-frei?

**Bewertung: ✅ Race-frei, aber mit 2 Feinheiten**

### Analyse
- `_omni_skip_state_change` wird **vor** `send_message.emit()` auf `False` gesetzt.
- `emit()` läuft synchron (Qt.DirectConnection im GUI-Thread).
- Der Listener (`_on_send_message`) setzt das Flag auf `True` **während des Emits**.
- Nach Rückkehr von `emit()` wird `if not self._omni_skip_state_change` ausgewertet.

**Race-Bedingungen ausgeschlossen:**
- Keine Nebenläufigkeit – alles im selben Thread.
- Keine Interrupts oder Preemption zwischen den Zeilen (CPython GIL im GUI-Thread).
- `_omni_skip_state_change` ist nur über diesen Pfad änderbar (kein anderer Setter).

**ABER: Edge-Case bei Reentranz?**
- Wenn `send_message.emit` synchron weitere `_send_cq`-Aufrufe triggern würde (z.B. durch indirekten Signal-Slot), könnte das Flag verschmiert werden.
- **Prüfung:** Gibt es einen Pfad, bei dem `_send_cq()` rekursiv aufgerufen wird?
  - `_on_send_message` → ... → `qso_sm.start_cq()` → `_send_cq()`?
  - Aktueller Code zeigt: `_on_send_message` ruft nur `encoder.transmit()` auf, was nicht über `_send_cq` zurückführt.
  - `_process_cq_reply` könnte in `_send_cq` aufgerufen werden? → Nein, das ist der `if pending_reply`-Zweig, der vor dem Flag-Set returniert.
- **Fazit:** Keine Reentranz.

**Empfehlung:**  
- Expliziten Kommentar im Code hinterlassen: "Flag wird nur im GUI-Thread gesetzt/gelesen – kein Lock nötig."
- Test schreiben, der zwei aufeinanderfolgende `_send_cq`-Aufrufe simuliert und prüft, dass `_omni_skip_state_change` nach dem zweiten Aufruf wieder `False` ist (AC13 ist schon vorgesehen – gut).

---

## 2. L3/L6/L11 Pause/Resume-Vollständigkeit – Alle QSO-Entry/Exit-Pfade abgedeckt?

**Bewertung: ⚠️ Ein Pfad fehlt: `_on_try_replace_pending_tx` (P1.9-Ersatz)**

### Abdeckungsmatrix

| Entry-Pfad | Pause? | Resume am Ende? |
|---|---|---|
| `_on_station_clicked` (Hunt) | ✅ `_omni_tx.pause()` + Flag | ✅ (via qso_complete/confirmed/timeout) |
| `_on_tx_slot_for_partner` (CQ-Reply) | ✅ laut L6-Ergänzung | ✅ (gleiche End-Pfade) |
| `_on_try_replace_pending_tx` (P1.9 Replace) | ❌ **FEHLT** | ❌? |

**Detaillierte Analyse `_on_try_replace_pending_tx` (mw_qso.py):**
- Dieser Slot wird aufgerufen, wenn während `CQ_CALLING` eine Antwort eintrifft und der Encoder die TX-Message ersetzen kann.
- Der Code setzt `qso_sm._set_state(TX_REPORT)` und startet ein QSO.
- **Es wird NICHT `_omni_tx.pause()` aufgerufen!**  
- Folge: OMNI bleibt aktiv, aber der QSO-Start ändert `_pending_switch` nicht.  
- **Ende des QSOs:** `_on_qso_complete` etc. prüfen `_omni_was_active_pre_qso` – das ist aber nicht gesetzt, weil `pause()` nie aufgerufen wurde.  
- Also wird nach QSO-Ende **kein Resume** ausgelöst → OMNI bleibt aktiv, aber `_was_active_pre_qso = False`. Das ist konsistent (kein flapping), aber der QSO wurde ohne Pause gestartet – OMNI könnte während des QSOs weitermachen?

**Check:**  
- In `_on_send_message` für CQ wird das OMNI-Filter angewandt.  
- Während des QSOs werden Reports gesendet, die nicht mit `CQ ` beginnen – OMNI-Filter greift nicht.  
- Aber `_omni_tx.advance()` läuft weiter in `_on_cycle_start`, weil `qso_active=True` den Zähler pausiert, aber `_slot_index` wird inkrementiert.  
- Das ist harmlos, solange kein neues CQ gesendet wird.  
- **Problem:** Wenn `_resume_cq_if_needed` nach QSO-Ende aufgerufen wird (Queue leer), sendet es `_send_cq()` → OMNI-TX ist noch aktiv → Slot-Filter entscheidet, ob gesendet wird. Das funktioniert korrekt, weil `_omni_tx.active` noch `True` ist.  
- **Gefahr:** Wenn während des QSOs ein anderer Pfad `_omni_tx.pause()` aufruft, würde `_omni_was_active_pre_qso` nicht gesetzt sein und das Flag nicht korrekt arbeiten.

**Empfehlung:**  
- In `_on_try_replace_pending_tx` analog zu den anderen Entry-Pfaden:
  ```python
  if self._omni_tx.active:
      self._omni_tx.pause()
      self._omni_was_active_pre_qso = True
  ```
- Alle 4 Entry-Pfade sollten identische Pause-Logik haben. Vorschlag: Extrahiere eine Hilfsmethode `_pause_omni_if_active()`.

---

## 3. L8 Single Source of Truth: `encoder.tx_even` – wirklich nur eine Stelle gesetzt?

**Bewertung: ✅ Ja, aber die Logik sollte zentralisiert werden**

### Setter-Stellen für `encoder.tx_even`:

1. **`_on_send_message`** (CQ-Pfad):  
   ```python
   if target_even is not None: self.encoder.tx_even = target_even
   ```
   Nur wenn OMNI aktiv und TX-Slot – korrekt.

2. **`_on_station_clicked`** (Hunt):  
   ```python
   their_even = getattr(msg, '_tx_even', None)
   if their_even is not None: self.encoder.tx_even = not their_even
   ```

3. **`_on_tx_slot_for_partner`** (CQ-Reply):  
   ```python
   if their_even is not None: self.encoder.tx_even = not their_even
   ```

4. **`_on_try_replace_pending_tx`** (P1.9 Replace):  
   ```python
   if their_even is not None: self.encoder.tx_even = not their_even
   ```

5. **`_run_auto_hunt`** (Auto-Hunt):  
   ```python
   if _candidate.tx_even is not None: self.encoder.tx_even = not _candidate.tx_even
   ```

**Analyse:**
- Jeder Setter setzt `encoder.tx_even` basierend auf der Parity der Gegenstation.
- **Keine Stelle überschreibt die andere unerwartet**, weil sie in unterschiedlichen Kontexten aufgerufen werden (CQ, Hunt, Reply).
- ABER: Es gibt keinen Schutz vor gleichzeitigen Setzern – das ist aber nicht nötig, weil alles synchron im GUI-Thread läuft.
- **Einziges Problem:** Wenn `_on_send_message` den OMNI-CQ-Pfad nimmt, setzt es ggf. `target_even` und überschreibt damit einen zuvor gesetzten Wert (z.B. von einem vorherigen Hunt). Das ist korrekt, weil der CQ immer eine neue Ziel-Parität wählt.

**Fazit:** Single Source of Truth ist gewahrt (nur Listener setzt `tx_even` für CQ), die anderen Pfade setzen es ebenfalls – aber das ist Design-bedingt und nicht überlappend.

**Empfehlung:**  
- Kommentar in `encoder.py` hinzufügen: "`tx_even` wird vor jedem TX gesetzt, letzter Setter gewinnt – das ist beabsichtigt."

---

## 4. L13 timing-API: Existiert `is_even_cycle()`?

**Bewertung: ✅ Existiert, aber Dokumentation ist ungenau**

### Code-Verifikation aus `core/timing.py`:
```python
def is_even_cycle(self) -> bool:
    return self.current_cycle_number() % 2 == 0
```

Rückgabewert: `True` wenn aktueller Zyklus gerade (even), `False` wenn ungerade (odd).  
**Bedeutung:** Der aktuelle Slot, den wir gerade hören/senden würden – nicht der nächste.

### V2-Nutzung:
- In `_on_cq_clicked`: `self.encoder.tx_even = not self.timer.is_even_cycle()` → gewünscht: nächster Slot im Gegentakt. Das ist korrekt: wenn aktuell even ist, wollen wir odd senden.
- In `_on_omni_stopped` Resume: `next_is_even = not self.timer.is_even_cycle()` – hier gewünscht: nächster Slot, der für OMNI-Start verwendet wird. **Aber:** Das Resume kann zu einem beliebigen Zeitpunkt aufgerufen werden, nicht nur am Slot-Boundary. Dadurch wird `not is_even_cycle()` verwendet, was dem "nächsten Slot" entspricht – korrekt, weil `start_with_parity_for_next_slot` dann die Parity verwendet.

**Risiko:**  
- Wenn `resume()` zwischen zwei Slots aufgerufen wird (genau am Boundary), könnte `is_even_cycle()` den alten oder neuen Slot liefern. Das wurde in L4 bereits als akzeptabel eingestuft (kein Special-Case nötig).  
- Der Encoder in `_next_slot_boundary()` verwendet `is_even == want_even and cycle_pos < 0.5` – das garantiert, dass bei Boundary der korrekte Slot gewählt wird (aktueller Slot passend, wenn < 0.5s vergangen).

**Fazit:** Methode existiert und wird korrekt verwendet. Dokumentation in `core/timing.py` könnte explizit sagen: "Liefert Parität des aktuellen Zyklus (nicht des nächsten)".

---

## 5. AC11/AC14 Bug-Beweis: Ist der Test aussagekräftig?

**Bewertung: ⚠️ AC14 ist unvollständig – benötigt Mock-Encoder**

### AC14: "State-Beweis bei OMNI-RX-Slot: nach `_send_cq()` ist `qso_sm.state == CQ_WAIT` (oder vor-Wert), nicht `CQ_CALLING`."

**Testidee aus V2:**
```python
def test_send_cq_with_omni_rx_slot_no_state_change():
    # OMNI aktiv, RX-Slot → should_tx() = False → Flag set → state bleibt
```

**Problem:** Der Test muss sicherstellen, dass `_on_send_message` (der Listener) den Flag setzt. Das erfordert:
- `omni_tx.should_tx()` liefert `(False, None)`.
- Ein realer `Encoder` würde versuchen zu senden – aber der Test soll TX vermeiden.
- Möglicherweise muss `send_message.emit` gemockt werden, damit der Listener aufgerufen wird, aber kein echter TX erfolgt.

**Vorschlag:**
```python
def test_send_cq_with_omni_rx_slot_no_state_change(qso_sm, omni_tx, mocker):
    # Arrange
    omni_tx.active = True
    mocker.patch.object(omni_tx, 'should_tx', return_value=(False, None))
    # Act
    qso_sm._send_cq()
    # Assert
    assert qso_sm.state != QSOState.CQ_CALLING
    assert qso_sm.state in (QSOState.CQ_WAIT, QSOState.IDLE)  # je nach Vorgänger
```

**Fehleranfälligkeit:** Der Test hängt von der korrekten Implementierung des Listener-Mocks ab. Ohne Mock würde `send_message.emit` den echten `_on_send_message` aufrufen, der wiederum `should_tx` aufruft – das ist im Test ohne GUI nicht vorhanden. **AC14 ist nur aussagekräftig, wenn die Signal-Listener-Kette simuliert wird.**

**Empfehlung:**  
- Test als Integrationstest mit vollständiger `qso_sm` und gemocktem `omni_tx` sowie gemocktem `Encoder` schreiben.
- Klarstellen, dass AC14 in Unit-Tests ohne GUI nicht direkt testbar ist – ggf. als Integrationstest kennzeichnen.

---

## 6. `_resume_cq_if_needed` + OMNI: Doppel-CQ nach Resume?

**Bewertung: ⚠️ Problem erkannt, aber V2-Lösung unvollständig**

### Analyse
Nach QSO-Ende (Queue leer) wird `_resume_cq_if_needed` aufgerufen, das `cq_mode = True` setzt und `_send_cq()` aufruft. Daneben wird in `mw_qso._on_qso_complete` etc. `_omni_tx.start_with_parity_for_next_slot(...)` aufgerufen, das OMNI wieder aktiviert.

**Ablauf (theoretisch):**
1. QSO endet → `_resume_cq_if_needed()` → `_send_cq()` → `send_message.emit("CQ ...")` → Listener (`_on_send_message`) prüft OMNI und sendet ggf. nicht.
2. Danach (im selben Slot) wird `start_with_parity_for_next_slot()` aufgerufen → OMNI aktiviert.

**Problem:**
- `_send_cq()` in Schritt 1 kann den State auf `CQ_CALLING` setzen (wenn kein OMNI oder TX-Slot). Danach wird OMNI resumed – der State bleibt `CQ_CALLING`. Das ist korrekt.
- **Aber:** Was wenn `_resume_cq_if_needed()` in `qso_state.py` aufgerufen wird, **bevor** `mw_qso` das Resume macht? Das ist der Fall bei `_on_qso_timeout` (qso_state ruft `_resume_cq_if_needed` direkt auf, BEVOR mw_qso das Signal verarbeitet).

**Timing:**
- `qso_state.on_cycle_end()` → `_resume_cq_if_needed()` → `_send_cq()`
- Einige Zeilen später: `mw_qso._on_qso_timeout` (via Signal) → `_omni_tx.start_with_parity_for_next_slot()`

**Bedeutung:**  
In der ersten Zeile wird `_send_cq()` aufgerufen, aber OMNI ist noch nicht resumed. Daher läuft der CQ normal (ohne OMNI-Filter). Erst danach wird OMNI resumed → der nächste CQ (im übernächsten Slot) wird dann gefiltert.

**Effekt:** Ein einzelner CQ ohne OMNI-Filter wird gesendet – das ist in Ordnung, da OMNI ja resumed wird und danach greift.

**Empfohlene Maßnahme:**  
- In `_on_qso_timeout/complete/confirmed` das Resume **vor** `_resume_cq_if_needed` platzieren? Geht nicht, weil `_resume_cq_if_needed` in `qso_state` aufgerufen wird, bevor mw_qso den Slot bekommt.  
- **Lösung:** `_resume_cq_if_needed` sollte das OMNI-Resume kennen? Nein, das würde die Trennung verletzen.  
- **Akzeptabel:** Der eine Slot ohne Filter ist tolerierbar. Aber Dokumentieren.

**Fazit:** Kein Doppel-CQ, aber ein ungefilterter CQ nach Resume. Das ist hinnehmbar.

---

## 7. Encoder-Thread-Safety: `_omni_skip_state_change` ohne Lock?

**Bewertung: ✅ Kein Lock nötig**

- `_omni_skip_state_change` wird nur im GUI-Thread gesetzt und gelesen.
- Der einzige Pfad, der es setzt, ist `_on_send_message` (Listener, im GUI-Thread).
- Der einzige Pfad, der es liest, ist `_send_cq()` (im GUI-Thread).
- Threading-Modell: `send_message.emit()` ist synchron, der Listener läuft im selben Thread wie `_send_cq`.
- Kein anderer Thread greift auf `qso_sm._omni_skip_state_change` zu.

**Fazit:** Sicher. Sollte trotzdem dokumentiert werden (siehe L1).

---

## 8. Test für DirectConnection-Verhalten: Wie testen, dass `emit()` synchron läuft?

**Bewertung: ✅ Indirekt testbar, aber nicht explizit nötig**

### Warum es schwer ist:
- `Qt.DirectConnection` vs `Qt.QueuedConnection` ist ein Qt-internes Detail.
- In einem Test ohne Event-Loop kann `emit` synchron sein (weil kein Thread-Wechsel stattfindet). Mit Event-Loop könnte AutoConnection queued sein, wenn Sender und Empfänger in verschiedenen Threads sind.
- Wir können nicht direkt prüfen, ob `emit` blockiert oder nicht.

### Indirekter Test:
- **AC14** prüft bereits das gewünschte Verhalten: Nach `_send_cq()` ist State NICHT `CQ_CALLING`, wenn OMNI RX-Slot.
- Dieser Test beweist, dass der Listener während des Emits den Flag setzt und dass der Flag nach dem Emit noch gelesen werden kann. Das funktioniert nur bei synchroner Ausführung.
- **Wenn emit asynchron wäre (QueuedConnection),** würde der Listener später laufen, der Flag wäre nach Rückkehr von emit noch `False` → State würde auf `CQ_CALLING` gesetzt → Bug reproduziert. Der Test würde dann fehlschlagen und uns zeigen, dass die Annahme falsch war.

**Fazit:** Der Test für AC14 fungiert implizit als Test für DirectConnection. Ein spezieller Test ist nicht nötig.

---

## Weitere Beobachtungen

### L10: `calls_made -= 1` entfernt – korrekt?
- V2 sagt: "RAUS. Defense-in-Depth gilt nicht für nicht mehr benötigte Logik."
- **Zustimmung:** Das war ein Pflaster für den nun gefixten Loop-Bug. Es zu entfernen macht den Code sauberer und deckt Regressionen schneller auf.

### L12: Singleton `block_cycles` Inkonsistenz
- V2 sagt: Aufrufer von `get_instance(block_cycles=40)` prüfen – aber in `main_window.py` steht `_block_cycles = 80`. Der Aufruf in `_init_optional_features` verwendet `get_instance(block_cycles=_block_cycles)`.  
- **Problem:** Der Singleton wurde beim ersten Aufruf von `get_instance(block_cycles=40)` (falls woanders) mit 40 initialisiert, später wird mit 80 aufgerufen, aber das wird ignoriert.  
- **Lösung:** `block_cycles` aus dem Konstruktor entfernen und fest auf 80 setzen (Plan v3.2 Default). Den Parameter in `get_instance` deprecaten.

### L15: Fehlende Tests für Caller-Queue + OMNI-Pause
- V2 führt 3 Tests ein (`test_omni_pause_on_cq_reply`, `test_omni_resume_after_qso_with_caller_queue`, `test_omni_resume_after_qso_empty_queue`).  
- **Bewertung:** Notwendig, aber die Tests müssen die korrekte Interaktion zwischen `qso_state._caller_queue` und `mw_qso._omni_was_active_pre_qso` abdecken.  
- **Risiko:** `_caller_queue` ist in `qso_state.py` definiert, `_omni_was_active_pre_qso` in `main_window.py`. Ein reiner qso_state-Test kann OMNI-Resume nicht prüfen – dazu braucht es Integrationstests.

---

## Fazit

| Kriterium | Status |
|---|---|
| L1 Race-Lösung | ✅ Robust, aber Reentranz dokumentieren |
| L2 `enable()` vs `start_with_parity_for_next_slot` | ✅ Korrekt |
| L3 Pause/Resume-Vollständigkeit | ⚠️ `_on_try_replace_pending_tx` fehlt |
| L4 Slot-Boundary Edge-Case | ✅ Akzeptabel |
| L5 Alle Wege konkret | ✅ |
| L6 Caller-Queue + OMNI | ✅ Dokumentiert |
| L7 Auto-Hunt-Konflikt | ✅ Kein Race |
| L8 Single Source of Truth `tx_even` | ✅ |
| L9 Block-Switch-Test | ✅ Arithmetisch prüfbar |
| L10 `calls_made -= 1` entfernt | ✅ Korrekt |
| L11 `_resume_cq_if_needed` + OMNI | ⚠️ Timing-Problem dokumentiert, aber akzeptabel |
| L12 Singleton `block_cycles` | ⚠️ Parameter ignorieren oder entfernen |
| L13 `is_even_cycle` | ✅ Existiert, Nutzung korrekt |
| L14 Reentrancy Toggle | ✅ Kein Problem |
| L15 Tests für Caller-Queue | ✅ Notwendig, aber Integrationstests nötig |

**Gesamturteil:** Der V2-Entwurf ist solide, aber es gibt zwei kritische offene Punkte:

1. **`_on_try_replace_pending_tx` fehlt die OMNI-Pause** – muss ergänzt werden.
2. **Timing von `_resume_cq_if_needed` vor OMNI-Resume** – führt zu einem ungefilterten CQ nach QSO-Ende, sollte dokumentiert werden, ob gewollt.

**Empfehlung:**  
- Korrektur von Punkt 1 vor V3.  
- Für Punkt 2: Entscheiden, ob man den einen ungefilterten CQ akzeptiert oder ob man `_resume_cq_if_needed` in `qso_state` zeitlich nach dem OMNI-Resume verschiebt (schwierig wegen Trennung).  
- Die Tests in L15 sollten als Integrationstests mit allen beteiligten Komponenten (`qso_sm`, `omni_tx`, gemockter `encoder`, gemocktes `main_window`) ausgeführt werden.

**Insgesamt:** Gute Arbeit, die Analyse ist tiefgehend. Die vorgeschlagenen Code-Änderungen adressieren das Kernproblem korrekt. Mit den obigen Korrekturen ist der Entwurf bereit für V3.
