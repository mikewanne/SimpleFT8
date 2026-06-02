"""SimpleFT8 — Diplome / Awards-Berechnung aus QSO-Records.

Reines Berechnungsmodul (KEINE UI, keine I/O). Bekommt eine Liste von
ADIF-Records (dicts mit GROSS-geschriebenen Keys, wie `log.adif.parse_adif_file`
sie liefert) und ermittelt pro Diplom die Menge der gearbeiteten und der
(per LoTW) bestaetigten Einheiten.

Hobby-Tool-Philosophie (KISS): die aus den vorhandenen QRZ-ADIF-Feldern direkt
ableitbaren Diplome — DXCC, WAC, WAS, WAZ, WAE (Europa-Naeherung), WPX. Kein
DLD/IOTA (Quellfelder fehlen: DOK gar nicht, IOTA ueberall "N/A").

Datenquelle der reichhaltigen Felder (DXCC/CONT/STATE/CQZ/CALL/BAND/
LOTW_QSL_RCVD) ist der QRZ-Export (`adif/_backup_qrz_export/`). Beide eigenen
Rufzeichen (DA1MHH + DO4MHH) fließen in EINEN gemeinsamen Pool — set-basiert,
also automatisch dedupliziert.

Bestaetigt = ausschliesslich `LOTW_QSL_RCVD == "Y"` (international anerkannt;
QRZ-interner Status `APP_QRZLOG_STATUS=C` wird bewusst NICHT als Bestaetigung
gewertet, da kein Diplom-Programm ihn anerkennt).
"""

import re

# Die 50 US-Bundesstaaten (USPS-Codes) fuer WAS. Bewusst NICHT ueber DXCC==291
# gefiltert: Alaska (DXCC 6) und Hawaii (DXCC 110) haben eigene DXCC-Nummern,
# tragen aber AK/HI im STATE-Feld und zaehlen fuer WAS mit. Gebiete wie
# Puerto Rico/Guam sind eigene DXCC-Entities und KEINE WAS-States -> fehlen
# hier bewusst.
US_STATES = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
})

# WAC: die sechs Kontinente. Antarktis (AN) zaehlt fuer WAC NICHT mit.
WAC_CONTINENTS = frozenset({"NA", "SA", "EU", "AF", "AS", "OC"})

# DXCC: offizielle Marken-Staffelung (ARRL). Basis 100, dann Endorsement-Marken.
# Honor Roll = innerhalb von 9 Einheiten zur aktuellen Gesamtzahl (~340).
DXCC_TIERS = (100, 150, 200, 250, 300)
DXCC_HONOR_ROLL = 331

# WAE (Worked All Europe, DARC): NAEHERUNG ueber eindeutige europaeische
# DXCC-Entities (CONT=="EU"). Das offizielle WAE hat zusaetzliche Multiplier
# (IT9-Sizilien, GM-Shetland, eu-Russland-Distrikte), die keine eigenen
# DXCC-Nummern sind — die erfasst diese Naeherung NICHT. In der UI ehrlich
# als "Naeherung" gekennzeichnet. Es gibt ~70 europaeische DXCC-Entities.
WAE_GOAL = 70

# WPX (Worked All Prefixes, CQ): Basis-Diplom = 300 verschiedene Praefixe.
WPX_GOAL = 300

# DXCC Challenge (ARRL): Summe eindeutiger (Entity, Band)-Slots, Ziel 1000.
# Offiziell zaehlen nur die HF-Baender 160-6 m (NICHT 60 m, NICHT 2 m+).
DXCC_CHALLENGE_GOAL = 1000
CHALLENGE_BANDS = frozenset({
    "160M", "80M", "40M", "30M", "20M", "17M", "15M", "12M", "10M", "6M",
})

# 5-Band-DXCC (ARRL): 100 Entities auf JEDEM der fuenf klassischen Baender.
FIVE_BAND_BANDS = ("80M", "40M", "20M", "15M", "10M")
FIVE_BAND_GOAL = 100

# Reihenfolge fuer eine stabile Anzeige im Dialog (DXCC + neue zuerst).
AWARD_ORDER = ("DXCC", "WAE", "WPX", "WAC", "WAS", "WAZ")

