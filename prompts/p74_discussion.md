# P74 — UX-Konsolidierung + Autogain-Konzept (Diskussion)

Du bist DeepSeek-V4-pro. Mike (Funker, Owner) hat 2 UX/Konzept-Wünsche
nach P71-Field-Test 18.05.2026 vormittags. Beide brauchen Konzept-
Diskussion BEVOR Code-Plan.

## Projekt-Kontext (kurz)

**SimpleFT8** — Hobby-Funker-Tool für FlexRadio, FT8/FT4/FT2. Aktueller
Stand v0.97.47, Tests 1453 grün.

**Hardware-Pflicht ANT1=TX only, ANT2=RX only** (Hardware-Schaden
möglich bei TX auf ANT2). Diversity-Modus nutzt beide für RX, TX immer
ANT1.

**Mike-Projekt-Philosophie:**
- Hobby-Tool, KEIN Contest-Tool
- KISS schlägt Eleganz
- Modern (dunkles Theme, Live-Visualisierung) statt 90er-WSJT-X-Stil
- „Hilft das einem Hobby-Funker beim Hobby-Funken?" muss JEDES Feature
  bestehen

## Punkt 1 (P74-A): Modal-Konsolidierung

**Mike-Beobachtung 18.05.:** Bei Bandwechsel auf 30m wurde Auto-TUNE
korrekt ausgeführt (P71 fix bestätigt). Aber DANACH ploppte direkt
DXTuneDialog auf (Diversity-Gain-Kalibrierung, 8 Zyklen × 15s = 2 Min)
weil für 30m kein Preset existierte.

**Mike-Quote:** „kann man das nicht in ein und den selben fenster
unterbringen viele fenster die aufploppen verwirren. Ein fenster was
erst die aktion und das beenden anzeigt ist übersichtlicher."

**Aktueller Code-Pfad (`ui/mw_radio.py:_on_band_changed`):**
1. Auto-TUNE Dialog öffnet (modal blockend) → schließt nach Erfolg
2. `_check_diversity_preset(band, mode, scoring)` läuft
3. Wenn kein Preset → `_start_dx_tuning()` → DXTuneDialog öffnet (modal)
4. Nach 2 Min: Dialog zeigt Ergebnisse → User clickt „Übernehmen"
5. Bei SWR-bad-TUNE: separates QMessageBox („Tuner konnte nicht
   matchen") — also potenziell 3. Fenster.

**Mein Lösungs-Vorschlag (KISS):**
- AutoTuneDialog am Ende NICHT sofort schließen, sondern als
  State-Machine-Dialog 3 Phasen anzeigen:
  - Phase „TUNE" → existing Auto-TUNE-Sequenz
  - Phase „Erfolg/Misserfolg-Banner" (2-3 s sichtbar)
  - Phase „Kalibrierung" wenn Diversity-Modus + kein Preset (statt
    separater DXTuneDialog)
- Cancel-Button durchgehend verfügbar.
- Am Ende: gleicher Dialog zeigt finale Ergebnis-Zeile + „Fertig"-Button.

**Frage an dich:**
1. Ist die State-Machine-Dialog-Lösung das richtige Pattern, oder
   gibt es einen einfacheren Weg (z.B. DXTuneDialog als embedded Widget
   in AutoTuneDialog)?
2. Was sind Race-Condition-Risiken bei dieser Konsolidierung? Aktuell
   schließt AutoTuneDialog mit `accept()/reject()` → MainWindow-Code
   läuft weiter → öffnet DXTuneDialog. Wenn alles in 1 Dialog:
   wer triggert die Phase-Wechsel?
3. KISS-Trade-off: lohnt sich der Refactor oder reicht es, einfach den
   DXTuneDialog visuell anders zu gestalten (z.B. weniger „pop-up"-mäßig)?
4. Gibt es UI-Frameworks-Idiom für „Multi-Step-Wizard mit Fortschritt"
   in PySide6 das hier passen würde?

## Punkt 2 (P74-B): Autogain-Konzept

**Mike-Wunsch 18.05.:** „Lass uns prüfen wie weit wir Autogain
verwirklichen können."

**Aktueller Zustand:**
- Diversity-Gain-Kalibrierung: 1× pro (band, FT-Mode) via 8-Zyklen-
  Mess-Session. Speichert Preset in `~/.simpleft8/kalibrierung/
  presets_standard.json` + `presets_dx.json`.
- Gain bleibt fix bis User neu kalibriert.
- P51-Bundle (v0.97.28): Eine Mess-Session liefert BEIDE Auswertungen
  (Std + DX) → 50% gespart.

**Mögliche Stufen von „Autogain":**
- **(a) Auto-Re-Kalibrierung:** Preset > 7/14/30 Tage alt → Vorschlag
  „Neu kalibrieren?" beim Band-Switch.
- **(b) Live-Gain-Adjustment:** während Betrieb Gain nachregeln basierend
  auf decoded stations / SNR-Distribution. Z.B. wenn Stations-Anzahl in
  letzten 10 Slots einbricht → Gain +5 dB testen.
- **(c) Smart Initial-Gain (Cross-Band-Interpolation):** wenn 40m + 20m
  schon kalibriert, 30m beim erstmaligen Wechsel via Interpolation
  schätzen statt 2-Min-Mess-Pflicht. Analog zu `_kruecken_skalierung`
  aus P54-FIX RFPresetStore.
- **(d) SNR-basierte Live-Feinjustierung:** wenn dominierende Stationen
  alle > -5 dB → Gain runter (Übersteuerung), wenn alle < -20 dB →
  Gain hoch.

**Bewertung pro Stufe:**
- (a) KISS, niedrig-risiko, hoher Nutzen (User muss nicht selbst tracken
  wann Preset alt wird).
- (b) hoch-risiko (Funkverkehr stören), Hobby-Kontext fragwürdig,
  Komplexität hoch.
- (c) mittel-risiko (Interpolation kann daneben sein, aber Krücke wie
  P54 ist akzeptiert), Nutzen hoch (2 Min gespart pro neues Band).
- (d) mittel-risiko (SNR-Distribution-Analyse nicht trivial),
  Komplexität hoch, Nutzen mittel.

**Frage an dich:**
1. Welche Stufen sind für Hobby-Funker wirklich sinnvoll (Projekt-
   Philosophie)?
2. Welche Risiken übersehe ich? Z.B. Mess-Drift durch Solar-Zyklus,
   Tageszeit, Antennen-Wetter?
3. Cross-Band-Interpolation (Stufe c): welche Variablen müssen
   interpoliert werden? Aktuell speichern wir `ant1_gain, ant2_gain,
   ratio`. Wie zuverlässig ist lineare Interpolation über Frequenz?
4. Auto-Re-Kalibrierung (Stufe a): empfohlener Decay-Zeitraum?
   7 Tage vs 14 vs 30?
5. Implementierungs-Reihenfolge: was zuerst? KISS-Strategie für ersten
   Wurf?

## Format

Strukturiere deine Antwort in 2 Sektionen (P74-A, P74-B). Pro Sektion:
1. Deine Empfehlung (kurz, klar)
2. Trade-offs
3. KISS-Check (Hobby-Funker-Use-Case?)
4. Erste Code-Skizze (nur Architektur, kein vollständiger Code)

Halte dich kurz. Max 1500 Wörter total.
