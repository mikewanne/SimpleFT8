# P1.9 Fix-Plan — V3 (final, Mike-vorlage-fertig)

**Status:** V3 = V1 + alle V2-Findings (12) + R1-Bestaetigung. R1 hat alle
6 Pruefauftraege als KORREKT bewertet, KEINE neuen Findings, KEINE vergessene
Doku. V3 ist die Implementations-Vorlage.

**Workflow-Stand:** V1 ✅ (756 Zeilen Plan, 4 Code-Aenderungen)
→ V2 ✅ (12 Findings A-L, davon 9 ⛔ kritisch)
→ R1 ✅ (Pruefauftraege 1-6 KORREKT, keine NEUE FINDINGS)
→ V3 (diese Datei) → Mike-Freigabe → Code.

**Ausgangs-Stand:** v0.95.2 (Tests 759 gruen). **Ziel:** v0.95.3.
**Commit-Aufteilung:** 1 Code-Commit (5 Dateien) + 1 Doku-Commit.

---

## 0. Bug-Diagnose (Kurz)

CQ-Worker schlaeft mit der CQ-Message bis `boundary - 1.3s`. Decoder wacht
`slot + 13.5s`, ist 0.5-3s spaeter fertig. Reply von DA1TST kommt typisch
wenn CQ-Audio bereits in `send_audio` (BLOCKING) laeuft → Report landet 1
Slot zu spaet. Reproduzierbar (4× Mike-Field-Test 05.05.).

**Wurzel:** Decoder-Encoder-Timing-Race. Encoder haelt CQ-Message in
Worker-Local — State-Update aendert daran nichts. Loesung muss BEIDES
korrigieren: (a) Decoder muss frueher fertig sein UND (b) Encoder muss
Replace-Mechanik haben.

---

## 1. Akzeptanzkriterien (V3 — finale Liste)

1. DA1TST-Reply im SELBEN Slot wo CQ scheduled war (Report :06:00 statt
   :06:30).
2. Bei zu spaetem Decoder (decode > 1.0s, Audio bereits gestartet): Status
   quo (1 Slot Delay), kein Crash, kein Doppel-TX.
3. State-Konsistenz nach Replace: TX_REPORT + `qso`-Daten + `_pending_reply=None`
   + **`_was_cq=True`** (V2 FINDING-A).
4. `encoder.tx_even` ist gesetzt **BEVOR** `request_replace` aufgerufen wird
   (V2 FINDING-D — Race-Vermeidung).
5. QSO-Panel zeigt „Antworte X (ANT...)" identisch zu `_process_cq_reply`-
   Pfad (V2 FINDING-C).
6. `qso_debug.log` enthaelt P1.9-Replace-Eintraege analog zu
   `_process_cq_reply` (V2 FINDING-B).
7. Bei Encode-Failure im Replace-Loop emittet Encoder `tx_finished` damit
   State sauber durchlaeuft (V2 FINDING-F).
8. Tests 759 → 764 gruen (3 Encoder + 2 SM-Tests).
9. Stats-Bias 0 — kein Mess- oder Logging-Pfad veraendert.
10. SNR-Effekt durch Decoder-Wake-Aenderung < 0.1 dB (R1-Pruefauftrag 1
    bestaetigt).

---

## 2. Code-Aenderungen (final mit allen V2-Findings)

### 2.1 `core/decoder.py:138` — Wake-Offset 1.5 → 2.5

```diff
-                _WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
+                # P1.9 Fix: FT8 wake 1s frueher (slot+12.5 statt slot+13.5),
+                # damit Decoder typisch 0.5-2.5s VOR Encoder-Wake fertig ist.
+                # Macht Encoder-Replace-Pfad ueberhaupt erst nutzbar.
+                # SNR-Effekt < 0.1 dB (R1: FT8-Signal endet bei slot+13.14s,
+                # Hanning-Fenster dampft Rand). FT4/FT2 unveraendert.
+                _WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
```

