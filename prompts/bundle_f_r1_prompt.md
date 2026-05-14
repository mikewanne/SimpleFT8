# DeepSeek-R1 Review — Bundle F (SimpleFT8 v0.97.22 → v0.97.23)

## Kontext

SimpleFT8 ist eine FT8/FT4/FT2-Funkdesktop-App für FlexRadio (PySide6
+ Python). Mike (Single-User, Hobbyfunker) hat heute morgen
Field-Test gemacht und 3 Bugs gemeldet nach Bundle E (TX-Slot-Lock
Refactor) und Bundle D (UI-Tweaks):

1. **OMNI CQ sendet nicht** mehr (KRITISCH — Feature komplett tot)
2. **Doppelter Slot-Fortschrittsbalken** sichtbar (großen entfernen,
   kleinen behalten)
3. **Magenta-Farbe** für Odd-Slot ist „rosa, nix funker-like" — soll
   Orange werden

## Diagnose Bug 1 (OMNI tot)

P34-Stufe2 gestern Nachmittag (v0.97.19) hat aus
`core/diversity.py` die `_phase`-State-Machine + `phase`-Property
komplett entfernt (Mike-Spec „Statik-Pipeline raus, nur noch dynamische
Antennen-Anpassung").

Aber `core/omni_cq.py:231-233` greift noch darauf zu:

```python
# V2-L12: kein Senden waehrend Diversity-Mess-Phase
if self._diversity.phase != "operate":
    return
```

`self._diversity.phase` wirft AttributeError (verifiziert mit
live Python-Check). Qt-Slot `on_cycle_start` ist `@Slot(int, bool)` —
Qt fängt Exceptions silently ab → kein TX, kein Log.

**Warum Tests grün waren:** 4 Test-Files setzen
`diversity.phase = "operate"` als MagicMock-Attribute auf einem Fake-
Diversity:
- `tests/test_omni_cq_signal.py:33,40`
- `tests/test_p23_omni_counter.py:37,47`
- `tests/test_p45_omni_stats_guard.py:64`
- `tests/test_p34_elif_chain_intact.py:34`

→ Memory-Lesson `feedback_test_critical_path_not_mock.md` voll
zutreffend (Mike 09.05.2026: „Tests dürfen den kritischen Pfad nicht
wegmocken.")

**Mein Plan-V2 (Anhang `bundle_f_v2.md`):**
- Phase-Check ersatzlos entfernen
- Test-Mocks bereinigen
- Bug-Schutz-Test: `DiversityController` darf KEIN `phase`-Attribut
  haben (sonst Regression)

## Diagnose Bug 2 (Doppel-Balken)

Bundle D (v0.97.21, gestern Abend) hat einen neuen Slot-Progress-Bar
(`_slot_progress_bar` QProgressBar 80×14 px) in der Statusbar
hinzugefügt. Der existierende große `cycle_bar` (QLabel mit Unicode-
Block-Zeichen + Sekunden-Text) im STATUS-Block der QSO-Card wurde NICHT
mit-entfernt.

**Plan:** `cycle_bar` komplett raus (Definition + Alias + Update-
Methode + Caller in `mw_cycle.py:519`).

## Diagnose Bug 3 (Farbe)

`ui/main_window.py:500` (Initial-Style) und `:1269` (Update-Code):
```python
chunk = "#00CCFF" if is_even else "#FF66CC"  # cyan / magenta
```

`#FF66CC` ist Magenta/Rosa. Mike will Orange.

**Plan:** `#FF66CC` → `#FFAA00` (Standard-Orange). Tooltip + Kommentar
+ Docstring konsistent mitziehen.

## Bitte um R1-Review

Verbindlich V1→V2→R1→V3-Workflow (Mike-Pflicht bei nicht-trivialen
Änderungen, siehe CLAUDE.md). Anlage:
- `bundle_f_v1.md` — initialer Plan
- `bundle_f_v2.md` — Self-Review mit Findings L1-L10
- `core/omni_cq.py` (227 LOC)
- `core/diversity.py` (Source ohne phase)
- `ui/main_window.py` (Statusbar-Bar Definition + Update)
- `ui/control_panel.py` (cycle_bar Definition + Update)
- `ui/mw_cycle.py` (cycle_bar Caller)
- `tests/test_omni_cq_signal.py` (Test-Mocks die phase setzen)

## Konkrete R1-Fragen

**R1-Q1 (DXTuneDialog-Race, KRITISCH):**
Wenn ich Phase-Check komplett raus nehme, läuft OMNI während
Gain-Messung (DXTuneDialog) weiter? Memory `project_lock_audit_pending.md`
sagt: `_gain_measure_locked`-Flag blockiert Band/Mode/RX-Mode-Wechsel,
aber NICHT direkt OMNI-Slot-Tick. Sollte ich vorsichtshalber einen
Schutz einbauen wie:
```python
if getattr(self._diversity, 'is_measuring', lambda: False)():
    return
```
…oder ist das Overengineering (KISS-Argument: DXTuneDialog ist modal,
User klickt OMNI nicht währenddessen)?

**R1-Q2 (Test-Cleanup-Vollständigkeit):**
Sind die 4 Test-Files in V2 vollständig oder gibt es weitere Stellen
wo `diversity.phase`-Mocks gesetzt werden? Ich habe gegrept aber R1
prüft bitte unabhängig.

**R1-Q3 (Cycle_bar Visual-Regression):**
`cycle_bar` ist ein QLabel mit Background-Styling im STATUS-Block der
QSO-Card. Wenn ich es ersatzlos entferne: gibt es Layout-Side-Effects
die ich übersehe? (Spacing, MinSize, Alignment-Bug?)

**R1-Q4 (Orange-Ton):**
`#FFAA00` ist mein Default. Alternativen `#FF8800` (wärmer rötlich),
`#FFB000` (etwas gelblicher). Mike sagt nur „Orange". Visuell soll
es als Pendant zu Cyan `#00CCFF` funktionieren — gut sichtbar auf
dunklem Hintergrund (`#1a1a1a`).

**R1-Q5 (Test-Mock-Pattern):**
Memory-Lesson `feedback_test_critical_path_not_mock.md` ist von
09.05.2026. Bundle F ist ein WEITERES Beispiel desselben Anti-Patterns
(Test mockt weg was Test prüfen sollte). Soll ich die Memory-Datei
erweitern oder eine separate `feedback_partial_fix_diversity_phase.md`
anlegen?

**R1-Q6 (Commit-Aufteilung):**
V1 schlägt 7 atomare Commits vor (C1-C7). Ist die Aufteilung sinnvoll
oder Overengineering bei diesem Bundle?

**R1-Q7 (Field-Test-Liste):**
Field-Test V1 F1-F5 ist OK oder zu dünn? Mike testet jede Stelle die
ich anfasse — was würdest du als R1 zusätzlich testen?

**R1-Q8 (Bug-Klasse-Schutz):**
Bundle F ist die 2. Iteration des „P34-Stufe2-Partial-Fix-Bug-Klasse"
(P40 war 1. Iteration mit `current_ant`-Aufrufern). Sollte ich einen
generischen Regression-Test bauen der sich nicht nur gegen `phase`,
sondern gegen weitere Partial-Fix-Klassen schützt? Wenn ja: was
genau testen?

## Bitte als R1 antworten

- Score 1-10 für V2-Qualität
- Findings: KRITISCH / SOLLTE / KÖNNTE / KLAERUNGSFRAGE
- Push-Empfehlung: „Push freigegeben" oder „Re-Review nötig"
- Antworten auf R1-Q1 bis R1-Q8 (kurz und konkret)
