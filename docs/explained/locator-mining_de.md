# Live Locator-DB (Locator Mining)

[English](locator-mining.md) | **Deutsch**

## Was macht das Feature?

Waehrend SimpleFT8 dekodiert, extrahiert es **Maidenhead-Locators
direkt aus CQ-Rufen und QSO-Antworten** — und schreibt sie in eine
persistente JSON-Datenbank. Beim Start einer Session und bei
Bandwechsel sind die genauen Stationspositionen sofort verfuegbar
— ohne Online-Lookup, ohne Wartezeit, ohne Fallback auf Land-
Mittelpunkte.

Kein anderer FT8-Client macht das in dieser Form.

## Wie funktioniert es?

### Quellen

Locators kommen aus mehreren Quellen, mit Prioritaet:

```
cq_6 > psk_6 > qso_log_6 > _4-Varianten
```

- **cq_6:** 6-stelliger Locator aus einem live empfangenen CQ
  (`CQ R9CA LO97`) — die genaueste Quelle, weil aktuell.
- **psk_6:** 6-stelliger Locator aus PSK-Reporter (Online-Lookup,
  Background-Polling).
- **qso_log_6:** 6-stelliger Locator aus eigenem ADIF-Logbuch
  (Bootstrap beim Start).
- **_4-Varianten:** 4-stellige Faellen wenn nichts Besseres da ist.

Eine bessere Quelle ueberschreibt nie eine schlechtere — ein
6-stelliges Live-CQ-Loc bleibt, auch wenn spaeter ein 4-stelliges
ADIF-Eintrag verfuegbar wird.

### Persistenz

Die DB liegt in `~/.simpleft8/locator_cache.json`:

- **Auto-Save alle 5 Minuten** waehrend des Betriebs
- **Save bei App-Schliessen**
- Damit ueberlebt die DB Hard-Kills

### Bootstrap

Beim ersten Start (oder leerer DB) werden ADIF-Logbuecher
importiert (z.B. LotW, QRZ, eigenes Logbuch). Das fuellt die DB
sofort mit tausenden Locators.

### Threading

`core/locator_db.py` nutzt `threading.RLock` um konkurrente
Zugriffe von Decoder-Thread + PSK-Worker abzufedern. `get()`
returnt eine Kopie — keine externen Referenzen auf interne Daten.

### Mobile-Suffix-Behandlung

Suffixe wie `/MM` (Maritime Mobile), `/AM` (Aeronautical Mobile)
oder `/QRP` werden mit `prec_km × 1.5` markiert — diese Stationen
bewegen sich, der Locator ist eine Schaetzung. In der Richtungs-
Karte werden sie ggf. ausgefiltert.

## Wann nuetzlich?

- **Praezise Karten-Anzeige:** Statt Land-Mittelpunkten werden
  exakte Positionen gezeigt — Diversity-Auswertung wird
  geographisch korrekt.
- **DX-Trend-Analyse:** Wer ist gerade auf welchem Sektor aktiv?
  Sofort beantwortbar dank live-aktueller DB.
- **Logbuch-Boost:** Bekannte Locator werden im Logbuch direkt
  beim Eintragen vor-ausgefuellt.

## Wo zu finden?

Das Feature ist immer aktiv — keine UI-Schalter. Die DB lebt im
Hintergrund.

**Anzeigen:**

- **RX-Panel:** km-Spalte zeigt Distanz dank Locator (sonst leer).
- **Richtungs-Karte:** alle Punkte basieren auf Locator-DB.
- **Logbuch:** Locator-Eingabe wird vorausgefuellt wo bekannt.
- **Logfile:** `simpleft8.log` zeigt
  `[LocatorDB] total in DB: N` beim Start.

## Status

Implementiert in v0.67, ADIF-Bootstrap-Logik in v0.70 erweitert.
Aktuell ueber 9.000 Calls in der DB, waechst mit jeder Session.
