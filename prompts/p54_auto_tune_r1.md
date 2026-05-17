[deepseek] ~52641 Tokens, 4 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=59812 out=11031 total=70843
## R1-Findings

### F1 (ROT): Falscher`watt`-Schlüssel im RFPresetStore-Save-Hook  
- Pfad: Plan AC6, Save-Code  
- Symptom: `rf_preset_store.save(radio, band, watts=round(avg_fwdpwr), rf=10)` speichert die gemessene momentane Leistung als Zielwatt-Schlüssel, nicht die feste TUNE-Ziellast (10 W). Damit entstehen Stützpunkte für willkürliche Watt-Werte wie 9 W oder 11 W. Die spätere Hybrid-Interpolation findet diese Einträge nicht zuverlässig unter der vom Benutzer gewählten Leistung (10 W).  
- Fix: Speichere unter `watt=10` (die nominale TUNE-Leistung) mit `rf=10`. Die gemessene FWDPWR dient nur zur Plausibilitätsprüfung und optional zum Logging. Korrekt:  
  ```python
  self.rf_preset_store.save(radio, band, watt=10, rf=10)
  ```

### F2 (ROT): Doppelte Modal-Warnung + Signalrouting im Auto‑Tune‑Pfad unvollständig  
- Pfad: `_tune_post_swr_check` (mw_tx.py) und AutoTuneDialog  
- Symptom: Im bestehenden Code öffnet `_tune_post_swr_check` bei SWR‑Bad eine `QMessageBox.warning`. Im Auto‑Tune‑Modus soll stattdessen das Signal `auto_tune_finished` emittiert werden und der Dialog die Zuständigkeit übernehmen. Der Plan (V1‑AC7, V2‑F5) spezifiziert nur, dass das Signal emittiert wird, **nicht** dass die MessageBox unterbleibt. Folge: Auto‑Tune zeigt zwei übereinander liegende Dialoge, der AutoTuneDialog kann nicht bestimmen, ob Erfolg oder Fehler, weil die MessageBox den Programmfluss blockiert.  
- Fix: `_tune_post_swr_check` muss bei gesetztem Flag `_auto_tune_running` **keine** MessageBox anzeigen und stattdessen das Signal `auto_tune_finished(success, swr, avg_fwdpwr)` emittieren. Erst danach darf die normale Logik (Marker‑Discard etc.) ausgeführt werden.  

### F3 (ORANGE): Vorzeitige Diversity‑Resume im Auto‑Tune‑Pfad  
- Pfad: `_tune_post_swr_check` nach erfolgreichem SWR‑Check (mw_tx.py:187 ff.)  
- Symptom: Im manuellen TUNE wird nach Freigabe des Band‑Markers Diversity automatisch fortgesetzt (`_check_diversity_preset`). Im Auto‑Tune nach Bandwechsel ist Diversity aber noch nicht initialisiert; der Bandwechsel‑Hook ruft `_check_diversity_preset` erst **nach** dem Auto‑Tune auf. Ein vorzeitiges Anstoßen durch den Post‑Check führt zu einer zusätzlichen, inkonsistenten Initialisierung, eventuell mit veraltetem Gain‑Cache.  
- Fix: Im Post‑Check den Diversity‑Resume‑Block nur ausführen, wenn **nicht** `_auto_tune_running` True ist. Der reguläre Bandwechsel‑Ablauf kümmert sich danach selbst um Diversity.  

### F4 (ORANGE): `_tune_in_progress`-Cleanup bei Auto‑Tune‑Timeout nicht garantiert  
- Pfad: `AutoTuneDialog`-Timeout-Timer, Cancel‑Pfad in `_start_auto_tune_for_band_change`  
- Erkenntnis: Der Dialog soll einen eigenen Timer (`tune_duration_s + 5 s`) als Sicherheits‑Backup besitzen. Bei Ablauf ruft der Timer `reject()` auf, was zum Cancel‑Pfad des Helpers führt. Der Cancel‑Pfad muss `_tune_in_progress = False` setzen (gemäß V2‑F2). Wird dies im Timer direkt versäumt, bleibt der Watchdog dauerhaft umgangen.  
- Fix: Im Timeout‑Arm des `AutoTuneDialog` den Cleanup (`_tune_in_progress=False`) **vor** dem `reject()` durchführen oder sicherstellen, dass der Cancel‑Pfad des Helpers dies garantiert (z. B. in `_tune_stop`). Im Zweifel ein dedizierter Signal‑Slot, der den Cleanup anstößt.  

### F5 (GELB): Meter‑Updates während `exec()`-Blockade verändern Anzeigezustände  
- Pfad: `exec()` im `AutoTuneDialog` während Bandwechsel; `_on_meter_update` läuft weiter.  
- Risiko: FWDPWR- und SWR‑Aktualisierungen können auf nicht mehr sichtbare UI‑Elemente schreiben oder das Control‑Panel kurzzeitig durcheinander bringen, weil die Anzeige nicht mehr zum aktuellen Kontext passt. Da der Aufruf im GUI‑Thread erfolgt, sind keine Thread‑Race‑Conditions zu erwarten, aber visuelle Inkonsistenzen (z. B. Watt‑Anzeige ändert sich unter dem Modal). Kein funktionaler Bug, aber unschön.  
- Maßnahme: Kein zwingender Fix; ggf. Meter‑Aktualisierung während `_auto_tune_running` auf das Dialog‑Widget umleiten oder temporär unterdrücken.  

