# P95 — Bundle Final-R1 (v0.97.67 vor Push)

Push-Freigabe ja/nein?

## Was P95 macht

**Feature A:** Rechtsklick auf TUNE-Button → Menü mit 10s/15s/20s.
Override-Pipeline `_on_tune_override(duration_s)` ruft `_tune_start`
mit expliziter Dauer. Setting `tune_duration_s` UNCHANGED. Bei aktiver
TUNE: stop + kein Auto-Restart (Mike-Default).

**Feature B:** Rechtsklick auf log_view im QSO-Panel → Toggle für
Even/Odd-Tag und Antennen-Anzeige. Re-Render aller bestehenden
Einträge via neue `_entries`-SOT-Liste. Persistierung in Settings.

## Architektur-Änderungen

- `ui/control_panel.py`: `_RadioCard` mit neuem `tune_override_requested`-
  Signal + `_on_tune_button_context_menu`. ControlPanel reemittet.
- `ui/mw_tx.py`: `_on_tune_clicked` → ruft `_tune_start(duration_s)`
  (Helper extrahiert). Neuer `_on_tune_override(duration_s)` für die
  Rechtsklick-Pipeline. Hardware-Pipeline (10W FEST, ANT1) lebt jetzt
  exklusiv in `_tune_start`.
- `ui/qso_panel.py`:
  - `_block_timestamps` ersetzt durch `_entries: list[dict]` als SOT.
  - 6 `add_*` Methoden refactored: `_entries.append(...)` +
    `_render_entry(entry)`.
  - Neue `_rerender_all` mit absoluter Scroll-Restore (R1-F2).
  - Neue `_on_log_context_menu` mit Toggle-Actions + Standard-Actions
    (Copy/SelectAll) ownership-sicher via `setParent(None)` (R1-F1).
- `ui/main_window.py`: Settings-Load + Signal-Connect für 2 Visibility-
  Flags. Save-Helper in `mw_qso.py`.

## V2-Findings (eingebaut)

- A-F1: Refactor zu `_tune_start` (kein Side-Channel-State)
- A-F2: Override während TUNE → stop, kein Auto-Restart
- B-F2: `_auto_trim_by_age` arbeitet jetzt auf `_entries`
- B-F4: `_last_omni_tx_even` bei `_rerender_all` zurückgesetzt
- B-F5: 2 separate bool-Keys statt dict (analog rx_panel_hidden_cols)
- B-F8: Entry-Dict-Schema dokumentiert

## R1-Findings (eingebaut)

- R1-F1: Standard-Actions ownership-sicher via `setParent(None)` + `deleteLater`
- R1-F2: Scroll-Position absolut + clamp auf neues max (statt nur at_bottom)

## Tests

- 20 neue P95-Tests in `tests/test_p95_bundle.py` (A-T1..T8, B-T1..T12)
- 6 alte qso_panel_rolling Tests auf neue API umgestellt (waren auf
  `_block_timestamps` basiert)
- 2 alte P63-Tests umgestellt auf `_tune_start` (Pipeline extrahiert)
- **Suite: 1638 → 1658 (+20 P95, alle grün)**

## Bewertungs-Fragen

1. Reichen die 20 Tests die Edge-Cases ab?
2. Re-Render-Performance bei vielen Einträgen (>200)? Theoretisch
   möglich da Mike lange Sessions fährt.
3. R1-F1 Ownership: `act.setParent(None)` vor `menu.addAction(act)` —
   gibt's einen Edge-Case bei Action-Lebenszyklus nach `menu.exec()`?
4. Hardware-Sicherheit Override-Pipeline: `_tune_start` IDENTISCH zu
   `_on_tune_clicked(True)` pre-P95 — 10W FEST + ANT1 verriegelt ✓.
5. Final-Check: missing edge cases? Production-Risiken?
