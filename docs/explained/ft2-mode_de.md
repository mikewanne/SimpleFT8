# FT2-Modus — Ultraschnelle digitale Kommunikation

## Kurzfassung

FT2 ist ein digitaler Modus mit 3,8-Sekunden-Zyklen — viermal schneller als FT8 mit 15 Sekunden. Er ist fuer Situationen mit starken Signalen gedacht, wo Geschwindigkeit wichtiger ist als Schwachsignal-Leistung. SimpleFT8 unterstuetzt FT2 fuer Empfang und Senden, kompatibel mit Decodium 3.0 von IU8LMC.

## Was ist FT2?

FT2 ist das schnellste Mitglied der FT-Modus-Familie:

| Eigenschaft | FT8 | FT4 | FT2 |
|-------------|-----|-----|-----|
| Slot-Dauer | 15,0 s | 7,5 s | 3,8 s |
| Signaldauer | 12,64 s | 4,94 s | 2,47 s |
| Tonabstand | 6,25 Hz | 20,83 Hz | 41,67 Hz |
| Bandbreite pro Signal | ~50 Hz | ~83 Hz | ~167 Hz |
| Samples pro Symbol | 1920 | 576 | 288 |
| Empfindlichkeit | -21 dB | -17,5 dB | -12 dB |
| Geschwindigkeitsfaktor vs. FT8 | 1x | 2x | 4x |

Alle drei Modi teilen dieselbe Nachrichtenstruktur: 77-Bit-Nutzlast, LDPC(174,91)-Kodierung, 4-GFSK-Modulation. Der einzige Unterschied ist die Geschwindigkeit (Symbolrate und Slot-Timing).

## Kompatibilitaet

SimpleFT8s FT2-Implementierung ist kompatibel mit **Decodium 3.0** von IU8LMC. Das ist wichtig, weil es verschiedene FT2-Implementierungen gibt:

| Software | Kompatibel? | Hinweis |
|----------|-------------|---------|
| Decodium 3.0 (IU8LMC) | Ja | Primaere FT2-Software, gleiches Protokoll |
| WSJT-X Improved FT2 | Nein | Andere Protokoll-Variante, nicht kompatibel |
| WSJT-X Standard | Nein | Unterstuetzt FT2 gar nicht |

Stelle sicher, dass die Stationen, die du arbeiten willst, ebenfalls Decodium 3.0 oder eine kompatible Implementierung verwenden.

## FT2-Frequenzen

FT2 hat eigene, von der Community vereinbarte Dial-Frequenzen, getrennt von FT8 und FT4:

| Band | FT2 Dial (MHz) | FT8 Dial (MHz) | FT4 Dial (MHz) |
|------|----------------|-----------------|-----------------|
| 80m | 3,578 | 3,573 | 3,575 |
| 60m | 5,360 | 5,357 | — |
| 40m | 7,052 | 7,074 | 7,047 |
| 30m | 10,144 | 10,136 | 10,140 |
| 20m | 14,084 | 14,074 | 14,080 |
| 17m | 18,108 | 18,100 | 18,104 |
| 15m | 21,144 | 21,074 | 21,140 |
| 12m | 24,923 | 24,915 | 24,919 |
| 10m | 28,184 | 28,074 | 28,180 |

SimpleFT8 stellt die korrekte Dial-Frequenz automatisch ein, wenn du in den FT2-Modus wechselst.

## Technische Details

### Modulation

FT2 verwendet 4-GFSK (Gaussian Frequency Shift Keying) mit 4 Toenen, identisch zu FT4. Die Symbolrate ist gegenueber FT4 verdoppelt:

- **288 Samples pro Symbol** bei 12 kHz Abtastrate = 41,667 Symbole/Sekunde
- **103 Symbole gesamt** pro Sendung: 87 Daten + 16 Sync
- **4 Costas-Sync-Arrays** fuer Zeit- und Frequenzsynchronisation
- **FEC:** LDPC(174,91) mit 14-Bit CRC — gleiche Fehlerkorrektur wie FT8 und FT4

### Timing-Anforderungen

Weil FT2-Zyklen nur 3,8 Sekunden lang sind, ist die Timing-Genauigkeit entscheidend:

- **Erforderliche Uhrgenauigkeit:** +-50 ms (gegenueber +-200 ms bei FT8)
- SimpleFT8s DT-Korrektur erledigt das automatisch nach 2 Messzyklen (~8 Sekunden)
- NTP-Synchronisation wird dringend empfohlen

