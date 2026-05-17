[deepseek] ~37257 Tokens, 4 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=42758 out=8409 total=51167
## R1-Findings

### F1 (ROT): Fehlender `set_power` nach `_apply_rf_preset` in `_tune_post_swr_check`
- **Pfad:** `ui/mw_tx.py` in `_tune_post_swr_check` – nach dem Speichern des Presets wird `_apply_rf_preset()` aufgerufen, aber kein `self.radio.set_power(self._rfpower_current)`.
- **Symptom:** `_rfpower_current` wird intern aktualisiert, das Radio behält aber den bisherigen Slider‑Wert. Im nächsten Closed‑Loop‑Zyklus regelt `_auto_adjust_tx_level` gegen eine veraltete Hardware‑Basis – Power‑Spike oder ungenaue Regelung.
- **Fix:** Unmittelbar nach `self._apply_rf_preset()` explizit `self.radio.set_power(self._rfpower_current)` aufrufen (analog zum P54‑Final‑R1‑ROT‑Fix).

### F2 (ROT): Cancel‑Race während der Convergenz‑Schleife
- **Pfad:** `_tune_converge_to_target` (noch nicht implementiert, aber laut Specs synchron über `QEventLoop`). Ein Cancel aus dem `AutoTuneDialog` ruft `_on_cancel_clicked` → `_tune_stop(None)` → setzt `_tune_in_progress=False` und schließt den Dialog.
- **Symptom:** Die im selben GUI‑Thread laufende `QEventLoop`-Schleife der Convergenz wird nicht informiert und passt den Slider weiter an – inkonsistenter Hardware‑Zustand, eventuell sogar nach bereits erfolgtem `tune_off()`.
- **Fix:** Ein `_tune_convergence_cancelled`‑Flag einführen. `_on_cancel_clicked` (und auch `_on_backup_timeout`) setzen es auf `True`. Die Convergenz‑Schleife prüft das Flag am Anfang jeder Iteration und liefert `None` zurück, wenn gesetzt (entsprechend V2‑F1).

### F3 (ROT): Fehlende Initialisierung von `_tune_converged_rf`
- **Pfad:** `ui/mw_tx.py` – die State‑Variable `_tune_converged_rf` wird in AC3/AC2 als Träger für den konvergierten Wert verwendet, ist aber im Mixin nicht deklariert (weder in `__init__` noch als Klassenattribut).
- **Symptom:** Laufzeit‑Fehler bei erstem Zugriff.
- **Fix:** In der `MainWindow`-Initialisierung `self._tune_converged_rf: Optional[int] = None` ergänzen.

### F4 (ROT): Harte Speicherung von `(band, 10, 10)` in `_tune_post_swr_check`
- **Pfad:** Aktueller Code in `_tune_post_swr_check` (AC3‑Pfad) enthält noch den P54b‑Bug: `self.rf_preset_store.save(..., 10, 10)`.
- **Symptom:** Der Kern des P54‑FIX wird nicht umgesetzt – es wird immer der Wunschwert statt des real konvergierten Slider‑Werts gespeichert.
- **Fix:** Durch `rf_to_save = self._tune_converged_rf if self._tune_converged_rf is not None else 10` ersetzen und in `save()` übergeben.

### F5 (ORANGE): Keine Plausibilitätsprüfung des konvergierten Slider‑Werts vor Speicherung
- **Pfad:** `_tune_converge_to_target` kann bei extremen FWDPWR‑Messungen (z. B. FWDPWR 20 W bei Soll 10 W) auf `rf=1` konvergieren. Solche Werte sind physikalisch unsinnig und würden einen falschen Stützpunkt in der Tabelle hinterlassen.
- **Symptom:** Folgende Last‑Regelungen mit diesem Anker scheitern oder regeln wild.
- **Fix:** In `_tune_post_swr_check` nach der Convergenz prüfen: wenn `rf_to_save < 3` oder `> 50` (für 10 W‑Ziel) → Warnung loggen und Fallback `rf=10` verwenden (speichern). Mike kann den Bereich bei Bedarf anpassen.

