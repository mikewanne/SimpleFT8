# HANDOFF — SimpleFT8 — 2026-04-23 (Nacht II)

## Heute erledigt

### Stats-Guard Bug gefixt (Root Cause durch DeepSeek-Analyse)

**Bug:** Statistiken wurden während CQ-Modus und laufendem QSO geloggt trotz Guard.

**Root Cause:** In `_on_station_clicked` (manueller Klick auf Station während CQ):
1. `stop_cq()` setzte `cq_mode=False`
2. `start_qso()` speicherte `_was_cq = self.cq_mode = False` (schon False!)
3. Nach QSO-Ende: `_resume_cq_if_needed()` sah beide False → `state=IDLE` → CQ **nicht** resumed + Stats geloggt

**3 Fixes:**
- `mw_qso.py::_on_station_clicked` — `_cq_was_active` VOR `stop_cq()` sichern, nach `start_qso()` als `_was_cq=True` setzen
- `qso_state.py::_process_cq_reply` — `self._was_cq = True` explizit setzen (CQ-Antwort, cq_mode=True garantiert)
- `mw_cycle.py::_log_stats` — Guard um `btn_cq.isChecked()` erweitert (3-fach robust: Button + cq_mode + State)

**Tests: 168 passed** (unverändert, kein neuer Test da Bug im Feld entdeckt)

### Statistics aktualisiert
- `scripts/generate_plots.py` ausgeführt → 8 PNGs + SimpleFT8_Bericht.pdf (7 Seiten)

---

# HANDOFF — SimpleFT8 — 2026-04-23 (Nacht)

## Nacht-Session 2026-04-23 — 3 "Sehr einfach"-Features erledigt

1. **60m Propagation** — war bereits in `core/propagation.py` (L181-190) implementiert:
   Interpolation aus 40m+80m (day/night getrennt) per _CONDITION_ORDER-Index-Median.
   → Nur Docs angepasst (CLAUDE.md + HANDOFF.md + TODO-Liste bereinigt).

2. **RX-Liste leeren bei Antennen/Diversity-Wechsel** — `ui/mw_radio.py`:
   - `_on_rx_panel_toggled` (RX ON/OFF) → Tabelle + QSO-Panel + Dicts leeren
   - `_enable_diversity` → Tabelle + QSO-Panel + Dicts leeren (beide Aufrufpfade: Preset-valid + Post-Gain)
   - `_disable_diversity` → Tabelle + QSO-Panel + Dicts leeren

3. **Alte CQ-Rufe auto-löschen (>5 Min)** — `core/station_accumulator.py::remove_stale`:
   - Neues Aging-Limit pro Station-Typ: 150s (active_qso) / **300s für CQ-Rufer** / 75s sonst
   - Test-Fix: `test_accumulator_aging` auf nicht-CQ-Message geändert + neuer Test `test_accumulator_cq_longer_aging`
   - Tests: **168 passed** (+1 vs. Baseline 167)

---

# HANDOFF — SimpleFT8 — 2026-04-23 (Abend)

## Heute erledigt

### DT-Timing vollständig korrigiert (Major Milestone)
- RX: DT_BUFFER_OFFSET FT8=2.0, FT4=1.0, FT2=0.8 (WSJT-X 0.5s eingerechnet)
- Korrektur konvergiert auf ~0.24s (FlexRadio VITA-49 RX-Hardware)
- TX: TARGET_TX_OFFSET=-0.8s (kompensiert 1.3s FlexRadio TX-Buffer)
- Validiert: 8 TX-Zyklen 0.0s DT am Icom, 20m + 40m getestet
- ntp_time: per-Band+Modus-Speicherung "FT8_20m", set_band(), engere Grenzen
- mw_radio: set_band()/set_mode(mode, band) korrekt verdrahtet

### 6 Bugs gefixt
- FT2 Even/Odd: `_slot_from_utc()` auf 3.8s-Arithmetik korrigiert (war 7.5s)
- Tune-Anzeige: `_tune_active` VOR `set_frequency()` gesetzt; immer "TUNE:" in Statusbar
- PSK bei Bandwechsel: gelöscht + Timer-Reset + Interval 300s (5min Rate-Limit)
- Stats-Guard: pausiert bei CQ-Modus und laufendem QSO
- 15m Diversity: Preset laden oder Warnung "bitte KALIBRIEREN"
- 3 veraltete Tests auf neues Key-Format angepasst → 167 passed

### Dokumentation
- dt.md erstellt (Theorie, Änderungen, Messergebnisse)
- CLAUDE.md + HANDOFF.md aktualisiert
- TODO.md: Per-Station DT-Offset Feature eingetragen

---

## Offen / Nächste Schritte (nach Schwierigkeit sortiert)

### Einfach
1. Per-Station DT-Offset TX — `encoder._station_dt_offset` (TODO.md)
2. Even/Odd dedizierter Timer — unabhängig vom Decoder-Thread
3. Gain-Bias beheben (Normal-Modus Gain-Messung wenn Stats aktiv)

### Mittel
4. CQ Sweet-Spot 800–2000 Hz fest
5. Kollisionserkennung verfeinern
6. Modus-abhängige Dwell-Time FT4/FT2
7. RF-Power-Presets pro Band+Watt

### Aufwändig
8. CQ-Freq Score-basierte Lückenwahl
9. Tertile-Analyse Statistik
10. AP-Lite Threshold Feldtest

### Feldtest-abhängig
11. FT2 ausführlicher Feldtest
12. OMNI-TX Feldtest

### Langfristig
13. IC-7300 Fork, Band Map, QSO-Resume

---

## Warnungen & Fallen

- **DT_BUFFER_OFFSET** — FT8=2.0, FT4=1.0, FT2=0.8 — nie zurücksetzen!
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 braucht eigenen Wert
- **dt_corrections.json Key-Format** — "FT8_20m" (Modus_Band)
- **cache.save() NIE im Cycle-Loop**
- **`_diversity_in_operate`** bei `_enable_diversity()` auf False setzen
- **`_r_hline` existiert nicht mehr** — heisst `_chline`
- **`_tune_active` + `_tune_freq_mhz`** in `main_window.__init__` initialisiert
- **`_was_cq` in `_on_station_clicked`** — immer NACH start_qso() auf True setzen wenn CQ vorher aktiv war

---

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q → 168 passed
```

---

## Letzter bekannter guter Zustand

- Git: `main`, commit `9b36565` (Stats-Guard-Fix noch nicht committed)
- Tests: 168 passed
- RX: ~0.24s konvergiert ✓ | TX: 0.0s Icom validiert ✓
- Sicherung: `Appsicherungen/2026-04-23_vor_dt_optimierung_core/`
