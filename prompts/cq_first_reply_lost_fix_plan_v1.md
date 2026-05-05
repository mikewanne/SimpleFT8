# P1.9 Fix-Plan — V1 (CQ First-Reply-Lost-Bug)

**Status:** V1 — wird in V2 selbst-reviewed, dann an R1, dann V3, dann Mike-Freigabe.
**Ausgangs-Stand:** v0.95.2 (Commit `43dd062` + Doku-Commit, Tests 759 gruen).
**Ziel-Version:** v0.95.3 — 1 atomarer Code-Commit + 1 Doku-Commit.
**Workflow-Prerequisites:** Compact-Notes `prompts/p1_9_compact_notes.md`,
Diagnose `prompts/cq_first_reply_lost_v{1,2,3}.md`. R1-Bewertung dort
abgeschlossen (6 Pruefauftraege bestaetigt + 3 Verbesserungen).

---

## 0. Code-Verifikation (Schritt 0 nach docs/WORKFLOW.md)

Alle Ziel-Stellen wurden vor Plan-Erstellung mit `Read`-Tool gegen Codebase
verifiziert. Zeilennummern stimmen mit aktuellem Stand v0.95.2 ueberein:

| Datei | Zeile(n) | Aktueller Code | Status |
|---|---|---|---|
| `core/decoder.py` | 138 | `_WAKE_OFFSETS = {"FT8": 1.5, ...}` | ✓ |
| `core/encoder.py` | 45 | `tx_started = Signal(str, bool, float)` | ✓ |
| `core/encoder.py` | 49-61 | `__init__` mit `_abort_event` | ✓ |
| `core/encoder.py` | 159-167 | `_tx_worker` mit `_abort_event.clear()` | ✓ |
| `core/encoder.py` | 198-296 | `_tx_worker_inner` (Sleep + send_audio) | ✓ |
| `core/qso_state.py` | 95-102 | Signals-Block | ✓ |
| `core/qso_state.py` | 158-164 | `_send_cq()` setzt `_pending_reply = None` | ✓ |
| `core/qso_state.py` | 455-465 | `on_message_received` CQ-Reply-Branch | ✓ |
| `ui/mw_qso.py` | (Connect) | Encoder-Signals werden in `main_window` connected | ✓ |

---

## 1. Bug-Diagnose (Kurzfassung — Detail in Compact-Notes)

**Symptom:** 4× heute reproduziert. CQ → DA1TST ruft im Folgeslot → wir senden
nochmal CQ statt Report → DA1TST wiederholt → erst dann Report. 1 Slot Delay.

**Wurzel:** Decoder-Encoder-Race. Encoder wacht `boundary - 1.3s` (FlexRadio-
Buffer). Decoder wacht `slot + 13.5s`, ready 0.5–3.0s spaeter. Encoder ist 0.2–
3.0s VOR Decoder fertig → CQ-Audio bereits in `send_audio` (BLOCKING) wenn
`_pending_reply` gesetzt wird. State-Update aendert nichts mehr an laufendem
TX, weil Encoder die CQ-Message in lokaler Variable des Workers haelt.

**Akzeptanzkriterien:**
1. DA1TST-Reply im SELBEN Slot wo wir die CQ scheduled hatten — Report :06:00
   statt :06:30 (1 Slot frueher).
2. Bei zu spaetem Decoder (decode > 1s, Audio bereits gestartet): Status quo
   — kein Crash, kein doppelter TX, kein verlorener Reply.
3. State-Konsistenz: nach erfolgreichem Replace ist `qso_state` exakt im
   Zustand wo `_process_cq_reply()` ihn gehabt haette (`TX_REPORT`, `qso`-
   Daten gesetzt, `_pending_reply = None`, `tx_even` korrigiert).
4. Tests 759 → ≥762 gruen (3 neue P1.9-Tests).
5. Stats-Bias 0 — kein Mess- oder Logging-Pfad veraendert.

---

## 2. Fix-Strategie — Kombination C + A in 1 atomarem Commit

R1-Empfehlung (Pruefauftrag 6): **1 Commit, nicht 2** — weil Option C alleine
den Bug NICHT fixt (R1 + V3 verifiziert: Encoder schlaeft mit der CQ-Message
in der Worker-Local, ein State-Update aendert daran nichts). Trennung in 2
Commits wuerde einen Zwischenstand erzeugen wo der Bug sichtbar bleibt
obwohl ein Code-Schritt drin ist. Atomare Auslieferung sauberer.

