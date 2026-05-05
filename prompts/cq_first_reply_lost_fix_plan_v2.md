# P1.9 Fix-Plan — V2 (Self-Review von V1)

**Status:** V2 = frische KI ueber V1. Ziel: Luecken/Fehler/Mehrdeutigkeiten
finden und V1 schaerfen — nicht das Problem neu loesen, sondern den Plan
verbessern. V2 ist eigenstaendig (R1 braucht V2 + 4 Code-Files).

V1: 24 KB Plan mit 4 Code-Aenderungen, 3 Tests, Risiko-Analyse, Rollback.
V2 prueft V1 systematisch gegen die Code-Realitaet.

---

## 1. Bestaetigung der V1-Architektur

V2 bestaetigt diese V1-Entscheidungen NACH Code-Verifikation:

- **1 atomarer Commit** (Option C alleine fixt nicht — V3-Diagnose
  bestaetigt: Encoder haelt CQ-Message in Worker-Local, State-Update aendert
  daran nichts).
- **Re-Encode im Worker-Loop** (statt `transmit()` neu aufzurufen) — der
  Worker-Thread laeuft bereits, kein neuer Thread noetig, kein
  `_is_transmitting=True`-Race.
- **`_audio_started`-Flag mit Lock** — atomarer Cutoff zwischen Replace-OK
  und Replace-Too-Late. Lock muss `_audio_started=True`-Setzung umfassen
  (V1 hat das in 2.2d unter `with self._replace_lock:`).
- **`try_replace_pending_tx`-Signal** statt direkter Encoder-Aufruf aus
  qso_state — saubere Trennung State-Machine vs UI-Layer (Connect in
  main_window-Schicht).
- **Defense-in-Depth in `_send_cq()`** — Sicherheitsgurt gegen Race wo
  Reply gemerkt wurde aber Replace zu spaet kam.

---

## 2. KRITISCHE FINDINGS — fehlende Punkte in V1

### 2.1 ⛔ FINDING-A: `_was_cq = True` fehlt im Slot-Handler

V1's `_on_try_replace_pending_tx` (Abschnitt 2.4b) setzt `_pending_reply = None`,
`qso`, State, `tx_even` — aber NICHT `_was_cq = True`.

**Vergleich mit `_process_cq_reply` Zeile 183:**
```python
self._was_cq = True  # CQ war aktiv (cq_mode=True hier garantiert)
```

**Wirkung des Fehlers:** Nach dem QSO ruft `_resume_cq_if_needed()` (qso_state.py
Zeile 351-367) auf. Diese Methode prueft `if self.cq_mode or self._was_cq` —
wenn beide False sind, geht state in IDLE statt CQ aufzunehmen.

`cq_mode` ist beim Replace-Trigger noch True (Worker-Thread setzt das nicht
zurueck). Aber wenn Mike waehrend des Replace-getriggerten QSOs
`stop_cq()` drueckt, wird `cq_mode=False`. Dann ist `_was_cq=False` und CQ
resumiert nicht — analog zum P1.5-Bug `_on_station_clicked` der den
`_cq_was_active`-Workaround brauchte.

**Fix in V3:** `self.qso_sm._was_cq = True` im Slot-Handler hinzufuegen,
ANALOG zu `_process_cq_reply`-Pfad. Zeile direkt nach `_pending_reply = None`.

### 2.2 ⛔ FINDING-B: `_dbg.reset(msg.caller)` + Debug-Log fehlt

V1's Slot-Handler erstellt das QSO-Datenobjekt ohne den Debug-Log zu
initialisieren. `_process_cq_reply` macht das auf Zeile 184-186:
```python
self._dbg.reset(msg.caller)
self._dbg.log("RX", f"CQ-Antwort von {msg.caller}: '{msg.raw}' ...")
```

**Wirkung:** Der `qso_debug.log`-Eintrag fuer das QSO startet nicht. Mike's
Debug-Workflow nach Field-Test verliert die initialen RX/TX-Eintraege.
Nicht funktional kritisch aber stoert die Debugging-Konsistenz.

**Fix in V3:** Ergaenze im Slot-Handler:
```python
self.qso_sm._dbg.reset(msg.caller)
self.qso_sm._dbg.log("RX", f"P1.9 Replace: CQ-Antwort von {msg.caller}: '{msg.raw}'")
self.qso_sm._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
```

