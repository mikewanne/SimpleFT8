# Cache-Reuse + Refactor (V2 — Self-Review-Ergänzung zu V1)

## V2-Delta zu V1 (zusätzliche Findings nach Self-Review)

### Finding 1: `_MULT` betrifft auch MEASURE_CYCLES — Auswirkung klären

V1 erwähnt nur OPERATE_CYCLES für _MULT. Aber `mw_radio.py:824` skaliert
auch MEASURE_CYCLES:

```python
self._diversity_ctrl.MEASURE_CYCLES = 6 * _MULT.get(mode, 1)
# FT8: 6, FT4: 12, FT2: 24
```

Wenn Mike's Vision _MULT komplett entfernt:
- FT4 Phase 3 = 6 Zyklen × 7.5 s = 45 s (statt 90 s heute)
- FT2 Phase 3 = 6 Zyklen × 3.8 s = 23 s (statt 91 s heute)

→ FT4/FT2 messen halb/viertel so lange. Akzeptabel? Mike sagt indirekt
„fair pattern wo keine Antenne benachteiligt wird" — Pattern fair 3:3
funktioniert mit 6 Zyklen unabhängig vom Modus. Aber Stations-Anzahl
und SNR-Streuung über kürzere Zeit ist statistisch dünner.

**Frage R1:** _MULT für MEASURE_CYCLES behalten (FT4/FT2 messen länger)
oder weg (alle Modi gleich 6 Zyklen)?

### Finding 2: CQ-Lock fehlt in `should_remeasure`

V1 sagt „QSO-Lock existiert schon". Korrekt für `qso_active`. Aber
**CQ-Ruf (cq_mode=True, state=CQ_CALLING/CQ_WAIT)** ist KEIN aktiver QSO
und wird vom aktuellen `should_remeasure` NICHT geblockt.

Aktuell:
```python
def should_remeasure(self, qso_active: bool) -> bool:
    return (self._phase == "operate"
            and self._operate_cycles >= self.OPERATE_CYCLES
            and not qso_active)
```

Mike's Vision: kein Auto-Refresh während CQ-Ruf. → API-Erweiterung:
`should_remeasure(qso_active, cq_active)` oder kombiniertes Flag.

### Finding 3: Timestamp-Konflikt PresetStore

PresetStore-Eintrag aktuell:
```json
{
  "rxant": "ANT1", "ant1_gain": 10, "ant2_gain": 20,
  "ant1_avg": -8.5, "ant2_avg": -10.2,
  "ratio": "70:30", "dominant": "A1",
  "timestamp": 1714567890,
  "measured": "2026-05-04 13:45"
}
```

Ein einziger `timestamp` für Gain UND Ratio. Mike will 1 h für Ratio,
6 h für Gain. → Brauchen wir 2 Felder (`gain_timestamp`, `ratio_timestamp`)?

**Frage R1:** Saubere Lösung: 2 Timestamps. KISS-Lösung: 1 Timestamp,
nur Ratio-Frist (1 h) entscheidet ob Phase 3 übersprungen wird, Gain-
Frist (6 h) entscheidet ob Phase 2 übersprungen wird. Bei Re-Save wird
nur ratio_timestamp aktualisiert.

### Finding 4: App-Start mit gültigem Cache

V1 nennt nur Bandwechsel. Aber: bei App-Start mit Cache < 1 h alt →
soll Phase 3 ebenfalls übersprungen werden?

Aktuell läuft beim App-Start die Pipeline immer durch (wenn Diversity
aktiv ist). Mike's Vision impliziert: ja, App-Start mit valid Cache =
direkt Operate. Aber ist Cache nach Suspend/Resume/Crash zuverlässig?

### Finding 5: Bandpilot-Wechsel + Cache-Reuse

Wenn Bandpilot um 17 UTC sagt „wechsle auf 20 m" und Cache ist da → 5-s-
Toast erscheint, kein Klick erforderlich. **Ist das transparent genug
oder zu schnell** für den User um zu verstehen warum die Pipeline
übersprungen wurde?

