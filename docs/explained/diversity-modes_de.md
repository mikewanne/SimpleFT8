# Diversity-Modi — Standard vs. DX-Bewertung

## Kurzfassung

SimpleFT8s Diversity-Funktion schaltet jeden FT8-Zyklus zwischen zwei Antennen um, um mehr Stationen zu empfangen. Der **Bewertungsmodus** bestimmt, wie entschieden wird, welche Antenne besser ist: Standard-Modus zaehlt alle Stationen (am besten fuer CQ und Contests), DX-Modus zaehlt nur schwache Stationen unter -10 dB SNR (am besten fuer DX-Jagd).

## Zwei Bewertungsmodi

| Modus | Was zaehlt | Am besten fuer | Button zeigt |
|-------|-----------|----------------|--------------|
| **Standard** | Alle dekodierten Stationen (SNR > -20 dB) | CQ-Betrieb, Contests, allgemeiner Betrieb | DIVERSITY |
| **DX** | Nur schwache Stationen (SNR < -10 dB) | DX-Jagd, seltene Stationen, lange Wege | DIVERSITY DX |

Wechsle zwischen den Modi durch Klick auf den Diversity-Button. Der aktuelle Modus wird auf dem Button angezeigt.

## Standard-Modus — Alles zaehlen

Im Standard-Modus gilt die Antenne als besser, die **mehr Stationen insgesamt** dekodiert. Das ergibt Sinn fuer den allgemeinen Betrieb: Wenn ANT1 25 Stationen dekodiert und ANT2 nur 18, hat ANT1 gerade die bessere Gesamtabdeckung.

Nutze den Standard-Modus wenn:
- Du CQ rufst und moeglichst viele Anrufer hoeren willst
- Du in einem Contest arbeitest, wo jeder Kontakt zaehlt
- Du einfach den besten Gesamtempfang willst

## DX-Modus — Schwache Signale zaehlen

Im DX-Modus zaehlen nur Stationen mit SNR unter -10 dB. Das sind die schwachen, entfernten Stationen — das DX, das du suchst. Eine starke lokale Station mit +15 dB zaehlt nicht, weil du die auf jeder Antenne hoerst.

Nutze den DX-Modus wenn:
- Du seltenes DX oder neue DXCC-Laender jagst
- Du Long-Path-Oeffnungen arbeitest, wo Signale an der Grenze sind
- Dir entfernte Stationen wichtiger sind als die Gesamtzahl

**Beispiel:** ANT1 dekodiert 25 Stationen gesamt, 3 davon unter -10 dB. ANT2 dekodiert 18 Stationen gesamt, 7 davon unter -10 dB. Im Standard-Modus gewinnt ANT1 (25 > 18). Im DX-Modus gewinnt ANT2 (7 > 3) — sie empfaengt mehr schwache DX-Stationen.

## So funktioniert die Messung

Beide Modi verwenden denselben 8-Zyklen-Messprozess:

1. **4 Zyklen auf ANT1** (2 gerade + 2 ungerade Slots): Werte sammeln
2. **4 Zyklen auf ANT2** (2 gerade + 2 ungerade Slots): Werte sammeln
3. **Auswertung:** Median-Werte beider Antennen vergleichen

Die Messung wechselt ab: A2, A1, A2, A1, A2, A1, A2, A1 — damit beide Antennen unter aehnlichen Ausbreitungsbedingungen gemessen werden.

### Median-Bewertung

SimpleFT8 verwendet den **Median** aller Messungen pro Antenne, nicht den Durchschnitt. Der Median ist robust gegen Ausreisser — ein einzelner ungewoehnlich guter oder schlechter Zyklus verzerrt das Ergebnis nicht. Mit 4 Messungen pro Antenne liefert der Median ein zuverlaessiges Bild.

### Die 8%-Schwelle

Nach der Messung vergleicht SimpleFT8 die beiden Median-Werte:

