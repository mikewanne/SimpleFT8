[deepseek] ~47925 Tokens, 7 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=57666 out=5193 total=62859
## DeepSeek-R1 Review: P2.OMNI-PATTERN-FIX V2 Self-Review

**Gelesen:** 2026-05-09, alle angehängten Files (encoder.py, qso_state.py, omni_tx.py, mw_cycle.py, mw_qso.py, timing.py, p2_omni_redesign_v3.md).  
**Fokus:** Offene Fragen aus §2, Bewertung L1-L17, Varianten-Entscheidung, Test-Strategie.

---

### 0. Zusammenfassung der Analyse

- **Problem bestätigt:** Encoder-Drift >0.3s nach Normal-CQ aus `on_cycle_end` bei OMNI wegen Slot-Vorlauf-Konflikt (V1 Wurzel korrekt).  
- **Ursache:** `_tx_worker_inner` berechnet `next_boundary` via `_next_slot_boundary()`, das bei `tx_even` fix auf einen Slot 2×Slot-Duration in der Zukunft zeigt. Im Sleep-Pfad (`sleep_dur > 0.001`) wartet der Worker dann auf `next_boundary + TARGET_TX_OFFSET - 0.5`. Wenn die `sleep_dur` negativ wird (cycle_pos > 13.7s bei FT8), fällt er in den `silence_secs`-Pfad mit `overshoot > 0.3s` → Drift.  
- **Pretrigger-Ansatz (Option E) ist die richtige Richtung:** TX-Planung für nächsten Slot vor Slot-Ende, bevor der Encoder überhaupt schlafen muss.

---

### 1. Bewertung L1–L17

| Lesson | Status | Kommentar |
|--------|--------|-----------|
| **L1** | ✅ korrekt, kritisch | Sleep-Pfad-Berechnung exakt nachvollzogen. Schwelle cycle_pos < 13.7s ist KONSERVATIV richtig. |
| **L2** | ✅ korrekt | `_omni_pretriggered` Flag ist zwingend. |
| **L3** | ✅ korrekt | Normal-CQ bleibt unberührt. |
| **L4** | ✅ korrekt | Toggle-Pfad braucht keinen Pretrigger. |
| **L5** | ✅ korrekt | Tabelle mit Werten stimmt, KISS-Konstante `dur - 1.3` ist gut. |
| **L6** | ✅ korrekt | Race mit `on_cycle_end` ist real. Lösung via `_omni_active_callback` oder `_was_pretriggered` Flag ist sauber. Bevorzuge Flag in qso_sm (KISS). |
| **L7** | ✅ anerkannt | Mode-Wechsel ist seltener Edge-Case. Encoder.abort() reicht. |
| **L8** | ✅ korrekt | `is_transmitting` Schutz ist vorhanden. |
| **L9** | ✅ korrekt | Pretrigger _send_cq bei TX-Slot, bei RX-Slot nur Flag. |
| **L10** | ✅ korrekt | `_pending_reply`-Check muss bleiben, Pretrigger checkt `should_tx` vor _send_cq. |
| **L11** | ✅ anerkannt | Auto-Hunt mutually exklusive. |
| **L12** | ✅ korrekt | P1.9 Replace funktioniert weiter. |
| **L13** | ✅ korrekt | Zeitlicher Ablauf nach erstem TX: is_transmitting wird vor Pretrigger-Schwelle false. |
| **L14** | ⚠️ **nicht korrekt** (siehe unten) | Beschreibung des Pattern-Ablaufs für Block 1 ist korrekt, aber das **grundlegende Problem L17** wird nicht gelöst. |
| **L15** | ✅ korrekt | `peek_next` Methode sauber definiert. |
| **L16** | ✅ korrekt | Pause/Inactive Schutz. |
| **L17** | **Kritisch, neu entdeckt – siehe §2** | **Pretrigger vs. aktiver TX-Thread: `is_transmitting=True` → transmit() skipt → nächster TX fällt aus.** |

**Fazit L1–L17:** Bis auf L14/L17 (das eigentliche Race) sind alle Punkte korrekt analysiert. L17 ist der **showstopper**.

---

### 2. Offene Fragen aus V2 Self-Review §2

#### 2.1 Ist Mid-Cycle-Pretrigger (Option E) der richtige Pfad?

**Ja, aber nur unter einer Bedingung:** Das Race L17 muss gelöst werden. Der Pretrigger ist rein konzeptionell korrekt (plant TX für nächsten Slot, ohne den Encoder in einen Sleep mit negativer Zeit zu treiben). Er vermeidet die Wurzel des Drifts. **Wenn das Race lösbar ist, ist Option E die richtige Wahl.**