# Klartext-Beschreibung je Diplom (fuer den Dialog / Tooltips).
AWARD_INFO = {
    "DXCC": "DX Century Club (ARRL) — 100 DXCC-Gebiete (Entities).",
    "WAE": "Worked All Europe (DARC) — Naeherung ueber europaeische "
           "DXCC-Laender (kein offizielles WAE).",
    "WPX": "Worked All Prefixes (CQ) — 300 verschiedene Rufzeichen-Praefixe.",
    "WAC": "Worked All Continents (IARU) — alle 6 Kontinente.",
    "WAS": "Worked All States (ARRL) — alle 50 US-Bundesstaaten.",
    "WAZ": "Worked All Zones (CQ) — alle 40 CQ-Zonen.",
}

# Betriebs-/Mobil-Zusaetze, die KEINEN WPX-Praefix bilden und vor der
# Praefix-Extraktion entfernt werden (z. B. DH7WW/P, S51PV/QRP, UR5ZEP/A).
_WPX_DROP_SUFFIXES = frozenset({
    "P", "M", "MM", "AM", "PM", "QRP", "QRPP", "A", "J", "R",
    "PORTABLE", "MOBILE", "LH", "LGT", "AG",
})

# WPX-Praefix aus einem normalen Call: fuehrender [A-Z0-9]-Teil bis
# einschliesslich der LETZTEN Ziffer, gefolgt von reinem Buchstaben-Suffix.
_WPX_RE = re.compile(r"^([A-Z0-9]*\d)[A-Z]*$")
_LEADING_LETTERS_RE = re.compile(r"^([A-Z]+)")


def wpx_prefix(call: str) -> str | None:
    """WPX-Praefix aus einem Rufzeichen (CQ-WPX-Regel, FT8-tauglich).

    Behandelt die drei im Log vorkommenden Slash-Formen:
        DA1MHH      -> "DA1"   (Normalfall)
        9A7W        -> "9A7"
        F5OYA/P     -> "F5"    (Mobil-Suffix entfernt)
        S51PV/QRP   -> "S51"
        OE/DL6CGU   -> "OE0"   (Praefix-Slash vorn, ohne Ziffer -> "0")
        SV9/DL1MTB  -> "SV9"
        N1UL/3      -> "N3"    (Regions-Ziffer ersetzt)
        RA0QK/8     -> "RA8"

    Liefert None, wenn kein sinnvoller Praefix ableitbar ist.
    """
    if not call:
        return None
    s = call.upper().strip().lstrip("<").rstrip(">")
    if not s:
        return None

    if "/" in s:
        parts = [p.strip() for p in s.split("/") if p.strip()]
        # Betriebs-Suffixe (P/M/QRP/...) verwerfen.
        core = [p for p in parts if p not in _WPX_DROP_SUFFIXES]
        if not core:
            return None
        if len(core) == 1:
            s = core[0]
        else:
            a, b = core[0], core[1]
            # Regions-Ziffer (z. B. N1UL/3 -> N3, RA0QK/8 -> RA8).
            if b.isdigit():
                m = _LEADING_LETTERS_RE.match(a)
                return (m.group(1) + b) if m else None
            if a.isdigit():
                m = _LEADING_LETTERS_RE.match(b)
                return (m.group(1) + a) if m else None
            # Praefix-Slash: der kuerzere Teil ist der Standort-Praefix
            # (OE/DL6CGU -> OE, SV9/DL1MTB -> SV9). Bei Gleichstand der erste.
            s = a if len(a) <= len(b) else b

    m = _WPX_RE.match(s)
    if m:
        return m.group(1)
    # Praefix-Teil ohne Ziffer (z. B. "OE", "EK") -> WPX-Regel: "0" anhaengen.
    if s.isalpha():
        return s + "0"
    return None


def _is_confirmed(rec: dict) -> bool:
    """QSO per LoTW bestaetigt? (einziges gewertetes Bestaetigungs-Kriterium)."""
    return str(rec.get("LOTW_QSL_RCVD", "")).strip().upper() == "Y"


def _int_or_none(value) -> int | None:
    """ADIF-Feld -> positive Ganzzahl oder None (toleriert '01', ' 14 ', '')."""
    s = str(value).strip()
    if not s.isdigit():
        return None
    n = int(s)
    return n if n > 0 else None


