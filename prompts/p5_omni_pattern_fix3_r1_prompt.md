# Auftrag an DeepSeek-Reasoner (R1) — P5.OMNI-PATTERN-FIX-3

Du bist Code-Reviewer fuer **P5.OMNI-PATTERN-FIX-3** in SimpleFT8.

## Kontext (kurz)

SimpleFT8 ist ein Hobby-Funker-Tool (KEIN Contest-Tool) fuer FT8/FT4/FT2.
v0.96.1 hat OMNI-CQ als signal-getriggertes Modul (`core/omni_cq.py`)
implementiert. **Field-Test 10.05.2026 zeigte 2 Issues:**

- **Issue B (kritisch):** Pos 1 (TX nach TX) wird IMMER von
  `encoder.transmit()` mit `False` (busy) abgewiesen. 5-Slot-Pattern
  TX-TX-RX-RX-RX ist halb tot.
- **Issue A (kosmetisch):** Display-Zeit der RX-Slots ist Wall-Time
  (`time.time()`) statt Slot-Boundary `:00`/`:15`/`:30`/`:45`.

Log-Beweis (`~/.simpleft8/simpleft8.log` Zeilen 719920-720109):
```
[OMNI-CQ] User-Start
[OMNI-CQ] CQ-Audiofrequenz: 475 Hz
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B2 [1/4] TX-E uebersprungen
[OMNI-CQ] encoder.transmit busy -> Slot B1 [1/4] TX-O uebersprungen
[OMNI-CQ-UI] Stop (manual_halt)
```

3× Pos 1 busy hintereinander, deterministisch reproduzierbar.

## Vorgeschichte (R1-Blindspot — WICHTIG)

In **P4-V5 (v0.96.1)** hattest du als R1 in der Klaerungsfrage 3
(Decoder-Blockade) Variante A „kein Schutz" als KISS-konform abgesegnet.
**Aber du hast den Encoder-Throughput-Race zwischen Pos 0 TX und Pos 1
TX nicht erkannt.** Das ist genau der Bug der jetzt im Field-Test
explodiert ist.

Lesson dokumentiert in `memory/feedback_r1_encoder_busy_blindspot.md`:

> Wenn ein Plan zwei oder mehr konsekutive TX-Slots vorsieht, MUSS der
> R1-Prompt explizit nach Encoder-Throughput fragen.

**Bei P5 ist das jetzt deine Pflicht-Frage.**

## Plan-Files

- `prompts/p5_omni_pattern_fix3_diagnose.md` — Compact-feste Diagnose
- `prompts/p5_omni_pattern_fix3_v1.md` — V1 mit 4 Loesungsoptionen
- `prompts/p5_omni_pattern_fix3_v2.md` — V2 Self-Review mit verfeinerter
  Wurzel-Analyse, finalisierter Pending-Verfall-Code-Skizze und R1-Prompt-
  Brief (du liest gerade die externalisierte Version dieses Briefs).

V2 ist die Hauptquelle. Lies V2 zuerst, dann den Code.

## Deine konkreten 8 Aufgaben (sortiert nach Wichtigkeit)

### 1. Encoder-Throughput-Diagnose (Pflicht)

Bei FT8 12.64s Audio + PTT-Settle + FlexRadio-Buffer-Drain — wann faellt
`_is_transmitting=False` relativ zur naechsten Slot-Boundary?

Konkret: Slot-Start :30, Pos 0 TX-E. Wann faellt `_is_transmitting=False`?
- Schaetzung als absolute Zeit (`:42.x` / `:43.x` / `:44.x`)?
- Welche Streuung (Min/Max)?
- Welche Komponenten haben welche Latenz?

Code-Quellen:
- `core/encoder.py:178-212` `transmit()`
- `core/encoder.py:214-233` `_tx_worker` (finally setzt `_is_transmitting=False`)
- `core/encoder.py:264-385` `_tx_worker_inner` (Drift-Guard, Audio-Send)

### 2. Drift-Guard-Verhalten (Pflicht)

`core/encoder.py:331-340` Drift-Guard greift wenn `silence_secs < 0.1`
UND `overshoot > 0.3`. Bei OMNI's `_do_tx_slot`:

- cycle_start kommt aus `core/timing.py:76-90` Tick-Loop (alle 100ms)
  via Qt-QueuedConnection zum GUI-Thread.
- Typische cycle_start-Aufruf-Zeit beim GUI-Thread: 100-400ms NACH echter
  Slot-Boundary (V2 §1.1 Schaetzung).

→ Greift Drift-Guard systematisch bei OMNI? Wenn ja: was sind die
Konsequenzen (silence_samples 30s, Worker blockt 42s+, etc.)?

→ Wie passt das zur Field-Test-Beobachtung „Pos 0 TX-E :30 ✓"
(Mike sah TX bei :30, NICHT bei :60)? V2 §1.3 hat einen
Widerspruchs-Aufloesungs-Versuch — ist deine Diagnose besser?

### 3. Loesungsoptionen-Bewertung (Pflicht)

V2 §2 schlaegt 4 Varianten vor:

