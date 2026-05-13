[deepseek] ~36557 Tokens, 5 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=40148 out=6149 total=46297
## Bundle C — Final Codereview

### KRITISCH (muss vor Push gefixt)

- **KP-1 (Mode-Sync)**: `PSKReporterClient` hat **keine Methode zum Ändern des Modes** nach Initialisierung.  
  `_reset_psk_polling_on_change` setzt nur das Backoff zurück, aber der interne `self._mode` bleibt auf dem ursprünglichen Wert (z.B. "FT8"). Nach einem Mode-Wechsel (z.B. FT8 → FT4) werden weiterhin Spots für den **alten Mode** abgefragt – der User sieht keine zu seinem aktuellen Modus passenden PSK-Daten.  
  **Betroffen**: beide Pfade (Statusbar im `_psk_worker` und `PSKReporterClient` in der Karte).  
  **Fix**: Füge `set_mode(mode: str)` zu `PSKReporterClient` hinzu, die `self._mode = mode.upper()` setzt und den Cache zurücksetzt/ungültig macht. Rufe diese in `_reset_psk_polling_on_change` auf, sowohl für den Statusbar-Client als auch den Karten-Client.

---

### SOLLTE (wäre besser vor Push zu fixen)

- **S-2 (Backoff-Wakeup)**: `reset_backoff` interrruptiert den laufenden Sleep im Worker-Thread nicht. Aktuell läuft der Sleep in 1s-Ticks, aber das Intervall (`current_interval_s`) wird erst **nach Ablauf des aktuellen Sleeps** neu gelesen. Im Worst-Case (max_s=600s) sieht der User nach einem Bandwechsel bis zu 10 Minuten alte Daten.  
  **Empfehlung**: Ein `threading.Event` in `_Backoff` und `_run_loop` einführen, das beim Reset gesetzt wird. Der Sleep-Check prüft dann `event.wait(timeout=1.0)` statt `time.sleep(1.0)` und bricht sofort ab.  
  **Aufwand gering – große UX-Verbesserung**.

- **S-6 (Sort-Key Legacy)**: In `_set_sort("time")` werden Messages ohne `_slot_start_ts` per `float(utc_display)` sortiert. `utc_display` ist ein HHMMSS-String (z.B. "120000"). Das ergibt 120000.0 – ein Wert, der **nicht mit Unix-Timestamps vergleichbar** ist (z.B. 1700000 für einen aktuellen Slot). Dadurch können alte Einträge (gestern) fälschlich als "neuer" erscheinen als frische, slot-basierte Messages.  
  **Empfehlung**: Für Legacy-Messages aus `_utc_display` einen absoluten Timestamp konstruieren: `heutiges_Datum + HHMMSS → datetime → timestamp`. Oder klar stellen, dass Mixed-Type nicht vorkommt und einen AssertionError werfen, um versteckte Inkonsistenzen aufzudecken.

---

### KOENNTE (Hinweise für zukünftige Iterationen)

- **K-5 (Spezifikationslücke)**: `_populate_row` hatte den gleichen `_slot_start_ts`-Bug wie `add_message`, wurde aber erst beim Implementieren entdeckt. Lesson: In V2/V3 sollten alle Codepfade, die eine Zeitangabe erzeugen, systematisch aufgelistet werden. Zukünftige Reviews besser strukturieren.

- **K-7 (Testtiefe)**: Die P13-Tests verwenden minimale `SimpleNamespace`-Stubs und decken nur den UTC-Pfad ab. Die volle `_populate_row`-Logik (km, country, Ant, Farben) wird nicht getestet. Ein Integrationstest mit einem vollständigeren `FT8Message`-Mock wäre wünschenswert, aber für den konkreten Bug ausreichend.

- **K-8 (Memory-Lesson)**: Im Team-Wissen festhalten: **"CPython GIL macht read-modify-write nicht atomar"**. V2 schrieb fälschlich, dass der GIL `current_s *= factor` schützt. R1 entdeckte den Fehler. Lektion in das Feedback-Dokument aufnehmen.

---

### Weitere Anmerkungen (nicht Teil des Schemas)

- **Test-Coverage**: `test_p10_psk_backoff_reset.py` testet die Thread-Safety gut. Es fehlt jedoch ein Test, der den Mode-Wechsel im Client überprüft (z.B. `client.set_mode()` + anschließender Fetch). Sollte nach Fix ergänzt werden.
- **Doku**: Der Docstring von `reset_backoff` erwähnt "worst-case 10 Min Latenz". Das ist akkurat für den aktuellen Code, aber nach S-2 würde sich die Latenz auf <1s reduzieren.

---

### Push-Freigabe: **NEIN**

**Begründung**: Der kritische Mode-Bug (KP-1) führt dazu, dass nach einem Mode-Wechsel **keine korrekten PSK-Spots** geladen werden – das Kern-Feature von P10 (sofortiger Re-Fetch bei Mode/Band-Wechsel) ist damit defekt. Ohne diesen Fix wäre der Push ein Rückschritt. Nach Implementierung von `set_mode()` und Anpassung der Helper kann neu bewertet werden. Die SOLLTE-Punkte (S-2, S-6) sind optional, aber empfehlenswert.
