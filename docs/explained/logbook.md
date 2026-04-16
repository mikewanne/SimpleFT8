# Logbook — QSO Management and Export

## In a Nutshell

SimpleFT8's built-in logbook stores every completed QSO in standard ADIF format. You can search, sort, view details, delete entries, and upload to QRZ.com — all from within the application. No external log software required.

## Features at a Glance

| Feature | Description |
|---------|-------------|
| Sortable table | Click any column header to sort by date, call, band, mode, country, or distance |
| Search | Filter by callsign, band, country name, or grid square |
| DXCC counter | Shows how many unique DXCC entities you have worked |
| QSO detail overlay | Click any QSO to see full details and QRZ.com station info |
| Delete QSOs | Remove incorrect or test entries from the log |
| QRZ.com upload | Bulk upload all QSOs to your QRZ.com logbook |
| Distance display | Shows km from your QTH, exact from grid or approximate from callsign prefix |

## The QSO Table

The logbook table shows six columns:

| Column | Content | Example |
|--------|---------|---------|
| Datum | Date of the QSO (DD.MM.YY) | 09.04.26 |
| Call | Callsign of the other station | EA3FHP |
| Band | Operating band | 20M |
| Mode | Digital mode used | FT8 |
| Land | Country (derived from callsign prefix) | Spain |
| km | Distance from your QTH | 1247 |

Click any column header to sort. Click again to reverse the sort order.

## Search

Type into the search field to filter the table in real time. The search checks:

- **Callsign** — type part of a call (e.g., "EA3" to find all Spanish stations)
- **Band** — type "20M" to show only 20-meter QSOs
- **Country** — type "Japan" or "Germany" to filter by country name
- **Grid** — type a grid square prefix (e.g., "JN" for southern Europe)

The search is case-insensitive. Clear the search field to show all QSOs again.

## DXCC Counter

The counter at the top right shows two values:

- **DXCC: 42** — Number of unique countries/entities you have worked
- **187 QSOs** — Total number of logged contacts

The DXCC count is derived from callsign prefixes and covers all QSOs across all ADIF files in your SimpleFT8 directory.

## QSO Detail Overlay

Click any row in the logbook to open the detail overlay on the right side. It shows:

### Station Information (from QRZ.com)
- Full name of the operator
- QTH (city/town), country, grid square
- DXCC entity number, CQ zone, ITU zone

The QRZ lookup happens in the background — the UI stays responsive while waiting for the result.

### Editable QSO Fields
- Date and time (UTC)
- Band and frequency
- Mode
- RST sent and received (signal reports)
- Grid square
- TX power
- Comment

### Actions
- **Speichern** — Save any edits to the ADIF file
- **QRZ Upload** — Upload this single QSO to QRZ.com
- **Loeschen** — Delete this QSO (with confirmation dialog)

## Deleting a QSO

To delete a QSO:

1. Click the QSO in the table to select it.
2. Click the **Loeschen** button (either in the table toolbar or in the detail overlay).
3. A confirmation dialog shows the call, date, time, band, and mode.
4. Click **Ja, loeschen** to confirm.

The QSO is permanently removed from the ADIF file. This cannot be undone. The table refreshes automatically after deletion.

## QRZ.com Upload

### Setup
Add your QRZ.com credentials in the SimpleFT8 settings:

- `qrz_api_key` — Your QRZ XML API key (from QRZ.com account settings)
- `qrz_username` — Your QRZ.com username
- `qrz_password` — Your QRZ.com password

### Single QSO Upload
Click a QSO in the logbook, then click **QRZ Upload** in the detail overlay. The status bar shows the result.

### Bulk Upload
Click the **QRZ** button in the logbook toolbar to upload all QSOs at once. The upload runs in the background and reports:

- How many QSOs were uploaded successfully
- How many were duplicates (already on QRZ.com)
- How many failed

## Distance Display

The km column shows the distance from your QTH (configured grid square) to the other station:

| Display | Source | Accuracy |
|---------|--------|----------|
| **1247** | Grid square from QSO exchange | Exact (grid center to grid center, Haversine formula) |
| **~8500** | Callsign prefix lookup | Approximate (country center point) |
| *(empty)* | Neither grid nor known prefix | No distance available |

The tilde (~) prefix indicates an approximate distance calculated from the callsign prefix rather than an actual grid exchange.

## ADIF File Format

QSOs are stored in ADIF 3.1.7 format, one file per day:

```
SimpleFT8_LOG_20260409.adi
SimpleFT8_LOG_20260410.adi
SimpleFT8_LOG_20260411.adi
```

Each file contains a header and one record per QSO. The format is compatible with all major logging software (Log4OM, DXKeeper, WSJT-X, etc.).

### Fields Written per QSO

| ADIF Field | Content |
|------------|---------|
| CALL | Other station's callsign |
| QSO_DATE | Date (YYYYMMDD) |
| TIME_ON | Time UTC (HHMMSS) |
| BAND | Band (e.g., 20M) |
| FREQ | Frequency in MHz |
| MODE | FT8, FT4, or FT2 |
| RST_SENT | Your signal report to them |
| RST_RCVD | Their signal report to you |
| GRIDSQUARE | Their grid locator |
| MY_GRIDSQUARE | Your grid locator |
| STATION_CALLSIGN | Your callsign |
| TX_PWR | Your transmit power in watts |
| COMMENT | "SimpleFT8 v1.0" |

## Tips for Operators

- **The logbook loads all ADIF files** in your SimpleFT8 directory, not just today's. Historical QSOs from previous sessions appear automatically.
- **QSOs are logged at RR73 time**, not when 73 is received. If the other station never sends 73, the QSO is still logged — RR73 is the standard completion point in FT8.
- **Back up your ADIF files.** They are plain text files in your SimpleFT8 directory. Copy them to a safe location regularly.
- **Delete with care.** Deletion is permanent and removes the record from the ADIF file on disk. There is no undo or recycle bin.
- **QRZ upload handles duplicates gracefully.** If a QSO already exists on QRZ.com, it is counted as a duplicate, not an error.
- **The detail overlay closes** when you switch back to the QSO tab. Click a logbook entry again to reopen it.
