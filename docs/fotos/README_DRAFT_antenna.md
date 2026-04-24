# Antenna Setup — Draft (noch nicht im README)

## Fotos (bereits in docs/fotos/ abgelegt)
- `Gesamt.png` — Originalfoto Gesamtansicht (korrekte Orientierung)
- `Gesamt Farbe.png` — Annotiert: Gelb = ANT1 (Kelemen-Dipol), Rot = ANT2 (Regenrinne)

---

## Sektion "Antenna Setup" — Deutsch

**Antennensetup für Diversity-Empfang**

Die App nutzt zwei grundverschiedene Antennen für Diversity-Experimente.
ANT1 ist ein Kelemen DP-201510 — ein Fächer-Dipol für 20m, 15m und 10m.
Der Einspeisepunkt sitzt an der Dachgaube im 3. OG, gespeist über einen
1:1-Balun (Anpassglied zwischen symmetrischem Dipol und Koaxialkabel).
Ein Dipolarm führt schräg nach oben zur Dachspitze, der andere schräg
nach unten über das Vordach zum Balkon — eine klassische Inverted-V-Form.

ANT2 ist die Regenrinne des Hauses — eine Zufalls-Längenantenne von etwa
15m Gesamtlänge: ~5m waagerecht entlang der Dachkante, ~8m senkrecht als
Fallrohr an der Hauswand, ~2m waagerecht zum Hauseingang. Diese Länge liegt
zwischen λ/4 und λ/2 für das 40m-Band (7 MHz). Die Regenrinne wurde nie
als Antenne installiert — sie wird nur angeklemmt und empfängt überraschend
exzellent.

Die Kombination ist für Diversity-Empfang ideal: unterschiedliche Geometrie
(Inverted-V vs. L-Form), unterschiedliche Polarisierung (diagonal vs. teils
vertikal/horizontal) und unterschiedliche Befestigung (frei gespannt vs.
gebäudegebunden) minimieren die Korrelation der Empfangssignale — genau das,
was Diversity-Empfang effektiv macht.

Auf dem zweiten Foto sind die Antennenpfade farblich markiert:
Gelb = ANT1 (Kelemen-Dipol), Rot = ANT2 (Regenrinne).

---

## Sektion "Antenna Setup" — English

**Antenna Setup for Diversity Reception**

The app uses two fundamentally different antennas for diversity experiments.
ANT1 is a Kelemen DP-201510 — a fan dipole for 20m, 15m, and 10m.
The feed point is located at the dormer window on the 3rd floor, fed through
a 1:1 balun (matching transformer between the balanced dipole and coaxial
cable). One dipole arm runs diagonally upward to the roof ridge, the other
diagonally downward via the porch roof to the balcony — a classic inverted-V
configuration.

ANT2 is the house gutter — a random wire antenna approximately 15m long:
~5m horizontal along the roof edge, ~8m vertical as the downspout along the
house wall, ~2m horizontal toward the front entrance. This length falls
between λ/4 and λ/2 for the 40m band (7 MHz). The gutter was never installed
as an antenna — it is simply clamped and receives with surprisingly excellent
results.

The combination is ideal for diversity reception: different geometry
(inverted-V vs. L-shape), different polarization (diagonal vs. partly
vertical/horizontal), and different mounting (free-hanging vs.
building-coupled) minimize signal correlation between the two receive paths —
exactly what makes diversity reception effective.

The second photo shows the antenna paths color-coded:
Yellow = ANT1 (Kelemen dipole), Red = ANT2 (gutter).

---

## Caveat-Text für Ergebnis-Sektion (DE + EN)

**DE — Infobox bei den Messergebnissen:**
> **Hinweis zur Interpretation**
> ANT1 (Kelemen DP-201510) ist auf 40m außerhalb seines Auslegungsbandes und
> damit deutlich suboptimal für diesen Frequenzbereich. ANT2 (Regenrinne, ~15m)
> liegt dagegen zwischen λ/4 und λ/2 für 40m und arbeitet dort vergleichsweise
> gut. Die gemessenen Gewinne (+93%/+118% Stationen) sind als **Obergrenze**
> zu verstehen — bei zwei gleichwertigen, für 40m optimierten Antennen ist ein
> geringerer, aber dennoch signifikanter Diversity-Gewinn zu erwarten.
>
> Folgetests auf **20m** sind geplant, wo der Kelemen DP-201510 in seinem
> Auslegungsband arbeitet und deutlich effizienter empfängt. Das 20m-Band
> (14 MHz) ist generell besser zu empfangen als 40m. Die Messreihe läuft.

**EN — Info box at results section:**
> **Note on Interpretation**
> ANT1 (Kelemen DP-201510) is operated off-band on 40m and is therefore
> significantly less efficient on this band. ANT2 (gutter, ~15m) falls between
> λ/4 and λ/2 for 40m and works comparatively well. The measured gains
> (+93%/+118% stations) represent an **upper bound** — with two well-matched,
> 40m-optimized antennas, a lower but still significant diversity gain is expected.
>
> Follow-up tests on **20m** are planned, where the Kelemen DP-201510 operates
> within its design band and receives considerably more efficiently. The 20m band
> (14 MHz) is generally easier to receive than 40m. Measurements are ongoing.

---

## Captions

**Bild 1 — Gesamt.png**
DE: Gesamtansicht des Hauses mit beiden Antennen. Links das Fallrohr der
Regenrinne (ANT2, ~15m Zufallsdrahtantenne). Oben rechts an der Dachgaube
der Einspeisepunkt des Kelemen DP-201510 (ANT1) — die dünnen Dipol-Drähte
heben sich kaum vom Hintergrund ab.

EN: Full view of the house with both antennas. On the left, the gutter
downspout (ANT2, ~15m random wire antenna). Upper right at the dormer,
the feed point of the Kelemen DP-201510 (ANT1) — the thin dipole wires
are barely visible against the background.

**Bild 2 — Gesamt Farbe.png**
DE: Annotierte Ansicht: Gelb = Kelemen DP-201510 Dipol mit Einspeisepunkt
(grüner Punkt) und Inverted-V-Verlauf. Rot = vollständige Regenrinne als
Zufallsantenne (Dachkante → Fallrohr → Hauseingang).

EN: Annotated view: Yellow = Kelemen DP-201510 dipole with feed point
(green dot) and inverted-V path. Red = complete gutter as random wire
antenna (roof edge → downspout → front entrance).