### 2.3 ⛔ FINDING-C: `tx_slot_for_partner.emit(msg)` Side-Effect fehlt

`_process_cq_reply` Zeile 198 emittet `tx_slot_for_partner.emit(msg)`. Im
mw_qso `_on_tx_slot_for_partner` (Zeile 425-435) macht das ZWEI Sachen:
1. Setzt `encoder.tx_even = not their_even`.
2. Schreibt `add_info(f"Antworte {msg.caller}{label}")` ins QSO-Panel.

V1's Slot-Handler macht (1) direkt mit `self.encoder.tx_even = not their_even`.
Aber (2) — die UI-Anzeige „Antworte DA1TST (ANT2 ↑3.2 dB)" — fehlt komplett.

**Wirkung:** QSO-Panel zeigt keinen Rufe-Eintrag fuer den Partner. Inkonsistenz
gegenueber Hunt-Modus (wo `_on_station_clicked` Zeile 86 das macht).

**Fix in V3:** Im Slot-Handler nach `tx_even`-Setzung ergaenzen:
```python
label = self._antenna_pref_label(msg.caller)
if label:
    self.qso_panel.add_info(f"Antworte {msg.caller}{label}")
```

Alternativ: `qso_sm.tx_slot_for_partner.emit(msg)` aus dem Slot-Handler
selbst aufrufen — DRY, aber dann emittiert das Slot-Handler ein Signal
das es selbst nicht empfaengt (sondern `_on_tx_slot_for_partner` macht
es). Sauberer ist direktes `add_info` im Slot-Handler.

### 2.4 ⛔ FINDING-D: tx_even-Race im Slot-Handler

V1's Slot-Handler (Abschnitt 2.4b) hat folgende Reihenfolge:
```python
1. encoder.request_replace(tx_msg)  → setzt _replace_message + abort_event
2. ... State-Setup ...
3. encoder.tx_even = not their_even
```

**Race:** Der Worker-Thread kann zwischen (1) und (3) aus dem Sleep
aufwachen, sieht `_replace_message != None`, ruft `_next_slot_boundary()`
auf — und liest dabei `tx_even` das in (3) noch nicht gesetzt ist. Das
ist `_next_slot_boundary`-Logik (encoder.py:181-194):
```python
if self.tx_even is not None:
    want_even = self.tx_even
    ...
```

Wenn `tx_even` zu diesem Moment einen alten Wert hat (oder None), nimmt der
Worker einen falschen Slot. Resultat: Report landet im falschen Slot
(eventuell EVEN statt ODD oder umgekehrt) — dann hoert die Gegenstation den
Report nicht.

**Fix in V3:** tx_even VOR `request_replace()` setzen:
```python
their_even = getattr(msg, '_tx_even', None)
if their_even is not None:
    self.encoder.tx_even = not their_even
if not self.encoder.request_replace(tx_msg):
    return  # zu spaet
```

Bonus-Sicherheit: tx_even ist ein einfaches bool-Attribut, lockless, aber
GIL-atomar in CPython. Reihenfolge-Korrektur reicht.

### 2.5 ⛔ FINDING-E: Connect-Stelle in V1 nicht verifiziert

V1 Abschnitt 2.4a sagt „in `main_window.py` wo `qso_sm.tx_slot_for_partner.connect(...)`
steht — neuen `try_replace_pending_tx`-Connect dort daneben einfuegen". Das ist
NICHT verifiziert. Wenn der Connect woanders liegt (mw_qso.py-Mixin oder
mw_radio.py), ist die Plan-Stelle falsch.

**Fix in V3:** Mit grep verifizieren:
```bash
grep -n "tx_slot_for_partner.connect" ui/*.py main.py
```

In V3 die exakte Datei + Zeile angeben.

### 2.6 ⛔ FINDING-F: Encode-Fehler im Replace-Pfad — State-Hang

V1's `_tx_worker_inner`-Loop hat:
```python
audio_12k = self.encode_message(message)
if audio_12k is None:
    return
```

Wenn `encode_message` im Replace-Pfad None returnt (sehr unwahrscheinlich
aber moeglich z.B. ungueltiges Format), kommt der Worker mit `return` raus
— `tx_finished` feuert NICHT (das passiert nur am Ende von _tx_worker_inner
nach send_audio). Aber `_is_transmitting` wird in `_tx_worker.finally` auf
False gesetzt.

