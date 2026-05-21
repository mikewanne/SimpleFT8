# P105 — QRZ.com Upload-Bestätigung fehlt — Diagnose nötig

Mike-Field-Beobachtung 21.05.2026:

Bei SimpleFT8 werden QSOs erfolgreich zu QRZ.com Logbook hochgeladen
(Upload-API gibt RESULT=OK zurück), aber **fast keines wird im QRZ-Logbook
als „Confirmed" markiert**. Auf 4 Screenshots sind nur ~4 von ~177 QSOs
grün/bestätigt.

## Echter ADIF-Output von SimpleFT8 (v0.97.81)

Beispiel-Record aus heutigem Log:

```
<CALL:5>HA1BF <QSO_DATE:8>20260520 <TIME_ON:6>110112 <TIME_OFF:6>110127
<BAND:3>30M <FREQ:9>10.136000 <MODE:3>FT8 <RST_SENT:3>-19
<GRIDSQUARE:4>JN86 <RST_RCVD:3>+08 <OPERATOR:6>DA1MHH
<STATION_CALLSIGN:6>DA1MHH <MY_GRIDSQUARE:4>JO31 <TX_PWR:3>100
<QSL_SENT:1>N <QSL_RCVD:1>N <MY_DXCC:3>230 <MY_COUNTRY:7>Germany
<MY_CQ_ZONE:2>14 <MY_ITU_ZONE:2>28 <COMMENT:14>SimpleFT8 v1.0 <EOR>
```

Mike's Callsign: **DA1MHH** (echt), Locator JO31.

## Upload-API-Code (log/qrz.py)

POST an `https://logbook.qrz.com/api` mit:
```
KEY=<api_key>
ACTION=INSERT
ADIF=<adif_record_string>
```

Headers: `User-Agent: SimpleFT8/1.0 (DA1MHH)`,
`Content-Type: application/x-www-form-urlencoded`.

Response wird als `KEY=VALUE&KEY=VALUE` geparst.

## Bisherige Tests / Bekanntes

- ADIF-Format sieht laut Doku-Vergleich korrekt aus.
- FT4 schreibt MODE=MFSK + SUBMODE=FT4 (ADIF-Standard).
- RST_SENT/RST_RCVD: R-Prefix wird gestrippt (P1.BUNDLE Bug-B-Fix).
- Upload-Response wird geparst aber nicht detailliert geloggt.

## Mike's Vermutung

> „kein einziges wurde bestätigt entweder format fehlt oder einträge fehlen"

## Hypothesen

**H1 — Confirmed-Definition:** QRZ „Confirmed" heißt BEIDE Logs (mein
+ Gegenstation) sind hochgeladen UND matchen. Wenn die Gegenstation
nicht QRZ nutzt sondern z.B. LoTW oder Club Log → kein QRZ-Confirmed.
Wäre kein SimpleFT8-Bug sondern normales QRZ-Verhalten.

**H2 — TIME_ON-Genauigkeit:** SimpleFT8 schreibt 6-stellig `HHMMSS`
(z.B. `110112`). QRZ-Match-Logik akzeptiert evtl. nur 4-stellig `HHMM`
oder Match-Toleranz ist ±X Minuten. Sekunden-Genauigkeit könnte
Match verhindern wenn Gegenstation 4-stellig schreibt.
Industry-Standard für FT8-ADIF: 4-stellig oder 6-stellig?

**H3 — APP_QRZLOG_STATUS / QRZCOM_QSO_UPLOAD_STATUS:** Referenz-ADIFs
von Mike enthalten `QRZCOM_QSO_UPLOAD_STATUS:1>Y`. Fehlt in unserem
ADIF — schickt das Upload eine Markierung mit zurück?

**H4 — FREQ-Präzision:** Wir schreiben `<FREQ:9>10.136000`.
WSJT-X schreibt typisch `14.074500` (5 Stellen). Andere Logger 6 Stellen.
Kein Unterschied erwartet — aber QRZ könnte Sonderfälle haben.

**H5 — Fehlende Felder:** Referenz-ADIFs haben `CONT` (Kontinent),
`DXCC`, `COUNTRY`, `DISTANCE`. SimpleFT8 schreibt MY_DXCC + MY_COUNTRY
(eigene Station) aber NICHT DXCC + COUNTRY der Gegenstation. Wenn QRZ
diese braucht um zu matchen → Problem.

**H6 — QSL_SENT/QSL_RCVD = N:** wir schreiben „N" (kein QSL gesendet).
Vielleicht setzt QRZ erst auf „Confirmed" wenn QSL_RCVD durch Upload-API
spezifisch gemarkt wird?

## Was R1 bitte beantwortet

1. **QRZ.com Logbook API Doku** — wie funktioniert der Confirmed-Status
   exakt? Quelle bitte angeben (offizielle QRZ-Doku oder Forum-Posts).
   Web-Recherche bitte einbauen wenn nötig.

2. **Welche der Hypothesen H1-H6 ist die wahrscheinlichste?**

3. **Welche ADIF-Felder fehlen die QRZ.com-Confirmed erleichtern würden?**
   Konkrete Liste mit Begründung.

4. **TIME_ON 4-stellig vs 6-stellig:** ist 6 ein Problem oder nicht?
   Industry-Standard?

5. **Konkreter Fix-Vorschlag** wenn ADIF-Verbesserung nötig: welche
   Felder hinzufügen, welche umbenennen.

6. **WSJT-X ADIF-Format** zum Vergleich — gibt's bekannte Unterschiede
   zu SimpleFT8?

## Wichtig

Mike ist Hobby-Funker — Lösung muss KISS sein. „Fehlende Felder"
hinzufügen ist OK wenn sinnvoll. „Format umstellen" nur wenn Beweis dass
es das Problem ist.

Bitte mit Recherche aus dem Web wenn nötig (R1 kann das).