### 2.2 `core/encoder.py` — Replace-API + Worker-Loop

#### 2.2a `__init__` erweitern (nach Zeile 61)

```diff
         self._abort_event = threading.Event()
+        # P1.9 Fix: Replace-Mechanik fuer CQ → Report im selben Slot.
+        # _audio_started: True ab Audio-Start (point of no return).
+        # _replace_message: neue Message die request_replace einreiht.
+        # _replace_lock: schuetzt _audio_started + _replace_message gegen
+        #                Race zwischen request_replace() und Worker-Wake.
+        self._audio_started = False
+        self._replace_message: str | None = None
+        self._replace_lock = threading.Lock()
```

#### 2.2b Neue Methode `request_replace` (nach `abort()`, ~Zeile 81)

```python
    def request_replace(self, message: str) -> bool:
        """P1.9 Fix: laufenden TX mit neuer Message ersetzen waehrend Sleep.

        Returns True wenn Replace eingereiht wurde, False wenn zu spaet
        (Audio bereits gestartet) oder kein TX laeuft.

        Race-Sicherheit: Lock + is_transmitting-Guard + atomare
        _audio_started-Pruefung verhindern Replace nach send_audio-Start.
        """
        with self._replace_lock:
            if not self._is_transmitting:
                return False
            if self._audio_started:
                return False
            self._replace_message = message
            self._abort_event.set()
            return True
```

#### 2.2c `_tx_worker` Reset-Logik (Zeile 159-167)

```diff
     def _tx_worker(self, message: str):
         """TX-Worker: Timing → PTT → Audio via VITA-49 → PTT off."""
         self._is_transmitting = True
         # v0.80 Fix A2: Event vor jedem TX zuruecksetzen
         self._abort_event.clear()
+        # P1.9 Fix: Replace-State pro TX-Zyklus zuruecksetzen.
+        self._audio_started = False
+        with self._replace_lock:
+            self._replace_message = None
         try:
             self._tx_worker_inner(message)
         finally:
             self._is_transmitting = False
+            self._audio_started = False
```

#### 2.2d `_tx_worker_inner` Loop (Zeile 198-230 ersetzen)

```python
    def _tx_worker_inner(self, message: str):
        # FESTE TX-Frequenz
        print(f"[TX] Frequenz: {self.audio_freq_hz} Hz → '{message}'")

        # P1.9: Loop ermoeglicht Re-Encode bei Replace-Request waehrend Sleep.
        while True:
            # 1. Audio codieren (re-codiert nach Replace mit neuer Message)
            audio_12k = self.encode_message(message)
            if audio_12k is None:
                # V2 FINDING-F: tx_finished MUSS feuern damit qso_state
                # nicht in TX_REPORT haengt. Invariant: jeder TX-Versuch endet
                # mit tx_finished.
                self.tx_finished.emit()
                return
            if len(audio_12k) > TRIM_SAMPLES:
                audio_12k = audio_12k[:-TRIM_SAMPLES]

            # 2. Naechste passende Slot-Grenze berechnen
            next_boundary = self._next_slot_boundary()

            # 3. Sleep bis Slot-Grenze. _abort_event weckt auf bei abort()
            #    ODER bei request_replace().
            sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
            if sleep_dur > 0.001:
                aborted = self._abort_event.wait(timeout=sleep_dur)
                if aborted:
                    # P1.9: Replace eingereiht? → re-encode + neuer Loop-Durchgang
                    with self._replace_lock:
                        if self._replace_message is not None:
                            message = self._replace_message
                            self._replace_message = None
                            self._abort_event.clear()
                            print(f"[Encoder] TX-Replace → '{message}'")
                            continue
                    print("[Encoder] TX abgebrochen (während Warte-Phase)")
                    return

            # Abort-Check ohne Sleep (sleep_dur <= 0.001)
            if not self._is_transmitting:
                print("[Encoder] TX abgebrochen (vor Sleep)")
                return

            # 4. Audio-Start vorbereiten — point of no return.
            #    _audio_started=True UNTER Lock setzen, damit ein gleichzeitig
            #    laufendes request_replace() entweder noch erfolgreich ist
            #    oder sauber False zurueckgibt. Kein Mid-State.
            with self._replace_lock:
                self._audio_started = True
            break  # raus aus dem while-Loop, weiter mit Audio-Send

        # ── ab hier UNVERAENDERT zur v0.95.2-Version ────────────────
        # 4. Silence-Padding berechnen ...
        now = time.time()
        # ... (Drift-Guard, Audio-Build, PTT, send_audio, tx_finished)
```

