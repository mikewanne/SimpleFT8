# P2.OMNI-PATTERN-FIX — V1 Diagnose-Plan

**Datum:** 2026-05-09
**Vorgaenger:** P2.OMNI-REDESIGN v0.95.23 (Loop-Tot-Bug gefixt, aber Pattern verschoben)
**Stand:** Mike-Field-Test 09.05.2026 ~08:34-08:38 UTC — Loop laeuft, Pattern falsch

---

## 0. Beobachtung (Mike's Field-Test, Screenshot 08:37)

```
08:34:45 [O] → Sende CQ DA1MHH JO31    ← Pos 0 Block 2 (TX Odd) korrekt
08:35:30 [E] → Sende CQ DA1MHH JO31    ← sollte 08:35:00 [E] sein (Pos 1, TX Even)
08:36:30 [E] → Sende CQ DA1MHH JO31    ← sollte 08:36:00 [E] sein (Pos 0 Block 1)
08:37:45 [O] → Sende CQ DA1MHH JO31    ← sollte 08:37:15 [O] sein (Pos 0 Block 2)
```

**Verschoben um +30s = 2 Slots ab Pos 1.** Erste TX ist korrekt (uber
`start_cq()` aus Toggle-Pfad mit Slot-Vorlauf), alle Folge-TX um 2 Slots
zu spaet.

**Erwartet (Block 2: O-TX, E-TX, O-RX, E-RX, O-RX):**
```
08:34:45 [O] TX (Pos 0)
08:35:00 [E] TX (Pos 1)
08:35:15 [O] RX (Pos 2)
08:35:30 [E] RX (Pos 3)
08:35:45 [O] RX (Pos 4)
08:36:00 [E] TX (Pos 0 Block 1, Rollover)  ← Even-First
08:36:15 [O] TX (Pos 1 Block 1)
08:36:30 [E] RX
08:36:45 [O] RX
08:37:00 [E] RX
08:37:15 [O] TX (Pos 0 Block 2 nach Rollover)
...
```

---

## 1. Wurzel-Hypothese (Encoder-Drift-Schutz vs OMNI-Slot-Start)

### 1.1 Code-Pfad bei Folge-TX (z.B. 08:35:00 [E] → soll TX Even)

```
08:35:00.0  mw_cycle._on_cycle_start emitted (Timer-Thread → GUI-Queue)
08:35:00.0x mw_cycle._on_cycle_start runs:
              → qso_sm.on_cycle_end()
                → state=CQ_WAIT, timeout_cycles=1
                → _send_cq()
                  → send_message.emit("CQ ...")
                    → mw_qso._on_send_message (DirectConnection):
                        → omni.should_tx() → (True, True) — Pos 1 Block 2
                        → encoder.tx_even = True
                        → encoder.transmit("CQ ...")
                          → Thread-Start, Worker ruft _next_slot_boundary
              → omni._tx.advance() → _slot_index=1
```

### 1.2 Encoder Drift-Verschiebung (`core/encoder.py`)

**`_next_slot_boundary` Z.206-233:**
```python
if self.tx_even is not None:
    want_even = self.tx_even  # True
    if is_even == want_even and cycle_pos < 0.5:
        return float(cycle_num * _SLOT)  # = 08:35:00 (AKTUELLER Slot)
    next_num = cycle_num + 1
    ...
```

Bei 08:35:00.0x: is_even=True, want_even=True, cycle_pos≈0.0X<0.5 →
returnt `cycle_num*15 = 08:35:00.0` (aktueller Slot).

**`_tx_worker_inner` Z.295-316 Drift-Vermeidung:**
```python
silence_secs = max(0.0, (next_boundary + TARGET_TX_OFFSET) - now)
# = max(0, (08:35:00 - 0.8) - 08:35:00.0x) = max(0, -0.8 - x) = 0.0
if silence_secs < 0.1:
    overshoot = now - (next_boundary + TARGET_TX_OFFSET)
    # = 08:35:00.0x - (08:35:00 - 0.8) = 0.8 + x ≈ 0.8
    if overshoot > 0.3:
        # Drift-Vermeidung → next_boundary += 2*15s = +30s
        next_boundary += 2 * _SLOT  # tx_even gesetzt → 2 Slots
        # → 08:35:30 [E] (Even, gleiche Paritaet)
```