### 2.1 Schritt C — Decoder-Wake 1.5 → 2.5 (`core/decoder.py:138`)

```diff
-                _WAKE_OFFSETS = {"FT8": 1.5, "FT4": 0.5, "FT2": 0.3}
+                # P1.9 Fix: FT8 wake 1s frueher (slot+12.5 statt slot+13.5),
+                # damit Decoder typisch 0.5-2.5s VOR Encoder-Wake fertig ist.
+                # Macht Encoder-Replace-Pfad ueberhaupt erst nutzbar.
+                # SNR-Effekt < 0.1 dB (R1, FT8-Signal endet bei slot+13.14s,
+                # Hanning-Fenster dampft Rand). FT4/FT2 unveraendert.
+                _WAKE_OFFSETS = {"FT8": 2.5, "FT4": 0.5, "FT2": 0.3}
```

**Wirkung:** Decoder ready 0.5–2.5s VOR Encoder-Wake (statt danach). Damit
ist das Replace-Window oft offen wenn `_pending_reply` gesetzt wird.

**Risiko:** SNR-Schwellen-Verschiebung. R1 quantifiziert <0.1 dB praktisch
verlustfrei (FT8-Signal endet bei `slot+0.5+12.64=13.14s`, neuer Wake-Punkt
liegt bei `slot+12.5s`, Differenz 0.64s am Signal-Ende wo Hanning-Fenster
bereits dampft). Stats-Sammlung Field-Test verifiziert.

### 2.2 Schritt A — Encoder-Replace-API (`core/encoder.py`)

#### 2.2a `__init__` erweitern (nach Zeile 61 `_abort_event = threading.Event()`)

```diff
         self._abort_event = threading.Event()
+        # P1.9 Fix: Replace-Mechanik fuer CQ → Report im selben Slot.
+        # _audio_started: True ab dem Moment wo send_audio gleich startet
+        #                 (point-of-no-return — kein Replace mehr moeglich).
+        # _replace_message: neue Message die request_replace() einreiht.
+        # _replace_lock: schuetzt _audio_started + _replace_message gegen
+        #                Race zwischen request_replace() und Worker-Wake.
+        self._audio_started = False
+        self._replace_message: str | None = None
+        self._replace_lock = threading.Lock()
```

#### 2.2b Neue Methode `request_replace` (nach `abort()` einfuegen, ~Zeile 81)

```python
    def request_replace(self, message: str) -> bool:
        """P1.9 Fix: laufenden TX mit neuer Message ersetzen waehrend Sleep.

        Returns True wenn Replace eingereiht wurde, False wenn zu spaet
        (Audio bereits gestartet) oder kein TX laeuft.

        Race-Sicherheit: Lock + is_transmitting-Guard (R1-Add) + atomare
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

#### 2.2c `_tx_worker` reset-Logik (Zeile 159-167)

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

#### 2.2d `_tx_worker_inner` Loop-Umbau (Zeile 198-296)

Kern-Aenderung: encode + sleep + audio in einer `while True`-Schleife,
sodass nach Wake aus `_abort_event.wait()` ein gepruefter Replace-Pfad zu
`continue` springen kann (re-encode mit neuer Message), waehrend ein
plain abort (kein Replace eingereiht) wie bisher mit `return` aussteigt.

```diff
     def _tx_worker_inner(self, message: str):
