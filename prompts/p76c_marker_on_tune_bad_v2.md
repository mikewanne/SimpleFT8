# P76-C TUNE-bad setzt Band-Marker proaktiv — V2 (Self-Review)

**Vorgaenger:** prompts/p76c_marker_on_tune_bad_v1.md

---

## Code-Verifikation V2

### Vorhandene Pre-Checks (sollen weiter funktionieren)
- `_on_cq_clicked` Z.298 ✓ → `set_cq_active(False)` + add_info
- `_on_btn_omni_cq_toggled` Z.836 ✓
- `_on_btn_auto_hunt_toggled` Z.931 ✓
- `_on_station_clicked` Z.152 ✓
- `_check_diversity_preset` Z.1279 ✓
- `_on_tx_finished` Z.441 ✓ (gepufferter Klick)
- `_on_band_changed` Z.515 ✓ (skip Auto-Tune wenn gesperrt — kein Block des Wechsels)

### Was bleibt frei (Mike-Spec)
- **Bandwechsel selbst:** `_on_band_changed` blockt nicht den Wechsel, nur Auto-Tune. ✓
- **Manueller TUNE:** `_on_tune_clicked` Z.78 hat KEINEN `_swr_blocked_bands`-Check. ✓
  Freischaltung passiert dann via TUNE-good-Branch Z.300-301 `_swr_blocked_bands.discard(band)`.

### Bug-Stelle (zu fixen)
`_tune_post_swr_check` Z.364-380 else-Branch hat KEINEN Marker-Set.
Kommentar Z.365 „AC7 P63: Marker bleibt rot" ist irreführend.

### Auto-Tune-Pfad
Z.366-371 (is_auto-Branch) emittet `auto_tune_done(False, ...)` an Dialog.
**FEHLT:** Marker-Set ist nicht da. Dialog zeigt Fehler an, aber Band bleibt
„offen" für CQ/OMNI/Hunt → gleicher Bug wie manueller Pfad.

---

## Findings

### F1 ✅ Variante A Pattern korrekt

Pattern aus `_on_swr_alarm` Z.658-668 ist die Referenz:
```python
band = self.settings.band.upper()
tuner = self.settings.get("tuner_present", True)
if tuner:
    self._swr_blocked_bands.add(band)
```

Im `_tune_post_swr_check` else-Branch identisch einsetzen.

### F2 🔴 Auto-Tune-Pfad muss AUCH Marker setzen

V1 hat es schon erwaehnt — wichtig: bei `is_auto=True` (Bandwechsel-Auto-Tune)
muss Marker GENAUSO gesetzt werden. Sonst startet User CQ direkt nach
Bandwechsel obwohl Auto-Tune fehlgeschlagen ist.

**Lösung:** Marker-Set VOR der `is_auto`-Abzweigung — gilt fuer beide Pfade.

### F3 🟡 Doku-Kommentar Z.365 korrigieren

Aktuell: `# AC7 P63: Marker bleibt rot. R1-F2: kein QMessageBox bei Auto-Tune.`

War irreführend — Marker wurde gar nicht gesetzt. Korrigieren auf:
`# P76-C (v0.97.50): Marker setzen wenn tuner_present=True (vorher nur Watchdog).`

### F4 ⚪ Text-Variante korrekt

