# P1.OMNI-START — V2 (Self-Review)

**Status:** V2 (Self-Review nach V1, alle V1-Fragen via Code-Verifikation
beantwortet).
**Folge zu V1.** Mike-Field-Test 08.05.2026, Bug latent seit v0.78 (30.04.2026).

---

## V1 → V2 Aenderungen

V1 hatte 7 offene Fragen. V2 hat alle via grep + Read verifiziert.
Wichtigster neuer Befund: **HALT-Button stoppt OMNI nicht!** Plus
`_was_cq`-Mechanismus fuer CQ-Resume nach QSO **funktioniert ohne Extra-
Code** dank `_process_cq_reply`.

---

## Pflicht-Kopf (fuer R1 in Schritt 2)

```
Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool fuer einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem loesen.
Strukturierte Liste: Luecken, Unklarheiten, Widersprueche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexitaet nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.
```

---

## 1. Field-Test-Beweis (unveraendert von V1)

Mike, 16:08 UTC, 08.05.2026, Diversity-Modus, Easter-Egg lange aktiviert.
Klick auf `btn_omni_cq` → Toggle-State korrekt → Statusbar zeigt
"Even=0 Odd=0" → KEIN CQ wird gesendet, auch nach mehreren Zyklen.

---

## 2. Bug-Wurzel + Code-Verifikation

### W1 — `ui/main_window.py:676-689` `_on_btn_omni_cq_toggled`
Setzt nur `omni_tx.active=True`. **Kein** `qso_sm.start_cq()`.

### W2 — `ui/main_window.py:691-703` `_on_omni_stopped`
Setzt nur Button-State zurueck. **Kein** `qso_sm.stop_cq()`. → Wenn OMNI
gestoppt wird (z.B. band_change), bleibt `cq_mode=True` haengen.

### W3 — `ui/mw_qso.py:211-230` `_on_cancel` (HALT-Button)
Stoppt CQ + QSO + TX + AP-Lite + Auto-Hunt. **Stoppt NICHT OMNI-TX!**
→ Inkonsistenz: HALT setzt `cq_mode=False`, aber `omni_tx.active=True`
bleibt. Symptom: Button bleibt visuell gedrueckt, OMNI-Counter laufen
weiter, beim naechsten CQ-Send greift Filter wieder, aber kein CQ kommt
weil `cq_mode=False`.

### W4 — Test-Coverage-Luecke
`tests/test_omni_tx.py` testet nur Modul-Logik isoliert. Keine
Integration mit `qso_sm.start_cq()` oder Mainwindow-Toggle.

---

## 3. V1-Fragen — Antworten aus Code-Verifikation

**Q1: Was wenn Klick OMNI-CQ waehrend `state != IDLE`?**
✅ `qso_state.py:152` `if state not in (IDLE, CQ_WAIT): return` → silent
no-op. **V2-Entscheidung:** OMNI-Toggle bei laufendem QSO blockieren mit
Statusbar-Hinweis. Toggle-State revertieren. Dann ist's konsistent.

**Q2: CQ-Reply waehrend OMNI aktiv → CQ-Resume?**
✅ Funktioniert OHNE Extra-Code. Pfad:
1. OMNI aktiv, `cq_mode=True`, `_send_cq()` schickt "CQ DA1MHH JO31"
2. `_on_send_message` greift OMNI-Filter (RX-Slot skip oder TX-Slot Even/Odd)
3. CQ-Reply kommt → `qso_state._process_cq_reply()` setzt `_was_cq=True`
   (qso_state.py:197), state geht zu TX_REPORT
4. QSO laeuft normal (Reply-Strings, kein "CQ ..." → OMNI-Filter NICHT
   aktiv → normal-Pfad) → ANT1 (encoder zentral)
5. QSO endet → `_resume_cq_if_needed()` (qso_state.py:307+314) sieht
   `_was_cq=True` → setzt `cq_mode=True` wieder → `_send_cq()` →
   OMNI-Filter greift wieder
