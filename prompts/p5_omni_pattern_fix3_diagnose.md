# P5.OMNI-PATTERN-FIX-3 — Diagnose & V1-Vorbereitung

**Datum:** 2026-05-10 ca. 06:30 UTC
**Status:** Diagnose-Phase fertig. Fresh-Instanz lädt diese Datei nach
Trigger „omni pattern fix3 starten" und beginnt Schritt 0 + V1.
**Vorgänger:** P4.OMNI-NEUBAU V5 (v0.96.1, Commits `0368427` C9 + `8244e37` C10)

---

## 0. Was die frische Instanz tun muss (Reihenfolge)

1. **Phase 1 Session-Start** wie immer (CLAUDE.md → MEMORY.md → HISTORY.md → HANDOFF.md).
2. **Diese Datei** komplett lesen (`prompts/p5_omni_pattern_fix3_diagnose.md`).
3. **Memory laden:**
   - `project_p5_omni_pattern_fix3.md` (Trigger-File)
   - `project_omni_cq_spec.md` (Mike-Spec, verbindlich)
   - `feedback_test_critical_path_not_mock.md` (P4-Lesson)
   - `feedback_r1_encoder_busy_blindspot.md` (P5-Lesson)
   - `prompts/p4_omni_neubau_v5_signal_v3.md` §8 Out-of-Scope (was V5 verworfen hat)
4. **Schritt 0 — Code-Verifikation:** alle file:line-Verweise unten gegen aktuellen Code grep'en.
5. **V1 schreiben** mit den unten ausgearbeiteten Akzeptanzkriterien als Basis.
6. **V2 Self-Review.**
7. **R1 DeepSeek-Reasoner** (`tools/deepseek_review.py`, model `deepseek-reasoner`).
   **WICHTIG:** R1 hat in P4-V5 Klärungsfrage 3 den Encoder-Busy-Race nicht
   erkannt (siehe `feedback_r1_encoder_busy_blindspot.md`). Bei P5 muss
   R1 explizit nach Encoder-Throughput / TX-Buffer-Timing zwischen
   konsekutiven TX-Slots gefragt werden — siehe „R1-Fragen" unten.
8. **V3 Compact-fest.**
9. **Mike-Freigabe + Compact + Code + Field-Test.**

---

## 1. Symptome (Field-Test 10.05.2026 ~06:30 UTC)

### Issue B — Pattern halb tot (kritisch)

`qso_panel`-Aufzeichnung beim ersten 10-Slot-Loop nach btn_omni_cq:

```
04:26:30 [E] → Sende    CQ DA1MHH JO31    ← Pos 0 Block 1 TX-E ✓
04:26:44 [O] ← Horche   ...                 ← Pos 1 SOLLTE TX-O sein, ist aber Horche
04:26:59 [E] ← Horche   ...                 ← Pos 2 Block 1 RX-E ✓
04:27:14 [O] ← Horche   ...                 ← Pos 3 Block 1 RX-O ✓
                                             ← Pos 4 Block 1 RX-E FEHLT KOMPLETT
04:27:45 [O] → Sende    CQ DA1MHH JO31    ← Block 2 Pos 0 TX-O ✓
04:27:59 [E] ← Horche   ...                 ← Pos 1 SOLLTE TX-E sein, ist aber Horche
```

Log-Auszug (`~/.simpleft8/simpleft8.log`):

```
[OMNI-CQ] User-Start
[OMNI-CQ] CQ-Audiofrequenz: 475 Hz
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B2 [1/4] TX-E uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ-UI] Stop (manual_halt)
```

### Issue A — Display-Zeit ist Wall-Time statt Slot-Boundary (kosmetisch)

Mike will dass die Horche-Zeile die **UTC-Slot-Boundary** zeigt (`:00`,
`:15`, `:30`, `:45`), nicht die Wall-Time des `cycle_start`-Trigger
(z.B. 04:26:**44** statt 04:26:**45**).

---

