# P1.AP-FIX V2 — Self-Review

**Stand:** 2026-05-06.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Plan → Code.
**Aufgabe:** V1 als „frische KI" reviewen, Lücken schließen.

---

## L1 — V1 hat Test-Konflikt verkannt: `test_generate_state1_basic` Z.34-46

V1 §6 sagt nur „24 unit-tests sollen grün bleiben" — aber:
```python
def test_generate_state1_basic():
    for c in cands:
        assert "DA1MHH" in c
        assert "JO31" in c   # ⛔ JO31 darf nach Fix nicht mehr drin sein!
```

Mit dem Fix wird `JO31` aus den Kandidaten entfernt → dieser Test **MUSS**
fehlschlagen. Das ist KEIN Regression-Bug sondern korrekte Folge des Fixes,
aber V1 macht das nicht klar.

**V2-Korrektur:** Test `test_generate_state1_basic` MUSS umgeschrieben werden —
das ist Teil des Plans, kein Edge-Case.

`test_generate_state1_snr_range` (6 Kandidaten, korrekt) und
`test_generate_state1_snr_clamping` (SNR-Range, splittet `c.split()[-1]`) sind
**form-unabhängig** und überleben den Fix unverändert.

---

## L2 — V1 §6 fehlt: ft8lib-Acceptance-Test

V1 sagt „jeder Kandidat geht durch `encoder.generate_reference_wave` ohne
`None`-Return" — aber das ist kein Standalone-Test sondern Konsequenz des
Fixes. Besser:

**V2-Test (NEU):** `test_generate_candidates_state1_ft8lib_compatible`:
```python
def test_generate_candidates_state1_ft8lib_compatible(encoder):
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", -5.0)
    assert len(cands) > 0
    for c in cands:
        wave = encoder.generate_reference_wave(c, 1500.0)
        assert wave is not None, f"ft8lib lehnt Kandidaten ab: '{c}'"
```

Macht den Bug-Fix maschinell nachweisbar — falls jemand später wieder
4-Token-Format einbaut, schlägt der Test sofort an.

---

## L3 — V1 hat Edge-Case übersehen: SNR-Fenster-Schritt

`range(-5, 6, 2)` produziert `[-5, -3, -1, 1, 3, 5]` — 6 Werte. Bei
`snr_estimate=5.0` (clamped 5) ergibt das Reports `0, 2, 4, 6, 8, 10`.

**V2-Frage:** Ist die Schrittweite `2` und das Fenster `±5 dB` sinnvoll? 6
Kandidaten zu korrelieren kostet Zeit — relevant fürs Echtzeit-Verhalten?
Aktueller Code gibt das vor und der Fix ändert das **nicht**. Gut. Aber
explizit als „nicht im Scope" in V3 markieren damit DeepSeek nicht
versucht den Algorithmus mit-zu-tunen.

---

## L4 — V1 hat versehentlich Format-Frage offengelassen

V1 §3 schlägt vor:
```python
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```

Aber FT8 hat **zwei** legitime 3-Token-Antworten in WAIT_REPORT:
1. **Report:** `OWN THEIR +05` (Standard-WSJT-X-Sequenz)
2. **R-Report:** `OWN THEIR R+05` (Bestätigung mit Report — kommt in der
   nächsten Phase, NICHT WAIT_REPORT)
3. **Grid:** `OWN THEIR JO31` (selten — wenn Gegenstation Grid statt Report
   schickt)

Aus `core/qso_state.py:213-220`:
```python
if msg.is_grid:        # → Grid-Antwort
    ...
elif msg.is_report:    # → Standard-Report
    ...
elif msg.is_r_report:  # → R-Report (nächste Phase)
    ...
```

WAIT_REPORT akzeptiert ALLE DREI. Aber:
- `is_grid`: Gegenstation antwortet **mit ihrem Grid** statt Report. Zwar
  legitim, aber **selten** in laufender QSO-Sequenz. AP-Lite-Sinn: schwacher
  Decode → erwarteter Standardpfad ist Report.
- `is_r_report`: kommt eher im nächsten Slot (nach unserem Report-Send).

