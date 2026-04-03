"""SimpleFT8 Geo — Maidenhead-Locator, Entfernungsberechnung, Callsign-Lookup."""

import math

# ── Maidenhead Grid → Lat/Lon ──────────────────────────────

def grid_to_latlon(locator: str) -> tuple[float, float] | None:
    """Maidenhead Grid-Locator in Lat/Lon umrechnen (Mitte des Feldes).

    Args:
        locator: 4 oder 6 Zeichen (z.B. 'JO31', 'JO31fk')
    Returns:
        (latitude, longitude) oder None bei ungueltigem Locator
    """
    loc = locator.upper().strip()
    if len(loc) < 4:
        return None
    if not (loc[0].isalpha() and loc[1].isalpha() and
            loc[2].isdigit() and loc[3].isdigit()):
        return None

    lon = (ord(loc[0]) - ord('A')) * 20.0
    lat = (ord(loc[1]) - ord('A')) * 10.0
    lon += int(loc[2]) * 2.0
    lat += int(loc[3]) * 1.0

    if len(loc) >= 6 and loc[4].isalpha() and loc[5].isalpha():
        lon += (ord(loc[4]) - ord('A')) * (5.0 / 60.0)
        lat += (ord(loc[5]) - ord('A')) * (2.5 / 60.0)
    else:
        lon += 1.0   # Mitte des 2°-Feldes
        lat += 0.5   # Mitte des 1°-Feldes

    return (lat - 90.0, lon - 180.0)


# ── Haversine Entfernung ───────────────────────────────────

def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreis-Entfernung in km (Haversine)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def grid_distance(my_grid: str, dx_grid: str) -> int | None:
    """Entfernung zwischen zwei Grid-Locatoren in km."""
    pos1 = grid_to_latlon(my_grid)
    pos2 = grid_to_latlon(dx_grid)
    if pos1 is None or pos2 is None:
        return None
    return int(distance_km(pos1[0], pos1[1], pos2[0], pos2[1]))


# ── Callsign → Land (Prefix-Lookup) ───────────────────────

