# P76-C Marker bei TUNE-bad — R1 Prompt (DeepSeek-V4-pro)

**Du bist DeepSeek-V4-pro im Workflow V1 → V2 → R1 → V3 → Code → Final-R1.**

Reviewe Bug-Diagnose + Fix-Strategie fuer SimpleFT8 v0.97.50 P76-C (Folge-Fix
nach P76-A SAFETY-Bug aus heutiger Session).

---

## Context — Mike-Field-Test 18.05.

Mike testet P76-A-Fix (echter SWR im Log statt 1.0): setzt SWR-Limit=1.5
in Settings, drueckt TUNE auf 40m. TUNE schlaegt fehl (SWR 2.0 > 1.5).
Log zeigt korrekt „⚠ Tuner konnte nicht matchen — SWR 2.0 > Limit 1.5".

**ABER:** CQ-Button bleibt klickbar. Klick startet TX → P53-Watchdog feuert
beim ersten TX-Versuch → bricht ab + setzt erst DANN Band-Marker.

**Mike-Spec:** Pre-TX-Sperre fehlt. Marker MUSS schon nach TUNE-bad
gesetzt sein, vor jedem TX-Versuch. Freigegeben durch manuellen TUNE
(zur Diagnostik / Freischaltung) oder Bandwechsel.

---

## Root Cause

`ui/mw_tx.py:_tune_post_swr_check` else-Branch (SWR-bad) Z.364-380:
- Kommentar sagt „AC7 P63: Marker bleibt rot" — irrefuehrend
- IM CODE wird KEIN `_swr_blocked_bands.add(band)` aufgerufen
- Marker wird heute nur von `_on_swr_alarm` (P53-Watchdog beim TX-Alarm) gesetzt
- Folge: CQ/OMNI/Hunt klickbar nach TUNE-bad

Konsequenz: Pre-Checks in `_on_cq_clicked` Z.298 / `_on_btn_omni_cq_toggled` /
`_on_btn_auto_hunt_toggled` / `_on_station_clicked` / `_check_diversity_preset`
greifen nicht, weil `_swr_blocked_bands` leer ist.

---

## Vorhandene Pre-Checks (bestaetigt funktional, sollen unveraendert bleiben)

- CQ Z.298, OMNI Z.836 (main_window), Hunt Z.931 (main_window),
  Station-Click Z.152, Diversity-Preset Z.1279, Buffered-Click Z.441,
  Bandwechsel-AutoTune Z.515 (skip nur, kein Block des Wechsels)
- `_on_tune_clicked` Z.78 hat KEINEN Marker-Check (Freischalt-Pfad) ✓
- `_tune_post_swr_check` TUNE-OK-Branch Z.300-301 `discard(band)` (Freischaltung) ✓

---

## Geplanter Fix (Variante A, KISS)

Pattern uebernommen aus `_on_swr_alarm` Z.658-668:

```python
else:
    # P76-C (v0.97.50): TUNE-bad setzt Band-Marker proaktiv. Vorher
    # nur P53-Watchdog beim TX-Versuch.
    tuner = self.settings.get("tuner_present", True)
    if tuner:
        self._swr_blocked_bands.add(band)

    if is_auto and dlg is not None:
        print(f"[P54a] DONE FAIL reason=swr_bad ...")
        dlg.auto_tune_done.emit(False, swr_now, avg_fwdpwr)
    else:
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

**Gesamt:** ~10 LOC im else-Branch. Marker-Set VOR is_auto-Abzweigung —
gilt fuer beide Pfade (manueller TUNE + Auto-Tune bei Bandwechsel).

---

## Pruef-Auftrag

### Architektur
1. **Variante A korrekt?** Marker-Set in else-Branch reicht oder zusaetzliche
   Logik noetig (z.B. Hysterese)?
2. **Marker-Set VOR is_auto-Abzweigung:** Soll Auto-Tune-Pfad GLEICH wie
   manueller Pfad Marker setzen? Oder Auto-Tune-Pfad eigenes Verhalten
   (z.B. kein Marker damit naechster Bandwechsel wieder Auto-Tune triggert)?
3. **`tuner_present=False`-Fall:** Heute kein Marker → Pre-Checks greifen
   nicht → CQ klickbar trotz SWR-bad. P63-Spec sagt so. KISS oder Bug?
   (Hinweis: in `_on_swr_alarm` ist das genauso.)

### Sicherheit (Pflicht!)
4. **ANT1-Pflicht:** Aenderung beruehrt nur Marker-Set + Text. Kein
   `set_tx_antenna`-Aufruf in neuem Block. Bestaetigung dass Hardware-
   Pfad unveraendert.
5. **Race-Condition:** Mehrfach-TUNE: Token-Guard schuetzt schon. Marker-Set
   ist idempotent (set.add) → kein Problem.
6. **TUNE-OK-Branch ueberschreibt korrekt:** `_swr_blocked_bands.discard(band)`
   Z.301 wenn naechster TUNE SWR-OK liefert → Freischaltung funktioniert.

### Konsistenz mit P63
7. **Was war P63's urspruengliche Annahme?** Kommentar „Marker bleibt rot"
   suggeriert dass Marker schon vorher gesetzt war (vom Watchdog). Aber wenn
   User TUNE drueckt OHNE vorherigen TX-Alarm, ist Marker leer. P63 hatte
   eine Luecke.
8. **Doku-Anpassung:** Kommentar in Z.365 korrigieren. P63 AC7 in CLAUDE.md
   adjustieren?

### UX
9. **Text-Variante:** „Band {band} gesperrt — SWR {swr} > Limit ... Manueller
   TUNE zum Freischalten nach Antennen-Check." — konsistent mit
   `_on_swr_alarm`-Modal-Text. OK?
10. **AutoTuneDialog:** Bei is_auto=True kriegt Dialog Signal mit success=False.
    User sieht Fehler-Anzeige im Dialog. Dass Marker gesetzt wurde, merkt
    User indirekt beim naechsten CQ-Klick (Band-gesperrt-Hinweis). Akzeptabel?

### Tests
11. 10 Tests T1-T10 (4 functional fuer Marker-Set, 2 Text-Varianten, 1
    TUNE-OK-Regression, 3 Source-Level). Reicht?

### Push-Empfehlung
12. PUSH FREIGEGEBEN nach V3 oder ueberarbeiten?

---

## Antwort-Format

Pro Finding:
- **F-Nummer + Status (🔴/🟠/🟡/⚪):** Befund
- **Begruendung:** mit Zeilen-Verweis wenn relevant
- **Empfehlung:** uebernehmen/abweichen/verwerfen
- **Aenderung am Code:** falls noetig

Am Ende: **PUSH FREIGEGEBEN** oder **ueberarbeiten**.

**KISS-Hinweis:** SimpleFT8 Hobby-Funker-Tool. Lieber 10 LOC einfach als 50 LOC
abstrahiert. Variante A bevorzugt wenn safety-OK.
