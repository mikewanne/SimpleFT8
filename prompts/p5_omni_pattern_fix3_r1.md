[deepseek] ~59666 Tokens, 8 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=70920 out=6985 total=77905
## §A — Encoder-Throughput-Diagnose

### Aufgabe 1: `_is_transmitting=False`-Latenz nach Slot-Start :30

**Schaetzung:**
- FT8 Audio: 12.64s (fest, `ft8lib.encode()` output)
- PTT-Settle: ~0.1-0.3s (`ptt_on()` → `radio.send_audio()`)
- FlexRadio Buffer-Drain: 1.3s (konstant, Hardware-Puffer)
- `send_audio` blockiert bis alle Samples im Radio-Buffer sind
- `ptt_off()`: ~0.1s (asynchron, aber `_is_transmitting=False` im `finally`)
- Thread-Scheduling-Jitter (Worker vs. GUI-Thread): ±0.1-0.5s

Formel: `tx_duration = 12.64s + 1.3s + ptt_off_latency + scheduling_jitter`

**Konkret bei Slot-Start :30 (Idealfall, kein Drift-Guard):**
- `:30.0` — `transmit()` aufgerufen (cycle_start ~:30.05-:30.2)
- `:30.2` — Worker startet (encode ~0.05-0.2s)
- `:30.4` — `send_audio(audio_full, 12000)` blockt
- Audio-Samples: ~12.64s @ 12kHz = 151680 Samples
- Blocking: Samples werden via VITA-49 UDP gestreamt
- FlexRadio puffert 1.3s von diesen Samples → `send_audio` kehrt zurueck wenn letztes Sample in Buffer geschrieben = `:30.4 + 12.64s = :43.0`
- Puffer-Drain laeuft noch 1.3s (Radio sendet Samples aus Buffer)
- `ptt_off()` Aufruf bei `:43.0` (nicht-blocking im Code)
- `_is_transmitting=False` im `finally` bei `:43.0` + minimaler Jitter

**Min:** `:42.8` (Audio frueher fertig, kein Jitter)
**Max:** `:44.5` (Thread-Scheduling, Qt-Event-Loop-Last, `send_audio`-Ueberhang)

**Fazit:** `_is_transmitting=False` faellt typisch **12.8-14.5s nach Slot-Start** = `:42.8-:44.5`. Pos 1-Slot bei `:45.0` hat damit **0.5-2.2s Window**. In der Praxis (mit FlexRadio Buffer-Drain und Jitter) ist das Fenster oft **< 1s**, was die 100% busy-Rate erklaert.

**Quellen im Code:**
- `encoder.py:348-349` — `send_audio` blockt bis Buffer voll
- `encoder.py:351-353` — `ptt_off()` danach
- `encoder.py:357-358` — `_is_transmitting = False` im `finally` (nicht direkt auditable — dort steht `self._is_transmitting = False` in Zeile 222/227/355? Pruefe: Zeile 222 `finally: self._is_transmitting = False`)

### Aufgabe 2: Drift-Guard-Verhalten bei OMNI

**Wann greift Drift-Guard?**

Bedingung in `encoder.py:331-340`:
```python
silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)  # = next_boundary - 0.8 - now
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    if overshoot > 0.3:
        # Drift-Guard greift
```

Für OMNI `_do_tx_slot`:
- `cycle_start` kommt aus `timing.py:86-87` im GUI-Thread (Typ: 100-400ms nach Slot-Boundary)
- Bei Slot N+1: `cycle_start` feuert bei `:45.15-:45.4` (Slot-Boundary :45)
- `transmit()` wird aufgerufen → Worker berechnet `_next_slot_boundary()`
- `now = :45.2` → `cycle_pos = 0.2 > 0.5?` Nein → **aktueller Slot wird genommen**: `next_boundary = :45.0`
- `silence_secs = :45.0 - 0.8 - :45.2 = -1.0 → 0.0`
- `silence_secs < 0.1` → True
- `overshoot = :45.2 - (:45.0 - 0.8) = 1.0s > 0.3` → **Drift-Guard GREIFT**
- `next_boundary += 2 * 15 = :75.0` → Worker sendet bei :75
- **Pos 1 TX-O erscheint bei :75 statt :45**