**Resultat:** TX landet bei 08:35:30 [E] statt 08:35:00 [E]. Mike sieht
das als „Pattern verschoben um +30s".

### 1.3 Warum erste TX korrekt war (08:34:45 [O])

Mike-Klick auf btn_omni_cq → `_on_btn_omni_cq_toggled` → `start_cq()` →
`_send_cq()` MITTEN im Slot (cycle_pos > 0.5, sagen wir 08:34:32 mit
cycle_pos=2.0):
- `_next_slot_boundary`: is_even=True (Slot 08:34:30), want_even=False
  (TX Odd), kein Match → next_num=current+1=08:34:45 (Odd) ✓
- silence_secs = 08:34:45 - 0.8 - 08:34:32.0 ≈ 12.2s > 0.1 → kein Drift
- TX bei 08:34:45 [O] ✓

**Initial-Pfad (Toggle) ≠ Folge-Pfad (on_cycle_end am Slot-Start).**

---

## 2. Mike's Spec-Erweiterung (09.05.2026)

> „auch bei abbruch qso es muss immer bei start ein kompleter block
> gestartet werden — entweder odd,even senden odd,even,odd empfangen
> oder even,odd senden even,odd,even empfangen. der block dar nicht
> mittendrin gestartet werden. heisst: kommt es zu einem qso und wird
> dieses beendet oder unterbrochen wird im naechsten zur verfuegung
> stehenden slot mit einem KOMPLETT neuen block gestartet und nicht
> mitten im block"

**Ableitungen:**

1. **Block-Start-Garantie:** Bei jedem OMNI-Activate (Toggle, Resume nach
   QSO, Resume nach Timeout) startet IMMER mit `_slot_index = 0`.
   → Aktuelle Code-Lage: ✅ `start_with_parity_for_next_slot` setzt
     `_slot_index = 0`. `_maybe_resume_omni` ruft das auf → Pos 0 garantiert.
2. **Kein Continue mid-pattern:** Beim Resume nach QSO darf NICHT
   `_slot_index` aus Pre-QSO-Zustand fortgesetzt werden.
   → Aktuelle Code-Lage: ✅ Wir nutzen `start_with_parity_for_next_slot`
     mit `_slot_index = 0`, NICHT `resume()` (das wuerde paused-State
     aufheben aber index behalten).
3. **Pattern-Integritaet:** Innerhalb eines Blocks muss das Pattern
   (TX,TX,RX,RX,RX) eingehalten werden — kein TX in RX-Slot, kein RX in
   TX-Slot.
   → **AKTUELLER BUG:** Encoder-Drift verschiebt TX in RX-Slot.

---

## 3. Loesungsoptionen (3 Architektur-Pfade)

### Option A — Pre-Slot _send_cq via cycle_tick

OMNI's `_send_cq` nicht aus `on_cycle_end` (Slot-Start), sondern aus
`cycle_tick` mit cycle_pos > 14s (FT8) bzw. ~1s vor Slot-Ende.

**Pro:**
- Encoder hat ~1s Vorlauf zum naechsten Slot, kein Drift.
- Pattern wird nicht verschoben.

**Kontra:**
- Architektur-Eingriff in `qso_state` — `_send_cq` muss aus 2 Quellen
  triggerbar (alte cycle_end fuer Normal-CQ, neue cycle_tick fuer OMNI).
- Doppel-Trigger-Schutz noetig.
- Test-Komplexitaet: cycle_tick-Mocking erforderlich.

### Option B — OMNI advance() VOR on_cycle_end (Lookahead-Semantik)

Reihenfolge in `mw_cycle._on_cycle_start` umkehren:
```python
# alt:
self.qso_sm.on_cycle_end()
if not self._omni_tx.is_paused():
    self._omni_tx.advance()
# neu:
if not self._omni_tx.is_paused():
    self._omni_tx.advance()
self.qso_sm.on_cycle_end()
```

