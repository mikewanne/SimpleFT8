[deepseek] ~12051 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=14544 out=11906 total=26450
## Kritik am QOL-Bundle-Prompt (V2)

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---|---|---|---|
| **Risiko** | **Widerspruch: Archiv wird „nicht gelöscht“ und doch gelöscht**<br>AK2 sagt: „einmalig archiviert, **nicht gelöscht**“. Später heißt es: „Nach 7 Tagen löscht Cleanup das Archiv-File mit (akzeptiert)“ – das ist ein logischer Bruch. Mike könnte sich auf die erste Aussage verlassen und Daten verlieren. | *Prompt* – AK2 Log-Rotation | Klarstellen: Entweder das Archiv dauerhaft behalten (z.B. in Unterordner `archive/` ohne Cleanup) oder die Aussage von „nicht gelöscht“ auf „zunächst nicht gelöscht, aber nach 7 Tagen gelöscht“ ändern. |
| **Risiko** | **T6/T7: `_saved` wird nicht initialisiert – Tests hängen von Benutzerdaten ab**<br>Die Tests rufen `set_mode("FT8","20m")` auf, aber `_load_for_current_key()` greift auf die echte `dt_corrections.json` zu. Existiert dort kein Eintrag, ist `saved_val=0.0` – Dedup funktioniert anders als erwartet. Das Test-Ergebnis ist umgebungsabhängig. | `tests/test_p_bundle_qol.py` – T6, T7 | Vor Test `ntp_time._saved` mit einem bekannten Wert befüllen (z.B. `_saved["FT8_20m"] = 0.65`) und `_last_logged_load` zurücksetzen. Dann kann Dedup deterministisch geprüft werden. |
| **Risiko** | **Fehlender Fallback bei Symlink-Erstellung**<br>Im Prompt ist der Fallback („direktes Datei-Open ohne Symlink“) nur als Textnotiz erwähnt, nicht im Code. `os.replace` auf fehlgeschlagenen Symlink führt ohne try/except zum App-Abbruch. | `core/log_setup.py` – `setup_main_log()` | Symlink-Erstellung in try/except wrapper; bei Fehler Warnung ausgeben und `open(target, "a")` ohne Symlink. |
| **Verbesserung** | **Redundantes drittes Element im Dedup-Tupel**<br>`(key, saved_val, saved_val != 0.0)` – der Boolean ist unnötig, weil `saved_val == 0.0`` immer den Print „Kein gespeicherter Wert“ auslöst. `(key, saved_val)` allein reicht für die Dedup-Entscheidung. | `core/ntp_time.py` – Zeilen um `_last_logged_load` | Auf `(key, saved_val)` vereinfachen. Spart eine Operation und ist lesbarer. |
| **Hinweis** | **`datetime.utcnow()` veraltet**<br>Ab Python 3.12 wird `datetime.utcnow()` mit Deprecation-Warnung beendet. Das Projekt nutzt bereits `datetime.now(timezone.utc)` an anderen Stellen? (z.B. debug_log.py tut das nicht). | `core/log_setup.py` – `dated_log_filename`, `cleanup_old_main_logs` | Ersetzen durch `datetime.now(timezone.utc)`, analog zu den FT8-Zeitkonventionen. |
| **Hinweis** | **Source-Check-Test T1 fragil**<br>Test prüft String-Muster in `main.py`. Jede Formatierungsänderung (andere Einrückung, Kommentarumbruch) bricht den Test. | `tests/test_p_bundle_qol.py` – T1 | Alternativ einen funktionalen Test: `import setproctitle` mocken und prüfen, dass `main.py` ohne Fehler startet. Für ein KISS-Projekt akzeptabel, aber auf Dauer wartungsintensiv. |
| **Hinweis** | **Keine Fehlerbehandlung bei fehlendem `_LOG_DIR`**<br>In `setup_main_log()` wird `_LOG_DIR.mkdir(parents=True, exist_ok=True)` implizit vorausgesetzt. Wenn das Verzeichnis nicht angelegt werden kann (Permission, volle Platte), schlägt der gesamte App-Start fehl. | `core/log_setup.py` – `setup_main_log()` | Ein try/except um das `mkdir` und die Dateiöffnung legen, bei Fehler eine Warnung ausgeben und Logging deaktivieren (analog zu `setproctitle`-Handling). |

### Zusammenfassung der Kernkritik

Der Prompt ist insgesamt gut durchdacht, KISS-konform und modulartig aufgebaut. Die drei schwerwiegendsten Punkte sind:

1. **Widerspruch Archiv-Haltbarkeit** – führt zu falschen Erwartungen bei Mike.  
2. **Test-Abhängigkeit von Benutzerdaten** – macht die Test-Suite nicht reproduzierbar.  
3. **Fehlender Fallback beim Symlink** – kann unter seltenen macOS-Bedingungen zum Absturz führen.

Die weiteren Punkte (deprecated API, redundanter Boolean, fragile Tests) sind eher kosmetischer Natur und mindern die Robustheit des Bundles nicht gravierend. Der Prompt bleibt trotz dieser Kritik eine solide Vorlage – die offenen Stellen sind in einer V3 einfach klärbar.
