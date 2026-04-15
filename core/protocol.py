"""SimpleFT8 Protocol Profiles — FT8, FT4, FT2 Konstanten.

Alle drei Modi nutzen den gleichen 77-bit Message Codec + LDPC 174/91.
Unterschiede: Timing, Symbole, Sync-Pattern, Bandbreite.

Quellen:
  FT8: kgoba/ft8_lib (MIT), WSJT-X Dokumentation
  FT4: WSJT-X Source (Detector/FtxFt4Decoder.cpp)
  FT2: Decodium (Detector/FtxFt2Stage7.cpp)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolProfile:
    """Konstanten fuer ein FT-Protokoll."""
    name: str               # "FT8", "FT4", "FT2"
    slot_time: float        # Slot-Dauer in Sekunden
    num_symbols: int        # Gesamt-Symbole pro Slot (Daten + Sync)
    num_data: int           # Daten-Symbole
    num_sync: int           # Sync-Symbole
    samples_per_symbol: int # Samples pro Symbol @ 12kHz
    sample_rate: int        # Basis-Samplerate (immer 12000)
    bandwidth_hz: float     # Approximative Bandbreite
    tone_spacing: float     # Abstand zwischen 4-GFSK Toenen (Hz)
    bits: int = 77          # Message Bits (immer 77)
    ldpc_n: int = 174       # LDPC Codeword Laenge (immer 174)
    ldpc_k: int = 91        # LDPC Message Laenge (immer 91)

    @property
    def symbol_duration(self) -> float:
        """Dauer eines Symbols in Sekunden."""
        return self.samples_per_symbol / self.sample_rate

    @property
    def signal_duration(self) -> float:
        """Dauer des Nutzsignals in Sekunden."""
        return self.num_symbols * self.symbol_duration

    @property
    def waveform_samples(self) -> int:
        """Gesamt-Samples des Nutzsignals."""
        return self.num_symbols * self.samples_per_symbol


# ─────────────────────────────────────────────────────────────────────────────
# FT8 — 15s Slots, 79 Symbole, Costas-Sync
# ─────────────────────────────────────────────────────────────────────────────

FT8 = ProtocolProfile(
    name="FT8",
    slot_time=15.0,
    num_symbols=79,         # 58 Daten + 21 Sync (3× Costas-7)
    num_data=58,
    num_sync=21,
    samples_per_symbol=1920,  # 12000 / 6.25 Hz
    sample_rate=12000,
    bandwidth_hz=50.0,      # ~50 Hz pro Signal
    tone_spacing=6.25,      # 4-GFSK Tone Spacing
)
# Verifizierung: 79 × 1920 / 12000 = 12.64s Signaldauer ✓


# ─────────────────────────────────────────────────────────────────────────────
# FT4 — 7.5s Slots, 103 Symbole, anderer Sync
# ─────────────────────────────────────────────────────────────────────────────

FT4 = ProtocolProfile(
    name="FT4",
    slot_time=7.5,
    num_symbols=103,        # 87 Daten + 16 Sync
    num_data=87,
    num_sync=16,
    samples_per_symbol=576, # 12000 / 20.833 Hz
    sample_rate=12000,
    bandwidth_hz=83.3,      # ~83 Hz pro Signal
    tone_spacing=20.833,    # 4-GFSK Tone Spacing (12000/576)
)
# Verifizierung: 103 × 576 / 12000 = 4.944s Signaldauer ✓
# Slot 7.5s - Signal 4.944s = 2.556s Pause


# ─────────────────────────────────────────────────────────────────────────────
# FT2 — 3.8s Slots, 103 Symbole, 16 Sync
# ─────────────────────────────────────────────────────────────────────────────

FT2 = ProtocolProfile(
    name="FT2",
    slot_time=3.8,
    num_symbols=103,        # 87 Daten + 16 Sync (gleich wie FT4!)
    num_data=87,
    num_sync=16,
    samples_per_symbol=288, # 12000 / 41.667 Hz
    sample_rate=12000,
    bandwidth_hz=166.7,     # ~167 Hz pro Signal
    tone_spacing=41.667,    # 4-GFSK Tone Spacing (12000/288)
)
# Verifizierung: 103 × 288 / 12000 = 2.472s Signaldauer ✓
# Slot 3.8s - Signal 2.472s = 1.328s Pause (Async TX Window)


# ─────────────────────────────────────────────────────────────────────────────
# Profil-Zugriff
# ─────────────────────────────────────────────────────────────────────────────

PROFILES = {
    "FT8": FT8,
    "FT4": FT4,
    "FT2": FT2,
}


def get_profile(mode: str) -> ProtocolProfile:
    """Profil fuer einen Modus abrufen."""
    return PROFILES.get(mode.upper(), FT8)


# ─────────────────────────────────────────────────────────────────────────────
# Band-Frequenzen pro Modus
# ─────────────────────────────────────────────────────────────────────────────

# Dial-Frequenzen in MHz (USB)
BAND_FREQUENCIES = {
    "FT8": {
        "160m": 1.840, "80m": 3.573, "60m": 5.357, "40m": 7.074,
        "30m": 10.136, "20m": 14.074, "17m": 18.100, "15m": 21.074,
        "12m": 24.915, "10m": 28.074,
    },
    "FT4": {
        "80m": 3.575, "40m": 7.047, "30m": 10.140, "20m": 14.080,
        "17m": 18.104, "15m": 21.140, "12m": 24.919, "10m": 28.180,
    },
    "FT2": {
        # FT2 Community-Frequenzen (DXZone/Decodium, Stand April 2026)
        "80m": 3.578, "60m": 5.360, "40m": 7.052, "30m": 10.144,
        "20m": 14.084, "17m": 18.108, "15m": 21.144, "12m": 24.923,
        "10m": 28.184,
    },
}
