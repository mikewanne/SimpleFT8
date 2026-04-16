# Logbuch — QSO-Verwaltung und Export

## Kurzfassung

SimpleFT8s integriertes Logbuch speichert jedes abgeschlossene QSO im Standard-ADIF-Format. Du kannst suchen, sortieren, Details ansehen, Eintraege loeschen und zu QRZ.com hochladen — alles innerhalb der Anwendung. Keine externe Log-Software noetig.

## Funktionen im Ueberblick

| Funktion | Beschreibung |
|----------|-------------|
| Sortierbare Tabelle | Klick auf Spaltenkopf sortiert nach Datum, Call, Band, Mode, Land oder Entfernung |
| Suche | Filtern nach Rufzeichen, Band, Laendername oder Locator |
| DXCC-Zaehler | Zeigt wie viele einzigartige DXCC-Gebiete du gearbeitet hast |
| QSO-Detail-Overlay | Klick auf ein QSO zeigt alle Details und QRZ.com-Stationsinformationen |
| QSOs loeschen | Fehlerhafte oder Test-Eintraege aus dem Log entfernen |
| QRZ.com-Upload | Alle QSOs gesammelt zu deinem QRZ.com-Logbuch hochladen |
| Entfernungsanzeige | Zeigt km von deinem QTH, exakt aus Grid oder naeherungsweise aus Rufzeichenpraefix |

## Die QSO-Tabelle

Die Logbuch-Tabelle zeigt sechs Spalten:

| Spalte | Inhalt | Beispiel |
|--------|--------|----------|
| Datum | Datum des QSOs (TT.MM.JJ) | 09.04.26 |
| Call | Rufzeichen der Gegenstation | EA3FHP |
| Band | Betriebsband | 20M |
| Mode | Verwendeter Digitalmodus | FT8 |
| Land | Land (aus Rufzeichenpraefix abgeleitet) | Spain |
| km | Entfernung von deinem QTH | 1247 |

Klicke auf einen Spaltenkopf zum Sortieren. Nochmal klicken dreht die Sortierung um.

## Suche

Tippe in das Suchfeld, um die Tabelle in Echtzeit zu filtern. Die Suche prueft:

- **Rufzeichen** — Teil eines Calls eingeben (z.B. "EA3" fuer alle spanischen Stationen)
- **Band** — "20M" eingeben zeigt nur 20-Meter-QSOs
- **Land** — "Japan" oder "Germany" eingeben filtert nach Laendername
- **Grid** — Locator-Praefix eingeben (z.B. "JN" fuer Suedeuropa)

Die Suche ignoriert Gross-/Kleinschreibung. Suchfeld leeren zeigt wieder alle QSOs.

## DXCC-Zaehler

Der Zaehler oben rechts zeigt zwei Werte:

- **DXCC: 42** — Anzahl der einzigartigen Laender/Gebiete die du gearbeitet hast
- **187 QSOs** — Gesamtzahl der geloggten Kontakte

Der DXCC-Zaehler wird aus Rufzeichenpraefixen abgeleitet und umfasst alle QSOs aus allen ADIF-Dateien in deinem SimpleFT8-Verzeichnis.

## QSO-Detail-Overlay

Klicke auf eine Zeile im Logbuch, um das Detail-Overlay auf der rechten Seite zu oeffnen. Es zeigt:

### Stationsinformationen (von QRZ.com)
- Vollstaendiger Name des Operators
- QTH (Stadt/Ort), Land, Grid-Locator
- DXCC-Gebietsnummer, CQ-Zone, ITU-Zone

Die QRZ-Abfrage laeuft im Hintergrund — die Oberflaeche bleibt reaktionsfaehig waehrend auf das Ergebnis gewartet wird.

### Editierbare QSO-Felder
- Datum und Uhrzeit (UTC)
- Band und Frequenz
- Mode
- RST gesendet und empfangen (Signalreports)
- Grid-Locator
- TX-Leistung
- Kommentar

### Aktionen
- **Speichern** — Aenderungen in die ADIF-Datei schreiben
- **QRZ Upload** — Dieses einzelne QSO zu QRZ.com hochladen
- **Loeschen** — Dieses QSO loeschen (mit Sicherheitsabfrage)

## Ein QSO loeschen

So loeschst du ein QSO:

1. Klicke das QSO in der Tabelle, um es auszuwaehlen.
2. Klicke den **Loeschen**-Button (entweder in der Tabellen-Leiste oder im Detail-Overlay).
3. Ein Bestaetigungsdialog zeigt Call, Datum, Uhrzeit, Band und Mode.
4. Klicke **Ja, loeschen** zur Bestaetigung.

