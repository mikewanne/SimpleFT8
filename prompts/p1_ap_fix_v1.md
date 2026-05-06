# P1.AP-FIX V1 — Diagnose-Prompt

**Stand:** 2026-05-06.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Plan → Code.
**Quelle:** P1.AP E2E-Test-Pipeline (v0.95.9) hat den Bug entdeckt.
**Test-Beweis:** `tests/test_ap_lite_e2e.py::test_generate_candidates_state1_format_bug` und `::test_try_rescue_state1_documents_bug`.

---

## 1. Ziel

`core/ap_lite.py:generate_candidates` produziert für State 1 (WAIT_REPORT)
FT8-konforme 3-Token-Kandidaten statt aktuell 4-Token-Strings, die ft8lib
ablehnt. Damit funktioniert der häufigste Rescue-Pfad (WAIT_REPORT) erstmals
seit Implementierung.

---

## 2. Akzeptanzkriterien

1. `generate_candidates(qso_state=1, ...)` liefert eine Liste mit ≥ 1 String
   wo jeder String exakt 3 Tokens hat (Format
   `OWN_CALL THEIR_CALL [+/-]NN`).
2. Alle generierten State-1-Kandidaten werden von `ft8lib.encode()` ohne
   `rc=5` akzeptiert (kein Fehler-Print).
3. `try_rescue` für State 1 mit zwei sauberen Buffern (echtes ft8lib-
   Encoding der Wahrheit) liefert `success=True` und
   `recovered_message` enthält die echten Callsigns.
4. Die existierenden Bug-Dokumentations-Tests
   (`test_try_rescue_state1_documents_bug`,
   `test_generate_candidates_state1_format_bug`) werden invertiert oder
   ersetzt — sie waren als Schutznetz gedacht und müssen am gefixten
   Verhalten ausgerichtet werden.
5. Bestehende E2E-Tests die NICHT State-1-spezifisch sind, bleiben grün.
6. Bestehende 24 unit-tests `tests/test_ap_lite.py` bleiben grün
   (insbesondere `test_generate_state1_basic`, `test_generate_state1_snr_range`,
   `test_generate_state1_snr_clamping` müssen ggf. angepasst werden weil
   sie das alte 4-Token-Format prüfen — das müssen wir verifizieren).
7. Gesamttests grün: 830 passing → erwartet ≥ 830 (durch Anpassungen
   können einzelne Test-Asserts sich ändern, Anzahl bleibt mind. gleich).

---

## 3. Betroffene Module/Dateien

- `core/ap_lite.py:121-127` — `generate_candidates` State-1-Branch.
  Aktuell:
  ```python
  if qso_state == 1:
      for snr_delta in range(-5, 6, 2):  # SNR-Fenster ±4 dB
          r = max(-30, min(29, snr_clamped + snr_delta))
          candidates.append(f"{own_callsign} {their_callsign} {own_locator} {r:+03d}")
  ```
  Vorschlag:
  ```python
  if qso_state == 1:
      for snr_delta in range(-5, 6, 2):  # SNR-Fenster ±4 dB
          r = max(-30, min(29, snr_clamped + snr_delta))
          candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
  ```
  Plus Code-Kommentar Z.122 anpassen (Format-Beschreibung).
- `tests/test_ap_lite_e2e.py` — 2 Bug-Doku-Tests umkehren in „rescue-funktional"-Tests.
- `tests/test_ap_lite.py` — Format-Asserts in `test_generate_state1_*` ggf. anpassen.

---

## 4. Randbedingungen

- **FT8-Konvention:** Jeder Frame hat genau 3 Tokens. Antwort auf Hunt-Call
  ist entweder Report (`+05`) ODER Grid (`JO31`), niemals beides.
- **AP_LITE_ENABLED=True** (live in Mike's Setup) — Fix wirkt sofort beim
  nächsten Decode-Fail im WAIT_REPORT-State.
- **Keine Hardware-Validierung in Kur** — synthetische E2E-Tests müssen
  beweisen dass der Fix korrekt ist (ft8lib akzeptiert, score > 0).
- **ANT1=TX-Pflicht** ist hier irrelevant (AP-Lite manipuliert RX-Buffer,
  triggert keinen TX direkt).
- **ADIF-Risiko:** Mit Fix kann State-1-Rescue erstmals echte QSOs
  rekonstruieren — falls `SCORE_THRESHOLD=0.75` zu permissiv ist, könnten
  falsche Reports geloggt werden. Aktueller Schutz: Mike's Field-Test-
  Validierung post-Kur. **Threshold NICHT in diesem Workflow ändern.**
- **Doku-Konsistenz:** Code-Kommentar Z.122 ist fachlich falsch („Report
  + Locator"). Muss mit-korrigiert werden, sonst wiederholt der nächste
  Reviewer den Bug.

---

## 5. Nicht im Scope

- `SCORE_THRESHOLD` Tuning (separates TODO post-Field-Test).
- `_build_costas_reference` Verbesserung (Code-TODO existiert, separat).
- State 3 Locator-Heuristik (auch Code-TODO, separat).
- AP-Lite-Disable wenn Fix riskant erscheint — Mike entscheidet im V3.
- Field-Test-Validierung — geht erst nach Kur.

---

## 6. Testbarkeit

**Unverzichtbar:**
- Test: `generate_candidates(state=1, ...)` liefert nur 3-Token-Strings.
- Test: jeder generierte Kandidat geht durch `encoder.generate_reference_wave`
  ohne `None`-Return (= ft8lib akzeptiert).
- Test: `try_rescue` State 1 mit sauberen Buffern → `success=True` und
  `recovered_message` ist 3-Token-Format.
- Test (Regression): die anderen 12 P1.AP-E2E-Tests bleiben grün.
- Test (Regression): die 24 P1.AP-Unit-Tests in `test_ap_lite.py` bleiben grün.

**Manuelle Code-Verifikation (V1):**
- `tests/test_ap_lite.py:34-66` (test_generate_state1_*) lesen — prüfen
  welche Asserts auf 4-Token bauen.

---

## 7. Bug-Befund (Hintergrund)

`core/ap_lite.py:126` (seit Implementierung):
```python
candidates.append(f"{own_callsign} {their_callsign} {own_locator} {r:+03d}")
# z.B. "DA1MHH DK5ON JO31 +05"  → 4 Tokens
```

FT8-Frame-Format erlaubt nur 3 Tokens. ft8lib lehnt mit `rc=5` →
`generate_reference_wave` returnt `None` → `correlate_candidate` returnt
0.0 → State-1-Rescue **scheitert IMMER mit score=0**, auch bei sauberen
Buffern (E2E-Test-Beweis 2026-05-06).

Symptom in Praxis: schwache QSOs im WAIT_REPORT-State werden NICHT
gerettet obwohl AP-Lite das Feature dafür ist.

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
