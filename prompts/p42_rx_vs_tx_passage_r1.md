# P42 — README-Passage: TX-RX-Asymmetrie bei nicht-resonanten Antennen (R1-Review)

## Auftrag an DeepSeek

Ich entwerfe eine Passage fuer die GitHub-README von SimpleFT8 (Hobby-FT8-Tool).
**Pruefe streng auf physikalische Korrektheit + verstaendliche Aussage.**

Fokus:
1. **Physik korrekt?** Reziprozitaet, Mismatch-Loss, Noise-Floor, SNR-Headroom
2. **FT8-Spezifika** stimmen? Decode-Schwelle, Costas-Sync-Empfindlichkeit
3. **Zahlen plausibel?** Mike's Setup: Kelemen DP-201510 Trap-Dipol (resonant 10/15/20m),
   Regenrinne L-Form 15m als ANT2, 70-100W RX
4. **Verstaendlichkeit** fuer Hobby-Funker (nicht Akademiker-Jargon)
5. **Konsistenz** mit Mike's Live-Daten (40m off-band: +61% Diversity-Gain;
   20m resonant: ~0% Gewinn aber +5% DX)

KP-Findings KRITISCH/SOLLTE/KOENNTE/OK. Kurz halten.

---

## Kontext: Mike's These

Verbreiteter Funker-Irrtum: „Wenn die Antenne sendet, empfaengt sie auch."
Mike sagt: bei nicht-resonanten Baendern (Tuner-Setup) **stimmt das nicht
in der Praxis** — TX funktioniert, RX leidet. Bei FT8 (digitale Modi mit
mathematischer Decode-Schwelle) ist RX-Sensitivitaet der eigentliche
Engpass — bei SSB/CW dagegen oft TX-Power.

## Verifikations-Frage 1: Reziprozitaet vs Headroom — stimmt mein Argument?

**Meine Annahme:** Antennen-Physik IST reziprok (Mismatch-Loss gilt auf beiden
Pfaden gleich). Aber das **Link-Budget** ist asymmetrisch:

- **TX-Seite hat 50+ dB Headroom** — du gibst 100 W rein, brauchst aber
  nur +50 dBm an deiner Antennen-Klemme. Selbst wenn 5-10 dB im Tuner
  verloren gehen, kommt das Signal bei der Gegenstation noch
  *millionenfach* ueber dem Rauschen an.
- **RX-Seite hat ~5-15 dB Headroom** — das Signal vom DX ist gegeben
  durch Pfadverlust. Selbst 3 dB Antennen-Loss kann unter die
  Decode-Schwelle druecken.

→ Verluste betreffen beide Pfade physikalisch gleich, ABER nur der
RX-Pfad hat keinen Spielraum. **Korrekt formuliert?**

## Verifikations-Frage 2: FT8-Spezifika

- **Decode-Schwelle FT8:** typischerweise -24 dB SNR in 2500 Hz Bandbreite
  (auf 50 Hz-FT8-Subkanal normalisiert). **Stimmt der Zahlenwert?**
- **Vergleich SSB:** geuebtes Ohr noch -5 dB SNR brauchbar, bei FT8
  geht's nicht — Costas-Sync braucht definierte Mindest-Korrelation
  und Reed-Solomon-LDPC-Decoder hat harte BER-Schwelle. **Korrekt?**
- **Folge:** bei FT8 zaehlt jedes dB RX-Sensitivitaet, weil schwache
  Stationen direkt an der Schwelle liegen. Bei SSB ist TX-Power
  oft wichtiger (man muss gehoert werden, vom Mensch ausgewertet). **OK?**

## Verifikations-Frage 3: Link-Budget Beispielrechnung

Stimmen die Werte fuer FT8 20m typischer Pfad 2000 km:

**TX-Pfad (Mike sendet 70W in nicht-resonante Antenne, Tuner 7 dB Loss):**
- PA-Ausgang: 70W = +48 dBm
- Nach Tuner: ~14W = +41 dBm (effektiv abgestrahlt)
- Pfadverlust 20m, 2000 km Sky-Wave: ca. -125 dB
- Ankunft bei Gegenstation: +41 - 125 = -84 dBm
- Noise-Floor 20m 2500 Hz: ca. -123 dBm (laendlich) bis -110 dBm (urban)
- Empfangsstaerke ueber Noise: +30 bis +43 dB ← weit ueber Decode-Schwelle ✓

**RX-Pfad (DX sendet 100W in resonante Antenne):**
- PA-Ausgang: 100W = +50 dBm
- Mit gute resonante Antenne: ~95W = +49.8 dBm
- Pfadverlust gleicher Pfad: -125 dB
- Ankunft bei Mike's Antennenklemme: +50 - 125 = -75 dBm
- Mismatch-Loss Tuner + nicht-resonante Antenne: -7 dB
- Am Receiver: -82 dBm
- Noise-Floor: -123 bis -110 dBm
- SNR: +28 bis +41 dB ← auch sicher decoder

Hmm — meine Beispielrechnung zeigt eigentlich KEIN Problem. **Wo ist der
echte Knackpunkt bei schwachen Stationen?**

Wahrscheinlich:
- Mike's Daten zeigen +60% Diversity-Gain auf 40m — der echte Wert
- Theoretisch sollte Reziprozitaet beide Pfade gleich treffen
- Wo entsteht in der Praxis der Asymmetrie-Faktor?

Vermutungen:
- **Schwache Stationen direkt an der Decode-Schwelle:** kleine Verluste
  kicken sie raus. Bei +20 dB starken Stationen ist 5 dB Loss egal.
  Bei 0 dB SNR ist 5 dB Loss = nicht decodiert.
- **Pol-Diversity-Effekt:** Trap-Dipol horizontal vs Regenrinne L-Form
  (eher vertikal) — manche Stationen kommen polarisations-gedreht an
  durch Skip-Reflexion. ANT2 faengt diese auf was ANT1 verpasst.
- **Sektor-Diversity:** beide Antennen haben unterschiedliche Richtungs-
  charakteristik. ANT2 hoert evtl. Sektoren in die ANT1 nicht horcht.

**R1: ist die "Reziprozitaet gilt, aber RX-Headroom fehlt"-Erklaerung
ueberhaupt der richtige Erklaerungs-Schluessel? Oder ist es eher
Pol-/Sektor-Diversity die in der Praxis den Unterschied macht?**

## Draft 1 (EN, fuer README.md)

```markdown
### Why Diversity Matters for FT8 — Receiver Sensitivity is the Bottleneck

A common misconception among ham operators: *"If my antenna transmits,
it must receive equally well."* Physically the antenna is indeed
reciprocal — losses apply identically to TX and RX paths. But the
**link budget is asymmetric**:

- **TX has ~50 dB headroom.** A 100W transmitter into a non-resonant
  antenna (tuner-matched) delivers +50 dBm at the feedpoint. Even
  with 7-10 dB tuner loss, the signal arrives at a 2000 km distant
  station typically 30-40 dB above the noise floor — well over the
  FT8 decode threshold (-24 dB SNR).
- **RX has only 5-15 dB headroom for weak DX.** The received signal
  strength is fixed by path loss, not by your power. A 5-7 dB
  antenna loss at your end can push weak stations under the FT8
  decode threshold — they simply disappear.

**For FT8/FT4/FT2 this matters more than for SSB/CW.** Digital modes
have a hard mathematical decoding threshold (Costas synchronization,
Reed-Solomon/LDPC error correction). A trained ear can still pull a
-5 dB SNR SSB signal out of the noise; the FT8 decoder cannot.

This is why **Diversity is a real win for the typical ham setup** —
a resonant antenna for one or two favorite bands, everything else
matched through a tuner. The non-resonant bands are exactly where the
gutter / wire / random secondary antenna picks up stations the main
antenna can't decode. Mike's measured data confirms this:

| Band | Main Antenna (ANT1) | Diversity Standard vs Normal |
|---|---|---|
| 40m | Trap dipole off-band, tuner-matched | **+61%** more stations |
| 20m | Trap dipole on resonant design band | ~0% (RX already optimal) |
| 30m, 12m, 17m | off-band (data growing) | expected +30 to +60% |

**The transmit side is rarely the problem with 70-100W.** The receive
side is. Diversity directly attacks that bottleneck.
```

