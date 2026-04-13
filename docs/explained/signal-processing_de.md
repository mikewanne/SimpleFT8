# Signalverarbeitungs-Pipeline

## Kurzfassung

SimpleFT8 nutzt eine mehrstufige Signalverarbeitungs-Pipeline, um schwache FT8-Signale aus dem Rauschen herauszuholen. Drei Kerntechniken arbeiten zusammen: **Anti-Alias Resampling**, **Spectral Whitening** und **Mehrstufige Signalsubtraktion**. Zusaetzlich faengt **Window Sliding** Stationen mit ungenauen Zeitreferenzen ein.

Die gesamte Pipeline laeuft automatisch in jedem 15-Sekunden-Zyklus. Kein Drehen an Knoepfen noetig.

## Das Problem

Das Rohsignal vom FlexRadio kommt per VITA-49 mit 24 kHz Abtastrate an. FT8-Dekodierung braucht 12 kHz. Zwischen "Audio rein" und "dekodierte Rufzeichen raus" kann einiges schiefgehen:

- **Aliasing** durch plumpe Abtastratenwandlung faltet hochfrequentes Rauschen ins FT8-Band
- **Ungleichmaessiger Rauschteppich** (QRM, Birdies, Schaltnetzteile) bevorzugt saubere Frequenzen bei der Dekodierung
- **Starke Signale verdecken schwache** -- eine Station mit -5 dB ist neben einer +15 dB Station praktisch unsichtbar
- **Timing-Fehler** -- nicht jede Gegenstation hat GPS-Sync; manche sind ein paar hundert Millisekunden daneben

Ein einfacher Decoder mit simpler Abtastratenverkleinerung uebersieht einen erheblichen Anteil an Stationen. SimpleFT8 adressiert jedes dieser Probleme gezielt.

## Anti-Alias Resampling (24 kHz auf 12 kHz)

### Warum

FT8 belegt 0--3000 Hz Audio-Bandbreite. Der Decoder (ft8_lib) erwartet 12 kHz Abtastrate. Das FlexRadio liefert 24 kHz per VITA-49/DAX.

Der naive Ansatz -- einfach jedes zweite Sample wegwerfen -- erzeugt **Aliasing**: Alle Signalanteile zwischen 6 kHz und 12 kHz (die obere Haelfte des 24-kHz-Spektrums) werden ins Band 0--6 kHz zurueckgefaltet und landen direkt auf den FT8-Signalen. Auch wenn FT8 nur unter 3 kHz lebt, erhoehen Rauschen und Stoersignale oberhalb von 6 kHz den Rauschteppich durch Aliasing.

### Wie

SimpleFT8 filtert **vor** dem Dezimieren mit einem Tiefpass:

1. Entwurf eines 63-Tap FIR-Filters mit Grenzfrequenz bei 6 kHz (= Nyquist der Ziel-Abtastrate 12 kHz)
2. Fensterfunktion: Hamming (gute Nebenzipfeldaempfung, einfach zu berechnen)
3. Das 24-kHz-Audio wird gefiltert
4. Dann wird um Faktor 2 dezimiert (jedes zweite Sample behalten)

### Die Mathematik

Die Filterkoeffizienten werden als gefensterte Sinc-Funktion berechnet:

```
h[n] = sinc(2 * fc * (n - 31)) * hamming(n)     fuer n = 0..62
```

Dabei ist `fc = 6000 / 24000 = 0.25` (normierte Grenzfrequenz). Die Sinc-Funktion ist die ideale Tiefpass-Impulsantwort; das Hamming-Fenster begrenzt sie auf 63 Koeffizienten, ohne grosse Nebenzipfel zu erzeugen.

Nach der Filterung wird jedes zweite Sample behalten: `output = filtered[::2]`.

### Ergebnis

Ein sauberes 12-kHz-Signal, bei dem alles oberhalb von 6 kHz **vor** dem Downsampling entfernt wurde. Keine Aliasing-Artefakte, kein eingefaltetes Rauschen. Die 63 Taps sind ein guter Kompromiss zwischen Filterqualitaet und Rechenzeit.

## Spectral Whitening (Spektrale Weissung)

### Warum

In der Praxis ist der Rauschteppich im FT8-Passband nicht flach. Manche Frequenzen tragen mehr Stoerungen als andere -- lokales QRM, Schaltnetzteile, LED-Treiber, oder einfach die Form der Empfaengerrauschzahl. Eine Station mit -21 dB neben einem Birdie hat effektiv einen schlechteren SNR als dieselbe -21 dB Station auf einer sauberen Frequenz, auch wenn der Decoder die gleiche Leistung misst.

### Wie

Spectral Whitening normalisiert jedes Frequenzbin anhand seines lokalen Rauschpegels. Dadurch wird der Rauschteppich ueber alle Frequenzen gleichmaessig ("weiss").