# Haeufigste Prefixe — deckt >95% des FT8-Verkehrs ab
_PREFIX_MAP = {
    # Europa
    'DA': 'DE', 'DB': 'DE', 'DC': 'DE', 'DD': 'DE', 'DF': 'DE',
    'DG': 'DE', 'DH': 'DE', 'DJ': 'DE', 'DK': 'DE', 'DL': 'DE', 'DM': 'DE',
    'PA': 'NL', 'PB': 'NL', 'PD': 'NL', 'PE': 'NL', 'PH': 'NL', 'PI': 'NL',
    'ON': 'BE', 'OO': 'BE', 'OR': 'BE', 'OT': 'BE',
    'F': 'FR', 'FA': 'FR', 'FB': 'FR', 'FC': 'FR', 'FD': 'FR', 'FE': 'FR',
    'FF': 'FR', 'FG': 'FR', 'FH': 'FR', 'FJ': 'FR', 'FK': 'FR', 'FL': 'FR',
    'FM': 'FR', 'FO': 'FR', 'FP': 'FR', 'FQ': 'FR', 'FR': 'FR', 'FS': 'FR',
    'FT': 'FR', 'FW': 'FR', 'FY': 'FR',
    'G': 'GB', 'GB': 'GB', 'GC': 'GB', 'GD': 'GB', 'GI': 'GB',
    'GJ': 'GB', 'GM': 'GB', 'GN': 'GB', 'GW': 'GB', 'GX': 'GB',
    'M': 'GB', 'MA': 'GB', 'MB': 'GB', 'MC': 'GB', 'MD': 'GB',
    'ME': 'GB', 'MF': 'GB', 'MG': 'GB', 'MI': 'GB', 'MJ': 'GB',
    'MM': 'GB', 'MN': 'GB', 'MP': 'GB', 'MQ': 'GB', 'MT': 'GB',
    'MU': 'GB', 'MW': 'GB', 'MX': 'GB',
    'I': 'IT', 'IK': 'IT', 'IN': 'IT', 'IS': 'IT', 'IT': 'IT',
    'IU': 'IT', 'IV': 'IT', 'IW': 'IT', 'IX': 'IT', 'IY': 'IT', 'IZ': 'IT',
    'EA': 'ES', 'EB': 'ES', 'EC': 'ES', 'ED': 'ES', 'EE': 'ES', 'EF': 'ES',
    'EG': 'ES', 'EH': 'ES',
    'CT': 'PT', 'CU': 'PT',
    'HB': 'CH', 'HE': 'CH',
    'OE': 'AT',
    'SP': 'PL', 'SQ': 'PL', 'SN': 'PL', 'SO': 'PL', '3Z': 'PL',
    'OK': 'CZ', 'OL': 'CZ',
    'OM': 'SK',
    'HA': 'HU', 'HG': 'HU',
    'YO': 'RO', 'YP': 'RO', 'YQ': 'RO', 'YR': 'RO',
    'LZ': 'BG',
    '9A': 'HR',
    'S5': 'SI', 'S6': 'SI',
    'E7': 'BA',
    'YU': 'RS', 'YT': 'RS',
    'Z3': 'MK',
    'ZA': 'AL',
    'SV': 'GR', 'SW': 'GR', 'SX': 'GR', 'SY': 'GR', 'SZ': 'GR',
    'TA': 'TR', 'TB': 'TR', 'TC': 'TR',
    'SM': 'SE', 'SA': 'SE', 'SB': 'SE', 'SC': 'SE', 'SD': 'SE',
    'SE': 'SE', 'SF': 'SE', 'SG': 'SE', 'SH': 'SE', 'SI': 'SE',
    'SJ': 'SE', 'SK': 'SE', 'SL': 'SE',
    'LA': 'NO', 'LB': 'NO', 'LC': 'NO', 'LD': 'NO', 'LE': 'NO',
    'LF': 'NO', 'LG': 'NO', 'LH': 'NO', 'LI': 'NO', 'LJ': 'NO',
    'LK': 'NO', 'LL': 'NO', 'LM': 'NO', 'LN': 'NO',
    'OH': 'FI', 'OF': 'FI', 'OG': 'FI', 'OI': 'FI',
    'OZ': 'DK', 'OU': 'DK', 'OV': 'DK', 'OW': 'DK', 'OX': 'DK',
    'TF': 'IS',
    'EI': 'IE', 'EJ': 'IE',
    'LY': 'LT',
    'YL': 'LV',
    'ES': 'EE',
    'UR': 'UA', 'US': 'UA', 'UT': 'UA', 'UU': 'UA', 'UV': 'UA',
    'UW': 'UA', 'UX': 'UA', 'UY': 'UA', 'UZ': 'UA',
    'R': 'RU', 'RA': 'RU', 'RB': 'RU', 'RC': 'RU', 'RD': 'RU',
    'RE': 'RU', 'RF': 'RU', 'RG': 'RU', 'RJ': 'RU', 'RK': 'RU',
    'RL': 'RU', 'RM': 'RU', 'RN': 'RU', 'RO': 'RU', 'RQ': 'RU',
    'RT': 'RU', 'RU': 'RU', 'RV': 'RU', 'RW': 'RU', 'RX': 'RU',
    'RY': 'RU', 'RZ': 'RU', 'UA': 'RU', 'UB': 'RU', 'UC': 'RU',
    'UD': 'RU',
    # Nordamerika
    'K': 'US', 'KA': 'US', 'KB': 'US', 'KC': 'US', 'KD': 'US',
    'KE': 'US', 'KF': 'US', 'KG': 'US', 'KI': 'US', 'KJ': 'US',
    'KK': 'US', 'KM': 'US', 'KN': 'US', 'KO': 'US', 'KQ': 'US',
    'KR': 'US', 'KS': 'US', 'KT': 'US', 'KU': 'US', 'KV': 'US',
    'KW': 'US', 'KX': 'US', 'KY': 'US', 'KZ': 'US',
    'N': 'US', 'NA': 'US', 'NB': 'US', 'NC': 'US', 'ND': 'US',
    'NE': 'US', 'NF': 'US', 'NG': 'US', 'NI': 'US', 'NJ': 'US',
    'NK': 'US', 'NM': 'US', 'NN': 'US', 'NO': 'US', 'NQ': 'US',
    'NR': 'US', 'NS': 'US', 'NT': 'US', 'NU': 'US', 'NV': 'US',
    'NW': 'US', 'NX': 'US', 'NY': 'US', 'NZ': 'US',
    'W': 'US', 'WA': 'US', 'WB': 'US', 'WC': 'US', 'WD': 'US',
    'WE': 'US', 'WF': 'US', 'WG': 'US', 'WI': 'US', 'WJ': 'US',
    'WK': 'US', 'WM': 'US', 'WN': 'US', 'WO': 'US', 'WQ': 'US',
    'WR': 'US', 'WS': 'US', 'WT': 'US', 'WU': 'US', 'WV': 'US',
    'WW': 'US', 'WX': 'US', 'WY': 'US', 'WZ': 'US',
    'AA': 'US', 'AB': 'US', 'AC': 'US', 'AD': 'US', 'AE': 'US',
    'AF': 'US', 'AG': 'US', 'AI': 'US', 'AJ': 'US', 'AK': 'US',
    'AL': 'US',
    'VE': 'CA', 'VA': 'CA', 'VB': 'CA', 'VC': 'CA', 'VD': 'CA',
    'VO': 'CA', 'VX': 'CA', 'VY': 'CA',
    'XE': 'MX', 'XF': 'MX',
    # Suedamerika
    'LU': 'AR', 'LO': 'AR', 'LP': 'AR', 'LQ': 'AR', 'LR': 'AR',
    'LS': 'AR', 'LT': 'AR', 'LV': 'AR', 'LW': 'AR',
    'PY': 'BR', 'PP': 'BR', 'PQ': 'BR', 'PR': 'BR', 'PS': 'BR',
    'PT': 'BR', 'PU': 'BR', 'PV': 'BR', 'PW': 'BR', 'PX': 'BR',
    'CE': 'CL',
    'HK': 'CO',
    'HC': 'EC',
    'OA': 'PE',
    'CX': 'UY',
    'YV': 'VE',
    # Asien
    'JA': 'JP', 'JE': 'JP', 'JF': 'JP', 'JG': 'JP', 'JH': 'JP',
    'JI': 'JP', 'JJ': 'JP', 'JK': 'JP', 'JL': 'JP', 'JM': 'JP',
    'JN': 'JP', 'JO': 'JP', 'JP': 'JP', 'JQ': 'JP', 'JR': 'JP',
    'JS': 'JP', '7J': 'JP', '7K': 'JP', '7L': 'JP', '7M': 'JP',
    'B': 'CN', 'BA': 'CN', 'BD': 'CN', 'BG': 'CN', 'BH': 'CN',
    'BI': 'CN', 'BJ': 'CN', 'BT': 'CN', 'BV': 'CN', 'BX': 'CN',
    'BY': 'CN',
    'HL': 'KR', 'DS': 'KR', 'DT': 'KR',
    'VU': 'IN', 'VT': 'IN', 'VV': 'IN', 'VW': 'IN',
    'HS': 'TH',
    'DU': 'PH',
    '9V': 'SG',
    '9M': 'MY',
    'YB': 'ID', 'YC': 'ID', 'YD': 'ID', 'YE': 'ID', 'YF': 'ID',
    'YG': 'ID', 'YH': 'ID',
    # Ozeanien
    'VK': 'AU',
    'ZL': 'NZ',
    'KH6': 'HI',  # Hawaii
    # Afrika
    'ZS': 'ZA', 'ZR': 'ZA', 'ZT': 'ZA', 'ZU': 'ZA',
    'SU': 'EG',
    'CN': 'MA',
    '5N': 'NG',
    '5Z': 'KE',
    # Karibik / Atlantik
    'HH': 'HT',
    'HI': 'DO',
    'CO': 'CU', 'CL': 'CU', 'CM': 'CU',
    'C3': 'AD', 'C31': 'AD',
    '4X': 'IL', '4Z': 'IL',
    'T3': 'KI', 'T31': 'KI',  # Kiribati
    'HZ': 'SA',
    'A4': 'OM',
    'A6': 'AE', 'A7': 'QA',
    # Afrika extra
    'TY': 'BJ', '5T': 'MR', '6W': 'SN', 'D4': 'CV', '9G': 'GH',
    'TU': 'CI', '3B': 'MU', 'J2': 'DJ',
    # Asien extra
    '4L': 'GE', 'UN': 'KZ', 'EX': 'KG', 'YI': 'IQ', 'AP': 'PK',
    # Pazifik extra
    'FK': 'NC', 'FO': 'PF', 'PJ': 'BQ',
}

