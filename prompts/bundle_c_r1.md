[deepseek] ~60632 Tokens, 5 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=67196 out=9271 total=76467
## Review-Ergebnis Bundle C V2 — Kritische Analyse

### Fundliste (Findings)

#### KP‑1 (KRITISCH) — `rx_panel.py`: `_slot_start_ts` wird ignoriert
- **Stelle**: `rx_panel.py` Zeile ~292 (in `add_message`) sowie die Sortierlogik in `_set_sort` (ca. Z. 500)
- **Befund**: V2-AK1 (P13) fordert, dass die UTC-Spalte die Slot-Boundary anzeigt, wenn `msg._slot_start_ts` gesetzt ist. Der Decoder setzt `_slot_start_ts` (`decoder.py Z. ~347`), aber `add_message` und `_set_sort` prüfen nur `_utc_display`/`_utc_str`, die jedoch **nicht** gesetzt werden. Stattdessen fällt der Code auf `time.strftime("%H%M%S", time.gmtime())` zurück, das immer die aktuelle Wall-Time liefert. Die AK sind nicht erfüllt.
- **Empfehlung**: Ersetze den Fallback durch eine Priorisierung:
  ```python
  if getattr(msg, '_slot_start_ts', None):
      utc_str = time.strftime("%H%M%S", time.gmtime(msg._slot_start_ts))
  else:
      utc_str = getattr(msg, '_utc_display', None) or getattr(msg, '_utc_str', None) or time.strftime("%H%M%S", time.gmtime())
  ```
  Entsprechend muss `_set_sort` (mode="time") ebenfalls auf `_slot_start_ts` zurückgreifen.

#### KP‑2 (KRITISCH) — `psk_reporter.py`: Thread‑unsafe `_Backoff`
- **Stelle**: `psk_reporter.py`, Klasse `_Backoff` – Methode `fail()` (ca. Z. 155–158) und `reset()` (ca. Z. 152)
- **Befund**: `fail()` liest `self.current_s`, multipliziert und schreibt zurück (read‑modify‑write). Wird `reset()` (von einem anderen Thread) zwischen Read und Write aufgerufen, kann der alte Wert zurückgeschrieben werden → Backoff springt auf einen inkorrekten Wert. Die Behauptung „CPython GIL macht es atomar“ ist falsch, da hier mehrere Bytecode-Instruktionen beteiligt sind.
- **Empfehlung**: Führe einen einfachen Lock (`threading.Lock()`) ein und schütze beide Methoden:
  ```python
  def fail(self) -> float:
      with self._lock:
          self.current_s = min(self.max_s, self.current_s * self.factor)
          return self.current_s

  def reset(self):
      with self._lock:
          self.current_s = self.base_s
  ```

#### KP‑3 (KRITISCH) — `psk_reporter.py`: `BACKOFF_MAX_S` nicht geändert
- **Stelle**: `psk_reporter.py` Zeile `BACKOFF_MAX_S = 3600` (ca. Z. 17)
- **Befund**: V2‑Plan fordert `BACKOFF_MAX_S = 600`. Der Code zeigt noch den alten Wert. Ohne Änderung wird der Backoff nicht auf 10 Minuten begrenzt.
- **Empfehlung**: `BACKOFF_MAX_S = 600` setzen und ggf. eine Konstante `PSK_BACKOFF_MAX_S` definieren.

#### S‑1 (SOLLTE‑FIX) — `psk_reporter.py`: Fehlende `reset_backoff()`-Methode
- **Stelle**: `psk_reporter.py`, Klasse `PSKReporterClient` (nach Zeile ~230)
- **Befund**: V2‑AK2 fordert eine public `reset_backoff()` Methode. Der Client hat nur `_backoff.reset()` (privat). Externer Zugriff (z.B. aus `mw_radio`) wäre nicht möglich.
- **Empfehlung**: Füge eine delegierende Methode hinzu:
  ```python
  def reset_backoff(self):
      self._backoff.reset()
  ```

#### S‑2 (SOLLTE‑FIX) — `main_window.py` fehlt in Backup-Liste
- **Stelle**: V2‑Plan „Backup‑Strategie“ nennt nur 3 Dateien. Der Code‑Eingriff für P10‑Fix‑B (`_psk_timer.start(0)`) muss in `ui/main_window.py` erfolgen (im `_on_band_changed`/`_on_mode_changed`‑Handler).
- **Empfehlung**: Ergänze `ui/main_window.py` in der Backup‑Liste und stelle sicher, dass die Änderungen dort dokumentiert sind.

