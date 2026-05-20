# P98 — Retry-Limits 3 → 5 (V2 Self-Review)

V1 in `prompts/p98_retry_limits_v1.md`. V1 hat 6 Findings selbst gesammelt.
V2 klärt diese + ergänzt Code-Verifikations-Details für DeepSeek-R1.

## V2-Klärungen über V1

### V2-F1: Bild 1 DG8DBW-Analyse (V1-F3 ausführen)

Sequenz aus Mike-Screenshot:
```
14:34:15 [O] → Sende DG8DBW DA1MHH -17    (1. Versuch, state=TX_CALL)
14:34:30 [E] ← Empf DA1MHH DG8DBW R-19    (Antwort, state→TX_REPORT)
14:34:45 [O] → Sende DG8DBW DA1MHH RR73   (RR73 raus, state=WAIT_RR73, rr73_retries=0)
14:35:00 [E] ← Empf DA1MHH DG8DBW R-19    (DG8DBW hat unsere RR73 nicht!)
14:35:15 [O] → Sende DG8DBW DA1MHH RR73   (Retry, rr73_retries=1, immer noch RR73)
                                          ← (Timeout im RX-Slot 14:35:30)
✗ DG8DBW — Timeout
```

**Befund:** 2 RR73-Versuche, dann Timeout. Mit `MAX_RR73_RETRIES=3` sollten
eigentlich 4 RR73 total möglich sein (1 initial + 3 retries). Aber:

- `on_decoder_finished` Retry-Pfad triggert nur wenn `timeout_cycles == 1`
  (also nach 1 leerer RX-Slot ohne Antwort). Bei DG8DBW kam aber im
  nächsten Slot R-19 zurück (NICHT leer) → Retry-Pfad NICHT getriggert.
- Empf R-19 trifft auf state=WAIT_RR73. Was passiert dann?

→ V2-Frage an R1: was passiert bei `WAIT_RR73 + is_r_report` (Gegenstation
schickt Report statt 73)? Wahrscheinlich: Re-Send als Retry, aber via
welchem Branch?

**Hypothese:** Es gibt einen `on_message_received`-Branch der bei
WAIT_RR73 + R-Report die State auf TX_REPORT zurückwechselt und RR73
erneut sendet. Dabei wird `rr73_retries` inkrementiert. Nach 2-3 solchen
Wechseln greift Limit ODER `MAX_QSO_DURATION = 180s`.

**Field-Test-Konsequenz:** Mit `MAX_RR73_RETRIES = 5` bekommt Mike mehr
Versuche egal welcher Branch greift.

### V2-F2: V1-F5 — Settings-Default `"max_calls": 99` in config

Initial-Default in `config/settings.py:60` ist 99 — das bedeutet „quasi-
endlos". Mike hat aber im Field-Test 3 Versuche → seine Settings-Datei
muss `max_calls: 3` enthalten (vermutlich von früheren Sessions).

**Entscheidung V2:**
- `config/settings.py` Initial-Default lassen wie er ist (99) — Mike hat
  eigene Settings.
- Code-Fallback `get("max_calls", 3)` → `get("max_calls", 5)` damit bei
  NICHT-Settings-Daten der neue Default greift.

### V2-F3: WAIT_REPORT-Verzweigung

In V1 sind 3 Stellen mit `get("max_calls", 3)` aufgelistet. Bei Settings-
Aktualisierung (Mike-Settings-Wechsel) greift welcher Pfad?

- `ui/main_window.py:1216` — beim Start (Hauptpfad)
- `ui/mw_qso.py:251` — Settings-Reload
- `ui/mw_cycle.py:515` — **hartcodiert 3**, nicht aus settings! V1 sagt
  „wird 5". Aber WARUM steht da 3 hartcodiert? Bug oder Absicht?

V2 prüft Stelle:
```
ui/mw_cycle.py:515  self.qso_sm.max_calls = 3
```
Vermutlich Reset-Pfad nach OMNI/Hunt-Stop. → R1-Frage: wirklich
hartcodiert? Sollte der nicht aus settings lesen?

### V2-F4: Tests-Anpassungen erweitert

V1 erwähnt nur `test_p1_bundle2.py`. Ergänzung:
- `tests/test_p1_bundle2.py:41` Kommentar „voll ausgereizt" mit `=3`
  passt nach Change nicht mehr → ändern auf `=5`
- `tests/test_p1_bundle2.py:78` analog
- `tests/test_modules.py:2379, 2751` setzen explizit `max_calls = 6` —
  unkritisch (Test-Override).
- `tests/test_settings_dialog_smoke.py:29` `max_calls: 3` als fixture —
  unkritisch.

Plus Regression-Tests dass neue Defaults greifen.

## Plan-Update V2

### Code-Änderungen (final)
1. `core/qso_state.py:107` `MAX_RR73_RETRIES = 3` → `5`
2. `core/qso_state.py:121` (`@dataclass QSOData`) `max_calls: int = 3` → `5`
3. `core/qso_state.py:163` (`QSOStateMachine.__init__`) `max_calls = 3` → `5`
4. `ui/main_window.py:1216` `get("max_calls", 3)` → `get("max_calls", 5)`
5. `ui/mw_qso.py:251` `get("max_calls", 3)` → `get("max_calls", 5)`
6. `ui/mw_cycle.py:515` `qso_sm.max_calls = 3` → `qso_sm.max_calls = 5`
7. `ui/settings_dialog.py:51` Hint-Text aktualisieren: „5 = Standard
   (FT8-üblich), 3 = schnell weiter, 7 = hartnäckig, 99 = quasi-endlos"

### Tests-Anpassungen
- `tests/test_p1_bundle2.py:41,78` `rr73_retries = 3` → `5` + Kommentar
  aktualisieren
- 5 neue Tests in `tests/test_p98_retry_limits.py`

### Doku
- HISTORY/HANDOFF/CLAUDE/TODO + APP_VERSION 0.97.69 → 0.97.70

## Fragen an DeepSeek-R1

1. **Bild 1 DG8DBW-Analyse:** im Code `on_message_received` mit
   state=WAIT_RR73 + is_r_report — welcher Branch greift? Wie ist die
   Re-Send-Logik bei nochmaligem R-Report?

2. **`ui/mw_cycle.py:515` hartcodiert 3:** wirklich Absicht oder Bug?
   Sollte aus settings lesen?

3. **Tests `test_p1_bundle2.py:41,78`:** mein V2-Plan setzt `rr73_retries
   = 5` damit „voll ausgereizt" semantisch stimmt. Alternative: Konstante
   importieren und damit testen?

4. **Field-Test-Risiko:** 5 Retries × FT8-Slot = 75s reine TX-Zeit pro
   Station. Insgesamt mit RX-Slots dazwischen ≈ 150s. Knapp unter
   `MAX_QSO_DURATION = 180s`. Sicherheit gegen Hang?

5. **Anderen Konstanten anfassen?** `MAX_STATION_CALLS = 7` als hartes
   Maximum bleibt? Oder hochsetzen?

6. **Final-Check:** missing edge cases? Tests-Coverage ausreichend?
