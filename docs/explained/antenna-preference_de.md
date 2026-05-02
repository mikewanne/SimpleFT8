# Antennen-Praeferenz pro Station

[English](antenna-preference.md) | **Deutsch**

## Was macht das Feature?

SimpleFT8 merkt sich pro Rufzeichen, welche Antenne die beste SNR
geliefert hat — und um wieviel dB. Beim QSO-Start wird automatisch
die richtige Antenne gewaehlt, ohne dass der Operator nachdenken
muss. Das ueberlagert die globale Diversity-Logik fuer die Dauer
des QSOs.

## Wie funktioniert es?

Diversity (Standard oder DX) trifft alle 15 Sekunden eine **globale**
Entscheidung: welche Antenne empfaengt gerade die meisten Stationen
(Standard) oder die meisten schwachen Stationen (DX). Das ist ein
Durchschnitt ueber alle empfangenen Calls.

Aber wenn DL3AQJ aus Norddeutschland kommt und ANT2 nach Norden
zeigt, ist ANT2 fuer **diese eine Station** vielleicht 6 dB besser —
egal was der Rest des Bandes sagt.

Der `AntennaPreferenceStore` (Modul `core/antenna_pref.py`) speichert
pro Callsign:

- **best_ant** — `"A1"` oder `"A2"`
- **delta_db** — wieviel dB Vorteil die bessere Antenne hat

Der Wert wird **bei jedem Empfang ueberschrieben** — kein Timeout,
kein Cache. Eine Station, die ich gerade jetzt hoere, ist die
genaueste Quelle. Hoere ich sie nicht, gibt es nichts anzurufen,
also ist auch kein historischer Wert noetig.

**Hysterese 1 dB:** Damit das System nicht hin- und herwechselt bei
Mini-Differenzen, wird ein Antennen-Wechsel erst bei mindestens
1 dB Unterschied zugelassen.

**QSO-Schutz:** Sobald ein QSO startet, friert die Antennen-Wahl
fuer diese Station ein. Die globale Diversity-Rotation pausiert,
beide Slots laufen auf der praeferierten Antenne. Nach QSO-Ende:
zurueck in den normalen Diversity-Rhythmus.

**Hardware-Pflicht:** Diese Praeferenz betrifft nur den Empfang.
TX laeuft IMMER ueber ANT1 — egal welche Antenne hier praeferiert
wird. ANT2 (Regenrinne) ist nicht fuer Sendebetrieb ausgelegt.

## Wann nuetzlich?

- **DX-Jagd:** Du willst eine seltene Station rufen, die gerade nur
  auf einer bestimmten Antenne sauber zu hoeren ist — Antenna-Pref
  waehlt automatisch die richtige.
- **Warteliste:** Mehrere Stationen rufen gleichzeitig — pro Station
  wird die optimale Antenne genommen.
- **QSO-Pingpong:** Wenn der Funkpartner zwischen Slots leicht
  unterschiedlich ankommt, bleibt die Antenne stabil.

## Wo zu finden?

- **QSO-Panel:** Bei aktivem QSO erscheint die Anzeige
  `Antworte DL3AQJ (ANT2, +6.3 dB)`.
- **Statusleiste:** `RX: A2 (+6.3 dB)` waehrend QSO.
- **RX-Panel:** Die Spalte "Antenne" zeigt den letzten Empfangs-
  Status pro Station (A1, A2, A1>2, A2>1).

Das Feature ist immer aktiv, sobald Diversity laeuft. Keine
Einstellung, kein An/Aus-Schalter — automatisches Lernen.