#### 2.2 Wie wird Race „Pretrigger vs. aktueller TX-Thread" gelöst?

Drei Varianten wurden genannt:

- **Variante 1 (enges Fenster):** Pretrigger erst nach TX-Ende (cycle_pos ~13.2–13.7s).  
  *Nachteil:* 0,5s-Fenster bei 100ms-Granularität → Risiko von Auslassern (10% Wahrscheinlichkeit pro Slot bei 0,5s Fenster). Über mehrere Slots kumuliert nahezu 100%. **Nicht robust.**

- **Variante 2 (Encoder-Queue):** `encoder.transmit` erlaubt eine zweite Message zu queuen, die nach dem laufenden TX im selben Worker-Loop gesendet wird.  
  *Vorteil:* Kein Race, keine engen Fenster.  
  *Nachteil:* Refactor des Encoders (bisher nur 1 Thread) + Koexistenz mit P1.9 Replace (der bereits den Sleep unterbricht).  
  **Bewertung:** Ist machbar und **die sauberste Lösung**. Replace und Queue können koexistieren, weil Replace nur im Sleep-Fenster greift, die Queue aber erst *nach* TX-Ende aktiv wird. Man muss nur aufpassen, dass `request_replace` nicht mit einer gequeuten Message kollidiert (einfach: nach Replace wird die Queue geleert, da die neue Message den Slot bekommt).  
  **Empfehlung: Variante 2 ist die richtige.**

- **Variante 3 (tx_finished als Trigger):** Nach TX-Ende wird in `_on_tx_finished` der Pretrigger für den nächsten Slot ausgelöst.  
  *Problem:* `_on_tx_finished` läuft asynchron im GUI-Thread. Bis dahin kann der nächste `cycle_tick` schon verpasst sein. Zudem müsste der Pretrigger dann den Encoder sofort triggern, aber `is_transmitting` ist gerade false geworden → das würde im selben Slot einen sofortigen TX starten (nicht für nächsten Slot). Komplex. **Nicht empfohlen.**

**Entscheidung: Variante 2 implementieren.**

#### 2.3 Mike's Spec „kompletter Block-Start" via `start_with_parity_for_next_slot` erfüllt? Edge-Cases?

- **Block-Start:** `_slot_index=0` und korrekter Block gemäß nächster Parität ist erfüllt (V3 AC1–AC5).  
- **Edge-Cases:**
  - **Cancel mid-pretrigger:** Wenn Mike HALT drückt, während ein Pretrigger gerade läuft (Flag gesetzt, aber `_send_cq` noch nicht aufgerufen oder `encoder.transmit` noch nicht gestartet).  
    **Schutz:** HALT ruft `encoder.abort()` + `_omni_pretriggered = False` setzen + `_omni_tx.stop_omni_tx`. Der abgebrochene Worker wird den TX nicht senden. Ein zusätzlicher `_omni_pretriggered = False` in `_on_cancel` ist sinnvoll.
  - **Mode-Wechsel während Pretrigger (L7):** `stop_omni_tx` + `encoder.abort()` reicht. Die gequeute Message in Variante 2 muss dann verworfen werden (einfach: Queue löschen bei `abort()`).
  - **Re-Enable nach Pause:** `start_with_parity_for_next_slot` setzt `_slot_index = 0` und Block neu – überschreibt den alten Slot-Index korrekt.

#### 2.4 Pretrigger-Skip bei RX-Slots korrekt?

**Ja.** Bei RX-Slots: `peek_next.is_tx = False` → kein `_send_cq`, nur Flag setzen. `qso_state` bleibt in `CQ_WAIT`. `on_cycle_end` wird durch das L6-Flag geschützt (kein Doppel-CQ).  
**Kein zusätzliches Signal nötig**, weil `_slot_index` ohnehin über `advance()` im nächsten `cycle_start` weitergeschaltet wird.

#### 2.5 cycle_tick-Granularity 100ms vs. Pretrigger-Fenster 200–500ms

Das Fenster `dur - 1.3` bis `dur - 0.5` (z.B. 13,7–14,5s bei FT8) ist **1,2s breit**. Bei 100ms Granularität sind das 12 Ticks. Auch wenn der genaue Sweet Spot für Sleep-freies Timing bei ~13,5s liegt, reicht die Breite, um mindestens einen Tick im Bereich `is_transmitting = False` und `overshoot < 0.3s` zu erwischen. **Sicher genug.**  
Zusätzlich prüft der Pretrigger `is_transmitting` und kann notfalls einen oder zwei Ticks warten (im nächsten Tick erneut prüfen) – das Fenster ist breit genug.

