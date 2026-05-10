[deepseek] ~42745 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=48678 out=9213 total=57891
## Kritischer Review von P22.PRESET-ATOMARITAET V2

### KRITISCH (Bug im Plan, muss in V3 raus oder anders)

- **K1 – `commit_with_ratio` zerstört staged bei Disk-Fehler**  
  `core/preset_store.py` (V2-Plan §5a): `self._staged.pop(key)` wird **vor** `_save_locked()` ausgeführt. Schlägt `_save_locked` fehl (Disk voll, Permission, etc.), ist der staged-Eintrag endgültig weg – die neuen Gain+Ratio-Werte sind unwiderruflich verloren. Der Aufrufer bekommt eine Exception, aber der half-state-artige Verlust ist nicht recoverable.  
  **Lösung: staged erst nach erfolgreichem `os.replace` aus dem Buffer entfernen.** Also staged kopieren, schreiben, bei Erfolg `pop`, bei Fehler staged liegen lassen.

- **K2 – Lifecycle-Cleanup: altes Band/Mode wird nicht ermittelt**  
  Plan §5e listet `_on_band_changed` und `_on_mode_changed` als `discard_staged`-Orte. Im Code von `ui/mw_radio.py` wird das neue Band als Argument übergeben (Z.~509). Das alte Band steht noch in `self.settings.band`. Der Plan spezifiziert nicht, dass man **vor** `self.settings.set("band", band)` das alte Band sichern muss, sonst discard auf dem neuen Band. Gleiches Problem in `_on_mode_changed` (Z.~307).  
  **Lösung: explizite Zeile „Vor dem Umschalten das alte Band/den alten Mode aus `settings.band`/`settings.mode` auslesen und `discard_staged` damit aufrufen."**

- **K3 – `_save_locked` Exception Handling killt ganze App**  
  `_save_locked` (Plan §5a) fängt Exception, löscht tmp-Datei und **re-raise**. Ein Fehler (z.B. `OSError` bei `os.replace`) wirft aus `commit_with_ratio` und `save_gain`/`save_ratio` eine Exception nach oben – bis in den Qt-GUI-Thread. Wenn der nicht gefangen wird (z.B. Signal-Handler), crasht die App.  
  **Sollte wenigstens `log.error` + `return False` oder im GUI-Thread gefangen werden. Ein unbemerkter Absturz ist für ein Hobby-Tool inakzeptabel.**

- **K4 – `_handle_phase3_stall` ist undefiniert**  
  Plan §5d verweist auf eine Methode `_handle_phase3_stall(band, ft_mode, scoring)`, die je nach Q1-Antwort implementiert werden soll. Aber **es gibt keinen Rumpf oder default** – im aktuellen Code der Dateien existiert sie nicht. Ohne konkrete Implementierung wird `tick_stall_check` → True einfach einen `AttributeError` werfen.  
  **Lösung: in V3 entweder einen Dummy mit `pass` oder den Fallback aus Q1(b) direkt als Implementierung festlegen.**

### SOLLTE (Verbesserung empfohlen)

- **S1 – `is_valid_gain` bricht fremde Importe**  
  `is_valid_gain` wird auch von externen Modulen genutzt (z.B. `settings.get_normal_preset`?), aber v. a. von `_assess_gain` in `mw_radio.py`. Die Änderung auf `"ratio" in entry` macht alle alten Einträge **ohne Ratio-Feld** ungültig – auch wenn sie nur im Normal-Mode verwendet werden (z.B. ein Preset das nie Diversity sah). Der Plan sagt, Normal-Mode bleibt bei `save_gain`, das kein Ratio setzt. Aber `_assess_gain` wird nur im Diversity-Pfad aufgerufen, also harmlos. **Trotzdem: Klarstellen in der Doku, dass `is_valid_gain` nur für Diversity-Store gedacht ist. Ein Kommentar im Code hilft.**

- **S2 – Test T6/T7 nutzen E2E mock-heavy**  
  T6 testet den gesamten Pfad von `_on_dx_tune_accepted` bis `stage_gain`. Dafür müssen viele Qt-Signale, Dialoge, Radio gemockt werden. Das testet eher die Mock-Zusammenstellung als den Code. Besser: `stage_gain`- und `commit_with_ratio`-Aufrufe isoliert prüfen (wie T1-T5), und die Integration in `_on_dx_tune_accepted` mit einem Spy auf `store.stage_gain` abdecken. Der Plan sollte auf reine Unit-Tests setzen, nicht auf E2E mit vielen Mocks.

