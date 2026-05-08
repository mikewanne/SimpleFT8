# P1.OMNI-START — V1 (Diagnose + Plan-Entwurf)

**Status:** V1 (initial draft, Mike-Field-Test 08.05.2026 16:08 UTC v0.95.21).
**Autor:** Claude (mit Mike-Beobachtung).
**Latent seit v0.78 (30.04.2026) — OMNI-TX scharfgeschaltet aber Toggle-Handler unvollstaendig.**

---

## 1. Field-Test-Beweis (Mike, 16:08 UTC, 08.05.2026)

Diversity-Modus, Easter-Egg lange aktiviert (OMNI-CQ-Button sichtbar).
Mike klickt `btn_omni_cq` → Button bleibt gedrueckt (Toggle-State korrekt) →
Statusbar zeigt zusaetzlich "Even=0 Odd=0" → **aber kein CQ wird gesendet**.
Auch nach mehreren Zyklen passiert nichts.

Erwartetes Verhalten (per `docs/OMNI_TX_DESIGN.md`):
- Klick auf btn_omni_cq → CQ-Loop startet automatisch in Diversity
- 5-Slot-Pattern Even/Odd-Rotation: Pos 0 TX, Pos 1 TX, Pos 2-4 RX
- Block-Wechsel nach 80 Zyklen
- Stop bei: erneuter Klick, band_change, ft_mode_change, rx_mode_change,
  totmann_expired, easter_egg_off, superseded

---

## 2. Bug-Wurzel (Code-Verifikation 08.05.2026)

### W1 — `ui/main_window.py:676-689` `_on_btn_omni_cq_toggled`

```python
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_tx.active:
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        self._omni_tx.enable()
        self.control_panel.update_omni_tx(True)
        self._update_statusbar()
        print("[OMNI-TX] User-Start")
    elif not checked and self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")
```

**Problem:** Setzt nur `omni_tx.active = True` (Slot-Filter aktiviert).
Aber `qso_sm.cq_mode` bleibt `False` → niemand ruft `_send_cq()` →
keine `send_message.emit("CQ ...")` → `_on_send_message` wird nie
gerufen → OMNI-Slot-Filter greift nie → kein TX.

### W2 — Code-Pfad-Analyse

**Was passiert beim aktuellen Klick:**
1. `omni_tx.enable()` → `active=True`, Slot-Index=0, Block=1, Counter=0 ✓
2. `mw_cycle._on_cycle_decoded` ruft `omni_tx.advance()` pro Zyklus → `_slot_index` rotiert ✓
3. **Aber:** `qso_sm.cq_mode = False` → `qso_sm._send_cq()` wird nie aufgerufen
4. → `_on_send_message` wird nie mit `"CQ ..."` aufgerufen
5. → OMNI-Filter (`if message.startswith("CQ ")`) greift nie
6. → `cq_even_count` / `cq_odd_count` bleiben 0
7. → `encoder.transmit()` wird nicht gerufen → kein TX

### W3 — Diversity-Modus btn_cq versteckt

`main_window.py:672`: `self.control_panel.btn_cq.setHidden(is_diversity)`.
In Diversity gibt es KEINEN normalen CQ-Button → Mike kann `cq_mode=True`
gar nicht manuell aktivieren. OMNI muss das selbst tun.

### W4 — Existierende Tests verfehlen den Bug

`tests/test_omni_tx.py` testet nur Modul-Logik (`enable()`, `should_tx()`,
`advance()` isoliert). Keine End-to-End-Integration mit `qso_sm.start_cq()`
oder `_on_send_message`. Bug ist seit v0.78 (30.04.2026) latent.

---

## 3. Fix-Konzept (V1, KISS)

**Option A — Toggle-Handler ergaenzt um qso_sm-Aufruf (bevorzugt):**

```python
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_tx.active:
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        self._omni_tx.enable()
        # P1.OMNI-START (v0.95.22): CQ-Loop in qso_state aktivieren —
        # OMNI-Filter in _on_send_message greift erst wenn jemand
        # send_message("CQ ...") emittet. start_cq() macht genau das.
        self.qso_sm.start_cq()
        self.control_panel.update_omni_tx(True)
        self._update_statusbar()
        print("[OMNI-TX] User-Start")
    elif not checked and self._omni_tx.active:
        self._omni_tx.stop_omni_tx("manual_halt")

def _on_omni_stopped(self, reason: str):
    btn = self.control_panel.btn_omni_cq
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
    # P1.OMNI-START (v0.95.22): CQ-Loop stoppen
    if self.qso_sm.cq_mode:
        self.qso_sm.stop_cq()
    self.control_panel.update_omni_tx(False)
    self._update_statusbar()
    print(f"[OMNI-TX-UI] Stop ({reason})")
```

**Option B (verworfen) — OMNI macht eigene `_send_cq`-Schleife:**
Reimplementiert was `qso_sm` schon tut. Verstoesst gegen DRY/KISS.
Plus: Reply-Handling, QSO-Lifecycle, Logging — alles waere zu duplizieren.

**Option C (verworfen) — `omni_tx.enable()` ruft direkt qso_sm.start_cq():**
omni_tx.py kennt qso_sm nicht (Architektur-Trennung). Coupling unsauber.

---

## 4. Akzeptanzkriterien (10 ACs)

1. ✅ Klick auf `btn_omni_cq` (Diversity, Easter-Egg an) → CQ wird auf
   `Pos 0 Even` gesendet, sichtbar in QSO-Panel + Log `[OMNI-TX] TX auf Even`.