---

### 3. Encoder-Refactor für Variante 2 – Risikobewertung

#### 3.1 Änderungen in `encoder.py`

```python
def __init__(self):
    ...
    self._pending_tx_message: str | None = None   # neu
    self._pending_tx_even: bool | None = None     # neu, um tx_even für den nächsten TX zu sichern
    self._queue_lock = threading.Lock()           # neu (optional, kann auch ohne Lock per Atomic-Bool)
```

```python
def transmit(self, message: str):
    if self._is_transmitting:
        # Statt SKIP: pending queue
        with self._queue_lock:
            # Nur eine pending Message erlauben (LIFO: letzter gewinnt)
            self._pending_tx_message = message
        return
    # ... normaler Pfad
    self._tx_thread = threading.Thread(...)
    self._tx_thread.start()
```

```python
def _tx_worker_inner(self, message: str):
    # Erstes Encoding + Timing + Audio-Send
    # Nach send_audio und tx_finished.emit(): prüfe pending
    with self._queue_lock:
        next_msg = self._pending_tx_message
        self._pending_tx_message = None
    if next_msg is not None:
        # Rekursiver Aufruf im selben Thread (kein neuer Thread)
        self._tx_worker_inner(next_msg)
```

**Wichtig:**  
- `self._is_transmitting` bleibt während des gesamten Worker-Laufs `True` (beide TX nacheinander).  
- `tx_finished` wird erst **nach** dem zweiten TX emittet (oder nach jedem – je nach Design). Für qso_state muss nach jedem TX `tx_finished` feuern, also nach erstem TX und nach zweitem TX separat. Einfachste Lösung: Worker ruft nach jedem einzelnen TX `self.tx_finished.emit()` auf, auch wenn eine pending Message folgt.  
- `abort()` muss die pending Message verwerfen:  
  ```python
  def abort(self):
      self._is_transmitting = False
      self._abort_event.set()
      with self._queue_lock:
          self._pending_tx_message = None
  ```
- `request_replace` muss prüfen, ob `_is_transmitting` und **nicht** der pending-Message-Pfad aktiv ist (d.h. im ersten TX). Einfach: Replace leert automatisch die pending Queue (weil die neue Message den Slot bekommt) – analog zu `_tx_worker_inner` wo nach Replace `pending_tx_message` verworfen wird.

#### 3.2 Koexistenz mit P1.9 Replace

- Replace setzt `_abort_event`, Worker wacht auf, sieht `_replace_message`, encode neu, und **geht zurück in den while-Loop**.  
- Dabei wird kein `tx_finished` emittet.  
- Nach dem erneuten Encoding wird `_audio_started` gesetzt und der Loop verlassen.  
- **Nach diesem TX** läuft der normale Pfad weiter: erst dann prüft Worker auf `_pending_tx_message`. Da Replace den Slot neu belegt, muss die pending Message **verworfen** werden – sonst würde nach dem Replace-TX noch ein CQ kommen (wäre falsch).  
  **Implementierung:** Im Replace-Pfad (`aborted` + `_replace_message` not None) **vor** `continue` die pending Queue leeren:  
  ```python
  if self._replace_message is not None:
      message = self._replace_message
      self._replace_message = None
      with self._queue_lock:
          self._pending_tx_message = None  # verwerfen
      continue
  ```
  Das ist sicher, weil während des Sleeps keine neuen Pretrigger kommen (Pretrigger prüft `is_transmitting` = True und skipt). Allerdings könnte ein Pretrigger *während* des Encodings des Replace-gesendeten TX im nächsten Slot feuern – dann wäre `is_transmitting` noch True → kein neuer Thread → aber das ist okay, weil der Replace-TX den Slot belegt und der nächste Pretrigger für den übernächsten Slot wäre.

#### 3.3 Gesamtrisiko

- **Mittel.** Der Refactor betrifft die Kernlogik des Encoders (1 Thread → Serialisierung). Tests müssen alle bestehenden TX-Pfade abdecken (CQ, Hunt, Reply, Replace).  
- **Empfehlung:** Zwei Commits:  
  1. Encoder-Queue-Mechanismus (inkl. Tests).  
  2. Dann Pretrigger-Logik oben drauf.  

---

### 4. Test-Strategie für Race-Variante 2

**Zusätzliche Tests in `tests/test_encoder_queue.py`:**

