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

### Sehr einfach — NÄCHSTE SESSION
1. **60m Propagation** — Interpolation 40m+80m (~5 Zeilen in core/propagation.py)
2. **RX-Liste leeren** — fehlende Trigger: Antennen-Wechsel + Diversity-Modus-Wechsel
3. **Alte CQ-Rufe auto-löschen** — CQ-Zeilen > 5 Min aus RX-Tabelle entfernen

### Einfach
4. Per-Station DT-Offset TX — `encoder._station_dt_offset` (TODO.md)
5. Even/Odd dedizierter Timer — unabhängig vom Decoder-Thread
6. Sticky Gap CQ-Freq
7. Gain-Bias beheben (Normal-Modus Gain-Messung wenn Stats aktiv)

### Mittel
8. CQ Sweet-Spot 800–2000 Hz fest
9. Kollisionserkennung verfeinern
10. Modus-abhängige Dwell-Time FT4/FT2
11. RF-Power-Presets pro Band+Watt

### Aufwändig
12. CQ-Freq Score-basierte Lückenwahl
13. Tertile-Analyse Statistik
14. AP-Lite Threshold Feldtest

### Feldtest-abhängig
15. FT2 ausführlicher Feldtest
16. OMNI-TX Feldtest

### Langfristig
17. IC-7300 Fork, Band Map, QSO-Resume

---

## Prompt für Items 1–3 (fertig, nächste Session verwenden)

SimpleFT8 PySide6 App. Lies zuerst CLAUDE.md + HANDOFF.md. Konsultiere DeepSeek via `pal chat model deepseek-chat` vor jeder Implementierung. Baseline: 167 Tests passed.

**Feature 1 — 60m Propagation:** core/propagation.py, HamQSL kein 60m → nach XML-Parse aus 40m+80m interpolieren. Lies Datei für Key-Format + Einhängepunkt.

**Feature 2 — RX-Liste leeren bei ALLEN Wechseln:** ui/mw_radio.py, Band+Modus bereits implementiert. Fehlend: Antennen-Wechsel + Diversity-Modus-Wechsel. Referenz: bestehende _on_band_changed Lösch-Zeilen.

**Feature 3 — Alte CQ-Rufe auto-löschen:** ui/rx_panel.py, CQ-Zeilen > 5 Min entfernen. Lies Datei für Spaltenstruktur + UTC-Format + besten Trigger-Punkt.

Am Ende: Tests grün, commit + push.

---

## Warnungen & Fallen

- **DT_BUFFER_OFFSET** — FT8=2.0, FT4=1.0, FT2=0.8 — nie zurücksetzen!
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 braucht eigenen Wert
- **dt_corrections.json Key-Format** — "FT8_20m" (Modus_Band)
- **cache.save() NIE im Cycle-Loop**
- **`_diversity_in_operate`** bei `_enable_diversity()` auf False setzen
- **`_r_hline` existiert nicht mehr** — heisst `_chline`
- **`_tune_active` + `_tune_freq_mhz`** in `main_window.__init__` initialisiert

---

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q → 167 passed
```

---

## Letzter bekannter guter Zustand

- Git: `main`, commit `9b36565`
- Tests: 167 passed
- RX: ~0.24s konvergiert ✓ | TX: 0.0s Icom validiert ✓
- Sicherung: `Appsicherungen/2026-04-23_vor_dt_optimierung_core/`
