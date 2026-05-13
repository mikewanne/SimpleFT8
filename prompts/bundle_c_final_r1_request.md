# Bundle C — Final R1 Codereview Request

Du bist DeepSeek-R1. Dies ist FINAL Codereview vor Push.
Pruefe implementierten Code gegen V3-Plan + suche restliche Bugs,
Race-Bedingungen, Test-Coverage-Gaps.

Antwort-Schema:
- KRITISCH (KP-N): muss vor Push gefixt
- SOLLTE (S-N): waere besser
- KOENNTE (K-N): Hinweis
- Push-Freigabe ja/nein

## Implementierte Aenderungen

### P10 — PSK-Backoff-Reset
- `core/psk_reporter.py:42-49` BACKOFF_MAX_S 3600 → 600 mit Begruendungs-Kommentar
- `core/psk_reporter.py:148-179` _Backoff thread-safe via threading.Lock
  (KP-2). reset() und fail() beide mit `with self._lock:`
- `core/psk_reporter.py:347-358` neue public Methode
  `PSKReporterClient.reset_backoff()` delegiert an `_backoff.reset()`
- `ui/mw_radio.py:260-285` neuer Helper `_reset_psk_polling_on_change`
  - Statusbar-Pfad: `_psk_first_fetch = True` + `_psk_timer.start(0)`
  - Karten-Pfad: defensiv navigate `_direction_map_dialog._map_canvas
    ._psk_client.reset_backoff()` mit try/except
- `ui/mw_radio.py:307` `_on_mode_changed` ruft Helper nach Settings
- `ui/mw_radio.py:373` `_on_band_changed` ruft Helper nach Settings

### P13 — RX-Panel-Slot-Times
- `ui/rx_panel.py:288-302` `add_message` nutzt `msg._slot_start_ts`
  mit `int(slot_ts)` (R1-K2), Fallback wie bisher
- `ui/rx_panel.py:394-405` `_populate_row` analog (war 2. Bug-Stelle
  die V2 anfangs uebersehen hatte — Final-Check entdeckte)
- `ui/rx_panel.py:597-616` `_set_sort` time-Branch defensiv mit
  Float-Key (mixed-Type-safe)

### Tests
- `tests/test_p10_psk_backoff_reset.py` NEU 6 Tests inkl.
  Thread-Safety mit 10 parallel-Threads
- `tests/test_p13_rx_panel_slot_times.py` NEU 6 Tests inkl.
  Source-Level Bug-Schutz + mixed-Type-Sort-Defensive
- `tests/test_psk_reporter.py:183` BACKOFF-Max-Test von 3600→600 angepasst
- 1204 → 1216 grün (+12)

## Konkrete Pruefauftraege

1. **P10 KP-2 Lock korrekt?** `_Backoff.fail()` macht `min(self.max_s,
   self.current_s * self.factor)` IM Lock — Multiplikation und
   Vergleich ist innerhalb. Read von `self.factor` und `self.max_s`
   ist read-only (dataclass-Attribute nach Init nicht mehr geaendert).
   Stimmt das oder muesste auch reset von außen pruefen?

2. **P10 reset_backoff() docstring** sagt „Worker-Thread im Sleep
   wird NICHT interruptet — aktueller Sleep laeuft bis Ende (worst-case
   10 Min Latenz)". Bei V3 hat das jemand als „akzeptabel" abgenickt.
   Aber: ist das Doku ausreichend oder solltest du Event-basiertes
   Wakeup empfehlen?

3. **P10 mw_radio Helper Reihenfolge:** In `_on_band_changed` ruft
   Helper NACH `settings.set("band", band)`. In `_on_mode_changed`
   NACH `settings.set("mode", mode)`. Korrekt — Worker liest neues
   Band/Modus aus settings. Ja?

4. **P10 mw_radio defensives navigate** zur Karte:
   ```python
   dlg = getattr(self, '_direction_map_dialog', None)
   if dlg is not None:
       canvas = getattr(dlg, '_map_canvas', None)
       client = getattr(canvas, '_psk_client', None) if canvas else None
       if client is not None:
           try: client.reset_backoff()
           except Exception as e: print(...)
   ```
   Verkettete getattr — defensiv genug? Oder zu paranoid?

5. **P13 — `_populate_row` Fix war NICHT in V2/V3 explizit erwaehnt.**
   Erst beim Code-Schreiben aufgefallen dass `_populate_row` einen
   eigenen utc-Generator hat (Z.394+). Final-Code hat ihn analog
   gefixt. Aber: zeigt das eine Memory-Lesson? Solche „2. Bug-Stelle"
   sollten in V2 schon auftauchen.

6. **P13 Sort-Branch mit Float-Key** — defensive mixed-Type-Sort.
   Aktuell: wenn `_slot_start_ts` Float, sort key Float. Wenn nur
   `_utc_display` als String, versucht `float(s)` — HHMMSS-Strings
   wie "1234" parsen sich als Float 1234.0. Korrekt? Was bei "abc"?
   except greift, return 0.0 → fall-back ans Ende. OK.

7. **P13 Tests — Mock-Strategie**: types.SimpleNamespace mit `dt=0.0`,
   `grid_or_report=""`, `antenna=""` als minimaler Stub. Real
   FT8Message hat 30+ Attribute. Test-Coverage geht nicht durch die
   Spalten-Rendering-Logik (km, country, etc.) sondern testet nur
   den UTC-Pfad. Reicht das oder muss ein full-msg-Test rein?

8. **Memory-Lesson (P10 KP-2)**: V2 hat „CPython GIL macht es atomar"
   geschrieben — falsch fuer read-modify-write. R1 hat den Bug
   entdeckt. Soll in feedback-Memory festgehalten werden?

9. **Field-Test-Risiken**: was kann beim ersten Field-Test brechen?
   2-3 Punkte fuer Mike's V3-§Field-Test.