**ABER:** Mike sah Pos 0 TX-E **bei :30** (nicht bei :60). Das bedeutet: **Drift-Guard griff bei Pos 0 NICHT.**

**Aufloesung:**
- Bei Pos 0 (:30) kam `cycle_start` sehr frueh (< 0.3s nach Boundary → `cycle_pos < 0.3` → `silence_secs` positiv → no Drift-Guard).
- Bei Pos 1 (:45) kam `cycle_start` spaeter (0.15-0.4s) → `overshoot > 0.3` → Drift-Guard.

**Widerspruch zu Field-Test-Log:** Der Log zeigt 3× `encoder.transmit busy` **ohne** Drift-Guard-Print. Aber wenn Drift-Guard gegriffen haette, wuerde `[TX] Drift-Vermeidung: overshoot=...` erscheinen.

**Hypothese H-D1:** Drift-Guard greift bei Pos 1 nicht, weil `cycle_start` IMMER sehr frueh kommt (< 0.1s before `(:45 - 0.8)`). Dann ist `silence_secs` positiv → kein Drift-Guard. Der Worker sendet bei `:45.0` korrekt. Aber dann muesste `_is_transmitting` bei `:57.6-:59.5` fallen (12.64+1.3+ptt_off). Pos 2 (`:60`) waere frei. **Pos 1 waere busy weil Pos 0 noch sendet.**

**H-D2 (wahrscheinlicher):** Drift-Guard greift NIE, weil `cycle_start` bei OMNI `_do_tx_slot` immer sehr frueh kommt. Der einzige Grund fuer Pos 1-busy ist das **Zeitfenster** zwischen Pos 0 TX-End (`:42.8-:44.5`) und Pos 1 Start (`:45.0`). Dieses Fenster ist **< 2.2s** und wird durch Jitter konsistent auf < 0 reduziert.

## §B — Loesungsoptionen-Bewertung

### Welche Variante ist KISS-konform und Hobby-Tool-tauglich?

**Variante A (Encoder-Queue mit Pending-Verfall)** — meine Wahl:

**Pro:**
- Minimaler Code-Zuwachs (~20-30 Zeilen in `encoder.py`)
- Keine neuen Module, keine Threads
- Nutzt existierenden `_replace_lock` und `_tx_worker_inner`-Loop
- Pending-Verfall verhindert Drift-Guard im Pending-Pfad (Test T9)
- Kompatibel mit V3-§8 "keine Aenderungen an encoder.py" — **muss gekippt werden** (siehe unten)

**Contra:**
- Verlaesst sich auf `_is_transmitting=False` spaetestens 1.5s vor Ziel-Slot
- Bei FlexRadio Buffer-Drain > 1.5s nach Audio-Ende: Pending-Verfall greift → kein TX
- `_pending_queued_at`-Race bei Multithreading: `_replace_lock` loest das

**Variante B (Mid-Cycle-Pretrigger)** — robust aber komplex:

**Pro:**
- Encoder hat konstante 1.3s Vorlauf, nie Drift-Guard
- Funktioniert auch bei 14.5s `_is_transmitting=False`

**Contra:**
- ~50-80 Zeilen in `omni_cq.py` (Pretrigger-Logik + `_tx_already_started_for_slot`-Flags)
- Verstoesst explizit gegen V3-§8-Verbot "cycle_tick-basierter Pretrigger"
- Race bei QSO-Start mid-pretrigger (zus. Checks noetig)
- Hohe Fehleranfaelligkeit im Feldtest

**Variante C/D (Spec-Aenderung)** — KISS aber der Operator verliert TX-Rate:

- Halbiert CQ-Rate (nur 1 TX/Block statt 2)
- Kein Code-Bug-Fix, sondern Spec-Aenderung — Mike muesste zustimmen

### V3-§8-Verbote-bewertung

**War der Verzicht gerechtfertigt?** Ja, fuer V3 (Signal-Refactor). Der Signal-getriggerte Pfad hatte einen simpleren Data-Flow ohne Threads.

**Soll es in P5 gekippt werden?** Ja — das Verbote "Encoder-Queue für OMNI" muss gekippt werden. Die Queue ist notwendig, um konsekutive TX-Slots zu bedienen. Die anderen Verbote (Frequenz-Recheck, qso_state-Aenderungen, etc.) bleiben.

