"""IC7100Interface — Stub für späteren CI-V + USB-Audio Fork.

Implementiert das RadioInterface-Pattern als Duck-Type (analog
IC7300Interface). Beim echten Fork wird sich zeigen ob 7300 + 7100
eine gemeinsame Helper-Basis bekommen — bewusst noch nicht jetzt
(KISS, kein premature DRY).

Hardware-Konstanten sind Schätzungen — beim echten Fork zwingend per
Messung validieren!
"""

from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal


def _not_implemented(method: str):
    """Hilfs-Funktion für einheitliche NotImplementedError-Meldungen."""
    raise NotImplementedError(
        f"IC-7100 {method}() noch nicht implementiert. "
        "Siehe TODO.md (P121) — Stubs vorhanden, CI-V-Protokoll fehlt."
    )


class IC7100Interface(QObject):
    """Stub-Klasse für IC-7100 CI-V Serial + USB Audio.

    Echte Implementierung folgt in separatem Ticket (CI-V Modell-ID 0x88,
    sounddevice USB Audio, kein Diversity, eine Antennenbuchse pro Modul,
    All-Mode KW+VHF+UHF).
    """

    # Radio-Identität
    radio_type: str = "ic7100"

    # Hardware-Konstanten — SCHÄTZUNGEN. Beim echten Fork validieren.
    tx_buffer_s: float = 0.5
    rx_hardware_offset_default_s: float = 0.10
    tune_power_w: int = 10

    # Signals (API-kompatibel)
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # BEWUSST keine Hardware-Anfassung im Konstruktor!
        self.ip = ""
        self.last_swr = 1.0

    # ── Identität & Capabilities ─────────────────────────────────

    @property
    def radio_name(self) -> str:
        return "IC-7100"

    @property
    def supports_diversity(self) -> bool:
        return False

    def get_antennas(self) -> list[str]:
        return ["ANT1"]

    # ── Stubs für alle Hardware-Methoden ─────────────────────────

    def connect(self) -> bool:                            _not_implemented("connect")
    def disconnect(self) -> None:                         _not_implemented("disconnect")

    @property
    def is_connected(self) -> bool:
        return False

    def set_frequency(self, freq_hz: int) -> bool:        _not_implemented("set_frequency")
    def get_frequency(self) -> Optional[int]:             _not_implemented("get_frequency")
    def set_mode(self, mode: str) -> bool:                _not_implemented("set_mode")
    def set_ptt(self, active: bool) -> bool:              _not_implemented("set_ptt")
    def set_tx_power(self, watts: int) -> bool:           _not_implemented("set_tx_power")
    def set_antenna(self, antenna: str) -> bool:          _not_implemented("set_antenna")
    def get_rx_audio_callback(self) -> Optional[Callable]: _not_implemented("get_rx_audio_callback")
    def send_audio(self, pcm_data: bytes) -> bool:        _not_implemented("send_audio")
    def get_meter_data(self) -> dict:                     _not_implemented("get_meter_data")
    def set_rx_antenna(self, ant: str) -> None:           _not_implemented("set_rx_antenna")
    def set_tx_antenna(self, ant: str) -> None:           _not_implemented("set_tx_antenna")
    def set_rfgain(self, gain: int) -> None:              _not_implemented("set_rfgain")
