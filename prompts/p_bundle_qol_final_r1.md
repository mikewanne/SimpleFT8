[deepseek] ~12141 Tokens, 5 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=14072 out=2340 total=16412
## Bewertung Bundle-A-Implementierung (v0.97.12)

### Übersicht

| Feature | Implementiert | Tests | Status |
|---------|---------------|-------|--------|
| P43 – `setproctitle` | `try/except` in `main.py` + `start_simpleft8_nokill.py` | T1 (Source-Check) | ✅ sauber |
| P20 – Log-Rotation | `core/log_setup.py` inkl. Symlink, Archiv, Cleanup | T2–T6 | ✅ solide |
| P18 – DT-Print-Dedup | `_log_load_dedup` + `_last_logged_load` in `ntp_time.py` | T7–T8 | ✅ funktionsfähig |

---

### 1. Korrektheit aller 5 Änderungen + 8 Tests

**P43 (setproctitle)**:  
- `main.py` verwendet `try: import setproctitle; setproctitle(...)` – korrekt, App läuft auch ohne Modul.  
- `start_simpleft8_nokill.py` identisch, aber Process-Title `SimpleFT8 (Ferienhaus)` – Absicht.  
- T1 prüft Reihenfolge `import` vor `except ImportError` – bestanden.  

**P20 (Log-Rotation)**:

| Teilfunktion | Korrekt | Anmerkung |
|-------------|---------|-----------|
| `dated_log_filename` | ✅ | UTC-basiert, Format stimmt (T2) |
| `cleanup_old_main_logs` | ✅ | Filtert nur `simpleft8-YYYY-MM-DD.log`, löscht > keep_days (T3) |
| `_archive_legacy_logfile` | ✅ | Verschiebt reguläre Datei in `archive/` mit Counter (T4) |
| `_setup_symlink` | ✅ | Atomar via `os.symlink` + `os.replace`, relativer Link (T5) |
| `setup_main_log` | ✅ | Vollständiger Ablauf, Fallback bei OSError (T6) |

**Besonders gut**: Fallbacks sind mehrfach abgesichert (symlink-Fehlschlag → trotzdem datierte Datei öffnen, kompletter Crash → stdout als Ersatz).

**P18 (DT-Print-Dedup)**:
- `_log_load_dedup` speichert `(key, saved_val)` als Marker. Nur wenn sich dieser ändert, wird geprintet.  
- Wird in `set_mode` und `set_band` aufgerufen – vermeidet doppelte Prints beim App-Start.  
- T7/T8 prüfen Dedup und erneutes Loggen bei Wechsel – beide bestanden.  

**Tests (8 insgesamt)**:  
- Alle 8 Tests sind sinnvoll, decken die kritischen Pfade ab.  
- Keine externen Abhängigkeiten (außer `tmp_path`).  
- T1 (Source-Check) könnte bei Code-Refactoring später brechen, aber aktuell ok.  

---

### 2. Bugs / Sideeffects

#### Symlink-Atomicität  
**Risiko: sehr gering**.  
- `_setup_symlink` erzeugt zuerst `simpleft8.log.tmp` (relativer Symlink), dann `os.replace` → atomarer Austausch auf Dateisystemebene.  
- Falls `os.symlink` oder `os.replace` fehlschlagen, wird der tmp-Link gelöscht und `False` zurückgegeben.  
- **Einziger Schwachpunkt**: Wenn die App während `os.replace` abstürzt, bleibt `simpleft8.log.tmp` liegen. Der Code räumt das beim nächsten Start auf (`tmp_link.unlink()`). Das ist aber kein Bug, sondern ein geplanter Temp-File-Cleanup.  
- **Empfehlung**: Den `tmp_link` beim nächsten Start überprüfen – ist bereits implementiert.

#### Archiv-Migration  
**Risiko: gering**.  
- `_archive_legacy_logfile` verschiebt eine reguläre `simpleft8.log` (kein Symlink) nach `archive/simpleft8-pre-rotation-YYYY-MM-DD.log`.  
- **Potenzielle Race**: Wenn zwei Instanzen gleichzeitig starten, könnten beide die Datei verschieben wollen. Da `_archive_legacy_logfile` nach `acquire_single_instance_lock` ausgeführt wird (in `setup_main_log`, das von `main.py` nach dem Lock gerufen wird), ist das ausgeschlossen.  
- **Counter-Suffix** verhindert Überschreiben, falls am selben Tag schon archiviert wurde.  