| # | Test | Beschreibung |
|---|------|-------------|
| T1 | `test_transmit_queues_when_busy` | Rufe `transmit(A)` während TX läuft → `_pending_tx_message = B`; kein Fehler. |
| T2 | `test_pending_tx_fires_after_current` | Starte TX, rufe `transmit(B)`, warte auf Worker-Ende → prüfe dass B gesendet wurde. |
| T3 | `test_pending_tx_overwrites_previous` | Rufe `transmit(A)`, dann `transmit(B)`, dann `transmit(C)` → nur C wird gequeued. |
| T4 | `test_abort_clears_pending` | Starte TX + queue, rufe abort → pending ist None, Worker bricht ab. |
| T5 | `test_replace_clears_pending` | Starte TX, queue, rufe request_replace → pending wird verworfen, Replace-TX gesendet. |
| T6 | `test_two_tx_in_worker_emits_tx_finished_twice` | TX + pending → nach jedem TX wird Signal emittet. |
| T7 | `test_pretrigger_race_with_tx` | Kombiniert mit Pretrigger: TX läuft, Pretrigger feuert (queue), nach TX-Ende wird der gequeute TX im nächsten Slot gesendet (kein Drift). |

**Integrationstest für L17 (Kernproblem):**

```python
def test_omni_pretrigger_no_skip_due_to_active_tx():
    """Sicherstellen dass ein Pretrigger während laufendem TX nicht verloren geht."""
    encoder = Encoder()
    # Starte ersten TX
    encoder.transmit("CQ DA1MHH JN58")
    # Pretrigger feuert
    encoder.transmit("CQ DA1MHH JN58")
    # Nach erstem TX muss der zweite gesendet werden
    # Verifikation: nach 14s (TX-Dauer + sleep) muss tx_finished 2× feuern
    # und die zweite Message muss korrekte Parität haben
```

---

### 5. Abschließende Empfehlung

1. **Option E (Mid-Cycle Pretrigger) mit Variante 2 (Encoder-Queue) implementieren.**  
2. **L6 Schutz über `_omni_pretriggered` Flag in `mw_cycle` + `_was_pretriggered` Flag in `qso_sm`.**  
3. **L17 Race wird durch Queue gelöst – sauberer und robuster als enge Fenster.**  
4. **Encoder-Refactor in separatem Commit mit umfassenden Tests.**  
5. **Pretrigger-Logik als zweiter Commit, Tests für den Gesamtflow.**  
6. **Field-Test mit Mike nach Implementation: wenigstens 10 OMNI-Blöcke (50 Slots) hintereinander ohne Drift.**  

**Offene Punkte vor Implementation klären:**  
- Soll `tx_finished` nach jedem einzelnen TX im Worker feuern oder erst nach der gesamten Serialisierung? → Nach jedem TX (qso_state braucht es).  
- Wie wird mit Replace + gleichzeitiger Queue umgegangen? → Replace verdrängt Queue (siehe oben).  

---

### 6. Antworten auf die 5 offenen Fragen (aus §2 des Self-Reviews)

1. **Mid-Cycle-Pretrigger (Option E) ist der richtige Pfad**, sofern das Race L17 via Encoder-Queue gelöst wird. Die Analyse L1–L16 ist vollständig und korrekt.  
2. **Race-Schutz:** Variante 2 (Encoder-Queue) wird empfohlen. Variante 1 (enges Fenster) ist zu fragil, Variante 3 (tx_finished-Trigger) zu komplex.  
3. **Block-Start `start_with_parity_for_next_slot`** ist korrekt. Edge-Cases (Cancel mid-pretrigger, Mode-Wechsel) sind durch bestehende abort/stop-Mechanismen geschützt.  
4. **Pretrigger-Skip bei RX-Slots** ist korrekt: kein _send_cq, nur Flag.  
5. **cycle_tick-Granularität 100ms** ist ausreichend: 1,2s-Fenster bei FT8 gibt 12 Ticks, genug für zuverlässigen Trigger.  

---

### 7. Nächste Schritte (für Mike/Maintainer)

1. **Encoder-Queue implementieren** (Datei: `core/encoder.py`).  
2. **Tests schreiben** (Datei: `tests/test_encoder_queue.py`).  
3. **Pretrigger-Logik in `mw_cycle.py` und `qso_state.py` einbauen** (unter Verwendung der Queue).  
4. **Integrations-Tests** (Datei: `tests/test_p2_omni_pattern_fix.py`).  
5. **Field-Test** mit Mike.  

---

*Ende DeepSeek-R1 Review. Alle Code-Stellen verifiziert, Lücken identifiziert, Empfehlung ausgesprochen.*
