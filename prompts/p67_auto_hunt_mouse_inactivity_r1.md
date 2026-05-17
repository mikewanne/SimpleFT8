[deepseek] ~26420 Tokens, 2 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=30804 out=8523 total=39327
## R1-Findings

### F1 (ORANGE): Fehlende Definition der Maus-Timeout-Konstante im Code
- **Pfad:** `ui/main_window.py` (neue Konstante erforderlich)
- **Symptom:** Plan (AC1) verlangt hartkodiertes `_AUTO_HUNT_MOUSE_TIMEOUT_S = 300` – keine Implementierung im vorliegenden Code sichtbar.
- **Wurzel:** AC1 wurde noch nicht umgesetzt; für Review nur Spezifikation.
- **Fix-Vorschlag:** Konstante als Klassenattribut `_AUTO_HUNT_MOUSE_TIMEOUT_S = 300` im `MainWindow` deklarieren, nahe der bestehenden `_PRESENCE_TIMEOUT`-Definition, um Sichtbarkeit und Wartbarkeit zu gewährleisten.

### F2 (ORANGE): Testmethoden-Namen in AC11 nicht an reale Codebasis angepasst
- **Pfad:** `tests/test_p67_mouse_inactivity.py` (gemäß AC11)
- **Symptom:** AC11 referenziert `_init_presence_timer` und `_on_auto_hunt_toggled` – diese existieren im echten Code nicht (heissen `_init_presence_watchdog` / `_on_btn_auto_hunt_toggled`). V2-Self-Review hat dies bereits erkannt.
- **Wurzel:** Plan-Phase-Fehler; AC11 wurde vor V2-Korrektur geschrieben.
- **Fix-Vorschlag:** AC11-Testbeschreibungen umbenennen, sodass T2, T4 u.a. die korrekten Methodennamen prüfen. Keine logische Änderung nötig.

### F3 (GELB): Konstante könnte klarer benannt werden
- **Pfad:** `ui/main_window.py`
- **Symptom:** `_AUTO_HUNT_MOUSE_TIMEOUT_S` ist knapp; `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S` wäre selbsterklärender.
- **Wurzel:** Stilpräferenz, kein Bug.
- **Fix-Vorschlag:** Umbenennung für Lesbarkeit, optional.

### F4 (GELB): `_auto_hunt_last_mouse_t` wird nur in UITimern genutzt – Lokalität ok, aber Kapselung könnte verbessert werden
- **Pfad:** `ui/main_window.py` (geplante Stelle in `_poll_mouse_activity`)
- **Symptom:** Variable, die nur für Auto-Hunt relevant ist, wird im Presence-Polling gesetzt. Das koppelt zwei unabhängige Konzepte.
- **Wurzel:** Designentscheidung, um eine zweite Polling-Schleife zu vermeiden.
- **Fix-Vorschlag:** Optional: eigene Mini-Methode `_update_auto_hunt_mouse_t()` aufrufen, um Trennung zu verdeutlichen. Keine funktionale Notwendigkeit.

## Pflicht-Fragen-Antworten

1. **Reason-Cleanup-Logik (DEFAULT vs. totmann_expired):**  
   Semantisch korrekt. `mouse_inactive_5min` erzwingt einen bewussten User-Restart, analog `manual_halt`. Ein Neustart soll nicht auf alten Fehler-Cooldowns aufbauen, da der Operator nicht mehr am Platz war. `totmann_expired` hingegen ist eine gesetzliche Pflicht (15 Min); der Operator könnte schnell zurückkehren und ohne Neuaufbau weitermachen wollen. Die unterschiedliche Behandlung ist daher begründet.

2. **`presence_can_tx()` parallel zum 5-Min-Maus-Stop:**  
   Kein Konsistenzproblem. Der 5-Min-Check ist ein zusätzlicher Auto-Hunt-spezifischer Schutz; CQ und laufende QSO bleiben davon unberührt. Nach `stop_auto_hunt("mouse_inactive_5min")` gibt `presence_can_tx()` korrekt `True`, weil der 15-Min-Presence-Timer noch nicht abgelaufen ist. Andere TX-Modi (manuelles CQ, OMNI) dürfen weiterlaufen – so gewollt.