Implementierung (Overlap-Add Verfahren):

1. Audio in ueberlappende Bloecke zerschneiden: **2048-Punkt-FFT**, **50% Ueberlappung** (Schrittweite 1024), Hanning-Fenster
2. Fuer jeden Block das Betrags-Spektrum berechnen
3. Fuer jedes Frequenzbin den **Median** eines gleitenden Fensters von 31 Nachbarbins nehmen -- das schaetzt den lokalen Rauschpegel
4. Jedes Bin durch seinen geschaetzten lokalen Rauschpegel teilen
5. Verstaerkung auf maximal **100-fach** begrenzen (verhindert extreme Verstaerkung in fast stillen Bins)
6. Inverse FFT zurueck in den Zeitbereich, Overlap-Add zur Rekonstruktion

### Die Mathematik

Fuer Frequenzbin `k` in Block `m`:

```
noise_floor[k] = median(|S[k-15]|, |S[k-14]|, ..., |S[k+15]|)
S_white[k] = S[k] * min(1 / noise_floor[k], 100)
```

Das 31-Bin-Medianfenster ist breit genug, um einzelne Signale zu glaetten, aber schmal genug, um frequenzabhaengige Rauschschwankungen nachzuverfolgen. Der Median (statt Mittelwert) ist robust gegenueber den Signalen selbst -- ein starker FT8-Ton in einem Bin blaest nicht den Rauschschaetzwert der Nachbarn auf.

### Ergebnis

Nach dem Whitening hat eine -22 dB Station neben einer lokalen Stoerquelle die gleiche Chance dekodiert zu werden wie eine -22 dB Station auf einer voellig sauberen Frequenz. In QRM-lastigen Umgebungen (40m abends, Contest-Wochenenden) bringt das geschaetzt 10--20% mehr dekodierte Stationen. Auf ruhigen Baendern ist der Effekt geringer.

**Kompromiss**: Whitening kann den effektiven SNR sehr starker Signale auf ohnehin sauberen Frequenzen leicht verringern. In der Praxis werden diese Signale trotzdem problemlos dekodiert -- der Kompromiss lohnt sich.

## Mehrstufige Signalsubtraktion (bis zu 5 Durchgaenge)

### Warum

Das ist die groesste Einzelverbesserung in der Pipeline. Die Grundidee: Nach dem Dekodieren der staerksten Stationen werden diese aus dem Audio **entfernt** und erneut dekodiert. Stationen, die zuvor hinter staerkeren verborgen waren, werden dadurch sichtbar.

Man kann es sich wie Zwiebelschichten vorstellen. Durchgang 1 findet die starken Stationen. Durchgang 2, mit diesen entfernt, findet die naechste Schicht. Und so weiter.

### Wie

1. **Durchgang 1**: Audio normal dekodieren. Liste dekodierter Nachrichten mit Frequenzen, Timing und SNR erhalten.
2. **Rekonstruktion**: Fuer jede dekodierte Nachricht (mit SNR >= -18 dB) das FT8-Signal mit dem Encoder auf exakt derselben Frequenz und demselben Timing mathematisch neu erzeugen.
3. **Subtraktion**: Das rekonstruierte Signal vom Audio-Wellenform abziehen.
4. **Durchgang 2**: Das Residual-Audio dekodieren. Neue Stationen, die vorher verdeckt waren, tauchen auf.
5. **Wiederholen** bis maximal 5 Durchgaenge. Jeder Durchgang bringt typischerweise weniger neue Stationen (abnehmender Ertrag).

Die Mindest-SNR-Schwelle von -18 dB stellt sicher, dass nur Signale subtrahiert werden, die mit hinreichender Zuverlaessigkeit dekodiert wurden. Ein falsch dekodiertes Signal zu subtrahieren wuerde Rauschen hinzufuegen statt entfernen.

### Ergebnis

Typische Verbesserung: **+30--50% mehr dekodierte Stationen** gegenueber einem Einzeldurchgang. Der Gewinn ist am groessten auf belebten Baendern (20m/40m bei Tageslicht), wo sich viele Stationen ueberlagern. Auf ruhigen Baendern mit nur wenigen Stationen gibt es weniger zu subtrahieren und der Gewinn ist geringer.

**Kompromiss**: Jeder Durchgang braucht Dekodierzeit (~50--100 ms pro Durchgang). Mit 5 Durchgaengen liegt die Gesamtdekodierzeit bei etwa 200--500 ms pro Zyklus statt ~50 ms. Auf einem modernen Mac liegt das bequem innerhalb des 15-Sekunden-FT8-Zyklus.

In seltenen Faellen kann eine imperfekte Signalrekonstruktion einem benachbarten Signal eine geringe Menge Energie entziehen. In der Praxis wurde bisher nicht beobachtet, dass dies zu verpassten Dekodierungen fuehrt.

