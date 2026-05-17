# R1 — DeepSeek-V4-pro Review für P54 (Auto-Tune bei Bandwechsel + RFPreset-Stützpunkt)

Du bist Senior-Code-Reviewer. Sprache: Deutsch. Prüfe diesen Plan
streng auf Bugs, Race-Conditions, Halluzinationen, Edge-Cases, KISS-
Verletzung, Hardware-Sicherheit.

## Kontext SimpleFT8

- FT8/FT4/FT2-Funk-App mit PySide6/Qt, FlexRadio FLEX-8400M Backend.
- **TUNE-Modus** (`radio.tune_on()`) startet internen Carrier — kein
  Encoder-TX. P63 hat 10 W FEST, Dauer 15/30 s, Watchdog-Bypass via
  `_tune_in_progress`, SWR-Marker-Pfad (`_swr_blocked_bands`).
- **RFPresetStore** (`core/rf_preset_store.py`) speichert pro
  `(radio, band, watts)` den konvergierten Slider-Wert (0-100). Hybrid-
  Strategie: exakter Treffer → lineare Interpolation → None.
- **Hardware-Pflicht:** ANT1 = TX-only, ANT2 = NUR RX. Niemals TX auf
  ANT2 (CLAUDE.md).

## Aufgabe (V1+V2-Kondensat)

**P54a:** Settings-Toggle `auto_tune_on_band_change` (Default True).
Bei Bandwechsel öffnet AutoTuneDialog (WindowModal, exec-blocking),
führt 10 W TUNE auf ANT1, schließt bei SWR-Good. Bei Timeout/Fail:
Warning + Marker bleibt.

**P54b:** Während TUNE wird FWDPWR gemessen. Bei SWR-Good:
`rf_preset_store.save(radio, band, watts=round(avg_fwdpwr), rf=10)`.
Damit hat jedes Band nach erstem TUNE einen 10-Slider-Stützpunkt.
Manueller TUNE-Klick speichert ebenfalls.

## V2-Selbst-Findings bereits berücksichtigt

- V2-F1: `_apply_rf_preset()` nach Save nochmal aufrufen.
- V2-F2: `_tune_in_progress=False` im Cancel-Pfad.
- V2-F3: Re-Entry-Schutz `_tune_active` in `_on_band_changed`.
- V2-F5: State `_auto_tune_running` + Signal `auto_tune_finished` nur
  bei aktiver Session.
- V2-F7: Helper `_start_auto_tune_for_band_change`, kein invasiver
  Refactor.

## Pflicht-Fragen

1. **Lineare Watt-Annahme:** Wir speichern `(band, watt=round(avg_fwdpwr),
   rf=10)`. RFPresetStore-Hybrid-Strategie interpoliert linear zwischen
   Stützpunkten. Bei FlexRadio FLEX-8400M ist Slider linear zu Output —
   aber gilt das auch bei stark off-band Antennen mit Tuner-Verlust?
   Reicht der 10-W-Stützpunkt als Anker für Hochskalierung auf 50 W?
2. **`exec()`-Modal in `_on_band_changed`:** Bandwechsel-Logik blockiert
   bis Auto-Tune fertig. Decoder-Thread läuft weiter, aber `cycle_finished`-
   Signals könnten sich anstauen. Ist das OK oder muss der Decoder
   pausiert werden?
3. **FWDPWR-Sampling während TUNE:** `_on_meter_update` läuft heute nur
   bei `encoder.is_transmitting`. V1 AC5 erweitert auf `_tune_active`.
   Gibt es Race-Conditions wenn `_tune_active` zwischen FWDPWR-Sample
   und `_tune_post_swr_check` von True→False wechselt?
4. **Plausibilitäts-Check:** V1 AC6 fordert `2 < avg < 80`. Sinnvoll?
   Zu eng/zu weit? Was ist mit 100-W-Stationen die 10 W Slider noch
   ~12 W Output haben?
5. **Auto-Tune bei jedem Bandwechsel:** Mike wechselt evtl. mehrmals
   pro Minute zwischen Bändern beim Stöbern. 15 s × N = nervig. Sollten
   wir ein Cooldown (z. B. „Auto-Tune nur 1×/Band pro 30 Min")
   einbauen? Oder reicht der User-Toggle?
6. **Mode-Wechsel:** Keine Re-Tune bei FT8↔FT4↔FT2 — Hardware
   identisch. Korrekt?
7. **AutoTuneDialog Cancel:** Reject() während Tuner mid-cycle —
   ist Hardware-State danach sauber? (Tuner hat keine Stopp-API beim
   LDG AT-200 Pro — `tune_off` stoppt nur den Carrier).
8. **Hardware-Pflicht ANT1:** Wo wird explizit `set_tx_antenna("ANT1")`
   im Auto-Tune-Pfad aufgerufen? Bestehender Code (`_on_tune_clicked`
   Z.105). Unser Helper muss das auch tun.
9. **App-Start-Verhalten:** Beim allerersten Connect (Radio.ip wird
   nicht-None) — sollte Auto-Tune NICHT triggern, nur bei expliziten
   User-Bandwechseln. V2-F9 sagt: ist OK weil Connect kein
   `_on_band_changed` triggert. Verifizieren?
10. **Test-Coverage:** Reichen 15 Tests? Welche fehlen?

## Antwortformat

```
## R1-Findings

### F1 (ROT): <Titel>
- Pfad: <Datei:Zeile>
- Symptom/Wurzel/Fix

### F2 (ORANGE): ...
### F3 (GELB): ...

## Pflicht-Fragen-Antworten
1. ...
...

## Empfehlung
Push-Status: FREIGEGEBEN / FREIGEGEBEN MIT F-X-FIX / BLOCKIERT
KP (kritische Punkte): ...
```

Max 1800 Wörter. Mike will Workflow autonom durchziehen — sei
gründlich aber pragmatisch.
