# HANDOFF — SimpleFT8 — 2026-04-25 (Session 3)

## Heute erledigt

### Statistik-Methodik korrigiert (Pooled Mean global, kein Stunden-Filter)
- `scripts/generate_plots.py`: `_combo_summary_fair()` zu schlankem Wrapper um
  `_combo_summary()` umgebaut — keine (date,hour)-Schnittmenge mehr. Grund: 1 Radio
  = nie 2 Modi gleichzeitig am selben Tag. Die 18-21 gemeinsamen Slots waren ein
  nicht repräsentativer Bias (+35% war falsch).
- Spalte „Gem. Stunden" → „Mess-tage" (zeigt `n_days`).
- README.md (DE+EN): Zahlen korrigiert auf **+88%/+122% Standard**, **+124%/+158% DX**,
  Total **22.696 Zyklen** (4 Messtage).
- 2 Commits gepusht: `0ac6788`, `3d292bf`.

### PDF-Erklärung funkerverständlich (kein Jargon)
- Spaltenheader: `Ø Stat./Zyklus` → `Ø Sta./15s-Zyklus` (Dauer explizit).
- `p3_header_subtitle`: „Pooled Mean über alle Messtage" → „Tagesdurchschnitt über
  4 Messtage, alle Tageszeiten".
- `p3_note1`: plain language — „So viele Stationen pro 15s-Zyklus im Schnitt,
  gemittelt über alle Messpunkte aus 4 Messtagen und allen Tageszeiten — echter
  Tagesdurchschnitt".
- `p1_summary_body` (DE+EN): „Pooled Mean" → „Durchschnitt über alle Messpunkte".
- Commit `208e26f` gepusht.

### Berechnungsmethodik in CLAUDE.md dokumentiert
- Neuer Abschnitt „Berechnungsmethodik (Tagesdurchschnitt)" erklärt exakt wie
  `Ø Sta./15s-Zyklus` berechnet wird (Summe ÷ Anzahl Zyklen, alle Tage × alle
  Stunden), mit Negativ-Beispiel („nicht Stationen/Stunde").
- Commit `e2f97fc` gepusht.

### v0.57 Implementation: Answer-Me Highlighting + Gain-Messung Logging
- `ui/rx_panel.py`: Farbe `_COLOR_ANSWER_ME_BG` `#2A1F00` → `#5A4A10` (Gold,
  klar gegen Active-Call `#2A1500` abhebbar). Bold-Logik in `_apply_active_highlight`
  (L268) erweitert: `setBold(is_active or is_answer_me)`. Bold beim direkten Einfügen
  in `_populate_row` (L419-426).
- `ui/mw_radio.py`: Neue Methode `_log_gain_result(r, band, ft_mode)` schreibt
  Append-Only-Eintrag nach `~/.simpleft8/gain_log.md` mit UTC + Band/Mode +
  Diversity/Standard-Scoring + ANT1/ANT2 Gains + Ø SNRs. Aufruf in
  `_on_dx_tune_accepted` direkt nach `_set_gain_measure_lock(False)` und VOR dem
  `if rx_mode == "normal"` early-return → beide Modi loggen. `from pathlib import Path`
  zu Top-Level Imports.
- `main.py`: APP_VERSION 0.56 → 0.57.
- DeepSeek-Review (deepseek-chat, thinking high): 0 Issues.
- 3 Commits gepusht: `81e731e`, `5ab484e`, `3872b60`.

### Prompt v0.58 für nächste Session erstellt
Datei: `~/Desktop/cq_freq_prompt_v0.58.md` (auch unter `/tmp/cq_freq_prompt_FINAL.md`).
- Score-basierte Lückenauswahl (Gewichte 50/25/0.01)
- Fester Sweet-Spot 800-2000Hz
- Modus-abhängige Dwell-Time (FT8=4z, FT4=8z, FT2=16z = ~60s einheitlich)
- Verfeinerte Kollisionserkennung (≥2 in ±1 ODER ≥3 in ±2)
- Sticky Gap (50Hz-Schwelle)
- Stats-Modus-Sperre **bewusst NICHT** in Scope (Mike: Variance kein Bias)
- DeepSeek-Review (deepseek-chat, thinking high) durchlaufen — `reset()`-Bug erkannt
  und in v4 eingebaut (`_current_gap_width_hz` muss in `reset()` zurückgesetzt werden).

---

## Offen / Nächste Schritte

### v0.58 — BEREIT ZUR UMSETZUNG (in neuer Session)
Prompt: `~/Desktop/cq_freq_prompt_v0.58.md`
- 5 atomare Sub-Tasks (Score, Sweet-Spot, Mode-Dwell, Kollision, Sticky)
- 14 neue Tests (197 → ≥214)
- 4 atomare Commits geplant

### Offene TODOs (priorisiert nach Mike's Bewertung)
1. **v0.58 Prompt** — sofort umsetzbar (siehe oben)
2. **Even/Odd Timer** — eigener dedizierter Timer unabhängig vom Decoder-Thread
   (FT2 am kritischsten)
3. **Gain-Bias beheben** — Stats-Modus erzwingt Gain-Messung für alle Modi (EINFACH)
4. **CQ-Zusammenfassung RX-Liste** überarbeiten (DeepSeek-Idee)
5. **Tertile-Analyse** für Statistik (kein Datencropping)
6. **AP-Lite Test-Pipeline** vor jedem Code-Fix (PRIO NIEDRIG)
7. **IC-7300 Fork** (LANGFRISTIG)

### Statistik Nächste Schritte
- Nachtmessungen auf 40m → Diagrammlinie stabiler
- 20m Daten sammeln (mind. 2 Tage Normal + 2 Tage Diversity_Std + 2 Tage Diversity_DX)
  VOR Veröffentlichung auf GitHub: CLAUDE.md-Regel beachten!

---

## Warnungen & Fallen

- **DeepSeek V4** — neues Modell (deepseek-chat), Verhalten unbestätigt. Antworten
  immer am tatsächlichen Code verifizieren — KI kann plausibel klingende aber
  falsche Zeilen-Angaben machen.
- **AP-Lite** — `AP_LITE_ENABLED = True` aber ungetestet. Nicht anfassen ohne
  Test-Pipeline.
- **OMNI-TX** — deaktiviert (Easter Egg: Klick auf Versionsnummer). NICHT auf
  GitHub wie aktiviert.
- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit sinnlos
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch! IC-7300 Fork braucht eigenen
  Wert
- **Statistik-Veröffentlichung** — Andere Bänder NUR pushen wenn: Normal +
  Div_Std + Div_DX je ≥2 Tage, ganzer Tag (06-22 UTC). Regel steht in CLAUDE.md.
- **Tagesdurchschnitt-Methodik** — Pooled Mean über ALLE Zyklen aller Messtage und
  Tageszeiten (kein Stunden-Filter). Berechnung dokumentiert in CLAUDE.md.

---

## Test-Suite Status
`./venv/bin/python3 -m pytest tests/ -q` → **197 passed** ✅

## Letzter bekannter guter Zustand
Git-Branch `main`, alle Commits gepusht (origin/main = lokal, kein Lag). App startet,
v0.57 läuft (Answer-Me Highlighting Gold + Bold, Gain-Log nach
`~/.simpleft8/gain_log.md`), Statistiken laufen, PDFs (DE+EN) aktuell mit 25.04-Daten
(22.696 Zyklen, +88%/+124%).