- **A — Encoder-Queue mit Pending-Verfall** (Mike-Empfehlung)
- **B — Mid-Cycle-Pretrigger via cycle_tick**
- **C — Pattern auf 1 TX/Block reduzieren** (Spec-Aenderung)
- **D — Pos 1 TX um 1 Slot verschieben** (Spec-Aenderung)

Welche ist KISS-konform und Hobby-Tool-tauglich? Begruendung mit
Code-Komplexitaet, Race-Risiken, Spec-Konformitaet.

### 4. V3-§8 Out-of-Scope (P4-V5) Verbote (Pflicht)

V3 §8 hatte Encoder-Queue + Mid-Cycle-Pretrigger explizit verboten:

```
❌ cycle_tick-basierter Pretrigger / QTimer
❌ Encoder-Queue für OMNI
❌ Aenderungen an core/encoder.py
❌ Frequenz-Recheck zur Laufzeit
```

War der Verzicht gerechtfertigt im Licht von Issue B? Soll die Liste in
P5 gekippt werden? Mit welcher Begruendung?

### 5. Hypothese H-Pos-4-RX-E-fehlt (V2 §1.4)

Mike sah keinen `:30 [E] Horche`-Eintrag fuer Pos 4 (Block 1, RX-E
:30 nach 4 Slots). V2 hat 6 Pfade abgeklappert und alle ausgeschlossen
(Pause, Stop, Off-by-one, Trim, advance_state-Drift, busy-Skip). Welche
Pfade habe ich uebersehen?

Eventuell ein Display-Bug in `qso_panel.add_listening` selbst?

### 6. Hypothese H-`:44 [O] Horche`-Quelle (V2 §1.3)

Bei busy-Pos-1 wird `slot_action` NICHT emittet (V5-Code Z. 226-229
nur log warning). Wer kann dann das `add_listening` bei `:44 [O]`
triggern?

`grep` zeigt main_window.py:760 als einzigen `add_listening`-Aufrufer.
Aber der wird bei busy-TX nicht aufgerufen (nur bei `is_tx=False`).

V2 vermutet entweder Mike-Beobachtungs-Fehler ODER UI-Bug. Was sagst du?

### 7. Pending-Verfall-Logik (V2 §2.1, §3)

Der vorgeschlagene Pending-Verfall:

```python
if pending_tx_even is not None:
    target_slot = ... (naechste passende Slot-Boundary)
    if target_slot - self._pending_queued_at > _SLOT * 1.5:
        # Verfall
```

- Ist `1.5 * cycle_duration` die richtige Schwelle?
- Edge-Case: Worker braucht genau 1.5 Slots → grenzwertig, was tun?
- Race: `_pending_queued_at` zwischen Pending-Setzen und finally-Lesen
  modifiziert → Lock noetig?
- Was wenn Pending-Re-Trigger erneut Drift-Guard-Bedingung ausloest?
  Dann verschiebt sich der Pending-TX um weitere 30s. Loop?

### 8. Test-Plan (V2 §3, §4)

V2 schlaegt T1-T11 vor (Unit + E2E). Sind die ausreichend? Welche
Race-Tests fehlen? Soll ich End-to-End mit echtem FT8Timer-Mock testen,
oder reicht Direct-Aufruf von `on_cycle_start`?

## Format deiner Antwort

Strukturiert in 6 Sektionen:

- **§A — Encoder-Throughput-Diagnose** (Aufgabe 1+2)
- **§B — Loesungsoptionen-Bewertung** (Aufgabe 3+4)
- **§C — Hypothesen-Aufloesung** (Aufgabe 5+6)
- **§D — Pending-Verfall-Review** (Aufgabe 7)
- **§E — Test-Plan-Review** (Aufgabe 8)
- **§F — Empfehlung an Mike** (1-2 Saetze)

## KISS-Gebot

SimpleFT8 ist ein Hobby-Funker-Tool. KEINE Contest-Modi, KEINE
Power-User-Features. Wenn ein Vorschlag in Richtung Komplexitaet geht
(Multi-Threading, neue Module, neue Abstraktion) — pruefe zuerst „braucht
das ein Hobby-Funker?". Bei nein: ablehnen.

V3-§8 Out-of-Scope-Liste (V2 §7 unveraendert) muss respektiert werden.
Bitte KEINE Vorschlaege fuer Frequenz-Recheck, qso_state-Aenderungen,
Listener-Pfad, Diversity-Antennen-Switch, Auto-Hunt-Coupling, AP-Lite.

## Datei-Beilagen (alles Vollfiles)

- `core/encoder.py` (385 Z.)
- `core/omni_cq.py` (258 Z.)
- `core/timing.py` (91 Z.)
- `ui/main_window.py`
- `ui/mw_cycle.py`
- `ui/mw_qso.py`
- `ui/qso_panel.py`
- `prompts/p4_omni_neubau_v5_signal_v3.md`
- `prompts/p5_omni_pattern_fix3_v2.md` (V2 Self-Review)

Lies V2 zuerst, dann den Code, dann antworte.

---

**Dein Output landet in `prompts/p5_omni_pattern_fix3_r1.md`.**
