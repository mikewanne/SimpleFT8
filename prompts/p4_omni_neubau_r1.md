[deepseek-high] ~46017 Tokens, 1 File(s) → deepseek-reasoner (max_tokens=32000)
[deepseek-high] R1 denkt — bis zu 5 Min ...
[deepseek-high] in=57386 out=13346 total=70732
## P4.OMNI-NEUBAU — R1 Review

### A — Bewertung V2-Lessons L1–L20

| L# | Bewertung | Begründung (mit Code-Beweis) |
|----|-----------|-----------------------------|
| L1 | ✅ BESTÄTIGT | `on_message_decoded` lebt in `ui/mw_cycle.py:909`, nicht in `mw_qso.py`. V2‑Korrektur (Check VOR `qso_sm.on_message_received`) ist korrekt. |
| L2 | ✅ BESTÄTIGT | Setzen von `encoder.tx_even` und `audio_freq_hz` direkt vor `transmit()` ist ein Race mit dem Encoder‑Worker (liest beide in `_next_slot_boundary`). Atomare API (`transmit(msg, tx_even=, audio_freq_hz=)`) ist die richtige Lösung. |
| L3 | ✅ BESTÄTIGT | `_last_qso_tx_even` muss in `_on_tx_finished` aus `encoder.tx_even` gemerkt werden. Edge‑Case Timeout: letzter TX‑Slot ist akzeptable Näherung. |
| L4 | ✅ BESTÄTIGT | Fallback 1500 Hz mit Log‑Warning ist besser als `or 1500`. |
| L5 | ⚠️ TEILWEISE | Befund (4 Blöcke bei FT4/FT2 zu kurz) ist richtig, aber Mike’s Spec sagt „alle 4 Blöcke (~5 Min)". Zeit‑basierte Lösung (300 s konstant) weicht ab. Beides dokumentieren, Spec priorisieren. |
| L6 | ✅ BESTÄTIGT | Flag‑Name `_omni_was_active_pre_qso` behalten – konsistent mit existierendem Code. |
| L7 | ✅ BESTÄTIGT | `encoder.tx_even` nach OMNI‑Stop nicht zurücksetzen – Normal‑CQ setzt selbst. |
| L8 | ✅ BESTÄTIGT | TX‑Emit nach `transmit()`, RX‑Emit am Anfang – präzise Definition ok. |
| L9 | ✅ BESTÄTIGT | V2 fordert gegenseitigen Stop in beiden Toggle‑Handlern. Der existierende Code (v0.95.25) tut das bereits, für den Neubau muss es übernommen werden. |
| L10 | ✅ BESTÄTIGT | Kritisch: `qso_state._process_cq_reply` ignoriert die Caller‑Queue bei `cq_mode=False`. V2‑Lösung (mw_qso übernimmt Queue‑Pop + `start_qso`) ist notwendig und korrekt. |
| L11 | ✅ BESTÄTIGT | Alte Tests: ~81 raus, neu: 27 → netto ~1015 Tests. V1’s Schätzung -50 war zu optimistisch. |
| L12 | ✅ BESTÄTIGT | Hardware‑Garantie ANT1 zentral in `Encoder.transmit()` – OMNI ruft nur das auf. |
| L13 | ✅ BESTÄTIGT | `time.sleep(0.5)` ist nicht cancelable → `_stop_event.wait(0.5)` ersetzen. Kritisch für sauberen Stop/Pause. |
| L14 | ✅ BESTÄTIGT | Präzisere Formulierung des RX‑Slot‑Verhaltens im Worker‑Loop (nice‑to‑have). |
| L15 | ✅ BESTÄTIGT | `Encoder.transmit()` returnt sofort, blockiert nicht – verifiziert. |
| L16 | ✅ BESTÄTIGT | Bandwechsel mid‑OMNI‑TX: Encoder‑TX läuft Slot zu Ende – dokumentieren. |
| L17 | ✅ BESTÄTIGT | APP_VERSION v0.96.0 – korrekter Minor‑Bump. |
| L18 | ✅ BESTÄTIGT | Commit‑Reihenfolge: Tests‑Migration zuerst (C1), dann neues Modul (C2), dann Rückbau – robuster als V1’s C1‑zuerst. |
| L19 | ➕ ERGÄNZUNG | `_diversity_ctrl`‑Init muss in V3 verifiziert werden (`mw_qso.py:223` zeigt Existenz, aber Init‑Ort prüfen). |
| L20 | ✅ BESTÄTIGT | Keine Settings‑Persistenz nötig – OMNI startet immer inaktiv. |