Konkret bedeutet das: Zeilen 198-230 in encoder.py werden durch obigen
Block ersetzt. Zeile 232 (`now = time.time()`) und alles danach bleibt
1:1.

### 2.3 `core/qso_state.py` — Signal + Defense-in-Depth + Trigger

#### 2.3a Neues Signal (nach Zeile 102)

```diff
     queue_changed = Signal(list)    # Warteliste geändert → UI aktualisieren
+    try_replace_pending_tx = Signal(object)  # P1.9: CQ-Reply waehrend CQ_CALLING
+                                              # → mw_qso versucht Encoder-Replace
```

#### 2.3b Defense-in-Depth in `_send_cq()` (Zeile 158-164)

```diff
     def _send_cq(self):
         """CQ-Ruf senden."""
+        # P1.9 Defense-in-Depth: falls _pending_reply bereits gesetzt ist
+        # (Race: Replace-Request kam zu spaet aber Reply ist gemerkt),
+        # direkt Reply verarbeiten statt nochmal CQ zu senden.
+        if self._pending_reply is not None:
+            print(f"[QSO] _send_cq: pending {self._pending_reply.caller} → process statt CQ")
+            self._process_cq_reply()
+            return
         self._pending_reply = None  # Alte Antwort verwerfen
         msg = f"CQ {self.my_call} {self.my_grid}"
         self._dbg.log("TX", f"Sende: '{msg}'")
         self._set_state(QSOState.CQ_CALLING)
         self.send_message.emit(msg)
```

#### 2.3c `on_message_received` Trigger (Zeile 455-465)

```diff
         # ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
         if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
             if msg.is_grid or msg.is_report:
                 # Antwort merken — wird in on_message_sent() verarbeitet
                 # (falls CQ TX noch laeuft, darf JETZT nicht gesendet werden!)
                 self._pending_reply = msg
                 print(f"[QSO] Antwort von {msg.caller} gemerkt (State={self.state.name})")
                 # Wenn CQ_WAIT oder IDLE: sofort verarbeiten (TX ist frei)
                 if self.state in (QSOState.IDLE, QSOState.CQ_WAIT):
                     self._process_cq_reply()
+                # P1.9: Bei CQ_CALLING (TX laeuft) versuche Replace im
+                # Encoder-Sleep. Falls erfolgreich: mw_qso schaltet direkt
+                # auf TX_REPORT um. Falls zu spaet: on_message_sent
+                # verarbeitet das pending nach TX-Ende (Status quo).
+                elif self.state == QSOState.CQ_CALLING:
+                    self.try_replace_pending_tx.emit(msg)
                 # Bei CQ_CALLING: on_message_sent() verarbeitet es nach TX-Ende
                 return
```

### 2.4 `ui/mw_qso.py` — Slot-Handler (mit allen V2-Findings A, B, C, D)

Neuer Slot-Handler nach `_on_tx_slot_for_partner` (vor `_on_qso_tab_changed`):