### F6 (ORANGE): Fehlende SWR‑Prüfung unmittelbar vor Phase B
- **Pfad:** Sequenz in `_start_auto_tune_for_band_change` / `_on_tune_clicked`. Nach Phase A (Match, z. B. 10 s) wird ohne Kontrolle der Last die Convergenz‑Phase B gestartet.
- **Symptom:** Wenn der Tuner nicht gematcht hat (SWR weiterhin >3), läuft Phase B mit stark reflektierter Leistung. Die Convergenz wird unzuverlässig, und die PA wird unnötig belastet (trotz 10 W).
- **Fix:** Vor Beginn von Phase B den aktuellen SWR abfragen. Ist er über dem Limit, Phase B überspringen und `_tune_converged_rf = None` setzen (Fallback). So wird kein falscher Wert gespeichert und die Hardware geschont.

### F7 (GELB): Unklare Timer‑Abläufe für Phase A / Phase B
- **Pfad:** `_start_auto_tune_for_band_change` und `_on_tune_clicked` starten einen einzigen `QTimer.singleShot` für die gesamte TUNE‑Dauer. Die Aufteilung in Match‑Phase und Convergenz‑Phase muss mit zusätzlichen Timern realisiert werden (V2‑F4 spezifiziert Phase B = min(5 s, ⅓ TUNE‑Dauer)). 
- **Symptom:** Ohne korrekte Implementierung läuft die Convergenz entweder zu kurz oder überlappt mit dem Auto‑Stop‑Timer.
- **Fix:** Einen ersten Timer nach `match_duration_s` starten, der die Convergenz‑Schleife triggert. Den Auto‑Stop‑Timer als Fallback auf `match_duration + max_phase_b_duration` setzen, um hängende Convergenz zu begrenzen.

### F8 (GELB): Krücken‑Seitenfall mit `anchor_rf=0` nicht abgesichert
- **Pfad:** `_kruecken_skalierung` (AC4) prüft `if anchor_rf <= 0: return None`. Das ist korrekt, aber der Fall `anchor_rf >0` bei sehr kleinen Werten (<3) könnte zu unsinnig kleinen Skalierungen führen (Pflichtfrage 7). Dies ist nicht sicherheitskritisch, da der Closed‑Loop später korrigiert – sollte aber mindestens in Test T7 abgedeckt werden.

### F9 (GELB): Fehlender Test für `_tune_post_swr_check` mit `_tune_converged_rf is None`
- **Pfad:** Testabdeckung – T6 prüft Speicherung mit konvergiertem Wert, T12 prüft Fallback. Dennoch sollte explizit ein Test existieren, der `_tune_converged_rf=None` simuliert und sicherstellt, dass `rf_to_save=10` gespeichert wird (Backward‑Compat).

## Pflicht-Fragen-Antworten

1. **QEventLoop + QTimer.singleShot Pattern**: Das Pattern ist technisch sauber, solange während der Schleife keine Slots ausgeführt werden, die den TUNE‑State verändern. Über `_tune_in_progress=True` wird der SWR‑Watchdog bereits ausgeschaltet. `_on_meter_update` füllt nur `_fwdpwr_samples` – kein Konflikt. Reentrant‑Probleme durch andere User‑Aktionen (z. B. Bandwechsel) sind durch Lock‑Mechanismen (`_gain_measure_locked`, `_tune_active`) abgeblockt. Einzig das Cancel‑Flag muss synchron geprüft werden (V2‑F1). Alternative wäre eine asynchrone State‑Machine mit `QTimer` ohne lokalen Event‑Loop – weniger elegantes KISS, aber robuster. Die gewählte Lösung ist akzeptabel.

2. **Cancel-Flag-Check**: Ein einfaches Flag `_tune_convergence_cancelled` ist ausreichend. Es wird atomar vom GUI‑Thread gesetzt und in der gleichen Thread‑Schleife geprüft. Ein expliziter `QEventLoop.quit()` würde die Schleife sofort beenden, könnte aber einen unvollständigen Iterationsschritt hinterlassen. Das Flag mit early‑return nach Sende‑Befehl ist sicherer.

