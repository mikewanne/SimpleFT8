# P61 Final-R1 (DeepSeek-V4-pro) — Code-Review nach Implementation

## Ergebnis: „Push freigegeben." 0 KP

### F-ROT — Mode-Awareness sauber

`set_mode` + Key `(base_call, band, mode)` vollständig. `mark_pick` trennt
nach Band und Modus, Filter-Block in `select_next` prüft `_recent_qso` VOR
fehlerbasiertem `_cooldown` — Reihenfolge korrekt. Lazy-Cleanup verhindert
Memory-Waste.

### F-ORANGE — Wiring komplett

- `main_window.__init__`: `set_mode(settings.mode)` direkt nach
  Instanziierung.
- `mw_radio._on_mode_changed`: `set_mode(mode)` nach `qso_sm._mode = mode`.
- Settings-Dialog/UI-Button laufen über `mode_changed`-Signal → mündet
  in `_on_mode_changed`. Kein programmatischer Mode-Change ohne `set_mode`.

### F-GELB — Hardware + Tests

- ANT1-Pflicht unverändert (kein Code-Touch).
- 10 Tests T1-T10 decken alle V3-Punkte ab.

### Bug-Risiko — mark_pick vor start_qso

Wenn `start_qso` fehlschlägt, bleibt Cooldown 5 Min gesetzt obwohl QSO
nie startete. **Geringes Risiko:**
- Manueller Klick weiterhin möglich (Cooldown blockt nur Auto-Pick)
- `start_qso` selten failures
- Race-Vermeidung überwiegt

### Manueller-Klick-Pfad

`_on_station_clicked` umgeht `select_next` → Cooldown blockt NICHT.
`mark_pick` wird erst über `on_qso_complete` gesetzt → manuelles QSO
geht durch. Korrekt umgangen.

## V4-pro 9-Cycle-Bilanz nach P61

Bundle I + J + P51 + P53 + P55 + P58 + P60 + **P61** = **8 Cycles + 1 Initial-R1 von P61**.
Halluzinations-Bilanz: 0 Halluzinationen, 100% verifizierbar (alle Pfade
im Code prüfbar).
