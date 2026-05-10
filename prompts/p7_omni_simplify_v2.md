# P7.OMNI-SIMPLIFY — V2 (Self-Review von V1)

**Datum:** 2026-05-10 ~10:50 UTC
**Vorgaenger:** V1 (`p7_omni_simplify_v1.md`)
**Status:** V2 Self-Review — als „frische KI" Luecken in V1 finden

---

## 0. Kontext

V1 plant OMNI radikal zu vereinfachen: 1 Slot-Paritaet, gekoppelt an Diversity-Re-Mess.
Diese V2 prueft V1 auf Luecken, bevor R1 (DeepSeek-Reasoner) drauf schaut.

---

## L1 KRITISCH: REMEASURE_INTERVAL_SECONDS = 3600 (1 STUNDE)

**Befund:** `core/diversity.py:476` `REMEASURE_INTERVAL_SECONDS = 3600`. Re-Mess passiert nur **alle 1 Stunde**, NICHT alle 5-6 Min wie Mike erinnert.

**Konsequenz fuer P7:**
- OMNI bleibt 1h auf einer Slot-Paritaet
- Stationen der anderen Paritaet hoeren OMNI 1h lang nicht
- Coverage-Luecke: 50% fuer 1h pro Wechsel

**3 Loesungs-Optionen:**

### Option A — Mike akzeptiert 1h-Intervall
Spec passt, kein Code-Aufwand zusaetzlich. Aber 1h ohne Wechsel ist DEUTLICH mehr als Mike erwartet hat. Hobby-Funker erwartet evtl. haeufiger.

### Option B — Eigener OMNI-Timer (entkoppelt)
OMNI hat eigenen Wechsel-Timer (z.B. 10 Min). Hat zwei Trigger:
1. Re-Mess (existing) — aber selten
2. Eigener Timer — 10 Min nach letztem Wechsel
→ Wechsel passiert **bei NAECHSTEM cycle_start nach 10 Min ODER Re-Mess**, was zuerst kommt.

Komplikation: Was wenn QSO laeuft? OMNI pausiert, Timer läuft weiter, beim Resume sofort Wechsel?

### Option C — Re-Mess-Intervall verkuerzen
`REMEASURE_INTERVAL_SECONDS` von 3600 auf z.B. 600 (10 Min) setzen. ABER das aendert globales Diversity-Verhalten — VERSTOSST gegen Mike's „Diversity unantastbar"!

**V2-Empfehlung:** Option B (OMNI-eigener Timer). Diversity bleibt unangetastet, OMNI wechselt haeufiger. Mike-Praezisierung noetig.

**Mike-Frage 1:** Wie oft soll Slot-Paritaet wechseln? 5/10/15/30 Min?

---

## L2 KRITISCH: cq_active blockt should_remeasure (mw_cycle.py:614-618)

**Befund:**
```
cq_active = (
    self.qso_sm.state in (QSOState.CQ_CALLING, QSOState.CQ_WAIT)
    or getattr(self.qso_sm, 'cq_mode', False)
)
if self._diversity_ctrl.should_remeasure(qso_active, cq_active):
    self._diversity_ctrl.start_measure()
```

OMNI nutzt `qso_sm.cq_mode` NICHT (Memory-Pflicht). qso_sm.state ist IDLE waehrend pure-OMNI. → `cq_active=False` → Re-Mess kann triggern. ✓ V1 OK.

**Aber Edge:** wenn Mike NORMAL-CQ und OMNI gleichzeitig nutzen wollte (Spec verbietet das aber UI-mutually-exclusive). Bei OMNI-only kein Konflikt.

**V2-OK** — kein Aenderungsbedarf, aber dokumentieren.

---

## L3: resume_after_qso(last_was_even) — Signatur veraltet

**Befund:** `core/omni_cq.py:133` `resume_after_qso(self, last_was_even: bool)` setzt `_block` basierend auf last_was_even. Bei P7 entfaellt `_block`. Last_was_even ist irrelevant.

**Problem:** Bestehende Aufrufer (`mw_qso`, `main_window`) uebergeben last_was_even. Wenn ich Signatur aendere, brechen sie.

**Loesung:** Signatur kompatibel halten, Parameter ignorieren:
```
def resume_after_qso(self, last_was_even: bool | None = None) -> None:
    if not self._paused: return
    self._paused = False
    # P7: _cq_tx_even bleibt unveraendert (Sync ueber Re-Mess, nicht Resume)
```

Oder: Aufrufer mit-anpassen. **V2-Empfehlung:** Signatur kompatibel halten (KISS, weniger Risiko).

---

## L4: counter_changed Signal-Format aendert

**Befund:** `core/omni_cq.py:57` `counter_changed = Signal(int, int)` — emit (even_count, odd_count). main_window:264 connected. main_window:747 handler. main_window:996-997 zeigt UI.

Bei P7 nur 1 Counter — Signal-Format aendert.

