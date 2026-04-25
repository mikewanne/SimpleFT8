# HANDOFF — SimpleFT8 — 2026-04-25

## Heute erledigt

### v0.56 — RF-Power-Presets pro Band+Watt (lernendes System)
- `core/rf_preset_store.py` (NEU): Hybrid-Lade-Strategie — exakter Treffer → lineare
  Interpolation/Extrapolation → Default. Atomic JSON-Write, Plausibilitäts-Warnung >20% Δ,
  Migration aus altem `rfpower_per_band`-Eintrag in config.json.
- `radio/base_radio.py` + `radio/flexradio.py`: `radio_type` Klassen-Konstante als Top-Level-Key
- `ui/mw_tx.py`: `_apply_rf_preset()`, Race-Schutz `_was_converged`, Save-Trigger refactored
- `ui/mw_radio.py`: `_apply_rf_preset()` bei Radio-Connect + Bandwechsel
- `ui/settings_dialog.py`: GroupBox "RF-Presets" — Tabelle + Reset-Buttons (disabled mid-TX)
- Tests: 168 → 197 passed (19 neue RFPresetStore-Tests)

### Refactoring + Tests
- `ui/mw_cycle.py`: 5 Helper-Methoden aus `_on_cycle_decoded` extrahiert
- `tests/test_modules.py`: 7× `DiversityController._evaluate` + 1× AP-Lite Costas-Test

### Doku & Prozess
- `CLAUDE.md`: Rollen, Commit-Richtlinien, DeepSeek-V4-Warnung
- `feierabend.md`: HISTORY.md-Pflicht-Hinweis präzisiert
- `TODO.md`: 5 Punkte aktualisiert (RX-Sort [x], DT-Offset PRIO NIEDRIG, TX-Freq-Bug)

### Statistiken
- 40m + 20m Messungen 25.04 committed; PDFs (DE+EN) neu generiert

---

## Offen / Nächste Session

### Prompt v0.57 — BEREIT ZUR UMSETZUNG
Datei: im letzten Claude-Chat gespeichert (Answer-Me + Gain-Log)

**Aufgabe 1 — `ui/rx_panel.py` (3 Stellen, trivial):**
- L37: `_COLOR_ANSWER_ME_BG` → `QColor("#5A4A10")` (dunkles Gold)
- L268: `f.setBold(is_active)` → `f.setBold(is_active or is_answer_me)`
- L421-423: Bold beim direkten Einfügen (`_populate_row`) setzen

**Aufgabe 2 — `ui/mw_radio.py` (neue Methode):**
- `_log_gain_result(r, band, ft_mode)` → Append `~/.simpleft8/gain_log.md`
- Aufruf nach `self._set_gain_measure_lock(False)` in `_on_dx_tune_accepted()`
- APP_VERSION → 0.57, HISTORY.md ergänzen, TODO [x]

### Offene TODOs (priorisiert)
1. **v0.57 Prompt** — sofort umsetzbar (siehe oben)
2. **CQ-Freq Algorithmus** — Score-basiert, Sweet-Spot, Dwell-Time (MITTEL)
3. **Gain-Bias beheben** — Stats-Modus erzwingt Gain-Messung für alle Modi (EINFACH)
4. **Even/Odd Timer** — eigener dedizierter Timer unabhängig vom Decoder-Thread
5. **Per-Station DT-Offset TX** — PRIO NIEDRIG (erst nach mehr Feldtest-Daten)

### Vermutliche Bugs (noch nicht reproduzierbar)
- **TX-Frequenz Normal-Modus** — manchmal kein Histogramm-Marker, TX bleibt auf alter Freq.
  Konsole beobachten: `[CQ] TX-Frequenz auf X Hz` — tritt es auf oder nicht?

---

## Warnungen & Fallen

- **DeepSeek V4** — neues Modell, Verhalten unbestätigt. Antworten immer am Code verifizieren.
- **AP-Lite** — `AP_LITE_ENABLED = True` aber ungetestet. Nicht anfassen ohne Test-Pipeline.
- **OMNI-TX** — deaktiviert (Easter Egg: Klick auf Versionsnummer). Nicht auf GitHub wie man es aktiviert.
- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit sinnlos
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen Wert

---

## Test-Suite Status
`./venv/bin/python3 -m pytest tests/ -q` → **197 passed** ✅

## Letzter bekannter guter Zustand
Git-Branch `main`, 8 Commits ahead of origin. App startet, RFPresetStore lädt/speichert
korrekt, Statistiken laufen, PDFs (DE+EN) aktuell mit 25.04-Daten.