„Band {band} gesperrt — SWR {swr} > Limit {limit}. Manueller TUNE zum
Freischalten nach Antennen-Check." — konsistent mit `_on_swr_alarm`-Modal
(Z.665 „Band {band} gesperrt — SWR {swr:.1f} > Limit {limit:.1f}").

### F5 ⚠️ AutoTuneDialog-Anzeige bei Marker-Set

Wenn `is_auto=True` und Marker wird gesetzt: User sieht im Dialog
„Auto-TUNE fehlgeschlagen — SWR X.X" (existiert schon). Marker-Set
passiert im Hintergrund. User merkt es indirekt wenn er CQ klickt
nach Dialog-Schliessen → „Band gesperrt"-Hinweis greift.

**Akzeptabel** — keine zusaetzliche UI-Aenderung noetig.

### F6 ⚠️ TUNE-OK-Branch loescht Marker (existiert schon)

Z.300-301 `_swr_blocked_bands.discard(band)` ✓. Wenn User nach
Antennen-Check erneut TUNE drueckt und SWR OK ist, wird Marker
geloescht. P63 AC6 unveraendert.

### F7 ⚪ Bandwechsel-Verhalten unveraendert

User wechselt auf anderes Band → kein Pre-Check auf gesperrtes
*aktuelles* Band, weil das aktuelle Band bleibt im Marker — anderes Band
ist „frei" (es sei denn auch dort wurde TUNE-bad gemacht).

### F8 ⚠️ Disconnect-Race bei Auto-Tune

Wenn Radio waehrend Auto-Tune disconnected (Z.263 Disconnect-Branch),
returnt der Post-Check fruehzeitig OHNE Marker-Set. Akzeptabel —
naechster TUNE-Versuch nach Re-Connect setzt Marker neu wenn noetig.

### F9 ⚪ Re-Entry-Schutz

`_tune_post_swr_check` hat Token-Guard Z.252. Wenn 2. TUNE startet
waehrend 1. Post-Check noch laeuft, returnt 1. Aufruf fruehzeitig.
Marker-Set passiert im 2. Aufruf (mit aktuellem Band).

### F10 ⚠️ `tuner_present=False` Verhalten

Mike hat `tuner_present=True` (LDG AT-200 Pro). Aber Code muss auch ohne
Tuner sauber laufen:
- `tuner=False` → kein Marker → User sieht „Antenne pruefen"-Text
- User soll trotzdem klar verstehen dass TX nicht moeglich ist
- **Aber:** ohne Marker greifen Pre-Checks nicht → CQ klickbar
- Akzeptabel? P63 hat das schon so → konsistent. Tuner=False ist edge-case.

---

## Aktualisierte Code-Strategie

### Single-Block-Aenderung in `_tune_post_swr_check`

```python
else:
    # P76-C (v0.97.50): TUNE-bad setzt Band-Marker proaktiv (vorher
    # nur P53-Watchdog beim TX-Versuch). Marker-Set VOR is_auto-Branch
    # damit beide Pfade (manuell + Auto-Tune) Konsistenz haben.
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
        # P75 (v0.97.48): QMessageBox raus, stattdessen rote Zeile
        # im Live-Log. P76-C (v0.97.50): Text variiert mit Marker-State.
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

**Gesamt:** ~10 LOC Aenderung in 1 Methode. KISS.

---

## Tests V2

- **T1** Manueller TUNE-bad mit `tuner_present=True` → Band in `_swr_blocked_bands`
- **T2** Manueller TUNE-bad mit `tuner_present=False` → Band NICHT in `_swr_blocked_bands`
- **T3** Auto-Tune-bad mit `tuner_present=True` → Band in `_swr_blocked_bands` (Konsistenz F2)
- **T4** Auto-Tune-bad mit `tuner_present=False` → Band NICHT in `_swr_blocked_bands`
- **T5** Manuell Text mit Tuner enthaelt „Band X gesperrt"
- **T6** Manuell Text ohne Tuner enthaelt „Tuner konnte nicht matchen"
- **T7** TUNE-OK loescht vorhandenen Marker (P63 AC6-Regression-Schutz)
- **T8** Source-Level: `_swr_blocked_bands.add` im else-Branch von `_tune_post_swr_check`
- **T9** Source-Level: kein Marker-Set im TUNE-good-Pfad (Branch-Sauberkeit)
- **T10** Source-Level: kein `set_tx_antenna` im neuen P76-C-Block (Hardware-Pflicht)

---

## Offene Fragen fuer R1

1. **F2:** Marker-Set VOR is_auto-Branch (gilt fuer beide Pfade) korrekt?
   Oder soll Auto-Tune-Pfad Marker NICHT setzen damit User noch Auto-Tune
   bei naechstem Bandwechsel kriegen kann? (Vermutung: konsistent setzen,
   User kann via manueller TUNE freischalten.)
2. **F5:** AutoTuneDialog soll nichts vom Marker-Set wissen, oder einen
   zusaetzlichen Status-Hinweis im Dialog zeigen?
3. **F10:** `tuner_present=False`-Fall — soll auch Marker gesetzt werden
   damit Pre-Checks greifen? P63-Spec sagt nein, aber das laesst Sperre
   loecherig. KISS-Frage.
4. **Test-Strategie:** Source-Level reicht (analog P63/P76-A) oder echte
   Functional-Tests?

---

## Workflow

✅ V1
✅ V2 (dieses Dokument)
⏭ R1 mit DeepSeek-V4-pro
⏭ V3
⏭ Code
⏭ Final-R1
⏭ Field-Test
