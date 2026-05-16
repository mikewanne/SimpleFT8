# P62 — Bandwechsel→Gain-Messung UX-Übergang

**Session:** 15.05.2026 mittags · APP_VERSION-Ziel 0.97.35 · Tests
1300 → ~1306

## Trigger

Mike-Field-Test P60-F6 15.05. vormittags: Bandwechsel 30m→20m während
Auto-Hunt-TX. Code bricht TX sauber ab (`encoder.abort + ptt_off`), aber
direkt danach startet Gain-Messung mit TUNE = 10W weil 20m noch keinen
Preset hatte. Mike-O-Ton:

> „eigendlich wäre pause sinnvoll? keine ahnung 1 sekunde bis tx auf
> null ist anstatt von 80 auf 10 watt zu gehen?"

Visueller Eindruck: „80W → 10W TUNE" statt sauberes „TX aus → neue
Messung". DeepSeek-V4-pro hat empfohlen P62 für diesen Slot anzugehen
(Niedriges Risiko, reine UI-Timing-Pufferung).

## Code-Pfad-Analyse

```
_on_band_changed (mw_radio.py:376)
  ├── encoder.abort() + radio.ptt_off()      (Z.416-419)
  └── _check_diversity_preset (Z.526)
        ├── gain_status == "fresh" → _enable_diversity (kein Tune, OK)
        └── gain stale/missing → _start_dx_tuning (Z.1247) ← BUG-Stelle
              ├── SICHERHEIT TX-Stop (Z.1326-1335)
              └── radio.tune_on() mit 10W (Z.1345) ← 0ms nach ptt_off
```

Zwischen `ptt_off` (~80W → 0W Übergang im FlexRadio-Hardware-Buffer
~100-300ms) und `tune_on()` mit 10W sind ms. Hardware-RF-Meter springt
visuell sofort von 80W auf 10W ohne sichtbare Nullphase.

## Lösungs-Optionen

### Option A — 1s QTimer.singleShot vor Tune-On (KISS, Mike-Vorschlag)

```python
# _check_diversity_preset Z.1247 (gain stale/missing-Branch)
self._set_gain_measure_lock(True)  # SOFORT sperren
self.statusBar().showMessage(
    "TX gestoppt — Gain-Messung startet in 1s ...", 1500)
QTimer.singleShot(
    1000,
    lambda: self._start_dx_tuning(scoring_mode=gain_scoring)
)
```

**Pro:** 1 Zeile Effekt, Mike sieht „TX aus → Pause → Messung"
**Contra:** Mini-Verzögerung bei Bandwechsel (+1s)

### Option B — Toast „TX aus → Messung in 1s" + Tune-On nach 1s

Wie A, aber mit Toast-Widget statt Statusbar. Mike hat keine Toast-
Infrastruktur außer den 2026-05-13 Toast-Bundle-Widgets in bandpilot_
dialogs.py — Overkill für 1s.

**Verworfen:** Statusbar reicht.

### Option C — Nur Toast, keine Pause

Mike sieht's, aber keine Pause. **Verworfen:** Mike-Spec war explizit
„1 Sekunde Pause".

### V1-Empfehlung: Option A

Mike-Spec-konform, KISS, sicher.

## Scope-Abgrenzung

**Pause GREIFT bei:**
- Bandwechsel mit stale/missing Gain → `_check_diversity_preset` →
  `_start_dx_tuning`-Pfad
- Mode-Wechsel mit stale/missing Gain (gleicher Pfad)

**Pause GREIFT NICHT bei:**
- KALIBRIEREN-Button (`_handle_dx_tuning` Z.1250) — User-Action, weiß was
  er tut, keine Verwirrung möglich