**Zusätzliche Ergänzungen zu L1 und L10:**
- **L1 ergänzen**: Der Listener‑Pfad muss **vor** `start_qso` den `encoder.tx_even` setzen (auf die Parität der eingehenden Antwort). Sonst sendet der Hunt‑Pfad auf der falschen Slot‑Parität.
- **L10 ergänzen**: Nach Stop (z.B. `band_change`) muss `_omni_was_active_pre_qso` in `_on_omni_stopped` auf `False` gesetzt werden, sonst versucht `_maybe_resume_omni` nach einem Caller‑Queue‑QSO fälschlich OMNI zu resumen.

---

### B — Race‑Condition‑Audit

#### 1. Worker‑Thread‑Lifecycle
- **`pause()` + `stop()` gleichzeitig**: `pause()` setzt `_paused=True`, `stop()` setzt `_paused=False`. Mit `RLock` serialisiert – kein Problem. **Aber**: Wenn `stop()` zuerst `_running=False` setzt, macht `pause()` danach nichts (Guard `if not self._running: return`). Korrekt.
- **`start()` während laufendem Worker**: Guard `if self._running: return` → idempotent. ✅
- **`resume_after_qso()` während Worker noch nicht ausgelaufen**: `pause()` joinet den Worker (max 2s). Nach dem Join ist der Worker tot → `resume_after_qso` ruft `start()` neu auf. Falls `pause()` aus irgendeinem Grund nicht aufgerufen wurde, könnte `start()` `_running=True` sehen und nichts tun → Bug. **Mitigation**: `resume_after_qso` sollte `_running` prüfen und ggf. den alten Worker joinen, bevor `start()` aufgerufen wird. ⛔ KRITISCH (sollte in V3 ergänzt werden).

#### 2. Cross‑Thread‑Datenaustausch
- **`encoder.tx_even` / `encoder.audio_freq_hz`**: OMNI‑Worker setzt diese direkt (oder via atomare API). Lesevorgang im Encoder‑Worker (`_next_slot_boundary`) ist in Python unter GIL atomic für einfache Typen. **Atomare API (V2‑L2) ist dennoch empfehlenswert**, aber nicht zwingend. **Andere betroffene Attribute**: `encoder._is_transmitting` (wird im Encoder‑Worker gesetzt, von OMNI gelesen? Nein). `tx_even` und `audio_freq_hz` sind die einzigen, die von aussen gesetzt werden.
- **`_paused`‑Flag**: Worker liest unter `self._lock` → safe.
- **`_caller_queue`‑Read in `_maybe_resume_omni`**: Wird im GUI‑Thread aufgerufen (via Signal). `_caller_queue` wird nur im GUI‑Thread modifiziert → safe.

#### 3. Decoder‑Encoder‑Timing
- **Marge zwischen OMNI‑Worker‑Wake und Encoder‑Wake**: 1.5 s – 1.3 s = **0.2 s**.  
  Bei OS‑Scheduling‑Verzögerung >0.2 s wacht OMNI‑Worker zu spät auf → `sleep_dur` für Encoder wird negativ → Drift‑Schutz schiebt TX um 2 Slots → **Pattern‑Drift**.  
  **Empfehlung**: OMNI‑Worker sollte 2.0 s vor Boundary aufwachen (Marge 0.7 s). ⛔ KRITISCH.

---

### C — Architektur‑Bewertung

- **3‑Schichten‑Architektur** (Normal‑CQ `qso_state.cq_mode` | OMNI `omni_cq.py` | gemeinsamer Hunt‑Pfad `start_qso`) ist sauber entkoppelt.
- **Listener‑Pfad in mw_cycle** (V2‑L1): Reihenfolge korrekt (OMNI‑Check VOR `qso_state.on_message_received`). **Aber**: Der Pfad muss vor `start_qso` den `encoder.tx_even` auf die Parität der eingehenden Antwort setzen. Fehlt in V2. ⛔ KRITISCH.
- **OMNI ruft `qso_state.start_qso` direkt**: Hunt‑State‑Machine funktioniert ohne Änderung, da `start_qso` keinen `cq_mode` voraussetzt. **Achtung**: `start_qso` setzt `_was_cq = self.cq_mode` → bei OMNI ist `cq_mode=False` → nach QSO wird kein CQ resumed, OMNI muss selbst über `_maybe_resume_omni` gestartet werden. Korrekt.

---

### D — Edge‑Cases die V2 übersehen könnte

