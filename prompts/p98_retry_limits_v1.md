# P98 — Retry-Limits 3 → 5 (V1)

## Mike-Spec (Field-Test 20.05.2026)

Mike-Beobachtung in 2 Screenshots:
1. **DG8DBW**: Report empfangen → 2× RR73 gesendet → Timeout (zu früh!)
2. **TA4SSK**: 3 Sende-Versuche → beim 3. (!) kam Antwort durch
   → „kuck mal mit den 3 versuch gerade noch erwischt"

**Mike-Spec:** Beide Retry-Limits von 3 auf **5** hochsetzen.

## R1-Brainstorm-Ergebnis (vorab)

DeepSeek-R1 hat folgende Empfehlung gegeben:
- **JA, beide auf 5.** WSJT-X-Konvention 3-5 Versuche, oft 5.
- Risiko gering: 5 × 30s = 150s, bleibt unter `MAX_QSO_DURATION = 180s`
- Etikette ok im Hobby-Kontext (kein Contest)
- WAIT_RR73 (halbes QSO) verdient mehr Aufwand → konsistent mit Mike's Intuition

## Code-Realität (verifiziert)

`core/qso_state.py`:
- Z.106: `MAX_STATION_CALLS = 7` — hartes Maximum (bleibt!)
- Z.107: `MAX_RR73_RETRIES = 3` — **wird 5**
- Z.119: `max_timeout: int = 5` — Zyklus-Counter-Limit (bleibt)
- Z.121: `max_calls: int = 3` — Klassen-Default für WAIT_REPORT (**wird 5**)
- Z.163: `self.max_calls = 3` — Instance-Default in `__init__` (**wird 5**)

`config/settings.py`:
- Z.60: `"max_calls": 99` — Settings-Default (Mike hat aber wohl 3 in seiner
  gespeicherten Settings-Datei, das stays as is — User-Override).

`ui/main_window.py:1216`, `ui/mw_qso.py:251`:
- `self.qso_sm.max_calls = self.settings.get("max_calls", 3)`
  → Fallback 3 wird **5**

`ui/mw_cycle.py:515`:
- `self.qso_sm.max_calls = 3` — hartcodiert! (**wird 5**)

`ui/settings_dialog.py:227-228`:
- `addItems(["3", "5", "7", "99"])` — Combo enthält 5 schon ✓
- Z.51: Hint-Text aktualisieren auf neuen Default

## Plan

### Änderungen Code (4 Stellen)
1. `core/qso_state.py:107` `MAX_RR73_RETRIES = 3` → `MAX_RR73_RETRIES = 5`
2. `core/qso_state.py:121` `max_calls: int = 3` → `max_calls: int = 5`
3. `core/qso_state.py:163` `self.max_calls = 3` → `self.max_calls = 5`
4. `ui/main_window.py:1216` `get("max_calls", 3)` → `get("max_calls", 5)`
5. `ui/mw_qso.py:251` `get("max_calls", 3)` → `get("max_calls", 5)`
6. `ui/mw_cycle.py:515` `self.qso_sm.max_calls = 3` → `self.qso_sm.max_calls = 5`
7. `ui/settings_dialog.py:51` Hint-Text aktualisieren (Default-Info)

### Optional (separat)
- `config/settings.py:60` `"max_calls": 99` — soll der bleiben? Mike hat
  vermutlich seine eigene gespeicherte Settings-Datei. 99 als initial-
  default ist „quasi-endlos", nicht hilfreich. Auf 5 setzen?
  → V2-Klärung.

### Tests
**Existierende Tests:**
- `tests/test_p1_bundle2.py:41,78` `rr73_retries = 3 # voll ausgereizt`
  → semantisch falsch nach Change. **Anpassen auf 5** damit Kommentar
  stimmt + Test ist robuster.
- `tests/test_modules.py:2379, 2751` `max_calls = 6` — explizit gesetzt,
  bleibt valid.
- `tests/test_settings_dialog_smoke.py:29` `max_calls: 3` — Test-fixture,
  unkritisch.

**Neue Tests P98:**
- T1: `MAX_RR73_RETRIES == 5` (Konstanten-Test)
- T2: `QSOData.max_calls`-Default == 5 (Klassen-Default)
- T3: WAIT_REPORT erlaubt 5 Retries vor TIMEOUT (vorher 3)
- T4: WAIT_RR73 erlaubt 5 Retries vor TIMEOUT (vorher 3)
- T5: Settings-Fallback in mw_qso/mw_cycle/main_window ist 5

## V1-Findings / Selbst-Check

**F1:** `MAX_STATION_CALLS = 7` (hartes Cap) — Mike's 5 < 7 ✓, kein Konflikt.

**F2:** `MAX_QSO_DURATION = 180s` (3-Min-Gesamt-Timeout) — wirkt als Notbremse.
  Bei 5 Retries × ~30s = 150s + Initial-Call → könnte knapp werden bei langen
  Zyklen (FT8 = 15s, also 5 × 30s je Retry-Round inkl. RX-Slot dazwischen).
  Theoretisch: 1 Initial + 5 Retries = 6 Senden × 15s + 5 RX-Slots × 15s
  = 165s. Knapp unter 180s, aber drin. **Mike-Etikette: 3 Min Total-Timeout
  ist die echte Grenze, die brauchen wir nicht anfassen.**

**F3:** Im Bild 1 (DG8DBW) hatte er nur 2 RR73-Versuche bevor Timeout.
  Warum nicht 3? Vermutlich: `MAX_RR73_RETRIES = 3` aber bei `<= 3` startet
  bei 0 → maximal 4 RR73 (1 initial + 3 retries). DG8DBW hat aber nach 2
  Retries Timeout — könnte am Gesamt-Timeout (3 Min) gelegen haben, NICHT
  am Retry-Limit. **R1-Frage**: prüfen ob nicht-Retry-Limit der Bottleneck war.

**F4:** Setzen wir `settings.get("max_calls", 5)` — User der schon
  `max_calls: 3` gespeichert hat, kriegt weiterhin 3. Migration via
  Settings-Dialog erlauben (Mike kann nachstellen). Kein Force-Override.

**F5:** Wenn Settings-Datei `max_calls: 99` enthält (initial-default in
  config/settings.py heute) — der Test im Field schon mit 99 würde ewig
  rufen. Möglicherweise hatte Mike's Settings noch das alte default 3
  von früher. → V2: in Settings-Dialog Reset-Default ggf. mit anpassen.

**F6:** Tests müssen ÜBERPRÜFEN dass die State-Machine wirklich 5 Versuche
  macht (nicht nur dass Konstante 5 ist). Realistischer Test: max_calls=5,
  simuliere 5 RX-Slots ohne Antwort → erwarte 5 Retries dann TIMEOUT.

## Workflow

V1 (jetzt) → V2 (Self-Review) → R1 (DeepSeek Code-Verifikation) → V3 →
Code + Tests → Final-R1 → atomare Commits → Doku.