-        # FESTE TX-Frequenz
-        print(f"[TX] Frequenz: {self.audio_freq_hz} Hz → '{message}'")
-
-        # 1. Audio SOFORT codieren — unabhaengig vom Timing, kein GIL-Problem
-        audio_12k = self.encode_message(message)
-        if audio_12k is None:
-            return
-
-        # Trailing Silence trimmen (FT8-Nutzsignal ist 12.64s, Rest ist stille)
-        # slot+0.5 + 13.5s = slot+14.0s → 1.0s Puffer vor naechstem Slot
-        if len(audio_12k) > TRIM_SAMPLES:
-            audio_12k = audio_12k[:-TRIM_SAMPLES]
-
-        # 2. Naechste passende Slot-Grenze berechnen
-        next_boundary = self._next_slot_boundary()
-
-        # 3. Bis zur Slot-Grenze schlafen ...
-        sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
-        if sleep_dur > 0.001:
-            aborted = self._abort_event.wait(timeout=sleep_dur)
-            if aborted:
-                print("[Encoder] TX abgebrochen (während Warte-Phase)")
-                return
-
-        # Abort-Check: kann auch ohne Sleep auftreten (sleep_dur <= 0.001)
-        if not self._is_transmitting:
-            print("[Encoder] TX abgebrochen (vor Sleep)")
-            return
+        # FESTE TX-Frequenz
+        print(f"[TX] Frequenz: {self.audio_freq_hz} Hz → '{message}'")
+
+        # P1.9: Loop ermoeglicht Re-Encode bei Replace-Request waehrend Sleep.
+        while True:
+            # 1. Audio codieren (re-codiert nach Replace mit neuer Message)
+            audio_12k = self.encode_message(message)
+            if audio_12k is None:
+                return
+            if len(audio_12k) > TRIM_SAMPLES:
+                audio_12k = audio_12k[:-TRIM_SAMPLES]
+
+            # 2. Naechste passende Slot-Grenze berechnen
+            next_boundary = self._next_slot_boundary()
+
+            # 3. Sleep bis Slot-Grenze. _abort_event weckt auf bei abort()
+            #    ODER bei request_replace().
+            sleep_dur = (next_boundary + TARGET_TX_OFFSET - 0.5) - time.time()
+            if sleep_dur > 0.001:
+                aborted = self._abort_event.wait(timeout=sleep_dur)
+                if aborted:
+                    # P1.9: Replace eingereiht? → re-encode + neuer Loop-Durchgang
+                    with self._replace_lock:
+                        if self._replace_message is not None:
+                            message = self._replace_message
+                            self._replace_message = None
+                            self._abort_event.clear()
+                            print(f"[Encoder] TX-Replace → '{message}'")
+                            continue
+                    print("[Encoder] TX abgebrochen (während Warte-Phase)")
+                    return
+
+            # Abort-Check ohne Sleep (sleep_dur <= 0.001)
+            if not self._is_transmitting:
+                print("[Encoder] TX abgebrochen (vor Sleep)")
+                return
+
+            # 4. Audio-Start vorbereiten — point of no return.
+            #    _audio_started=True UNTER Lock setzen, damit ein gleichzeitig
+            #    laufendes request_replace() entweder noch erfolgreich ist
+            #    oder sauber False zurueckgibt. Kein Mid-State.
+            with self._replace_lock:
+                self._audio_started = True
+            break  # raus aus dem while-Loop, weiter mit Audio-Send
 
         # 4. Silence-Padding berechnen ...
         now = time.time()
```

Der Rest von `_tx_worker_inner` (ab Zeile 232 `now = time.time()`) bleibt
unveraendert. `silence_secs`-Berechnung, Drift-Guard, Audio-Build, PTT,
`tx_started.emit`, `send_audio`, `ptt_off`, `tx_finished.emit` — alles
bleibt wie es ist, weil es ausserhalb der Replace-Schleife laeuft.

### 2.3 Schritt B — State-Machine Signal + Defense-in-Depth (`core/qso_state.py`)

#### 2.3a Neues Signal (nach Zeile 102 `queue_changed = Signal(list)`)

```diff
     queue_changed = Signal(list)    # Warteliste geändert → UI aktualisieren
+    try_replace_pending_tx = Signal(object)  # P1.9: CQ-Reply waehrend CQ_CALLING
+                                              # → mw_qso versucht Encoder-Replace
```

#### 2.3b Defense-in-Depth in `_send_cq()` (Zeile 158-164)

R1-Empfehlung (Pruefauftrag 5): zusaetzlicher Sicherheitsgurt falls Replace-
Request den Encoder verfehlt aber `_pending_reply` schon gesetzt ist.

```diff
     def _send_cq(self):
         """CQ-Ruf senden."""
+        # P1.9 Defense-in-Depth: falls _pending_reply bereits gesetzt ist
+        # (Race: Replace-Request kam zu spaet, aber Reply ist gemerkt),
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

#### 2.3c `on_message_received` — Replace-Trigger im CQ_CALLING-Branch (Zeile 455-465)

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
+                # auf TX_REPORT um. Falls zu spaet: on_message_sent()
+                # verarbeitet das pending nach TX-Ende (Status quo Verhalten).
+                elif self.state == QSOState.CQ_CALLING:
+                    self.try_replace_pending_tx.emit(msg)
                 # Bei CQ_CALLING: on_message_sent() verarbeitet es nach TX-Ende
                 return
