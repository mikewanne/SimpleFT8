# Cache-Reuse + Refactor (V1 — Diskussions-Prompt für R1)

## Auftrag

Mike will einen größeren Refactor des Diversity-Mess-Systems besprechen.
**NUR DISKUSSION** — keine Code-Vorschläge schreiben. Bewerte fachlich
und KISS-orientiert. Antworte strukturiert auf Deutsch, knapp, sachlich.

## Kontext (aktueller Stand v0.91)

- **Diversity Phase 3:** Mess-Phase 6 Zyklen × 15 s = 1:30 Min (FT8).
  Pattern v0.90 fair 3:3 (A1A1A2A2A1A2). v0.91 Adaptiv-Stop nach 4 Zyklen
  bei klarer Differenz möglich.
- **Operate-Phase:** 60 Zyklen ≈ 15 Min, dann Re-Measure.
- **Re-Measure-Trigger:** zaehler-basiert (`_operate_cycles >= OPERATE_CYCLES`).
- **Modus-Skalierung:** `_MULT = {FT8: 1, FT4: 2, FT2: 4}` skaliert
  MEASURE_CYCLES und OPERATE_CYCLES proportional zu Slot-Dauer.
- **Settings-Option:** `diversity_operate_cycles` (Default 80) für Re-Measure-Periode.
- **PresetStore:** `save_ratio()`, `is_valid()` (6 h global für Gain).
- **Cache-Schutz v0.91 #8:** Adaptiv-Stop-Ratios werden NICHT in PresetStore.
- **Normal-Modus:** kein Cache, manuelle Kalibrierung über „NEU"-Button (`btn_remeasure`).

## Mike's Vision (zu bewerten)

### Kern-Änderungen

1. **Zeit-basiertes Re-Measure (nicht Zyklen-basiert):**
   - **1 Stunde Validity** für Diversity-Ratio (statt 15 Min Zyklen-Counter).
   - Wenn letzte Messung > 60 Min her → automatisch neu messen
     (Phase 3 startet, ~1 Min, fair 3:3 Pattern bleibt).
   - **Lock:** kein Auto-Refresh während aktivem QSO oder CQ-Ruf
     (analog zu aktuell `qso_active`-Schutz).

2. **Pro-Band+Modus-Cache (statt nur Operate-Counter):**
   - PresetStore speichert `ratio + dominant + timestamp` pro `band+ft_mode+scoring`
     (z.B. `20m_FT8_standard`, `20m_FT8_dx`, `40m_FT8_standard`).
   - Beim Bandwechsel: wenn Cache-Eintrag < 1 h alt → übernehmen, Phase 3 überspringen.
   - 5-Sekunden-Hinweis-Toast (non-modal, kein Klick erforderlich):
     „Diversity aus Cache — A1 70:30, vor 23 Min gemessen".

3. **Normal-Modus raus aus dem Cache-System:**
   - Kein Auto-Refresh, kein Cache-Reuse für Normal.
   - „Normal ist normal — andere Software macht das auch nicht."
   - Manuelle Kalibrierung über bestehenden „NEU"-Button bleibt, aber **speichert nicht**.

4. **`OPERATE_CYCLES` Konstante entfernen:**
   - Logik nur noch zeit-basiert (`time.time() - _last_measured_at >= 3600`).
   - Konstante in `core/diversity.py:27` weg.
   - Settings-Option `diversity_operate_cycles` weg (`main_window.py:822`).

5. **`_MULT`-Skalierung entfernen:**
   - Aktuell: `_MULT = {FT8: 1, FT4: 2, FT2: 4}` skaliert
     MEASURE_CYCLES und OPERATE_CYCLES für FT4/FT2.
   - Neu: 1-Stunden-Frist gilt unabhängig vom Modus.
   - `mw_radio.py:821-824` entfernen.

6. **Pattern bleibt fair 3:3** (v0.90, nicht ändern).

## Code-Stellen (verifiziert)

```
core/diversity.py:27       OPERATE_CYCLES = 60
core/diversity.py:461      def should_remeasure(self, qso_active: bool)
core/diversity.py:488      property operate_cycles
core/preset_store.py:19    VALIDITY_SECONDS = 6*3600   # global, müsste split werden
core/preset_store.py:99    def is_valid(band, ft_mode)
core/preset_store.py:139   def save_ratio(band, ft_mode, ratio, dominant)
ui/main_window.py:822      OPERATE_CYCLES aus Settings
ui/mw_radio.py:821-824     _MULT-Skalierung
ui/mw_radio.py:_on_band_changed        Cache-Check muss VOR reset() rein
ui/mw_cycle.py:220         save_ratio() bereits implementiert nach Phase 3
```

## Was V0.91 #8 Cache-Schutz macht (wichtig!)

Adaptiv-Stop-Ratios setzen `_was_early_stopped = True`. mw_cycle.py
prüft das Flag und überspringt `save_ratio()`. Damit landen nur
voll-gemessene 6-Zyklen-Ratios im Cache. **Mike's Vision baut darauf auf
— Cache enthält nur „solide" Werte.**

## Was Mike implizit nicht ändern will

- Phase 3 Messung selbst (fair 3:3, 6 Zyklen, Adaptiv-Stop bei klarer Differenz)
- Phase 2 Gain-Messung (separate 6h-Validity bleibt)
- Manuellen „NEU"-Button (Diversity sofort neu einmessen)
- v0.91 Cache-Schutz (Adaptiv-Stop-Ratios nicht persistiert)

## Was R1 bewerten soll

### A) Zeit-basiertes Re-Measure

