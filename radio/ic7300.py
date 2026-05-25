"""IC7300Interface — Stub für späteren CI-V + USB-Audio Fork.

Implementiert das RadioInterface-Pattern als Duck-Type (kein Erbe von
RadioInterface, da FlexRadio den gleichen Pattern macht — siehe
P121-Architektur-Klarstellung in TODO.md).

Alle Hardware-Methoden raisen NotImplementedError. Class-Variables sind
gesetzt damit radio_factory + UI-Layer ohne Hardware-Connect arbeiten
können (z.B. radio.radio_name für Dialog-Titel, radio.supports_diversity
für UI-Toggles).

Hardware-Konstanten sind Schätzungen (USB-Audio Latenz, kein VITA-49) —
beim echten Fork zwingend per Messung validieren!
"""

from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal


def _not_implemented(method: str):
    """Hilfs-Funktion für einheitliche NotImplementedError-Meldungen."""
    raise NotImplementedError(
        f"IC-7300 {method}() noch nicht implementiert. "
        "Siehe TODO.md (P121) — Stubs vorhanden, CI-V-Protokoll fehlt."
    )


class IC7300Interface(QObject):
    """Stub-Klasse für IC-7300 CI-V Serial + USB Audio.

    Echte Implementierung folgt in separatem Ticket (CI-V Modell-ID 0x94,
    sounddevice USB Audio, kein Diversity, eine Antennenbuchse).
    """

    # Radio-Identität (Duck-Type-Konvention, NICHT geerbt von ABC)
    radio_type: str = "ic7300"

    # Hardware-Konstanten — SCHÄTZUNGEN. Beim echten Fork validieren:
    # - tx_buffer_s: USB-Audio-Latenz (sounddevice typisch 200-800ms)
    # - rx_hardware_offset_default_s: USB-Audio-Latenz RX-seitig
    tx_buffer_s: float = 0.5
    rx_hardware_offset_default_s: float = 0.10
    tune_power_w: int = 10

    # Signals (API-kompatibel zu FlexRadio damit UI-Layer transparent ist)
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # BEWUSST keine Hardware-Anfassung im Konstruktor!
        # Stub muss instanziierbar sein für UI-Vorbereitung +
        # radio_factory-Tests, ohne Serial-Port oder USB-Audio zu öffnen.
        self.ip = ""           # für Code-Pfade die ip-presence prüfen
        self.last_swr = 1.0    # für Watchdog-kompatible Default-Reads

    # ── Identität & Capabilities ─────────────────────────────────

    @property
    def radio_name(self) -> str:
        return "IC-7300"

    @property
    def supports_diversity(self) -> bool:
        # IC-7300 hat nur 1 Antennenbuchse → niemals Diversity-fähig
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
