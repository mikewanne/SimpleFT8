# Richtungs-Karte (3D-Globus)

[English](direction-map.md) | **Deutsch**

## Was macht das Feature?

Ein drehbarer 3D-Globus (Azimuthal-Equidistant-Projektion) mit
**16 Richtungs-Sektor-Wedges** zeigt **wo gerade Ausbreitung
stattfindet** — nicht nur wo PSK-Reporter mal Stationen gemeldet
hat, sondern was im aktuellen Slot tatsaechlich gehoert wird.
Antennen-Farbcodierung (ANT1/ANT2/Rescue) macht den Diversity-
Beitrag jeder Antenne sofort sichtbar.

## Wie funktioniert es?

### Zwei Modi

- **RX-Modus** (Default): Wedge-Laenge = Anzahl unique Stationen
  aus dieser 22.5°-Himmelsrichtung in den letzten 60 Minuten.
- **TX-Modus** (v0.71): Wedge-Laenge = max-Reichweite in km.
  Ein einziger VK6-Spot bei 16.000 km zaehlt mehr als 50
  Iberien-Spots.

### Datenpfad

Decoder-Thread → `_emit_map_snapshot_if_open` →
`direction_map_signal.emit(snapshot, band)` →
`Qt.QueuedConnection` → `_on_direction_map_snapshot` (GUI-Thread)
→ `canvas.update_stations`. Niemals direkt aus dem Decoder-Thread
Widget-Methoden aufrufen — immer ueber das Signal (Cross-Thread-
Schutz).

### Sektor-Aggregation

`core/direction_pattern.py` aggregiert Stations-Empfaenge in
16 Sektoren à 22.5° Himmelsrichtung. Pro Sektor: Anzahl Stationen,
durchschnittlicher SNR, beste Antenne (ANT1 oder ANT2).

Mobile-Suffixe (`/MM`, `/AM`, `/QRP`) werden gefiltert weil ihre
Locator-Praezision schlechter ist (1.5x prec_km).

### Theme

Aurora-Theme (hell, fuer Tagesbetrieb) und Dark-Theme (Nacht).
Toggle persistent gespeichert (v0.72).

### Live-Daten

Das Karten-Dialog bleibt waehrend des Empfangs offen und
aktualisiert sich pro Slot mit den frischen Decodes. Wenn ein
Bandwechsel passiert, wird die RX-History des neuen Bandes
sofort nachgeladen (60-Minuten-Cache).

## Wann nuetzlich?

- **„Macht ein QSO mit NA gerade Sinn?"** — Ein Blick auf die
  Karte: kein Vektor nach Westen → spar dir die Versuche.
- **Diversity-Visualisierung:** Welche Antenne traegt am meisten
  in welche Richtung? ANT1-blaue Wedges nach Norden, ANT2-orange
  Wedges nach Sueden — sofort lesbar.
- **DX-Trend:** Wenn ein Sektor ploetzlich heller wird, oeffnet
  das Band in diese Richtung. Live-Operative-Information.

## Wo zu finden?

Der Karten-Dialog wird ueber den Settings-Dialog geoeffnet:
**Einstellungen → Tab "Daten & Tools" → Karte oeffnen ...**

Der Dialog ist non-modal — er bleibt offen und aktualisiert sich
live, parallel zum normalen Empfangs-Betrieb.

**Settings:**

- RX/TX-Toggle oben in der Karte
- Aurora/Dark-Theme-Toggle
- Filter (z.B. nur DX-Sektoren mit > 1000 km Distanz)

**Hardware-Hinweis:** Im TX-Modus zeigt die Karte PSK-Reporter
Reverse-Lookups (wer hat MICH gehoert?). Die TX-Antenne ist immer
ANT1 — die Karte trifft KEINE Antennen-Auswahl, sie visualisiert
nur was bereits empfangen oder gesendet wurde.

## Status

Live in v0.66 eingefuehrt, in v0.71 um TX-Distanz-Modus
erweitert, in v0.72 um Aurora-Theme. Alle drei Versionen DeepSeek-
reviewed.