```python
    @Slot(object)
    def _on_try_replace_pending_tx(self, msg):
        """P1.9: CQ-Reply waehrend CQ_CALLING → versuche Encoder-Replace.

        Wenn erfolgreich: state direkt zu TX_REPORT, Encoder sendet Report
        im selben Slot statt erst nach CQ-Ende.
        Wenn zu spaet (Audio bereits gestartet): kein State-Wechsel,
        on_message_sent verarbeitet pending nach TX-Ende (Status quo).
        """
        from core.qso_state import QSOData, QSOState
        import time

        # Nur Grid-Replies haben sofortigen Report (R+Report waere zu spaet
        # im QSO-Flow; das verarbeitet weiterhin _process_cq_reply nach TX).
        if not msg.is_grid:
            return

        # Report-Format identisch zu _process_cq_reply (Zeile 201)
        snr = self.qso_sm._last_snr
        report = f"{snr:+03d}" if snr > -30 else "-10"
        tx_msg = f"{msg.caller} {self.qso_sm.my_call} {report}"

        # V2 FINDING-D: tx_even MUSS vor request_replace gesetzt werden,
        # damit der Worker beim Wake _next_slot_boundary() mit korrektem
        # Wert aufruft.
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even

        if not self.encoder.request_replace(tx_msg):
            return  # zu spaet — Status quo Pfad uebernimmt

        # Replace eingereiht → State analog _process_cq_reply
        self.qso_sm._pending_reply = None
        self.qso_sm._was_cq = True  # V2 FINDING-A: CQ-Resume nach QSO
        self.qso_sm.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
            our_snr=report,
        )
        # V2 FINDING-B: Debug-Log analog _process_cq_reply
        self.qso_sm._dbg.reset(msg.caller)
        self.qso_sm._dbg.log("RX", f"P1.9 Replace: CQ-Antwort von {msg.caller}: '{msg.raw}'")
        self.qso_sm._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
        self.qso_sm._set_state(QSOState.TX_REPORT)
        # V2 FINDING-C: QSO-Panel-Anzeige analog _on_tx_slot_for_partner
        label = self._antenna_pref_label(msg.caller)
        if label:
            self.qso_panel.add_info(f"Antworte {msg.caller}{label}")
        # ACHTUNG: KEIN send_message.emit — Encoder hat die Message bereits
        # ueber _replace_message bekommen.
        print(f"[QSO] P1.9 Replace OK: CQ → '{tx_msg}'")
```

### 2.5 `ui/main_window.py:543` — Connect

V2 FINDING-E verifiziert: `self.qso_sm.tx_slot_for_partner.connect(self._on_tx_slot_for_partner)`
liegt in `ui/main_window.py:543`. Direkt darunter neuen Connect:

```diff
         self.qso_sm.tx_slot_for_partner.connect(self._on_tx_slot_for_partner)
+        # P1.9: CQ-Reply waehrend CQ_CALLING → Encoder-Replace versuchen
+        self.qso_sm.try_replace_pending_tx.connect(self._on_try_replace_pending_tx)
```

### 2.6 `main.py` — APP_VERSION

```diff
-APP_VERSION = "0.95.2"
+APP_VERSION = "0.95.3"
```

---

## 3. Tests (5 final)

Datei: neue `tests/test_p1_9_replace.py` (sauberer als bestehende
`test_modules.py` zu verlaengern).

### Test 1: `request_replace` waehrend Sleep erfolgreich

```python
def test_encoder_request_replace_during_sleep():
    """P1.9: Replace setzt _replace_message + weckt Worker via abort_event."""
    from core.encoder import Encoder
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is True
    assert enc._replace_message == "DA1TST DA1MHH -10"
    assert enc._abort_event.is_set()
```

### Test 2: `request_replace` zu spaet (Audio gestartet)

```python
def test_encoder_request_replace_too_late():
    """P1.9: Replace nach _audio_started=True wird abgelehnt."""
    from core.encoder import Encoder
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = True
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
    assert enc._replace_message is None
```

### Test 3: `request_replace` ohne TX

```python
def test_encoder_request_replace_no_tx():
    """P1.9: Replace ohne laufenden TX → False."""
    from core.encoder import Encoder
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
```

