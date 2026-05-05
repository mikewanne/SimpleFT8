# P1.10 Compact-Notes — Stand vor Workflow-Start (2026-05-05)

Diese Datei sichert den Konversations-Kontext vor `/compact` damit der
naechste Session-Start sauber den P1.10 V1-Workflow starten kann.

---

## Aktueller Stand

- **App-Version:** v0.95.3 (deployed, App laeuft PID 80961, Python 3.12).
- **Letzte Commits:**
  - `a1cebb9` docs: v0.95.3 Stand + HISTORY/HANDOFF/CLAUDE/TODO
  - `20c7fe7` P1.9 Fix: Decoder-Wake + Encoder-Replace
- **Tests:** 764 gruen.
- **P1.9 Field-Test:** ✅ BESTAETIGT (2/2 QSOs, Replace-Pfad genommen).

---

## P1.10 — End-of-QSO Icom-73-Loop

### Symptom — 2× reproduziert (Mike, 11:24-:27 + 11:28-:29 UTC)

Nach **unserem** RR73 und **DA1TST** 73 (QSO intern komplett, ADIF
geloggt, `qso_confirmed.emit` gefeuert) sendet das IC-7300 von DA1TST
**fuenfmal weiter** das `73` in den nachfolgenden ODD-Slots, bis es
von selbst aufhoert.

### Trace 1 (11:24-11:27 UTC, vollstaendig aus Log)

```
11:24:00 [E] → DA1TST DA1MHH RR73         (TX_RR73 → on_message_sent → WAIT_73)
11:24:15 [O] ← DA1MHH DA1TST 73           (RX, State=WAIT_73)
                                           → qso_confirmed.emit ✓
                                           → _resume_cq_if_needed → CQ_CALLING
11:24:28 [E] → CQ DA1MHH JO31             (auf ODD-Slot, weil tx_even=ODD aus QSO)
11:24:42 STATE CQ_CALLING → CQ_WAIT
11:24:44 STATE CQ_WAIT → CQ_CALLING (timer trigger)
11:24:45 [O] ← DA1MHH DA1TST 73           (RX 2., State=CQ_CALLING)
                                           → log "nach Timeout/CQ ignoriert"
                                           → faellt durch alle State-Branches
11:24:58 [E] → CQ DA1MHH JO31
11:25:15 [O] ← DA1MHH DA1TST 73           (RX 3.)
11:25:28 [E] → CQ DA1MHH JO31
11:25:45 [O] ← DA1MHH DA1TST 73           (RX 4.)
11:25:58 [E] → CQ DA1MHH JO31
11:26:15 [O] ← DA1MHH DA1TST 73           (RX 5.)
11:26:28 [E] → CQ DA1MHH JO31
11:26:30 ... IC-7300 stoppt
11:26:58 [E] → CQ DA1MHH JO31
11:27:14 STATE CQ_CALLING (Decoder-leer)
...
11:27:45 [O] ← DA1MHH DA1TST JO31         (NEUER Anruf — Mike hat Icom neu getriggert)
11:27:57 → P1.9 Replace OK
11:27:58 [E] → DA1TST DA1MHH -15
```

### Trace 2 (11:28-11:29 UTC) — bestaetigt Reproduzierbarkeit

Nach 2. RR73 von uns + 73 von DA1TST: dasselbe — `73` immer wieder
gesendet, bis IC-7300 aufgibt.

### Mike's Funker-Hypothese

WSJT-X / JTDX / MSHV-Tools senden optional ein **einzelnes Hoeflichkeits-
73** zurueck nach 73-Empfang („Auto Sequence" + „Tx 73"). Damit
beendet die Gegenstation ihre Auto-Sequence-Schleife. SimpleFT8 sendet
aktuell **kein** 73 zurueck — IC-7300 retried 5× und gibt dann auf.
Andere FT8-Apps (WSJT-X selbst) reagieren weniger empfindlich, weil
sie selbst keine Auto-Sequence haben oder nach erstem 73 stoppen.