`_slot_index` referenziert dann den NAECHSTEN Slot (nach advance), nicht
den aktuellen.

`should_tx()` returnt fuer nachsten Slot:
- 08:35:00 [E] on_cycle_start: advance → _slot_index=1 (Pos 1 Block 2 = TX Even)
- on_cycle_end → _send_cq → mw_qso._on_send_message → encoder.tx_even=True
- Encoder bei 08:35:00.0x: want_even=True, is_even=True, cycle_pos<0.5 →
  return cycle_num*15 = 08:35:00.0 — **selbe Drift-Falle**!

**Wait** — wenn `_slot_index` jetzt fuer NAECHSTEN Slot steht:
- Pos 1 = 08:35:15 [O] (next slot), not 08:35:00 [E]
- target_even fuer Pos 1 Block 2 = (08:35:15 ist Odd) → want_even=False (??)

Nein, das stimmt nicht. Pos 1 in Block 2 = TX Even (laut Pattern). Aber
wenn _slot_index=1 = NAECHSTER Slot 08:35:15 [O], dann ist die Paritaet
schon FIX: 08:35:15 ist Odd. Wir koennen nicht „TX Even" erzwingen, ohne
das Pattern zu brechen.

Also Block-Pattern muss zur Slot-Paritaet passen:
- Slot 0 (08:34:45 [O], OMNI-Start): TX Odd
- Slot 1 (08:35:00 [E]): TX Even
- Slot 2 (08:35:15 [O]): RX
- ...

`should_tx()` muss anhand des AKTUELLEN Slot-Index entscheiden, nicht
naechster. Also Option B kollidiert mit Pattern-Definition.

**Option B ist NICHT trivial.** Braucht Pattern-Redefinition oder
Off-by-One-Anpassung.

### Option C — Encoder TARGET_TX_OFFSET-Korrektur fuer OMNI-Pfad

Erkenne OMNI-Pfad in encoder, reduziere oder eliminiere TARGET_TX_OFFSET.
Aber: TARGET_TX_OFFSET = -0.8 ist FlexRadio-Hardware-Buffer-Kompensation.
Ohne sie: TX-Audio startet 1.3s zu spaet → DT-Drift.

**Option C ist NICHT akzeptabel — Hardware-Garantie verletzt.**

### Option D — Encoder schaltet im aktuellen Slot SCHNELL durch

Drift-Schwelle `> 0.3s` fuer OMNI-Pfad lockern (z.B. > 0.8s oder
> 1.0s). Dann kein Schiebe um 2 Slots, aber TX-Audio startet bei
cycle_pos=0.0-0.8s im aktuellen Slot — verspaetete TX.

FT8 erlaubt DT bis 0.5s. Bei silence_secs=0 startet send_audio sofort
(bei cycle_pos=0.0X), Audio dauert 12.64s, endet bei cycle_pos+12.64.
PTT-On->RF-Out hat 1.3s FlexRadio-Buffer. Effektives RF-Audio startet bei
cycle_pos+1.3 statt +0.5 (WSJT-X-Standard) → DT≈+0.8s zu spaet.

**Gegenstation sieht DT=+0.8s** → bei vielen Decodern noch decodierbar
(WSJT-X DT-Toleranz +1.5s), aber suboptimal.

**Option D ist NICHT akzeptabel — DT-Quality-Verlust.**

### Option E — `_send_cq` PreSlot via Mid-Cycle-Trigger (Hybrid)

Neuer Mechanismus in `mw_cycle._on_cycle_tick` (laeuft ~10x/Sek):
- Wenn cycle_pos in Schwelle (z.B. 13.5-14.0s fuer FT8):
  - Wenn OMNI active und qso_sm in CQ_WAIT/CQ_CALLING-State:
    - Trigger einmaligen `_send_cq` fuer NAECHSTEN Slot
    - Set Flag damit kein Doppel-Trigger im naechsten cycle_tick

