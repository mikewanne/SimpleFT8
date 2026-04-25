# HANDOFF — SimpleFT8 — 2026-04-25 (Session 4, Abend)

## Heute erledigt

### v0.59 — CQ-Frequenz-Algorithmus Praxis-Tuning (3 Punkte + Bug-Fix)

Nach v0.58-Feldtest am Radio (DA1MHH, 20 m FT8 Diversity DX) hatte Mike drei
funkpraktische Probleme gefunden. Komplett überarbeitet, Punkt für Punkt
validiert:

**Punkt 1 — Suchbereich dynamisch (`334a246`):**
- `SWEET_SPOT_MIN_HZ` / `SWEET_SPOT_MAX_HZ` Klassenkonstanten entfernt
- Suchbereich pro Cycle = `min(occupied_bins)..max(occupied_bins)` + Margin
- Median über alle Stationen, Sticky-Check folgt dynamischem Bereich
- v0.58-Idee "fester Sweet-Spot 800-2000 Hz" funkpraktisch verworfen — TX
  landete am leeren Rand statt bei der Aktivität

**Punkt 1b — Graduelle Lücken-Toleranz (`c4fa032`):**
- Bei 70+ Stationen gab's keine Lücke ≥150 Hz mehr → `None` → kein Wechsel
  → TX hängte auf voller Position fest
- Stufen `(max_count_per_bin, min_gap_bins)`: `(0,3)`→`(0,2)`→`(0,1)`→
  `(1,3)`→`(1,2)`. Findet IMMER Position außer leerem Histogramm
- Score-Funktion erweitert: `n_self` (Stationen IM TX-Bin) = 100 Hz Strafe
  pro Station — verhindert dass TX in Notfall-Stufe auf Station landet

**Punkt 1c — `SEARCH_MARGIN_BINS = 0` (`419ab52`):**
- v0.59 v2 hatte Margin = 2 Bins → TX landete 100 Hz außerhalb der letzten Station
- Mike-Anforderung: TX strikt zwischen niedrigster und höchster Station
- Margin auf 0 = exakt min..max

**Punkt 3 — Slot-Counter + Histogramm-Refresh jeden Slot (`af9dfb8`):**
- Mike's Idee 1:1: einfacher Loop `x = 60: tick: x-1: if x=0 then suche: reset`
- DeepSeek bestätigte: Slot-Counter > Wallclock-Timer (kein Drift, friert
  bei App-Pause korrekt ein)
- `_SEARCH_INTERVAL_SLOTS = {FT8:4, FT4:8, FT2:16}` = ~60 s alle Modi
- `tick_slot()` + `seconds_until_search` property
- `update_proposed_freq()` 40 Zeilen kürzer (elapsed-time-Logik weg)
- `_min_dwell_s` / `_recalc_interval_s` / `_last_check_time` etc. entfernt
- `mw_cycle._refresh_diversity_freq_view()` läuft JEDEN Slot in
  `_on_cycle_decoded` UNABHÄNGIG vom messages-Inhalt → fixt P1 (Histogramm-
  Update Guard) implizit. Ein Bug der seit v0.54 drin war.
- ProgressBar Range 0-15 → 0-60, Farbschwellen 5/10 → 15/30

### Statistiken aktualisiert
- `scripts/generate_plots.py` ausgeführt → DE + EN PDFs neu generiert
- 40m + 20m + diverse Modi
- Datenstand 25.04.2026: 22.696 Zyklen, Diversity Standard +88%, DX +124%

### DeepSeek-Konsultationen (alle deepseek-chat, thinking medium-high)
1. CQ-Frequenz-Auswahl-Algorithmus-Konzept (vor Punkt 1 Recherche)
2. CQ-Frequenz-Wechselrate Funkpraxis (vor Punkt 3 Entscheidung 60s vs Slot)
3. Slot-Counter vs Wallclock Sanity-Check (vor Punkt 3 Implementation)
Alle drei lieferten praxistaugliche Empfehlungen, jede am Code verifiziert
(DeepSeek V4 ist neu — keine blinde Übernahme).