```
relative_Differenz = |Score_A1 - Score_A2| / max(Score_A1, Score_A2)
```

| Differenz | Ergebnis | Verhaeltnis |
|-----------|----------|-------------|
| Unter 8% | Antennen sind praktisch gleich | 50:50 |
| 8% oder mehr | Eine Antenne ist deutlich besser | 70:30 zugunsten der besseren |

Die 8%-Schwelle verhindert unnoetige Verzerrung, wenn beide Antennen aehnlich gut sind.

## Betriebsverhaeltnisse

Nach der Messung geht SimpleFT8 in die **Betriebsphase** und schaltet die Antennen nach dem Verhaeltnis:

| Verhaeltnis | Muster (pro 10 Zyklen) | Bedeutung |
|-------------|------------------------|-----------|
| **50:50** | A1, A1, A2, A2, A1, A1, A2, A2, ... | Beide Antennen bekommen gleich viel Zeit |
| **70:30** | A1, A1, A2, A1, A1, A2, A1, A1, A2, A1 | Dominante Antenne bekommt 7 von 10 Zyklen |
| **30:70** | A2, A2, A1, A2, A2, A1, A2, A2, A1, A2 | ANT2 dominant, gleiches Muster umgedreht |

Das 50:50-Muster nutzt 2-Zyklen-Bloecke, damit sowohl gerade als auch ungerade Slots auf jeder Antenne abgedeckt werden. Das 70:30-Muster verteilt die Zyklen der schwachen Antenne gleichmaessig, um den Diversity-Vorteil zu erhalten.

## Automatische Neumessung

Nach **60 Zyklen** Betrieb (ca. 15 Minuten) startet SimpleFT8 automatisch eine neue Messung — aber nur wenn kein QSO aktiv ist. Aktive QSOs werden nie unterbrochen.

Das stellt sicher, dass das Antennenverhaeltnis sich an aendernde Ausbreitung anpasst. Was vor 15 Minuten die bessere Antenne war, muss es jetzt nicht mehr sein.

## Bandwechsel

Beim Bandwechsel setzt der Diversity-Controller komplett zurueck und startet eine frische Messung. Das ist noetig, weil die Antennenleistung auf 20m nichts mit der Leistung auf 40m zu tun hat.

## Die Anzeige lesen

Das Kontrollfeld zeigt den aktuellen Diversity-Status:

- **Messung (4/8):** Messphase, Schritt 4 von 8
- **50:50 (42/60):** Betrieb im gleichen Verhaeltnis, Zyklus 42 von 60 bis zur Neumessung
- **70:30 A1 (15/60):** ANT1 dominant bei 70:30, Zyklus 15 von 60

Die LED-Leiste oder das Verhaeltnis-Label aendert die Farbe je nach Status:
- Gruen: dominante Antenne klar vorne
- Teal/Blau: 50:50, beide Antennen aehnlich
- Gelb: Messung laeuft

## Tipps fuer den Betrieb

- **Starte mit Standard-Modus** fuer deine erste Session. Wechsle nur zu DX-Modus, wenn du aktiv DX jagst.
- **Fuehre zuerst die Gain-Messung durch** (DX Tuning), bevor du Diversity aktivierst. Diversity funktioniert am besten, wenn jede Antenne bereits ihre optimale Preamp-Einstellung hat.
- **Verschiedene Antennen helfen am meisten.** Eine Vertikal- und eine Dipolantenne bringen mehr Diversity-Gewinn als zwei identische Dipole am selben Mast.
- **Schalte Diversity nicht waehrend eines QSOs aus.** Das System schuetzt aktive QSOs automatisch und misst nicht neu, waehrend du mitten in einem Kontakt bist.
- **Beobachte das Verhaeltnis ueber die Zeit.** Wenn es konsistent 70:30 zugunsten einer Antenne zeigt, ist die einfach besser auf diesem Band gerade. Wenn es staendig wechselt, aendern sich die Bedingungen schnell — Diversity macht genau seinen Job.