### Code-Pfad verifiziert (qso_state.py)

```python
# Z.430-436: TX_RR73 → WAIT_73 (sauber)
elif self.state == QSOState.TX_RR73:
    self.qso_complete.emit(self.qso)
    self.cq_qso_count += 1
    self._set_state(QSOState.WAIT_73)
    self.qso.timeout_cycles = 0

# Z.582-586: WAIT_73 + 73-Empfang → KEIN 73 zurueck, direkt CQ resumieren
if self.state == QSOState.WAIT_73:
    if msg.is_73 or msg.is_rr73:
        print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
        self.qso_confirmed.emit(self.qso)
        self._resume_cq_if_needed()        # ← HIER ist der Hebel
    elif msg.is_r_report and msg.caller == self.qso.their_call:
        # Hoeflichkeit fuer R-Report (wenn Station unser RR73 nicht empfangen)
        if self.qso.rr73_retries < 2:
            self.qso.rr73_retries += 1
            tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
            self.send_message.emit(tx_msg)
        return

# Z.447-451: CQ_CALLING + 73 → ignoriert (zu spaet, Status-quo Pfad)
if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
    if msg.is_rr73 or msg.is_73:
        self._dbg.log("RX", f"RR73/73 von {msg.caller} nach Timeout/CQ — ignoriert")
        # KEIN return — faellt durch zu Caller-Queue-Check, dann State-Branches.
        # In CQ_CALLING + msg.is_73: alle State-Branches greifen nicht.
```

### Hypothese fuer Loesung — V1-Skizze (NICHT implementations-fertig)

**Option A — Hoeflichkeits-73 in WAIT_73:**
Wenn 73 in WAIT_73 empfangen → `tx_msg = "{their_call} {my_call} 73"`
senden, neuer State `TX_73_COURTESY` (oder TX_RR73 reuse mit Flag),
nach `on_message_sent` direkt zu `_resume_cq_if_needed`. Counter pro
QSO `qso.courtesy_73_sent = True` damit nicht doppelt.

**Option B — Counter pro Station (Cross-QSO):**
`_courtesy_73_for_call: dict[str, bool]` — zusaetzliche Sicherheit dass
ein 73 nicht mehrfach zurueck gesendet wird wenn IC-7300 trotzdem weiter
sendet (was er hier nicht tut — er stoppt nach 5 Slots).

**Option C — Hybrid:**
A + B. Vermutlich Overengineering wenn IC-7300 nach 1 73 zufrieden.

### R1-Pruefauftraege (V1 → V2 → R1)

1. **TX-Slot fuer Courtesy-73:** wir sind in WAIT_73 (nach unserem RR73
   :24:00). 73 kommt :24:15 (ODD). Wenn wir sofort 73 senden wollen:
   Encoder hat tx_even=ODD aus QSO → naechster ODD-Slot waere :24:45.
   Aber :24:30 EVEN ist eigentlich der „naechste freie Slot". Erlaubt
   FT8-Etiquette ein TX im selben Slot wo wir RX hatten? (Nein —
   half-duplex.) Also frueheste TX-Moeglichkeit ist :24:45 ODD.
2. **Decoder-Encoder-Race wie P1.9:** der 73-Empfang :24:15 wird vom
   Decoder mit P1.9-Wake-Offset 2.5 bei :12.5+decode_time geliefert.
   Encoder-Worker (CQ-TX) schlaeft schon mit der CQ-Message. Brauchen
   wir hier P1.9-Replace-Pfad analog? **JA** — sonst geht 1 Slot
   verloren wie beim P1.9-Bug.
3. **State-Wechsel-Reihenfolge:** Wenn Replace gelingt, ist neue
   Message `73` statt `CQ`. State sollte nicht TX_RR73 sein (das wuerde
   bei TX_RR73-on_message_sent ADIF doppelt loggen!). Eigene State
   `TX_73_COURTESY` notwendig.