### Test 4: Defense-in-Depth in `_send_cq()` (V2 FINDING-G)

```python
def test_send_cq_with_pending_reply_processes_instead():
    """P1.9 Defense-in-Depth: _send_cq mit pending → process statt CQ."""
    from core.qso_state import QSOStateMachine, QSOState
    from core.message import FT8Message
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    msg = FT8Message(raw="DA1MHH DA1TST JN66", target="DA1MHH",
                     caller="DA1TST", grid_or_report="JN66",
                     is_grid=True, snr=-15, freq_hz=1500)
    sm._pending_reply = msg
    captured = []
    sm.send_message.connect(captured.append)
    sm._send_cq()
    assert any("DA1TST DA1MHH" in m for m in captured), \
        "Erwartet Report-TX, nicht CQ-TX"
    assert sm._pending_reply is None
    assert sm.state == QSOState.TX_REPORT
```

### Test 5: `try_replace_pending_tx` Signal-Trigger (V2 FINDING-H)

```python
def test_cq_calling_grid_reply_emits_try_replace():
    """P1.9: CQ_CALLING + Grid-Reply → try_replace_pending_tx Signal."""
    from core.qso_state import QSOStateMachine, QSOState
    from core.message import FT8Message
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_CALLING)
    captured = []
    sm.try_replace_pending_tx.connect(captured.append)
    msg = FT8Message(raw="DA1MHH DA1TST JN66", target="DA1MHH",
                     caller="DA1TST", grid_or_report="JN66",
                     is_grid=True, snr=-15, freq_hz=1500)
    sm.on_message_received(msg)
    assert len(captured) == 1
    assert captured[0] is msg
    assert sm._pending_reply is msg  # weiter gemerkt fuer Fallback
```

**Bestehende Tests pruefen:** V2 FINDING-I — `test_qso_cq_reply_during_tx_pending_then_processed`
darf nicht brechen. Manuelle Pruefung dass kein `assert` auf abwesende Signale.

**Erwartung:** 759 → 764 Tests gruen.

---

## 4. Atomare Commit-Aufteilung

R1-Empfehlung: 1 Code-Commit + 1 Doku-Commit.

### Commit 1 — Code (5 Dateien + neue Test-Datei)

```
P1.9 Fix: CQ-Reply im selben Slot via Decoder-Wake + Encoder-Replace

Bug: Decoder-Encoder-Race fuehrte zu 1-Slot-Verzoegerung beim ersten
Reply auf CQ. Encoder wachte 0.2-3.0s VOR Decoder fertig → CQ-Audio
bereits in send_audio (BLOCKING) wenn _pending_reply gesetzt wurde.
Reproduzierbar (4× Field-Test 05.05. Mike).

Fix (atomare Kombination):
- core/decoder.py:138 — _WAKE_OFFSETS["FT8"] 1.5 → 2.5 (Decoder ready
  0.5-2.5s VOR Encoder-Wake). SNR-Effekt < 0.1 dB (R1).
- core/encoder.py — request_replace API + Loop in _tx_worker_inner
  fuer Re-Encode + _audio_started/_replace_message/_replace_lock
  + tx_finished.emit im Encode-Fehler-Pfad (V2 FINDING-F).
- core/qso_state.py — Signal try_replace_pending_tx + Emit in
  on_message_received bei CQ_CALLING + Defense-in-Depth in _send_cq().
- ui/mw_qso.py — _on_try_replace_pending_tx Slot mit tx_even-vor-
  request_replace (V2 FINDING-D), _was_cq=True (FINDING-A),
  Debug-Log (FINDING-B), QSO-Panel-Anzeige (FINDING-C).
- ui/main_window.py:543 — Connect.
- tests/test_p1_9_replace.py NEU — 5 Tests (3 Encoder + 2 SM).

Tests 759 → 764 gruen.

Voller V1→V2(12 Findings A-L)→R1(6 Pruefauftraege KORREKT, keine
neuen Findings)→V3 Workflow.
```

