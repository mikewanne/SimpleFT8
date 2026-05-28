"""FakeRadio — Sim-Implementierung der Radio-Oberflaeche fuer Tests ohne Hardware.

P64 (v0.98.38, 28.05.2026): Laesst SimpleFT8 OHNE echtes FlexRadio starten.
Duck-typing-kompatibel zur FlexRadio-Oberflaeche (QObject + 8 Signals + die
~34 Member die der App-Code nutzt). Liefert KEINE echten Audio-Daten — die
Fake-Decodes (CQ-Stationen, Report-Wechsel) kommen vom `SimInjector`
(core/sim_injector.py), der die Decoder-Signals direkt feuert.

**Aktivierung:** Env-Var `SIMPLEFT8_FAKE_RADIO=1` (in radio_factory). Kein UI,
kein persistentes Setting — reines Dev-/Test-Werkzeug.

**Nebennutzen:** Konformitaets-Check fuer die RadioInterface-Abstraktion vor
dem geplanten Icom-Fork. Jede Methode die der App-Code auf `self.radio`
aufruft MUSS hier existieren — fehlt eine, crasht der Sim-Start und legt das
FlexRadio-Leck offen.

DeepSeek-R1 (V4-pro): GO, 0 Blocker. ip="SIM" (non-empty → App-Gates
`if self.radio.ip:` behandeln als connected); get_frequency Default > 0;
explizite Member (kein __getattr__-Masking).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class FakeRadio(QObject):
    """Fake-Radio fuer Sim-Modus — alle Methoden no-op/store, nie Hardware."""

    # ── Signals (identisch zu FlexRadio) ───────────────────────────
    connected = Signal()
    disconnected = Signal()
    frequency_changed = Signal(float)
    audio_received = Signal(object)
    meter_update = Signal(str, float)   # (name, value) — FWDPWR/SWR/ALC
    swr_alarm = Signal(float)
    dx_tune_progress = Signal(str)
    error = Signal(str)

    # ── Hardware-Konstanten (P121-Pattern, Duck-typing) ────────────
    radio_type = "fake"
    tx_buffer_s = 1.3
    rx_hardware_offset_default_s = 0.26
    tune_power_w = 10

    def __init__(self, freq_hz: int = 14_074_000):
        super().__init__()
        self._connected = False
        self._freq_hz = freq_hz
        self._sim_swr = 1.0
        self._tx_audio_level = 1.0
        self._rx_ant = "ANT1"
        self._tx_ant = "ANT1"
        # Vom Decoder gesetzt (mw_radio: radio.on_audio_callback =
        # decoder.feed_audio) — wird hier NIE gerufen (kein Audio im Sim).
        self.on_audio_callback = None

    # ── Verbindung ─────────────────────────────────────────────────
    @property
    def ip(self) -> str:
        # Non-empty → die ~45 App-Gates `if self.radio.ip:` behandeln den
        # Sim als verbunden (R1-bestaetigt KISS, kein Patch der Call-Sites).
        return "SIM"

    def connect(self) -> bool:
        self._connected = True
        self.connected.emit()
        return True

    def auto_connect(self, max_retries: int = 10, retry_delay: float = 3.0,
                     on_attempt=None, **kwargs) -> bool:
        # Signatur identisch zum echten auto_connect (mw_radio ruft mit
        # max_retries/retry_delay/on_attempt). connected erst nach Event-
        # Loop-Start emittieren, damit alle Handler verdrahtet sind.
        QTimer.singleShot(0, self._do_connect)
        return True

    def _do_connect(self) -> None:
        self._connected = True
        self.connected.emit()

    def reconnect_forever(self, on_waiting=None, **kwargs) -> bool:
        QTimer.singleShot(0, self._do_connect)
        return True

    def abort_connect(self) -> None:
        pass

    def abort_reconnect(self) -> None:
        pass

    def disconnect(self) -> None:
        self._connected = False
        self.disconnected.emit()

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Frequenz & Mode ────────────────────────────────────────────
    def set_frequency(self, freq) -> bool:
        # Final-R1-Fix: Einheit normalisieren. App ruft mit MHz (TUNE,
        # z.B. 14.074) ODER Hz (z.B. 14074000). Intern IMMER Hz fuehren,
        # damit get_frequency() konsistent Hz liefert (wie das echte Radio).
        # Schwelle 100 kHz trennt eindeutig (FT8-Baender 1.8-50 MHz vs
        # MHz-Werte < 100).
        try:
            self._freq_hz = int(freq * 1_000_000) if freq < 100_000 else int(freq)
        except (TypeError, ValueError):
            pass  # ungueltiger Wert → alten behalten (Sim, nie kritisch)
        self.frequency_changed.emit(float(self._freq_hz))
        return True

    def get_frequency(self):
        # R1-Hinweis: Default > 0 (Band-Erkennung/Karte/PSK erwarten numerisch Hz).
        return self._freq_hz or 14_074_000

    def set_mode(self, mode: str) -> bool:
        return True

    def set_rx_filter(self, lo_hz: int, hi_hz: int) -> None:
        pass

    def apply_ft8_preset(self, *args, **kwargs) -> None:
        pass

    # ── PTT & Senden ───────────────────────────────────────────────
    def set_ptt(self, active: bool) -> bool:
        return True

    def ptt_off(self) -> None:
        pass

    def set_tx_power(self, watts: int) -> bool:
        return True

    def set_power(self, watts: int) -> bool:
        return True

    def set_rfpower_direct(self, value: int) -> None:
        pass

    def set_tx_level(self, level: float) -> None:
        self._tx_audio_level = level

    def create_tx_stream(self) -> None:
        pass

    def send_audio(self, pcm_data: bytes) -> bool:
        return True

    # ── TUNE ───────────────────────────────────────────────────────
    def tune_on(self) -> None:
        pass

    def tune_off(self) -> None:
        pass

    # ── Antennen ───────────────────────────────────────────────────
    def get_antennas(self) -> list[str]:
        # 2 Antennen → supports_diversity=True → Diversity-Anzeige testbar.
        return ["ANT1", "ANT2"]

    def set_antenna(self, antenna: str) -> bool:
        return True

    def set_rx_antenna(self, ant: str) -> None:
        self._rx_ant = ant

    def set_tx_antenna(self, ant: str) -> None:
        self._tx_ant = ant

    # ── Gain ───────────────────────────────────────────────────────
    def set_rfgain(self, gain: int) -> None:
        pass

    def set_rfgain_secondary(self, gain: int) -> None:
        pass

    def has_secondary_slice(self) -> bool:
        return True

    # ── Metering / SWR ─────────────────────────────────────────────
    def set_swr_limit(self, value: float) -> None:
        pass

    def set_sim_swr(self, value: float) -> None:
        """Sim-Helper: SWR-Wert setzen (vom SimInjector / Tests genutzt)."""
        self._sim_swr = value

    @property
    def last_swr(self) -> float:
        return self._sim_swr

    def get_meter_data(self) -> dict:
        return {"swr": self._sim_swr, "fwd_power": 0.0, "alc": 0.0,
                "mic_level": 0.0}

    @property
    def tx_raw_peak(self) -> float:
        return 0.0

    @property
    def tx_audio_level(self) -> float:
        return self._tx_audio_level

    @tx_audio_level.setter
    def tx_audio_level(self, value: float) -> None:
        self._tx_audio_level = value

    def get_rx_audio_callback(self):
        return None

    # ── Radio-Info ─────────────────────────────────────────────────
    @property
    def radio_name(self) -> str:
        return "FakeRadio (Sim)"

    @property
    def supports_diversity(self) -> bool:
        return len(self.get_antennas()) >= 2