6. → **Reply-Resume funktioniert ohne Aenderung an OMNI-Code.**

**Q3: HALT + OMNI aktiv → Inkonsistenz.**
✅ Bestaetigt (W3). **V2-Entscheidung:** HALT-Handler `_on_cancel` muss
`self._omni_tx.stop_omni_tx("manual_halt")` rufen wenn aktiv.

**Q4: Stop-Reasons-Symmetrie — alle Reasons sollen CQ stoppen?**
✅ JA. Alle Stop-Reasons (manual_halt, band_change, ft_mode_change,
rx_mode_change, totmann_expired, easter_egg_off, superseded) sollen
auch CQ-Loop beenden. **V2-Entscheidung:** `_on_omni_stopped(reason)`
zentral `qso_sm.stop_cq()` rufen — egal welcher Reason.

**Q5: OMNI nach App-Restart automatisch?**
✅ Nein. Easter-Egg + Klick sind Pflicht. Default OFF. Unveraendert.

**Q6: Tests Qt-offscreen?**
✅ Toggle-Handler-Test ja (Mainwindow + Mocks). `qso_sm.start_cq()`-Effekt
ja. Modul-Tests `omni_tx.py` bleiben Qt-frei.

**Q7: Cooldown auf btn_omni_cq?**
✅ Wie in v0.78 explizit weggelassen. OMNI ist passiver, kein Bot-Tarn-
Schutz noetig (HISTORY v0.78). Unveraendert.

---

## 4. Lessons L1-L8 (Self-Review)

### L1 — `_was_cq`-Mechanismus traegt CQ-Resume durch
V1 hatte gefragt ob CQ nach QSO-Antwort automatisch resumed. Antwort: JA,
ohne Extra-Code. `_process_cq_reply` setzt `_was_cq=True`, nach QSO ruft
`_resume_cq_if_needed()` `start_cq()` wieder → OMNI-Filter greift wieder.
**Konsequenz:** V3 muss NICHTS am QSO-Reply-Pfad aendern.

### L2 — HALT-Button-Inkonsistenz ist eigenes Problem
V1 hatte das nur als Risiko erwaehnt, V2 macht es zum Pflicht-Fix in §5.
Ohne den Fix gibt es einen sichtbaren Inkonsistenz-Bug (Button bleibt
gedrueckt nach HALT).

### L3 — `_on_omni_stopped` zentraler Cleanup-Punkt
Statt jedem Stop-Aufrufer `qso_sm.stop_cq()` aufzubuerden, machen wir's
zentral im Slot. ALLE Stop-Reasons triggern den gleichen Cleanup. KISS.

### L4 — Diversity-Lock + OMNI
`btn_cq` ist in Diversity versteckt → User kann NICHT manuell `cq_mode=True`
aktivieren. Nur OMNI-Toggle aktiviert CQ-Loop in Diversity. Korrekte
Architektur, OMNI ist DIE Diversity-CQ-Funktion.

### L5 — `state != IDLE`-Edge-Case (Mike klickt OMNI waehrend QSO)
V1 fragte, V2 entscheidet: **Toggle blockieren**, Statusbar "OMNI nur
im IDLE startbar — laufendes QSO erst beenden", Button-State revertieren.
Sonst hat Mike einen Toggle der gedrueckt aussieht aber nichts tut.

### L6 — `_was_cq` ist State-Machine-Internal
Externe Mainwindow-Code-Pfade sollten `_was_cq` nicht direkt setzen.
P1.HUNT-SNR und v0.95.2 haben das mehrfach beruehrt — vermeidbar.
OMNI-Fix bleibt aussen, nutzt nur `start_cq()` / `stop_cq()`.

