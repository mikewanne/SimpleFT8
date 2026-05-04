# R1-Diskussion — Diversity-Cache-Reuse beim Bandwechsel

## Rolle

Du bist Senior-Funker + Senior-Reviewer. **NUR DISKUSSION** — keine Code-
Vorschläge schreiben. Mike fragt nach ehrlicher Einschätzung. Antworte auf
Deutsch, knapp, sachlich.

## Aktueller Stand (SimpleFT8 v0.90, 2026-05-04)

- Diversity-Pipeline = Tunen → Phase 2 (Gain-Messung 12 Zyklen, ~3 Min)
  → Phase 3 (Diversity-Einmessung 6 Zyklen Pattern A1A1A2A2A1A2 = fair 3:3
  seit v0.90 KRITISCH-Fix) → Operate (60 Zyklen ≈ 15 Min, dann Re-Measure)
- Pipeline-Dauer nach Block 1: ~4:31 Min total
- **`PresetStore` existiert bereits** (`core/preset_store.py`, 6h Validity):
  - `save_gain(band, ft_mode, rxant, ant1_gain, ant2_gain, ...)` — wird
    nach Phase 2 aufgerufen
  - `save_ratio(band, ft_mode, ratio, dominant)` — wird nach Phase 3
    aufgerufen (mw_cycle.py:220)
  - `is_valid(band, ft_mode)` — Frist-Check 6 Stunden
  - Speicher: `~/.simpleft8/kalibrierung/presets_standard.json`
    + `presets_dx.json` (zwei separate Files pro Scoring-Modus)
- **`DiversityCache` separat** (`core/diversity_cache.py`, 2h):
  trackt nur Pipeline-Abschluss-Status
- **v0.74 Bug-Fix (2026-04-25):** `load_preset()` aus `DiversityController`
  GELÖSCHT — Begründung „Pattern band-spezifisch, Ratio darf NIE aus Cache
  geladen werden". Regression-Test bewacht das (`test_load_preset_removed`).
- Aktuell: `_on_band_changed()` in `mw_radio.py:265` ruft
  `_diversity_ctrl.on_band_change()` → reset → neue Phase-3-Messung
  ist Pflicht.

## Mike's Vorschlag

**Bei jedem Bandwechsel:**
1. Schaue Cache: gibt es Diversity-Ratio für `band+mode+scoring`?
2. Wenn vorhanden UND nicht älter als X → übernehmen, KEINE Mess-Phase,
   direkt Operate
3. Wenn älter als X → wie bisher Pipeline (oder nur Phase 3 wenn Gain
   noch valid)
4. Im laufenden Betrieb: alle 80 Zyklen (= 20 Min FT8) Auto-Refresh des
   Cache-Eintrags
5. Frage: Wie groß kann X sein? Macht das Sinn?

**Mike's Use-Case:** Hobby-Funker. App starten → 1-3 Stunden funken →
fertig. Bandwechsel im Betrieb wenn Verbindungen weniger werden.

## Mein Vorab-Standpunkt (kannst du angreifen)

**Macht Sinn — aber Risiken:**

1. v0.74-Bug-Fix-Logik: damals war Cache global (nicht band-spezifisch),
   v0.74 beendete das. Mike's Vorschlag ist band-spezifisch (`band+mode+scoring`)
   → Begründung „Pattern band-spezifisch" gilt nicht mehr — das ist OK.

2. Was sich tageszeitlich ändert: Bandbedingungen, Stationen-Anzahl,
   8 %-Schwellwert-Entscheidung 70:30 vs 50:50. Antennen-Hardware
   stabil.

3. Statistik-Daten 20m FT8 (Stand 26.04.): Diversity_Normal +15-30 % im
   Tageshoch — Ratio wechselt also durchaus innerhalb des Tages. ANT2-
   Win-Rate 79 % (Std), 86 % (Dx) — Pre-v0.90 Bias-Daten, post-v0.90 noch
   nicht gemessen.

**Mein X-Vorschlag:** **2-4 Stunden Default**.
- 2h: Sicher, deckt typische Hobby-Session
- 4h: Großzügig, deckt halbe Tagesphase
- 6h (= aktuelle PresetStore-Validity): grenzwertig, Tag→Nacht-Übergang
  kann dazwischenliegen (besonders 18 UTC Sommer)
- 12h+: Definitiv zu viel

**Implementation-Skizze (NICHT bauen, nur denken):**
- `_on_band_changed`: nach Gain-Pipeline auch Ratio-Cache-Check
- Falls valid → `_diversity_ctrl` mit gespeicherten ratio+dominant
  initialisieren, Phase=operate setzen, Phase 3 überspringen
- Sonst: aktueller Pfad
- v0.74-Regression-Test muss überdacht werden (oder neuer Test der
  band-spezifisches Reuse explizit erlaubt)
- UI-Feedback: Toast „Diversity aus Cache (3h alt) — A1 70:30"

**Auto-Refresh alle 80 Zyklen Operate:** sinnvoll, refresht Cache
automatisch ohne extra Messung. ABER: nur Re-Measure-Endwerte speichern,
nicht den Operate-Run.

## Was ich von dir wissen will

1. **Cache-Validity X — was hältst du für vernünftig?** Kannst du
   meine 2-4h begründen oder hast du andere Erfahrungswerte aus
   Funk-Praxis (du als Senior-Funker)?

2. **Tageszeit-Variation — überschätze ich das Risiko?** Ist Antennen-
   Verhältnis tageszeitlich oft stabiler als ich denke?

3. **Risiko-Bewertung:** Welcher Edge-Case ist der schlimmste? Wie
   würde Mike merken wenn der Cache veraltet ist?

4. **Auto-Refresh-Mechanismus alle 80 Zyklen:** sinnvoll? Oder lieber
   nur explizit bei Re-Measure-Triggern?

5. **Ist die Implementation überhaupt der Mühe wert?** Pipeline ist
   nach Block 1 ~4:31 Min, nach Block 2 ~3:20 Min. Spart der Cache-
   Reuse genug bei Bandwechsel um die Komplexität zu rechtfertigen?
   Oder ist Bandwechsel im Hobby-Betrieb so selten (1-2 mal pro
   Session) dass es egal ist?

6. **Programmier-Leitsätze (CLAUDE.md):** Overengineering vermeiden.
   KISS. Drei aehnliche Zeilen besser als verfruehte Abstraktion. Wo
   stehst du im Bezug auf diesen Vorschlag?

Antworte strukturiert, **nur Meinung + Begründung**, keine Code-
Vorschläge.