- **S3 – Stall-Detector: `_stall_counter` Reset im QSO-Fall?**  
  Wenn während Phase 3 ein QSO beginnt (selten, aber möglich durch `_on_cycle_start` – dort wird bei active QSO die Antenne forced, aber Phase bleibt measure), wird `tick_stall_check` weiter aufgerufen, aber `_measure_step` inkrementiert nicht (weil `record_measurement` im QSO unterdrückt? Nein, bei active QSO wird die Antenne nicht gewechselt? Im Code `_on_cycle_start` wird bei `_in_qso` eine präferierte Antenne gesetzt, aber `record_measurement` wird trotzdem in `_handle_diversity_measure` aufgerufen wenn `was_phase == "measure"`. Also inkrementiert). Sollte passen. **Trotzdem: Kommentar im Plan, dass QSO während Phase 3 den Counter nicht stört.**

- **S4 – Adaptiv-Stop discard in `mw_cycle.py` ist redundant**  
  Plan §5c: bei `_early_stopped` wird `_store.discard_staged()` aufgerufen. Aber `_was_early_stopped` wird in `_check_phase3_early_stop` gesetzt, **bevor** `_evaluate` aufgerufen wird. `_evaluate` setzt `_phase = "operate"`. Der normale Path in `_handle_diversity_measure` (nach `_evaluate`) prüft `if not _early_stopped: ...` und commit sonst discard. Das ist korrekt. **Aber:** Der discard wird zweimal aufgerufen? Einmal in `_check_phase3_early_stop`? Nein, `_check_phase3_early_stop` ruft `_evaluate` und return, dann geht `record_measurement` zu Ende und in `_handle_diversity_measure` wird der discard ausgeführt. Also einmal. Ok.

### KOENNTE (Optional, schöneres Design)

- **C1 – `_staged` als komplexer Typ**  
  Statt eines einfachen dicts könnte `_staged` als `dict[str, dict]` mit `band_mode`-Key bleiben. Das ist aber bereits so geplant. Keine Änderung nötig.

- **C2 – `tick_stall_check` in `_on_cycle_decoded` eher am Anfang**  
  Aktueller Plan: nach `record_measurement` aufrufen. Besser direkt nach `pop_diversity_queue`, um den Counter so früh wie möglich zu starten. Ist Geschmackssache.

- **C3 – `_handle_phase3_stall` als Strategy-Pattern**  
  Q1 könnte man als Callback-parametrisierbar machen, damit Mike später umschalten kann. Overengineering für Hobby-Tool.

### Q1/Q2/Q3 Antworten

- **Q1 – Stall-Fallback: (b) Disable-Diversity**  
  Begründung: Kein Fake-Wert, Mike behält Kontrolle, klare Aktion. Option (a) ist risikoreich wenn 50:50 bei Hardware-Fehler aktiv bleibt. (c) ist frustrierend (hängt wie heute). (b) hat den geringsten Schaden und ist verständlich.

- **Q2 – Bandwechsel mid-Phase-3: (a) Discard sofort**  
  Begründung: KISS. Bandwechsel während Messung ist selten. Memory-Wachstum und stale-Gain-Risiko sind höher als der paar Sekunden Gewinn durch Stage-Keep.

- **Q3 – Adaptiv-Stop ohne Persist: Bestehenden Schutz behalten**  
  Begründung: Weniger Daten = potentiell ungenauer. Mike kann bei Bedarf mit vollem Messdurchlauf arbeiten. Wenn oft Adaptiv-Stop auftritt, sollte die Hardware-Ursache (schwaches Signal) gefixt werden, nicht der Cache.

### KISS-Bewertung

Der Plan ist **angemessen schlank** für ein Hobby-Tool. Die Stage/Commit-Architektur ist leichtgewichtig, der Stall-Detector simpel. Die Zahl der Änderungen (8 Dateien) ist überschaubar. Einziger overengineerter Punkt: der atomic write mit `tempfile` + `os.replace` – das ist Standard-Pattern aber für ein Tool das nur von einem User lokal läuft ein bisschen übertrieben. Aber akzeptabel.

**Gesamteindruck:** V2 ist solide, aber die drei KRITISCH-Punkte (K1-K3) müssen vor Implementierung behoben werden. K4 ist ein Design-Lücke. Tests sind ausreichend, aber S2 verhindert mock-heavy Anti-Pattern.