| Edge‑Case | Schweregrad | Mitigation |
|-----------|-------------|------------|
| **App‑Start während laufendem Slot** (cycle_pos > 12s) | ⚠️ SOLLTE | `_compute_next_boundary` schaut mindestens einen Slot voraus → funktioniert. |
| **Bandwechsel mid‑OMNI‑TX** | ✅ OK | Encoder‑TX läuft zu Ende, dann Stop (V2‑L16). |
| **Mode‑Wechsel Diversity → Normal** | ✅ OK | Stop‑Trigger, Worker terminiert. |
| **Decoder‑Hang / Decoder‑Crash** | ✅ OK | OMNI‑Worker unabhängig. |
| **Encoder‑Crash (Exception in `_tx_worker`)** | ✅ OK | `transmit()` gibt ggf. False zurück, OMNI verliert einen Slot. |
| **2 Antworten in 1 RX‑Slot** (Even+Odd gleichzeitig) | ⛔ KRITISCH (akzeptabel) | Erste Antwort startet QSO, zweite wird **komplett ignoriert** (Listener return). Anrufer geht verloren. Für Hobby‑Tool akzeptabel, aber sollte dokumentiert werden. |
| **Antwort während TX‑Slot** (Decoder dekodiert vor TX‑Ende) | ✅ OK | Antwort gehört zum vorherigen RX‑Slot → kein Problem. |
| **Caller‑Queue‑QSO nach OMNI‑Stop** | ⛔ KRITISCH | `_omni_was_active_pre_qso` bleibt True nach Stop → `_maybe_resume_omni` könnte fälschlich Caller‑Queue bearbeiten. **Lösung**: `_on_omni_stopped` muss `_omni_was_active_pre_qso = False` setzen (bereits in V1 enthalten, in V3 sicherstellen). |

---

### E — Test‑Plan‑Vollständigkeit

**Fehlende Tests (sollten ergänzt werden):**
- `test_atomic_transmit_api` – verifiziert, dass `transmit` mit `tx_even`/`audio_freq_hz`‑Parametern funktioniert und Race schließt.
- `test_caller_queue_during_omni` – Integration: OMNI läuft, QSO läuft, zweiter Anrufer kommt → Queue wird nach QSO abgearbeitet, dann OMNI resume.
- `test_multiple_answers_one_slot` – Unit: zwei Nachrichten an uns in einem RX‑Slot → erste akzeptiert, zweite ignoriert (oder dokumentiert).
- `test_worker_timing_margin` – verifiziert, dass `_stop_event.wait(timeout=prelead-1.3)` nicht zu kurz wird (z.B. OS‑Delay‑Simulation).
- `test_band_change_during_omni_tx` – Integration: TX läuft, Bandwechsel kommt → TX läuft zu Ende, OMNI gestoppt.

**Unnötige Tests:**
- Detailtests für `_compute_next_boundary` (T15‑T17) sind sinnvoll, aber könnten parametrisiert werden (pytest‑parametrize für verschiedene Target‑Paritäten). ✅

---

### F — Commit‑Reihenfolge

V2‑L18 ist robust. **Einzige Korrektur**: C1 (Tests‑Migration) sollte **vor** C2 (neues Modul) kommen, damit alte Tests nicht auf alten Code verweisen. Die Reihenfolge ist:
1. **C1**: Alte OMNI‑Tests löschen (~81 Tests). Tests grün (weniger).
2. **C2**: Neues Modul `core/omni_cq.py` + Unit‑Tests (27 Tests). Tests grün.
3. **C3**: Rückbau `core/qso_state.py` + `core/encoder.py` (OMNI‑Reste entfernen). Tests grün (keine Abhängigkeiten).
4. **C4**: Rückbau `ui/mw_cycle.py` (alle `_omni_pretrigger_*` raus). Tests grün.
5. **C5**: Anschluss `main_window.py` + `mw_qso.py` (OMNI‑Integration). Integration‑Tests grün.
6. **C6**: Stop‑Trigger (`mw_radio`, `totmann`). Integration‑Tests grün.
7. **C7**: Doku + APP_VERSION.

**Bleiben Tests nach jedem Commit grün?** Ja, weil alte Tests vor dem Rückbau gelöscht werden und neue Tests erst nach dem neuen Modul aktiviert werden. ⚠️ **Achtung**: In C5 werden die Integration‑Tests aktiv – diese könnten auf die in C3/C4 entfernten Teile angewiesen sein. Da diese Teile nicht mehr existieren und die Integration‑Tests nur OMNI‑Funktionalität prüfen (die in C2 implementiert wurde), sind sie unabhängig. ✅

---

### G — KISS‑Bewertung

