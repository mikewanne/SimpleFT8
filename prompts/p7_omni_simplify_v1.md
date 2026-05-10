# P7.OMNI-SIMPLIFY — V1 (Mike-Spec radikale Vereinfachung, 10.05.2026)

**Datum:** 2026-05-10 ~10:30 UTC
**Vorgaenger:** v0.96.3 P6.OMNI-DOUBLE-AUDIO (gescheitert)
**Status:** V1 Entwurf

---

## 0. Spec-Quelle

Mike-Dialog 10.05.2026 ~10:30 UTC nach Field-Test v0.96.3:
- P5 Pending-Verfall: `Pending TX verfallen (diff=29.8s > 22.5s)` → Pos 1 wurde verworfen
- P6 Pair-Audio: 27.6s durchgehend `_is_transmitting=True` → **Diversity-Antennen-Switching pausiert**
- Mike's Aussage: „Diversity ist der Kern, **unantastbar**, das laeuft top"
- Mike-Vorschlag: OMNI als simples Single-Slot-CQ mit Paritaets-Wechsel an Diversity-Re-Mess gekoppelt

---

## 1. Symptome (warum P5+P6 nicht funktionieren)

### 1.1 P5 (Encoder-Pending-Queue)
- Verfall-Schwelle `1.5 * cycle_duration = 22.5s` zu klein
- Real-Diff bei OMNI-konsekutiven Slots: 29.8s
- Auch bei groesserer Schwelle: TX kaeme 30s zu spaet → in Pos-3-RX-Slot rein
- **Variante A loest das Race nicht — physisch unmoeglich, 2 TX in 15s-Slots ohne Pre-Trigger**

### 1.2 P6 (Pair-Audio)
- Pos 0 + Pos 1 als 1 Audio-Block (27.6s durchgehend TX)
- `_is_transmitting=True` fuer 28s
- `mw_cycle.py:595` TX-Schutz: `if self.encoder.is_transmitting: return`
- → **Diversity-Antennen-Switching wird 28s lang skipped pro Pair**
- Mike sieht „nur eine Antenne" → Diversity de facto ausser Betrieb waehrend OMNI

### 1.3 Wurzel
TX-TX-direkt-konsekutiv passt physisch nicht zu Encoder + Diversity. Beide Workarounds (Pending-Queue, Pair-Audio) brechen entweder das Pattern (P5) oder Diversity (P6).

**Loesung muss anderswo ansetzen: Pattern aendern statt Encoder/Diversity verbiegen.**

---

## 2. Neue Spec (Mike-Idee, 10.05.2026 ~10:30)

### 2.1 Kernkonzept

OMNI ist ein **Single-Slot-CQ-Modus** der gekoppelt an Diversity-Re-Messung die Slot-Paritaet wechselt.

```
OMNI-Toggle  →  CQ alle 30s in Slot-Paritaet P (Even ODER Odd)
                P = aktuelle Slot-Paritaet beim ersten cycle_start
                
~5 Min Even (~10 CQ-Rufe)
   |
   v
Diversity-Re-Mess startet  →  Paritaet wechseln (P = !P)
   |  (Mess-Phase ist TX-frei → kein Konflikt)
   v
~5 Min Odd (~10 CQ-Rufe)
   |
   v
Diversity-Re-Mess startet  →  Paritaet wechseln zurueck
   |
   v
... permanent alternierend
```

### 2.2 Was wegfaellt vom alten OMNI

- ❌ 5-Slot-Pattern (TX-TX-RX-RX-RX)
- ❌ Block 1 / Block 2 mit gespiegelten Paritaeten
- ❌ Auto-Block-Rollover nach 5 Slots
- ❌ Toggle-Start IMMER Block 1
- ❌ counter_changed (Even+Odd separat) — nur 1 Counter
- ❌ Encoder-Pending-Queue (P5)
- ❌ Pair-Audio (P6)
- ❌ Mid-Stream Timer fuer tx_started

### 2.3 Was erhalten bleibt

- ✅ Frequenz-Sticky (bei erstem TX, dann fix)
- ✅ Diversity-only (Mode-gekoppelt)
- ✅ Pause/Resume bei eingehender Antwort
- ✅ Stop-Bedingungen: manual_halt, band_change, mode_change
- ✅ Hardware-Pflicht ANT1 (encoder.transmit setzt zentral)
- ✅ Easter-Egg-Toggle ueber Versionsnummer (UI bleibt)

