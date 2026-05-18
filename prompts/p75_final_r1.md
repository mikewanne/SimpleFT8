# P75 — Final-R1 Push-Freigabe-Check

Du bist DeepSeek-V4-pro. Code-Phase fertig. R1-Findings F1-F6 alle
übernommen. Tests **1453 → 1463 grün (+10 P75)**.

## Was wurde umgesetzt

- **C1 (Style):** `ui/control_panel.py` — neuer `_tune_btn_style`-Cluster
  (dezent-gelb inaktiv `rgba(60,50,0,...)`, grün aktiv `rgba(0,150,0,...)`).
- **C2 (Bug + QMessageBox):** `ui/mw_tx.py`:
  - `_tune_stop` Ende ruft `btn_tune.setChecked(False)` mit `blockSignals`
  - SWR-bad-manueller-Pfad: `QMessageBox.warning` → `qso_panel.add_info`
- **C3 (Banner):** `ui/dx_tune_dialog.py` — `prev_tune_swr`-Param,
  Header-Banner mit grünem Hintergrund wenn Wert übergeben.
- **C4 (Pipeline):** `ui/mw_radio.py:_open_dx_tune_dialog` übergibt
  `prev_tune_swr` aus `radio.last_swr` wenn SWR ≤ Limit.
- **C5 (Tests):** `tests/test_p75_button_modal.py` NEU mit 10 Tests.
- **C6:** APP_VERSION 0.97.47 → 0.97.48.

## Aufgabe

Push-Freigabe-Check. Klassifikation 🔴/🟠/🟡/⚪.

**Schwerpunkte:**
1. Hardware-Pflicht: keine ANT2-Setzung in den geänderten Pfaden?
2. Race-Schutz: Token-Guard in `_tune_stop` + blockSignals reichen?
3. F4 Konsequenz: User sieht SWR-bad-Fehler im manuellen TUNE-Pfad
   wirklich (rote Zeile im qso_panel)? Was wenn er gerade auf Logbuch-
   Tab ist und es nicht sieht?
4. F3 Banner-Bedingung: `prev_tune_swr = radio.last_swr if <= limit`
   — was wenn manueller Kalibrieren-Klick OHNE vorausgehenden TUNE?
   Dann ist last_swr evtl. „stale" → wir zeigen ggf. Banner mit
   altem TUNE-Wert.
5. Test-Coverage: reichen 10 Tests?
6. Reverse-Compat: alte Tests in P63/P54-FIX-Test-Files noch grün?

Wenn alles OK: **„PUSH FREIGEGEBEN"**. Sonst konkrete Blocker.

Max 1000 Wörter.

## V3-Spec im Anhang
`prompts/p75_v3_final.md`.
