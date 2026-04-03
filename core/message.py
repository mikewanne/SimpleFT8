"""SimpleFT8 Message — FT8-Nachrichten parsen und klassifizieren."""

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
        """Rufzeichen des Senders."""
        if self.is_cq:
            return self.field2
        return self.field1

    @property
    def target(self) -> str:
        """Rufzeichen des Empfängers (leer bei CQ)."""
        if self.is_cq:
            return ""
        return self.field2

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

    # CQ mit Richtung (z.B. "CQ DX DA1MHH JO31")
    if f1 == "CQ" and len(parts) == 4 and not _looks_like_call(f2):
        f1 = f"CQ {f2}"
        f2 = parts[2]
        f3 = parts[3]

    return FT8Message(
        raw=msg_str.strip(),
        field1=f1, field2=f2, field3=f3,
        snr=snr, freq_hz=freq_hz, dt=dt,
    )


def _looks_like_call(s: str) -> bool:
    """Prüft ob ein String wie ein Rufzeichen aussieht."""
    if len(s) < 3 or len(s) > 10:
        return False
    has_digit = any(c.isdigit() for c in s)
    has_alpha = any(c.isalpha() for c in s)
    return has_digit and has_alpha