## Window Sliding (+/-0,3 s Versatz)

### Warum

FT8-Nachrichten sind 12,64 Sekunden lang innerhalb eines 15-Sekunden-Slots. Der Decoder nimmt an, dass das Signal zu einem bestimmten Zeitpunkt beginnt (DT = 0). Aber nicht jede Station hat eine genaue Zeitreferenz -- manche sind 100--300 ms zu frueh oder zu spaet. Eine Station mit DT = +0,35 s kann am Rand des Decoder-Suchfensters liegen und uebersehen werden.

### Wie

SimpleFT8 dekodiert das Audio an drei Zeitversaetzen:

| Versatz | Samples bei 12 kHz | Wirkung |
|---------|-------------------|---------|
| 0 | 0 | Normale Dekodierposition |
| +0,3 s | +3600 | Faengt verspaetete Stationen ein |
| -0,3 s | -3600 | Faengt verfruehte Stationen ein |

Das Audio wird vor jedem Dekodierversuch um den Versatz verschoben. Ergebnisse aus allen drei Versaetzen werden zusammengefuehrt und dedupliziert (erstes Vorkommen gewinnt).

### Ergebnis

Typisch **+5--10% mehr dekodierte Stationen**, vorwiegend Grenzfaelle mit unpraezisem Timing. Die DT-Werte in den Dekodierergebnissen werden um den angewandten Versatz korrigiert, sodass die angezeigten Zeiten akkurat bleiben.

## Pipeline-Ueberblick

Die vollstaendige Pipeline fuer jeden 15-Sekunden-FT8-Zyklus:

```
VITA-49 Audio (24 kHz int16)
  |
  v
Noise-Floor-Normalisierung (Ziel: Median abs ~300)
  |
  v
Anti-Alias Tiefpassfilter (63-Tap Sinc, Hamming, fc=6 kHz)
  |
  v
Dezimierung um Faktor 2 --> 12 kHz
  |
  v
RMS Auto-Gain-Control (Ziel -12 dBFS, +/-3 dB Hysterese)
  |
  v
DC-Offset entfernen
  |
  v
Spectral Whitening (2048-Punkt-FFT, 50% Ueberlappung, 31-Bin-Median)
  |
  v
RMS-Normalisierung (-18 dBFS)
  |
  v
Window Sliding (0, +0,3 s, -0,3 s)
  |
  v
ft8_lib C-Decoder (Costas-Sync, LDPC 50 Iterationen, CRC-Pruefung)
  |
  v
Signalsubtraktion (Rekonstruktion + Subtraktion, bis zu 5 Durchgaenge)
  |
  v
Drift-Kompensation (+/-0,5, +/-1,5 Hz/s lineare Driftkorrektur)
  |
  v
Ergebnis-Fusion + Deduplizierung
```

## Erwarteter Gewinn

| Technik | Typische Verbesserung |
|---------|----------------------|
| Signalsubtraktion (5 Durchgaenge) | +30--50% mehr Dekodierungen |
| Spectral Whitening | +10--20% bei starkem QRM |
| Window Sliding | +5--10% Grenzfall-Stationen |
| Kombiniert | Bis zu 2x mehr Stationen als einfacher Decoder |

Das sind **Schaetzwerte** aus kontrollierten Tests auf 20m und 40m. Der tatsaechliche Gewinn haengt von den Bandbedingungen, Tageszeit, QRM-Pegel und der Anzahl aktiver Stationen ab. Auf einem ruhigen Band mit 5 Stationen wird man keine Verdoppelung sehen. An einem belebten 40m-Abend mit 30+ Stationen und lokalem QRM macht die Pipeline einen sehr deutlichen Unterschied.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Deutlich mehr Dekodierungen pro Zyklus | Hoeherer CPU-Verbrauch (~200--500 ms statt ~50 ms pro Zyklus) |
| Vollautomatisch, kein Eingriff des Operators noetig | Signalsubtraktion kann selten einem Nachbarsignal geringe Energie entziehen |
| Spectral Whitening behandelt QRM effektiv | Whitening kann den SNR starker Signale auf sauberen Frequenzen leicht verringern |
| Window Sliding faengt Stationen mit Timing-Problemen ein | Drei Dekodierversuche pro Durchgang erhoehen die Verarbeitungszeit |
| Alle Verfahren sind in der DSP-Literatur etabliert | Rekonstruktionsqualitaet haengt von der Encoder-Genauigkeit ab |

## Status

Getestet und stabil seit v0.5. Signalsubtraktion, Spectral Whitening und Anti-Alias Resampling bilden den Kern von SimpleFT8s Dekodiervorteil. Die Drift-Kompensation kam spaeter hinzu (v0.24) und gilt noch als experimentell.