4. **`qso_confirmed.emit` schon gefeuert** — `_on_qso_confirmed`
   triggert `add_qso_complete`, `logbook.refresh`, `add_info("CQ-Modus
   läuft weiter…")`. Wenn wir 73 senden waehrend CQ-Modus „weiter
   laeuft": UI inkonsistent? Vielleicht qso_confirmed.emit erst NACH
   Courtesy-73 feuern.
5. **Tests:** 73 in WAIT_73 → 1× courtesy 73 + state. Counter doppel-
   geschuetzt. Kein doppeltes ADIF.
6. **Field-Test-Risiko:** wenn Courtesy-73 falsch gesendet (z.B. an
   andere Stationen die uns 73 schicken weil sie selber im WAIT_73
   sind und uns als Bestaetigung sehen): Endlosschleife. Counter muss
   idiotensicher sein.

### Workflow-Plan fuer naechste Session

1. **V1** schreiben — `prompts/p1_10_v1.md` mit allen 6 Pruefauftraegen,
   Datei:Zeile-praezise, Loesungs-Optionen A/B/C diskutiert (NICHT
   entschieden — V2/R1/V3-Job).
2. **V2** Self-Review.
3. **R1** mit DeepSeek-Reasoner + qso_state.py + encoder.py + mw_qso.py.
4. **V3** R1-Findings einarbeiten.
5. **Mike-Freigabe** Diagnose-V3.
6. **Plan-V1→V2→R1→V3** mit Code-Diffs.
7. **Mike-Freigabe** Plan-V3.
8. **Code-Implementation** (1 atomarer Commit + Doku-Commit).
9. **Field-Test** Mike: DA1TST-Szenario, IC-7300 sollte nach 1 unserem
   Courtesy-73 KEIN weiteres 73 mehr senden.

### Hardware-Setup (unveraendert)

- FlexRadio = DA1MHH (TX immer ANT1, 100 W)
- IC-7300 = DA1TST (Test-Setup, manuell EVEN/ODD)
- 30m FT8 Field-Test heute

### Diagnose-Files (zu erstellen nach Compact)

- `prompts/p1_10_v1.md` — V1 Diagnose (eigenstaendig)
- `prompts/p1_10_v2.md` — Self-Review
- `prompts/p1_10_v3.md` — R1-Findings eingearbeitet

---

## Bekannte Fallen — wichtig fuer P1.10-Implementierung

- **`qso_complete` vs `qso_confirmed`:** `qso_complete.emit` feuert in
  `on_message_sent` TX_RR73 → ADIF schreiben. `qso_confirmed.emit` feuert
  bei 73-Empfang in WAIT_73 → UI „QSO komplett ✓". Reihenfolge nicht
  vertauschen — sonst doppelter ADIF-Eintrag.
- **`_resume_cq_if_needed` ruft eventuell `_send_cq()` auf** — wenn
  vorher `_pending_reply` gesetzt war (P1.9-Defense-in-Depth) wird das
  verarbeitet statt CQ.
- **tx_even-Erbschaft aus QSO:** Encoder.tx_even bleibt nach RR73 auf
  „nicht ihres". Nach Courtesy-73 sollte tx_even reset oder neu gesetzt
  werden je nach Strategie.
- **P1.9-Replace-Pfad analog nutzen:** Decoder ist mit P1.9-Wake-Offset
  2.5 schon frueh genug, request_replace existiert. Wir koennen den
  vorhandenen Encoder-Replace-Mechanismus reusen statt neuen Pfad
  bauen.

---

## Memory-Pflicht nach P1.10-Erledigung

- HISTORY.md → v0.95.4 Eintrag
- HANDOFF.md (beide Pfade) Stand v0.95.4
- CLAUDE.md (beide Pfade) Aktueller Stand
- TODO.md → P1.10 als ✅
- Memory ggf. neu (Lesson aus Workflow)

---

**Compact-Notes Ende. Naechster Session-Start: HANDOFF.md → diese Datei
lesen → V1 schreiben.**
