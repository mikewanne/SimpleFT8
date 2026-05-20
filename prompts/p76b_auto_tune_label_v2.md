Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P76-B — Auto-TUNE-Dauer-Anzeige UX (V2)

## 1. Ziel

Status-Label im `AutoTuneDialog` so umbauen, dass User keine falsche
Dauer-Erwartung mehr aufbauen. Heute zeigt der Dialog während der
ganzen Pipeline `N / 5 s` (bzw. eingestellte `tune_duration_s`), läuft
real aber 5..13.5 s (worst-case) weiter, weil Phase B (Closed-Loop-
Convergenz bis FWDPWR≈10 W) und Post-SWR-Check noch laufen.

Mike-Field-Test 18.05. nach P75: „wesentlich länger als 5 s gedauert".

## 2. Akzeptanzkriterien

- **AC1** Phase 1 (`_elapsed_s ≤ duration_s`) zeigt Soll-Anzeige
  `"ANT1, 10W → {mode} — {elapsed_s} / {duration_s} s · SWR X · FWDPWR Y W"`
  (= heutiges Verhalten, unverändert).
- **AC2** Phase 2 (`_elapsed_s > duration_s`) zeigt Label
  `"ANT1, 10W → {mode} — Leistung wird angepasst · {elapsed_s} s · SWR X · FWDPWR Y W"`
  — keine Soll-Anzeige mehr, SWR + FWDPWR bleiben sichtbar.
- **AC3** Erfolgs-/Fehler-Branch über `auto_tune_done` unverändert.
- **AC4** Cancel-Click verhält sich wie heute.
- **AC5** Backup-Timeout (`_BACKUP_GRACE_S = 12`) unverändert.
- **AC6** Wechsel von Phase 1 zu Phase 2 geschieht genau bei
  `_elapsed_s > duration_s` (also frühestens beim Tick `_elapsed_s = duration_s + 1`).

## 3. Betroffene Module/Dateien

- `ui/auto_tune_dialog.py:141-155` `_on_tick` — Label-Logik je nach
  Phase. ~15 LOC modifiziert.
- `tests/test_p76b_auto_tune_label.py` — NEU, 4 Tests.
- `main.py` — `APP_VERSION` 0.97.62 → 0.97.63.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` — Standard-Update.

## 4. Randbedingungen

- **Threading:** `_on_tick` läuft im GUI-Thread, kein Lock nötig.
- **Hardware:** AutoTuneDialog macht keinen TX selbst. ANT1=TX-Setup
  liegt in `_tune_post_swr_check`-Pfad und ist unverändert.
- **UX-Konsistenz:** Mike sieht in Phase 1 sein User-Setting ehrlich
  runterlaufen, in Phase 2 weiß er klar „Convergenz läuft noch" —
  keine falschen Erwartungen mehr.
- **i18n:** App ist deutsch.
- **CLAUDE.md Hardware-Pflicht:** Nicht betroffen.
- **Wording:** "Leistung wird angepasst" (Mike-freundlich, kein
  techy „Power-Convergenz").
- **Tests-Setup:** Mock-Parent braucht `radio.last_swr` (float) und
  `_fwdpwr_samples` (list). Beides existiert real, kann gemockt werden.

## 5. Nicht im Scope

- **Mehr-Phasen-Anzeige** (Phase 3 Post-Check als eigene Phase): nur
  2 s am Ende, wenn `auto_tune_done` kommt läuft eh Erfolgs-Branch.
  KISS.
- **Phasen-Hinweise vor TUNE-Start** (Erklärtext).
- **AutoTuneDialog-Refactor zu State-Machine**: das ist P74-A,
  separater Workflow.
- **`duration_s` Settings-Migration**: unverändert.
- **Icon-Wechsel beim Phase-Wechsel**: Spinner läuft eh durch.
- **Variante B (pure KISS „TUNE läuft · X s")**: in V1 verworfen
  zugunsten Variante B+, da Mike sein Setting sehen will. V2 wird
  diese Diskussion NICHT erneut führen.

## 6. Testbarkeit

`tests/test_p76b_auto_tune_label.py` NEU:

- **T1** `test_phase1_label_shows_soll_anzeige_within_duration`
  Setup `duration_s=5`, `_elapsed_s=3` (vorbelegt vor `_on_tick`),
  nach `_on_tick` enthält Label "4 / 5 s" (elapsed wird +1 inkrementiert).
- **T2** `test_phase2_label_drops_soll_anzeige_after_duration`
  Setup `duration_s=5`, `_elapsed_s=6` (vor `_on_tick`).
  Nach `_on_tick` (`_elapsed_s=7`): Label enthält
  "Leistung wird angepasst" und NICHT "/ 5".
- **T3** `test_phase_transition_at_duration_boundary`
  `_elapsed_s=4` → nach `_on_tick` `_elapsed_s=5`, zeigt noch
  Phase 1 ("5 / 5 s"). `_elapsed_s=5` → nach `_on_tick` `_elapsed_s=6`,
  zeigt Phase 2.
- **T4** `test_live_values_shown_in_both_phases`
  `radio.last_swr=1.3`, `_fwdpwr_samples=[9.5]`. Phase 1 + Phase 2
  Label enthält "SWR 1.3" und "FWDPWR 9.5W".

Tests verwenden minimalen `MagicMock(spec=AutoTuneDialog)` analog
Bundle-G Pattern. Bind `_on_tick` an Mock via `__get__(obj)`.

## 7. KISS-Bewertung

- **Code-Diff:** ~15 LOC in `_on_tick` (if/else nach Phase).
- **Komplexität:** keine — Tick-Counter (`_elapsed_s`) und
  `duration_s` (Parameter) sind bereits Instanz-Variablen.
- **Risiko:** sehr klein. Reine Label-Anzeige.
- **Variante B+ (Hybrid)** statt Variante B (pure KISS) gewählt, weil
  Mike laut TODO-Eintrag explizit sein Setting wiedererkennen will.

## Was prüfen

1. Habe ich Edge-Cases übersehen — z.B. `duration_s=0`,
   `_elapsed_s=0`, was wenn User schnell auf Cancel klickt vor dem
   ersten Tick?
2. Ist das Wording „Leistung wird angepasst" verständlich für Hobby-
   Funker oder zu vage? Alternativen: „Leistung wird auf 10 W
   eingeregelt"; „Sender stellt sich ein"; „Power-Match läuft".
3. Sollte Phase 2 doch eine Worst-Case-Obergrenze andeuten
   (z.B. „max ~7 s")? Pro: Orientierung. Con: false promise wenn
   doch länger.
4. Soll Phase 1 visuell vom Phase 2 unterscheidbar sein
   (z.B. anderer Akzent-Farbton im Label)? Oder genügt der Text?
5. Sind die Tests AC-deckend, oder fehlt eine wichtige Annahme
   (z.B. dass `auto_tune_done` zwischendrin kommt und das Label
   überschreibt)?
6. Bei Backup-Timeout in Phase 2 → Label switched normalerweise
   auf Fehler-Anzeige via `_on_auto_tune_done(False, 0, 0)`.
   Habe ich da einen Test, der ein Race-Free-Verhalten sichert?
7. KISS-Sicht: lohnt sich der Phase-Wechsel überhaupt, oder ist
   Variante B (pure KISS) doch der richtige Hobby-Tool-Ansatz?
