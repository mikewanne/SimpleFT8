# Temporale Polarisations-Diversity

[English](DIVERSITY.md) | **Deutsch**

[Zurueck zur README](../README_DE.md) | [DX Tuning](DX_TUNING_DE.md) | [Leistungsregelung](POWER_REGULATION_DE.md)

## Die Idee

FT8 arbeitet mit 15-Sekunden-Empfangszyklen. In jedem Zyklus hat der Decoder genau eine Chance, das aufzunehmen, was auf der Frequenz passiert. Wenn deine Antenne gerade in einem Fading steckt, verpasst du Stationen, die eigentlich perfekt dekodierbar waren — du hast nur nicht mit der richtigen Antenne gehoert.

SimpleFT8 nutzt beide Antennenanschluesse des FlexRadio und wechselt in jedem Zyklus zwischen ihnen. Stationen, die auf ANT1 und ANT2 dekodiert werden, fliessen in eine gemeinsame Liste. Wenn eine Station auf beiden Antennen erscheint, wird der bessere SNR behalten.

Das ist keine neue Idee in der HF-Technik — temporale Diversity ist ein bewaehrtes Verfahren. Neu ist die Anwendung auf die feste 15-Sekunden-Zyklusstruktur von FT8, bei der die Umschaltkosten null sind (du verlierst nichts durch den Wechsel zwischen den Zyklen).

## So funktioniert es

1. **Zyklus N** (gerade): Empfang auf ANT1, Dekodierung, Stationen zur Liste hinzufuegen
2. **Zyklus N+1** (ungerade): Empfang auf ANT2, Dekodierung, neue Stationen hinzufuegen, SNR fuer bekannte aktualisieren
3. **Wiederholen**: Die akkumulierte Liste waechst mit Stationen beider Antennen

Jede Station im RX-Panel zeigt, welche Antenne sie dekodiert hat:
- **A1** — nur auf ANT1 gehoert
- **A2** — nur auf ANT2 gehoert
- **A1>2** — auf beiden gehoert, ANT1 hatte besseren SNR
- **A2>1** — auf beiden gehoert, ANT2 hatte besseren SNR

Stationen werden nach 2 Minuten ohne Kontakt ausgeblendet.

## UCB1 Adaptives Verhaeltnis

Im AUTO-Modus wechselt SimpleFT8 nicht immer 50:50. Es verwendet den UCB1 (Upper Confidence Bound) Algorithmus — einen Multi-Armed-Bandit-Ansatz — um das optimale Verhaeltnis zu finden.

Wenn ANT1 konsistent mehr Stationen liefert, verschiebt sich das Verhaeltnis Richtung 70:30 (7 Zyklen ANT1, 3 Zyklen ANT2). Wenn beide gleich gut sind, bleibt es bei 50:50. Der Explorationsbonus stellt sicher, dass die schwaechere Antenne weiterhin regelmaessig getestet wird, damit sich das System anpasst, wenn sich die Bedingungen aendern.

Nach 80 Zyklen (~20 Minuten) misst das System automatisch neu.

**Warum nicht einfach die bessere Antenne nehmen und dabei bleiben?**
Weil sich "besser" aendert. Ionosphaerisches Fading, Wind bewegt Antennen, lokale Stoerquellen — was vor 5 Minuten die bessere Antenne war, muss es jetzt nicht mehr sein. UCB1 balanciert Exploitation (die aktuell bessere Antenne haeufiger nutzen) mit Exploration (die andere weiterhin pruefen).

## Messergebnisse

Kontrollierter Test auf 40m, 3. April 2026, FlexRadio FLEX-8400M, gleiche Antennen (ANT1 + ANT2), 2 Minuten Abstand:

| Modus | Stationen | Zeit (UTC) |
|-------|:---------:|:----------:|
| Normal (nur ANT1) | 27 | 16:31 |
| Diversity (ANT1+ANT2) | 37 | 16:33 |

**+37% mehr Stationen** mit Diversity, gleiche Hardware, nahezu identische Bedingungen.

### Normal-Modus — 27 Stationen
![Normal-Modus 40m](screenshots/normal_27stations_40m.png)

### Diversity-Modus — 37 Stationen
![Diversity-Modus 40m](screenshots/diversity_37stations_40m.png)

Beachte die Ant-Spalte rechts: A1, A2, A1>2, A2>1 — zeigt, welche Antenne jede Station beigesteuert hat. Mehrere Stationen (z.B. Kasachstan mit 4323 km) wurden nur ueber eine bestimmte Antenne dekodiert.

## Was du brauchst

- Ein beliebiges FlexRadio mit zwei Antennenanschluessen (funktioniert auch auf Single-SCU Modellen)
- Zwei Antennen (koennen sehr unterschiedlich sein — Draht + Vertikal, Beam + Loop, usw.)
- SimpleFT8 uebernimmt die Antennenumschaltung ueber die SmartSDR API

## Einschraenkungen

- Funktioniert nur waehrend RX-Zyklen — TX verwendet immer die vom Radio gewaehlte Antenne
- Die Verbesserung haengt davon ab, wie unterschiedlich deine Antennen sind. Zwei identische Antennen am selben Mast bringen wenig
- Beste Ergebnisse, wenn die Antennen unterschiedliche Polarisation, Hoehe oder Ausrichtung haben