**V2-Empfehlung:** Fix beschränkt sich auf **Standard-Report** (`+05`-Format),
weil:
- Höchste Praxis-Häufigkeit (≥ 95% der WAIT_REPORT-Antworten)
- Locator-Variante hätte unbekannten Locator (Code-TODO Z.127 sagt das
  selbst)
- R-Report-Kandidat wäre Premature-Optimization

In V3 explizit als bewusste Scope-Entscheidung dokumentieren.

---

## L5 — V1 hat Compact-Risk übersehen

Mike hat angekündigt: Compact-Zeitpunkt nach Plan-V3, vor Code. Das heißt:
**Plan-V3 muss Code-fertig sein** — alle Diffs, alle Test-Änderungen
explizit. Nach Compact lese ich den persistierten Plan und code direkt.

**V2-Erweiterung Plan-V3:**
- Konkrete Diffs für `core/ap_lite.py` (1 Zeile + 1 Kommentar)
- Konkrete Diffs für `tests/test_ap_lite.py:test_generate_state1_basic`
- Konkrete Diffs für `tests/test_ap_lite_e2e.py` (2 Bug-Doku-Tests umkehren)
- Neuer Test `test_generate_candidates_state1_ft8lib_compatible`
- Erwarteter Test-Count nach Fix: 830 → 831 (+1 neu, 0 entfernt)

---

## L6 — V1 hat Risiko-Bewertung zu schwach

V1 §4 erwähnt „ADIF-Risiko" knapp. V2 präzisiert:

**Risiko-Analyse:**
| Szenario | Vor Fix | Nach Fix |
|---|---|---|
| Sauberer Decode | OK (AP-Lite läuft nicht) | OK (AP-Lite läuft nicht) |
| Schwacher Decode WAIT_REPORT, Gegenstation echt | Rescue scheitert silent | Rescue versucht — bei Score≥0.75 erfolgreich |
| Schwacher Decode WAIT_REPORT, fremde Station auf gleicher Freq | Rescue scheitert silent | Rescue prüft Kandidaten, falls Score≥0.75 → falscher Report |

**Mitigation:** `SCORE_THRESHOLD=0.75` ist der Sicherheitsanker. Tests
zeigen: saubere Buffer erreichen aktuell ~0.42 → Threshold ist eher zu hoch.
Risiko durch Fix ist mathematisch sehr niedrig (Threshold-Übertreffung
braucht echtes Signal-Match).

**Field-Test-Pflicht post-Kur:** Beobachten dass Rescue-Rate steigt UND
keine offensichtlich falschen Reports im Log landen. Bei Auffälligkeiten
`AP_LITE_ENABLED=False` als Notbremse.

---

## L7 — V1 hat HISTORY/Doku-Pflicht nicht erwähnt

Schritt 6 des Skills (HISTORY+HANDOFF+CLAUDE+Memory updaten) ist Pflicht.
V3 muss das in Implementations-Reihenfolge einplanen — kein „danach noch
Doku" als optional.

---

## L8 — V1 hat Lessons-Learned nicht eingeplant

Skill verlangt 3 Fragen am Ende (was war überraschend, anders machen,
welches Memory). Plan-V3 muss das als finalen Punkt listen.

---

## L9 — Zusammenfassung der V2-Korrekturen für V3

1. **Test-Anpassungen explizit:** `test_generate_state1_basic` muss
   neu geschrieben werden (JO31-Assert raus). 2 E2E-Tests müssen umgekehrt
   werden (Bug-Doku → Erfolg-Doku).
2. **NEU:** `test_generate_candidates_state1_ft8lib_compatible` — verhindert
   Regression auf 4-Token-Format.
3. **Format-Entscheidung explizit:** Nur Standard-Report (`+05`), kein Grid,
   kein R-Report.
4. **Risiko-Analyse-Tabelle** in V3 aufnehmen.
5. **Plan-V3 muss Compact-fest sein:** alle Diffs konkret.
6. **HISTORY/HANDOFF/CLAUDE/Memory-Updates** als Pflicht-Schritt einplanen.
7. **Lessons-Learned** als finaler Pflicht-Schritt.

---

**Workflow-Status:** V2 fertig. Weiter mit R1 (DeepSeek-Reasoner).