Pro:
- Encoder hat genug Vorlauf (~1s) → kein Drift
- Architektur-clean: OMNI-spezifischer Trigger nur bei OMNI active
- Pattern bleibt korrekt

Kontra:
- Cycle_tick-Mock fuer Tests
- Reentrancy-Schutz noetig
- Eigene Logik fuer normalen CQ vs OMNI

---

## 4. Empfehlung — Option E mit Variation

**Vorschlag fuer Mike:**

1. **Architektur:** OMNI's Slot-Trigger laeuft Mid-Cycle (cycle_pos > 13s
   fuer FT8) statt Slot-Start.
2. **Implementation:** Neue Methode `_omni_pretrigger()` in mw_cycle,
   aufgerufen aus `_on_cycle_tick`. Setzt `omni._slot_index += 1`,
   ruft `omni.should_tx()` fuer KOMMENDEN Slot, falls TX-Slot setzt
   `encoder.tx_even`, ruft `_send_cq()`. Flag `_omni_pretriggered`
   verhindert Doppel-Trigger.
3. **mw_cycle._on_cycle_start:** entfernt `omni.advance()` (jetzt im
   Pretrigger).
4. **Initial-TX (Toggle):** unveraendert — `start_with_parity_for_next_slot`
   + `start_cq` → `_send_cq` mit Vorlauf.

**Aber:** Ich bin mir nicht 100% sicher dass Option E die einzig saubere
Lösung ist. **DeepSeek-R1 muss konsultiert werden** zur Architektur-
Entscheidung — Option A vs E vs ggf. neu zu erfindende Option F.

---

## 5. Code-Verifikations-Pflicht (Schritt 0 vor V2)

```bash
# 1. Encoder Drift-Vermeidung (v0.80 Fix B)
grep -n "overshoot\|TARGET_TX_OFFSET\|next_slot_boundary" core/encoder.py

# 2. mw_cycle Reihenfolge (on_cycle_end vs advance)
grep -n "on_cycle_end\|advance\|cycle_tick" ui/mw_cycle.py

# 3. _send_cq-Aufrufer
grep -n "_send_cq" core/qso_state.py

# 4. cycle_tick-Listener
grep -n "cycle_tick\|_on_cycle_tick" ui/mw_cycle.py core/timing.py

# 5. OMNI's advance + should_tx Reihenfolge
grep -n "should_tx\|advance" core/omni_tx.py ui/mw_qso.py ui/mw_cycle.py
```

---

## 6. Akzeptanzkriterien (V1, vorlaeufig)

| AC | Beschreibung |
|---|---|
| AC1 | Block 1 (next_is_even=True bei Activate): TX Even, TX Odd, RX, RX, RX in EXAKT diesen Slots |
| AC2 | Block 2 (next_is_even=False): TX Odd, TX Even, RX, RX, RX in EXAKT diesen Slots |
| AC3 | Block-Rollover bei Pos 4→0: neuer Block startet im naechsten verfuegbaren Slot mit Pos 0 |
| AC4 | OMNI-Activate (Toggle): Pos 0 startet im naechsten verfuegbaren Slot, NIE mid-pattern |
| AC5 | OMNI-Resume nach QSO-Ende: Pos 0 startet im naechsten verfuegbaren Slot |
| AC6 | OMNI-Resume nach QSO-Timeout: Pos 0 startet im naechsten verfuegbaren Slot |
| AC7 | OMNI-Resume nach QSO-Cancel/HALT: KEIN Resume (HALT stoppt OMNI komplett) |
| AC8 | Encoder-Drift-Schutz (v0.80 Fix B) bleibt unveraendert (DT-Quality-Garantie) |
| AC9 | Field-Test: 10 Slots OMNI-Loop zeigt EXAKT erwartetes Pattern (no skipping, no shifting) |
| AC10 | Stats: cq_even_count + cq_odd_count synchronisiert mit tatsaechlich gesendeten TX |

---

## 7. Offene Fragen fuer V2/R1