**Empfehlung: Variante A (Encoder-Queue) + Aufhebung des Encoder-Queue-Verbots.**

## §C — Hypothesen-Aufloesung

### H-Pos-4-RX-E-fehlt (V2 §1.4)

Mike sah keinen `:30 [E] Horche`-Eintrag fuer Pos 4 (Block 1, RX-E nach 4 Slots). V2 hat 6 Pfade ausgeschlossen:

1. `_paused = True` — Logs zeigen kein QSO → ausgeschlossen
2. `_active = False` — Stop kam erst nach Symptom → ausgeschlossen
3. Slot-Index-Off-by-one — `_advance_state` ist 1× pro slot → ausgeschlossen
4. Anzeige-Limit/Trimm — 300s Window → ausgeschlossen
5. `_advance_state`-Drift durch busy-Skip — `_slot_index` bleibt synchron → ausgeschlossen
6. Unbekannter Toggle — Mode-Wechsel/Diversity? Logs zeigen keine → ausgeschlossen

**Fehlender Pfad (H-X1):** `add_listening` wird in `_on_omni_slot_action` aufgerufen:
```python
if not is_tx:
    self.qso_panel.add_listening(time.time(), target_even)
```
Bei Pos 4 ist `is_tx=False`, also muesste der Aufruf erfolgen. **Aber:** Mike's Logs zeigen `manual_halt` nach ca. 1.5 Bloecken. **Wenn `stop()` im `on_cycle_start` NACH `_advance_state` aufgerufen wurde, wurde `_active=False` gesetzt, bevor `_do_rx_slot` fuer Pos 4 feuert?** Nein — `_advance_state` ist **nach** `_do_rx_slot` im Code.

**H-X2 (UI-Bug):** `qso_panel.add_listening` verwendet `slot_start_ts=time.time()` (Wall-Time). Wenn der Aufruf kommt, nachdem der Slot bereits vorbei ist (z.B. wegen Qt-Event-Queue-Latenz), zeigt `slot_start_ts` auf den **naechsten** Slot. Der Eintrag erscheint dann an der falschen Position im QSO-Panel. Mike koennte den Eintrag uebersehen haben weil er nicht am erwarteten Ort stand.

**H-X3 (meine Diagnose):** Der wahrscheinlichste Pfad ist **UI-Bug in `add_listening`**: `time.time()` liefert die Aufruf-Zeit, nicht die Slot-Boundary. Wenn der Aufruf zufaellig im naechsten Slot (1:00) landet (was bei 0.5-1s Latenz gut moeglich ist), zeigt der Eintrag `:00 [E]` statt `:30 [E]`. Mike erwartet `:30` und sieht `:00` → glaubt es fehlt.

### H-`:44 [O] Horche`-Quelle (V2 §1.3)

Bei busy-Pos-1 wird `slot_action` NICHT emittet (nur log warning). Wer triggert `add_listening` bei `:44 [O]`?

**Code-Pfade:**
1. `main_window.py:760` `_on_omni_slot_action(label, True, False)` wird **nicht** aufgerufen (kein `slot_action.emit` bei busy)
2. `qso_panel.add_tx` wird NICHT aufgerufen (kein `encoder.tx_started` bei busy)
3. `qso_panel.add_listening` direkt — wird nirgendwo anders aufgerufen

**H-Y1 (Display-Bug):** Der Eintrag `:44 [O]` stammt aus einem **vorherigen** Zyklus. Mike hat vielleicht veraltete Eintraege im Buffer gesehen. `_auto_trim_by_age` trimmt nur > 5 Min, nicht > 1 Block. Ein alter `:44 [O]`-Eintrag von vor 75s waere noch sichtbar.

**H-Y2 (Mike-Beobachtungsfehler):** Mike hat `:44 [O]` falsch interpretiert. Der Eintrag war `:45 [O]` (Pos 0 naechster Block) oder stammt aus einem anderen Pfad.

