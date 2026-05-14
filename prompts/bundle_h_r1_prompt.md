# DeepSeek-R1 Review — Bundle H (Bandpilot-Aware Diversity-Klick)

## Kontext

SimpleFT8 (Bundle G heute morgen erledigt — Diversity Std↔DX Toggle bei
2. Div-Klick). Bundle H löst orthogonalen Pfad: Normal → DIVERSITY-Klick.

Heute zeigt `mw_radio.py:578-633` inline-Dialog „Diversity Standard /
DX / Abbruch" UNABHÄNGIG vom Bandpilot-Modus.

Mike-Wunsch (Beobachtung):

| Bandpilot | Daten | Verhalten |
|---|---|---|
| off | egal | Dialog wie heute |
| auto | genug | **kein Dialog** — Bandpilot wählt + Toast (6s, 2-er Ranking, Trophäen) |
| auto | zu wenig | Dialog dynamisch „Nicht genug Daten — bitte wählen" |
| manual | genug | Manual-Dialog 2 Buttons Std/DX |
| manual | zu wenig | Dialog wie off+Mangel-Text |

## Architektur-Skizze (V2)

1. `core/mode_recommender.py::recommend_for_hour(..., allowed_modes=None)`
   neuer Parameter. Bei `allowed_modes` gesetzt + current_mode NOT in
   allowed_modes → Tolerance-Skip + decision="switch", Top-1 aus
   allowed_modes-Subset.
2. `core/mode_recommender.py::code_mode_to_scoring(decision_mode) -> str`
   neue Modul-Function (diversity_normal → "normal", diversity_dx → "dx").
3. `ui/mw_radio.py::_show_diversity_choice_dialog(intro_text) -> str|None`
   extrahiert aus inline-Dialog Z.578-633. Returnt "normal"/"dx"/None.
4. `ui/mw_radio.py::_on_rx_mode_changed("diversity")` Refactor mit
   bp_mode-Dispatch.
5. `BandpilotManualDialog` unverändert (ranking-len-agnostisch), aber
   Hint Z.195 anpassen bei `current=None` (H-Pfad).

## R1-Fragen

**R1-Q1 (recommend_for_hour API-Erweiterung):**
`allowed_modes=None` Default + Spezial-Pfad bei `current not in
allowed_modes`: Tolerance-Skip, decision="switch". Sauber oder besser
separate API `recommend_top_of(allowed_modes)`?

**R1-Q2 (Inline-Dialog-Extraktion):**
`_show_diversity_choice_dialog(intro_text)` mit dynamischem
QLabel-setText. Modal-exec(). Memory-Leak bei mehrfachem Open/Close?
WA_DeleteOnClose nötig?

**R1-Q3 (Test-Strategie):**
- Echter `HourlyBandpilot` braucht `~/.simpleft8/bandpilot_hourly.json`
  + `statistics/` — viel Setup
- MagicMock für `_bandpilot.recommend()` ist pragma
- Memory-Lesson `feedback_test_critical_path_not_mock.md`: kritischer
  Pfad ist `_on_rx_mode_changed`-Routing, NICHT `recommend()` selbst
  → MagicMock für `_bandpilot` ist OK, kritischer Pfad bleibt echt
- Aber: 1 Test mit ECHTEM `recommend_for_hour` + Test-Summary-Dict für
  `allowed_modes`-Logik?

**R1-Q4 (Bundle H Bug-Schutz-Test):**
Bundle F+G hatten Anti-Mock-Pattern-Tests (echtes Objekt um Re-Regression
zu schützen). Bundle H? Was wäre der „kritische Pfad" der gemockt
werden könnte?

**R1-Q5 (Edge-Cases):**
- DXTuneDialog läuft → Bundle H blockiert via `_gain_measure_locked`?
- OMNI-CQ aktiv (sollte heute eh nicht — Normal-Modus heißt Easter-Egg
  ist aus, btn_omni_cq versteckt) → bei H-Pfad relevant?
- Bandpilot returns rec mit decision_mode = current_mode (no_change)
  — kann bei allowed_modes-Pfad NICHT vorkommen weil current=normal
  niemals in allowed_modes ∈ (div_normal, div_dx)?

**R1-Q6 (UX-Detail):**
Bei `auto + genug Daten` Mike will Toast 6s zeigen. Im aktuellen Code
`_show_bandpilot_auto_toast` läuft VOR `_set_rx_mode_direct`. Bei H-
Pfad ruft `_activate_diversity_with_scoring(scoring)` Cache-Dispatch
auf → ggf. DXTuneDialog. Reihenfolge: Toast erst, dann
DXTuneDialog (User sieht Toast 6s, dann Dialog) — OK?

**R1-Q7 (Sonstiges):**
Übersehe ich Pitfalls? Compact-Sicherung?

## Score 1-10 + KRITISCH/SOLLTE/KÖNNTE + Push-Empfehlung.