Wenn deine Uhr um mehr als ~100 ms abweicht, wird die Dekodierung fehlschlagen oder unzuverlaessig sein.

### RX-Filter

SimpleFT8 erweitert den RX-Filter automatisch auf **4000 Hz** im FT2-Modus (gegenueber 3100 Hz fuer FT8/FT4). Das ist noetig, weil FT2-Signale ~167 Hz breit sind — mehr als dreimal so breit wie FT8-Signale. Mit dem Standard-Filter von 3100 Hz wuerden Stationen am Rand des Durchlassbereichs verloren gehen.

### Signaldauer und Pause

Jeder FT2-Slot ist 3,8 Sekunden lang:
- Signal: 2,47 Sekunden (103 Symbole x 288 Samples / 12000 Hz)
- Pause: 1,33 Sekunden (verfuegbar fuer asynchrones TX-Fenster)

Die 1,33 Sekunden Pause zwischen Signalende und dem naechsten Slot-Start ist die Zeit, in der das System von TX auf RX umschaltet oder den Decoder startet.

## Wann FT2 verwenden

FT2 ist die richtige Wahl wenn:

- **Signale stark sind.** FT2s groessere Bandbreite bedeutet weniger Schwachsignal-Empfindlichkeit (-12 dB gegenueber -21 dB bei FT8). Nutze es, wenn der SNR ueber ca. -5 dB liegt.
- **Du Geschwindigkeit willst.** Ein komplettes QSO dauert ca. 20 Sekunden statt 1-2 Minuten in FT8. Theoretischer Durchsatz: bis zu 240 QSOs/Stunde.
- **Contest- oder Pile-Up-Betrieb.** Schneller Wechsel bedeutet mehr QSOs pro Stunde.
- **Die Bandoeffnung kurz ist.** Wenn eine kurze Sporadic-E-Oeffnung auftaucht, kannst du mit FT2 mehr Stationen arbeiten, bevor sie schliesst.
- **DXpeditionen und Sonderveranstaltungen.** Hoher Durchsatz fuer seltene Rufzeichen.

FT2 ist **nicht** die richtige Wahl wenn:

- **Signale schwach sind.** Unter -10 dB SNR dekodiert FT8, wo FT2 scheitert.
- **Du DX auf grenzwertigen Pfaden arbeitest.** FT8s 15-Sekunden-Slot sammelt mehr Energie.
- **Wenige Stationen auf der Frequenz sind.** Bei geringer Aktivitaet hat FT8 mehr Nutzer und bessere Chancen, einen QSO-Partner zu finden.
- **Schlechte Zeitsynchronisation.** Systeme ohne NTP koennen mit dem engen Timing Probleme haben.

## Moduswechsel in SimpleFT8

1. **FT2** im Moduswaehler im Kontrollfeld auswaehlen.
2. SimpleFT8 passt automatisch an: Dial-Frequenz, RX-Filterbreite, TX-Timing und Slot-Dauer.
3. Der Zyklus-Timer in der Statusleiste zeigt 3,8-Sekunden-Zyklen statt 15-Sekunden-Zyklen.
4. Die DT-Korrektur laedt den gespeicherten FT2-Wert (falls eine fruehere Messung existiert).
5. Die komplette QSO-Logik (Hunt, CQ, Warteliste) funktioniert identisch — nur schneller.

Du kannst jederzeit zurueck zu FT8 oder FT4 wechseln. Der Moduswechsel wird an der naechsten Zyklusgrenze wirksam.

## Tipps fuer den Betrieb

- **Zuerst Aktivitaet pruefen.** FT2 wird weniger genutzt als FT8. Schaue auf den FT2-Frequenzen nach, bevor du umschaltest — wenn niemand da ist, wechsle zurueck zu FT8.
- **NTP-Sync verwenden.** Timing-Fehler, die in FT8 harmlos sind, koennen in FT2 verpasste Dekodierungen verursachen.
- **Breitere Signale im Wasserfall erwarten.** Jedes FT2-Signal ist ~167 Hz breit, also passen weniger Stationen in den Durchlassbereich als bei FT8.
- **QSO-Abschluss ist schnell.** Pass auf — ein komplettes CQ + QSO kann in unter 30 Sekunden passieren.
- **Gleicher QSO-Ablauf.** Alles was du ueber Hunt-Modus, CQ-Modus und die Warteliste weisst, gilt auch fuer FT2. Das Protokoll ist identisch, nur die Uhr laeuft schneller.