**Loesung:**
- Variante A: Signal bleibt `(int, int)` — emit (cq_count, 0). UI zeigt "Even=10 Odd=0" wenn Paritaet Even, sonst (0, cq_count). Hacky.
- Variante B: Signal aendert auf `(int)`. Handler/UI muss angepasst werden.
- Variante C: Signal-Pair (count, current_tx_even). UI kann beide nutzen.

**V2-Empfehlung:** Variante C — `cq_count_changed = Signal(int, bool)` mit (count, current_tx_even). UI kann selbst entscheiden was darstellen.

UI-Update `main_window:996-997`:
```
omni_str = f"  Ω CQ={self._omni_cq.cq_count} ({'E' if self._omni_cq.cq_tx_even else 'O'})"
```

---

## L5: UI-Anpassung control_panel + main_window

**Befund:** main_window:996-997 zeigt "Ω Even=X Odd=Y". Nach P7: 1 Counter.

**control_panel.py:** auch grep — gibt es dort einen Counter-Display?

**V2-Aktion:** in C4 `ui/main_window.py: _on_omni_slot_action` UND Counter-Display anpassen (zwei Files-Edits, 1 Commit).

---

## L6: First-Slot-Wahl — was wenn cq_audio_hz noch nicht gesetzt?

**Befund V1 §4.2:**
```
if _cq_tx_even is None:
    _cq_tx_even = is_even
if _cq_audio_hz is None:
    _init_audio_freq()
if is_even == _cq_tx_even:
    encoder.transmit(...)
```

Reihenfolge: Paritaet setzen → Frequenz setzen → senden. ✓

**Edge-Case:** _init_audio_freq() ruft `diversity.get_free_cq_freq()`. Wenn Diversity noch in measure-Phase (gerade misst), gibt das None oder veralteten Wert?

`diversity.get_free_cq_freq()` returnt vermutlich None waehrend measure (nicht initialisiert). OMNI Fallback ist 1500 Hz.

**V2-Aktion:** _init_audio_freq sollte nicht in measure-Phase rufen. Defensive Check:
```
if diversity.phase == "measure":
    return  # warten bis operate
```

Aber dann sendet OMNI nicht waehrend Mess. Das ist OK (Mess ist eh TX-frei in der Praxis).

**Mike-Frage 2:** Soll OMNI waehrend Mess-Phase (90s) senden?
- NEIN: kein Audio-Konflikt, sauber
- JA: schnellerer CQ-Loop

V2-Empfehlung: NEIN (KISS). Mess ist 90s, irrelevant fuer Hobby.

---

## L7: Stop-Bedingungen werden in mw_cycle/mw_radio behandelt — was aendert sich?

**Befund:** OMNI's Stop-Trigger sind:
- `manual_halt` — User-Klick
- `band_change` — `mw_radio.set_band` ruft `omni_cq.stop("band_change")`
- `mode_change` — `mw_radio` Wechsel zu Normal-Mode
- `totmann_expired` — Totmannschalter (Memory project_omni_cq)

Diese Pfade bleiben unveraendert. ✓

