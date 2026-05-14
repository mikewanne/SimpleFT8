# Bundle H Final-R1 Review

Code fertig. Bitte Final-Review.

## Stand

- **Tests:** 1194 → **1205 grün** (+11 Bundle H, V3 prognostizierte ~12)
- **Backup:** `Appsicherungen/2026-05-14_v0.97.24_vor_bundle_h/`
- **APP_VERSION:** 0.97.24 → 0.97.25 (folgt in Doku-Commit)

## Patches

### C1 — `core/mode_recommender.py`

- `recommend_for_hour()` neuer Parameter `allowed_modes:
  tuple[str,...] | None = None`. Bei gesetzt:
  - Ranking nur aus allowed_modes (statt 3 CODE_MODES)
  - Wenn `current_mode not in allowed_modes`: Tolerance-Skip,
    `decision="switch"`, `decision_mode=top1`
  - Daten-Check bleibt: ein allowed_mode mit zu wenig Daten → None
- `HourlyBandpilot.recommend()` Pass-through-Parameter
- Neue Modul-Function `code_mode_to_scoring(decision_mode) -> str`:
  - „diversity_dx" → „dx", sonst „normal"

### C2 — `ui/bandpilot_dialogs.py`

`BandpilotManualDialog`: bei `current=None`:
- ● -Marker nicht setzen (Vergleich mode_code == None scheitert eh)
- Hint-Label NICHT erzeugen (verwirrt sonst „● = aktueller Modus
  (Normal)" obwohl Normal nicht im Ranking ist)

### C3 — `ui/mw_radio.py`

**`_show_diversity_choice_dialog(intro_text: str) -> str | None`**:
- Extrahiert aus inline-Dialog Z.578-633
- intro_text als Parameter (dynamisch je Bandpilot-Status)
- R1-S1: WA_DeleteOnClose

**`_on_rx_mode_changed("diversity")` Refactor:**
Inline-Dialog ersetzt durch bp_mode-Dispatch:
```python
elif mode == "diversity":
    bp_mode = ...
    rec = self._bandpilot.recommend(
        band, utc_hour, current_mode="normal",
        allowed_modes=("diversity_normal", "diversity_dx"),
    ) if bp_mode in ("auto", "manual") else None
    # defensive no_change-Fallback
    if rec is not None and rec.get("decision") == "no_change":
        rec = None
    if bp_mode == "auto" and rec is not None:
        scoring = code_mode_to_scoring(rec["decision_mode"])
        self._show_bandpilot_auto_toast(...)
    elif bp_mode == "manual" and rec is not None:
        chosen = self._show_bandpilot_manual_dialog(..., current=None)
        if chosen is None: ...abort
        scoring = code_mode_to_scoring(chosen)
    else:
        intro_text = "Nicht genug Daten ..." if bp_mode in ("auto","manual")
                     else "Welchen Modus verwenden?"
        scoring = self._show_diversity_choice_dialog(intro_text)
        if scoring is None: ...abort
    self._activate_diversity_with_scoring(scoring)
```

### C4 — `tests/test_bundle_h.py` NEU (11 Tests)

- T1a/b/c: `recommend_for_hour` mit allowed_modes (ECHTE Logik,
  synthetisches summary_24h, kein Mock — Anti-Mock-Pattern erfüllt)
- T2a/b/c/d: `code_mode_to_scoring` Mapping (4 Fälle)
- T9: BandpilotAutoToast mit 2-elementigem Ranking (kein Crash)
- T8a/b: ManualDialog Hint bei current=None vs current=set
- T10: `decision="switch"` IMMER bei H-Pfad (current nie in allowed)

## R1-Findings Status

- **K1 (Auto+DXTuneDialog UX-Race):** TEILWEISE übernommen mit
  Begründung. R1 wollte `_enable_diversity` direkt ohne
  `_check_diversity_preset`. **Position V3:** Mike's Spec „kein
  Dialog" meinte den **Wahl-Dialog** (Std/DX), NICHT den **Mess-
  Dialog** (DXTuneDialog ist funktional nötig wenn Gain stale —
  ohne Mess hardware-unausgewogen). DXTuneDialog ist konsistent zur
  Spec, Toast kommt VOR Mess-Dialog. **Akzeptabel?**
- **S1 (WA_DeleteOnClose):** ÜBERNOMMEN in
  `_show_diversity_choice_dialog`
- **S2 (Integration-Test echter recommend_for_hour):** ÜBERNOMMEN —
  T1-Suite mit synthetischem summary_24h, KEIN MagicMock
- **S3 (no_change-Fallback):** ÜBERNOMMEN (`if rec.decision ==
  "no_change": rec = None`)

## Bitte Final-R1-Antwort

1. „Push freigegeben" oder „Re-Review"?
2. K1-TEILWEISE-Übernahme-Begründung (DXTuneDialog ist Mess-, kein
   Wahl-Dialog) akzeptabel?
3. Anti-Pattern eingeschlichen?