## Draft 2 (DE, fuer README_DE.md)

```markdown
### Warum Diversity bei FT8 wirklich was bringt — Empfang ist der Engpass

Verbreiteter Funker-Irrtum: *„Wenn meine Antenne sendet, empfaengt sie
auch genauso gut."* Physikalisch stimmt das fuer die Antenne selbst
(Reziprozitaetsprinzip — Verluste sind auf TX- und RX-Pfad gleich).
Aber das **Link-Budget ist asymmetrisch**:

- **TX-Seite hat etwa 50 dB Reserve.** 100W in eine ueber Tuner
  angepasste, nicht-resonante Antenne liefern +50 dBm an der Klemme.
  Selbst mit 7-10 dB Tuner-Verlust kommt das Signal bei einer
  Gegenstation in 2000 km Entfernung typisch noch 30-40 dB ueber dem
  Rauschen an — weit ueber der FT8-Decode-Schwelle (-24 dB SNR).
- **RX-Seite hat nur 5-15 dB Reserve fuer schwache DX-Stationen.**
  Die empfangene Signalstaerke ist durch den Pfadverlust festgelegt,
  nicht durch deine Sendeleistung. Schon 5-7 dB Antennen-Verlust am
  deinem Ende kippen schwache Stationen unter die Decode-Schwelle —
  sie verschwinden dann komplett.

**Bei FT8/FT4/FT2 ist das viel relevanter als bei SSB/CW.** Digitale
Modi haben eine harte mathematische Decode-Schwelle (Costas-Synchroni-
sation, Reed-Solomon-/LDPC-Fehlerkorrektur). Ein geuebtes Ohr kann
ein SSB-Signal bei -5 dB SNR noch verstehen — der FT8-Decoder nicht.

Genau hier liegt der **echte Mehrwert von Diversity fuer das typische
Funker-Setup** — eine resonante Antenne fuer ein, zwei Lieblings-Baender,
alles andere ueber Tuner. Auf den off-band-Baendern faengt die zweite
Antenne (Dachrinne, Drahtschleife, Random-Secondary) Stationen ein die
die Hauptantenne nicht mehr decodieren kann. Mike's gemessene Daten
bestaetigen das:

| Band | Hauptantenne (ANT1) | Diversity Standard vs Normal |
|---|---|---|
| 40m | Trap-Dipol off-band, Tuner | **+61 %** mehr Stationen |
| 20m | Trap-Dipol auf Resonanzband | ~0 % (RX schon optimal) |
| 30m, 12m, 17m | off-band (Daten wachsen) | erwartet +30 bis +60 % |

**Das Senden ist mit 70-100W selten das Problem.** Das Empfangen
schwacher Stationen ist es. Diversity adressiert genau diesen Engpass.
```

---

## Bitte gib zurueck

1. **Physik-Verifikation:** Ist mein Reziprozitaet-vs-Headroom-Argument
   der richtige Erklaerungs-Schluessel? Oder eher Pol-/Sektor-Diversity
   die in Mike's Daten dominiert?
2. **FT8-Decode-Schwelle:** stimmt -24 dB SNR (in 2500 Hz Bandbreite)?
3. **Link-Budget-Beispielrechnung:** plausibel, oder gibt es Fehler?
4. **Verstaendlichkeit:** ist die Passage fuer einen DL-Funker ohne
   Akademiker-Hintergrund klar?
5. **Verbesserungs-Vorschlaege** wenn Aenderungen substantiell sind.

Bitte konkret und ohne Marketing-Sprech.
