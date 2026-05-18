# P76-C Marker bei TUNE-bad — V3 (nach R1-V4-pro)

**Status:** R1 freigegeben, alle Findings adressiert.

## R1-Findings & Aktion

- F01-F06 ⚪ Architektur/Race/Hardware/Regression: alle uebernommen
- **F07 🟡** Kommentar Z.365 korrigieren — in Code-Block eingebaut
- **F08 🟡** CLAUDE.md AC7-Doku anpassen — wird im Doku-Update gemacht
- F09 ⚪ Text-Varianten OK
- F10 🟡 AutoTuneDialog indirekt — KISS-akzeptiert
- F11 ⚪ 10 Tests reichen, konkrete Faelle uebernommen

## Finaler Code (R1-direkt-vorgeschlagen)

`ui/mw_tx.py` else-Branch (ab Z.364):

```python
else:
    # P76-C (v0.97.50): TUNE-bad setzt Band-Marker proaktiv. Vorher
    # wurde Marker nur vom P53-Watchdog beim TX-Versuch gesetzt — User
    # konnte CQ klicken obwohl Tuner-Match fehlschlug.
    tuner = self.settings.get("tuner_present", True)
    if tuner:
        self._swr_blocked_bands.add(band)

    if is_auto and dlg is not None:
        # P71: DONE FAIL swr_bad-Log
        print(f"[P54a] DONE FAIL reason=swr_bad "
              f"band={self.settings.band} mode={self.settings.mode} "
              f"swr={swr_now:.1f} limit={swr_limit:.1f}")
        dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
    else:
        # P75 (v0.97.48): QMessageBox raus, rote Zeile im Live-Log.
        # P76-C (v0.97.50): Text variiert mit Marker-State.
        if tuner:
            self.qso_panel.add_info(
                f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > "
                f"Limit {swr_limit:.1f}. Manueller TUNE zum Freischalten "
                f"nach Antennen-Check."
            )
        else:
            self.qso_panel.add_info(
                f"⚠ Tuner konnte nicht matchen — SWR {swr_now:.1f} > "
                f"Limit {swr_limit:.1f}. Antenne pruefen oder TUNE wiederholen."
            )
```

## Tests T1-T10 (R1-bestaetigt)

1. **T1** Manueller TUNE-bad mit Tuner → Band in `_swr_blocked_bands`
2. **T2** Auto-Tune-bad mit Tuner → Band in `_swr_blocked_bands`
3. **T3** TUNE-bad ohne Tuner → kein Marker, Watchdog-Text
4. **T4** TUNE-OK nach TUNE-bad → Marker discarded (Regression P63 AC6)
5. **T5** Text mit Tuner enthaelt „Band X gesperrt"
6. **T6** Text ohne Tuner enthaelt „Tuner konnte nicht matchen"
7. **T7** Source-Level: `_swr_blocked_bands.add` im else-Branch
8. **T8** Source-Level: kein Marker-Set im if-Branch (TUNE-OK)
9. **T9** Source-Level: kein `set_tx_antenna` im P76-C-Block (Hardware-Pflicht)
10. **T10** Idempotenz: zweimal TUNE-bad nacheinander → Marker bleibt 1× drin

## Atomare Commits

- **C1** `ui/mw_tx.py` else-Branch Refactor (Marker-Set + Text-Variante)
- **C2** `tests/test_p76c_marker_on_tune_bad.py` NEU
- **C3** `main.py` APP_VERSION 0.97.49 → 0.97.50
- **C4** HISTORY+HANDOFF+CLAUDE+TODO+Memory Update (F08: P63 AC7-Doku)

## Field-Test (nach Code)

- **F1 (Radio):** Limit=1.5, TUNE auf 40m → SWR-bad → CQ-Klick muss SOFORT
  „⚠ CQ blockiert" zeigen, KEIN TX-Start
- **F2 (Radio):** Wie F1 + OMNI-Klick → muss sofort blockiert sein
- **F3 (Radio):** Wie F1 + Auto-Hunt-Klick → muss blockiert sein
- **F4 (Radio):** Wie F1 + manueller TUNE bei niedrigem SWR → Marker geloescht
  → CQ wieder klickbar
- **F5 (Radio):** Wie F1 + Bandwechsel auf 17m → bleibt klickbar
  (40m-Marker bleibt aber, kein Multi-Band-Sperre)
- **F6 (ohne Radio):** Tests gruen

Push pending bis F1-F5.
