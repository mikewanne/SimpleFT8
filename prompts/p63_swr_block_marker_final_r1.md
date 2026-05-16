## Code-Review der P63-Implementation (v0.97.36)

### 1. Implementierte AC-Kriterien (V3-Plan)

Alle 13 Acceptance Criteria wurden korrekt umgesetzt:

- **AC1 (Lock-Release)** – `_on_swr_alarm` ruft nach dem Stop-Block `_set_gain_measure_lock(False)` auf; der Bug aus dem Mike-17m-Test (dauerhaft gesperrte UI) ist behoben.
- **AC2/AC3 (Marker/Modal-Branching)** – Im SWR-Alarm wird bei `tuner_present=True` das Band in `_swr_blocked_bands` gesetzt und eine passende Modal-Message ausgegeben; ohne Tuner erscheint nur eine Warnung ohne Marker.
- **AC4 (Watchdog-Bypass)** – `_on_swr_alarm` prüft zuerst `_tune_in_progress` und returnt sofort, bevor irgendein anderer Check läuft. Der Bypass wird vor dem manuellen Tune aktiviert.
- **AC5 (10W fest, Dauer aus Setting)** – `_on_tune_clicked` verwendet hart 10 W (`set_rfpower_direct(10)`) und liest die Tune-Dauer aus `tune_duration_s` mit Whitelist 15/30 s. Token-Pattern (`_tune_auto_stop_token`) ist vorhanden.
- **AC6/AC7 (2s Post-Tune SWR-Check)** – `_tune_stop` plant via `QTimer.singleShot(2000, …)` den Callback `_tune_post_swr_check`. Dieser prüft `radio.last_swr` und entfernt bei SWR ≤ Limit den Marker (`_swr_blocked_bands.discard(band)`) und setzt bei Diversity-Modus die Pipeline fort; bei zu hohem SWR erscheint ein Modal „Tuner konnte nicht matchen“ ohne Marker-Clear.
- **AC8 (Pre-Checks)** – Alle sechs Stellen sind abgesichert:
  - `_on_btn_omni_cq_toggled`  
  - `_on_btn_auto_hunt_toggled`  
  - `_on_cq_clicked`  
  - `_on_station_clicked`  
  - `_check_diversity_preset`  
  - `_start_dx_tuning` (über den vorhandenen Pre-Check in `_check_diversity_preset` sowie eigenen Check im Gain-Pfad)  
  Jeder Block setzt den Button zurück und gibt eine Info-Meldung aus.
- **AC9 (Tuner=False skipt Auto-TUNE)** – `_start_dx_tuning` führt die automatische TUNE-Phase nur aus, wenn `radio.ip and tuner_present`; im Else-Zweig wird die Leistung zurückgesetzt (Power-Reset).
- **AC10** – (entfällt, nicht spezifiziert)
- **AC11 (Auto-TUNE-Fehler)** – Die innere `_after_tune`-Funktion in `_start_dx_tuning` prüft SWR nach 3 s und setzt bei Überschreitung Marker sowie `_set_gain_measure_lock(False)`.
- **AC12 (Pending-Click-Schutz)** – `_on_station_clicked` prüft als erstes `_swr_blocked_bands` und buffert nicht, wenn das Band gesperrt ist. `_on_tx_finished` prüft vor Ausführung des gepufferten Klicks ebenfalls den Marker; so wird eine nachträgliche Sperre während des TX abgefangen.
- **AC13 (ANT1-Pflicht)** – Vor `self.radio.tune_on()` ruft `_start_dx_tuning` explizit `self.radio.set_tx_antenna("ANT1")` auf. Dasselbe geschieht im manuellen Tune über `_on_tune_clicked`.

### 2. Sicherheits-Check (Edge-Cases & Concurrency)

- **Lock-Release in allen Fehlerpfaden:**  
  `_on_swr_alarm` → Lock wird direkt nach Stop freigegeben.  
  `_start_dx_tuning` → Bei SWR-Fehler Lock-Release, Marker gesetzt.  
  `_check_diversity_preset` → Vor Pre-Check wird kein Lock gesetzt; die Methode schaltet auch keinen Lock ein, ein Entsperren ist nicht nötig.  
  → Alle Pfade sind abgedeckt.
- **Concurrency `_swr_blocked_bands`:**  
  Wird ausschließlich im GUI-Thread beschrieben und gelesen (alle beteiligten Methoden sind Qt-Slots). Kein Thread-Wechsel, keine Race-Condition.
- **Token-Pattern:**  
  `_tune_auto_stop_token` und `_tune_post_check_token` werden mit `object()` eindeutig ersetzt und im Timer-Callback gegen das aktuelle Token geprüft. Timer laufen im GUI-Thread → kein Race möglich. Bei manuellem Stop (User klickt TUNE aus) wird `token=None` übergeben, sodass `_tune_stop` den Stop bedingungslos ausführt.
- **Pending-Click-Schutz:**  
  `_on_station_clicked` verhindert das Puffern auf gesperrten Bändern. Sollte ein Puffer während des TX durch ein späteres SWR-Alarm-Ereignis obsolet werden, fängt `_on_tx_finished` das ab und verwirft den Klick. Das Flag `_pending_station_click` wird in `_on_swr_alarm` und `_abort_active_tx` zurückgesetzt.
- **ANT1-Pflicht:**  
  Sowohl der manuelle als auch der automatisierte TUNE-Branch setzen PTX-Antenne auf ANT1.

### 3. KISS-Check

Die Lösung verwendet einfache, lineare Kontrollflüsse:
- Ein In-Memory-`set` für die Marker, keine Persistenz.
- Timer-Ketten mit Token, kein komplexer Zustandsautomat.
- Die Pre-Checks sind kurze `if band in _swr_blocked_bands`-Blöcke.
- Keine Overhead-Schichten oder unnötige Abstraktionen.  
→ **Kein Overengineering**, passend zur Hobby-Funker-Umgebung.

### 4. Push-Empfehlung

**Push freigegeben.**  
Die V3-ACs sind vollständig und korrekt umgesetzt, Tests (jetzt 1327 grün) decken die kritischen Pattern ab. Für den anschließenden **Field-Test-Plan F1–F10** (Mike) sind alle Szenarien abgedeckt – von rotem Band über manuellen Tune bis zu Settings-Tuner=AUS. Keine weiteren Nachbesserungen nötig.