2. ✅ Naechster TX-Slot (Pos 1) sendet CQ auf `Odd` → Log `[OMNI-TX] TX auf Odd`.
3. ✅ Pos 2-4 sind RX → Log `[OMNI-TX] RX-Slot → skip CQ`.
4. ✅ Statusbar `Ω Even=N Odd=M` zeigt steigende Counter.
5. ✅ Erneuter Klick (Toggle off) → `qso_sm.stop_cq()` + `omni_stopped("manual_halt")`
   → CQ-Loop stoppt, Button entriegelt.
6. ✅ Bandwechsel waehrend OMNI aktiv → `omni_stopped("band_change")` →
   `qso_sm.stop_cq()` lauft → CQ-Loop stoppt sauber.
7. ✅ Mutually-exclusive: laufender Auto-Hunt wird via "superseded" gestoppt
   bevor OMNI startet.
8. ✅ CQ-Antwort kommt rein → normaler QSO-Pfad → `omni_tx.on_qso_started()`
   resetet Counter (block bleibt) → nach RR73/Timeout: `qso_sm` resumed
   `cq_mode=True` und naechster Slot ist wieder OMNI.
9. ✅ Hardware-Sicherheit: `encoder.transmit()` ruft `set_tx_antenna("ANT1")`
   zentral (Encoder-Pfad) — OMNI muss nichts extra tun.
10. ✅ Tests 1003 → ~1010 (+7 geschaetzt: Toggle-Start, Toggle-Stop,
    band_change-Stop, Mutually-exclusive, CQ-Antwort-Resume, Edge-Case
    laufendes-QSO, Backward-compat omni_tx Modul-Tests bleiben gruen).

---

## 5. Offene Fragen (an V2-Self-Review)

1. **Was wenn Klick OMNI-CQ waehrend `qso_sm.state != IDLE`?**
   `start_cq()` macht `if state not in (IDLE, CQ_WAIT): return` → silent fail.
   Soll OMNI dann nicht aktiviert werden? Oder OMNI aktivieren + warten bis QSO endet?
2. **CQ-Reply waehrend OMNI aktiv:** `qso_sm._process_cq_reply()` setzt
   `_was_cq=True` damit nach QSO-Ende CQ resumed. Funktioniert das mit OMNI?
   Oder muss `_was_cq` anders gehandelt werden?
3. **Edge-Case: User klickt OMNI ↔ HALT-Button.** HALT setzt `cq_mode=False`
   via `cancel()`. Aber `omni_tx.active` bleibt True → Inkonsistenz?
4. **Stop-Reasons-Symmetrie:** Bei JEDEM `omni_stopped(reason)` muss
   `qso_sm.stop_cq()` laufen, oder gibt's Reasons wo CQ weiter laufen soll?
   Aktuelle Reasons: manual_halt, band_change, ft_mode_change, rx_mode_change,
   totmann_expired, easter_egg_off, superseded, timer_expired (nur Auto-Hunt).
5. **OMNI nach App-Start automatisch?** Nein — Easter-Egg + Klick sind
   Pflicht-Aktivierung. Default OFF nach Restart.
6. **Tests: brauchen Qt-offscreen?** Toggle-Handler-Test ja (UI),
   `qso_sm.start_cq()`-Effekt ja. Modul-Tests `omni_tx.py` bleiben Qt-frei.
7. **Cooldown auf btn_omni_cq?** Auto-Hunt hat 5s Reflex-Cooldown nach Stop.
   OMNI hat aktuell keinen — laut HISTORY v0.78 explizit weggelassen
   (`OMNI ist passiver, kein Bot-Tarn-Schutz noetig`). Beibehalten.

---

## 6. Risiken

- **Bestehende Tests koennten brechen:** Falls Tests `_on_btn_omni_cq_toggled`
  ohne `qso_sm`-Mock testen, koennten sie auf den neuen Aufruf nicht
  vorbereitet sein. V2 muss `tests/test_omni_tx.py` + ggf. Mainwindow-Tests
  pruefen.
- **`stop_cq()` bei state in (TX_*)`:** `stop_cq` setzt `cq_mode=False`,
  `_set_state(IDLE)` nur wenn `state in (CQ_CALLING, CQ_WAIT)`. Wenn ein
  laufendes QSO da ist, bleibt der State erhalten — gutes Verhalten,
  laufendes QSO wird nicht abgebrochen.
- **Doppelter `start_cq()`-Aufruf:** Wenn Mike Easter-Egg deaktiviert und
  reaktiviert ohne dazwischen `omni_stopped` zu triggern? — Programmatischer
  Path ueber Easter-Egg deaktiviert ruft `disable()` was `stop_omni_tx
  ("easter_egg_off")` triggert → `omni_stopped` Signal → `_on_omni_stopped`
  ruft `qso_sm.stop_cq()`. Sicher.

---

## 7. Workflow-Plan

V1 (diese Datei) → V2 (Self-Review, Code-Verifikation der offenen Fragen) →
R1 (DeepSeek-Reasoner Plan-Review) → V3 (Compact-fest) → Mike-Freigabe →
Code → Final-R1 → atomare Commits + Doku.

**Erwartung:** ~30 Min Workflow + Code, ~15 Zeilen Diff (Toggle-Handler +
omni-stopped-Handler erweitern), +7 Tests, APP_VERSION 0.95.21 → 0.95.22.

---

## 8. Nicht im Scope

- Refactor von `omni_tx.py` (bleibt unveraendert)
- Aenderung des 5-Slot-Patterns oder block_cycles
- Aenderung der Stop-Reason-Tabelle
- Easter-Egg-UI-Logik (control_panel.py)
- Auto-Hunt-Pfad (separate Mode-Funktion)
- Hardware-Antenne-Logik (Encoder macht das schon zentral)