**Overengineering‑Verdacht:**
- **Atomare `encoder.transmit`‑API** (V2‑L2): Unter GIL ist das Setzen von bool/int‑Attributen atomic. Die atomare API ist nicht zwingend nötig, aber sie macht den Code sauberer und verhindert zukünftige Fehler. **Akzeptabel**.
- **`slot_action`‑Signal** mit drei Parametern: Für eine Hobby‑App ausreichend. **OK**.
- **Worker‑Thread‑State‑Machine** mit eigenem `_stop_event` und `_lock`: Notwendig für Thread‑Safety, kein Overengineering.
- **Frequenz‑Recheck** alle 4 Blöcke: Könnte einfacher sein (z.B. nur bei QSO‑Ende oder gar nicht), aber Mike’s Spec verlangt es. **Beibehalten**.

**Vereinfachungspotential:**
- **Caller‑Queue‑Integration** (L10): Könnte man auch komplett weglassen und behaupten, dass OMNI keine Caller‑Queue unterstützt. Mike hat aber keine gegenteilige Aussage gemacht. Für KISS wäre das einfacher. **Aber**: Mike erwartet, dass die Queue auch unter OMNI funktioniert (HISTORY zeigt, dass sie existiert). Also bleiben lassen.
- **Timing‑Marge**: Statt `_OMNI_TX_PRELEAD_S = 2.0` (statt 1.5) erhöhen – einfache Konstante, kein Architektur‑Eingriff.

**Fazit**: Der Plan ist hinreichend KISS. Keine gravierenden Overengineering‑Punkte.

---

### Ergebnisse des Race‑Audits (Zusammenfassung)

| ID | Schweregrad | Befund | Empfohlene Massnahme |
|----|-------------|--------|----------------------|
| R1 | ⛔ KRITISCH | Timing‑Marge 0.2 s zu knapp → Pattern‑Drift bei OS‑Delay >0.2 s | `_OMNI_TX_PRELEAD_S` auf 2.0 erhöhen (Marge 0.7 s) |
| R2 | ⛔ KRITISCH | Listener‑Pfad setzt `encoder.tx_even` nicht vor `start_qso` → falsche Slot‑Parität | Vor `start_qso` `encoder.tx_even = not msg.is_even` setzen (oder aus `msg._tx_even`) |
| R3 | ⚠️ SOLLTE | `resume_after_qso` ohne join des alten Workers → könnte auf laufenden Worker treffen | `resume_after_qso` sollte `_thread.join()` aufrufen, falls Worker noch lebt |
| R4 | ⚠️ SOLLTE | `_omni_was_active_pre_qso` wird bei Stop nicht invalidiert → Caller‑Queue‑Risiko | In `_on_omni_stopped` explizit `self._omni_was_active_pre_qso = False` setzen (V1 enthält das bereits) |
| R5 | ⚠️ SOLLTE | Zweite Antwort in einem RX‑Slot wird komplett ignoriert | Dokumentieren; ggf. später in Caller‑Queue aufnehmen |

---

### Abschliessende Empfehlung

🟡 **„Plan braucht V3‑Anpassungen (Liste folgt)"**

Die Architektur ist grundsätzlich solide, aber es gibt **zwei kritische Lücken** (R1: Timing‑Marge, R2: fehlender `encoder.tx_even`‑Set im Listener) und **eine wichtige** (R3: `resume_after_qso`‑Join). Diese müssen vor der Mike‑Freigabe behoben werden.

**Empfohlene V3‑Aufgaben (vor Compact):**
1. `_OMNI_TX_PRELEAD_S` von 1.5 s auf **2.0 s** erhöhen.
2. Im Listener‑Pfad (`mw_cycle.on_message_decoded`) **vor** `start_qso` den `encoder.tx_even` auf die Gegenparität der eingehenden Nachricht setzen (z.B. `encoder.tx_even = not msg.is_even` – dazu muss `FT8Message` eine `is_even`‑Property haben oder aus `msg._tx_even` extrahiert werden).
3. `resume_after_qso` um einen Join des alten Workers ergänzen (falls noch nicht terminiert).
4. In `_on_omni_stopped` sicherstellen, dass `_omni_was_active_pre_qso` auf `False` gesetzt wird (V1 enthält das, im konkreten Code prüfen).
5. Timing‑Marge‑Test ergänzen (z.B. Sleep‑Verzögerung simulieren).
6. Test für mehrere Antworten in einem Slot dokumentieren (akzeptiertes Verhalten).

Nach diesen Anpassungen ist der Plan bereit für die Konsolidierung und Mike‑Freigabe.
