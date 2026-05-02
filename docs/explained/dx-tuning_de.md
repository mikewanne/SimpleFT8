# DX Tuning — Automatische Gain-Messung

[English](DX_TUNING.md) | **Deutsch**

[Zurueck zur README](../README_DE.md) | [Diversity](DIVERSITY_DE.md) | [Leistungsregelung](POWER_REGULATION_DE.md)

## Das Problem

Jede Antenne verhaelt sich auf jedem Band anders. Der Preamp-Gain, der auf 20m gut funktioniert, fuegt auf 40m moeglicherweise zu viel Rauschen hinzu. Und was gestern passte, passt heute vielleicht nicht mehr — Regen am Speisepunkt, nasser Boden, atmosphaerische Bedingungen, sogar die Temperatur kann die optimalen Einstellungen verschieben.

Die meisten Operatoren stellen ihren Preamp einmal ein und vergessen ihn. Dabei verschenken sie Empfangsleistung.

## Was DX Tuning macht

SimpleFT8s DX Tuning fuehrt eine automatisierte Messung ueber beide Antennen bei mehreren Gain-Einstellungen durch. Es dauert etwa 4,5 Minuten (18 FT8-Zyklen) und liefert eine klare Empfehlung: welche Antenne bei welcher Gain-Einstellung den besten Empfang auf diesem Band liefert, genau jetzt.

Die Ergebnisse werden als Presets pro Band gespeichert. Beim naechsten Wechsel auf 20m werden die optimalen Einstellungen sofort geladen.

## So funktioniert es

1. Klicke **EINMESSEN** im Antennen-Panel
2. SimpleFT8 fuehrt 3 Runden mit je 6 Zyklen durch (18 Zyklen gesamt)
3. Jede Runde testet eine andere Gain-Einstellung (0 dB, 10 dB, 20 dB)
4. Innerhalb jeder Runde wechseln die Zyklen zwischen ANT1 und ANT2
5. Fuer jede Kombination (Antenne + Gain) werden der Durchschnitts-SNR und die Stationsanzahl erfasst
6. Nach allen 18 Zyklen wird die beste Kombination angezeigt

### Messstart
![DX Tuning Start](screenshots/dx_tuning_start.png)

### Messergebnisse
![DX Tuning Ergebnisse](screenshots/dx_tuning_result.png)

Bei dieser 20m-Messung sahen die Ergebnisse so aus:

| Antenne | Gain 0 dB | Gain 10 dB | Gain 20 dB |
|---------|:---------:|:----------:|:----------:|
| ANT1 | -0,8 dB Avg (13 St.) | -4,6 dB Avg (8 St.) | +1,6 dB Avg (9 St.) |
| ANT2 | **+3,0 dB Avg (25 St.)** | +7,6 dB Avg (21 St.) | +1,2 dB Avg (11 St.) |

Gewinner: ANT2 bei 0 dB Gain — bester Durchschnitts-SNR bei den meisten Stationen.

## Presets pro Band

Nach der Messung werden die optimalen Einstellungen gespeichert:

```
20m: ANT2, Gain 0 dB (gemessen 2026-04-04 11:50)
40m: ANT1, Gain 20 dB (gemessen 2026-04-04 14:46)
```

Wenn du das Band wechselst, laedt SimpleFT8 automatisch das Preset und konfiguriert das Radio. Kein manuelles Nachstellen noetig.

## Wann neu messen?

- Nach deutlichen Wetteraenderungen (Regen, Sturm)
- Wenn du die Antennenhardware aenderst
- Saisonal (Ausbreitungspfade verschieben sich)
- Wenn der Empfang schlechter scheint als gewohnt

Die Messung dauert nur 4,5 Minuten und laeuft im Hintergrund, waehrend du weiter empfaengst. Du kannst jederzeit abbrechen.

## Technische Details

- Die Messung ist verschachtelt: ANT1 und ANT2 wechseln sich innerhalb jeder Gain-Runde ab, um den Einfluss wechselnder Ausbreitungsbedingungen waehrend des Tests zu minimieren
- Der SNR wird als Durchschnitt der Top-5 dekodierten Stationen pro Kombination berechnet
- Die Stationsanzahl ist eine sekundaere Metrik — mehr Stationen bei aehnlichem SNR bestaetigt die Messung
- TX bleibt waehrend der gesamten Messung auf ANT1 (nur die RX-Antenne wechselt)
- Der `rfgain`-Parameter des Radios wird fuer jeden Schritt ueber die SmartSDR API gesetzt