# Land-Code → voller Name (fuer Anzeige)
_COUNTRY_NAMES = {
    'DE': 'Germany', 'NL': 'Netherlands', 'BE': 'Belgium', 'FR': 'France',
    'GB': 'England', 'IT': 'Italy', 'ES': 'Spain', 'PT': 'Portugal',
    'CH': 'Switzerland', 'AT': 'Austria', 'PL': 'Poland', 'CZ': 'Czechia',
    'SK': 'Slovakia', 'HU': 'Hungary', 'RO': 'Romania', 'BG': 'Bulgaria',
    'HR': 'Croatia', 'SI': 'Slovenia', 'BA': 'Bosnia', 'RS': 'Serbia',
    'MK': 'N.Macedonia', 'AL': 'Albania', 'GR': 'Greece', 'TR': 'Turkey',
    'SE': 'Sweden', 'NO': 'Norway', 'FI': 'Finland', 'DK': 'Denmark',
    'IS': 'Iceland', 'IE': 'Ireland', 'LT': 'Lithuania', 'LV': 'Latvia',
    'EE': 'Estonia', 'UA': 'Ukraine', 'RU': 'Russia',
    'US': 'USA', 'CA': 'Canada', 'MX': 'Mexico',
    'AR': 'Argentina', 'BR': 'Brazil', 'CL': 'Chile', 'CO': 'Colombia',
    'EC': 'Ecuador', 'PE': 'Peru', 'UY': 'Uruguay', 'VE': 'Venezuela',
    'JP': 'Japan', 'CN': 'China', 'KR': 'S.Korea', 'IN': 'India',
    'TH': 'Thailand', 'PH': 'Philippines', 'SG': 'Singapore',
    'MY': 'Malaysia', 'ID': 'Indonesia',
    'AU': 'Australia', 'NZ': 'N.Zealand', 'HI': 'Hawaii',
    'ZA': 'S.Africa', 'EG': 'Egypt', 'MA': 'Morocco', 'NG': 'Nigeria',
    'KE': 'Kenya', 'HT': 'Haiti', 'DO': 'Dom.Rep.', 'CU': 'Cuba',
    'AD': 'Andorra', 'KI': 'Kiribati', 'IL': 'Israel', 'SA': 'S.Arabia',
    'OM': 'Oman', 'AE': 'UAE', 'QA': 'Qatar',
    'BJ': 'Benin', 'MR': 'Mauritania', 'SN': 'Senegal', 'CV': 'Cape Verde',
    'GH': 'Ghana', 'CI': 'Ivory Coast', 'MU': 'Mauritius', 'DJ': 'Djibouti',
    'GE': 'Georgia', 'KZ': 'Kazakhstan', 'KG': 'Kyrgyzstan',
    'IQ': 'Iraq', 'PK': 'Pakistan',
    'NC': 'New Caledonia', 'PF': 'Polynesia', 'BQ': 'Bonaire',
}