### Finding 6: `_was_early_stopped`-Flag bei Cache-Load

Wenn Cache geladen wird (Phase 3 übersprungen) → Pipeline läuft direkt
in operate. Was passiert mit `_was_early_stopped`?

- Cache-Eintrag stammt aus voll-gemessener Pipeline (Cache-Schutz v0.91 #8)
- Bei Cache-Load setzen wir Phase=operate ohne `_was_early_stopped` zu setzen
- Nach 1 h Auto-Refresh läuft Phase 3 wieder normal → save_ratio greift normal

→ Sollte stimmen. Aber Edge-Case: was wenn beim Cache-Load aus Versehen
`_was_early_stopped=True` gesetzt würde? Dann würde nach 1 h Auto-Refresh
KEIN save erfolgen → Cache veraltet weiter. Bug-Falle.

### Finding 7: Tests-Migration

`tests/test_diversity_bandwechsel.py` hat `test_load_preset_removed` —
bewacht v0.74-Bug-Fix dass kein global-Cache verwendet wird. Mike's
Vision führt band-spezifischen Cache wieder ein → Test muss umgeschrieben:
„band-spezifisches Reuse erlaubt, globales weiterhin nicht".

## V2-Zusatz-Fragen an R1

### G) Code-Migration

17. **`MEASURE_CYCLES`-Skalierung:** _MULT behalten (FT4/FT2 messen länger)
    oder entfernen (alle Modi 6 Zyklen)?

18. **PresetStore-Timestamp:** 1 oder 2 Timestamps? Was ist KISS?

19. **App-Start mit Cache:** Phase 3 überspringen oder immer messen?
    Risiko bei Suspend/Resume.

20. **Tests-Migration:** Wie testet man „Cache wird geladen bei
    Bandwechsel" sauber? Mock-PresetStore + Aufruf von `_on_band_changed`?

### H) UX-Edge-Cases

21. **5-s-Toast Sichtbarkeit:** reicht das? Oder sollte es bleiben bis
    User klickt? (Mike sagt: nein, kein Klick — aber prüf ob das
    transparent genug ist).

22. **Cache-Reuse + Auto-Hunt:** wenn Auto-Hunt Bandwechsel triggert
    und Cache-Reuse spart 1 Min, wird Auto-Hunt früher aktiv. OK?

## V2-Zusatz: KISS-Variante als Alternative

Falls R1 sagt Mike's Refactor ist zu groß, alternative minimal-Variante:

**Variante MINI** (nur Cache-Reuse, alles andere bleibt):
- PresetStore bekommt `RATIO_VALIDITY_SECONDS = 3600` separat von Gain
- `_on_band_changed` prüft `is_valid_ratio(band, mode)` VOR
  `_diversity_ctrl.on_band_change()`
- Wenn ja → ratio+dominant laden, Phase=operate setzen, Toast
- Wenn nein → aktueller Pfad
- **OPERATE_CYCLES, _MULT, Settings-Option bleiben unverändert**
- Auto-Refresh bleibt zaehler-basiert (60 Zyklen)

Aufwand MINI: ~1-2 h
Aufwand MIKE-VISION: ~3-5 h

**Frage R1:** MIKE-VISION konsequent durchziehen oder MINI als
Zwischenschritt? Mike's Argument für VISION: KISS durch weniger
Konstanten + Settings + Modus-Skalierungen.

## Format Antwort R1

Strukturiert nach A–H. Klare Empfehlung am Ende:
- VISION (Mike's komplette Refactor-Idee) ?
- MINI (nur Cache-Reuse) ?
- Hybrid (was VISION übernehmen, was nicht) ?

Mit Begründung jeweils. Begründung > Antwort.

## Auftrag

Nur Diskussion. Kein Code. Kein Plan. Reine Bewertung der Refactor-
Richtung aus Code-Logik + Funk-Praxis + KISS-Sicht.