## 2. Wurzel-Analyse (Issue B, kritisch)

**Encoder-Race zwischen 2 konsekutiven TX-Slots.**

| Zeit | Encoder-Zustand | OMNI-Aktion |
|---|---|---|
| :29 | TX-Pretrigger (1.3s vor Slot, Pos 0 TX-E) | — |
| :30 | TX läuft (Audio-Render in `_tx_worker_inner`) | Pos 0 cycle_start → `_do_tx_slot(True)` → `encoder.transmit()` ✓ True (Worker schon gestartet, `_is_transmitting=True` aus Pretrigger) |
| :30-:43 | TX läuft, `_is_transmitting=True` | — |
| ~:43-:44 | TX-Worker `finally: _is_transmitting=False` | — |
| :45 | Encoder kurz danach noch im finally / Sleep | Pos 1 cycle_start → `_do_tx_slot(False)` → `encoder.transmit()` checkt `_is_transmitting`. Wenn True → **return False** → V5 AC11: nur log warning, KEIN slot_action emit, KEIN TX. |

**Race-Detail:** zwischen TX-Worker-`finally` und Pos-1-cycle_start liegen
0-2s. Die Reihenfolge ist nicht-deterministisch (FlexRadio-TX-Buffer 1.3s
+ Audio-Codec-Delay + Thread-Scheduling). In Praxis: **bei FT8 ist
`_is_transmitting` zum cycle_start Pos 1 fast immer noch True**, weil
TX-Audio bei :30-:43.5 läuft + finally + Sleep-Wakeup-Delay → cycle_start
:45 trifft eine offene Race-Window.

Code-Verweise:
- `core/encoder.py:189-212` `transmit()` — `if self._is_transmitting: return False`
- `core/encoder.py:222-233` `_tx_worker` — `_is_transmitting=True`/`False` Set
- `core/omni_cq.py` `_do_tx_slot()` — bei `not ok` nur log, kein slot_action
- `core/omni_cq.py` `_advance_state()` — advanced trotzdem (AC10)

### Pos 4 (RX-E Block 1) fehlt — Hypothese

Im Display-Log fehlt der Eintrag bei :30 (zwischen :15 und :45). Vermutung:
sekundärer Effekt von Pos 1 — wenn der :45-Slot als "skipped" markiert
ist und encoder.transmit später NACHHOLT (über `_next_slot_boundary`,
das `cycle_pos > 0.5` → next slot wählt), könnte das den RX-E :30 Slot
blocken (encoder schreibt in dem Slot statt OMNI). MUSS BEI SCHRITT 0
VERIFIZIERT WERDEN durch Live-Log-Inspektion.

**Alternative Hypothese:** mw_cycle hat einen early-return in der
Diversity-Antennen-Branch wenn `encoder.is_transmitting` (mw_cycle.py:589
`if self.encoder.is_transmitting: return`) — allerdings läuft der OMNI-
Hook BEFORE diesem Check (mw_cycle.py:587 nach unserem C9-Patch). Also
sollte OMNI immer durchkommen. Verifizieren!

### Encoder-Throughput-Problem ist V5 Architektur-Choice (V3 §8)

V3 §8 hat explizit verboten:
- ❌ `Änderungen an core/encoder.py` (atomare API ist fertig, C3)
- ❌ `Encoder-Queue für OMNI`
- ❌ `cycle_tick-basierter Pretrigger / QTimer`
- ❌ `Frequenz-Recheck zur Laufzeit`

P2.OMNI-PATTERN-FIX (v0.95.24, Commits `6a86764` + `337e4ca`) hatte
genau diese 2 Bausteine implementiert (Encoder-Queue + Mid-Cycle-
Pretrigger via cycle_tick) und damit das Pattern stabil. P3.OMNI-PATTERN-
FIX-2 (v0.95.25, Commit `ee3ac9a`) hat es auf QTimer-Pretrigger erweitert.

