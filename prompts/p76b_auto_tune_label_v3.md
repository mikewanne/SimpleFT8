# P76-B — Auto-TUNE-Dauer-Anzeige UX (V3)

## 1. Ziel

Status-Label im `AutoTuneDialog` so umbauen, dass User keine falsche
Dauer-Erwartung aufbauen. Heute zeigt der Dialog während der ganzen
Pipeline `N / 5 s` (bzw. eingestellte `tune_duration_s`), läuft real
aber 5..13.5 s (worst-case), weil Phase B (Closed-Loop-Convergenz bis
FWDPWR≈10 W) und Post-SWR-Check noch laufen.

Mike-Field-Test 18.05. nach P75: „wesentlich länger als 5 s gedauert".

## 2. Akzeptanzkriterien

- **AC1** Phase 1 (`_elapsed_s ≤ duration_s`) zeigt Soll-Anzeige
  `"ANT1, 10W → {mode} — {elapsed_s} / {duration_s} s · SWR X · FWDPWR Y W"`
  (= heutiges Verhalten, unverändert).
- **AC2** Phase 2 (`_elapsed_s > duration_s`) zeigt Label
  `"ANT1, 10W → {mode} — Leistung wird auf 10 W eingeregelt · {elapsed_s} s · SWR X · FWDPWR Y W"`
  — keine Soll-Anzeige mehr, SWR + FWDPWR bleiben sichtbar.
- **AC3** Phase 2 nutzt einen helleren Akzent-Ton (`color: #DDA`)
  statt `#AAA` — leichter visueller Hinweis dass jetzt etwas anderes
  läuft (R1-F4). Phase 1 bleibt `#AAA`.
- **AC4** Erfolgs-/Fehler-Branch über `auto_tune_done` unverändert;
  bei `success=True` zeigt Label `"✓ TUNE OK — SWR X · FWDPWR Y W"`
  (Style-Reset auf Standard ist nicht zwingend — Label-Text dominiert).
- **AC5** Cancel-Click + Backup-Timeout (`_BACKUP_GRACE_S = 12`)
  unverändert.
- **AC6** Phase-Wechsel geschieht beim Tick `_elapsed_s > duration_s`
  — Edge-Case `duration_s ≤ 0` defensiv via `effective_duration =
  max(1, duration_s)` abgefangen (R1-F1).

## 3. Betroffene Module/Dateien

- `ui/auto_tune_dialog.py:141-155` `_on_tick` — Label-Logik je nach
  Phase + Style-Akzent. ~20 LOC modifiziert.
- `tests/test_p76b_auto_tune_label.py` — NEU, 5 Tests (T1-T5).
- `main.py` — `APP_VERSION` 0.97.62 → 0.97.63.
- `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` — Standard-Update.

## 4. Randbedingungen

- **Threading:** `_on_tick` läuft im GUI-Thread, kein Lock nötig.
- **Hardware:** AutoTuneDialog macht keinen TX selbst. ANT1=TX-Setup
  liegt in `_tune_post_swr_check`-Pfad und ist unverändert.
- **UX:** Phase 1 = User-Setting läuft ehrlich runter. Phase 2 =
  klare Aussage „Leistung wird auf 10 W eingeregelt" + heller
  Akzent-Ton = User versteht Convergenz läuft noch.
- **i18n:** App ist deutsch.
- **Wording:** „Leistung wird auf 10 W eingeregelt" — Mike-freundlich,
  präzise (10 W ist Auto-TUNE-Ziel), kein techy „Power-Convergenz".
- **Edge-Case `duration_s=0`:** Settings clamped 5/10/15 s, aber
  defensiv `max(1, duration_s)` damit kein „X / 0 s"-Anzeige-Glitch.

## 5. Nicht im Scope