def compute_awards(records) -> dict:
    """Berechnet den Stand aller Diplome aus einer Record-Liste.

    Args:
        records: Iterable von ADIF-Record-dicts (Keys GROSS, z.B. "DXCC").

    Returns:
        dict award_key -> {
            "label": str,            # Anzeigename
            "goal": int,             # Ziel (100/70/300/6/50/40)
            "worked": set,           # gearbeitete Einheiten
            "confirmed": set,        # davon per LoTW bestaetigt (Teilmenge)
        }
        DXCC enthaelt zusaetzlich:
          "tiers", "honor_roll",
          "challenge": set[(entity, band)]      # DXCC-Challenge-Slots (160-6 m)
          "five_band": dict[band -> set(entity)] # fuer 5-Band-DXCC (80..10 m)
    """
    awards = {
        "DXCC": {"label": "DXCC", "goal": 100, "worked": set(), "confirmed": set(),
                 "tiers": DXCC_TIERS, "honor_roll": DXCC_HONOR_ROLL,
                 "challenge": set(), "five_band": {}},
        "WAE": {"label": "WAE", "goal": WAE_GOAL, "worked": set(), "confirmed": set()},
        "WPX": {"label": "WPX", "goal": WPX_GOAL, "worked": set(), "confirmed": set()},
        "WAC": {"label": "WAC", "goal": 6, "worked": set(), "confirmed": set()},
        "WAS": {"label": "WAS", "goal": 50, "worked": set(), "confirmed": set()},
        "WAZ": {"label": "WAZ", "goal": 40, "worked": set(), "confirmed": set()},
    }

    for rec in records:
        if not isinstance(rec, dict):
            continue
        confirmed = _is_confirmed(rec)

        dxcc = _int_or_none(rec.get("DXCC", ""))
        cont = str(rec.get("CONT", "")).strip().upper()
        band = str(rec.get("BAND", "")).strip().upper()

        # DXCC: Entity-Nummer (+ Challenge-Slots + 5-Band-Buckets)
        if dxcc is not None:
            awards["DXCC"]["worked"].add(dxcc)
            if confirmed:
                awards["DXCC"]["confirmed"].add(dxcc)
            if band in CHALLENGE_BANDS:
                awards["DXCC"]["challenge"].add((dxcc, band))
            if band in FIVE_BAND_BANDS:
                awards["DXCC"]["five_band"].setdefault(band, set()).add(dxcc)

            # WAE: europaeische DXCC-Entity (Naeherung)
            if cont == "EU":
                awards["WAE"]["worked"].add(dxcc)
                if confirmed:
                    awards["WAE"]["confirmed"].add(dxcc)

        # WPX: Praefix aus dem Rufzeichen
        pfx = wpx_prefix(str(rec.get("CALL", "")))
        if pfx:
            awards["WPX"]["worked"].add(pfx)
            if confirmed:
                awards["WPX"]["confirmed"].add(pfx)

        # WAC: Kontinent
        if cont in WAC_CONTINENTS:
            awards["WAC"]["worked"].add(cont)
            if confirmed:
                awards["WAC"]["confirmed"].add(cont)

        # WAS: US-Bundesstaat
        state = str(rec.get("STATE", "")).strip().upper()
        if state in US_STATES:
            awards["WAS"]["worked"].add(state)
            if confirmed:
                awards["WAS"]["confirmed"].add(state)

        # WAZ: CQ-Zone 1..40
        cqz = _int_or_none(rec.get("CQZ", ""))
        if cqz is not None and 1 <= cqz <= 40:
            awards["WAZ"]["worked"].add(cqz)
            if confirmed:
                awards["WAZ"]["confirmed"].add(cqz)

    return awards


def dxcc_tier_status(count: int):
    """Hoechste erreichte DXCC-Marke + naechstes Ziel fuer eine Anzahl.

    Returns:
        (current, nxt) mit:
          current: int (erreichte Marke), "Honor Roll", oder None (noch < 100)
          nxt:     int (naechste Marke), "Honor Roll", oder None (alles erreicht)
    """
    if count >= DXCC_HONOR_ROLL:
        return "Honor Roll", None
    reached = [t for t in DXCC_TIERS if count >= t]
    current = reached[-1] if reached else None
    nxt = next((t for t in DXCC_TIERS if count < t), None)
    if nxt is None:
        # alle Marken erreicht, aber noch nicht Honor Roll
        nxt = "Honor Roll"
    return current, nxt


def five_band_status(five_band: dict) -> list:
    """5-Band-DXCC-Status je Band.

    Args:
        five_band: dict band -> set(entity), wie von compute_awards geliefert.

    Returns:
        Liste [(band, count, reached_bool), ...] in FIVE_BAND_BANDS-Reihenfolge.
    """
    out = []
    for b in FIVE_BAND_BANDS:
        n = len(five_band.get(b, ()))
        out.append((b, n, n >= FIVE_BAND_GOAL))
    return out