**H-Y3 (meine Praeferenz):** Die wahrscheinlichste Quelle ist **alter UI-Buffer**. Mike hat eine Session ohne vorherigen OMNI-Start gehabt, oder der Eintrag stammt aus `add_info` mit falschem Timestamp-Format. **Ich rate: Ignorieren — Issue B ist kritisch, Issue A kosmetisch, aber H-`:44` ist wahrscheinlich kein Bug im Code sondern Beobachtungs-Artefakt. V3 sollte trotzdem AC-B7 mit "RX-Eintrag erscheint an Slot-Boundary" testen.**

## §D — Pending-Verfall-Review

### Schwelle: `target_slot - queued_at > _SLOT * 1.5`

**Richtig:** 
- FT8: `1.5 * 15.0 = 22.5s`
- Maximal erwartete `_is_transmitting=False`-Latenz: ~14.5s (12.64 Audio + 1.3 Buffer + PTT + Jitter)
- 22.5s > 14.5s → Pending bleibt aktiv wenn Worker innerhalb 14.5s fertig wird
- **Gut gewaehlt**

**Edge-Case:** Worker braucht genau 22.5s (z.B. Drift-Guard greift + Audio):
- FT8: `_pending_queued_at = :45.0`, `target_slot = :60.0` (naechster Slot nach 22.5s)
- Worker fertig bei `:45.0 + 22.5s = :67.5`
- `target_slot - queued_at = 15.0s < 22.5s` → **Pending bleibt**, aber Worker braucht nochmal 12.64s → `_is_transmitting=False` bei `:80.0`
- Naechster passender Slot nach `_next_slot_boundary()`: `:90.0` (nach `:80.0`)
- Pending: `:90.0 - :45.0 = 45.0s > 22.5s` → **Verfall**
- **Resultat:** Einmal Drift-Guard im Pending → Verfall. Ok — verhindert Endlos-Loop.

**Race `_pending_queued_at`:** 
- Im Code: `self._pending_queued_at = time.time()` wird **vor** `_replace_lock` gesetzt? Nein — im vorgeschlagenen Code steht `with self._replace_lock:` nur fuer `_pending_tx`-Set. `_pending_queued_at` wird ausserhalb gesetzt → **Race**: Worker liest `_pending_queued_at` waehrend `_is_transmitting=True` (after lock release). **Fix:** Setze `_pending_queued_at` UNTER `_replace_lock`.

```python
with self._replace_lock:
    if self._is_transmitting:
        self._pending_tx = (message, tx_even, audio_freq_hz)
        self._pending_queued_at = time.time()  # <<< HIER
        return True
```

### Edge-Case: Pending-Re-Trigger loest erneut Drift-Guard aus

Wenn Worker bei `:74.0` fertig wird und Pending-Ziel `:75.0` ist (gerade mal 1s spaeter):
- `_exit_worker` ruft `_tx_worker_inner(pending_msg)` mit `_is_transmitting=True`
- `_next_slot_boundary()`: `now = :74.0`, `tx_even = False` (Odd gewuenscht), naechster passender Slot = `:75.0`
- `silence_secs = :75.0 - 0.8 - :74.0 = 0.2s > 0.1` → **kein Drift-Guard**
- Worker schlaeft 0.2s (bis `:74.2`), dann `send_audio` bei `:74.2`
- `send_audio` blockt bis `:74.2 + 12.64 = :86.84`
- **TX bei :75.0 (ok)** — aber erst ab `:75.0 + 1.3 = :76.3` on-air (Flex-Buffer)
- **Pattern bleibt synchron**

**Aber:** Wenn `next_boundary = :75.0` und Worker schlaeft bis `:74.2`, ist das 0.8s vor `:75.0`. `TARGET_TX_OFFSET = -0.8` → `send_audio` startet bei `:74.2` → Stille bis `:75.0` → FT8-Audio ab `:75.0`. **RF on-air bei `:75.0 + 1.3 - 0.8 = :75.5`** (korrekt — DT≈0.5s, entspricht WSJT-X-Protokoll). **Pending funktioniert sauber.**

**Fazit:** Pending-Verfall-Logik ist solide. Schwelle `1.5 * cycle_duration` ist gut gewaehlt. `_pending_queued_at` muss unter Lock gesetzt werden.

## §E — Test-Plan-Review

### T1-T11 abdecken alle Kern-Szenarien?