**Wirkung:** State-Machine ist auf TX_REPORT, aber `on_message_sent` wird
nie aufgerufen → State haengt in TX_REPORT bis zum 3-Min-QSO-Timeout.

**Fix in V3:** Entweder `tx_finished.emit()` im Encode-Fehler-Pfad emittieren
(invariant: jeder TX-Versuch endet mit tx_finished) ODER `encoding_error`
abfangen und State zuruecksetzen.

Pragmatischer Ansatz: `tx_finished.emit()` im Replace-Pfad-Fehler hinzufuegen.
Macht den Pfad konsistent zum normalen TX-Ende.

### 2.7 🟡 FINDING-G: Test fuer Defense-in-Depth fehlt

V1 hat 3 Encoder-Tests (request_replace) aber keinen Test fuer den
Defense-in-Depth in `_send_cq()`. Der ist sehr einfach zu schreiben:

```python
def test_send_cq_with_pending_reply_processes_instead():
    """P1.9 Defense-in-Depth: _send_cq mit pending Reply → process statt CQ."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    msg = make_msg("DA1TST", target="DA1MHH", grid="JN66")
    sm._pending_reply = msg
    captured = []
    sm.send_message.connect(captured.append)
    sm._send_cq()
    assert any("DA1TST DA1MHH" in m for m in captured), \
        "Erwartet Report-TX, nicht CQ-TX"
    assert sm._pending_reply is None
    assert sm.state == QSOState.TX_REPORT
```

**Fix in V3:** 4. Test ergaenzen.

### 2.8 🟡 FINDING-H: Test fuer State-Machine-Trigger fehlt

V1 testet die Encoder-API, aber nicht den `try_replace_pending_tx`-Emit-Pfad
in `on_message_received`. Bei CQ_CALLING + Grid-Reply muss das Signal
feuern.

```python
def test_cq_calling_grid_reply_emits_try_replace():
    """P1.9: CQ_CALLING + Grid-Reply → try_replace_pending_tx Signal."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_CALLING)
    captured = []
    sm.try_replace_pending_tx.connect(captured.append)
    msg = make_msg("DA1TST", target="DA1MHH", grid="JN66")
    sm.on_message_received(msg)
    assert len(captured) == 1
    assert captured[0] is msg
    assert sm._pending_reply is msg  # weiter gemerkt fuer Fallback
```

**Fix in V3:** 5. Test ergaenzen.

### 2.9 🟡 FINDING-I: Bestehender Test `test_qso_cq_reply_during_tx_pending_then_processed`

Der Test (aus v0.95.2) prueft: bei CQ_CALLING + Reply wird `_pending_reply`
gesetzt, dann `on_message_sent` ruft `_process_cq_reply` und feuert Report.

Mit V1's Aenderung wird ZUSAETZLICH `try_replace_pending_tx` emittiert. Wenn
der Test keinen Listener fuer dieses Signal hat: Signal verpufft. Test
bleibt gruen. **OK.**

ABER: wenn der Test darauf prueft dass NUR `_pending_reply` gesetzt wird (und
NICHTS sonst), wuerde das try_replace-Emit eventuell auffallen. V2 muss
diesen Test im Detail durchlesen — V1 hat das nicht getan.

**Fix in V3:** Test-Datei anschauen, sicherstellen dass kein `assert no_signal`
vorhanden ist. Falls doch: anpassen.

### 2.10 🟡 FINDING-J: Reset von `_replace_message` zu spaet?

V1's `_tx_worker.finally` setzt `_audio_started=False` aber NICHT
`_replace_message=None`. Wenn ein TX abgebrochen wird (`abort()`), und
gleichzeitig kommt ein `request_replace`-Aufruf zwischen `is_transmitting=True`
und Reset → `_replace_message` koennte gesetzt bleiben.

Beim NAECHSTEN `_tx_worker(message)` wird das in `_tx_worker` Zeile (V1
Abschnitt 2.2c):
```python
with self._replace_lock:
    self._replace_message = None
```
zurueckgesetzt. Also der naechste TX erbt den Stale-State NICHT — der wird
ueberschrieben.

**Aber:** zwischen `abort()`-finally und `_tx_worker`-start gibt es ein
Fenster wo `_replace_message != None` ist und `_is_transmitting=False`.
In `request_replace`-Pruefung: `if not self._is_transmitting: return False` —
also kein Race. **OK, V1 ist hier sauber.** V2 bestaetigt.

