# Bundle F — V2 (Self-Review)

**Basis:** `bundle_f_v1.md`
**Datum:** 2026-05-14 morgens

## Findings (Self-Review von V1)

### L1 (KRITISCH) — DXTuneDialog-Race klären

V1-Q1: Phase-Check raus → was schützt OMNI gegen TX während Gain-Mess?

**Code-Verifikation `ui/mw_radio.py`:**
- `_gain_measure_locked`-Flag wird bei Gain-Mess gesetzt
- Blockiert Band-/Mode-/RX-Mode-Wechsel
- Blockiert **NICHT** OMNI-Slot-Tick (OMNI läuft im Qt-Slot
  `on_cycle_start` parallel)

**Aktuelle Realität (mit Phase-Check `!= "operate"`):**
- War vorher der Schutz, bevor P34-Stufe2 die Phase rauswarf.
- Seit gestern Nachmittag: Phase fehlt, OMNI startet aber dadurch
  AUCH NICHT (silently) — Test-Mocks waren grün, Live-Code tot.

**Realer DXTuneDialog-Flow:**
1. User klickt KALIBRIEREN oder Bandwechsel `gain=stale` → DXTuneDialog
   wird modal geöffnet
2. Dialog macht selbst Antennen-Switches + sendet eigene Test-Töne
3. OMNI: wenn vor Mess aktiv war, läuft `on_cycle_start` weiter — würde
   während Mess senden wollen → Encoder-Konflikt + Antennen-Switch-
   Konflikt

**Schlussfolgerung:** Ohne Schutz ist Race-Bedingung real. Aber: User
kann OMNI NICHT starten während DXTuneDialog läuft (Dialog modal,
btn_omni_cq nicht klickbar). OMNI vor Mess: praktisch unwahrscheinlich
weil DXTuneDialog meist beim Initial-Setup läuft (vor erstem OMNI).

**R1-Frage:** Brauchen wir Schutz, oder reicht „User klickt OMNI erst
nach Mess-Abschluss"? Pragma-Position: Mike-Setup OMNI-CQ ist ein
Easter-Egg, wird selten genutzt → KISS = Phase-Check raus, kein
Ersatz. Falls Race auftritt: separater Fix wenn empirisch beobachtet.

### L2 — Test-Mocks: MagicMock-Auto-Attr

`test_omni_cq_signal.py:37`: `diversity = MagicMock()`. Ohne explizites
`diversity.phase = "operate"` würde MagicMock `diversity.phase` als
weiteren MagicMock-Sub-Mock zurückgeben → `MagicMock() != "operate"` =
`True` → OMNI bricht ab.

**Konsequenz:** wenn V1-Fix Phase-Check rauswirft, müssen Tests die
`diversity.phase = "operate"` setzen funktionieren nach Cleanup
trotzdem (Setter selbst ist harmlos, kann bleiben wenn Tests grün
bleiben). Aber besser: Setter raus → klarer Schnitt, Tests testen
NICHT mehr ein nicht-existentes Feature.

**Plan-Anpassung:** Phase-Setter-Zeilen aus allen 4 Test-Files
entfernen UND `diversity_phase`-Parameter aus `_make_omni`-Helpers raus.

### L3 — cycle_bar Tests gar nicht vorhanden

V1-Q2 verifiziert: `grep -rn cycle_bar tests/` → KEIN Treffer. Lösch-
Operation ist sauber, keine Test-Anpassung außer V1 erwähntem T-Layout-
Verifikation.

### L4 — Bundle-D Test hat Magenta-Assertion

V1-Q3 verifiziert: `tests/test_bundle_d.py:212`:
```python
assert "#FF66CC" in style, f"Expected magenta (#FF66CC) in style: {style}"
```
**Plan:** Diese Assertion auf `#FFAA00` ändern + Error-Message + Test-
Name anpassen.

### L5 — `update_cycle_bar` Methode-Signatur

V1 sagt `update_cycle_bar` raus. Aber: ist `cycle_bar` möglicherweise
direkt von Drittcode angesprochen? grep — nur eine Stelle in
`mw_cycle.py:519`. Sauber löschbar.

### L6 — Field-Test F5 unrealistisch

V1-F5 „OMNI während Gain-Mess klicken (sollte UI-blockiert sein)" ist
schwer zu reproduzieren weil DXTuneDialog modal — User KANN nicht
klicken. Test verifiziert nichts. Streichen.

