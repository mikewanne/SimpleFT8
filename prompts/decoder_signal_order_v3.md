# Fix E — Decoder-Signal-Reihenfolge fuer korrekten Fix D — V3

**Status:** V3 (nach DeepSeek-R1-Review von V2, Mike-Freigabe vorab erteilt).
**Datum:** 2026-04-30.
**Vorgaenger:** v0.81 (commit `267625d`) — Fix D (`on_decoder_finished`).
**Backup:** `Appsicherungen/2026-04-30_vor_decoder_reihenfolge_fix/`

---

## R1-Bilanz V2 → V3

R1-Review (deepseek-reasoner, Reviewer-Modus): **Fix E ist robust.**

| Frage | R1-Antwort |
|---|---|
| P1 Decoder-Hang | TRADEOFF — akzeptabel, kein Notfall-Tick |
| P2 Race message_decoded vs cycle_finished | JA — FIFO garantiert (selber Sender, gelockter Thread) |
| P3 `_assign_slot_parity` Konsistenz | JA — bestaetigt, `_tx_even` korrekt gesetzt |
| P4 Race cycle_start(N+1) vs cycle_finished(N) | TRADEOFF — selten, transient, akzeptabel |
| P5 try/finally? | NEIN — Slot ueberspringen sicherer als Halb-State-Tick |
| P6 eigeninitiativ | Keine weiteren edge-cases |

→ V3 = V2 mit R1-Bilanz dokumentiert. Implementation startet.

---

## Loesung (1:1 wie V2)

1. `core/decoder.py`: NEUES Signal `cycle_finished = Signal()`,
   emittet nach allen `message_decoded`-Emissions (auch im
   else-Branch fuer leere Slots).
2. `ui/mw_radio.py`: 1 neue `connect`-Zeile.
3. `ui/mw_cycle.py`: `on_decoder_finished`-Aufruf aus
   `_on_cycle_decoded` ENTFERNEN, in neue Methode
   `_on_cycle_finished` einfuegen.
4. `tests/test_modules.py`: 1 neuer Reihenfolge-Test.
5. `main.py`: APP_VERSION 0.81 → 0.82.
6. `HISTORY.md`: Eintrag.

---

## Akzeptanzkriterien (final, V2 unveraendert)

A1. Doppel-Report-Bug behoben (Real-QSO-Verifikation noetig).
A2. Retry-Pfad funktional, DT 0.0-0.1s.
A3. `msg._tx_even` Konsistenz gewahrt.
A4. CQ_WAIT in `on_cycle_end` (Slot-START), Decoder-unabhaengig.
A5. 3-Min-Gesamttimeout in `on_cycle_end`, Decoder-unabhaengig.

506 Tests gruen erwartet (505 + 1 Reihenfolge-Test).

---

## Atomare Commits (geplant)

1. `feat(decoder): cycle_finished-Signal nach message_decoded-Emissions`
   (decoder.py + Test)
2. `feat(mw_cycle): _on_cycle_finished aus cycle_finished-Signal`
   (mw_cycle.py + mw_radio.py)
3. `chore(release): v0.82 — Doppel-Report-Bug-Fix Korrektur (Fix E)`
   (main.py + HISTORY.md + prompts)

---

## Lessons-V3

Mike's Erinnerung "du arbeitest nicht den deepseek workflow" war
berechtigt. V1→V3 fuer Fix E ist der korrekte Pfad — nicht der
Quick-Fix. R1 hat zwar keinen BLOCKER gefunden, aber die
strukturierte Pruefung der Side-Effect-Liste (P3, P4) gibt mir
Sicherheit dass keine Regression entsteht.

**Lesson fuer Memory:** Bei jedem Bugfix der direkt nach einem
fehlgeschlagenen Bugfix kommt: **Workflow nicht abkuerzen.** Eile
fuehrt zu Fehler-Annahmen wie der V3-Fix-D-Annahme
("`_handle_normal_mode` ruft `on_message_received` direkt").