Das QSO wird dauerhaft aus der ADIF-Datei entfernt. Das kann nicht rueckgaengig gemacht werden. Die Tabelle aktualisiert sich automatisch nach dem Loeschen.

## QRZ.com-Upload

### Einrichtung
Trage deine QRZ.com-Zugangsdaten in den SimpleFT8-Einstellungen ein:

- `qrz_api_key` — Dein QRZ XML API Key (aus den QRZ.com-Kontoeinstellungen)
- `qrz_username` — Dein QRZ.com-Benutzername
- `qrz_password` — Dein QRZ.com-Passwort

### Einzelnes QSO hochladen
Klicke ein QSO im Logbuch, dann klicke **QRZ Upload** im Detail-Overlay. Die Statusleiste zeigt das Ergebnis.

### Massen-Upload
Klicke den **QRZ**-Button in der Logbuch-Leiste, um alle QSOs auf einmal hochzuladen. Der Upload laeuft im Hintergrund und meldet:

- Wie viele QSOs erfolgreich hochgeladen wurden
- Wie viele Duplikate waren (schon auf QRZ.com vorhanden)
- Wie viele fehlgeschlagen sind

## Entfernungsanzeige

Die km-Spalte zeigt die Entfernung von deinem QTH (konfigurierter Grid-Locator) zur Gegenstation:

| Anzeige | Quelle | Genauigkeit |
|---------|--------|-------------|
| **1247** | Grid-Locator aus dem QSO-Austausch | Exakt (Feldmitte zu Feldmitte, Haversine-Formel) |
| **~8500** | Rufzeichenpraefix-Zuordnung | Naeherung (Landesmittelpunkt) |
| *(leer)* | Weder Grid noch bekanntes Praefix | Keine Entfernung verfuegbar |

Die Tilde (~) zeigt an, dass die Entfernung naeherungsweise aus dem Rufzeichenpraefix berechnet wurde, nicht aus einem tatsaechlichen Grid-Austausch.

## ADIF-Dateiformat

QSOs werden im ADIF-3.1.7-Format gespeichert, eine Datei pro Tag:

```
SimpleFT8_LOG_20260409.adi
SimpleFT8_LOG_20260410.adi
SimpleFT8_LOG_20260411.adi
```

Jede Datei enthaelt einen Header und einen Datensatz pro QSO. Das Format ist kompatibel mit allen gaengigen Log-Programmen (Log4OM, DXKeeper, WSJT-X, usw.).

### Felder pro QSO

| ADIF-Feld | Inhalt |
|-----------|--------|
| CALL | Rufzeichen der Gegenstation |
| QSO_DATE | Datum (JJJJMMTT) |
| TIME_ON | Uhrzeit UTC (HHMMSS) |
| BAND | Band (z.B. 20M) |
| FREQ | Frequenz in MHz |
| MODE | FT8, FT4 oder FT2 |
| RST_SENT | Dein Signalreport an die Gegenstation |
| RST_RCVD | Signalreport der Gegenstation an dich |
| GRIDSQUARE | Grid-Locator der Gegenstation |
| MY_GRIDSQUARE | Dein Grid-Locator |
| STATION_CALLSIGN | Dein Rufzeichen |
| TX_PWR | Deine Sendeleistung in Watt |
| COMMENT | "SimpleFT8 v1.0" |

## Tipps fuer den Betrieb

- **Das Logbuch laedt alle ADIF-Dateien** in deinem SimpleFT8-Verzeichnis, nicht nur die von heute. QSOs aus frueheren Sessions erscheinen automatisch.
- **QSOs werden zum RR73-Zeitpunkt geloggt**, nicht wenn 73 empfangen wird. Wenn die Gegenstation nie 73 sendet, ist das QSO trotzdem geloggt — RR73 ist der Standard-Abschlusspunkt bei FT8.
- **Sichere deine ADIF-Dateien.** Es sind einfache Textdateien in deinem SimpleFT8-Verzeichnis. Kopiere sie regelmaessig an einen sicheren Ort.
- **Vorsicht beim Loeschen.** Das Loeschen ist dauerhaft und entfernt den Eintrag aus der ADIF-Datei auf der Festplatte. Es gibt keinen Papierkorb und kein Rueckgaengig.
- **QRZ-Upload behandelt Duplikate korrekt.** Wenn ein QSO bereits auf QRZ.com existiert, wird es als Duplikat gezaehlt, nicht als Fehler.
- **Das Detail-Overlay schliesst sich**, wenn du zurueck zum QSO-Tab wechselst. Klicke erneut auf einen Logbuch-Eintrag, um es wieder zu oeffnen.