P4.OMNI-NEUBAU C3 (`1d76457`) hat die Encoder-Queue wieder rausgemacht.
P4.OMNI-NEUBAU C5 (`b58c5df`) hat den Mid-Cycle-Pretrigger entfernt
("Rückbau ui/mw_cycle.py").

→ **V5-KISS-Verzicht hat den Race zurückgebracht.** Die V3-§8-Liste muss
in P5 überdacht werden.

---

## 3. Lösungsoptionen (zu V1/V2 ausarbeiten, R1-zur Bewertung)

### Option A — Encoder-Queue zurückbringen
- `core/encoder.py`: Bei `transmit()` mit `_is_transmitting=True` einen
  pending-Job queuen statt `return False`. Worker-Thread checkt am Ende
  ob Pending vorliegt → startet sofort.
- **Pro:** wenig Code-Änderung in OMNI, alle TX-Slots werden bedient.
- **Kontra:** verstößt gegen V3 §8 ("Encoder-Queue für OMNI ❌"), Mike
  hatte das mit V5 explizit weggehauen. Re-Architektur-Entscheidung.
- **Komplexität:** ~30-50 Z. in `core/encoder.py`, evtl. neue Tests.

### Option B — Mid-Cycle-Pretrigger zurückbringen
- `ui/mw_cycle._on_cycle_decoded` (oder cycle_tick): wenn Pos 1 ansteht,
  `peek_next()` an OMNI rufen + encoder.transmit mid-cycle starten.
- **Pro:** zeitlich genauer als A (TX startet noch vor Slot-Boundary),
  P3-Praxis-erprobt.
- **Kontra:** verstößt gegen V3 §8, neue cycle_tick-Hook, mehr
  Komplexität als A.

### Option C — Pattern auf 1 TX/Block, öfter Block-Wechsel
- Statt `(True, True, False, False, False)` → `(True, False, False)` (3
  Slots, 1 TX). Block-Wechsel alle 3 Slots → alternierende E/O-Coverage
  bleibt erhalten.
- **Pro:** kein Encoder-Race möglich (Pos 1 ist immer RX).
- **Kontra:** ändert Mike-Spec (`project_omni_cq_spec.md` 5-Slot-Pattern
  "TX-TX-RX-RX-RX"). Mike-Freigabe nötig.

### Option D — Pos 1 TX um 1 Slot nach hinten verschieben
- Pattern: `(True, False, True, False, False)` Block 1 → TX-E, RX-O,
  TX-E, RX-O, RX-O? Nein, Mike wollte E + O Coverage. Variante:
  `(True, False, False, True, False)` → TX-E, RX-O, RX-E, TX-O, RX-E?
  Block 2 dann gespiegelt.
- **Pro:** beide TX-Slots laufen, Encoder-Idle-Zeit dazwischen.
- **Kontra:** ändert Mike-Spec. Auch hier Freigabe nötig.
- **Risiko:** verteilt CQ-Frequenz mehr Zeit auseinander, eventuell
  weniger Antworten pro Block.

### Empfehlung an Mike (V1-Vorschlag)

**Variante A (Encoder-Queue) ist KISS-konform und löst Issue B sauber
ohne Mike-Spec zu ändern.** Die V3-§8-Verbot-Liste war eine bewusste
Entscheidung damals — aber im Licht des Field-Tests muss sie überdacht
werden. R1 soll explizit dazu Stellung nehmen.

---

## 4. Issue A — Slot-Boundary-Display (kosmetisch, gehört in P5-V3)

**Ist-Zustand:** `ui/main_window.py:760` ruft
```python
self.qso_panel.add_listening(time.time(), target_even)
```

**Soll:** Zeit auf nächste Slot-Boundary `:00`/`:15`/`:30`/`:45` runden
(bei FT8 = `15s`; bei FT4 `7.5s`; bei FT2 `3.8s`).

**Implementierung:**
```python
slot = self.timer.cycle_duration   # 15.0 / 7.5 / 3.8
ts = time.time()
slot_start = (ts // slot) * slot
self.qso_panel.add_listening(slot_start, target_even)
```

