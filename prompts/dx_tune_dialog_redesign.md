# Design-Diskussion: Einmess-Fenster (DXTuneDialog) kleiner + übersichtlicher

Du bist UX-Reviewer für ein **Hobby-Funker**-Tool (SimpleFT8, PySide6/Qt-Desktop-
Dialog, KISS-Philosophie, KEIN Contest-Tool). Zielgruppe: Funker, der die App startet,
ein bisschen FT8 funkt — kein Power-User. **Visueller Stil:** dunkles Theme, Neon-
Akzente. Wir besprechen NUR den **Informations-Aufbau** dieses Fortschritts-Fensters —
noch KEIN Code. Mike (User) findet es zu groß und zu verwirrend.

## Was das Fenster tut
Es misst beim Kalibrieren ~3 min lang abwechselnd ANT1 und ANT2 bei drei Gain-Stufen
(0/10/20 dB), um pro Antenne den besten Gain + den Antennen-Vergleich (Diversity) zu
ermitteln. 12 Mess-Zyklen (2 Runden × 2 Antennen × 3 Gain), je ~15 s. TX bleibt immer
auf ANT1 (Hardware-Sicherheit). Ergebnis gilt für Diversity Standard UND DX gleichzeitig.

## IST-Zustand (Screenshot-Text, von oben nach unten)
1. Fenstertitel (Titelleiste): „Diversity (Standard + DX) — Kalibrierung 20m"
2. **Großes Titel-Label (Wiederholung!):** „Diversity (Standard + DX) — Kalibrierung 20m"
3. Gelb, 2 Zeilen: „12 Zyklen interleaved • ANT1 & ANT2 bei gleichem Gain verglichen /
   Dauert ca. 3 Minuten • TX bleibt immer auf ANT1"
4. Blau fett: „Runde 1/2 — ANT1 Gain 20 dB"
5. Grau mono: „Schritt 5/12 (5/6 in dieser Runde)"
6. Kursiv blau: „Misst gleichzeitig für Standard- und DX-Modus"
7. Fortschrittsbalken mit Text: „4 / 12 Zyklen"
8. Grau klein: „Restzeit: ca. 2:00 min"
9. Grau: „Zwischenergebnisse (Top-5 SNR-Schnitt pro Kombination)"
10. Mono-Box (5 Zeilen): ANT1/ANT2 Gain-Werte mit Ø SNR + Stationszahl
11. Roter Button „Abbrechen"

Fenstergröße: fix 520 × 460-510 px.

## Probleme die ich sehe (Mike: „1/12, 5 von 12, 2/2 verwirrt")
- **Doppelter Titel** (Titelleiste + Label 2 sind identisch).
- **DREI Fortschritts-Zähler nebeneinander** mit teils verschiedenen Zahlen:
  - „Runde 1/2" (Label 4)
  - „Schritt 5/12 (5/6 in dieser Runde)" (Label 5)
  - Balken „4 / 12 Zyklen" (Label 7)
  → Der Balken zeigt `_step` (4), das Schritt-Label `_step+1` (5) → **off-by-one**,
    wirkt widersprüchlich. Und Runde/Schritt/in-Runde sind 3 Sichten auf denselben
    Fortschritt.
- **Drei Erklärtexte** (Label 3 zweizeilig + Label 6) sagen teils dasselbe; „interleaved"
  ist Fachjargon, den ein Hobby-Funker nicht braucht.
- **Zeit dreifach:** „Dauert ca. 3 Minuten" (Label 3) + Balken + „Restzeit ca. 2:00"
  (Label 8).

## Mein V1-Vorschlag (schlanker Aufbau)
```
[Titelleiste: Antennen-Kalibrierung 20m]            ← reicht als Titel

(nur falls aus TUNE-Pipeline:) ✓ TUNE OK — SWR 1.2  ← grünes Banner (bleibt)

Vergleicht ANT1 ⇄ ANT2 · TX bleibt auf ANT1 · gilt für Standard + DX
─────────────────────────────────────────
Misst gerade:  ANT2 · Gain 10 dB                    ← blau fett (was läuft)
[██████████░░░░░░░]  Zyklus 5 / 12 · noch ~2:00 min ← EINE Bar mit allem
─────────────────────────────────────────
Zwischenergebnisse  (Ø SNR pro Antenne + Gain)
┌─────────────────────────────────┐
│ ANT1   0 dB   Ø −22.5 dB   (2)  │
│ ANT1  10 dB   Ø −18.2 dB  (10)  │
│ ANT2   0 dB   Ø −16.2 dB  (10)  │
│ ANT2  10 dB   Ø −15.6 dB  (20)  │
└─────────────────────────────────┘
[ Abbrechen ]
```
Änderungen: großes Titel-Label raus (Titelleiste reicht) · 3 Zähler → 1 Balken-Zeile
(„Zyklus N/12 · noch ~M:SS"), synchron, kein off-by-one · 3 Erklärtexte → 1 knappe
graue Zeile ohne Fachjargon · Höhe von ~480 auf ~360-380 px runter.

## Meine Fragen an dich
1. **Ist mein schlankerer Aufbau richtig priorisiert** für einen Hobby-Funker? Was ist
   für ihn beim Warten wirklich relevant, was ist Ballast?
2. **Brauchen wir „Runde 1/2" überhaupt?** Oder reicht „Zyklus 5/12 · noch 2 min"? Die
   Runden-Info ist intern (Fairness ANT1/ANT2-Reihenfolge) — sieht der User einen Nutzen?
3. **„Misst gerade: ANT2 · Gain 10 dB"** — behalten (zeigt Leben/Fortschritt) oder auch
   weg (die Bar zeigt ja Fortschritt)? Ich tendiere zu behalten (eine kurze Zeile).
4. **Zwischenergebnis-Tabelle:** der eigentliche Mehrwert. Aktuell „Top-5 SNR-Schnitt".
   Spalten-Layout/Beschriftung verständlicher machbar? (Ø SNR = Mittelwert, Zahl in
   Klammern = wie viele Stationen gemittelt.)
5. **Übersehe ich etwas** das ein wartender User braucht (z.B. „du kannst weiterfunken"
   / „nicht schließen")? Oder etwas das raus kann?
6. **Overengineering-Check:** ist mein Vorschlag selbst schon zu viel, oder genau richtig?

Gib einen konkreten, priorisierten Aufbau-Vorschlag zurück (Reihenfolge + was raus/rein),
mit kurzer Begründung je Punkt. KISS, Hobby-Funker, kein Contest-Tool.
