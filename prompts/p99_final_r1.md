# Final-R1 — P99 committeter Code-Review

Du hast schon das R1-Pre-Code-Review gemacht: gemeinsamer Counter +
Inkrement-VOR-send + Standard-Cleanup empfohlen, alle Findings sind
im Code drin (Commit 452cf18).

Schau dir jetzt das tatsächlich committeten Code an und sage ob's
sauber sitzt oder nachgebessert werden muss.

## Was committet ist

`core/qso_state.py:662-735` — WAIT_RR73-Branch in `on_message_received`.

3 Pfade gegen gemeinsamen `rr73_retries`-Counter gecappt:

- `is_r_report` (Z.679): `rr73_retries += 1` → wenn `> MAX_RR73_RETRIES` →
  TIMEOUT (mit `_dbg.log` + `_set_state(TIMEOUT)` + `qso_timeout.emit` +
  `_resume_cq_if_needed`). Sonst alter Pfad (`their_snr` + advance).

- `is_report` (Z.693): dito + retry-Send mit `R{_last_snr:+03d}`.

- `is_grid` (Z.713): dito + retry-Send mit `{_last_snr:+03d}` (kein R-Prefix).

`is_rr73 or is_73` (Z.663) UNVERÄNDERT — QSO erfolgreich, Counter
explizit nicht angefasst.

## Tests `tests/test_p99_wait_rr73_message_cap.py`

5 Tests mit echten FT8Message-Instanzen (kein Mock). Alle grün.
Gesamt 1756 → 1761.

## Was du prüfen sollst

1. **Cap-Check-Reihenfolge:** `rr73_retries += 1` ZUERST, dann
   `if > MAX_RR73_RETRIES: TIMEOUT-Pfad`. Korrekt? Pattern konsistent
   mit Z.430-443 (Decoder-Pfad)?

2. **Counter-Sharing mit Decoder-Pfad:** Wenn `on_decoder_finished`
   in einem Slot bei `timeout_cycles == 1` den Counter inkrementiert
   und im gleichen Slot (oder kurz danach) eine Message kommt — gibt's
   ein Doppel-Inkrement-Risiko? Mein R1-Pre-Code sagte nein (Decoder
   läuft nach Messages). Nochmal verifizieren?

3. **TIMEOUT-Cleanup-Vollständigkeit:** `_set_state(TIMEOUT)` →
   `_resume_cq_if_needed()` schaltet im Solo-Mode sofort TIMEOUT →
   IDLE. Daher prüfen Tests `qso_timeout.emit` statt `state==TIMEOUT`.
   Reicht das oder muss noch was anderes aufgeräumt werden
   (z.B. `their_snr`, `_pending_*`)?

4. **`_dbg.log`-Format:** Format-String macht das gleiche Pattern wie
   Z.440? Konsistent?

5. **Edge-Case Counter-Vorhin-Zustand:** Wenn `rr73_retries` bereits
   durch Decoder-Pfad auf 5 ist und eine valide R-Report kommt → wir
   inkrementieren auf 6, TIMEOUT, kein RR73-Send. Mike-Spec sagt OK
   (QSO eh kaputt). Hast du noch Bedenken?

6. **Code-Komment-Block:** ist verständlich? Hinweis auf akzeptiertes
   Risiko drin?

7. **Tests T1-T5:** decken alle Pfade ab. Übersehe ich einen Edge-Case?

8. **Sonstiges:** ist die Lücke wirklich zu? Gibt es einen 4. Vektor
   (z.B. `msg.is_cq` in WAIT_RR73 — kommt nicht vor weil Caller-Check
   davor greift)?

## Format

Sei knapp. Severity, Datei:Zeile, Was, Vorschlag. Wenn alles passt:
„PUSH FREIGEGEBEN". Wenn nicht: konkret nachbessern.
