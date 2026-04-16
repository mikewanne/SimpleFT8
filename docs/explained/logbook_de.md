# Logbuch & QRZ-Integration

## Uebersicht

SimpleFT8 enthaelt ein vollstaendig integriertes Logbuch, das jedes abgeschlossene QSO automatisch im ADIF 3.1.7 Format speichert.

## Funktionen

### QSO-Tabelle
- **Sortierbare Spalten**: Datum, Call, Band, Modus, RST gesendet/empfangen, Grid, Land, km
- **Suche**: Filtern nach Rufzeichen, Band oder Land (Suchleiste oben)
- **DXCC-Zaehler**: Zeigt einzigartige Laender an
- **QSO-Zaehler**: Gesamtzahl der QSOs

### Entfernungsanzeige (km)
- **Exakt**: Wenn der Grid-Locator der Gegenstation bekannt ist (aus dem QSO-Austausch)
- **Ungefaehr (~)**: Wenn kein Grid vorhanden ist, wird die Entfernung aus dem Rufzeichen-Prefix geschaetzt (z.B. VK = Australien, JA = Japan)
- Die Entfernung wird von deinem Locator (JO31) mit der Haversine-Formel berechnet

### QSO-Detail-Ansicht
Klicke auf ein QSO im Logbuch um zu sehen:
- Vollstaendige QSO-Daten (Call, Datum, Zeit, Band, Modus, RST, Grid)
- **QRZ.com-Abfrage**: Name, Standort, Foto (benoetigt QRZ API-Key)
- **Upload zu QRZ**: Einzelnes QSO oder alle auf einmal

### QSO loeschen
1. Klicke auf das QSO das du loeschen willst
2. Klicke auf **Loeschen** (roter Button)
3. Bestaetigen im Dialog
4. QSO wird aus der ADIF-Datei auf der Festplatte entfernt

### QRZ.com-Integration
- **Abfrage**: Klicke auf ein QSO um QRZ.com-Info zu sehen (Name, QTH, Foto)
- **Upload**: Alle QSOs ins QRZ.com-Logbuch hochladen
- **Einrichtung**: QRZ API-Key in den Einstellungen eintragen

## ADIF-Dateien

QSOs werden als taegliche ADIF-Dateien gespeichert:
```
SimpleFT8_LOG_20260415.adi
SimpleFT8_LOG_20260416.adi
```

Jede Datei enthaelt Standard ADIF 3.1.7 Felder: CALL, QSO_DATE, TIME_ON, BAND, FREQ, MODE, RST_SENT, RST_RCVD, GRIDSQUARE, MY_GRIDSQUARE, STATION_CALLSIGN, TX_PWR.

## Tipps

- Das Logbuch laedt beim Start ALLE .adi-Dateien aus dem SimpleFT8-Verzeichnis
- QSOs werden sofort nach dem Senden von RR73 eingetragen (kein Warten auf 73 noetig)
- Die Suchleiste findet schnell eine bestimmte Station
- Der DXCC-Zaehler zaehlt einzigartige Laender-Prefixe ueber alle QSOs