3. **ANT1 in Phase B**: Der einmalige `set_tx_antenna("ANT1")`-Aufruf zu Beginn der TUNE‑Phase (aus `_start_auto_tune_for_band_change` und `_on_tune_clicked`) ist ausreichend. Ein zusätzlicher Aufruf in jeder Iteration wäre reine Vorsorge, würde aber die Radio‑Kommunikation unnötig belasten und bei Verbindungsproblemen die Schleife stören. Hardware‑Pflicht ist erfüllt.

4. **PA-Schutz bei rfpower=1**: Wenn die Convergenz auf `rf=1` führt, sollte dieser Wert nicht gespeichert werden, da er nicht dem physikalischen Verhalten einer gesunden Antenne/PA für 10 W entspricht. Ein Plausibilitäts‑Check mit Grenzen `rf ∈ [3, 50]` für 10 W‑Ziel ist dringend zu empfehlen (siehe F5). Werte außerhalb führen zu Fallback `rf=10`.

5. **Tuner-Match-Phase A**: 10 s sind für einen LDG AT‑200 Pro typisch ausreichend. Scheitert der Match jedoch (z. B. an einem nicht resonanten Draht), liefert Phase B keine verlässliche Konvergenz. Daher ist eine SWR‑Kontrolle nach Phase A (siehe F6) notwendig: `swr > limit` → Phase B überspringen, kein Speichern.

6. **Krücken‑Formel**: `anchor_rf * (target_watt / anchor_watt) * 0.9` ist mathematisch korrekt. Mit `anchor_rf=14`, `anchor_watt=10`, `target_watt=50` ergibt sich 63 % – plausibel. Der Sicherheitsfaktor 0,9 dämpft konservativ, das ist gewollt.

7. **Krücken‑Faktor bei sehr niedrigen Anker‑Werten**: Bei `anchor_rf=3`, `target_watt=80` kommt 21,6 % heraus, was für 80 W höchstwahrscheinlich zu wenig ist. Da der Closed‑Loop jedoch im ersten QSO den echten Wert ermittelt und speichert, ist dieser Fall unkritisch – die erste Aussendung wird eventuell etwas leise, danach ist der Stützpunkt korrekt. Ein zusätzlicher Minimum‑Startwert ist nicht Mike’s Konzept und würde die Kalibrierungs‑Philosophie verwässern.

8. **Test-Coverage**: Die 16 geplanten Tests decken die Grundfunktionen und die V2‑Erweiterungen (T15, T16) gut ab. Zusätzlich sollten getestet werden:  
   - Cancel‑Race während Convergenz (in T15 bereits vorgesehen)  
   - Phase‑A‑Zeitüberschreitung mit SWR‑Check  
   - Krücke mit `anchor_rf=0`  
   - `_tune_post_swr_check` mit `_tune_converged_rf is None`  
   - `_tune_converge_to_target` mit sehr kurzer `duration_s`.  
   Diese Lücken können in einer späteren Test‑Iteration geschlossen werden.

9. **Backwards-Kompatibilität**: Die heute Mittag gespeicherten falschen `(band, 10, 10)`‑Einträge aus P54 werden beim nächsten TUNE‑Durchlauf mit dem echten konvergierten Wert überschrieben. Ein Migrations‑Skript ist nicht nötig, da die alten Einträge den Betrieb nicht blockieren – sie sind lediglich ungenau. Die In‑Place‑Korrektur ist ausreichend.

10. **Settings‑Tabelle Race**: Während der Convergenz (max 5 s) ist der alte Wert noch im Store. Ein öffnender User sieht also noch den veralteten Eintrag; das ist ein normaler Read‑State. Der Speichervorgang in `_tune_post_swr_check` erfolgt erst nach vollständig abgeschlossener Convergenz und ist kurz (atomarer Save). Danach zeigt die Tabelle den neuen Wert. Eine Race‑Condition mit korrupten Daten besteht nicht.

## Empfehlung
Push-Status: **FIX**  
KP (kritische Punkte): F1, F2, F3, F4 müssen vor Push korrigiert werden. F5 (Plausibilitäts‑Check) und F6 (SWR‑Prüfung vor Phase B) sind stark empfohlen und sollten als ORANGE‑Issues noch in diesem Zyklus umgesetzt werden. Nach Behebung der ROT‑Findings kann der Code freigegeben werden.
