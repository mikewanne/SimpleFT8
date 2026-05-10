# R1-Auftrag: Kritischer Review von P22.PRESET-ATOMARITAET V2

## Deine Rolle

Du bist DeepSeek-Reasoner und reviewst einen Implementierungsplan
(V2) — NICHT den Code selbst (der existiert noch nicht). Dein Ziel: den
Plan kritisieren und konkret verbessern, bevor er umgesetzt wird.

**Du sollst NICHT die Probleme loesen, sondern den Plan kritisieren.**

## Kontext: SimpleFT8

SimpleFT8 ist ein Hobby-FT8-Tool fuer Mike (Funker DA1MHH). Es hat
zwei Antennen (ANT1 = TX/RX-Hauptantenne, ANT2 = nur RX-Zusatz).
Diversity-Modus dekodiert auf beiden Antennen parallel und merged
die Ergebnisse — bringt +88-124% mehr Stationen.

Diversity hat zwei Mess-Phasen:
- Phase 2 = Verstaerker-Kalibrierung (manuell oder automatisch beim Start)
- Phase 3 = Antennenvergleich (8 Zyklen, automatisch nach Phase 2)

Beide Werte werden in einer JSON gespeichert (`presets_dx.json` /
`presets_standard.json`). Die Architektur-Schwaeche: Phase 2 und Phase 3
schreiben getrennt. Wenn Phase 3 haengt, landet nur Phase 2 im File →
„Half-State". Beim Neustart triggert die App wieder Phase 3 → wenn
Wurzelbedingung noch da ist (z.B. Antennen-Switch greift nicht), endlos.

Mike's Symptom heute: DX direkt nach Start haengt bei „MESSEN 0/6", bis
er ueber Standard-Modus eine erfolgreiche Phase-3-Mess erzwungen hat.

## Was du bekommst

1. **V2-Plan** — der eigentliche Bauplan (siehe unten als Anhang)
2. **`core/preset_store.py`** — komplett (das File wird erweitert)
3. **`ui/mw_radio.py` Z. 850-1300** — relevanter Pipeline-Code
4. **`ui/mw_cycle.py` Z. 220-300** — Phase-3-Erfolgs-Pfad
5. **`core/diversity.py`** — komplett (Mess-Algorithmus + Adaptiv-Stop)

Wenn andere Files relevant scheinen, gib explizit an welche du brauchst —
ich gebe sie dir nach.

## Was du pruefen sollst

### A. Architektur des Plans

A1. Ist die Stage/Commit/Discard-API in `PresetStore` sauber? Ueberseh
    ich Edge-Cases?
A2. Ist die `is_valid_gain` Half-State-Reject-Logik korrekt? Bricht sie
    bestehende Workflows?
A3. Ist der Lifecycle-Cleanup vollstaendig (Liste in §5e)? Fehlen
    Pfade die staged-Eintraege liegen lassen?
A4. Ist der atomic-write-Refactor (`tempfile` + `os.replace`) korrekt
    fuer die Plattform (macOS)? Race-Risiken?

### B. Race-Conditions / Threading

B1. `PresetStore` hat ein `threading.Lock`. Reicht das fuer staged-Buffer?
    Welche Threads schreiben/lesen?
B2. Was wenn `_on_dx_tune_accepted` (GUI-Thread) und `_on_cycle_decoded`
    (GUI-Thread, aber Decoder-Signal) sich ueberlappen? Beide nutzen
    `_pending_dx_diversity` und `_diversity_ctrl.phase`.
B3. Bandwechsel-Race: V2-Q2 sagt „discard sofort". Was wenn
    `_on_band_changed` mid-Phase-3 feuert? Ist `tick_stall_check` dann
    sauber zurueckgesetzt?

### C. Stall-Detector

C1. Ist `STALL_LIMIT_CYCLES = 12` (~3 Min FT8) sinnvoll? Zu niedrig
    (false positive bei langsamem Mess)? Zu hoch (Mike wartet)?
C2. Pattern „N Zyklen ohne `_measure_step`-Inkrement" — gibt es Faelle
    wo `_measure_step` zwischendurch reset wird (z.B. Reset-Pfad)? Wuerde
    das den Counter false-clearen?
C3. Adaptiv-Stop und Stall-Detector — kollidieren die? Adaptiv-Stop kann
    bei `_measure_step == _early_stop_at` greifen (z.B. 4/8). Stall-Detector
    sieht dann `_measure_step` Inkrement → reset Counter. Sauber.

### D. Mike-Klaerungsfragen Q1-Q3

D1. **Q1 (Stall-Fallback):** V2-Vorschlag (b) Disable-Diversity. Was
    spricht dagegen? Wuerdest du (a) 50:50 oder (c) Hard-Stop bevorzugen?
    Warum?
D2. **Q2 (Bandwechsel):** V2-Vorschlag (a) Discard sofort. Memory-Pattern
    OK? Wuerde Keep-Pattern echte Vorteile bringen?
D3. **Q3 (Adaptiv-Stop weiter ohne Persist):** Bestehender v0.91-Schutz
    erhalten. Vernuenftig? Oder argumentiere fuer Persist.

### E. Tests

E1. Decken T1-T14 die kritischen Pfade ab? Fehlt etwas?
E2. Sind die Test-Namen aussagekraeftig?
E3. Gibt es Tests die mock-heavy sind und nichts pruefen
    (Anti-Pattern: Test-prueft-Mock-statt-Code)?

### F. Was uebersieht V2 ggf?

F1. Andere Half-State-Pfade die ich nicht mitbedacht habe?
F2. Konkurrierende Features (P17 RESOLVED — wirklich?)?
F3. Backwards-Compat-Probleme bei `is_valid_gain`-Aenderung?
F4. Ist die Plan-Struktur Compact-fest (V3 muss nach Compact lesbar
    sein)?

## Form deiner Antwort

Bitte als strukturierte Liste:

- **KRITISCH** (Bug im Plan, muss in V3 raus oder anders): konkret + Datei:Zeile-Verweis wenn moeglich
- **SOLLTE** (Verbesserung empfohlen): konkret + Begruendung
- **KOENNTE** (Optional, schoeneres Design): kurz erwaehnen
- **Q1/Q2/Q3 Antworten:** dein Vorschlag + 1 Satz Begruendung

Halluzination vermeiden: wenn du eine Behauptung ueber den Code machst,
verweise auf Datei:Zeile. Wenn du es nicht im Code siehst, sag es
explizit („vermute", „nicht im uebersendeten Code sichtbar").

KISS-Bewertung am Ende: Ist V2 angemessen schlank fuer ein Hobby-Tool
oder overengineered?

---

## V2-Plan (Anhang)

[V2-Inhalt wird vom CLI angehaengt]