### L7 — Test-Skeleton (8 Tests)
1. `test_omni_toggle_starts_cq_loop` — `_on_btn_omni_cq_toggled(True)` →
   `omni_tx.active=True` AND `qso_sm.cq_mode=True` AND `_send_cq` aufgerufen.
2. `test_omni_toggle_off_stops_cq_loop` — Toggle off → `omni_tx.active=False`
   AND `qso_sm.cq_mode=False`.
3. `test_omni_band_change_stops_cq` — `_omni_tx.stop_omni_tx("band_change")`
   → `_on_omni_stopped("band_change")` → `qso_sm.cq_mode=False`.
4. `test_omni_totmann_stops_cq` — gleiches Schema fuer "totmann_expired".
5. `test_omni_superseded_stops_cq` — Auto-Hunt-Klick → OMNI stop_omni_tx
   ("superseded") → `qso_sm.cq_mode=False`.
6. `test_omni_blocked_during_active_qso` — qso_sm.state=WAIT_REPORT →
   `_on_btn_omni_cq_toggled(True)` → `omni_tx.active=False` (nicht
   aktiviert) AND `qso_sm.cq_mode=False` AND Statusbar-Message.
7. `test_halt_button_stops_omni` — `_on_cancel` mit OMNI aktiv →
   `omni_tx.active=False` AND `qso_sm.cq_mode=False`.
8. `test_cq_reply_during_omni_keeps_was_cq` — OMNI aktiv, `_process_cq_reply`
   → `_was_cq=True` (Backward-compat-Beweis: Resume nach QSO unveraendert).

**Plus:** Bestehende Tests `tests/test_omni_tx.py` muessen alle gruen
bleiben (Modul-Tests, kein Eingriff in `omni_tx.py`).

### L8 — Tests-Soll: 1003 → 1011 (+8)

---

## 5. V2-finaler Plan (vor R1-Review)

### Diff 1 — `ui/main_window.py` `_on_btn_omni_cq_toggled` (Z.676-689)

```python
def _on_btn_omni_cq_toggled(self, checked: bool):
    """User-Klick auf btn_omni_cq: enable + start CQ-Loop / stop CQ-Loop.

    P1.OMNI-START (v0.95.22): Aktiviert ZUSAETZLICH den CQ-Loop in qso_state,
    sonst greift OMNI-Slot-Filter nie. Mutually-exclusive: laufender Auto-Hunt
    wird via "superseded" gestoppt.

    Bei laufendem QSO (state != IDLE/CQ_WAIT): Toggle blockieren, Statusbar-
    Hinweis. Sonst haette Mike einen aktivierten Button ohne Wirkung.
    """
    if checked and not self._omni_tx.active:
        # P1.OMNI-START: Wenn QSO laeuft → blockieren, kein OMNI-Start
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            btn = self.control_panel.btn_omni_cq
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
            self.statusBar().showMessage(
                "OMNI-CQ nur im Leerlauf startbar — erst laufendes QSO beenden",
                4000,
            )
            return
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        self._omni_tx.enable()
        # P1.OMNI-START: CQ-Loop in qso_state aktivieren —
        # OMNI-Filter in _on_send_message greift erst wenn jemand
        # send_message("CQ ...") emittet. start_cq() macht genau das.
        self.qso_sm.start_cq()
        self.control_panel.update_omni_tx(True)
        self._update_statusbar()
        print("[OMNI-TX] User-Start")
    elif not checked and self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
```

### Diff 2 — `ui/main_window.py` `_on_omni_stopped` (Z.691-703)

