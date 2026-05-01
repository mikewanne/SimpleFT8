# Cleanup I — Dead-Code raus (AGC + input_sample_rate) — V3

**Status:** V3 (nach R1-Review von V2, Mike-Freigabe vorab erteilt).

---

## R1-Bilanz V2 → V3

| Frage | R1-Antwort |
|---|---|
| P1 toter Code wirklich tot | JA — kein Aufruf, keine Referenz |
| P2 Test-Loeschung sicher | JA — KISS-Win, kein Verlust |
| P3 Git-History als Backup | JA — kein Stub-Kommentar |
| P4 Side-Effect-Risiko | NEIN — keine Race-Condition |
| **P5 eigeninitiativ** | **`self.input_sample_rate = 24000` (Z.127) auch tot — nie gelesen, hartcodiert in `_resample_to_12k(source_rate=24000)` Z.233** |

V3 nimmt R1's P5 mit auf — Mike's „ich nehme alles" deckt diesen
zusaetzlichen toten Member. Cleanup bleibt klein.

---

## Aenderungen (final)

### 1. `core/decoder.py`

Loeschen:
- Z.51-55: 5 `_AGC_*`-Konstanten
- Z.58-94: `_apply_agc`-Funktion (~37 Zeilen)
- Z.127: `self.input_sample_rate = 24000` (R1-P5)
- Z.130: `self._agc_state`-Init
- Z.270-271: auskommentierter Aufruf + Kommentar

### 2. `tests/test_modules.py`

Loeschen Z.22-57: 4 AGC-Tests + Header-Kommentar.

### 3. `core/timing.py` (NEU in V3 — Doc J integriert)

Schritt-0-Verifikation hat ergeben: `sync_ntp()` (Z.62-70) wird
NIRGENDS aufgerufen, `_ntp_offset` (Z.36) bleibt immer 0.0. Der
TODO-Kommentar in Z.44 ("ungetestet — Feldtest noetig (Vorzeichen,
Smoothing)") betraf genau diesen toten Pfad.

Loeschen:
- Z.36: `self._ntp_offset = 0.0`
- Z.44: TODO-Zeile im Docstring (zwei-Zeilen-Docstring auf eine
  Zeile reduzieren)
- Z.45 vereinfachen: `return ntp_time.get_time() + self._ntp_offset`
  → `return ntp_time.get_time()`
- Z.62-70: `sync_ntp()`-Methode loeschen

Gesamt-Reduzierung kombiniert (decoder.py + timing.py + tests):
~60 Zeilen.

---

## Akzeptanzkriterien

A1. App-Verhalten 1:1 unveraendert.
A2. Decoder-Pipeline weiterhin funktional.
A3. Tests: 514 → 510 (4 AGC-Tests weg).
A4. **NEU:** `_resample_to_12k(audio_raw, source_rate=24000)` Aufruf
    in `_process_cycle` weiterhin korrekt — `source_rate=24000`
    als Argument bleibt hardcoded, R1-bestaetigt.

---

## Atomare Commits (geplant)

1. `chore(decoder): toten AGC-Code + input_sample_rate-Member entfernen`
   — core/decoder.py + tests/test_modules.py
2. `chore(release): v0.85 — Dead-Code-Cleanup (Cleanup I)`
   — main.py + HISTORY.md + HANDOFF.md + CLAUDE.md + prompts

---

## Lessons-V3

R1's P5-Empfehlung als Beleg: der Workflow findet auch in
"trivialen" Aufgaben zusaetzlichen Wert. Hier ein 1-Zeilen-
Member der seit unbekannter Zeit ungenutzt ist.