### 2.4 Re-Mess-Trigger-Synchronitaet (Mike-Praezisierung)

**Wichtiger Edge-Case:** Diversity-Re-Mess pausiert bei laufendem QSO (existierende Logik). Wenn Paritaets-Wechsel an einen TIMER gekoppelt waere, koennte er waehrend QSO triggern → CQ und Re-Mess waeren nicht mehr synchron.

**Loesung:** Trigger ist die **echte Re-Mess** — nicht ein Timer.

- QSO startet → Mess pausiert (existierend)
- Waehrend QSO → keine Re-Mess → kein Wechsel → OMNI bleibt auf alter Paritaet
- QSO endet → Mess kann wieder starten
- Naechste echte Re-Mess startet → Paritaets-Wechsel
- → CQ-Pfad und Re-Mess sind IMMER synchron

### 2.5 Wechsel-Zeitpunkt

**Bei Re-Mess START** (nicht Ende):
- `_diversity_ctrl.start_measure()` ist EINE klare Methode
- Mess-Phase ist TX-frei → Wechsel wirkt sich erst nach Mess aus, kein Race
- Robuster als Ende (kein Phase-Uebergang ueberwachen)

---

## 3. Code-Verifikation (Stand 10.05.2026 ~10:30)

| File:Line | Symbol | Stand | Aktion |
|---|---|---|---|
| `core/encoder.py:85` | `_pending_tx`, `_pending_queued_at` | P5-State | **WEG** |
| `core/encoder.py:187-247` | `transmit()` mit Pending-Pfad | P5-Pending-Logik in transmit() | **rueckrollen auf vor v0.96.2** |
| `core/encoder.py:249-290` | `_tx_worker` mit Pending-Loop | P5-Loop | **rueckrollen auf single-pass** |
| `core/encoder.py:292-447` | `transmit_pair`, `_tx_pair_worker`, `_tx_pair_inner` | P6-Pair | **WEG** |
| `core/encoder.py:449-490` | `_run_one_tx_pass`, `_compute_target_slot` | P5-Helper | **WEG** |
| `core/omni_cq.py:60` | `_TX_PATTERN = (T,T,F,F,F)` | 5-Slot-Pattern | **WEG** |
| `core/omni_cq.py:74-79` | `_slot_index`, `_block`, counters | Block-State | **stark vereinfacht** |
| `core/omni_cq.py:82, 101, 119, 245, 249, 257` | `_pair_in_progress` | P6-Flag | **WEG** |
| `core/omni_cq.py:170-183` | `on_cycle_start(cycle_num, is_even)` | Pattern-Logik | **REWRITE auf single-slot** |
| `core/omni_cq.py:188-201` | `_next_slot_action()` | TX-Pattern-Lookup | **WEG** |
| `core/omni_cq.py:203-273` | `_do_tx_slot`, `_do_rx_slot`, `_advance_state`, `_slot_label` | Pattern-Helpers | **WEG** |
| `ui/mw_cycle.py:619-620` | `should_remeasure()` + `start_measure()` | Re-Mess-Trigger-Stelle | **NEU: Hook auf `omni_cq.flip_tx_parity()`** |
| `ui/main_window.py:752-770` | `_on_omni_slot_action(label, is_tx, target_even)` | OMNI-Slot-Display | **VEREINFACHEN** (kein _do_rx_slot mehr → keine Horche-Anzeige aus OMNI; oder behalten falls nuetzlich) |
| `core/diversity.py:499` | `start_measure()` | Bestehende Methode | **NICHT anfassen** (nur Hook hinzufuegen) |

---

## 4. Loesung

### 4.1 Encoder zurueckrollen

`core/encoder.py` zurueck auf den Stand vor v0.96.2 (Commit `a0f45ee` P5-Vorbereitung):
- `_pending_tx`, `_pending_queued_at` weg aus `__init__`
- `transmit()` ohne Pending-Branch (returnt False bei busy, wie alte v0.96.1)
- `_tx_worker` als single-pass (wie alte v0.96.1)
- `transmit_pair`, `_tx_pair_worker`, `_tx_pair_inner` komplett weg
- `_run_one_tx_pass`, `_compute_target_slot` weg

### 4.2 omni_cq.py radikal vereinfachen

