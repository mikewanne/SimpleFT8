# DT-Zeitkorrektur

## Kurz gesagt

SimpleFT8 nutzt das FT8-Band selbst als Zeitreferenz. Der Median-DT (Delta Time) aller dekodierten Stationen zeigt, ob die eigene Uhr driftet — und korrigiert das automatisch.

## Das Problem

FT8 braucht praezises Timing. Das Protokoll toleriert etwa +-1 Sekunde, aber die Dekodierqualitaet verschlechtert sich merklich jenseits von +-0,5 Sekunden. Schlimmer noch: Das eigene TX-Timing beeinflusst, wie gut ANDERE Stationen DICH dekodieren — schlampiges Timing bedeutet weniger PSKReporter-Spots und weniger Antworten auf CQ.

Mehrere Faktoren arbeiten gegen dich:

- **NTP ist gut, aber nicht genug.** Es synchronisiert die Systemuhr auf UTC, weiss aber nichts ueber die Audio-Verarbeitungslatenz zwischen Software und Radio.
- **Dein FlexRadio hat Latenz.** Audio wandert vom Radio ueber VITA-49 UDP, durch den OS-Audio-Stack, in SimpleFT8. Dieser Weg ist nicht instantan, und die Verzoegerung ist nicht konstant.
- **Kleine Drifts akkumulieren sich.** 50ms Drift pro Stunde sind anfangs unsichtbar. Nach 4 Stunden Betrieb bist du 200ms daneben — genug, um die Dekodierraten messbar zu beeinflussen.
- **Kein Internet = kein NTP.** Portabelbetrieb, Contest-Fielddays oder einfach eine wackelige Internetverbindung — NTP ist weg, und deine Uhr ist auf sich allein gestellt.

## Wie funktioniert es?

Jede dekodierte FT8-Nachricht kommt mit einem DT-Wert — dem Zeitversatz zwischen dem erwarteten Ankunftszeitpunkt (basierend auf deiner Uhr) und dem tatsaechlichen Ankunftszeitpunkt. Der Decoder berechnet das automatisch waehrend der Sync-Erkennung.

Der entscheidende Punkt: Wenn EINE Station DT = +0,4s zeigt, hat vielleicht diese Station eine schlechte Uhr. Aber wenn ALLE 20 Stationen in einem Zyklus DT um +0,4s zeigen, liegt das Problem nicht bei denen — sondern bei uns. Unsere Uhr geht 0,4 Sekunden nach gegenueber dem Band-Konsens.

SimpleFT8 nutzt das aus:

1. **DT-Werte sammeln** aus allen dekodierten Nachrichten eines Zyklus. Ausreisser verwerfen (nur Werte zwischen -2,0s und +2,0s sind gueltig).
2. **Minimum 5 Stationen voraussetzen.** Darunter ist die Stichprobe zu klein zum Vertrauen.
3. **Den Median-DT nehmen.** Nicht den Durchschnitt — den Median (siehe unten warum).
4. **EMA-Glaettung anwenden** (exponentieller gleitender Mittelwert, Alpha = 0,3):
   ```
   neue_korrektur = 0,7 * alte_korrektur + 0,3 * median_dt
   ```
5. **Totzone: 50ms.** Wenn der Betrag des Median-DT kleiner als 50ms ist, wird kein Update angewandt. Das verhindert, dass die Korrektur dem Messrauschen hinterherlaeuft.
6. **get_time() anpassen.** Die Korrektur fliesst in alle Timing-Berechnungen ein. TX startet zum korrigierten Zeitpunkt, unter Beruecksichtigung von sowohl Uhr-Drift ALS AUCH Radio-Latenz.

## Warum Median und nicht Durchschnitt?

Stell dir einen Zyklus mit 20 dekodierten Stationen vor:

```
DT-Werte: +0,3  +0,4  +0,3  +0,5  +0,4  +0,3  +0,4  +0,5  +0,4  +0,3
          +0,4  +0,3  +0,5  +0,4  +0,3  +0,4  +0,3  +0,5  +0,4  +1,8
```

Die letzte Station hat DT = +1,8s — vermutlich eine kaputte Uhr auf deren Seite, oder QSB hat die Sync-Erkennung verfaelscht.

- **Durchschnitt:** (Summe / 20) = +0,46s — nach oben gezogen durch den einen Ausreisser.
- **Median:** +0,4s — ignoriert den Ausreisser komplett.