1. Welche Option (A/E/F) ist architektursauber + KISS?
2. Ist Mid-Cycle-Trigger Race-frei (encoder.is_transmitting vs. neuer
   transmit-Aufruf)?
3. Wie wird Doppel-Trigger im Pretrigger-Pfad verhindert?
4. Wann genau ist „naechster verfuegbarer Slot" — sofort (next slot) oder
   nach genug Vorlauf (next slot mit > 1s Encoder-Headroom)?
5. Konflikt mit Auto-Hunt PreSlot-Logik (auto_hunt.py)?
6. P1.9 Encoder-Replace-Logik (request_replace) interagiert mit
   Pretrigger?

---

## 8. Test-Strategie (V1, vorlaeufig)

**Pattern-Beweis-Tests (gegen Bug):**
- T1: Block 1 voll-Pattern: 5 aufeinanderfolgende Slots zeigen E-TX,
  O-TX, E-RX, O-RX, E-RX EXAKT
- T2: Block 2 voll-Pattern: 5 Slots O-TX, E-TX, O-RX, E-RX, O-RX EXAKT
- T3: Block-Rollover: Slot 5-9 zeigt Pattern des anderen Blocks
- T4: 10 Slots Continuous: kein Pattern-Drift, jeder TX im richtigen
  Slot

**Resume-Tests (Mike's Spec):**
- T5: Activate → Block 1 startet Pos 0, NICHT Pos N
- T6: QSO startet → OMNI pause → QSO endet → Resume mit Pos 0 (neuer
  Block-Start)
- T7: QSO mit nicht-leerer Caller-Queue → kein Resume → naechstes QSO
- T8: HALT mid-OMNI → kein Resume nach naechstem cycle

**Encoder-Tests:**
- T9: Mid-Cycle-Trigger: cycle_pos=14s → _send_cq laeuft, Encoder hat
  > 1s Vorlauf, kein Drift
- T10: Drift-Vermeidung greift NICHT bei Pretrigger-Pfad

---

## 9. Files-Anhang fuer R1

- `core/encoder.py` (Drift-Logik)
- `core/qso_state.py` (`_send_cq`, on_cycle_end)
- `core/omni_tx.py` (Pattern, advance, should_tx)
- `ui/mw_cycle.py` (cycle_tick, cycle_start, advance-Reihenfolge)
- `ui/mw_qso.py` (_on_send_message, Pause/Resume-Helpers)
- `core/timing.py` (cycle_tick-Signal)
- Mike's Field-Test-Screenshot 08:34-08:37
- p2_omni_redesign_v3.md (Vorgaenger-Plan)

---

## 10. R1-Auftrag (V2-Phase)

> Lieber DeepSeek-Reasoner R1,
>
> wir haben einen Pattern-Verschiebungs-Bug in OMNI-CQ entdeckt.
> P2.OMNI-REDESIGN v0.95.23 hat den Loop-Tot-Bug gefixt, aber Mike's
> Field-Test (08:34-08:37 UTC) zeigt: Pattern um 2 Slots verschoben.
>
> Wurzel: Encoder-Drift-Schutz (v0.80 Fix B, > 0.3s overshoot) trifft
> bei OMNI's `_send_cq` am Slot-START → schiebt TX um 2 Slots.
>
> Bitte pruefe:
> 1. Ist Wurzel-Hypothese (§1) korrekt?
> 2. Welche der 3 Loesungsoptionen (A=PreSlot-Trigger, E=Hybrid Mid-Cycle
>    Trigger, oder eigene F) ist architektursauber + KISS fuer ein
>    Hobby-FT8-Tool?
> 3. Mike's Spec „immer kompletter Block-Start" — ist das in §2/AC4-AC7
>    korrekt erfasst?
> 4. Risiken: Race-Conditions, Auto-Hunt-Konflikt, P1.9-Replace-Konflikt?
> 5. Test-Strategie §8: vollstaendig oder Lücken?
>
> Erwarte: Architektur-Empfehlung + Code-Diff-Skizze + Risikoliste.
