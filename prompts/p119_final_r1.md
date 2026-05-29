# Final-R1 — P119: Phase B (10W-Einpendeln) + Krücke entfernt — IMPLEMENTIERT

Du bist Reviewer für FlexRadio-TX-Code. Die Implementierung ist fertig + alle
2169 Tests grün. Prüfe die committe-reife Umsetzung gegen die V3-Akzeptanz-
kriterien. KEIN Code generieren — nur Findings nach Severity (🔴/🟠/🟡/🟢):
Datei · Was · Warum · Vorschlag. Am Ende: PUSH FREIGEBEN / NACHBESSERN.

## V3-Akzeptanzkriterien (was umgesetzt sein soll)
- AC1: Phase B (`_tune_converge_to_target(10)`) + Helper `_wait_with_event_loop`
  + `_kruecken_skalierung` komplett entfernt.
- AC2: SWR-Freeze (`_tune_last_valid_swr = swr_after_match` aus
  `_compute_match_swr`) BLEIBT — Band-Sperre/Sicherheit unberührt (P142/P153/P159).
- AC3: 10W-Stützpunkt-Save (`rf_preset_store.save(..., 10, rf)`) + `_tune_converged_rf`
  raus aus `_tune_post_swr_check`. Der `was_blocked`-Pfad (Band-Freigabe +
  Diversity-Resume) + `auto_tune_done.emit` bleiben.
- AC4: `_apply_rf_preset` fällt bei `load()==None` direkt auf `get_tx_power`.
- AC5: Auto-TUNE-Skip bei Bandwechsel nutzt `has_any_preset(radio, band)`
  statt `has_anchor(watt=10)` — sonst liefe Auto-TUNE bei jedem Bandwechsel.
- AC6: Anzeige „auf 10 W eingeregelt" raus aus beiden TUNE-Dialogen.

## Bekannte bewusste Entscheidung
- `_tune_convergence_cancelled` bleibt als Flag bestehen (wird von den
  Dialog-Cancel-Handlern noch gesetzt, nach Wegfall der Phase-B-Schleife aber
  nicht mehr ausgewertet). Bewertung: harmloser No-op, oder doch entfernen?

## Prüf-Fragen
1. Ist die SWR-Sicherheit (Freeze, Post-Check, Band-Sperre) WIRKLICH unberührt?
   Übersehe ich einen Pfad wo der Wegfall von Phase B die Bewertung kippt?
2. `_tune_post_swr_check`: ist nach Entfernung des Save-Blocks der `is_auto`-
   Signal-Pfad (`rf_logged = "n/a"`, `auto_tune_done.emit`) noch konsistent?
3. Wird `_fwdpwr_samples` noch korrekt geleert (war im Save-Block-Umfeld)?
4. `has_any_preset` — korrekt thread-safe + band-agnostisch? Edge-Case leeres dict.
5. Resttote Variablen/Referenzen die ich übersehen habe?
6. PUSH FREIGEBEN oder NACHBESSERN?

## Der vollständige Diff
Siehe angehängte Datei `p119_diff.txt` (git diff der 4 Kern-Dateien). Die zwei
Dialog-Dateien (dx_tune_dialog/auto_tune_dialog) ändern nur Anzeige-Texte.
