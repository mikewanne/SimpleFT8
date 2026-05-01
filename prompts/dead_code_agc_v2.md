# Cleanup I — Dead-Code _apply_agc raus — V2

**Status:** V2 (nach Self-Review von V1, vor R1-Review).

---

## V1 → V2 Self-Review-Diff

V1 war minimal aber sauber. Self-Review fuegt 2 Punkte hinzu:

1. **`recent_calls` deque-Check (Z.125):** ist die `recent_calls`-
   deque wirklich genutzt? Schauen.
2. **`occupied_freqs`-Liste (Z.126):** wird die noch genutzt?
3. **`input_sample_rate = 24000`-Member (Z.127):** wird die ausser
   bei einem Read genutzt?

Wenn weiterer toter Code drin ist, kann ich den im selben Cleanup
mit erschlagen. Aber: KISS sagt SCOPE klein halten — nur AGC-
Cleanup, nicht „alle Member auditieren".

**Entscheidung V2:** Scope auf AGC begrenzt. R1 darf in P5 darauf
hinweisen, aber separater Workflow fuer andere Cleanups.

---

## Aenderungen (1:1 wie V1)

### `core/decoder.py`

- Z.51-55: 5 `_AGC_*`-Konstanten loeschen
- Z.58-94: `_apply_agc`-Funktion loeschen
- Z.130: `self._agc_state`-Init loeschen
- Z.270-271: auskommentierter Aufruf + Kommentar loeschen

### `tests/test_modules.py`

- Z.22-57: 4 AGC-Tests + Header-Kommentar loeschen

---

## Akzeptanzkriterien (V1 unveraendert)

A1. App-Verhalten 1:1 unveraendert.
A2. Decoder-Pipeline weiterhin funktional.
A3. Tests: 514 → 510 (4 AGC-Tests weg).

---

## Frage an R1

(unveraendert von V1, P1-P5)

---

## V2-Spec-Notiz

Cleanup ist trivial — V1/V2 fast identisch. Bei so kleinen
Aufgaben ist der Workflow Beleg-Stueck, nicht Risikomanagement.
R1 soll trotzdem pruefen ob etwas uebersehen wurde (z.B. weitere
tote Member im decoder.py).
