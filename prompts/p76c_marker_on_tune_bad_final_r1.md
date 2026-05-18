# P76-C Marker bei TUNE-bad — Final-R1 Prompt

Final-Push-Freigabe fuer SimpleFT8 v0.97.50 P76-C (Folge-Fix nach P76-A).

## Was gemacht wurde

**Bug:** Nach P76-A-Fix entdeckte Mike: TUNE-bad logged korrekt „SWR 2.0 > 1.5"
aber CQ blieb klickbar → erst beim TX-Versuch greift P53-Watchdog.

**Fix:** In `_tune_post_swr_check` else-Branch `_swr_blocked_bands.add(band)`
wenn `tuner_present=True`. Marker-Set VOR is_auto-Abzweigung (gilt fuer
manuellen + Auto-Tune-Pfad). Text-Variante: mit Tuner „Band X gesperrt",
ohne Tuner „Tuner konnte nicht matchen".

**Tests:** 1474 → **1484 grün** (+10 P76-C T1-T10). Plus 1 P75-Test-Anpassung
(suchte alten Kommentar „AC7 P63: Marker bleibt rot" → P76-C-Marker).

## R1-V4-pro war schon einverstanden (Push freigegeben, F07+F08 Doku-Hinweise)

Bitte Final-Review:

### Code-Korrektheit
1. Marker-Set passiert VOR is_auto-Abzweigung → beide Pfade konsistent?
2. TUNE-OK-Branch (if) hat weiter `discard(band)` (P63 AC6 Freischaltung)?
3. `tuner_present=False` macht KEIN Marker (P63-Konsistenz mit `_on_swr_alarm`)?

### Hardware-Pflicht
4. Kein `set_tx_antenna` im neuen Block? Beruehrt nur SWR-Marker-State?

### Doku
5. CLAUDE.md sollte AC7-Spec praezisieren (P63 sagte „bleibt rot",
   P76-C ergaenzt „setzt rot").

### Tests
6. 10 Tests reichen (4 functional + 4 Source-Level + Idempotenz + Regression)?

### Push-Empfehlung
7. PUSH FREIGEGEBEN nach Doku-Update?

## Code-Diff (zur Verifikation)

`ui/mw_tx.py` else-Branch (war Z.364-380, jetzt erweitert):

```python
else:
    # P76-C (v0.97.50): TUNE-bad setzt Band-Marker proaktiv.
    # Vorher wurde Marker nur vom P53-Watchdog beim TX-Versuch
    # gesetzt — User konnte CQ klicken obwohl Tuner-Match fehlschlug.
    # Marker-Set VOR is_auto-Abzweigung → konsistent fuer beide
    # Pfade (manuell + Auto-Tune bei Bandwechsel).
    tuner = self.settings.get("tuner_present", True)
    if tuner:
        self._swr_blocked_bands.add(band)

    if is_auto and dlg is not None:
        # P71: DONE FAIL swr_bad-Log
        print(f"[P54a] DONE FAIL reason=swr_bad ...")
        dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
    else:
        # P75 (v0.97.48): QMessageBox raus, rote Zeile im Live-Log.
        # P76-C (v0.97.50): Text variiert je nach Marker-State.
        if tuner:
            self.qso_panel.add_info(
                f"⚠ Band {band} gesperrt — SWR {swr_now:.1f} > "
                f"Limit {swr_limit:.1f}. Manueller TUNE zum "
                f"Freischalten nach Antennen-Check."
            )
        else:
            self.qso_panel.add_info(
                f"⚠ Tuner konnte nicht matchen — SWR {swr_now:.1f} > "
                f"Limit {swr_limit:.1f}. Antenne pruefen oder TUNE "
                f"wiederholen."
            )
```

Bitte Antwort: `PUSH FREIGEGEBEN` oder `ueberarbeiten`.