- **Mehr-Phasen-Anzeige** (Phase 3 Post-Check separat): KISS.
- **Phasen-Hinweise vor TUNE-Start** (Erklärtext).
- **AutoTuneDialog-Refactor zu State-Machine** (P74-A).
- **`duration_s` Settings-Migration**.
- **Variante B (pure KISS „TUNE läuft · X s")**: bereits in V1 zugunsten
  Hybrid B+ verworfen — Mike will sein Setting sehen.
- **Worst-Case-Obergrenze in Phase 2** („max ~7 s"): false promise
  (R1-F3 abgelehnt).
- **Format-Änderung `· X s`**: marginal (R1-F8 abgelehnt).

## 6. Testbarkeit

`tests/test_p76b_auto_tune_label.py` NEU:

**Mock-Struktur (R1-F6 präzisiert):**
```python
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def _make_dialog_mock(*, duration_s=5, mode="FT8", elapsed_s=0,
                     swr=1.3, fwdpwr=9.5):
    from ui.auto_tune_dialog import AutoTuneDialog
    obj = MagicMock(spec=AutoTuneDialog)
    obj._duration_s = duration_s
    obj._mode = mode
    obj._elapsed_s = elapsed_s
    obj._parent = MagicMock()
    obj._parent.radio = MagicMock()
    obj._parent.radio.last_swr = swr
    obj._parent._fwdpwr_samples = [fwdpwr]
    obj._status_label = MagicMock()
    # _on_tick als gebundene Methode
    obj._on_tick = AutoTuneDialog._on_tick.__get__(obj)
    return obj
```

- **T1** `test_phase1_label_shows_soll_anzeige_within_duration`
  `duration_s=5, _elapsed_s=3` → nach `_on_tick` enthält Label
  `"4 / 5 s"` und `"FT8"` und `"SWR 1.3"` und `"FWDPWR 9.5W"`.
- **T2** `test_phase2_label_drops_soll_anzeige_after_duration`
  `duration_s=5, _elapsed_s=6` → nach `_on_tick` (`_elapsed_s=7`)
  enthält Label `"Leistung wird auf 10 W eingeregelt"` und `"7 s"`
  und NICHT `"/ 5"`. SWR + FWDPWR bleiben sichtbar.
- **T3** `test_phase_transition_at_duration_boundary`
  `duration_s=5, _elapsed_s=4` → Tick → `_elapsed_s=5`: Phase 1
  („5 / 5 s"). `_elapsed_s=5` → Tick → `_elapsed_s=6`: Phase 2.
- **T4** `test_duration_zero_defensive_clamp`
  `duration_s=0, _elapsed_s=0` → Tick → kein Crash, kein „X / 0 s",
  Phase 1 mit Soll 1 oder direkter Phase 2 ist ok — Hauptsache
  Output ist sinnvoll lesbar.
- **T5** `test_auto_tune_done_overrides_phase2_label` (R1-F5)
  `_elapsed_s=8` (Phase 2 aktiv) → `_on_auto_tune_done(True, 1.2,
  9.8)` aufrufen → Label enthält `"✓ TUNE OK"` und `"SWR 1.2"`
  (das Phase-2-Label wurde überschrieben). Timer-Stops müssen
  korrekt gerufen werden.

## 7. KISS-Bewertung

- **Code-Diff:** ~20 LOC in `_on_tick` (if/else nach Phase, Stylesheet-
  Wechsel).
- **Komplexität:** keine — Tick-Counter + duration_s sind bereits da.
- **Risiko:** sehr klein. Reine Label-Anzeige.
- **Variante B+ (Hybrid)** bestätigt — Mike-Wunsch „Setting sehen".

## R1-Findings Bilanz

| Schwere | Finding | Status |
|---|---|---|
| 🟠 F1 | `duration_s=0` Edge-Case | ✅ defensive `max(1, ·)` + T4 |
| 🟡 F2 | Wording „auf 10 W eingeregelt" | ✅ AC2 angepasst |
| ⚪ F3 | „max ~7 s" Hinweis | ❌ abgelehnt — false promise |
| ⚪ F4 | Farb-Akzent Phase 2 | ✅ `#DDA` als heller Hinweis (AC3) |
| 🟠 F5 | Test `auto_tune_done` in Phase 2 | ✅ T5 ergänzt |
| 🟡 F6 | Test-Spec Mock-Struktur | ✅ präzise ausformuliert (Sek. 6) |
| ⚪ F7 | Variante B vs B+ Overengineering | ❌ Mike-Spec, V1 begründet |
| 🟡 F8 | `· X s` Format | ❌ marginal, gewohntes Muster |
