# P36 — README + Hilfe Update fuer Adaptive Diversity (v0.97.2)

## Auftrag an DeepSeek

Du bekommst 4 Text-Drafts fuer die GitHub-Hauptseite und Hilfe-Dateien von
SimpleFT8 (Hobby-FT8-Tool fuer FlexRadio, Solo-Entwickler Mike Hammerer
DA1MHH). Dein Job:

**KRITISIERE den Wortlaut, schlage Verbesserungen vor.**
NICHT die Methodik. NICHT die Diversity-Implementierung selber. NUR den
**Text**.

Pruefkriterien:
1. **Verstaendlichkeit fuer Hobby-Funker** (nicht Programmierer-Sprech)
2. **Werbe-Sprech reduzieren** (kein „revolutionary breakthrough"-Stil)
3. **Technische Korrektheit** (was wird tatsaechlich behauptet?)
4. **Zweisprachigkeit** (Deutsch + Englisch parallel — beide Versionen
   konsistent in Wirkung, nicht 1:1-Uebersetzung)
5. **Laenge** (Github-README ist begrenzt, lange Erklaerungen gehoeren in
   `docs/explained/`)

## Kontext

**SimpleFT8 v0.97.2** hat „Adaptive Diversity" eingefuehrt:
- Vorher (v0.96 und frueher): einmal pro Stunde 90 Sekunden Mess-Pause —
  beide Antennen werden in 12 Slots vermessen, Median bestimmt 50:50/70:30,
  Verhaeltnis bleibt 1h fix.
- Jetzt (v0.97): slot-fuer-slot Auswertung. 5-Slot-Rolling-Buffer pro
  Antenne (~75s bis voll). Same 8%-Median-Differenz-Schwelle. Vergleich
  alle 15s statt 1x/h. Reagiert live auf QSB / Conditions / Skip-Drift.

Mike's Vision-Zitat: *„App starten -> ein bisschen FT8 funken -> fertig.
Keine Stunden-langen Sessions mit komplexer Konfiguration."*

Statik bleibt als Fallback drin (Stufe 2 in 2-3 Wochen: Statik komplett raus).

---

## Draft 1: README.md (English) — neuer Bullet im Key-Innovations-Block

Soll als ERSTER Bullet im „Key Innovations"-Block stehen.

```markdown
- **🆕 Adaptive Diversity (v0.97)** — Antenna ratio adjusts
  **slot-by-slot in real time** based on what's actually being decoded,
  instead of one 90-second calibration measurement every hour. The
  previous method made a single decision per hour and lived with the
  result for 60 minutes; the new method evaluates a rolling 5-slot
  buffer per antenna (~75 seconds to fill) and reacts to changing
  propagation as it happens. No UI lock, no measurement pause, no
  missed slots during recalibration. When ANT2 (gutter) suddenly
  outperforms ANT1 (resonant dipole) — or vice versa as conditions
  shift — the system follows immediately. 8% median-difference
  threshold prevents flapping; live switching between 30:70, 50:50,
  and 70:30 ratios. Toggle in Settings: "Adaptive Diversity (Test
  Phase)". The static measurement method remains available as
  fallback.
```

## Draft 2: README_DE.md — neuer Bullet im „Hauptfunktionen"-Block

```markdown
- **🆕 Adaptive Diversity (v0.97)** — Das Antennen-Verhaeltnis passt
  sich **slot-fuer-slot in Echtzeit** an dem an was gerade dekodiert
  wird, statt einer 90-Sekunden-Messung pro Stunde. Die alte Methode
  hat einmal pro Stunde entschieden und mit dem Ergebnis 60 Minuten
  gelebt; die neue Methode wertet einen rollenden 5-Slot-Puffer pro
  Antenne (~75 Sekunden bis voll) aus und folgt den Bedingungen wenn
  sie sich aendern. Keine UI-Sperre, keine Mess-Pause, keine verlorenen
  Slots durch Neukalibrierung. Wenn ANT2 (Regenrinne) ploetzlich besser
  ist als ANT1 (resonanter Dipol) — oder umgekehrt bei wechselnden
  Bedingungen — folgt das System sofort. 8% Median-Differenz-Schwelle
  verhindert Flackern; wechselt live zwischen 30:70, 50:50 und 70:30.
  Toggle in Einstellungen: „Adaptive Diversity (Testphase)". Die
  statische Mess-Methode bleibt als Fallback verfuegbar.
```

## Draft 3: docs/explained/diversity-modes.md (EN) — neue Sektion am Anfang nach Intro

```markdown
## 🆕 Adaptive Diversity (v0.97) — Real-time vs Hourly

### Before (v0.96 and earlier): Static measurement
At the start of every hour, SimpleFT8 paused for **~90 seconds** to
measure both antennas. It collected 6 cycles on ANT1, 6 cycles on
ANT2, calculated the median station count, and chose a fixed ratio
(50:50 if difference < 8%, otherwise 70:30 toward the better antenna).
The ratio then stayed locked for the next hour — even if propagation
changed.

### After (v0.97): Slot-by-slot
The new adaptive method collects scores **every slot during normal
operation**. A rolling 5-slot buffer per antenna (~75 seconds total
to fill) provides median values that update with each new slot. The
same 8% threshold applies, but the comparison happens every 15
seconds instead of every hour.

### Why this matters
- **No measurement pause** — no UI lock, no skipped CQ slots
- **Follows real conditions** — QSB, skip-zone drift, time-of-day
  changes
- **No 1-hour lag** — when a band opens to North America at 18:00
  UTC, the system reacts within minutes, not at the next hour
  boundary
- **Half-state immune** — no "measurement was interrupted, presets
  file is half-written" edge cases (the old static pipeline had
  several)
```

## Draft 4: docs/explained/diversity-modes_de.md — neue Sektion (Spiegel)

```markdown
## 🆕 Adaptive Diversity (v0.97) — Echtzeit vs Stuendlich

### Vorher (v0.96 und frueher): Statische Messung
Zu jeder vollen Stunde hat SimpleFT8 die App fuer **~90 Sekunden
gesperrt** um beide Antennen zu vermessen. 6 Zyklen auf ANT1, 6
Zyklen auf ANT2, Median berechnet, festes Verhaeltnis gewaehlt
(50:50 wenn Differenz < 8%, sonst 70:30 zugunsten der staerkeren
Antenne). Dieses Verhaeltnis blieb dann eine Stunde lang fix — auch
wenn sich die Ausbreitung aenderte.

### Jetzt (v0.97): Slot-fuer-Slot
Die neue adaptive Methode sammelt Scores **in jedem laufenden Slot**.
Ein rollender 5-Slot-Puffer pro Antenne (~75 Sekunden bis voll)
liefert Median-Werte die mit jedem neuen Slot aktualisiert werden.
Dieselbe 8%-Schwelle wie vorher, aber der Vergleich passiert alle
15 Sekunden statt einmal pro Stunde.

### Warum das wichtig ist
- **Keine Mess-Pause** — keine UI-Sperre, keine ausgelassenen
  CQ-Slots
- **Folgt echten Bedingungen** — QSB, Skip-Zone-Drift,
  Tageszeit-Wechsel
- **Keine 1-Stunden-Verzoegerung** — wenn das Band um 18:00 UTC
  nach Nordamerika oeffnet, reagiert das System binnen Minuten,
  nicht erst beim naechsten Stundenwechsel
- **Immun gegen Halbzustaende** — keine „Messung wurde unterbrochen,
  Preset-Datei ist halb geschrieben"-Edge-Cases (das alte
  Statik-System hatte mehrere)
```

---

## Bitte gib zurueck:

1. **Pro Draft**: Was ist gut? Was ist schlecht? Konkrete Verbesserungen.
2. **Konsistenz EN/DE**: Wirken beide Versionen aequivalent oder hat eine
   einen anderen Ton?
3. **Hobby-Funker-Test**: Versteht ein DL-Funker ohne Programmier-Kenntnis
   was hier passiert?
4. **Werbe-Sprech-Check**: Welche Stellen klingen zu „Marketing"?
5. **Verbesserte Drafts** wenn die Aenderungen substantiell sind —
   sonst nur konkrete Diff-Vorschlaege.

Keine Methodik-Kritik. Nur Text/Sprache/Klarheit. Kurze Antwort bitte.