#### S‑3 (SOLLTE‑FIX) — Statusbar‑Pfad hat kein Backoff
- **Stelle**: `ui/main_window.py`, `_psk_worker` (ca. Z. 940–980)
- **Befund**: Der Statusbar‑Pfad pollt bei Server‑Outage stur alle 5 Minuten weiter. Die Last auf dem PSK‑Server wird nicht reduziert. V2 adressiert nur den Karten‑Pfad. Konsistenz und Höflichkeit gegenüber dem öffentlichen Server sprechen für einen einfachen Backoff.
- **Empfehlung**: Führe im `_psk_worker` einen einfachen Backoff ein (z.B. nach Fehler Interval auf max 10 Min erhöhen, bei Erfolg zurücksetzen). Alternativ akzeptieren, falls Mike die zusätzliche Last für unkritisch hält (dann HINWEIS).

#### K‑1 (KOENNTE) — `_psk_timer.start(0)`‑Race vermeiden
- **Stelle**: `ui/main_window.py`, `_fetch_psk_stats` (ca. Z. 920) und `_on_band_changed`
- **Befund**: Bei schnellem Bandwechsel kann ein alter Worker noch laufen, während ein neuer gestartet wird. Beide rufen `update_psk_stats` auf. Das führt zu kurzzeitiger Inkonsistenz, aber keinem schweren Bug.
- **Empfehlung**: Optional einen `_psk_busy`‑Flag setzen und neuen Start verwerfen, wenn noch ein Worker läuft. Mike’s KISS‑Prinzip spricht dagegen – hier eher belassen.

#### K‑2 (KOENNTE) — Slot‑Boundary‑Rundung prüfen
- **Stelle**: `rx_panel.py` (nach Einbau von `_slot_start_ts`)
- **Befund**: `time.gmtime(slot_ts)` führt bei Float‑Werten mit Sub‑Sekunden zu einer ungewollten Abrundung. Da `_slot_start_ts` aus `time.time()` und `cycle_pos` berechnet wird, ist das Risiko minimal, kann aber bei Float‑Artefakten zu einer Anzeige der vorherigen Sekunde führen.
- **Empfehlung**: Verwende `time.gmtime(int(slot_ts))` oder `time.gmtime(round(slot_ts))`, um auf die nächste ganze Sekunde zu runden (bzw. zum Slot‑Start zu gelangen).

#### H‑1 (HINWEIS) — `_utc_display` wird nirgends gesetzt
- **Stelle**: `rx_panel.py` Zeile ~292
- **Befund**: Der Fallback auf `_utc_display` und `_utc_str` schlägt immer fehl, da der Decoder diese Attribute nicht setzt. Aktuell wird ohnehin `time.strftime` verwendet – kein Fehler, aber nach P13 muss der neue Pfad sauber greifen.
- **Empfehlung**: Nach Korrektur von KP‑1 ist das erledigt.

#### H‑2 (HINWEIS) — `rx_history_store` mögliche Inkonsistenz
- **Stelle**: `rx_history_store.py` (nicht im Plan gezeigt)
- **Befund**: V2 behauptet „nicht betroffen“. Falls der Store bisher UTC als String (Wall‑Time) speichert und zukünftig Slot‑Boundary‑Strings, kann nach Migration eine Mischung alter/neuer Formate auftreten. Die Sortierung ist davon nicht betroffen, die Anzeige aber ggf.
- **Empfehlung**: Bei Deployment die History‑Datei löschen oder eine Migration auf Basis von `_slot_start_ts` durchführen.

#### H‑3 (HINWEIS) — `_psk_band` nicht thread‑safe
- **Stelle**: `ui/main_window.py`, `_fetch_psk_stats` (Z. ~939) und `_psk_worker` (Z. ~946)
- **Befund**: `self._psk_band` wird im GUI‑Thread gesetzt, der Worker liest es später. Bei schnellem Bandwechsel könnten die Worker das alte Band verwenden. Das ist kein echter Bug, da die Anfragen trotzdem abgesetzt werden, aber die angezeigte Band‑Information kann kurz inkonsistent sein.
- **Empfehlung**: Könnte durch lokales Kopieren im Worker entschärft werden, aber für Hobby‑Tool akzeptabel.

### Zusammenfassung

| Kategorie | Anzahl |
|-----------|--------|
| KRITISCH (Bug) | 3 |
| SOLLTE‑FIX (architektonisch) | 3 |
| KOENNTE (Optimierung) | 2 |
| HINWEIS (klein) | 3 |

**Plan‑Status: V3 nötig** – Die drei kritischen Fehler (fehlende Implementierung der Slot‑Time in `rx_panel` und die Backoff‑Race‑Condition in `psk_reporter`) machen den V2‑Plan in dieser Form nicht freigabefähig. Nach Korrektur dieser Punkte (insb. KP‑1 und KP‑2) kann der Plan in einer V3‑Review erneut geprüft werden. Die restlichen SOLLTE‑FIXe sollten ebenfalls vor Freigabe behoben werden.