Geaenderte Dateien:
- `core/decoder.py`
- `core/encoder.py`
- `core/qso_state.py`
- `ui/mw_qso.py`
- `ui/main_window.py`
- `main.py` (APP_VERSION)
- `tests/test_p1_9_replace.py` (NEU)

### Commit 2 — Doku

```
docs: v0.95.3 Stand + HANDOFF/CLAUDE/HISTORY/TODO update nach P1.9-Fix
```

Geaenderte Dateien:
- `HISTORY.md` (neuer v0.95.3-Eintrag prepended)
- `HANDOFF.md` (beide Pfade SimpleFT8/ + FT8/ identisch)
- `CLAUDE.md` (beide Pfade — Header-Block prepended)
- `TODO.md` (P1.9 → ✅)

R1-Bestaetigung Pruefauftrag 6: keine vergessene Doku-Stelle.

---

## 5. Doku-Update-Reihenfolge (CLAUDE.md PFLICHT)

1. **HISTORY.md** — v0.95.3-Eintrag prepended:

```markdown
## 2026-05-05 v0.95.3 — P1.9 First-Reply-Lost-Bug-Fix

**Atomare Commits:** [HASH-CODE] (Code+Tests) + [HASH-DOKU] (Doku).
**Wurzel:** Decoder-Encoder-Timing-Race (FlexRadio TX-Buffer 1.3s).
Encoder wakes 0.2-3.0s VOR Decoder fertig → CQ-Audio bereits in
send_audio (BLOCKING) wenn _pending_reply gesetzt wurde → 1 Slot
Verzoegerung beim ersten Reply, eine ueberfluessige CQ. Reproduzierbar
(4× Mike-Field-Test 05.05.).

**Fix-Kombination (1 atomarer Commit):**
- core/decoder.py:138 — _WAKE_OFFSETS["FT8"] 1.5 → 2.5
- core/encoder.py — request_replace API + Replace-Loop +
  tx_finished.emit im Encode-Fehler-Pfad
- core/qso_state.py — try_replace_pending_tx Signal +
  Defense-in-Depth in _send_cq
- ui/mw_qso.py — _on_try_replace_pending_tx Slot
- ui/main_window.py:543 — Connect

**Voller V1→V2→R1→V3 Workflow.** V2 fand 12 Findings A-L (9 kritisch
+ 3 Tests + 0 kleine), R1 bestaetigte alle 6 Pruefauftraege als
KORREKT mit Hinweis auf gleichen Encode-Bug im Nicht-Replace-Pfad
(separater Fix). Tests 759 → 764 gruen (3 Encoder + 2 SM).
```

2. **HANDOFF.md** (beide Pfade SimpleFT8/HANDOFF.md + FT8/HANDOFF.md):
   - Header: „**Stand 2026-05-05:** **v0.95.3 — P1.9-Fix.**"
   - P1.9-Eintrag im OFFEN-Block ENTFERNEN (war 🔴, jetzt ✅)
   - Neuer ✅-Eintrag oben analog „✅ P1.5 Field-Test BESTAETIGT"

3. **CLAUDE.md** (beide Pfade SimpleFT8/CLAUDE.md + FT8/CLAUDE.md):
   - Header `**Aktueller Stand:**` Block prepended mit v0.95.3-Eintrag
   - Test-Count `759 passed` → `764 passed`

4. **TODO.md**:
   - P1.9-Block → ✅ markieren mit Datum + Commit-Hash + Test-Count

5. **Memory:** keine neue Lesson noetig — V1→V2→R1→V3 lief sauber.

---

## 6. Risiko-Analyse (V3 — final)

