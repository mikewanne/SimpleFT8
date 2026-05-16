# P62 V2 — Self-Review

## F1 — Lock-Race bei mehrfachem Bandwechsel (ORANGE)

V1: Lock SOFORT setzen, dann QTimer 1s → `_start_dx_tuning`. Aber: was
passiert wenn User in der 1s erneut Band wechselt?

**Pfad-Analyse:**
- Lock ist True → `_on_band_changed` Z.385 prüft `_gain_measure_locked`
  und IGNORIERT den 2. Bandwechsel (existierender Schutz)
- QTimer-Lambda läuft trotzdem nach 1s → `_start_dx_tuning` für altes
  Band

**Risiko-Bewertung:** Mike-Praxis: schnelles Doppel-Bandwechsel ist
unwahrscheinlich (Bandwechsel ist bewusste Aktion). Plus: existierender
Pipeline-Lock-Schutz greift. KEIN Bug.

**V3-Entscheidung:** Akzeptabel. Aber Sicherheit erhöhen via
`_tune_token`-Pattern (analog `_start_tune_only` Z.1295):

```python
self._set_gain_measure_lock(True)
self._tune_token = object()
_token = self._tune_token
def _deferred_start():
    if self._tune_token is _token:  # Token noch gültig
        self._start_dx_tuning(scoring_mode=gain_scoring)
self.statusBar().showMessage(...)
QTimer.singleShot(1000, _deferred_start)
```

→ Bei externem `_tune_token = None` (Bandwechsel, der Lock umgehen
würde) wird Callback ignoriert.

**Aber:** Lock GREIFT in `_on_band_changed` Z.385 schon. Der Token-
Schutz ist Belt-and-Suspenders.

**V3-Final:** KISS-Lambda OHNE Token-Pattern. Wenn Race auftreten würde,
ist der Pipeline-Lock-Schutz da. Token-Pattern für `_start_tune_only`
ist anders motiviert (3s-TUNE während Mike was klickt).

## F2 — Statusbar-Timeout 1500ms vs 1000ms QTimer (GELB)

V1 Statusbar `showMessage("...", 1500)`. QTimer 1000ms.

**Problem:** wenn Statusbar nach 1500ms gelöscht wird, ist da schon
500ms `_start_dx_tuning` am Laufen — der setzt eigene Statusbar-Message
„TUNEN — 10W auf ANT1 fuer 3s ...".

**Verifikation:** `_start_dx_tuning` Z.1342-1343:
```python
self.statusBar().showMessage(
    f"TUNEN — {tune_power}W auf ANT1 fuer 3s ...", 0)
```

→ Überschreibt die alte Message ohnehin. KEIN Problem.

**V3-Entscheidung:** Statusbar-Timeout 1500ms lassen — kein Schaden,
falls QTimer mal aussetzt sieht User Text trotzdem 500ms länger.

## F3 — KALIBRIEREN-Pfad-Konsistenz prüfen (GELB)

V1 sagt: Pause greift NICHT in KALIBRIEREN. Verifikation:

`_handle_dx_tuning` Z.1250 ruft direkt `self._start_dx_tuning(...)` (Z.1271).
KEIN `_check_diversity_preset` dazwischen. ✓

**T5 (Test) wird das absichern** — Source-Level-Check dass `_handle_dx_tuning`
KEIN QTimer für Tune-Pause hat.

## F4 — `_pending_dx_diversity`-Flag Setzung-Reihenfolge (ORANGE)

V1 zeigt:
```python
gain_scoring = "snr" if scoring == "dx" else "stations"
self._pending_dx_diversity = True
self._pending_diversity_scoring = scoring
self._start_dx_tuning(scoring_mode=gain_scoring)
```

V3-Plan würde das so umstellen:
```python
gain_scoring = "snr" if scoring == "dx" else "stations"
self._pending_dx_diversity = True
self._pending_diversity_scoring = scoring
self._set_gain_measure_lock(True)
self.statusBar().showMessage("TX gestoppt — Gain-Messung startet in 1s ...", 1500)
QTimer.singleShot(1000, lambda: self._start_dx_tuning(scoring_mode=gain_scoring))
```

**Wichtig:** `_pending_dx_diversity = True` und Scoring SOFORT setzen,
BEVOR die 1s startet. Damit sind die States für den deferred Aufruf
korrekt — auch wenn etwas dazwischen passieren würde.

**V3-OK.**

## F5 — gain_scoring Closure-Variable (GELB)

Lambda captured `gain_scoring`. Python-Closure ist by-reference, aber
da `gain_scoring` lokale Funktions-Variable ist und nicht überschrieben
wird, ist Capture safe.

**V3-OK.**

## F6 — Tests — wie testet man QTimer.singleShot? (ORANGE)

Source-Level-Test (T1) prüft Existenz des QTimer-Aufrufs. Aber
Behavior-Test (Pause IST 1000ms, _start_dx_tuning wird WIRKLICH später
gerufen) ist mit Qt-Test-Framework knifflig.

**V3-Lösung:** Hauptsächlich Source-Level-Tests. Plus 1 Funktional-
Test mit `QSignalSpy` oder `monkeypatch` auf `QTimer.singleShot` um
zu verifizieren dass mit `1000` aufgerufen wird.

**V3-Test-Liste finalisiert:**
- T1 Source-Level: `_check_diversity_preset` enthält `QTimer.singleShot`
  mit `1000`
- T2 Source-Level: `_set_gain_measure_lock(True)` kommt VOR
  `QTimer.singleShot` in `_check_diversity_preset`
- T3 Source-Level: Statusbar-Hinweis-Text „TX gestoppt — Gain-Messung
  startet in 1s" enthalten
- T4 Source-Level: gain-fresh-Branch KEIN QTimer (nur direkter
  `_enable_diversity`-Aufruf)
- T5 Source-Level: `_handle_dx_tuning` KEIN QTimer für Tune-Pause
  (gleiche-Datei-Konsistenz)
- T6 Funktional: monkeypatch QTimer.singleShot, ruf
  `_check_diversity_preset(stale-gain-Mock)`, verifiziere
  singleShot wurde mit 1000+Callable aufgerufen

## F7 — Backup vor Code

V1 erwähnt es nicht explizit. Standard-Pattern:
`Appsicherungen/2026-05-15_v0.97.34_vor_p62/`. Ergänzung in C3.

## F8 — Doku-Konsistenz

P62 in TODO/HANDOFF/CLAUDE/HISTORY/Memory updaten. Memory-Datei NEU
`project_p62_bandchange_ux_pause.md`. MEMORY.md Index erweitern.

## V2-Final-Übersicht der Änderungen ggü V1

| V1 | V3 |
|---|---|
| 5 Tests | 6 Tests (T6 Funktional-Test mit monkeypatch hinzu) |
| Lock-Race-Frage offen | F1 analysiert, Token-Pattern verworfen (KISS) |
| Statusbar-Timeout-Mismatch | F2 analysiert, OK |
| Backup-Implizit | F7 explizit |

## V2-Verifikation Code-Stellen

- `ui/mw_radio.py:376-470` _on_band_changed (Bandwechsel-Trigger)
- `ui/mw_radio.py:1213-1248` _check_diversity_preset (Bug-Stelle Z.1247)
- `ui/mw_radio.py:1250-1271` _handle_dx_tuning (KALIBRIEREN-Pfad, soll KEINE Pause)
- `ui/mw_radio.py:1316-1346` _start_dx_tuning (eigentliche Tune-Pipeline)
- `ui/mw_radio.py:385` Pipeline-Lock-Schutz im Bandwechsel (Race-Schutz)

Alle verifiziert. R1 kann starten.
