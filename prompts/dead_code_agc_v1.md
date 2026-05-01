# Cleanup I — Dead-Code _apply_agc raus — V1

**Status:** V1 (Erstentwurf, vor Self-Review).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.84 (commit `11a6220`) — Feature H Tertile-Analyse.

---

## 0. Kontext

`core/decoder.py` enthaelt eine `_apply_agc`-Funktion (~40 Zeilen)
plus 5 `_AGC_*`-Konstanten plus ein `self._agc_state`-Member, das
seit Laengerem deaktiviert ist (Z.270-271):

```python
# RMS Auto-Gain Control — DEAKTIVIERT
# audio_12k, self._agc_state = _apply_agc(audio_12k, self._agc_state)
```

Der Aufruf ist auskommentiert, die Funktion + Konstanten + State-
Member existieren weiter ohne Verwendung in der Produktivlogik.

**Plus:** 4 Tests in `tests/test_modules.py:24-57` testen die tote
Funktion. Sie laufen gruen, sind aber bedeutungslos — sie testen
Code, der nie ausgefuehrt wird.

**KISS-Wert:** weg damit. Code-Reduzierung ohne
Verhaltensaenderung.

---

## 1. Aenderungen

### 1.1 `core/decoder.py`

Loeschen:
- Z.51-55: 5 `_AGC_*`-Konstanten
- Z.58-94: `_apply_agc`-Funktion (~40 Zeilen)
- Z.130: `self._agc_state`-Init im `__init__`
- Z.270-271: auskommentierter Aufruf + Kommentar

### 1.2 `tests/test_modules.py`

Loeschen Z.22-57 (4 AGC-Tests + Kommentar-Header):
- `test_agc_loud_signal`
- `test_agc_normal_signal`
- `test_agc_clipping_protection`
- `test_agc_silence`

### 1.3 Imports pruefen

`core/decoder.py` importiert `numpy as np`. Wird weiter genutzt
(im `_decode_loop`), kein Cleanup noetig.

---

## 2. Akzeptanzkriterien

### A — Funktional

A1. App-Verhalten 1:1 unveraendert (Funktion war eh nicht aktiv).
A2. Decoder-Pipeline unveraendert: `_resample_to_12k` →
    DT-Korrektur → `_preprocess_audio` → `_decode_with_subtraction`.
A3. Test-Suite gruen: 514 → 510 (4 AGC-Tests entfernt).

### B — Side-Effect-frei

B1. Keine API-Aenderung an `Decoder` (`__init__` interner Member
    weg, kein public method/property betroffen).
B2. Keine bestehende Caller-Logik betroffen.
B3. Keine andere Datei beruehrt (nur decoder.py + test_modules.py).

### C — Robustheit

C1. **Was wenn AGC spaeter wieder gebraucht wird?** Git-History hat
    den Code (commit-archive). Re-Aktivierung ist 5 Min Arbeit.
C2. **Was wenn AGC eine versteckte Side-Effect-Wirkung hatte?** Der
    auskommentierte Aufruf wurde ueber lange Zeit nie aktiviert,
    Real-Welt-Tests (mehrere QSO-Sessions, v0.78+) zeigen einwandfreies
    RX. Kein Risiko.

---

## 3. Code-Diff-Skizze

### 3.1 `core/decoder.py` — Block-Loeschen

Zeilen 51-94 (Konstanten + Funktion) entfernen.
Zeile 130 (`self._agc_state`-Init) entfernen.
Zeilen 270-271 (Kommentar + auskommentierter Aufruf) entfernen.

**Geloeschter Block 51-94 (Auszug zur Verifikation):**

```python
_AGC_TARGET_INT16: float = 8225.0
_AGC_ALPHA:        float = 0.02
_AGC_HYSTERESIS:   float = 3.0
_AGC_MAX_GAIN:     float = 4.0
_AGC_MIN_GAIN:     float = 0.1


def _apply_agc(audio_int16, gain_state):
    """RMS-basierter Auto-Gain-Control für FT8 Audio-Eingang."""
    # ... 30 Zeilen ...
    return audio_out, (current_gain, ema_gain)
```

### 3.2 `tests/test_modules.py` — Block-Loeschen Z.22-57

```python
# ── AGC ──────────────────────────────────────────────────────────────────────

def test_agc_loud_signal():
    ...

def test_agc_normal_signal():
    ...

def test_agc_clipping_protection():
    ...

def test_agc_silence():
    ...
```

---

## 4. Frage an R1 (Reviewer)

Du bist Senior-Reviewer. KEIN Code schreiben.

V1-Plan + angehaengter Code (`core/decoder.py`,
`tests/test_modules.py`).

**P1 (Toter Code wirklich tot?):** Greift IRGENDEIN Code-Pfad
auf `_apply_agc`, `_AGC_*` oder `self._agc_state` zu — auch
indirekt? Pruefe gegen den angehaengten Code.

**P2 (Test-Loeschung sicher?):** Die 4 AGC-Tests testen
mathematisches Verhalten der ungenutzten Funktion. Loeschen statt
behalten — KISS-Win oder Verlust?

**P3 (Git-History reicht als Backup?):** Falls AGC spaeter wieder
gebraucht wird — Git-History hat den Code, Re-Aktivierung
straightforward. R1, gibt es Argumente fuer "in-Code-Erhalten"
(z.B. Kommentar `# Reserved for AGC`)?

**P4 (Side-Effect-Risiko):** Selbst auskommentierter Aufruf war
durch `if abs(_shift_samples) > 100`-Pfad geguardet. Wenn ich
`_agc_state` aus `__init__` loesche, kann das eine Race-Condition
oder unerwartete AttributeError triggern? Pruefe Threading-Modell.

**P5 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. weiterer
toter Code im decoder.py, oder ob wir den `self.recent_calls`-
deque Member auch loeschen koennten — nenn es.

---

## 5. Out-of-Scope

- Re-Aktivierung von AGC mit besserem Algorithmus.
- Refactor des Decoder-Pipelines.
- Versionsbump v0.84 → v0.85.

---

## 6. Aufwandsschaetzung

~30 Min (15 Min Loeschen + 15 Min Tests + Final-R1).

---

## 7. Migration / Backwards-compat

- Public API unveraendert.
- Keine Settings-Datei-Aenderung.
- Tests reduzieren sich auf 510 (war 514).