| Risiko | Wahrscheinlichkeit | Wirkung | Mitigation |
|---|---|---|---|
| SNR-Verlust durch Wake-Offset 2.5 | gering | <0.1 dB Schwelle (R1) | Field-Test 1 Tag, Stats-Vergleich vor/nach |
| Race im _replace_lock bei 2 Replace-Requests | sehr gering | nur erstes Replace gewinnt | Lock + Set-Once-Logik |
| Worker im Audio-Start-Race | gering | Lock umfasst Audio-Start | atomare with-Klammer (2.2d) |
| Re-Encode-Failure → State-Hang | sehr gering | tx_finished feuert sauber | V2 FINDING-F |
| `_replace_message` ueberlebt TX-Ende | sehr gering | naechstes _tx_worker resettet | 2.2c Reset-Logik |
| Tests brechen (P1.5 + Encoder) | gering | API-additiv, keine Breaking-Changes | `pytest -q` vor Commit |
| State-Inkonsistenz nach Replace | sehr gering | Slot-Handler analog _process_cq_reply | V2 FINDING-A/B/C/D abgedeckt |
| Replace bei R-Report (statt Grid) | gering | falscher TX | Slot-Handler `if not msg.is_grid: return` |
| tx_even-Race im Slot-Handler | gering nach Fix | Worker liest falschen Slot | V2 FINDING-D — tx_even VOR request_replace |
| `_was_cq` nicht gesetzt → kein CQ-Resume | gering nach Fix | CQ haengt in IDLE | V2 FINDING-A behoben |

---

## 7. Rollback-Plan

Wenn Field-Test einen Folgebug zeigt:

1. `git revert [HASH-CODE]` — atomarer Revert moeglich (1 Commit).
2. `APP_VERSION` zurueck auf "0.95.2" + Doku zurueck.
3. Field-Test mit v0.95.2 — sicher dass das bekannte 1-Slot-Delay-
   Symptom dort keine neuen Bugs hat.

---

## 8. Field-Test-Protokoll (Mike)

- 30m FT8 mit DA1TST am IC-7300.
- DA1TST ruft uns waehrend wir CQ senden.
- Erwartung NACH Fix: Report im SELBEN Slot wie CQ scheduled war (statt
  +1 Slot).
- Visuell: QSO-Panel zeigt CQ-Slot direkt gefolgt von Report-Slot,
  KEINE „CQ"-Wiederholung dazwischen.
- Logs sammeln: `[Encoder] TX-Replace →` und `[QSO] P1.9 Replace OK:`
  → Erfolgs-Quote ueber 5-10 QSOs.
- Falls Replace zu spaet (Decoder > 1.0s): Status quo Pfad, kein Crash.

---

## 9. Workflow-Status

- [x] Schritt 0 Code-Verifikation
- [x] V1 (24 KB)
- [x] V2 — Self-Review (12 Findings A-L)
- [x] R1 — DeepSeek-Reasoner (6 Pruefauftraege KORREKT, keine NEUE FINDINGS)
- [x] V3 (diese Datei)
- [ ] **Mike-Freigabe**
- [ ] Code-Implementation (1 Commit)
- [ ] Doku-Implementation (1 Commit)
- [ ] Field-Test Mike

---

## 10. Mike-Freigabe-Frage

Plan ist implementations-bereit. Drei kompakte Eckpunkte zur Bestaetigung:

1. **Strategie:** 1 atomarer Code-Commit (5 Dateien + neue Test-Datei) +
   1 Doku-Commit. Atomar weil Option C alleine den Bug nicht fixt.

2. **Risiko-Profil:** keine Breaking-Changes. SNR-Effekt <0.1 dB.
   Worst-Case bei Race: Status quo (1 Slot Delay, Code v0.95.2-Verhalten).

3. **Test-Coverage:** 759 → 764 (3 Encoder-API + 2 SM-Logik). UI-Slot-Handler
   nicht direkt getestet (UI-Code), aber alle 4 Effekte abgedeckt.

**Bereit fuer Implementation?** Wenn ja → atomare Commits + Field-Test.

---

**V3 Ende.**