| Test | Deckt ab | Bewertung |
|------|----------|-----------|
| T1: `test_transmit_returns_true_when_busy_and_queues_pending` | Pending-Queue Mechanik | ✅ Grundlegend |
| T2: `test_pending_consumed_after_finally` | Konsum im Worker-Finally | ✅ |
| T3: `test_pending_dropped_if_target_slot_in_past_more_than_1_5_slots` | Verfall-Schwelle | ✅ |
| T4: `test_add_listening_uses_slot_boundary_ft8` | Issue A (Slot-Boundary) | ✅ |
| T5: `test_add_listening_slot_boundary_all_modes` | FT4/FT2 Issue A | ✅ |
| T6: `test_pending_not_consumed_if_omni_stopped` (AC-Z5) | Stop waehrend Pending | ✅ |
| T7: `test_pending_omni_only_not_normal_cq` (AC-Z6) | Kein Missbrauch durch Normal-CQ | ✅ |
| T8: `test_pending_transmit_does_not_drift` | Pending-Re-Trigger ohne Drift | ✅ (neu in V2) |
| T9: `test_pending_verfall_after_drift_guard_in_pending` | Drift-Guard im Pending → Verfall | ✅ (neu in V2) |
| T10: `test_pending_queued_at_race` | Lock-Check | ❌ **FEHLT** |
| T11: `test_pending_not_re_entrant` | Re-Entry-Schutz | ❌ **FEHLT** |

**Fehlende Tests:**

1. **Race-Test T10:** `test_pending_queued_at_race` — Zwei Threads rufen `transmit()` parallel, einer pending, der andere erfolgreich. Pruefe `_pending_queued_at` unter Lock gesetzt.

2. **Re-Entry-Test T11:** `test_pending_not_re_entrant` — Wenn Pending gerade konsumiert wird und ein weiterer `transmit()` kommt → darf pending nicht ueberschrieben werden. (Wird durch `_is_transmitting=True` im Re-Trigger verhindert — trotzdem testen.)

3. **E2E-Test mit echtem FT8Timer-Mock:** Der V2-Plan sagt "Direct-Aufruf von `on_cycle_start`". **Das reicht nicht!** Es fehlt ein Test der das **Zusammenspiel** von `_do_tx_slot` (omni_cq.py) → `encoder.transmit()` → Worker → Drift-Guard → Pending-Konsum prueft.

   **Vorschlag:** Ein Integration-Test `test_omni_cq_encoder_flow`:
   - Fake FT8Timer, der `cycle_start` feuert
   - Fake-Encoder, der `transmit` mit echter `_is_transmitting`-Simulation (0.1s Blocking)
   - Pruefe: `counter_changed` nach erfolgreichem TX
   - Pruefe: `console.log` Warnung bei busy

4. **Drift-Guard im Pending-Pfad:** T9 testet das, aber braucht einen Mock der `_next_slot_boundary` so manipuliert, dass `overshoot > 0.3` im Re-Trigger auftritt. **Wichtig:** Sicherstellen dass der Verfall nicht in einer Endlos-Re-Trigger-Schleife landet.

**Fazit:** T1-T11 sind ausreichend, aber T10+T11 fehlen. Integration-Test mit Timer-Mock waere wuenschenswert, aber nicht zwingend (KISS). T9 ist der wichtigste Test — wenn der gruen ist, ist die Pending-Logik robust.

## §F — Empfehlung an Mike

Implementiere **Variante A (Encoder-Queue mit Pending-Verfall)** in v0.96.2. Der Bug in Pos 1 wird behoben, solange die Latenz von `_is_transforming=False` < 1.5 Slots nach Pending-Queue-Zeitpunkt bleibt. **Setze `_pending_queued_at` unter `_replace_lock`** und fuege die 2 fehlenden Tests (Race + Re-Entry) hinzu. Falls nach dem Patch die busy-Rate nicht auf 0 sinkt (Log zeigt weiterhin `transmit busy` trotz Pending) → erhoehe die Verfall-Schwelle auf `2.0 * cycle_duration` (30s bei FT8) — das gibt mehr Spielraum fuer Drift-Guard im Pending-Pfad. Sollte auch das nicht helfen, **upscale zu Variante B** (Mid-Cycle-Pretrigger) unter Aufhebung des V3-§8-Vebots.