3. **Race: `stop_auto_hunt` vs. `_run_auto_hunt` im selben Slot:**  
   Kein Race. `_on_auto_hunt_polling_tick` und `_run_auto_hunt` laufen beide im GUI-Thread (Qt-Event-Loop serialisiert). Der Doppelcheck `if not self.active` in `select_next` fängt den Fall ab, dass `stop_auto_hunt` vor der Kandidatenauswahl aufgerufen wurde. Wenn der Stop erst nach `select_next` eintrifft, wird der zurückgegebene Kandidat genutzt, was unbedenklich ist (kein aktiver TX-Abbruch).

4. **Initialwert 0.0 + Keyboard-Aktivierung:**  
   Robust. Der erste Polling-Tick nach App-Start würde sofort `_auto_hunt_last_mouse_t = 0.0` auslösen, aber Auto-Hunt ist dann noch nicht aktiv. Beim ersten Start per Click (egal ob Maus oder Tastatur über Tab+Space) wird in `_on_btn_auto_hunt_toggled(True)` der Anker auf `time.monotonic()` gesetzt, vor dem ersten Polling-Tick. Ein Keyboard-Toggle feuert denselben Signalpfad und setzt den Anker zuverlässig.

5. **UI-Feedback-Text:**  
   Klar und handlungsorientiert. Eventuell präziser: „Auto-Hunt gestoppt — 5 Minuten ohne Mausbewegung. Maus bewegen und AUTO HUNT-Taste drücken zum Fortsetzen.“ Aktuell fehlt das Wort „Taste“; geringfügige Verbesserung möglich.

6. **Konstante in `core/auto_hunt.py` vs. `main_window.py`:**  
   **Pro UI-Layer:** Maus-Polling lebt ausschliesslich in der GUI; `AutoHunt`-Klasse ist unabhängig vom UI-Kontext. Die Konstante dorthin zu verschieben würde eine unnötige Kopplung schaffen und das KISS-Prinzip verletzen.  
   **Contra:** Zentralisierung aller Auto-Hunt-Konstanten erleichtert die Übersicht, aber der Nutzen rechtfertigt nicht die Verletzung der Schichttrennung. **Empfehlung:** In `main_window.py` belassen.

7. **Test-Coverage T1–T10:**  
   Grundlegende Tests vorhanden (Grenzfall, aktiver/inaktiver Check, Cleanup). Fehlende Edge-Cases:  
   - Reset-Wirkung über mehrere Polling-Ticks: Mausbewegung nach 4 Minuten, dann 6 Minuten Ruhe → Stop muss ausbleiben, weil Anker aktualisiert wurde.  
   - Gleichzeitiges Eintreten von `mouse_inactive_5min` und `timer_expired` (trivial, aber dokumentiert).  
   - Verifikation, dass `_on_btn_auto_hunt_toggled` den Anker vor dem initialen `_on_auto_hunt_polling_tick()`-Aufruf setzt (Reihenfolgetest).  
   Insgesamt ausreichend für den geplanten Umfang; die genannten Punkte könnten in einer Nachlieferung ergänzt werden.

## Empfehlung
- **Push-Status:** FREIGEGEBEN MIT F2-FIX (Test-Namensanpassung obligatorisch)  
- **KP (kritische Punkte):**  
   Keine Hardware-Sicherheitsverletzungen, keine Race-Conditions. Der Plan ist funktional korrekt und integriert sich sauber in die bestehende Architektur. Die kleine Namenskorrektur in den Tests muss vor der Implementierung erfolgen, um Fehlschläge zu vermeiden. F1 (fehlende Konstante) ist reine Planlücke – wird bei Umsetzung behoben.