1. **1 h Auto-Refresh** — vernünftig für Hobby-Use? Oder zu aggressiv
   (15-Min-System hat sich bisher bewährt) bzw. zu lasch (Tag/Nacht-
   Wechsel kann Ratio in 1 h kippen, z.B. 18 UTC Sommer)?
2. **Trigger-Mechanismus:** time-based statt cycle-based. Vorteile?
   Nachteile? KISS-Verbesserung oder neuer Edge-Case (z.B. Uhr-Sprung,
   NTP-Korrektur, Suspend/Resume)?
3. **QSO-Lock:** existiert schon. CQ-Ruf-Lock auch nötig oder über
   `qso_active` abgedeckt?

### B) Pro-Band-Cache

4. **1 h Validity** — empfohlen ja/nein? Mike's vorheriger Vorschlag war
   2 h, du hattest 2-4 h empfohlen. Ist 1 h zu strikt oder genau richtig?
5. **5-s-Toast ohne User-Interaktion:** ausreichend Transparenz, oder
   sollte User aktiv bestätigen können „neu messen statt Cache nehmen"?
   Mike sagt: kein Klick, nur Hinweis.
6. **Schreibverhalten:** Cache wird VOR jedem Auto-Refresh überschrieben
   (gleichzeitig mit `_phase=operate`). Soll's einen separaten Save-Pfad
   geben für „bei Bandwechsel save" vs „bei Auto-Refresh save"?

### C) Normal-Modus raus

7. **Sinnvoll, dass Normal nichts cached?** Mike sagt: „andere Software
   macht das auch nicht". Stimmst du zu (Hobby-Use, Normal ist Standard)
   oder ist das ein Verlust (z.B. wenn Mike vorher manuell kalibriert hat
   wäre Wiederverwendung hilfreich)?
8. Konsequenz: Manuelle Kalibrierung in Normal-Modus berechnet einen Wert
   aber speichert nichts → User muss bei jedem App-Start neu klicken.
   Akzeptabel?

### D) Konstanten-Cleanup

9. **`OPERATE_CYCLES` Konstante entfernen** — Risiko? Wo wird die
   Konstante außer in `should_remeasure` noch verwendet (z.B. UI-Anzeige
   „Operate-Phase 12/60")?
10. **`_MULT` entfernen** — gilt nur für OPERATE_CYCLES (zeitlich) oder
    auch MEASURE_CYCLES (was bei FT4/FT2 schneller fertig ist, also
    aktuell mehr Slots = gleiche Zeit)? Mike sagt nicht explizit.
    Empfehlung?
11. **Settings-Option `diversity_operate_cycles` entfernen** — User
    verliert Tuning-Möglichkeit. Akzeptabel da Hobby-Use?

### E) Edge-Cases

12. **Cache-Alter knapp unter 1 h + Tag/Nacht-Wechsel:** z.B. Cache 55 Min
    alt aus 17:30 UTC, jetzt 18:25 UTC → Bandbedingungen können sich
    bereits geändert haben. Wie schwerwiegend?
13. **Fehlende Stationen für Re-Measure:** wenn um 03 UTC nach 1 h
    Auto-Refresh keine 5 Stationen empfangen werden (`MIN_MEASURE_STATIONS`),
    blockt Phase 3? Aktuelles `record_measurement` zählt trotzdem hoch
    (`station_count=0` → nichts gefunden). Was passiert nach 6 Slots
    ohne genug Daten?
14. **App-Suspend/Resume:** wenn Mac schläft, läuft `time.time()` weiter.
    Nach Aufwachen ist Cache 8 h alt → frische Messung. OK?

### F) KISS-Bewertung

15. **Insgesamt eine Vereinfachung oder neue Komplexität?** Konstanten
    weg = einfacher. Aber zeit-basiertes Tracking + Cache-Reuse-Logik =
    neuer Code.
16. **Fix-Aufwand-Schätzung:** Mike's Vision (kompletter Refactor)
    versus minimal-Cache-Reuse-only (aktuelle Lösung beibehalten +
    Cache-Lookup im Bandwechsel). Was ist sinnvoller?

## Mein Vorab-Standpunkt (kannst du angreifen)

**Pros:**
- Time-based statt cycle-based ist physikalisch sauberer (Antennen-
  Bedingungen ändern sich zeitlich, nicht zykluseweise).
- Konstanten-Cleanup vereinfacht das Code-Modell deutlich.
- 1-h-Cache + Auto-Refresh ist konsistent (eine Frist statt zwei: Cache-
  Reuse < 1 h vs Operate-Counter 15 Min).
- Normal raus ist sauber — keine Sonder-Cases.

**Cons:**
- Größerer Refactor als ursprünglich geplant. Höheres Risiko für
  Regressionen.
- Settings-Option weg = kein Tuning für Power-User. Aber Mike sagt:
  Hobby-Tool, KISS.
- 1 h könnte für Tag/Nacht-Übergang knapp sein (typisch 17-19 UTC).
  2 h wäre konservativer aber bedeutet 2 Re-Measures statt 4 pro Session.

**Frage:** Stimmst du der Refactor-Richtung zu? Oder ist Mike's Vision
overengineering und ein minimal-invasiver Cache-Reuse-only-Patch besser?

## Was R1 NICHT machen soll

- Code schreiben
- v0.91 Block 2 / v0.90 Pattern-Fix bewerten (sind durch)
- Tests entwerfen (kommt später)
- UI-Design vorschlagen (Toast-Layout etc.)

## Format der Antwort

Strukturiert nach A–F oben. Pro Punkt:
1. Klar/unklar
2. Schweregrad / Empfehlung
3. Begründung aus Code-Logik oder Funk-Praxis

Am Ende: **klare Gesamtempfehlung** — Mike-Vision umsetzen, abändern, oder verwerfen?