```
class OmniCQ(QObject):
    Signals:
      omni_started, omni_stopped, slot_action, cq_freq_changed,
      cq_count_changed (1 Zaehler statt 2)
    
    State:
      _active, _paused
      _cq_audio_hz: int | None  (sticky)
      _cq_tx_even: bool | None  (NEU — gewaehlte Paritaet)
      _cq_count: int            (1 Zaehler statt 2)
    
    API:
      start()                   →  _active=True, _cq_tx_even=None (wird beim ersten cycle_start gesetzt)
      stop(reason)
      pause()
      resume_after_qso(...)
      flip_tx_parity()          →  NEU public, von mw_cycle gerufen bei Re-Mess
      on_cycle_start(cycle_num, is_even):
          if not active or paused: return
          if _cq_tx_even is None:
              _cq_tx_even = is_even   # erster Slot waehlen
          if _cq_audio_hz is None:
              _init_audio_freq()
          if is_even == _cq_tx_even:
              # mein Slot — sende
              encoder.transmit(cq_msg, tx_even=_cq_tx_even, audio_freq_hz=_cq_audio_hz)
              _cq_count += 1
              cq_count_changed.emit(_cq_count)
              slot_action.emit(label, True, _cq_tx_even)
          # else: warten bis naechster passender Slot
```

### 4.3 mw_cycle Hook fuer Re-Mess

`ui/mw_cycle.py:620` direkt nach `start_measure()`:
```
if self._diversity_ctrl.should_remeasure(qso_active, cq_active):
    self._diversity_ctrl.start_measure()
    # NEU P7: OMNI-Paritaet wechseln synchron zur Re-Mess.
    if hasattr(self, '_omni_cq') and self._omni_cq.is_active():
        self._omni_cq.flip_tx_parity()
    ...
```

### 4.4 main_window._on_omni_slot_action

Variante A — wegwerfen (kein RX-Anzeige mehr, OMNI ist passiver Modus, RX-Stationen kommen ueber rx_panel an):
```
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label, is_tx, target_even):
    # P7: nur TX-Slots geben hier slot_action — kein Horche-Display mehr.
    pass  # oder loeschen
```

Variante B — Horche-Display fuer „nicht-mein"-Slots behalten:
```
@Slot(str, bool, bool)
def _on_omni_slot_action(self, label, is_tx, target_even):
    if not is_tx:  # OMNI emit "horche" fuer fremd-paritaet
        ...
```

**V1 schlaegt Variante A vor** (Display weg) — vereinfacht. V2/R1/V3 koennen das ueberdenken.

---

## 5. Akzeptanzkriterien

| AC | Kriterium | Test |
|---|---|---|
| AC1 | OMNI-Start in Diversity-Mode aktiviert _active=True, _cq_tx_even=None | T1 |
| AC2 | Erster on_cycle_start setzt _cq_tx_even auf is_even des aktuellen Slots | T2 |
| AC3 | Auf passendem Slot (is_even == _cq_tx_even): encoder.transmit gerufen + cq_count erhoeht + slot_action emit | T3 |
| AC4 | Auf unpassendem Slot (is_even != _cq_tx_even): kein encoder.transmit | T4 |
| AC5 | flip_tx_parity() toggelt _cq_tx_even (True ↔ False) | T5 |
| AC6 | mw_cycle._on_cycle_start ruft omni._omni_cq.flip_tx_parity() bei Re-Mess-Start | T6 (Integration) |
| AC7 | Pause: _cq_tx_even bleibt; resume_after_qso: _cq_tx_even bleibt (Sync via Re-Mess, nicht via Resume) | T7 |
| AC8 | Frequenz-Sticky: _cq_audio_hz wird 1× gesetzt, dann fest | T8 |
| AC9 | Stop: _active=False, _cq_tx_even=None, _cq_count=0, _cq_audio_hz=None | T9 |
| AC10 | Hardware-Garantie ANT1: encoder.transmit setzt zentral (unveraendert) | Code-Read |
| AC11 | Diversity-Switching laeuft normal (kein P6-Pair-Block) | Field-Test |
| AC12 | Tests-Bilanz: 1034 → ~1000 gruen (massiv weniger Tests durch Pattern-Wegfall) | pytest |

---

## 6. Field-Test-Plan