# Ungefaehre Koordinaten pro Land (Hauptstadt/Mitte) fuer km-Schaetzung
_COUNTRY_COORDS = {
    'DE': (51.0, 10.0), 'NL': (52.3, 4.9), 'BE': (50.8, 4.4), 'FR': (46.6, 2.2),
    'GB': (51.5, -0.1), 'IT': (42.5, 12.5), 'ES': (40.4, -3.7), 'PT': (38.7, -9.1),
    'CH': (46.8, 8.2), 'AT': (47.5, 14.5), 'PL': (52.0, 20.0), 'CZ': (49.8, 15.5),
    'SK': (48.7, 19.7), 'HU': (47.5, 19.0), 'RO': (44.4, 26.1), 'BG': (42.7, 25.5),
    'HR': (45.8, 16.0), 'SI': (46.1, 14.5), 'BA': (43.9, 17.7), 'RS': (44.0, 21.0),
    'GR': (37.9, 23.7), 'TR': (39.9, 32.9), 'SE': (59.3, 18.1), 'NO': (59.9, 10.7),
    'FI': (60.2, 24.9), 'DK': (55.7, 12.6), 'IS': (64.1, -21.9), 'IE': (53.3, -6.3),
    'LT': (54.7, 25.3), 'LV': (56.9, 24.1), 'EE': (59.4, 24.7),
    'UA': (50.4, 30.5), 'RU': (55.8, 37.6),
    'US': (39.0, -98.0), 'CA': (56.0, -106.0), 'MX': (23.6, -102.5),
    'AR': (-34.6, -58.4), 'BR': (-15.8, -47.9), 'CL': (-33.4, -70.6),
    'CO': (4.7, -74.1), 'VE': (10.5, -66.9), 'PE': (-12.0, -77.0),
    'JP': (35.7, 139.7), 'CN': (39.9, 116.4), 'KR': (37.6, 127.0),
    'IN': (28.6, 77.2), 'TH': (13.8, 100.5), 'PH': (14.6, 121.0),
    'SG': (1.3, 103.8), 'MY': (3.1, 101.7), 'ID': (-6.2, 106.8),
    'AU': (-25.3, 133.8), 'NZ': (-41.3, 174.8), 'HI': (21.3, -157.8),
    'ZA': (-33.9, 18.4), 'EG': (30.0, 31.2), 'MA': (33.9, -6.9),
    'NG': (9.1, 7.5), 'KE': (-1.3, 36.8),
    'IL': (31.8, 35.2), 'SA': (24.7, 46.7), 'AE': (25.2, 55.3),
    'CU': (23.1, -82.4), 'KI': (1.5, 173.0), 'QA': (25.3, 51.5),
    # Afrika
    'BJ': (6.5, 2.6), 'MR': (18.1, -15.9), 'SN': (14.7, -17.4),
    'CV': (15.0, -23.6), 'GH': (5.6, -0.2), 'CI': (6.8, -5.3),
    'MU': (-20.2, 57.5), 'DJ': (11.6, 43.1),
    # Asien extra
    'GE': (41.7, 44.8), 'KZ': (51.2, 71.4), 'KG': (42.9, 74.6),
    'IQ': (33.3, 44.4), 'PK': (33.7, 73.0),
    # Pazifik extra
    'NC': (-22.3, 166.5), 'PF': (-17.5, -149.6), 'BQ': (12.2, -68.3),
}