### F6 (GELB): Testabdeckung für Randfälle ungenügend  
- Plan: 15+1 Tests (AC12 + V2‑F6).  
- Lücken: Kein Test für Timeout‑Pfad, Cancel während Auto‑Tune, verfrühtes `radio.ip=None`, Plausibilitäts‑Grenzwerte exakt (2.0 und 80.0).  
- Empfehlung: Mindestens vier weitere Tests (Timeout‑Handle, Cancel‑Cleanup, Verbindungsverlust während TUNE, Grenzfälle der FWDPWR‑Prüfung).

## Pflicht-Fragen-Antworten

1. **Lineare Watt-Annahme** – Die Slider‑Ausgangsleistungskennlinie des FlexRadio ist bei gutem SWR annähernd linear. Verluste durch den externen Tuner sollten in derselben Größenordnung bleiben. Der 10‑W‑Stützpunkt als Anker für 50 W ist ausreichend, weil der Closed‑Loop während der ersten TX‑Slots die Abweichung korrigiert. Ungenauigkeiten von einigen Watt sind daher unkritisch.  
2. **`exec()` in `_on_band_changed`** – Der Decoder‑Thread läuft weiter, Signale werden in der Qt‑Event‑Queue gepuffert und nach dem `exec()` sequenziell verarbeitet. Das ist sicher; ein explizites Pausieren ist unnötig, solange keine zeitkritischen Abhängigkeiten bestehen (hier nicht der Fall).  
3. **FWDPWR‑Sampling‑Race** – keine echte Race‑Condition, da `_tune_active` und `_fwdpwr_samples` nur im GUI‑Thread verändert werden. Die Reihenfolge „Clear, dann Meter‑Update“ ist durch die Ein‑Thread‑Natur geschützt. Das Flag kann zwischen Sample und Post‑Check nicht asynchron toggeln.  
4. **Plausibilitäts‑Check (2 < avg < 80)** – Die Grenzen sind gut gewählt: 2 W unterscheidet sicher zwischen tatsächlicher Abstrahlung und Rauschen/Fehler; 80 W liegt weit über dem bei 10 W Slider Möglichen, fängt also grobe Fehlmessungen ab. 100‑W‑Stationen mit 10 W Slider liegen um 10 ± 3 W. Durchlass‑Tuner können etwas mehr Verlust bringen, aber nie unter 2 W. Die Grenzen sind angemessen.  
5. **Cooldown bei mehrfachem Bandwechsel** – Ein interner Cooldown pro Band (z. B. 30 Min) ist aus UX‑Sicht wünschenswert, aber nicht erforderlich, weil Mike den Toggle `auto_tune_on_band_change` im Settings‑Dialog deaktivieren kann. Sein Arbeitsstil (gezieltes Stöbern) verträgt die 15‑s‑Pause. Ein späteres Feature‑Request bleibt möglich; für die aktuelle Version reicht der Toggle.  
6. **Mode‑Wechsel (FT8↔FT4↔FT2)** – Hardware‑Eigenschaften und Slider‑Leistungskennlinie sind identisch, daher kein Re‑Tune nötig. Richtig.  
7. **Cancel während Tuner‑Mitte** – Der Befehl `tune_off` schaltet den Carrier aus; der externe Tuner (LDG AT‑200 Pro) läuft dann ins Leere und bleibt im zuletzt erreichten Zustand. Es gibt keine Hardware‑Gefahr; nach einem erneuten TUNE wird der Tuner wieder aktiv. Der Zustand ist sauber genug.  
8. **ANT1‑Pflicht** – Der Helper `_start_auto_tune_for_band_change` (V2‑F7) repliziert die Schritte aus `_on_tune_clicked(True)`; darin ist `set_tx_antenna("ANT1")` explizit enthalten. Wird korrekt umgesetzt.  
9. **App‑Start‑Verhalten** – Beim initialen Connect läuft kein `_on_band_changed`-Callback (nur ControlPanel‑Initialisierung ohne Signal‑Feuerung). Erst ein echter User‑Klick auf einen Band‑Button triggert Auto‑Tune. Das ist konform zur Spezifikation. ✔  
10. **Test‑Coverage** – 15+1 Tests decken die Hauptpfade gut ab. Es fehlen jedoch Tests für Timeout, Cancel und Verbindungsverlust. Insgesamt sollten es mindestens 20 Tests sein; siehe F6.

## Empfehlung

Push-Status: **FREIGEGEBEN MIT F1‑F2‑FIX**  
KP (kritische Punkte):  
- F1 (watt‑Schlüssel) sofort korrigieren.  
- F2 (Signal‑Routing + MessageBox‑Unterdrückung) vor Implementierung des AutoTuneDialog klären.  
- F3 (Diversity‑Resume‑Schutz) in `_tune_post_swr_check` ergänzen.  
- F4 (Timeout‑Cleanup) im AutoTuneDialog verbindlich vorsehen.  
- Test‑Suite um die genannten Randfälle erweitern (F6).  

Damit ist das Bundle sicher und erfüllt Mikes autonomen Workflow.