### Internet-Recherche
- FT8/FT4/FT2 Splatter, Bandbreite, Operating-Praxis recherchiert
- Konsens: 30-60 s Min-Dwell ist Standard, < 30 s killt QSO-Aufbau
- WSJT-X stock hat keinerlei automatisches Frequency-Hopping
- Bestätigt Mike's Praxiserfahrung am Radio

## Offen / Nächste Schritte

### Punkt 2 (Score-Tuning für TX-Position) — NICHT umgesetzt
Mike's Beobachtung mit v0.58: TX landete bei 1675 Hz am Rand der breitesten
Lücke statt zentral. Das war v0.58-Score "by design" (Lückenbreite dominiert).
In v0.59 ist das durch Punkt 1+1b+1c teilweise gelöst (kein Rand mehr durch
dynamischen Bereich), aber die zentralere Position innerhalb einer Lücke
ist noch offen. Aktuell: Mitte der besten Lücke. Praxis zeigt ob das reicht.

### Beobachtungen am Radio (v0.59 v4 nach Neustart)
- TX-Suche funktioniert "top, astrein" (Mike-Zitat)
- 60 s Countdown läuft ehrlich slot-synchron
- Histogramm refresht jeden Slot
- Anzeige geht 60→0, dann Suche, dann reset
- Kein Hängen mehr auf voller Position

### Nicht-CQ-Freq-bezogene offene Punkte (aus älterem TODO)
1. **Even/Odd dedizierter Timer** — unabhängig vom Decoder-Thread (FT2 kritisch)
2. **Gain-Bias beheben** — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
3. **CQ-Zusammenfassung RX-Liste** — DeepSeek-Idee: ins QSO-Panel verschieben
4. **Tertile-Analyse Statistik** — kein Datencropping, alle Werte in 3 Drittel
5. **AP-Lite Test-Pipeline** — synthetische E2E-Tests vor jedem Code-Fix
6. **IC-7300 Fork** — TARGET_TX_OFFSET dort separat messen
7. **Warteliste-Screenshot** — sobald DL3AQJ antwortet

## Warnungen & Fallen

- **DeepSeek V4** — neues Modell, jede Antwort am Code verifizieren
- **`SWEET_SPOT_MIN_HZ`/`MAX_HZ` gibt's nicht mehr** — falls in altem Code/Test
  Verweis auftaucht: war v0.58-Sackgasse, v0.59 entfernt
- **Histogramm-Refresh muss IMMER pro Slot laufen** — niemals einen
  `if messages:` Guard um `_refresh_diversity_freq_view()` legen, sonst
  P1-Bug zurück (hängende Anzeige, Counter-Drift)
- **CQ-Such-Periode = 60 s konstant alle Modi** — < 30 s killt QSO-Aufbau
  weil antwortende Stationen auf alter TX-Frequenz fixiert sind
- **`_search_slots_remaining` muss in `set_mode()` UND `reset()` gesetzt** —
  Bandwechsel/Modus-Wechsel braucht harten Reset
- **AP-Lite** — `AP_LITE_ENABLED = True` aber ungetestet, nicht anfassen
- **OMNI-TX** — deaktiviert (Easter Egg: Klick auf Versionsnummer)
- **TARGET_TX_OFFSET = -0.8** — FlexRadio-spezifisch, IC-7300 braucht eigenen Wert
- **cache.save() nie im Cycle-Loop** — refresht Timestamp → 2h Gültigkeit sinnlos

## Test-Suite Status
`./venv/bin/python3 -m pytest tests/ -q` → **211 passed** ✓

## Letzter bekannter guter Zustand
- Branch `main`, alle Commits lokal (kein Push ohne Mike-Freigabe)
- App v0.59 läuft, 20 m FT8 Diversity DX getestet
- TX-Suche funktioniert glatt slot-synchron
- Statistik-PDFs (DE + EN) aktuell mit 25.04-Daten

## Nicht gepusht (lokal seit `66f44c8` Feierabend Session 3)
- v0.58: 5 Commits (`b7a06b5`, `b15c62a`, `255b0f9`, `06afbd8`, `392eb17`)
- v0.59: 4 Commits (`334a246`, `c4fa032`, `419ab52`, `af9dfb8`)
- Total 9 Commits ungepusht — warten auf Mike-Freigabe