```python
def _on_omni_stopped(self, reason: str):
    """Slot fuer omni_stopped(reason): Button-State + Statusbar zuruecksetzen.

    P1.OMNI-START (v0.95.22): ALLE Stop-Reasons stoppen den CQ-Loop in
    qso_state — sonst bleibt cq_mode=True haengen waehrend OMNI nicht
    mehr lauft.

    Im Gegensatz zu Auto-Hunt KEIN UI-Reflexions-Cooldown — OMNI ist passiver,
    kein Bot-Tarn-Schutz noetig.
    """
    btn = self.control_panel.btn_omni_cq
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
    # P1.OMNI-START: CQ-Loop stoppen (idempotent — stop_cq macht nix wenn cq_mode=False)
    if self.qso_sm.cq_mode:
        self.qso_sm.stop_cq()
    self.control_panel.update_omni_tx(False)
    self._update_statusbar()
    print(f"[OMNI-TX-UI] Stop ({reason})")
```

### Diff 3 — `ui/mw_qso.py` `_on_cancel` (Z.211)

```python
@Slot()
def _on_cancel(self):
    """HALT — stoppt ALLES: CQ, QSO, TX, Messung, OMNI, Auto-Hunt."""
    self._active_qso_targets.clear()
    self._pending_station_click = None
    self.rx_panel.set_active_call("")
    if self.encoder.is_transmitting:
        self.encoder.abort()
        if self.radio.ip:
            self.radio.ptt_off()
    self.qso_sm.stop_cq()
    self.qso_sm.cancel()
    self.control_panel.set_cq_active(False)
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_end()
    # P1.OMNI-START (v0.95.22): OMNI ebenfalls stoppen
    if self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
    self.qso_panel.add_info("HALT — alles gestoppt")
    self.statusBar().showMessage("HALT — CQ, QSO, TX, OMNI gestoppt", 5000)
    print("[HALT] Alles gestoppt")
```

### Diff 4 — `main.py` APP_VERSION

```python
APP_VERSION = "0.95.22"
```

### Diff 5 — NEU `tests/test_p1_omni_start.py` (8 Tests aus L7)

---

## 6. Risiken

- **Bestehende Tests:** `tests/test_omni_tx.py` testet `omni_tx.py` modulweise.
  Keine Aenderung dort, sollten gruen bleiben. Mainwindow-Tests muessten
  ggf. `qso_sm.start_cq` mocken.
- **Zwei `start_cq()`-Aufrufe parallel:** Falls Easter-Egg waehrend OMNI
  aktiv deaktiviert wird → `omni_stopped("easter_egg_off")` →
  `_on_omni_stopped` ruft `stop_cq`. Sicher.
- **`stop_cq()` waehrend laufendem QSO:** `stop_cq` setzt `cq_mode=False`,
  `_set_state(IDLE)` nur wenn state in (CQ_CALLING, CQ_WAIT). Laufendes
  QSO wird NICHT abgebrochen (gut). Aber `_was_cq` bleibt → nach QSO-Ende
  versucht `_resume_cq_if_needed` CQ wieder aufzunehmen, obwohl OMNI
  gestoppt wurde. **Pruefen:** `_resume_cq_if_needed` ruft `start_cq()`
  ohne `omni_tx.active`-Check. Wenn OMNI gestoppt wurde aber QSO endet,
  startet wieder CQ ohne OMNI-Filter (`omni_tx.active=False`) → CQ wird
  durchgehend gesendet (kein Pattern). **Halb-Problem:** Mike hat OMNI
  bewusst gestoppt waehrend QSO lief, das System resumed regulaeres CQ.
  Eigentlich Sollverhalten? Oder will Mike bei Stop-while-QSO komplett
  CQ aus?
  
  **R1-Pruefauftrag dazu (8.1):** Wuenscht sich Mike bei Stop-while-QSO
  komplett CQ-aus, oder nur OMNI-aus + regulaeres CQ resume? Aktuelle
  V2-Variante: regulaeres CQ resume (default-Verhalten via `_was_cq`).

---

## 7. R1-Pruefauftraege (10)

R1-Plan-Review soll explizit pruefen:

1. **`_on_omni_stopped` ruft `qso_sm.stop_cq()` zentral:** korrekt? Oder
   gibt's Stop-Reasons wo CQ weiterlaufen sollte?