- Bei Gain fresh → `_enable_diversity` direkt (kein Tune)
- TUNE-Only via `_start_tune_only` (z.B. Cache-„Weiter"-Pfad)

**Architektur-Entscheidung:** Pause in `_check_diversity_preset`
EINGEBAUT, nicht in `_start_dx_tuning`. Damit ist die Trennung sauber —
KALIBRIEREN-Button-Pfad ruft direkt `_start_dx_tuning`, der Bandwechsel-
Pfad geht über `_check_diversity_preset`.

## Code-Plan (atomar)

| Commit | Datei | Was |
|---|---|---|
| C1 | `ui/mw_radio.py` | `_check_diversity_preset` stale/missing-Branch: lock+Statusbar+QTimer 1s → `_start_dx_tuning` |
| C2 | `tests/test_p62_bandchange_ux.py` NEU | T1-T4 Source+Behavior-Tests |
| C3 | `main.py` APP_VERSION 0.97.34 → 0.97.35 + Backup |
| C4 | Doku |

## Tests

- **T1** Source-Level: `_check_diversity_preset` enthält
  `QTimer.singleShot` mit `1000` und ruft `_start_dx_tuning` als
  Lambda/Callback (gain stale/missing-Branch)
- **T2** Lock wird SOFORT gesetzt (`_set_gain_measure_lock(True)` VOR
  QTimer-Aufruf) — User kann in der 1s-Pause nichts klicken
- **T3** Statusbar-Hinweis-Text vorhanden (Source-Level)
- **T4** Gain fresh-Branch unverändert (`_enable_diversity` direkt
  gerufen, KEIN QTimer)
- **T5** KALIBRIEREN-Pfad (`_handle_dx_tuning`) ruft `_start_dx_tuning`
  weiterhin direkt OHNE QTimer (Source-Level)

## Hardware-Pflicht ANT1

Keine TX-Antennen-Logik berührt. `radio.tune_on()` läuft weiterhin auf
ANT1 (im FlexRadio-Setter). 1s Pause ändert nur Timing, keine Antennen-
Wahl.

## Risiko-Bewertung

| Risiko | Bewertung |
|---|---|
| 1s zu kurz → noch nicht sichtbar | Niedrig — FlexRadio-RF-Meter ist 300ms-Buffer, nach 1s definitiv auf 0 |
| 1s zu lang → Mike-Annoyance | Niedrig — Bandwechsel ist seltenes Event, 1s vertretbar |
| QTimer-Race bei schnellem Doppel-Bandwechsel | Mittel — `_tune_token` ist nicht vor `_start_dx_tuning` gesetzt. Aber: 1s Pause ist klein genug dass Mike kein Doppel-Bandwechsel macht |
| Lock vor QTimer → User stuck wenn QTimer-Callback fehlt | Niedrig — QTimer.singleShot ist Qt-zuverlässig, kein Drop |
| Test mockt Qt-Timer schwer | Mittel — Test mit Source-Level-grep + Funktional-Mock via QApplication |

## Aus Scope

- Variable Pause-Zeit konfigurierbar machen (KISS, 1s fest)
- Pause bei Cache-„Weiter"-Pfad (`_start_tune_only`) — eigener Use-Case,
  nicht Mike-Spec
- Pause beim Mode-Wechsel von Mode A auf Mode B mit Gain-Reset —
  greift implizit via `_check_diversity_preset`-Aufruf

## Field-Test-Punkte für Mike

| F# | Was prüfen |
|---|---|
| F1 | Bandwechsel auf NEUES Band ohne Gain-Preset → 1s Pause „TX gestoppt — Gain-Messung startet in 1s..." sichtbar, dann TUNE |
| F2 | Bandwechsel auf Band MIT Gain-Preset → KEINE Pause, direkt Diversity aktiv |
| F3 | KALIBRIEREN-Button → KEINE Pause (User-Action) |
| F4 | RF-Meter geht zwischen 80W (alt) und 10W (TUNE) durch 0W sichtbar |
| F5 | Während der 1s Pause: alle Buttons gesperrt (User kann nichts triggern) |