```

### 2.4 Schritt D — Slot-Handler in mw_qso.py

#### 2.4a Connect (in `main_window.py` wo `qso_sm`-Signals connected werden)

Die existierenden Connects sind in `main_window.py` (nicht in `mw_qso.py`).
Beim grep wo `qso_sm.tx_slot_for_partner.connect(...)` steht — neuen
`try_replace_pending_tx`-Connect dort daneben einfuegen. Ziel-Slot:
`self._on_try_replace_pending_tx`.

#### 2.4b Neuer Slot in `ui/mw_qso.py` (nach `_on_tx_slot_for_partner` einfuegen)

```python
    @Slot(object)
    def _on_try_replace_pending_tx(self, msg):
        """P1.9: CQ-Reply waehrend CQ_CALLING → versuche Encoder-Replace.

        Wenn erfolgreich: state direkt zu TX_REPORT (analog _process_cq_reply)
        und Encoder sendet sofort Report im selben Slot statt erst nach CQ.
        Wenn zu spaet (Audio gestartet): kein State-Wechsel, on_message_sent
        verarbeitet pending nach TX-Ende (Status quo).
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

        if not self.encoder.request_replace(tx_msg):
            return  # zu spaet — Status quo Pfad uebernimmt

        # Replace eingereiht → State direkt nach TX_REPORT umschalten
        self.qso_sm._pending_reply = None
        self.qso_sm.qso = QSOData(
            their_call=msg.caller,
            their_grid=msg.grid_or_report if msg.is_grid else "",
            freq_hz=msg.freq_hz,
            start_time=time.time(),
            our_snr=report,
        )
        # tx_even Gegentakt setzen (analog _on_tx_slot_for_partner)
        their_even = getattr(msg, '_tx_even', None)
        if their_even is not None:
            self.encoder.tx_even = not their_even
        self.qso_sm._set_state(QSOState.TX_REPORT)
        # ACHTUNG: KEIN send_message.emit — Encoder hat die Message bereits
        # ueber _replace_message bekommen, send_message-Pfad wuerde einen
        # zweiten transmit() ausloesen.
        print(f"[QSO] P1.9 Replace OK: CQ → '{tx_msg}'")
```

---

## 3. Tests (3 neu)

In `tests/test_modules.py` (oder neue Datei `tests/test_p1_9_replace.py`).

### Test 1: Replace gelingt waehrend Sleep

```python
def test_encoder_request_replace_during_sleep():
    """P1.9: Replace setzt _replace_message + weckt Worker via abort_event."""
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is True
    assert enc._replace_message == "DA1TST DA1MHH -10"
    assert enc._abort_event.is_set()
```

### Test 2: Replace verweigert nach Audio-Start

```python
def test_encoder_request_replace_too_late():
    """P1.9: Replace-Request nach _audio_started=True wird abgelehnt."""
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = True
    enc._audio_started = True
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
    assert enc._replace_message is None
```

### Test 3: Replace verweigert ohne aktiven TX

```python
def test_encoder_request_replace_no_tx():
    """P1.9: Replace-Request ohne laufenden TX → False."""
    enc = Encoder(audio_freq_hz=1500)
    enc._is_transmitting = False
    success = enc.request_replace("DA1TST DA1MHH -10")
    assert success is False
```

### Bestehende Tests die NICHT brechen duerfen

- `test_qso_known_station_can_call_again` (P1.5, v0.95.2)
- `test_qso_cq_reply_during_tx_pending_then_processed` (v0.95.2)
- `test_qso_caller_queue_accepts_known_station` (v0.95.2)
- `test_qso_resume_pops_known_station_from_queue` (v0.95.2)
- Encoder-Tests in `tests/test_encoder.py` (Wake-Offset 1.5 → 2.5 darf
  Encoder-Logik nicht beeinflussen — Encoder kennt `_WAKE_OFFSETS` nicht).

**Test-Erwartung:** 759 → 762 gruen (3 neue + 0 angepasst).

---

## 4. Atomare Commit-Aufteilung

R1-Empfehlung: **1 Code-Commit** (alle 4 Code-Dateien zusammen, weil Option C
alleine den Bug nicht fixt) + **1 Doku-Commit**.

### Commit 1 — Code

```
P1.9 Fix: CQ-Reply im selben Slot via Decoder-Wake + Encoder-Replace

Bug: Decoder-Encoder-Race fuehrte zu 1-Slot-Verzoegerung beim ersten
Reply. Encoder wachte 0.2-3.0s VOR Decoder fertig → CQ-Audio bereits
in send_audio (BLOCKING) wenn _pending_reply gesetzt wurde.

Fix (Kombination — atomar):
- core/decoder.py:138 — _WAKE_OFFSETS["FT8"] 1.5 → 2.5 (Decoder ready
  0.5-2.5s VOR Encoder-Wake). SNR-Effekt < 0.1 dB.
- core/encoder.py — request_replace(message) API + Loop in
  _tx_worker_inner fuer Re-Encode + _audio_started/_replace_message/
  _replace_lock.
- core/qso_state.py — Signal try_replace_pending_tx + Emit in
  on_message_received bei CQ_CALLING + Defense-in-Depth in _send_cq().
- ui/mw_qso.py — _on_try_replace_pending_tx Slot.

Tests 759 → 762 gruen (+3 P1.9-Tests, alle bestehenden bestehen).

Voller V1→V2→R1→V3 Workflow + R1-bestaetigte Plan-Reihenfolge
(1 Commit, weil Option C alleine den Bug nicht fixt).
```

Geaenderte Dateien: `core/decoder.py`, `core/encoder.py`,
`core/qso_state.py`, `ui/mw_qso.py`, `main.py` (APP_VERSION → "0.95.3"),
`tests/test_modules.py` (oder neue Test-Datei).

### Commit 2 — Doku

```
docs: v0.95.3 Stand + HANDOFF/CLAUDE.md update nach P1.9-Fix
```

Geaenderte Dateien: `HISTORY.md`, `HANDOFF.md` (beide Pfade SimpleFT8/ und
FT8/), `CLAUDE.md` (beide Pfade), `TODO.md` (P1.9 → ✅).

---

## 5. Doku-Updates (Reihenfolge nach CLAUDE.md PFLICHT)

### 5.1 `HISTORY.md` — neuer Eintrag prepended

```markdown
## 2026-05-05 v0.95.3 — P1.9 First-Reply-Lost-Bug-Fix

**Atomare Commits:** [HASH-CODE] (Code+Tests) + [HASH-DOKU] (Doku).
**Wurzel:** Decoder-Encoder-Timing-Race (FlexRadio TX-Buffer 1.3s).
Encoder wakes 0.2-3.0s VOR Decoder fertig → CQ-Audio bereits in
send_audio (BLOCKING) wenn _pending_reply gesetzt wurde → 1 Slot
Verzoegerung beim ersten Reply, eine ueberfluessige CQ zwischen
Empfang und Report. Reproduzierbar (4× Mike-Field-Test).

**Fix-Kombination (1 atomarer Commit, R1-Empfehlung):**
- core/decoder.py:138 — _WAKE_OFFSETS["FT8"] 1.5 → 2.5
- core/encoder.py — request_replace API + Replace-Loop
- core/qso_state.py — try_replace_pending_tx Signal +
  Defense-in-Depth in _send_cq
- ui/mw_qso.py — _on_try_replace_pending_tx Slot

**Voller V1→V2→R1→V3 Workflow.** R1-bestaetigt mit 3 Verbesserungen
(is_transmitting-Guard, Defense-in-Depth, 1-Commit-Strategie).
Tests 759 → 762 gruen.
```

### 5.2 `HANDOFF.md` (BEIDE Pfade — SimpleFT8/HANDOFF.md + FT8/HANDOFF.md identisch)

- Header: „**Stand 2026-05-05:** **v0.95.3 — P1.9-Fix.**"
- P1.9-Eintrag im OFFEN-Block ENTFERNEN (war 🔴, jetzt ✅).
- Neuer ✅-Eintrag oben analog zu „✅ P1.5 Field-Test BESTAETIGT".

### 5.3 `CLAUDE.md` (BEIDE Pfade)

- Header `**Aktueller Stand:**` Block prepended mit v0.95.3-Eintrag (analog
  zu v0.95.2-Block).
- Test-Count `759 passed` → `762 passed` updaten.

### 5.4 `TODO.md`

- P1.9-Block → ✅ markieren mit Datum + Commit-Hash + Test-Count.

### 5.5 Memory

Falls Workflow-Lesson aus dem Fix: Memory-Datei in
`/Users/mikehammerer/.claude-account1/projects/-Users-mikehammerer-Documents-KI-N8N-Projekte-FT8/memory/`
schreiben + MEMORY.md Index aktualisieren. **Aktuelle Einschaetzung:** keine
neue Lesson — V1→V2→R1→V3 lief sauber, kein Korrektur-Bedarf.

---

## 6. Risiko-Analyse

| Risiko | Wahrscheinlichkeit | Wirkung | Mitigation |
|---|---|---|---|
| SNR-Verlust durch Wake-Offset 2.5 | gering | <0.1 dB Schwelle (R1) | Field-Test 1 Tag, Stats-Vergleich |
| Race im _replace_lock bei 2 Replace-Requests pro TX | sehr gering | nur erstes Replace gewinnt, zweites bekommt False | Lock + Set-Once-Logik im Worker |
| Worker im Audio-Start-Race (request_replace zwischen Wake und _audio_started=True) | gering | Lock umfasst Audio-Start-Setzung — atomar | siehe 2.2d, Lock vor `break` |
| Re-Encode-Failure (encode_message returnt None) | sehr gering | Worker returnt sauber, kein Crash | bestehender Pfad |
| `_replace_message` ueberlebt TX-Ende bei Race | sehr gering | beim naechsten transmit() weg, weil `_tx_worker` resettet | Reset in 2.2c |
| Tests brechen (P1.5 + Encoder-Tests) | gering | bestehende Tests benutzen weder request_replace noch _audio_started | Vor Commit `pytest -q` ueber alle Tests |
| State-Inkonsistenz nach Replace (qso-Daten falsch) | mittel | falscher their_call / falscher Slot | Slot-Handler analog zu `_process_cq_reply` (Zeile 188-198) — gleiche QSOData-Felder |
| Replace bei R-Report (statt Grid) | gering | wuerde den falschen TX einreihen (Report statt RR73) | Slot-Handler prueft `if not msg.is_grid: return` (siehe 2.4b) |
| Encoder-tx_started.emit feuert mit alter Message-Variable | gering | Worker-Local `message` wurde im Loop ueberschrieben → emit feuert mit neuer Message ✓ | Code-Pfad lesen — `message` wird in jedem Schleifen-Durchlauf neu gesetzt |

---

## 7. Rollback-Plan

Wenn Field-Test einen Folgebug zeigt:

1. `git revert [HASH-CODE]` — atomarer Revert moeglich, weil 1 Commit.
2. `APP_VERSION` zurueck auf "0.95.2" + HANDOFF/CLAUDE.md zurueck.
3. Field-Test mit v0.95.2 — sicher dass Symptom dort bekannt ist (1 Slot
   Delay, aber keine neuen Bugs).

---

## 8. Field-Test-Protokoll

Mike's Test-Szenario (er hat es 4× heute reproduziert):
- 30m FT8 mit DA1TST am IC-7300 (anderes FT8-Tool an anderer Antenne).
- DA1TST ruft uns waehrend wir CQ senden.
- Erwartung NACH Fix: Report im SELBEN Slot wo CQ scheduled war (statt
  +1 Slot).
- Visueller Indikator: QSO-Panel zeigt CQ-Slot direkt gefolgt von
  Report-Slot ohne dazwischenliegende „CQ"-Wiederholung.

Falls Replace zu spaet ist (Decoder > 1.0s decoding): Status quo Pfad mit
1-Slot-Delay greift, kein Crash. Mike soll Logs `[Encoder] TX-Replace →`
und `[QSO] P1.9 Replace OK:` mitschreiben fuer Erfolgs-Quote.

---

## 9. Workflow-Status

- [x] Schritt 0: Code-Verifikation (alle Zeilen verifiziert)
- [x] Plan V1 (diese Datei)
- [ ] Plan V2 — Self-Review (Claude)
- [ ] Plan R1 — DeepSeek-Reasoner mit allen 4 Code-Dateien attached
- [ ] Plan V3 — R1-Findings einarbeiten
- [ ] Mike-Freigabe
- [ ] Code-Implementation (1 Commit)
- [ ] Doku-Implementation (1 Commit)
- [ ] Field-Test Mike
- [ ] Falls Field-Test gruen: HISTORY/HANDOFF/CLAUDE/TODO/Memory-Update.

---

**V1 Ende. Naechster Schritt: V2 — Self-Review.**
