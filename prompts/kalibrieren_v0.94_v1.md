# v0.94 KALIBRIEREN-Button erweitern + Stats-Bug Phase 2

## Auftrag an R1 (DeepSeek-Reasoner)

**NUR DISKUSSION** — kein Code, kein Plan. Strukturierte Bewertung
auf Deutsch, knapp + sachlich. Mike's Vorschlag fachlich + KISS-orientiert
beurteilen, Edge-Cases identifizieren.

## Kontext (v0.93 Stand, frisch released)

- KALIBRIEREN-Button (`control_panel.einmessen_clicked`) ruft
  `_handle_dx_tuning` (mw_radio.py:1079) → nur Phase 2 (Gain-Mess-Pipeline,
  ~2 Min interleaved 8 Schritte ANT1/ANT2 × G10/G20).
- Phase 3 (Diversity-Ratio-Messung) startet aktuell:
  - bei Diversity-Aktivierung via Button (über `_check_diversity_preset` /
    `_activate_diversity_with_scoring`)
  - bei Bandwechsel mit aktiver Diversity
  - automatisch nach 1h-Frist (v0.93 zeit-basiert)
- v0.93 Cache-Reuse: bei `is_valid_ratio` < 1h → Phase 3 skip + 5s-Toast.
- v0.93 Score-basierte Messung statt station_count.

## Mike's Vorschlag (zwei Punkte)

### Punkt 1: KALIBRIEREN je nach RX-Modus erweitern

**Aktuell:** KALIBRIEREN macht IMMER nur Phase 2 (Gain-Messung).

**Mike's Idee:**
- RX-Modus = **Normal** → KALIBRIEREN nur Phase 2 (Gain), fertig.
  Speichert Gain im PresetStore Standard.
- RX-Modus = **Diversity Standard** → KALIBRIEREN macht Phase 2 (Gain mit
  scoring="stations") + Phase 3 (Standard-Ratio-Messung) → speichert
  beides im PresetStore Standard, **Timer (`_last_measured_at`) wird
  zurückgesetzt** auf `time.time()`.
- RX-Modus = **Diversity DX** → analog mit scoring="snr" für Gain +
  Phase 3 DX-Ratio → PresetStore DX, Timer reset.

**Begründung:** UX-Win — User klickt einmal, kriegt komplette frische
Kalibrierung für aktuellen Modus. Aktuell muss er KALIBRIEREN klicken
*und dann manuell warten bis Phase 3 startet* (oder Diversity neu
aktivieren).

### Punkt 2: Stats-Logging während Phase 2 — Bug + Fairness-Bug 0-Stations

**Bug A (gerade entdeckt):**
- `_is_antenna_tuning_active` (mw_cycle.py:633-648) prüft
  `self._rx_mode == "dx_tuning"` — aber der Code setzt `_rx_mode` NIE
  auf `"dx_tuning"` (nur als Kommentar in main_window.py:204 erwähnt).
- Folge: während Phase 2 (DXTune-Dialog läuft) wird Stats trotzdem
  geloggt. Hardware-Antenne schaltet nach `_schedule[_step]`
  (ANT1/ANT2 × G10/G20), aber Diversity-Pattern läuft parallel mit
  `choose()` und setzt `msg.antenna = "A1"/"A2"` falsch.
- Mike's Screenshot zeigt: CU2JX (-22 dB) im RX-Panel als "A1", aber
  im DXTuneDialog ist Schritt 5/8 (ANT2 Gain 10 dB) — die Station
  landet im Bucket `(ANT2, 20)` mit "1 St.".
- Bei 4 Tagen × 24h Pooled-Mean ist der Bias < 0.5 % (Kalibrierung
  selten), aber technisch ist es falsch.

**Mike's Fairness-Frage zu 0-Stations-Logging:**
- "Werden 0-Stations-Slots geloggt? Bei schlechten Bedingungen kann
  Normal=0 und Diversity=3 sein — wenn 0-Slots nicht geloggt werden,
  wird Pooled-Mean von Normal künstlich höher weil weniger Datenpunkte
  gemittelt werden."

**Code-Verifikation (Stand v0.93):**
- `core/station_stats.py:96` `log_cycle(station_count, ...)` filtert
  NICHT auf `station_count == 0` → schreibt grundsätzlich auch leere
  Slots.
- Aber `_log_stats` (mw_cycle.py:650) hat Pre-Conditions die loggen
  blocken:
  - `stats_enabled` setting
  - Band in `LOGGED_BANDS`
  - `_stats_warmup_cycles > 0` (6 Slots nach Bandwechsel)
  - `_is_antenna_tuning_active()` (Phase 3 measure)
  - CQ/QSO aktiv
- Wenn keine dieser Bedingungen blockt → wird auch bei 0 Stationen
  geloggt. Mike's Sorge ist (vermutlich) unbegründet — aber Mike will
  Bestätigung.

## Was R1 bewerten soll