**V2-Aktion:** Stop-Bedingungen-Liste in V3 explizit dokumentieren („nicht angefasst") damit R1 nicht meckert.

---

## L8: Bestehende Tests Inventar (was bricht)

V1 sagt 40+ Tests obsolet. Konkret:

### test_omni_cq_signal.py (32 Tests, ALLE obsolet)
- T1-T22: 5-Slot-Pattern + Block-Wechsel + Pos 0/1/2/3/4 — alles WEG mit P7
- Z. 401 + Z. 489 + T2N: encoder.transmit/transmit_pair Mocks — neu
- Tests komplett neu schreiben (~10 fuer simplified API)

### test_encoder_pending.py (8 Tests, ALLE WEG)
- Datei loeschen — Pending-Mechanismus ist raus

### test_omni_cq_integration.py (~14 Tests, anpassen)
- `_FakeMW` mit OMNI: Pattern-Aufrufe `_slot_index = N` etc. → entfallen
- Pause/Resume-Tests: bleiben (API kompatibel)
- Stop-Tests: bleiben

### test_main_window_slot_boundary.py (5 Tests)
- bleibt unangetastet (allgemeine Slot-Boundary)

### test_p1_9_replace.py (5 Tests)
- bleibt unangetastet (Encoder-Replace-Pfad — kein Pending)
- Nach Encoder-Rueckrollung: alle gruen?
- **V2-Risiko:** P1.9-Tests setzen `_is_transmitting=True` direkt — pruefen ob Encoder-Rueckrollung sie betrifft

**V2-Aktion:** vor C5 manuell test_p1_9_replace.py durchspielen.

---

## L9: Cycle_count Bug in timing.py (aus Debug-Log)

**Befund:** Im P6-Field-Test sahen wir 14s-Latenz im _on_omni_slot_action. Wurzel war (vermutlich): **timing.py emit `_cycle_count` als ersten Param** statt `cycle_num`. Das ist eine SEPARATE Baustelle die mit P6 sichtbar wurde.

**P7-Relevanz:** OMNI nutzt `cycle_num` Parameter NICHT (V1 §4.2). Aber `is_even` Parameter wird genutzt. is_even-Berechnung in timing.py ist KORREKT (basiert auf echtem cycle_num intern). Also P7 nicht direkt betroffen.

**V2-Risiko:** wenn OMNI auf is_even baut und timing.py Latenz wieder hat, koennte is_even fuer falschen Slot gelten.

**Mitigation:** Im neuen `on_cycle_start(cycle_num, is_even)` den is_even-Wert FRESH neu berechnen aus time.time():
```
fresh_is_even = (int(time.time() / cycle_dur) % 2 == 0)
```
Spiegelt P6-Quick-Fix in main_window. Robust gegen Signal-Latenz.

**V2-Empfehlung:** in V3 §4.2 expliziten Fresh-Compute einbauen.

---

## L10: Frequenz-Sticky — bleibt sie ueber Paritaets-Wechsel?

**Befund:** _cq_audio_hz wird einmal beim ersten TX gesetzt. Bei Paritaets-Wechsel bleibt sie. ✓ Mike-Spec sagt: „Frequenz sticky — Wechsel nur wenn voll".

**Aber:** beim Paritaets-Wechsel koennte die andere Paritaet eine andere belegte Frequenz-Liste haben. Die optimale Frequenz fuer Even-Slot (z.B. wenig Kollisionen mit Stationen die in Even rufen) ist nicht zwingend die optimale fuer Odd.

**V2-Diskussion:** soll Frequenz beim Paritaets-Wechsel auch neu gewaehlt werden?
- JA: ein Aufruf `_init_audio_freq()` bei jedem Wechsel — komplex.
- NEIN: simpel, KISS, Mike-Spec.

**V2-Empfehlung:** NEIN, Frequenz bleibt sticky. Mike kann manuell durch Stop+Start neue Frequenz holen wenn noetig.

---

## L11: Ist OMNI's Sende-Pfad threading-sicher?

**Befund:** on_cycle_start laeuft im GUI-Thread. flip_tx_parity wird auch von mw_cycle (GUI-Thread) gerufen. _cq_tx_even Modifikation ist single-thread.

`encoder.transmit()` ist thread-safe (Lock vorhanden).

**V2-OK** — kein Lock noetig.

---

## L12: Edge — OMNI-Start in measure-Phase

**Befund:** Mike toggelt OMNI waehrend Diversity gerade misst (90s Phase). Was passiert?

V1: `_init_audio_freq()` ruft `diversity.get_free_cq_freq()` → koennte None oder veraltet returnen. Fallback 1500 Hz.

`on_cycle_start` triggers cycle_start signals weiterhin. OMNI wuerde im FALSCHEN Slot senden (Mess-Slot ist nicht TX-Slot).

**V2-Loesung:** OMNI darf erst senden wenn `diversity.phase == "operate"`. Sonst skip on_cycle_start als no-op.

```
def on_cycle_start(self, cycle_num, is_even):
    if not self._active or self._paused:
        return
    # P7: nicht senden waehrend Diversity-Mess (Mess-Slots sind belegt)
    if self._diversity.phase != "operate":
        return
    ...
```

Aber: wer prueft das? Encoder.transmit hat keinen Diversity-Check. mw_cycle hat den Check. OMNI muss selbst pruefen.

**V2-Empfehlung:** `_diversity` Referenz nutzen (existiert bereits in OmniCQ.__init__).

---

## V2-Lessons Zusammenfassung

| L | Schweregrad | Aktion fuer V3 |
|---|---|---|
| L1 | KRITISCH | Mike-Frage zu Wechsel-Intervall (5/10/15/30 Min via OMNI-Timer) |
| L2 | OK | dokumentieren in V3 |
| L3 | mittel | Signatur kompatibel halten, Param ignorieren |
| L4 | mittel | Signal aendern auf `(int, bool)` |
| L5 | mittel | UI in C4 mit anpassen |
| L6 | mittel | _init_audio_freq Defensive: nicht waehrend measure |
| L7 | OK | dokumentieren |
| L8 | mittel | test_p1_9_replace.py vor C5 verifizieren |
| L9 | mittel | Fresh-Compute is_even in on_cycle_start (Robustheit) |
| L10 | OK | Frequenz bleibt sticky (Mike-Spec) |
| L11 | OK | kein Lock noetig |
| L12 | mittel | OMNI no-op waehrend Diversity-Mess-Phase |

---

## Fragen an Mike (V3-Vorbedingung)

1. **Wechsel-Intervall:** Aktuell wuerde Re-Mess nur alle 1h triggern (= 1h auf einer Paritaet). Soll ein eigener OMNI-Timer (5/10/15/30 Min?) den Wechsel haeufiger triggern?
2. **Senden waehrend Diversity-Mess:** OMNI soll waehrend der ~90s Mess-Phase NICHT senden, oder?

Beide Antworten flieessen in V3 ein.

---

## Naechste Schritte

1. Mike beantwortet Frage 1+2
2. V3 schreiben mit V2-Lessons + Mike-Antworten
3. R1-Brief mit V1+V2+V3-Pre-Draft schreiben
4. R1-Lauf
5. V3-Final + Compact + Code

---

**Ende V2.**
