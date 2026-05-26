"""SimpleFT8 Message — FT8-Nachrichten parsen und klassifizieren."""

import copy
from dataclasses import dataclass, field


@dataclass
class FT8Message:
    """Eine dekodierte FT8-Nachricht."""
    raw: str                    # Roher Message-String z.B. "CQ DA1MHH JO31"
    field1: str = ""            # Erstes Feld (CQ, Rufzeichen, DE)
    field2: str = ""            # Zweites Feld (Rufzeichen)
    field3: str = ""            # Drittes Feld (Locator, Rapport, RR73, 73)
    snr: int = -30              # Signal-Rausch-Verhältnis in dB
    freq_hz: int = 0            # Audio-Frequenz in Hz
    dt: float = 0.0             # Zeitversatz
    antenna: str = ""           # Diversity: "A1", "A2", "AB" (beide)

    @property
    def is_cq(self) -> bool:
        return self.field1 == "CQ" or self.field1.startswith("CQ ")

    @property
    def is_directed_to(self) -> bool:
        """Ist eine direkte Nachricht an ein bestimmtes Rufzeichen."""
        return not self.is_cq and self.field1 != "DE" and self.field1 != "QRZ"

    @property
    def caller(self) -> str:
        """Rufzeichen des Senders (field2, bei CQ auch field2)."""
        return self.field2

    @property
    def target(self) -> str:
        """Rufzeichen des Empfängers (field1, leer bei CQ)."""
        if self.is_cq:
            return ""
        return self.field1

    @property
    def grid_or_report(self) -> str:
        return self.field3

    @property
    def is_report(self) -> bool:
        """Ist ein Signal-Rapport (z.B. -08, +12, R-08)."""
        f3 = self.field3
        if not f3:
            return False
        if f3.startswith("R"):
            f3 = f3[1:]
        try:
            v = int(f3)
            return -50 <= v <= 50
        except ValueError:
            return False

    @property
    def is_r_report(self) -> bool:
        """R-prefix Report (Bestätigung + SNR) z.B. R-08, R+12."""
        return self.field3.startswith("R") and self.is_report

    @property
    def is_rr73(self) -> bool:
        return self.field3 in ("RR73", "RRR")

    @property
    def is_73(self) -> bool:
        return self.field3 == "73"

    @property
    def is_grid(self) -> bool:
        """Ist ein Maidenhead-Locator (4 Zeichen)."""
        g = self.field3
        if len(g) != 4:
            return False
        return (g[0].isalpha() and g[1].isalpha() and
                g[2].isdigit() and g[3].isdigit())


# PyFT8 gibt bei unbekannten Formaten Fehler-Strings zurueck (z.B. DXpedition-Modus)
# Diese beginnen mit bekannten Fehlerpraefixen oder haben unerwartete Struktur
_PYFT8_ERROR_PREFIXES = (
    "DXpedition",
    "not implemented",
    "Error",
    "Invalid",
    "???",
    "Msg:",
)


def parse_ft8_message(msg_str: str, snr: int = -30,
                       freq_hz: int = 0, dt: float = 0.0) -> FT8Message:
    """Einen dekodierten FT8-String in ein FT8Message-Objekt parsen."""
    parts = msg_str.strip().split()

    # PyFT8 Fehler-Strings abfangen (DXpedition, unbekannte Formate)
    if not parts or any(msg_str.strip().startswith(p) for p in _PYFT8_ERROR_PREFIXES):
        return FT8Message(
            raw=msg_str.strip(), field1="?", field2="?", field3="?",
            snr=snr, freq_hz=freq_hz, dt=dt,
        )

    f1, f2, f3 = "", "", ""
    if len(parts) >= 1:
        f1 = parts[0]
    if len(parts) >= 2:
        f2 = parts[1]
    if len(parts) >= 3:
        f3 = " ".join(parts[2:])

    # CQ mit Richtung (z.B. "CQ DX DA1MHH JO31", "CQ JA HG60IPA")
    # P136 (26.05.2026 Mike-Field-Bug): vorher nur len==4, dadurch wurde
    # "CQ JA HG60IPA" (3 parts, kein Grid) als f1=CQ/f2=JA/f3=HG60IPA
    # geparst → caller=JA → Auto-Hunt rief "JA" an. Mit len>=3 greift
    # Richtungs-Erkennung auch ohne Grid.
    if f1 == "CQ" and len(parts) >= 3 and not looks_like_callsign(f2):
        f1 = f"CQ {f2}"
        f2 = parts[2]
        f3 = parts[3] if len(parts) >= 4 else ""

    return FT8Message(
        raw=msg_str.strip(),
        field1=f1, field2=f2, field3=f3,
        snr=snr, freq_hz=freq_hz, dt=dt,
    )


def looks_like_callsign(s: str) -> bool:
    """Prueft ob ein String wie ein Rufzeichen aussieht.

    Drei Regeln (KISS-Heuristik, alle muessen erfuellt sein):
    - Laenge 3-10 Zeichen
    - mindestens 1 Ziffer
    - mindestens 1 Buchstabe

    Filtert Direction-Marker (JA, EU, NA, DX), Keywords (CQ, TEST,
    QSO, RR73). Laesst Sonderformate wie 1A0KM/4U1UN/R1A0KM durch.

    Slash-Suffixe (DA1MHH/P) müssen vom Aufrufer abgespalten werden —
    diese Funktion erwartet einen reinen Token ohne `/`.
    """
    if len(s) < 3 or len(s) > 10:
        return False
    has_digit = any(c.isdigit() for c in s)
    has_alpha = any(c.isalpha() for c in s)
    return has_digit and has_alpha


# Backward-Compat-Alias fuer interne Caller (kann spaeter entfernt werden).
_looks_like_call = looks_like_callsign