**Tests:** mocken `timer.cycle_duration=15`, `time.time()` → 04:26:44.5,
erwarten dass `add_listening` mit ts=04:26:30 (`floor(.../15)*15`)
gerufen wird.

---

## 5. Akzeptanzkriterien für V1 (Vorschlag, in V1 schärfen)

| AC | Kriterium |
|---|---|
| AC-B1 | Pos 1 TX läuft IMMER. Encoder akzeptiert konsekutive TX-Aufrufe ohne `return False`. |
| AC-B2 | Pos 4 (RX-E Block 1) wird IMMER im qso_panel angezeigt. |
| AC-B3 | Pattern Block 1 EXAKT: TX-E, TX-O, RX-E, RX-O, RX-E (5 Einträge pro Block). |
| AC-B4 | Pattern Block 2 EXAKT: TX-O, TX-E, RX-O, RX-E, RX-O. |
| AC-B5 | Auto-Rollover Block 1 ↔ Block 2 nach 5 Slots. |
| AC-B6 | 10-Slot-Loop in qso_panel ohne Lücke, ohne Drift. |
| AC-A1 | `add_listening`-Zeit zeigt Slot-Boundary `:00`/`:15`/`:30`/`:45`. |
| AC-A2 | Bei FT4/FT2-Modus: Slot-Boundary entsprechend `cycle_duration` gerundet. |
| AC-Z1 | Hardware-Garantie ANT1 unverändert (encoder.transmit setzt zentral). |
| AC-Z2 | Tests: alle 1020 weiter grün, neue Tests für Issue B + A. |

---

## 6. R1-Fragen (V2 → R1, V3 mit Stellungnahmen)

1. **Encoder-Throughput:** kann der V5-on_cycle_start-Pfad bei FT8 (15s)
   zwei konsekutive TX-Slots bedienen oder ist die TX-Worker-finally-
   Race zu eng? Wenn nein — welche der 4 Optionen ist KISS-konform?
2. **V3-§8 Out-of-Scope:** war das Verbot gerechtfertigt im Licht von
   Issue B? Soll Encoder-Queue / Mid-Cycle-Pretrigger zurückgeholt
   werden?
3. **Pos 4 RX-E fehlt:** Hypothese korrekt (Encoder-Spätstart blockt
   :30 Slot)? Oder anderer Pfad?
4. **Slot-Boundary-Display (Issue A):** ist `floor(time.time() /
   cycle_duration) * cycle_duration` der saubere Weg?

---

## 7. Out-of-Scope für P5 (kein Scope-Creep!)

- ❌ Frequenz-Recheck-Logik (V5 §8 KISS bleibt)
- ❌ qso_state-State-Maschinen-Änderungen
- ❌ Listener-Pfad in `mw_cycle.on_message_decoded`
- ❌ Diversity-Antennen-Switch
- ❌ Auto-Hunt-Coupling

P5 ist NUR: TX-Throughput-Race fixen + Display-Slot-Boundary.

---

## 8. APP_VERSION-Plan

`v0.96.1 → v0.96.2` (Patch-Bump: Bug-Fix Pos-1-Race + Display-Korrektur,
kein neues Feature).

---

## 9. Test-Bilanz erwartet

1020 grün → ~1025-1030 grün (neue Tests für AC-B + AC-A, keine
gestrichenen).

---

## 10. Plan-Files V1-V3 Pfad

- `prompts/p5_omni_pattern_fix3_v1.md` (frische Instanz schreibt)
- `prompts/p5_omni_pattern_fix3_v2.md` (Self-Review)
- `prompts/p5_omni_pattern_fix3_r1.md` (R1-Output)
- `prompts/p5_omni_pattern_fix3_v3.md` (Compact-fest, einzige Wahrheit)

---

**Ende Diagnose. Frische Instanz: bei „omni pattern fix3 starten"
diese Datei laden + Schritt 0 + V1.**