### A) KALIBRIEREN-Button erweitern (Punkt 1)

1. **Logisch sinnvoll?** UX-Argument: ein Klick = komplette Kalibrierung
   für aktuellen Modus. Oder ist das Mixing-of-Concerns?
2. **Code-Komplexität:** `_handle_dx_tuning` (Z.1079) ruft aktuell
   `_start_dx_tuning(scoring_mode=gain_scoring)`. Phase 3 startet erst
   wenn `_pending_dx_diversity = True` flag (siehe
   `_activate_diversity_with_scoring` Z.566-568). Ist die
   Wiederverwendung des `_pending_*`-Flags clean, oder brauchen wir eine
   neue Pipeline-Klasse?
3. **Edge-Case:** User klickt KALIBRIEREN während Phase 2 schon läuft
   → was passiert? Aktuell: vermutlich Ignored oder Crash. Sollte
   Pending sein bis Phase 2 fertig?
4. **Edge-Case:** User wechselt Modus (Normal → Diversity Standard)
   während Phase 2 läuft → durch v0.92 Lock geblockt (`_gain_measure_locked`).
   OK so?
5. **Timer-Reset:** `_last_measured_at = time.time()` nach Phase 3 schon
   in `_evaluate` (v0.93). Mike's "Timer-Reset" implizit dabei. Brauchen
   wir explizites Setting?

### B) Stats-Bug Phase 2 (Bug A)

6. **Fix-Strategie:** `_is_antenna_tuning_active` um Check
   `self._dx_tune_dialog is not None` erweitern → Stats werden während
   Phase 2 pausiert. Saubere Lösung?
7. **Alternativ:** `_rx_mode = "dx_tuning"` setzen wenn
   `_start_dx_tuning` aufgerufen wird, zurücksetzen wenn DXTuneDialog
   schließt. Cleaner aber invasiver.
8. **RX-Panel-Anzeige:** Während Phase 2 sollte msg.antenna die echte
   Hardware-Antenne aus `_schedule[_step]` reflektieren statt
   Diversity-Pattern. Wert-Win oder Overengineering?

### C) 0-Stations-Logging (Mike's Fairness-Frage)

9. **Tatsache:** `log_cycle` filtert NICHT auf 0 — Slots mit 0
   Stationen werden geschrieben. Bestätigt korrekt?
10. **Pre-Conditions:** Sind die Block-Pfade in `_log_stats`
    (warmup, tuning, CQ, QSO) faire Filter, oder fehlt was wenn z.B.
    Diversity 3 Stationen liefert während Normal 0?
11. **Asymmetrie-Risiko:** Können Bedingungen auftreten wo Normal-Modus
    in einem Slot logged wird aber Diversity in dem GLEICHEN
    physikalischen Slot nicht? (Beide laufen ja nicht parallel — User
    wechselt). Oder ist das Pooled-Mean robust gegen Asymmetrie weil
    Modi an verschiedenen Slots gemessen werden?

### D) KISS-Bewertung

12. **Aufwand:** Punkt 1 (KALIBRIEREN-Erweiterung) + Punkt 2 Bug-A-Fix
    + Optional RX-Panel-Anzeige. Geschätzt 2-3 h. Worth it?
13. **Was kann weg gelassen werden?** Punkt 3 (RX-Panel-Anzeige) ist
    Cosmetic — Stats-Logging ist KRITISCH für Datenqualität.

## Mein Vorab-Standpunkt (kannst du angreifen)

**Pro KALIBRIEREN-Erweiterung:**
- UX-Win, ein Klick statt zwei Schritte
- Konsistenz mit v0.93-Vision (zeit-basiert, atmosphärisch korrekt)
- Bug-Fix Phase 2 + Phase 3 in einem Workflow

**Pro Stats-Bug-Fix:**
- Daten-Qualität ist wichtigster Wert für SimpleFT8
- 1-2% Bias über Kalibrier-Phasen ist messbar in Pooled-Mean wenn
  oft kalibriert wird

**Skeptisch zu RX-Panel-Anzeige während Phase 2:**
- Cosmetic, kein Daten-Effekt
- Mike sieht im Kalibrier-Dialog welche Antenne läuft

## R1's Empfehlung gefragt

**Klare Ja/Nein-Antworten** + Begründung:
1. KALIBRIEREN-Button erweitern? Ja/Nein + warum
2. Stats-Bug Phase 2 fixen? Ja/Nein + Strategie (`_is_antenna_tuning_active`
   erweitern vs `_rx_mode = "dx_tuning"`)
3. 0-Stations-Logging korrekt? Bestätigung oder Lücke?
4. RX-Panel-Antennen-Anzeige während Phase 2 fixen? Ja/Nein

**KISS-Bewertung gesamt:** überschaubar oder over-engineering?

## Was R1 NICHT machen soll

- Code schreiben
- Plan-Datei erstellen
- Tests entwerfen
- v0.93-Architektur grundsätzlich in Frage stellen
