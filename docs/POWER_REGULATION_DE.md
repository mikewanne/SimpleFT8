# Automatische TX-Leistungsregelung

[English](POWER_REGULATION.md) | **Deutsch**

[Zurueck zur README](../README_DE.md) | [Diversity](DIVERSITY_DE.md) | [DX Tuning](DX_TUNING_DE.md)

## Das Problem

Du stellst 75W am Power-Slider ein. Das Radio zeigt 42W am Meter. Jeder Funkamateur kennt diesen Frust.

Der Grund: `rfpower` am FlexRadio (und den meisten modernen Transceivern) setzt das Maximum der PA, aber die tatsaechliche Ausgangsleistung haengt vom Audio-Drive-Level ab, das die PA erreicht. Bei DAX Digital-Audio umfasst die Kette `mic_level`, Software-Gain, DAX-Treiber-Gain und bandabhaengige PA-Charakteristiken. Jedes Glied kann die tatsaechliche Leistung reduzieren.

Verschiedene Baender verhalten sich unterschiedlich. 20m liefert dir vielleicht 66W bei den gleichen Einstellungen, wo 40m nur 53W bringt. Wetter beeinflusst das SWR, was die Leistung beeinflusst. Mantelwellen fuegen eine weitere Variable hinzu.

## Wie SimpleFT8 das loest

SimpleFT8 verwendet einen geschlossenen Regelkreis:

1. **Du waehlst** die gewuenschte Leistung (z.B. 70W) per Button
2. **Waehrend TX** meldet das FWDPWR-Meter am Radio die tatsaechlichen Watt
3. **Nach jedem TX-Zyklus** (~15 Sekunden) vergleicht SimpleFT8 Ist- mit Soll-Wert
4. **Der Audio-Drive wird automatisch angepasst** fuer den naechsten Zyklus
5. **Innerhalb von 2-3 Zyklen** (~30-45 Sekunden) konvergiert die Ausgangsleistung auf den Zielwert

Die Anpassung verwendet einen P-Regler mit der Quadratwurzel-Beziehung zwischen Leistung und Amplitude: Um die Leistung um 10% zu erhoehen, erhoehst du die Amplitude um ~5% (da P proportional zu V zum Quadrat ist).

## Clipping-Schutz

Den Audio-Drive zu weit zu erhoehen verursacht Clipping — harte Verzerrung, die Splatter erzeugt und benachbarte Stationen stoert. SimpleFT8 ueberwacht den Audio-Spitzenpegel, bevor er das Radio erreicht:

- **Peak < 90%**: Sicher, gruener Indikator
- **Peak 90-100%**: Grenzbereich, gelber Indikator
- **Peak > 100%**: Clipping erkannt, roter "CLIP!"-Indikator — Auto-Regelung stoppt die Erhoehung

Das stellt sicher, dass dein Signal sauber bleibt, auch wenn das System maximale Leistungsabgabe anstrebt.

## Kalibrierung pro Band

Der optimale Audio-Drive-Level variiert pro Band. SimpleFT8 speichert den kalibrierten Wert fuer jedes Band. Wenn du von 20m auf 40m wechselst, wird der gespeicherte 40m-Drive-Level sofort geladen — kein Warten auf erneute Konvergenz.

Wenn sich die Bedingungen aendern (nasse Antenne, Temperaturschwankung), erkennt der kontinuierliche Regelkreis den Leistungsabfall und korrigiert innerhalb weniger Zyklen nach.

## Die TX-Statusanzeige

Die RADIO-Karte zeigt alle relevanten TX-Metriken in einem gerahmten Bereich:

- **TUNE**-Button + **Watt-Anzeige**: Aktuelle Vorwaertsleistung
- **Peak**: Audio-Spitzenpegel (Headroom vor Clipping)
- **TX-Balken**: Aktueller auto-angepasster Drive-Level (0-150%)
- **SWR**: Antennenanpassungs-Qualitaet

*(Screenshot des TX-Status waehrend der Sendung wird ergaenzt)*

## Technische Details

### Regelalgorithmus

```
measured_watts = average(FWDPWR samples during TX cycle)
ratio = target_watts / measured_watts          (clamped 0.5 - 2.0)
amplitude_factor = sqrt(ratio)                 (P ∝ V²)
correction = Kp * (amplitude_factor - 1.0)     (Kp = 0.4)
correction = clamp(correction, -0.15, +0.15)   (max step per cycle)
new_level = current_level * (1.0 + correction)
new_level = clamp(new_level, 0.05, 1.50)       (absolute limits)
```

Sicherheitsregeln:
- Wenn measured > target * 1.05 und correction erhoehen wuerde: stattdessen reduzieren
- Wenn Audio-Peak >= 0.95 und correction erhoehen wuerde: aktuellen Level halten
- Aenderungen < 1% werden ignoriert (verhindert Oszillation)

### Audio-Drive-Kette

```
PyFT8 encoder (12kHz float32)
  → Resample to 24kHz
  → Multiply by tx_audio_level (0.05 - 1.50)
  → Clip to [-1.0, +1.0]
  → Convert to int16 big-endian
  → VITA-49 packets to radio
```

Zusaetzlich wird `transmit set mic_level=X` (0-100) an die interne Gain-Stufe des Radios gesendet. Fuer tx_audio_level 0-1.0 skaliert mic_level linear. Ueber 1.0 bleibt mic_level bei 100 und nur der Software-Gain steigt.

### Warum zwei Gain-Stufen?

Der `mic_level` des Radios steuert den analogen Gain vor der PA. Der Software-`tx_audio_level` steuert den digitalen Signalpegel. Beide zusammen geben mehr Dynamikumfang:
- **0-100%**: mic_level uebernimmt die Arbeit, Software bei Unity-Gain
- **100-150%**: mic_level am Maximum, Software liefert zusaetzlichen Boost
- Der `np.clip` stellt sicher, dass der int16-Ausgang niemals ueberlaeuft, auch bei 150%
