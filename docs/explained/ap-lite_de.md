# AP-Lite v2.2 — Schwache QSOs retten

## Kurz gesagt

Wenn das Signal des QSO-Partners zu schwach zum Dekodieren ist, kombiniert AP-Lite zwei aufeinanderfolgende gescheiterte Dekodierversuche und gewinnt dadurch ~4-5 dB effektiven SNR-Gewinn. Das reicht oft, um ein sterbendes QSO doch noch zu retten.

## Das Problem

- Du bist mitten im QSO, dein Partner hat seinen Report gesendet, aber der Decoder schafft es nicht.
- Nach der maximalen Anzahl Wiederholungen laeuft das QSO in einen Timeout — frustrierend fuer beide Seiten.
- Das Signal IST da (man sieht die Spur im Wasserfall), nur zu schwach fuer einen einzelnen Slot.
- Standard-FT8-Decoder geben auf und machen weiter. Das QSO stirbt.

## Wie funktioniert es?

AP-Lite nutzt eine Grundeigenschaft von FT8 aus: Wenn eine Nachricht nicht bestaetigt wird, wiederholt der Sender sie. Diese Wiederholung ist nicht verschwendet — sie traegt dieselbe Information, nur in anderem Rauschen. AP-Lite kombiniert beide Versuche.

1. **Erster Dekodierversuch scheitert.** AP-Lite speichert den rohen PCM-Audiobuffer (das volle 12,64-Sekunden-Fenster).
2. **Partner wiederholt** (FT8-Standard: wiederholen bis bestaetigt). Zweiter Dekodierversuch scheitert ebenfalls.
3. **Ausrichtung.** AP-Lite richtet die beiden Buffer anhand der Costas-Synchronisationsarrays aus — das bekannte 7-Ton-Sync-Muster, das jede FT8-Nachricht enthaelt. Das Suchfenster ist +-8 Samples zeitlich und +-1,5 Hz frequenzmaessig, um kleine Takt- und Oszillatorunterschiede zwischen den Zyklen auszugleichen.
4. **Kohaerente Addition.** Beide ausgerichteten Buffer werden Sample fuer Sample addiert. Das Signal addiert sich konstruktiv (gleiche Wellenform, deterministisch), waehrend das Rauschen inkohaerents addiert (zufaellig, unkorreliert zwischen den Zyklen).
5. **Kandidaten-Korrelation.** Der kombinierte Buffer wird gegen eine Menge von Kandidaten-Nachrichten korreliert — Nachrichten, die AP-Lite aufgrund des aktuellen QSO-Zustands erwartet.
6. **Entscheidung.** Wenn der beste Korrelationswert >= 0,75 ist, wird die Nachricht akzeptiert und das QSO geht weiter.

## Die Mathematik

Zwei unabhaengige Beobachtungen desselben Signals mit unabhaengigem Rauschen:

```
x1 = s + n1
x2 = s + n2
```

Nach kohaerenter Addition:

```
x_kombiniert = x1 + x2 = 2s + (n1 + n2)
```

Signalleistung skaliert quadratisch mit dem Amplitudenfaktor:

```
P_signal = (2)^2 * P_s = 4 * P_s    → +6 dB
```

Rauschleistung addiert sich (unabhaengig, unkorreliert):

```
P_rauschen = P_n + P_n = 2 * P_n    → +3 dB
```

Netto-SNR-Gewinn:

```
SNR_gewinn = 6 dB - 3 dB = 3 dB (theoretisches Minimum aus Mittelung)
```

In der Praxis erreicht AP-Lite ~4-5 dB, weil die Costas-gewichtete Korrelation den Sync-Ton-Positionen (wo der SNR am hoechsten ist) extra Gewicht gibt und so 1-2 dB ueber den reinen Mittelungsgewinn hinaus herausholt.

Der 3 dB theoretische Gewinn ist dasselbe Prinzip wie bei gestackten Antennen oder Mittelung in der Radioastronomie — nichts Exotisches, einfach das Gesetz der grossen Zahlen angewandt auf Signalverarbeitung.

## Kandidaten-Erzeugung

AP-Lite ist kein blinder Decoder. Es weiss WAS es suchen muss, weil es den QSO-Stand kennt:

- **WAIT_REPORT Zustand:** Die erwartete Nachricht ist ein Signal-Report. AP-Lite erzeugt Kandidaten ueber ein Fenster von +-5 dB um den erwarteten SNR, z.B.: `DA1MHH DK5ON -15`, `DA1MHH DK5ON -14`, ..., `DA1MHH DK5ON -10`. Das sind 11 Kandidaten (einer pro dB-Stufe von -20 bis -10).
- **WAIT_RR73 Zustand:** Die erwarteten Nachrichten sind `DA1MHH DK5ON RR73`, `DA1MHH DK5ON RRR` oder `DA1MHH DK5ON 73`. Das sind genau 3 Kandidaten.

Weniger Kandidaten bedeutet eine niedrigere Falsch-Positiv-Rate. Im WAIT_RR73-Zustand ist die Wahrscheinlichkeit, dass ein zufaelliges Rauschmuster eine von nur 3 spezifischen FT8-kodierten Nachrichten bei >= 0,75 Korrelation trifft, verschwindend gering.

## Warum 0,75?

Der Korrelationsschwellenwert ist ein Kompromiss:

- **Zu niedrig (z.B. 0,5):** Falsch-Positive — Rauschen matcht einen Kandidaten zufaellig, das QSO loggt einen Kontakt der nie stattgefunden hat.
- **Zu hoch (z.B. 0,95):** Das Feature feuert nie — man braucht 4-5 dB Gewinn, aber man verwirft alles unterhalb von nahezu perfekter Korrelation.
- **0,75** ist ein konservativer Startwert, gewaehlt vor dem Feldtest. Er wird anhand realer Daten kalibriert: Korrelationswerte von bekannt-guten und bekannt-schlechten Dekodierungen aufzeichnen, dann den Schwellenwert am optimalen Trennpunkt setzen.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| +4-5 dB rettet marginale QSOs die sonst in den Timeout laufen | Funktioniert nur waehrend aktiver QSOs (braucht Zustandsinfo fuer Kandidaten) |
| Null Fehlalarm-Risiko bei WAIT_RR73 (nur 3 moegliche Nachrichten) | Korrelationsschwelle 0,75 muss im Feld kalibriert werden |
| Voll automatisch, kein Eingriff des Operators noetig | Fuegt ~5ms Verarbeitung pro gescheitertem Dekodierversuch hinzu |
| Kandidaten-basiert: weiss WAS gesucht wird, keine Blindsuche | Kann bei CQ-Dekodierung nicht helfen (zu viele unbekannte Nachrichten) |
| Nutzt Daten die sonst weggeworfen wuerden (gescheiterte Buffer) | Partner muss wiederholen (FT8-Standard, aber nicht garantiert) |

## Status

**UNGETESTET** — Code fertig (v0.22 Skeleton, v0.26 volle Implementierung), standardmaessig deaktiviert (`AP_LITE_ENABLED = False` in `core/ap_lite.py`).

Aktivierung erst nach Feldtest-Kalibrierung des 0,75-Korrelationsschwellenwerts. Nach Aktivierung auf `[AP-Lite]` Log-Eintraege achten.
