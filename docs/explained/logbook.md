# Logbook & QRZ Integration

## Overview

SimpleFT8 includes a fully integrated logbook that automatically records every completed QSO in ADIF 3.1.7 format.

## Features

### QSO Table
- **Sortable columns**: Date, Call, Band, Mode, RST Sent/Received, Grid, Country, km
- **Search**: Filter by callsign, band, or country (search bar at top)
- **DXCC counter**: Shows unique countries worked
- **QSO count**: Total QSOs displayed

### Distance Display (km)
- **Exact**: When the other station's grid locator is known (from QSO exchange)
- **Approximate (~)**: When no grid is available, distance is estimated from the callsign prefix (e.g., VK = Australia, JA = Japan)
- Distance is calculated from your locator (JO31) using the Haversine formula

### QSO Detail Overlay
Click any QSO in the logbook to see:
- Full QSO data (call, date, time, band, mode, RST, grid)
- **QRZ.com lookup**: Name, location, photo (requires QRZ API key)
- **Upload to QRZ**: Single QSO or bulk upload

### Delete QSO
1. Click the QSO you want to delete
2. Click **Delete** button (red)
3. Confirm in the dialog
4. QSO is removed from the ADIF file on disk

### QRZ.com Integration
- **Lookup**: Click any QSO to see QRZ.com info (name, QTH, photo)
- **Upload**: Upload all QSOs to your QRZ.com logbook
- **Setup**: Enter your QRZ API key in Settings

## ADIF Files

QSOs are stored as daily ADIF files:
```
SimpleFT8_LOG_20260415.adi
SimpleFT8_LOG_20260416.adi
```

Each file contains standard ADIF 3.1.7 fields: CALL, QSO_DATE, TIME_ON, BAND, FREQ, MODE, RST_SENT, RST_RCVD, GRIDSQUARE, MY_GRIDSQUARE, STATION_CALLSIGN, TX_PWR.

## Tips

- The logbook loads ALL .adi files from the SimpleFT8 directory on startup
- QSOs are added immediately after RR73 is sent (no need to wait for 73)
- Use the search bar to quickly find a specific station
- The DXCC counter counts unique country prefixes across all QSOs
