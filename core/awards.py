"""SimpleFT8 — Diplome / Awards-Berechnung aus QSO-Records.

Reines Berechnungsmodul (KEINE UI, keine I/O). Bekommt eine Liste von
ADIF-Records (dicts mit GROSS-geschriebenen Keys, wie `log.adif.parse_adif_file`
sie liefert) und ermittelt pro Diplom die Menge der gearbeiteten und der
(per LoTW) bestaetigten Einheiten.

Hobby-Tool-Philosophie (KISS): nur die vier klassischen, aus den vorhandenen
QRZ-ADIF-Feldern direkt ableitbaren Diplome — DXCC, WAC, WAS, WAZ. Kein
DLD/IOTA (Quellfelder zu lueckenhaft), kein Band-/Mode-Split.

Datenquelle der reichhaltigen Felder (DXCC/CONT/STATE/CQZ/LOTW_QSL_RCVD) ist
der QRZ-Export (`adif/_backup_qrz_export/`). Beide eigenen Rufzeichen
(DA1MHH + DO4MHH) fließen in EINEN gemeinsamen Pool — set-basiert, also
automatisch dedupliziert.

Bestaetigt = ausschliesslich `LOTW_QSL_RCVD == "Y"` (international anerkannt;
QRZ-interner Status `APP_QRZLOG_STATUS=C` wird bewusst NICHT als Bestaetigung
gewertet, da kein Diplom-Programm ihn anerkennt).
"""

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

# Reihenfolge fuer eine stabile Anzeige im Dialog.
AWARD_ORDER = ("DXCC", "WAC", "WAS", "WAZ")

# Klartext-Beschreibung je Diplom (fuer den Dialog / Tooltips).
AWARD_INFO = {
    "DXCC": "DX Century Club (ARRL) — 100 DXCC-Gebiete (Entities).",
    "WAC": "Worked All Continents (IARU) — alle 6 Kontinente.",
    "WAS": "Worked All States (ARRL) — alle 50 US-Bundesstaaten.",
    "WAZ": "Worked All Zones (CQ) — alle 40 CQ-Zonen.",
}


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
    """Berechnet den Stand aller vier Diplome aus einer Record-Liste.

    Args:
        records: Iterable von ADIF-Record-dicts (Keys GROSS, z.B. "DXCC").

    Returns:
        dict award_key -> {
            "label": str,            # Anzeigename
            "goal": int,             # Ziel (100/6/50/40)
            "worked": set,           # gearbeitete Einheiten
            "confirmed": set,        # davon per LoTW bestaetigt (Teilmenge)
        }
        DXCC enthaelt zusaetzlich "tiers" (Marken) und "honor_roll".
    """
    awards = {
        "DXCC": {"label": "DXCC", "goal": 100, "worked": set(), "confirmed": set(),
                 "tiers": DXCC_TIERS, "honor_roll": DXCC_HONOR_ROLL},
        "WAC": {"label": "WAC", "goal": 6, "worked": set(), "confirmed": set()},
        "WAS": {"label": "WAS", "goal": 50, "worked": set(), "confirmed": set()},
        "WAZ": {"label": "WAZ", "goal": 40, "worked": set(), "confirmed": set()},
    }

    for rec in records:
        if not isinstance(rec, dict):
            continue
        confirmed = _is_confirmed(rec)

        # DXCC: Entity-Nummer
        dxcc = _int_or_none(rec.get("DXCC", ""))
        if dxcc is not None:
            awards["DXCC"]["worked"].add(dxcc)
            if confirmed:
                awards["DXCC"]["confirmed"].add(dxcc)

        # WAC: Kontinent
        cont = str(rec.get("CONT", "")).strip().upper()
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
