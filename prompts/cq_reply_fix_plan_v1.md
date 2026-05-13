# CQ-Reply-Bug Fix — Implementations-Plan V1 (Option A)

**Status:** V1 = Plan-Entwurf. Mike hat Option A freigegeben (komplett
rip-out der 5-Min-Sperre). V2 = Self-Review, R1 = DeepSeek-Pruefung,
V3 = final, dann Plan-Mode + atomare Commits.

**Version-Bump:** v0.95.1 → **v0.95.2** (Bugfix-only patch).

---

## 1. Strategie

- **3 Block-Stellen + Hilfsmechanik komplett entfernen** statt nur
  `_WORKED_BLOCK_SECS = 0` (Mike's Anti-Overengineering-Regel).
- **Existing Test invertieren** + 2 neue Tests fuer den vorher unge-
  testeten Pfad (CQ_CALLING-During-TX und Caller-Queue ohne Block).
- **Atomare Commits**: 2 Commits — (1) Code+Tests zusammen, (2) Doku.

Begruendung 2-Commit-Aufteilung statt 3:
- Commit 1 nur Code wuerde `test_qso_worked_recently_block` rot
  hinterlassen (testet aktiv die geloeschte Sperre). Bisecting bricht.
- Tests + Code zusammen = logisch ein „Bug-Fix"-Schritt, atomar gruen.

---

## 2. Atomare Commits

### Commit 1 — `core: remove 5-min worked-recently lockout (P1.5 fix)`

**Geaenderte Files:**
- `core/qso_state.py` — alle 7 Stellen entfernen
- `tests/test_modules.py` — Test #477 invertieren + 2 neue Tests
- `main.py` — APP_VERSION 0.95.1 → 0.95.2

**Tests vor Commit:** alle gruen (756 → vermutlich 758 mit +2 neuen,
weil 1 invertiert).

### Commit 2 — `docs: P1.5 CQ-Reply-Bug fix dokumentation`

**Geaenderte Files:**
- `HISTORY.md` — neuer Eintrag `## 2026-05-05 v0.95.2 — CQ-Reply-Bug-Fix`
- `HANDOFF.md` (Projekt-Root + SimpleFT8/) — Stand v0.95.2, P1.5 raus
- `CLAUDE.md` (Projekt-Root + SimpleFT8/) — Aktueller Stand + Test-Count
- `TODO.md` — P1.5 entfernen aus „ALS NAECHSTES", in HISTORY-Sektion
- Memory `feedback_funker_entscheidung_filter_in_rx.md` — neue Lesson

---

## 3. Code-Diffs Commit 1

### 3.1 `core/qso_state.py`

**Loeschung 1 — Zeile 119+120 (Definition + Konstante):**

```python
# VORHER:
        self._worked_calls: dict = {}   # {callsign: timestamp} — gesperrte Calls nach QSO
        self._WORKED_BLOCK_SECS = 300   # 5 Minuten Sperre nach QSO
        self._caller_queue: list = []   # Warteliste: Stationen die während QSO gerufen haben

# NACHHER:
        self._caller_queue: list = []   # Warteliste: Stationen die während QSO gerufen haben
```

**Loeschung 2 — Zeile 168-176 (Methode `_is_worked_recently`):**

```python
# VORHER:
    def _is_worked_recently(self, callsign: str) -> bool:
        """True wenn diese Station in den letzten _WORKED_BLOCK_SECS gearbeitet wurde."""
        ts = self._worked_calls.get(callsign)
        if ts is None:
            return False
        if time.time() - ts > self._WORKED_BLOCK_SECS:
            del self._worked_calls[callsign]
            return False
        return True

# NACHHER:
(komplett geloescht — 8 Zeilen + Leerzeile)
```

**Loeschung 3 — Zeile 190-193 (Block #2 in `_process_cq_reply`):**

```python
# VORHER:
        # Kein CQ-Reply verarbeiten wenn CQ-Modus nicht aktiv (z.B. nach HALT)
        if not self.cq_mode:
            print(f"[QSO] {msg.caller} ignoriert — CQ-Modus nicht aktiv")
            return

        # Kein neues QSO mit kuerzlich gearbeiteter Station
        if self._is_worked_recently(msg.caller):
            print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
            return

        # 73/RR73 als CQ-Antwort ignorieren (Gegenstation steckt in Schleife)
        if msg.is_73 or msg.is_rr73:

# NACHHER:
        # Kein CQ-Reply verarbeiten wenn CQ-Modus nicht aktiv (z.B. nach HALT)
        if not self.cq_mode:
            print(f"[QSO] {msg.caller} ignoriert — CQ-Modus nicht aktiv")
            return

        # 73/RR73 als CQ-Antwort ignorieren (Gegenstation steckt in Schleife)
        if msg.is_73 or msg.is_rr73:
```

**Loeschung 4 — Zeile 440-443 (TX_RR73 Eintrag):**

```python
# VORHER:
        elif self.state == QSOState.TX_RR73:
            # ADIF sofort loggen (RR73 oder 73 gesendet = QSO von unserer Seite bestaetigt)
            self.qso_complete.emit(self.qso)
            self.cq_qso_count += 1
            # Call sperren: kein neues QSO mit dieser Station fuer 5 Minuten
            if self.qso.their_call:
                self._worked_calls[self.qso.their_call] = time.time()
                print(f"[QSO] {self.qso.their_call} gesperrt fuer {self._WORKED_BLOCK_SECS}s")
            # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
            self._set_state(QSOState.WAIT_73)

# NACHHER:
        elif self.state == QSOState.TX_RR73:
            # ADIF sofort loggen (RR73 oder 73 gesendet = QSO von unserer Seite bestaetigt)
            self.qso_complete.emit(self.qso)
            self.cq_qso_count += 1
            # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
            self._set_state(QSOState.WAIT_73)
```

**Loeschung 5 — Zeile 470 (Block #3 Caller-Queue):**

```python
# VORHER:
        if (self.cq_mode
                and self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING)
                and msg.target == self.my_call
                and (msg.is_grid or msg.is_report)
                and msg.caller != self.qso.their_call
                and not self._is_worked_recently(msg.caller)
                and not any(q.caller == msg.caller for q in self._caller_queue)):
            self._caller_queue.append(msg)

# NACHHER:
        if (self.cq_mode
                and self.state not in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING)
                and msg.target == self.my_call
                and (msg.is_grid or msg.is_report)
                and msg.caller != self.qso.their_call
                and not any(q.caller == msg.caller for q in self._caller_queue)):
            self._caller_queue.append(msg)
```

**Loeschung 6 — Zeile 479-482 (Block #1 Hauptpfad):**

```python
# VORHER:
        # ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
            if msg.is_grid or msg.is_report:
                # Beendet ist beendet: kuerzlich gearbeitete Stationen ignorieren
                if self._is_worked_recently(msg.caller):
                    print(f"[QSO] {msg.caller} ignoriert — kuerzlich gearbeitet (beendet ist beendet)")
                    return
                # Antwort merken — wird in on_message_sent() verarbeitet
                self._pending_reply = msg

# NACHHER:
        # ── Jemand ruft UNS (CQ-Modus, oder im IDLE) ──
        if self.state in (QSOState.IDLE, QSOState.CQ_WAIT, QSOState.CQ_CALLING) and msg.target == self.my_call:
            if msg.is_grid or msg.is_report:
                # Antwort merken — wird in on_message_sent() verarbeitet
                self._pending_reply = msg
```

**Diff-Summe qso_state.py:** -22 Zeilen, +0 Zeilen. Kein neuer Code,
nur Loeschungen.

### 3.2 `tests/test_modules.py`

**Aenderung 1 — Test `test_qso_worked_recently_block` invertieren
(Z. 477-492):**

```python
# VORHER:
def test_qso_worked_recently_block():
    """Kuerzlich gearbeitete Station wird im CQ-Modus ignoriert."""
    import time
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm._worked_calls["R3EDI"] = time.time()  # gerade gearbeitet
    sm.state = QSOState.CQ_WAIT
    sm.cq_mode = True
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    # Sollte ignoriert werden → kein neuer TX
    assert not any("R3EDI" in s and "RR73" not in s and "CQ" not in s for s in sent)

# NACHHER:
def test_qso_known_station_can_call_again():
    """Funker-Entscheidung: bekannte Station darf erneut anrufen.

    Mike's Philosophie 2026-05-05: keine 5-Min-Sperre. Wenn eine bekannte
    Station ruft, hat sie meist einen Grund (kein 73 erhalten). Filter
    'Neue Stationen' im RX-Panel blendet aus Anzeige aus, NICHT aus dem
    Reply-Pfad. Ersetzt das frühere test_qso_worked_recently_block.
    """
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.CQ_WAIT
    sm.cq_mode = True
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    # Sollte als CQ-Reply verarbeitet werden → state=TX_REPORT, send_message emit
    assert sm.state == QSOState.TX_REPORT
    assert any("R3EDI" in s and "DA1MHH" in s for s in sent)
```

**Aenderung 2 — neuen Test hinzufuegen (nach Test #1):**

```python
def test_qso_cq_reply_during_tx_pending_then_processed():
    """CQ-Reply waehrend TX laeuft → _pending_reply gesetzt → nach TX-Ende verarbeitet.

    Vorher nicht getestet — der CQ_CALLING-Pfad der bei Field-Test
    2026-05-05 mit DA1TST das Symptom zeigte (kombiniert mit Sperre).
    """
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.CQ_CALLING       # TX laeuft
    sm.cq_mode = True
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    # Reply kommt waehrend TX
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    # CQ_CALLING-Pfad: pending merken, NOCH nicht verarbeiten
    assert sm.state == QSOState.CQ_CALLING
    assert sm._pending_reply is msg
    assert len(sent) == 0  # noch kein TX

    # TX-Ende → on_message_sent verarbeitet pending
    sm.on_message_sent()
    assert sm.state == QSOState.TX_REPORT
    assert any("R3EDI" in s and "DA1MHH" in s for s in sent)


def test_qso_caller_queue_accepts_known_station():
    """Caller-Queue nimmt bekannte Stationen waehrend QSO auf (kein Block).

    Block #3 (qso_state.py:470 vorher `not _is_worked_recently`) wurde
    entfernt. Test sichert ab: bekannte Station ruft uns waehrend QSO →
    landet in Warteliste.
    """
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm.state = QSOState.WAIT_REPORT
    sm.qso.their_call = "EA3FHP"  # aktiver QSO-Partner

    # R3EDI war frueher gearbeitet (vor Fix gewuerde geblockt)
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    # R3EDI soll in Queue landen
    assert len(sm._caller_queue) == 1
    assert sm._caller_queue[0].caller == "R3EDI"
```

**Diff-Summe test_modules.py:** -16 Zeilen (alter Test), +52 Zeilen
(invertierter + 2 neue) = netto +36 Zeilen.

**Test-Count-Erwartung:**
- Vorher: 756
- Nachher: 756 - 1 (geloescht) + 1 (invertiert ersetzt) + 2 (neu) = **758**

### 3.3 `main.py`

```python
# VORHER:
APP_VERSION = "0.95.1"

# NACHHER:
APP_VERSION = "0.95.2"
```

---

## 4. Doku-Updates Commit 2

### 4.1 `HISTORY.md` — Eintrag anhaengen

```markdown
## 2026-05-05 v0.95.2 — CQ-Reply-Bug-Fix (P1.5)

**Bug-Wurzel:** 5-Min-Sperre `_WORKED_BLOCK_SECS = 300` blockierte
CQ-Replies an 3 Stellen (qso_state.py:480, 191, 470). Effekt: Stationen
mit denen wir innerhalb 5 Min ein QSO hatten konnten uns nicht erneut
anrufen — App ignorierte sie still.

**Field-Test 05:30-05:33 UTC** zeigte: DA1TST nach :28:00 RR73 versuchte
ab :31:30 mehrfach uns zu rufen (Grid JO31), App sendete weiter CQ
statt Report. Erklaerte Mike's Aussage „manchmal klappt QSO, manchmal
nicht — auch mit fremden Stationen" (selbe Station < 5 Min spaeter
ruft erneut, oft weil unser RR73 nicht angekommen ist).

**Workflow:** voller V1→V2→R1→V3 Diagnose + voller V1→V2→R1→V3 Plan.
DeepSeek-R1 bestaetigte Hauptwurzel, keine zweiten Pfade, keine
Halluzinationen. Alle anderen Hypothesen (Race tx_finished/message_decoded,
_send_cq clearet pending, Slot-Mismatch, is_grid 4-char, Auto-Hunt,
encoder.abort-Race) verworfen.

**Aenderungen `core/qso_state.py`:**
- Z. 119, 120 — `_worked_calls` Dict + `_WORKED_BLOCK_SECS` Konstante geloescht
- Z. 168-176 — Methode `_is_worked_recently` komplett geloescht
- Z. 190-193 — Block #2 in `_process_cq_reply` geloescht
- Z. 440-443 — TX_RR73 Eintrag-Stelle in `_worked_calls` geloescht
- Z. 470 — Block #3 in Caller-Queue-Add geloescht
- Z. 479-482 — Block #1 in Hauptpfad geloescht (-22 Zeilen, +0)

**Mike's Funker-Philosophie:** Filter „Neue Stationen" im RX-Panel ist
die korrekte Stelle (blendet aus Anzeige aus, nicht aus Reply-Pfad).
State-Machine soll nicht filtern — Funker entscheidet.

**Tests:**
- `test_qso_worked_recently_block` invertiert →
  `test_qso_known_station_can_call_again`
- NEU: `test_qso_cq_reply_during_tx_pending_then_processed`
- NEU: `test_qso_caller_queue_accepts_known_station`
- 756 → 758 gruen

**Folgebug-Risiko:**
- Doppel-ADIF wenn Station < 5 Min nach RR73 erneut anruft → TODO P1.7
  (lokaler Duplikat-Filter ADIF/Logbuch). QRZ.com filtert serverseitig
  bereits.
- Endlos-Schleife wenn Station nie 73 sendet → real-Welt-Schutz: Funker
  gibt nach 2-3 Versuchen auf, QSB beendet.
- Stats-Bias: 0 (`_worked_calls` nur in qso_state.py genutzt, R1-grep
  bestaetigt).

**Atomare Commits:**
- (1) `core: remove 5-min worked-recently lockout (P1.5 fix)` —
  qso_state.py + test_modules.py + main.py
- (2) `docs: P1.5 CQ-Reply-Bug fix dokumentation` — HISTORY + HANDOFF + CLAUDE + TODO + Memory
```

### 4.2 `HANDOFF.md` (beide Pfade)

- TODO „🔴 P1.5 CQ-Reply-Recognition-Bug" raus
- Stand auf v0.95.2 (Datum, Test-Count 758)
- P1.7 Lokaler Duplikat-Filter als neuen TODO-Punkt erwaehnt

### 4.3 `CLAUDE.md` (beide Pfade)

- Header `**Aktueller Stand:** v0.95.1` → `**Aktueller Stand:** v0.95.2`
- Test-Count `756 passed` → `758 passed`
- Ein-Satz-Erwaehnung „v0.95.2 — CQ-Reply-Bug-Fix, 5-Min-Sperre raus"

### 4.4 `TODO.md`

- Section „🔴 P1.5 CQ-Reply-Recognition-Bug" → loeschen oder als
  „✅ P1.5 — erledigt v0.95.2 (siehe HISTORY)" markieren.
- P1.7 (Duplikat-Filter) ist bereits drin (vorhin angelegt).
- Debug-Linien `[DBGLOOP]`, `[DBGTX]` Status pruefen — sind die noch
  drin? Falls ja: nach P1.5-Fix entfernen oder Note „bleiben fuer P1.6".

### 4.5 Memory `feedback_funker_entscheidung_filter_in_rx.md` (NEU)

Lesson aus 2026-05-05: bei Filter-Entscheidungen pruefen ob Filter im
**Anzeige-Pfad** oder **Verarbeitungs-Pfad** gehoert. Mike's Linie:
**Anzeige** = okay, **Verarbeitung** = Funker-Entscheidung. State-
Machine soll nicht stillschweigend filtern.

Memory-Index `MEMORY.md` Eintrag ergaenzen.

---

## 5. Verifikations-Schritte (vor Commit)

1. **Tests gruen:** `./venv/bin/python3 -m pytest tests/ -q` → 758 passed
2. **App startet:** `./venv/bin/python3 main.py` (kurz, dann zu)
3. **Trockentest CQ-Reply:** unit-Tests decken die 3 Pfade ab — kein
   Field-Test noetig vor Commit.
4. **Field-Test post-Commit:** Mike testet DA1TST-Szenario nach Commit 1.

---

## 6. Risikoanalyse

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| Test-Coverage-Luecke (uebersehener Block) | gering | R1-Pruefung bestaetigt 3 Stellen vollstaendig |
| Doppel-ADIF-Eintrag bei kurzem Re-Call | mittel | TODO P1.7 (lokaler Duplikat-Filter), QRZ filtert serverseitig |
| Endlos-Schleife wenn Station nie 73 | gering | Real-Welt: Funker gibt auf nach 2-3 Versuchen |
| Stats-Bias | 0 | R1-grep bestaetigt: `_worked_calls` nur in qso_state.py |
| Bestehende QSO-Flows kaputt | gering | -22 Zeilen Loeschung, keine neue Logik. Tests decken alle Pfade ab |
| Caller-Queue-Pop Race | gering | `_process_cq_reply` Block #2 weg, aber andere Pre-Conds bleiben (cq_mode-Check Z. 186-188, is_73/is_rr73 Z. 196-198) |

---

## 7. Auftrag an V2 / R1

Bitte pruefen:

1. **Diff-Vollstaendigkeit:** sind alle 7 Stellen (Z. 119, 120, 168-176,
   190-193, 440-443, 470, 479-482) korrekt erfasst? Gibt es eine 8.
   Stelle die Plan-V1 uebersieht?

2. **Test-Coverage:** decken die 3 Tests (1 invertiert + 2 neu) den Bug
   und seine Folgen ab? Insbesondere:
   - Hauptpfad CQ_WAIT-Empfang: ✓
   - Hauptpfad CQ_CALLING-Empfang waehrend TX: ✓
   - Caller-Queue-Add: ✓
   - Was fehlt: Caller-Queue-Pop nach QSO-Ende mit zwei Stationen, eine
     vorher gearbeitet? (R1 entscheidet ob das ein 4. Test braucht)

3. **Reihenfolge der Commits:** Code+Tests in EINEM Commit (Plan-V1)
   oder 2 Commits (Code allein → Tests separat)? Bisecting-Vorteil
   vs. Reinheit der atomaren Aufteilung.

4. **Folgebug-Risiko:** ist die Doppel-ADIF-Mitigation (TODO P1.7)
   ausreichend, oder muss in v0.95.2 schon ein Stub-Schutz rein?

5. **Memory-Lesson-Formulierung:** beschreibt
   `feedback_funker_entscheidung_filter_in_rx.md` die Lesson korrekt?

6. **Versions-Bump:** v0.95.1 → v0.95.2 ist Bugfix-Patch. Korrekt?
   (CLAUDE.md sagt: „Bei Bugfix-only: unveraendert lassen". Aber das
   ist ein wesentlicher Bug-Fix → Patch-Bump v0.95.2 macht Sinn.)

7. **CLAUDE.md-Header-Update:** V1 sagt nur Test-Count + Datum. Reicht
   das? Oder soll der lange „Stand"-Block einen v0.95.2-Eintrag
   bekommen analog v0.95.1?

Antworten:
- bestaetigt / aenderung pro Punkt
- konkrete Code-Diff-Verbesserungen
- KEINE neue Logik vorschlagen — nur Plan-Korrekturen.

---

## 8. Was V1 NICHT macht

- Kein eigentlicher Code-Diff in den Files.
- Kein Field-Test.
- Kein Push.
- Kein P1.7-Implementation (separater Workflow).

---

**V1 Ende. V2 = frische-KI Self-Review. V3 = R1-Review-Findings.
Plan-Mode + Commits erst nach Mike-Freigabe.**
