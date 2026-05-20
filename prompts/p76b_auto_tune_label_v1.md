# P76-B — Auto-TUNE-Dauer-Anzeige UX (V1)

## 1. Ziel

Status-Label im `AutoTuneDialog` so umbauen, dass User keine falsche
Dauer-Erwartung mehr aufbauen. Heute zeigt der Dialog während der
ganzen Pipeline `N / 5 s` (bzw. eingestellte `tune_duration_s`), läuft
real aber 5..13.5 s (worst-case) weiter, weil Phase B (Closed-Loop-
Convergenz bis FWDPWR≈10 W) und Post-SWR-Check noch laufen.

Mike-Field-Test 18.05. nach P75: „wesentlich länger als 5 s gedauert".

## 2. Akzeptanzkriterien

- **AC1** Phase 1 (TUNE-Match, `duration_s` aus User-Setting) zeigt
  weiterhin Soll-Anzeige `X / N s` — User sieht hier sein eingestelltes
  Tuner-Match-Fenster ehrlich runterlaufen.
- **AC2** Nach Ablauf von `duration_s` wechselt das Label auf
  "Power-Convergenz · X s" — keine falsche Soll-Anzeige mehr, nur
  elapsed-Sekunden.
- **AC3** Wenn `auto_tune_done(success=True)` kommt → Erfolgsanzeige
  unverändert ("✓ TUNE OK — SWR X · FWDPWR Y W") + 800 ms accept.
- **AC4** Wenn `auto_tune_done(success=False)` oder Backup-Timeout →
  Fehleranzeige unverändert.
- **AC5** Bei Cancel-Click reagiert der Dialog wie heute.
- **AC6** Live-Werte (SWR, FWDPWR) bleiben sichtbar in beiden Phasen
  (User sieht Convergenz visuell).
- **AC7** Backup-Timeout-Konstante (`_BACKUP_GRACE_S = 12`) unverändert.

## 3. Betroffene Module/Dateien

- `ui/auto_tune_dialog.py:141-155` `_on_tick` — Label-Logik je nach
  Phase.
- `tests/test_p76b_auto_tune_label.py` — NEU, 4 Tests.
- `main.py` `APP_VERSION` 0.97.62 → 0.97.63.
- HISTORY/HANDOFF/CLAUDE/TODO Standard-Update.

## 4. Randbedingungen

- **Threading:** `_on_tick` läuft im GUI-Thread, kein Lock nötig.
- **Hardware:** AutoTuneDialog macht keinen TX. ANT1=TX-Setup
  unverändert in `_tune_post_swr_check`-Pfad.
- **UX-Konsistenz:** Mike sieht Phase-1-Soll, danach klar dass
  Convergenz unbestimmte Restzeit läuft → keine Verwirrung mehr.
- **i18n:** App ist deutsch, Label deutsch.
- **CLAUDE.md Hardware-Pflicht:** Nicht betroffen.

## 5. Nicht im Scope

- **Mehr-Phasen-Anzeige** (Phase 3 Post-Check separat): Post-Check
  läuft nur 2 s am Ende. Wenn `auto_tune_done` kommt, läuft der
  Dialog ohnehin in den Erfolgs-/Fehler-Pfad. Keine separate Phase
  notwendig — Komplexität ohne Mehrwert (KISS).
- **Dialog-Schließ-Verhalten** unverändert.
- **Phasen-Hinweise vor TUNE-Start** (z.B. Erklärtext).
- **AutoTuneDialog-Refactor zu State-Machine** (das ist P74-A, separater
  Workflow).
- **`duration_s` Settings-Migration**: bleibt unverändert.

## 6. Testbarkeit

`tests/test_p76b_auto_tune_label.py` NEU:

- **T1** `test_phase1_label_shows_soll_anzeige_within_duration`
  Setup `duration_s=5`, `_elapsed_s=3`, `_on_tick` aufrufen. Status-
  Label enthält "3 / 5 s".
- **T2** `test_phase2_label_drops_soll_anzeige_after_duration`
  Setup `duration_s=5`, `_elapsed_s=7`, `_on_tick` aufrufen. Status-
  Label enthält "Power-Convergenz · 7 s" und NICHT "/ 5".
- **T3** `test_phase_transition_at_duration_boundary`
  `_elapsed_s=5` (= duration_s) zeigt noch Phase 1 (5 / 5 s),
  `_elapsed_s=6` zeigt Phase 2.
- **T4** `test_live_values_shown_in_both_phases`
  SWR + FWDPWR sichtbar in Phase 1 + Phase 2.

## 7. KISS-Bewertung

- **Code-Diff:** ~15 LOC in `_on_tick` (if/else nach Phase).
- **Komplexität:** keine — Tick-Counter ist bereits da.
- **Risiko:** sehr klein. Reine Label-Anzeige, keine TUNE-Logik.

## 8. Diskussion-Punkt (für DeepSeek-R1)

**Variante B (pure KISS):** Label durchgehend
`"TUNE läuft · bitte warten · X s"` (kein Soll, einfacher Code).
- Pro: maximal einfach, garantiert keine falsche Erwartung
- Con: Mike sieht keinen Bezug zum User-eingestellten `duration_s`
  („greift mein Setting?")

**Variante B+ (Hybrid, in V1 oben spezifiziert):** Phase-1 Soll-
Anzeige bis `duration_s`, Phase-2 nur elapsed.
- Pro: User sieht Setting bis es abläuft, danach ehrlich „läuft noch"
- Con: Phase-Wechsel-Logik etwas Mehrcode

→ Empfehlung V1: **B+ Hybrid** weil informativer und kaum Mehraufwand.
Bitte R1 bewertet ob B oder B+ besser zum Hobby-Funker-Kontext passt.