#### Fallback-Verhalten  
- Bei OSError in `setup_main_log` wird `fallback_path` (`simpleft8.log` ohne Rotation) geöffnet und in stderr dokumentiert.  
- **Sideeffect**: Die `_archive_legacy_logfile` wird dann nicht ausgeführt – das ist korrekt, da der Fallback-Pfad ja die alte Datei ist.  
- **Kein Log-Verlust**: Im Worst-Case (auch Fallback-Open fehlschlägt) wird `sys.__stdout__` zurückgegeben – die App läuft ohne Datei-Log weiter.  

#### P18 Dedup in Verbindung mit `_load_saved`  
- `_load_saved` wird beim Modul-Import aufgerufen, danach `set_mode`/`set_band` (durch `mw_radio.py`).  
- Dadurch gibt es genau einen Print pro (mode, band) beim Start, auch wenn `mw_radio.py` dreimal `set_mode` aufruft.  
- **Edge Case**: Wenn der gespeicherte Wert 0.0 ist, printet `_log_load_dedup` `"Kein gespeicherter Wert, starte bei 0"` – und das nur einmal.  
- Kein Spam.  

---

### 3. KISS-Konformität

| Komponente | Wertung | Begründung |
|------------|---------|------------|
| P43 | 👍 **KISS** | Minimaler `try/except`, keine zusätzliche Abstraktion. |
| P20 | ⚠️ **Akzeptabel** | Log-Rotation ist nötig; Implementierung ist mit 8 Funktionen und ~100 Zeilen etwas groß, aber jede Funktion hat eine klare Verantwortung. Symlink-Ansatz ist Standard. |
| P18 | 👍 **KISS** | Einfaches Dictionary-Tupel als Cache, 4 Zeilen. |

**Gesamteindruck**:  
Die Änderungen bleiben nahe am Code, keine überflüssigen Abstraktionen. Einzig `_setup_symlink` hätte man vielleicht mit `pathlib` in eine Zeile packen können, aber so ist es lesbarer.

---

### 4. Verbleibendes Risiko

| Risiko | Eintrittswahrsch. | Auswirkung | Maßnahme |
|--------|-------------------|------------|----------|
| OS X unterstützt `os.symlink` nicht (z.B. exFAT) | sehr gering | Fallback greift → log ohne Symlink | ✅ Code hat Fallback |
| Zwei Instanzen schreiben gleichzeitig in archivierte Datei | nahezu 0 | Lock verhindert Doppelstart | ✅ Single-Instance-Lock vor setup_main_log |
| `_archive_legacy_logfile` verschiebt Datei nach `replace`, danach ist sie weg – falls `setup_main_log` crasht | gering | Einmaliger Verlust der alten `simpleft8.log` (nicht datiert) | akzeptabel, da die App danach neu startet und eine neue dateierte Datei erzeugt |
| Symlink bleibt nach `os.replace` ungültig, wenn das Target gelöscht wird (z.B. durch externes Skript) | mittel | symlink wird "dangling" – Logging funktioniert dann über datierte Datei, nicht über den Symlink | Der Code öffnet die datierte Datei direkt, der Symlink dient nur dem Benutzer. Ein Dangling-Symlink ist kosmetisch, kein Datenverlust. |

**Fazit**: Kein kritisches Restrisiko. Die Fehlerabsicherung ist robust.

---

### 5. Push freigegeben?

**Ja, Push freigegeben.**  
- Alle Tests grün (+8).  
- Kein Bug oder Sideeffect identifiziert, der den Betrieb gefährdet.  
- Code ist sauber dokumentiert, KISS eingehalten.  
- Fallbacks decken seltene Fehlerzustände ab.  

**Empfehlung**:  
Nach dem Push einen kurzen Blick in die Live-Logs werfen, um sicherzustellen, dass die Rotation auf dem Zielsystem (macOS) ordnungsgemäß funktioniert (Symlink-Auflösung, Archivierung). Ansonsten keine weiteren Änderungen nötig.
