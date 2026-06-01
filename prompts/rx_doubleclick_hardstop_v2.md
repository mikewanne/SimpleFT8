Du bist Senior-Python/PySide6-Entwickler. Projekt SimpleFT8 — Hobby-FT8-Tool,
EIN Operator, FlexRadio. KISS-Pflicht. ZUERST Diagnose im angehängten Code,
dann Plan-Review. Belege mit Datei:Zeile. Stimme meiner Hypothese NICHT
automatisch zu — prüfe sie.

================================================================================
OPERATOR-WUNSCH (Mike, Field 01.06.2026)
================================================================================
Bei Auto-Hunt sieht Mike im EMPFANGSFENSTER (RX-Liste) eine Station die er
JETZT rufen will → Doppelklick. Aktuell: sie wird gerufen, ABER Auto-Hunt
läuft weiter. Mike will: **Doppelklick in der RX-Liste ist eine bewusste,
absichtliche Handlung → ALLES unterbrechen** (laufendes CQ, laufendes QSO,
aktiver Auto-Hunt) und SOFORT die geklickte Station rufen. KEIN Auto-Resume —
Auto-Hunt ist beendet bis er ihn neu startet (passt zur bestehenden
Auto-Hunt-Philosophie: Stop = Pflicht-Restart per User-Klick).

================================================================================
IST-ZUSTAND (verifiziert, core/auto_hunt.py + ui/mw_qso.py angehängt)
================================================================================
`_on_station_clicked(msg)` (mw_qso.py:168) ist der zentrale Klick-Handler. Ablauf:
- Vorab-Returns: SWR-Sperre (Z.177), TX-aktiv→Buffer (Z.189), Diversity-Einmessen
  (Z.211), Slot-Lock-Mismatch (Z.221).
- Dann: OMNI pausieren (235), CQ stoppen (239-242),
  **Auto-Hunt: `on_manual_qso_start()` (Z.244-245)** ← NUR `_manual_override=True`,
  Auto-Hunt bleibt `active=True`, Timer läuft → das ist Mikes Problem!
- start_qso (Z.276).

`on_manual_qso_start/end` (auto_hunt.py) = PAUSIEREN+RESUME (manual_override).
`stop_auto_hunt("manual_halt")` (auto_hunt.py) = HARTER STOP: active=False, Timer
stop, Signal auto_hunt_stopped → UI-Reset. Das ist was HALT (`_on_cancel`
mw_qso.py:419) und der Button (main_window) nutzen.

**KRITISCH — `_on_station_clicked` hat DREI Aufrufer:**
1. `rx_panel.station_clicked`-Signal (main_window.py:811) = der ECHTE
   RX-Doppelklick. ← Mikes Fall, soll HART stoppen.
2. TX-Buffer-Resume (mw_qso.py:527 `_on_station_clicked(buffered)`) = ein
   RX-Klick der während TX gebuffert wurde. Soll sich wie (1) verhalten.
3. **P164/P158-Einschub** (mw_qso.py:1059, `_p158_maybe_start_inserted_call`):
   Eine Station die uns im QSO-FENSTER anklickt wird NACH QSO-Ende eingeschoben
   und Auto-Hunt soll danach RESUMEN. Dieser Pfad MUSS sanft bleiben
   (`on_manual_qso_start`), sonst breche ich das gerade gebaute P164-Feature.

================================================================================
MEIN PLAN (V1/V2 — bitte kritisch prüfen)
================================================================================
Neuer Parameter `_on_station_clicked(msg, hard_stop: bool = True)`:
- (1) RX-Signal + (2) TX-Buffer-Resume rufen mit Default `hard_stop=True`.
- (3) P164-Einschub ruft explizit `hard_stop=False`.

Im Handler, am Auto-Hunt-Punkt (Z.244):
```python
if hard_stop:
    if self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("manual_halt")
    # P164-Merker verwerfen (wie HALT _on_cancel), sonst wird nach dem
    # RX-QSO noch eine im QSO-Fenster vorgemerkte Station gerufen:
    self._qso_pending_insert = None
    self._p158_insertable.clear()
else:
    if self._auto_hunt.active:
        self._auto_hunt.on_manual_qso_start()   # P164: pausieren + resume
```
Plus: TX-aktiv-Pfad (Z.189-210) — bei `hard_stop` dort auch sofort
`stop_auto_hunt` (sonst läuft Auto-Hunt im 1 Buffer-Slot optisch weiter)?

================================================================================
FRAGEN
================================================================================
F1. Ist der `hard_stop`-Parameter-Ansatz sauber/KISS, oder gibt es eine
    elegantere Unterscheidung der 3 Aufrufer? Default-Wert True korrekt
    (RX-Klick = häufigster Fall)?
F2. Laufendes QSO ABBRECHEN: im nicht-TX-Pfad überschreibt `start_qso(neue)` das
    alte QSO implizit. Reicht das für "sofort abbrechen", oder braucht es
    explizit `qso_sm.cancel()` vor start_qso? Doppel-Report/State-Leak-Risiko?
F3. TX-aktiv-Pfad (Z.189): Klick während Auto-Hunt sendet → Buffer + im nächsten
    Slot `_on_station_clicked(buffered, hard_stop=True)` → stoppt dann. Reicht
    das, oder im TX-Pfad SOFORT `stop_auto_hunt` (UX: Button sofort aus)?
F4. Vorab-Return-Pfade (SWR-Sperre/Slot-Lock/Einmessen) brechen VOR dem Ruf ab
    → dort KEIN Auto-Hunt-Stop (kein Ruf zustande gekommen). Richtig, oder
    erwartet Mike dass der Doppelklick IMMER stoppt — auch wenn der Ruf an
    Hardware/Lock scheitert?
F5. `stop_auto_hunt` emittiert `auto_hunt_stopped`→UI-Cooldown-Lifecycle
    (main_window:449). Direkt danach start_qso — Konflikt (Button-Reset während
    QSO startet)? HALT macht es genauso, also vermutlich ok — bestätige.
F6. `on_manual_qso_end` wird in QSO-Ende-Handlern (mw_qso.py:713, 1026) global
    gerufen → setzt manual_override=False. Wenn Auto-Hunt hart gestoppt (active=
    False) → harmlos (kein Resume)? Bestätige kein versehentliches Re-Resume.
F7. Hardware/Sicherheit: TX läuft über ANT1 (bestehender Klick-Pfad). Die
    Änderung ändert nur Auto-Hunt-Stop-Semantik, NICHT den TX/Antennen-Pfad —
    bestätige.
F8. Tests: welche bestehenden Tests prüfen `on_manual_qso_start` im Klick-Pfad
    (test_modules/test_p158/test_p164)? Was muss angepasst werden?

Antwort: (1) Diagnose, (2) F1-F8 knapp mit Datei:Zeile, (3) Severity-Tabelle
🔴/🟠/🟡/⚪.

Angehängt: ui/mw_qso.py, core/auto_hunt.py.