2. **HALT mit OMNI aktiv:** ist `omni_tx.stop_omni_tx("manual_halt")` der
   richtige Reason? Oder sollte ein neuer Reason "halt_button" rein?
3. **`state != IDLE`-Block:** soll OMNI-Klick komplett blockiert werden,
   oder OMNI aktivieren + erst nach QSO-Ende effektiv? V2 nimmt blockieren —
   ist das die Mike-erwartete UX?
4. **`_resume_cq_if_needed` nach OMNI-Stop:** wenn Mike OMNI waehrend QSO
   stoppt, resumed `_was_cq=True` regulaeres CQ. Gewuenscht? Oder soll
   bei Stop-while-QSO `_was_cq=False` gesetzt werden?
5. **Auto-Hunt-Symmetrie:** Auto-Hunt hat keinen `cq_mode`-Eingriff. OK so?
   (Auto-Hunt ist station-spezifisch, nicht CQ-broadcast.)
6. **OMNI-Filter funktioniert nur bei `"CQ "`-Strings:** Reply-Strings
   gehen normal durch. Sicher dass kein OMNI-Filter-Bypass auf Replies?
7. **Tests-Coverage:** sind die 8 Tests aus L7 ausreichend? Edge-Cases
   uebersehen?
8. **Hardware ANT1:** ist garantiert via encoder.transmit zentral. Nicht
   nochmal pruefen.
9. **Race: `start_cq()` setzt `cq_mode=True` und ruft `_send_cq()` sofort.**
   `_send_cq` macht `send_message.emit("CQ ...")` → `_on_send_message`
   → OMNI-Filter `should_tx()` → bei Pos 0 (Even) Counter=0 → wird gesendet.
   Aber der allererste Slot nach `enable()` ist Pos 0 — `should_tx()`
   returnt `(True, True)` → Encoder.tx_even=True, sendet auf Even.
   **Frage:** Korrekt? Oder ist Pos 0 evtl. eines RX-Slots gleich nach
   dem Klick (wenn Mike mitten im Slot klickt)?
10. **Doppel-Aktivierung:** Was passiert wenn Mike OMNI klickt, OMNI laeuft,
    Mike klickt nochmal aus (Toggle off) und sofort wieder ein? Sequence:
    `enable() → start_cq() → stop_omni_tx("manual_halt") → omni_stopped →
    stop_cq() → enable() → start_cq()`. Sicher? Counter werden beim
    `enable()` zurueckgesetzt → ja sicher.

---

## 8. V2-Diff zu V1 — was bleibt, was aendert sich

| V1 | V2 |
|---|---|
| 7 offene Fragen | alle 7 beantwortet via grep |
| Fix nur Toggle-Handler | Fix Toggle + Stop-Slot + HALT-Handler (3 Stellen) |
| Tests +7 geschaetzt | +8 spezifiziert (L7 Skeleton) |
| state!=IDLE als offene Frage | als Block-mit-Statusbar-Hinweis loesen |
| HALT als Risiko | als Pflicht-Fix |
| ~10 Zeilen Diff | ~25 Zeilen Diff (3 Stellen, klein) |

---

## 9. Out-of-Scope

- Refactor von `omni_tx.py` (bleibt unveraendert)
- 5-Slot-Pattern oder block_cycles aendern
- Stop-Reason-Tabelle erweitern (V2-L3 entscheidet zentral cleanup)
- Easter-Egg-UI-Logik (control_panel.py)
- Auto-Hunt-Pfad (separate Mode-Funktion)
- Hardware-Antenne-Logik (Encoder zentral)
- `_resume_cq_if_needed` aendern (regulaeres CQ-Resume nach OMNI-Stop ist
  V2-Default; falls R1 anders entscheidet, wird's in V3 ergaenzt)

---

**V2-Ende. Bereit fuer R1-Plan-Review (DeepSeek-Reasoner).**