Mit 20+ Stationen pro Zyklus ist der Median extrem robust. Selbst wenn 5 Stationen miserables Timing haben, spiegelt der Median immer noch den Mehrheitskonsens wider. Das ist derselbe Grund, warum Medianfilter in der Bildverarbeitung und Sensorfusion eingesetzt werden — sie sind von Natur aus resistent gegen Ausreisser.

## Die Mathematik

Die Korrektur-Aktualisierung folgt einem exponentiellen gleitenden Mittelwert:

```
C_neu = C_alt * (1 - alpha) + DT_median * alpha
```

Mit Alpha = 0,3:

```
C_neu = C_alt * 0,7 + DT_median * 0,3
```

Das bedeutet:

- **30% jeder neuen Messung** fliessen in die Korrektur ein.
- **70% der vorherigen Korrektur** bleiben erhalten.
- Nach einem ploetzlichen Sprung dauert es etwa 5-7 Zyklen (~75-105 Sekunden) bis zur Konvergenz auf den neuen Wert (Zeitkonstante = 1/Alpha ≈ 3,3 Zyklen).
- Die Glaettung verhindert, dass die Korrektur aufgrund von Messrauschen herumspringt, verfolgt aber dennoch echte Drift.

Totzone-Filter:

```
wenn |DT_median| < 0,050:  → kein Update (Messrauschen)
```

Gueltiger DT-Bereich:

```
-2,0s <= DT <= +2,0s  → gueltig (fuer Median-Berechnung verwendet)
ausserhalb             → verworfen (offensichtlich kaputte Station oder Sync-Fehler)
```

## Erwarteter Gewinn

- Haelt das TX-Timing innerhalb von +-100ms des Band-Konsens. Ohne Korrektur kann die Uhr-Drift ueber mehrere Stunden 200-500ms erreichen.
- Besseres Timing bedeutet, dass Empfangsstationen dich zuverlaessiger dekodieren. Das uebersetzt sich direkt in mehr PSKReporter-Spots und mehr Antworten auf CQ.
- Selbstkalibrierend: keine NTP-Abhaengigkeit, kein GPS, kein Internet noetig. Das FT8-Band IST die Zeitreferenz. Solange andere Stationen senden (und das tun sie immer auf aktiven Baendern), funktioniert die Korrektur.
- Beinhaltet automatisch die Radio-Latenz. NTP korrigiert nur die Systemuhr — es hat keine Ahnung, dass dein FlexRadio 50-150ms Audio-Verarbeitungsverzoegerung hinzufuegt. Die DT-Korrektur sieht das Ende-zu-Ende-Timing so wie andere Stationen es wahrnehmen.

## Vor- und Nachteile

| Vorteil | Nachteil |
|---------|----------|
| Selbstkalibrierend aus realer Bandaktivitaet | Braucht mindestens 5 Stationen pro Zyklus |
| Beinhaltet Radio-Audio-Latenz automatisch | Erste ~3 Zyklen: keine Korrektur (Daten werden aufgebaut) |
| Kein Internet, NTP oder GPS erforderlich | Glaettungsfaktor 0,3 koennte bei ploetzlichen Spruengen zu langsam oder bei stabilen Uhren zu schnell sein |
| Robuster Medianfilter ignoriert Ausreisser-Stationen | 50ms-Totzone bedeutet, dass sehr kleine Drifts nie korrigiert werden |
| Funktioniert auf jedem Band mit FT8-Aktivitaet | Auf einem toten Band mit <5 Stationen pausiert die Korrektur |

## Status

**UNGETESTET** — Code fertig (v0.21, `core/ntp_time.py`), Feldvalidierung steht noch aus.

Im Feldtest zu pruefen:
- **Vorzeichenkonvention:** Bedeutet positiver DT_median, dass unsere Uhr nachgeht oder vorgeht? Der Code nimmt "nachgehend" an (addiert positive Korrektur). Falls PSKReporter-Spots nach Aktivierung schlechter werden, stimmt das Vorzeichen nicht.
- **Glaettungsfaktor:** 0,3 koennte Feintuning brauchen. Zu hoch = zittrige Korrektur. Zu niedrig = zu langsam um reale Drift zu verfolgen.
- **Totzone:** 50ms koennten zu konservativ oder zu aggressiv sein. Die rohen Median-DT-Werte loggen und pruefen.

Auf `[DT-Korr] Median=+X.XXXs -> Korrektur=+X.XXXs (n=XX)` im Log achten.