### 2.11 🟡 FINDING-K: `tx_started.emit` mit alter Message?

Im V1's `_tx_worker_inner`-Loop ist `message` eine lokale Variable die im
`continue`-Pfad neu zugewiesen wird:
```python
if self._replace_message is not None:
    message = self._replace_message
    ...
    continue
```

Nach `continue` wird `audio_12k = self.encode_message(message)` mit der NEUEN
Message gerufen. Spaeter `tx_started.emit(message, _tx_even, next_boundary)`
ebenfalls mit der NEUEN Message. **OK, sauber.**

### 2.12 🟡 FINDING-L: `_assign_slot_parity` Reihenfolge

CLAUDE.md „Bekannte Fallen" warnt: `cycle_decoded` muss vor `message_decoded`
bleiben weil `_assign_slot_parity` `msg._tx_even` setzt BEVOR
`on_message_received` es liest.

V1 fasst die Decoder-Signal-Reihenfolge nicht an — also OK. Aber V2 muss
das explizit bestaetigen damit R1 nicht halluziniert.

**Bestaetigung in V3:** kein Decoder-Signal-Pfad geaendert. `msg._tx_even`
ist gesetzt wenn `on_message_received` laeuft → unser neuer
`try_replace_pending_tx.emit(msg)` reicht das `msg` weiter, mw_qso liest
`msg._tx_even` korrekt.

---

## 3. KLEINERE FINDINGS

### 3.1 V1 Abschnitt 2.3b: `_pending_reply = None` redundant?

V1 fuegt Defense-in-Depth ein, danach bleibt `self._pending_reply = None`
am Anfang von `_send_cq()`. Im Defense-in-Depth-Pfad ist `_pending_reply`
nach `_process_cq_reply()` schon None (Zeile 171). Im Normal-Pfad ist es
sowieso None.

**Zur Diskussion in V3:** Belassen ist sicher (kein Bug), entfernen ist
sauberer. V2-Empfehlung: belassen, weil Code-Diff minimaler.

### 3.2 V1 Abschnitt 2.4b: `freq_hz=msg.freq_hz` ohne Korrektur?

`_process_cq_reply` Zeile 192 setzt `freq_hz=msg.freq_hz` ohne weitere
Logik. V1 macht das gleich. Aber im Hunt-Pfad (`start_qso` Zeile 239) ist
`freq_hz=freq_hz` aus Parameter. Beide identisch. **OK.**

### 3.3 V1 Test 1: `_audio_started=False` explizit setzen

```python
enc._audio_started = False
```

Das ist im `Encoder.__init__` schon der Default. Ueberredundant aber
defensiv geschrieben. **OK, lassen.**

### 3.4 V1 Doku-Abschnitt 5.1 HISTORY-Eintrag

V1 Hash-Code-Platzhalter `[HASH-CODE]` sieht gut aus. R1 + V3 koennen das
final fuellen.

---

## 4. NICHT-FINDINGS — V1 ist hier korrekt

V2 hat verifiziert dass V1 in folgenden Bereichen korrekt ist:

| Bereich | V1-Punkt | V2-Bestaetigung |
|---|---|---|
| Loop in `_tx_worker_inner` (Re-Encode) | 2.2d | Korrekt — Worker re-iteriert sauber |
| Lock umfasst Audio-Start | 2.2d (`with _replace_lock: _audio_started=True`) | Atomar OK |
| `_pending_reply` bleibt gesetzt bei Replace-Fail | nicht explizit | Code-Pfad: V1 setzt nur bei Erfolg auf None — Fallback intact |
| Defense-in-Depth `_send_cq` | 2.3b | Defensiv und korrekt |
| Atomare 1-Commit-Strategie | 4 | R1-bestaetigt + V3-Logik sauber |
| Risiko-Tabelle | 6 | Alle 9 Risiken plausibel |
| SNR-Effekt < 0.1 dB | 2.1 | R1 hat das verifiziert |
| Encoder-Tests Mock-Free | 3 | Threading nicht getestet aber API-Surface ok |

---

## 5. Akzeptanzkriterien — V2-Update

Erweitert um Findings A, B, C, D:

1. DA1TST-Reply im SELBEN Slot wo CQ scheduled war.
2. Bei zu spaetem Decoder: Status quo, kein Crash.
3. State-Konsistenz nach Replace: TX_REPORT + qso-Daten + `_pending_reply=None`
   + **`_was_cq=True`** (FINDING-A).
4. Tests 759 → ≥764 gruen (3 Encoder + 1 SM-Defense-in-Depth + 1 SM-Trigger).
5. Stats-Bias 0.
6. **QSO-Panel zeigt „Antworte X (ANT...)" genauso wie bei `_process_cq_reply`**
   (FINDING-C).
7. **Debug-Log `qso_debug.log` enthaelt P1.9-Eintrag bei Replace-OK**
   (FINDING-B).
8. **`encoder.tx_even` ist gesetzt BEVOR `request_replace` aufgerufen wird**
   (FINDING-D).
9. **Bei Encode-Failure im Replace-Pfad emittet Encoder `tx_finished` damit
   State sauber durchlaeuft** (FINDING-F).

---

## 6. V2-To-Do fuer V3 (Aktions-Liste)

- [ ] FINDING-A: `_was_cq = True` im Slot-Handler ergaenzen.
- [ ] FINDING-B: Debug-Log-Eintrag im Slot-Handler.
- [ ] FINDING-C: `add_info("Antworte ...")` ins QSO-Panel.
- [ ] FINDING-D: tx_even-Setzung VOR `request_replace` im Slot-Handler.
- [ ] FINDING-E: Connect-Stelle mit grep verifizieren — exakte Datei+Zeile in V3.
- [ ] FINDING-F: `tx_finished.emit` im Encode-Fehler-Pfad des Replace-Loops.
- [ ] FINDING-G: 4. Test (Defense-in-Depth `_send_cq`).
- [ ] FINDING-H: 5. Test (try_replace-Trigger bei CQ_CALLING+Grid).
- [ ] FINDING-I: bestehenden CQ-pending-Test pruefen, ggf. anpassen.

---

## 7. R1-Pruefauftraege (V2-Liste)

V2 markiert was R1 beurteilen soll — nicht das Problem neu loesen, sondern
gegen Code halten:

1. **Race-Sicherheit Encoder-Replace nach FINDING-D Korrektur:** ist die
   Reihenfolge tx_even-set → request_replace → state-set sauber? Gibt es
   andere Reihenfolge-Probleme?

2. **State-Konsistenz nach Replace:** decken die 4 Slot-Handler-Aktionen
   (`_pending_reply=None`, `qso=...`, `_was_cq=True`, `_set_state(TX_REPORT)`)
   alles ab was `_process_cq_reply` macht? Was uebersehen wir?

3. **FINDING-F Encode-Fehler-Pfad:** ist `tx_finished.emit` korrekt? Oder
   sollte stattdessen `_is_transmitting=False` + state-reset im qso_sm
   erfolgen? (Kein invariant garantiert tx_finished bei jedem TX-Versuch.)

4. **Worker-Loop Edge-Case `_audio_started`-Reset:** wenn der erste Loop-
   Durchlauf mit der CQ-Message bricht weil aborted ohne replace, dann
   `return` aus dem Worker → `finally` setzt `_audio_started=False`. Bei
   Worker-Re-Run mit neuem `transmit()` ist `_audio_started=False` wieder.
   **Aber:** im Replace-Pfad bleibt der Worker im selben `_tx_worker`-Aufruf
   und faehrt im 2. Loop-Durchlauf weiter. Das `_audio_started=True` wird
   vor send_audio gesetzt. Bei TX-Ende geht's in finally. Sauber?

5. **Test-Coverage:** sind 5 Tests genug? Was fehlt? V2 hat z.B. keinen
   Test fuer mw_qso Slot-Handler (UI-Code, schwer zu mocken).

6. **Plan-Vollstaendigkeit:** ist die V2-Doku-Sektion vollstaendig? Welche
   Doku-Stelle vergessen wir?

---

## 8. Abschluss

V2 hat 12 Findings + 4 kleinere Punkte gefunden. V3 muss:
- 9 Findings einarbeiten (kritische A-F + Tests G-I)
- Connect-Stelle E mit grep verifizieren
- 2 Akzeptanzkriterien ergaenzen (3, 6, 7, 8, 9 sind neu)
- R1 bekommt V2 + alle 4 Code-Files + diese Pruefauftraege

**V2 Ende. Naechster Schritt: R1-Review.**
