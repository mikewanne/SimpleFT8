# P76-C TUNE-bad setzt Band-Marker proaktiv — V1

**Status:** Lücke in P63 — Folge-Bug aus Mike-Field-Test P76-A
**Datum:** 18.05.2026 nach P76-A
**Vorgaenger:** v0.97.49 Tests 1474

---

## Bug-Symptom (Mike-Field-Test 18.05.)

Mike setzt SWR-Limit auf 1.5, macht TUNE auf 40m:
- TUNE schlaegt fehl (SWR 2.0 > 1.5)
- QSO-Log: „⚠ Tuner konnte nicht matchen — SWR 2.0 > Limit 1.5"
- **ABER:** CQ-Button bleibt klickbar — Klick auf CQ startet TX → P53-Watchdog
  feuert beim ersten TX → bricht ab + setzt Marker NACH dem Versuch
- Mike-Spec: Marker MUSS schon nach TUNE-bad gesetzt sein, vor jedem TX-Versuch.

## Mike's Forderung (verbatim)

> „cq ruf trotzdem möglich, bricht dann aber ab weil swr sperre greift.
> aber bedinung sollte gar nicht erst möglich sein alles müsste gespeert
> sein ausser bandwechsel (weil da ist ja der swr vlt gut) oder manuelles
> tunen, fals ich problem beseitigt hab um zu prüfen und/oder band
> freizugeben zum funken"

## Root Cause (Code-verifiziert)

`ui/mw_tx.py:_tune_post_swr_check` Z.364-380 (else-Branch / SWR-bad):
```python
else:
    # AC7 P63: Marker bleibt rot. R1-F2: kein QMessageBox bei Auto-Tune.
    if is_auto and dlg is not None:
        print(f"[P54a] DONE FAIL reason=swr_bad ...")
        dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
    else:
        self.qso_panel.add_info(
            f"⚠ Tuner konnte nicht matchen — SWR {swr_now:.1f} > "
            f"Limit {swr_limit:.1f}. Antenne pruefen oder TUNE wiederholen."
        )
```

**Problem:** Kommentar sagt „Marker bleibt rot" — aber im Code wird KEIN
`_swr_blocked_bands.add(band)` aufgerufen. Der Kommentar ist eine
Annahme/Halluzination — Marker wird heute nur in `_on_swr_alarm` Z.662
gesetzt (P53-Watchdog beim TX-Alarm).

**Konsequenz:**
- Wenn TUNE direkt SWR-bad findet (kein TX vorher), gibt's keinen Marker
- Pre-Checks in `_on_cq_clicked`/`_on_btn_omni_cq_toggled`/`_on_btn_auto_hunt_toggled`
  greifen nicht
- Erst beim TX-Versuch feuert Watchdog → bricht ab, setzt dann Marker

## Fix-Strategie (Variante A, KISS)

**Pattern uebernommen aus `_on_swr_alarm` Z.658-674:**

Im `_tune_post_swr_check` else-Branch Marker-Set einbauen wenn
`tuner_present=True`:

```python
else:
    # P76-C (v0.97.50): TUNE-bad setzt Marker proaktiv —
    # vorher wurde Marker nur vom P53-Watchdog gesetzt (erst beim
    # TX-Versuch). Mike-Spec: schon nach TUNE-bad sperren.
    band = self.settings.band.upper()
    tuner = self.settings.get("tuner_present", True)
    if tuner:
        self._swr_blocked_bands.add(band)

    if is_auto and dlg is not None:
        print(f"[P54a] DONE FAIL reason=swr_bad ...")
        dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
    else:
        # Text leicht erweitert wenn Marker gesetzt — sonst irrefuehrend
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

## Was bleibt klickbar (Mike-Spec)

- **Bandwechsel:** kein Pre-Check auf `_swr_blocked_bands` notwendig
  (anderes Band → vlt. anderer SWR). Verifizieren ob `_on_band_changed`
  Marker nicht aktiv prueft.
- **Manueller TUNE:** `_on_tune_clicked` muss Marker IGNORIEREN (zum
  Freischalten). Verifizieren dass kein Block-Pre-Check da ist.
- **Alle TX-Aktionen** (CQ, OMNI, Hunt, Station-Click, Diversity-Start)
  bleiben gesperrt — Pre-Checks existieren schon (P63 AC8).

## Hardware-Pflicht (ANT1)

Aenderung beruehrt nur Marker-Set + Text — kein Antennen-Pfad.

## Test-Bedarf

- T1: TUNE-bad mit `tuner_present=True` → `_swr_blocked_bands` enthaelt das Band
- T2: TUNE-bad mit `tuner_present=False` → kein Marker (nur Hinweis-Text)
- T3: Text-Variante mit Marker enthaelt „Band X gesperrt"
- T4: Text-Variante ohne Marker enthaelt „Tuner konnte nicht matchen"
- T5: Auto-Tune-Pfad setzt Marker auch (Signal-Emit + Marker-Set)
- T6: TUNE-OK ueberschreibt Marker korrekt (Freischaltung — existiert schon P63 AC6)
- T7: Source-Level: Marker-Set MUSS in else-Branch von `_tune_post_swr_check` sein

## Akzeptanz-Kriterien

- **AC1:** Nach TUNE-bad mit Tuner: Band-Marker gesetzt + Hinweis „Band X gesperrt"
- **AC2:** Nach TUNE-bad ohne Tuner: kein Marker (User-Hinweis „Antenne pruefen")
- **AC3:** Auto-Tune-Pfad verhaelt sich identisch zum manuellen Pfad bzgl. Marker
- **AC4:** CQ/OMNI/Hunt-Klick nach TUNE-bad ist blockiert (P63 AC8 unveraendert)
- **AC5:** Bandwechsel ist erlaubt nach TUNE-bad
- **AC6:** Manueller TUNE ist erlaubt nach TUNE-bad (zum Freischalten)

## Offene Fragen fuer R1

1. **Variante A reicht?** Oder Sampling/Hysterese gegen Wackeln noetig (z.B. 2x TUNE-bad)? KISS-Antwort vermutlich „nein, 1x reicht — User hat explizit TUNE gedrueckt".
2. **Auto-Tune-Pfad-Konsistenz:** Soll Marker auch im is_auto-Branch gesetzt werden? Heute fehlt dort der `_swr_blocked_bands.add`. **Empfehlung V1:** ja, gleicher Schutz auch bei Auto-Tune.
3. **Doku-Kommentar:** „AC7 P63: Marker bleibt rot" entfernen oder korrigieren?
4. **Text-Variante:** „Band X gesperrt" ist konsistent mit `_on_swr_alarm`-Modal — gut?

## Workflow-Schritte

1. V2 (Self-Review)
2. R1 mit DeepSeek-V4-pro
3. V3
4. Code (3 atomare Commits + Tests)
5. Final-R1
6. Field-Test bei Mike: Reproduktion mit SWR-Limit=1.5
