[deepseek] ~35675 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=40869 out=7275 total=48144
| Schwere | Finding | Datei:Zeile | Empfehlung |
|---|---|---|---|
| **KRITISCH** | Bestehende P35-Bug-E-Tests (`test_bandpilot_skips_when_current_is_normal`, `test_bandpilot_rejects_normal_target`) testen explizit das alte Block-Verhalten. Nach Entfernung der Skip-Blöcke werden sie **fehlschlagen**, da Bandpilot jetzt auch bei `current="normal"` agiert. Der Plan ignoriert diese beiden Tests. | `tests/test_mw_radio_bandpilot.py` (letzte beiden Tests) | Diese Tests **löschen** (da das Block-Verhalten nicht mehr existiert) oder in positive Tests umwandeln, die bestätigen, dass Bandpilot jetzt in `"normal"` richtig reagiert (z.B. dass `_bandpilot.recommend` aufgerufen wird, Entscheidung gefällt wird). Push blockiert, solange diese Tests nicht angepasst sind. |
| **SOLLTE-FIX** | In `_set_rx_mode_direct(target="normal")` wird `_disable_diversity()` aufgerufen, das bereits `_apply_normal_mode()` ausführt. Direkt danach folgt ein **zweiter Aufruf** von `_apply_normal_mode()` und `set_rx_mode("normal")`. Doppelaufrufe können zu unerwünschten Nebeneffekten führen (z.B. mehrfaches Setzen von TX-Frequenz, UI-Updates). Obwohl vermutlich idempotent, ist es unsauber und bricht das Prinzip der einzigen Verantwortlichkeit. | `ui/mw_radio.py` `_set_rx_mode_direct` (ca. Z. 733–745) | Entweder den gesamten `if target == "normal":`-Block ersetzen durch `self._disable_diversity()` und danach `return` (da `_disable_diversity` bereits alles erledigt), oder `_disable_diversity()` so umbauen, dass es kein `_apply_normal_mode()` aufruft, und den Aufruf nur im `_set_rx_mode_direct` vorhalten. |
| **SOLLTE-FIX** | In `_apply_bandpilot_auto` wird bei TX-Verzögerung `target` in `_bandpilot_pending` gespeichert. Der Konsistenz-Check in `_on_bandpilot_tx_finished` prüft nur **Band**, nicht den **aktuellen RX-Modus**. Wenn der Benutzer zwischenzeitlich manuell den Modus wechselt (z.B. von `normal` auf `diversity_dx`), wird der pending-Wechsel trotzdem ausgeführt und überschreibt den manuellen Modus. Altes Verhalten war durch den Normal-Block geschützt, jetzt kann dieser Fall eintreten. | `ui/mw_radio.py` `_on_bandpilot_tx_finished` | Füge einen zusätzlichen Check hinzu: vergleiche `current_mode` zum Zeitpunkt der Ausführung mit dem `current`, das ursprünglich in `_maybe_apply_bandpilot` verwendet wurde. Speichere dazu auch `current` im pending-Tupel. Falls abweichend → pending verwerfen. (Alternativ als **KOENNTE** einstufbar, da selten.) |
| **KOENNTE** | Der neue Test T6 (TX-Verzögerung mit Normal als Target) ist geplant, aber es gibt noch keinen Test für den Fall, dass `current="normal"` und der Recommender `None` zurückgibt (unzureichende Daten). Der bestehende Test `test_maybe_apply_bandpilot_silent_when_insufficient_data` wird laut Plan auf `current="normal"` umgestellt – das ist ausreichend, aber ein eigener expliziter Test (z.B. `test_normal_insufficient_data_shows_statusbar`) würde die Abdeckung erhöhen. | `tests/test_p46_bandpilot_normal.py` (noch nicht existent) | Ergänze einen Test, der sicherstellt, dass bei `current="normal"` und `rec=None` `_show_bandpilot_insufficient_data` aufgerufen wird und kein Wechsel stattfindet. |
| **HINWEIS** | Der doppelte `_apply_normal_mode`-Aufruf in `_set_rx_mode_direct` könnte ein Relikt aus der Zeit sein, bevor `_disable_diversity` den Normal-Modus korrekt gesetzt hat. Da der Code jetzt geändert wird, bietet sich eine Gelegenheit zur Bereinigung. | `ui/mw_radio.py` `_set_rx_mode_direct` (ca. Z. 733–745) | Siehe SOLLTE-FIX oben. |
| **HINWEIS** | Der Plan verweist auf die bestehenden P35-Bug-E-Tests (die 4 Workaround-Tests) und will sie auf `current="normal"` umstellen. Das ist korrekt. Allerdings wird nicht erwähnt, dass die beiden separaten P35-Bug-E-Tests (siehe KRITISCH) ebenfalls angepasst werden müssen. | `tests/test_mw_radio_bandpilot.py` (gesamte Datei) | Nach dem Entfernen der Skip-Blöcke muss die gesamte Test-Suite durchlaufen – die beiden speziellen Tests müssen vorher gelöscht oder umgeschrieben werden. |
| **HINWEIS** | Der Bandpilot-Wechsel zu Normal im Auto-Modus löst einen Toast aus, der "Normal gewählt" zeigt. Der Toast verschwindet nach 5 Sekunden. Das ist konsistent mit den anderen Toasts. Keine Änderung nötig. | — | Beibehalten. |
| **HINWEIS** | Der Manual-Dialog erlaubte bereits vor P46 die Auswahl von Normal (weil nur `_apply_bandpilot_auto` blockte, nicht der Dialog-Pfad). Der neue T5 testet dies explizit. Das ist gut. | — | OK. |

---

## Gesamtbewertung: 8 / 10

Der Plan ist durchdacht, basiert auf einer sauberen Analyse (V1+V2) und deckt die wichtigsten Aspekte ab. Die Code-Änderung selbst ist minimal und risikolos, die Tests sind umfassend geplant (T1–T6).

### Entscheidung: **Plan muss erst X machen**

Bevor Code geschrieben wird, müssen folgende Punkte adressiert werden:

1. **KRITISCH:** Die beiden P35-Bug-E-Tests (`test_bandpilot_skips_when_current_is_normal`, `test_bandpilot_rejects_normal_target`) müssen im Plan explizit als zu **löschend** oder **umzuschreibend** aufgeführt werden. Andernfalls schlagen sie nach dem Patch fehl und brechen die CI.

2. **SOLLTE-FIX:** Der doppelte `_apply_normal_mode`-Aufruf in `_set_rx_mode_direct` sollte vereinheitlicht werden. Obwohl nicht blockierend, ist das ein Code-Smell, der bei der Gelegenheit behoben werden sollte.

Wenn diese beiden Punkte im Plan korrigiert werden (V3), kann der Code ohne Bedenken geschrieben werden.