| F | Test | Erwartung |
|---|---|---|
| F1 | App start, Diversity, OMNI toggeln | OMNI-Start-Log + CQ-Audiofreq-Set |
| F2 | 5 Min beobachten | CQ-Ruf jede 30s in EINER Paritaet, Antennen-Switching laeuft normal |
| F3 | Diversity-Re-Mess kommt (nach ~5 Min) | OMNI-Paritaet wechselt automatisch (Log: „[OMNI-CQ] Paritaets-Wechsel auf Even/Odd") |
| F4 | Antwort kommt waehrend OMNI | OMNI pausiert, QSO laeuft normal |
| F5 | QSO endet | OMNI resumed in alter Paritaet, neue Re-Mess kommt eventuell, dann Wechsel |
| F6 | Bandwechsel mid-OMNI | OMNI auto-stop (band_change) |
| F7 | Mode-Wechsel auf Normal | OMNI auto-stop (mode_change) |
| F8 | Diversity-Anzeige im UI | Beide Antennen wechseln sichtbar (kein „nur eine") |

**Bestanden wenn:** F1-F3 sauber + F8 zeigt Diversity normal aktiv.

---

## 7. Test-Plan

### 7.1 Tests die WEGGEHEN

- `tests/test_encoder_pending.py` (8 Tests) — komplett WEG
- `tests/test_omni_cq_signal.py` (32 Tests) — komplett NEU schreiben (alte Pattern-Tests obsolet)
- `tests/test_omni_cq_integration.py` — anpassen (neue API)

### 7.2 Tests die BLEIBEN

- `tests/test_main_window_slot_boundary.py` (5 Tests) — bleibt, ist allgemeine Slot-Boundary-Berechnung
- Alle anderen Tests unangetastet

### 7.3 NEUE Tests fuer simplified OMNI

| ID | Name | AC |
|---|---|---|
| T1 | `test_start_initializes_state` | AC1 |
| T2 | `test_first_cycle_sets_tx_even_from_signal` | AC2 |
| T3 | `test_matching_cycle_calls_encoder_transmit` | AC3 |
| T4 | `test_non_matching_cycle_skips_encoder` | AC4 |
| T5 | `test_flip_tx_parity_toggles` | AC5 |
| T6 | `test_remeasure_triggers_flip_via_mw_cycle` (Integration) | AC6 |
| T7 | `test_pause_resume_keeps_parity` | AC7 |
| T8 | `test_frequency_sticky_after_first_tx` | AC8 |
| T9 | `test_stop_resets_state` | AC9 |
| T10 | `test_remeasure_during_qso_no_flip` (Re-Mess pausiert bei QSO → kein Flip) | AC6+AC7 |

**Erwartete Bilanz:** 1034 → 994 gruen (-40 Pattern-Tests, +10 simplified Tests, -8 Pending-Tests, +netto)

### 7.4 KEIN Worker/Sleep/Boundary-Mock

(Lesson `feedback_test_critical_path_not_mock.md`) — Tests rufen `on_cycle_start` direkt mit synthetischen Werten, kein Encoder-Worker-Mock notwendig (encoder ist MagicMock).

---

## 8. Atomare Commits-Plan

| # | Commit | Files | Tests |
|---|---|---|---|
| C1 | `core/encoder.py: P5+P6 zurueckrollen (transmit_pair + Pending-Queue weg)` | core/encoder.py | — |
| C2 | `core/omni_cq.py: radikale Vereinfachung (5-Slot-Pattern → single-slot)` | core/omni_cq.py | — |
| C3 | `ui/mw_cycle.py: Re-Mess-Hook → omni_cq.flip_tx_parity()` | ui/mw_cycle.py | — |
| C4 | `ui/main_window.py: _on_omni_slot_action vereinfachen` | ui/main_window.py | — |
| C5 | `tests: alte OMNI+Pending-Tests weg, neue simplified Tests` | tests/test_encoder_pending.py (DELETE), tests/test_omni_cq_signal.py (REWRITE), tests/test_omni_cq_integration.py (UPDATE) | T1-T10 |
| C6 | `main.py: APP_VERSION 0.96.3 → 0.96.4` | main.py:16 | — |
| C7 | `Doku: HISTORY + HANDOFF + CLAUDE + TODO + Memory + Spec` | HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md, memory/* | — |

**Reihenfolge:** C1 → grun-Check → C2 → grun-Check → C3 → C4 → C5 → grun-Check → C6 → C7.

**Pre-Code:** git status / Tests-Baseline 1034 verifizieren.

---

## 9. Out-of-Scope

- ❌ Diversity-Logik aendern (UNANTASTBAR per Mike-Spec)
- ❌ Re-Mess-Trigger-Logik aendern (`should_remeasure`, `start_measure` bleiben)
- ❌ Encoder-Pending oder Pair (sind eh raus durch P7)
- ❌ Normal-CQ-Pfad anfassen (`qso_state.cq_mode` bleibt)
- ❌ Counter-Display ueberarbeiten (1 Counter statt 2 ist ok, UI zeigt es weiterhin)

P7 ist NUR: OMNI radikal vereinfachen + Re-Mess-Hook.

---

## 10. APP_VERSION-Plan

`v0.96.3 → v0.96.4` (Patch-Bump: OMNI-Refactor, kein neues Feature).

---

## 11. Doku-Update Plan (C7)

- `HISTORY.md`: P7-Eintrag mit Wurzel (P5+P6 nicht-passend), neue Spec, Test-Bilanz, Commit-Hashes
- `HANDOFF.md`: Stand „P7 ERLEDIGT, Field-Test pending"
- `CLAUDE.md` Header: Aktueller Stand v0.96.4
- `TODO.md`: P7-Block raus, Field-Test als TOP
- `memory/project_omni_cq_spec.md`: **Spec komplett neu** (alte 5-Slot-Spec obsolet, neue single-slot-Spec)
- `memory/MEMORY.md` Index: P5-Eintrag „abgebrochen wegen Diversity-Block", P7-Eintrag „aktuell ✅"
- `memory/project_p7_omni_simplify.md`: NEU — Trigger-File fuer fresh-Instanz nach Compact

---

## 12. Risiko-Bewertung

| ID | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | Re-Mess-Hook greift nicht bei jeder Re-Mess (z.B. unterschiedliche Pfade in mw_cycle) | Niedrig — `start_measure()` ist EINZIGE Stelle in mw_cycle | Code-Read verifiziert + T6 |
| R2 | OMNI startet vor erster Re-Mess → Paritaet bleibt 5+ Min auf Initial-Wert | Mittel — kann Mike's Erwartung verzerren | Akzeptiert, in Doku/Spec dokumentieren |
| R3 | Re-Mess waehrend QSO pausiert → bei Resume kein sofortiger Flip → Mike erwartet evtl. Wechsel | Mittel | Mike-Praezisierung: Sync IMMER ueber echte Re-Mess, nie ueber QSO-End-Trigger. Doku |
| R4 | Bestehende Tests brechen massiv (40+) | Hoch (gewollt) | Tests komplett neu schreiben, klar dokumentieren |
| R5 | Encoder-Rueckrollung bricht andere Pfade (P1.9 Replace, etc.) | Niedrig — P5+P6 sind isoliert hinzugefuegt, P1.9 vor v0.96.2 | Tests verifizieren (test_p1_9_replace.py) |
| R6 | Mike's Mike-Frequenz-Algorithmus (`get_free_cq_freq`) returnt None → Fallback 1500 | Niedrig (existierend) | unveraendert |
| R7 | Counter-Display zeigt nur noch 1 Zaehler statt 2 (Even+Odd) | Mittel — UI muss angepasst werden | C4 oder separater UI-Cleanup |

---

## 13. Plan-Files Verzeichnis

- 🔜 `prompts/p7_omni_simplify_v1.md` (DIESE DATEI)
- 🔜 `prompts/p7_omni_simplify_v2.md` (Self-Review)
- 🔜 `prompts/p7_omni_simplify_r1_prompt.md` (R1-Brief)
- 🔜 `prompts/p7_omni_simplify_r1.md` (R1-Output)
- 🔜 `prompts/p7_omni_simplify_v3.md` (Compact-fest, Code-Plan)

---

## 14. Naechste Schritte

1. **V2 Self-Review** (Claude) — was uebersieht V1?
2. **R1 (DeepSeek-Reasoner)** — Brief mit V1+V2, Code-Files
3. **V3 (Compact-fest)** — alle Findings einarbeiten
4. **Mike-Freigabe**
5. **Compact** (Cold-Start-Test post-Compact)
6. **Code** (atomare Commits C1-C7)
7. **Final-R1**
8. **Field-Test mit Mike** (V3 §6)
9. **Push**

---

**Ende V1.**