def callsign_to_distance(callsign: str, my_grid: str) -> int | None:
    """Ungefaehre Entfernung zum Callsign-Prefix (wenn kein Grid verfuegbar)."""
    my_pos = grid_to_latlon(my_grid)
    if not my_pos:
        return None

    call = callsign.upper().strip().lstrip('<').rstrip('>')
    if '/' in call:
        parts = call.split('/')
        call = max(parts, key=len)

    # Prefix → Country Code → Coords
    for plen in [3, 2, 1]:
        prefix = call[:plen]
        if prefix in _PREFIX_MAP:
            code = _PREFIX_MAP[prefix]
            if code in _COUNTRY_COORDS:
                lat, lon = _COUNTRY_COORDS[code]
                return int(distance_km(my_pos[0], my_pos[1], lat, lon))
    return None


def callsign_to_country(callsign: str) -> str:
    """Callsign → Laender-Kuerzel (2-3 Buchstaben fuer Anzeige)."""
    call = callsign.upper().strip().lstrip('<').rstrip('>')
    # Slash-Calls: DA1MHH/P → DA1MHH
    if '/' in call:
        parts = call.split('/')
        call = max(parts, key=len)

    # 3-char, 2-char, 1-char Prefix probieren
    for plen in [3, 2, 1]:
        prefix = call[:plen]
        if prefix in _PREFIX_MAP:
            code = _PREFIX_MAP[prefix]
            return _COUNTRY_NAMES.get(code, code)
    return "?"