**Ersatz F5:** „OMNI startet, dann Bandwechsel zu Band mit
gain=stale" → testet ob OMNI das DXTuneDialog-Opening übersteht.

### L7 — Tooltip + Docstring + Kommentar nicht vergessen

V1 erwähnt mehrere Stellen für Magenta-Replacement:
- Z.486 Kommentar
- Z.495 Tooltip
- Z.500 Initial-Style (Cyan, kein Effekt — kein Fix nötig)
- Z.1253 Docstring
- Z.1269 chunk-Constant + Inline-Kommentar

Alle MÜSSEN konsistent „Orange" sagen, sonst stilistischer Drift.

### L8 — TODO.md / Memory Updates

Nach Fix:
- Memory `feedback_test_critical_path_not_mock.md` ergänzen mit
  diesem Beispiel (OMNI Phase-Check ist 2. Vorfall nach P4.OMNI v0.96.0)
- TODO.md: Bundle F als erledigt eintragen
- HISTORY.md anhängen
- HANDOFF.md updaten
- CLAUDE.md-Header updaten

### L9 — Bug-Schutz-Test gegen P34-Partial-Fix-Klasse

NEU im Plan: Test der `DiversityController` Source-Code grep'd nach
`phase` und sicherstellt dass die Klasse KEIN `phase`-Attribut hat
(verhindert dass jemand das wieder einführt ohne OMNI anzupassen).

```python
def test_diversity_has_no_phase_attribute():
    """T-Bug-Schutz: DiversityController hat KEIN phase-Attribut.

    Falls jemand das wieder einführt, MUSS OMNI mit angepasst werden
    (sonst silent AttributeError im Qt-Slot)."""
    from core.diversity import DiversityController
    from core.timing import FT8Timer
    d = DiversityController(FT8Timer())
    assert not hasattr(d, 'phase'), \
        "DiversityController hat wieder phase-Attribut — OMNI muss " \
        "angepasst werden (siehe Bundle F Lesson)."
```

### L10 — `cycle_bar` Side-Effects

`cycle_bar` ist ein QLabel mit Background-Styling. Entfernen ändert
das Layout: STATUS-Block schrumpft um ~22 px. Mike's Bild zeigt
„unter Status: IDLE | DT" steht der Balken → Mike will den weg. OK,
aber Lock-Test: gibt es Layout-Tests die Höhe asserten? Nein (grep
`status.*height\|cycle.*height` in tests/ → leer).

## Antworten auf V1-Q's

- Q1: KISS, Phase-Check raus, kein Ersatz (R1-Bestätigung erbeten)
- Q2: cycle_bar in Tests: keiner — clean löschen
- Q3: Magenta-Assertion in test_bundle_d.py:212 — auf Orange
- Q4: Orange-Konsistenz: nur _slot_progress_bar (kein anderer
  Magenta-State im Code für Odd-Slot)
- Q5: cycle_bar in Tests: nein
- Q6: APP_VERSION 0.97.22 → 0.97.23 (Bugfix-Bundle)
- Q7: Backup-Name `Appsicherungen/2026-05-14_v0.97.22_vor_bundle_f/`

## Offene R1-Fragen

- R1-Q1: DXTuneDialog-Race — Phase-Check ersatzlos OK oder echter
  Schutz nötig (z.B. `if getattr(self._diversity, '_gain_busy', False)`)?
- R1-Q2: Sind alle 4 Test-Files (`test_omni_cq_signal`, `test_p23_omni_counter`,
  `test_p45_omni_stats_guard`, `test_p34_elif_chain_intact`) ausreichend?
  Gibt es weitere Test-Files mit `diversity.*phase`?
- R1-Q3: Cycle_bar-Entfernung — gibt es Visual-Regressions die ich übersehe?
- R1-Q4: Orange `#FFAA00` vs anderer Orange-Ton (`#FF8800` etwas wärmer,
  `#FFAA00` mit etwas Gelb)? Mike will „Orange" generisch — `#FFAA00`
  ist ein vernünftiges Standard-Orange.
- R1-Q5: Memory-Lesson-Format: soll `feedback_test_critical_path_not_mock.md`
  ergänzt werden oder NEU `feedback_partial_fix_diversity_phase.md`?
- R1-Q6: Test-Bilanz: kann ich +1 Bug-Schutz-Test (L9) + 3-4
  Sanity-Tests einbauen? Erwartung 1179 + ~5 = 1184.
