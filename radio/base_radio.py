"""RadioInterface — Abstract Base Class für alle Radio-Implementierungen.

Ermöglicht zukünftige Forks für andere Geräte (IC-7300, etc.) durch
Austausch des Radio-Moduls ohne Änderungen am Rest der Software.

Implementierungen:
    radio/flexradio.py  → FlexRadioInterface (SmartSDR TCP + VITA-49)
    radio/ic7300.py     → IC7300Interface (CI-V Serial + USB Audio) [ZUKÜNFTIG]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Callable


class RadioInterface(ABC):
    """Minimales Interface für FT8-Radio-Steuerung.

    Alle radio-spezifischen Details (Protokoll, Audio-Transport, Metering)
    sind hinter diesem Interface versteckt. main_window.py verwendet
    ausschließlich diese Methoden.
    """

    # ── Verbindung ─────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> bool:
        """Verbindung zum Radio herstellen.

        Returns:
            True bei Erfolg, False bei Fehler.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Verbindung trennen, Ressourcen freigeben."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True wenn Radio verbunden und bereit."""
        ...

    # ── Frequenz & Mode ────────────────────────────────────────────

    @abstractmethod
    def set_frequency(self, freq_hz: int) -> bool:
        """Empfangs-/Sendefrequenz setzen.

        Args:
            freq_hz: Frequenz in Hz (z.B. 14074000 für 20m FT8)
        Returns:
            True bei Erfolg.
        """
        ...

    @abstractmethod
    def get_frequency(self) -> Optional[int]:
        """Aktuelle Frequenz in Hz, oder None wenn unbekannt."""
        ...

    @abstractmethod
    def set_mode(self, mode: str) -> bool:
        """Betriebsart setzen.

        Args:
            mode: z.B. "DIGU", "USB", "LSB"
        """
        ...

    # ── PTT & Senden ──────────────────────────────────────────────

    @abstractmethod
    def set_ptt(self, active: bool) -> bool:
        """PTT (Push-To-Talk) setzen.

        Args:
            active: True = Senden, False = Empfangen
        """
        ...

    @abstractmethod
    def set_tx_power(self, watts: int) -> bool:
        """Sendeleistung setzen.

        Args:
            watts: Leistung in Watt (1-100)
        """
        ...

    # ── Antennen ──────────────────────────────────────────────────

    @abstractmethod
    def get_antennas(self) -> list[str]:
        """Liste verfügbarer Antennen. z.B. ['ANT1', 'ANT2']"""
        ...

    @abstractmethod
    def set_antenna(self, antenna: str) -> bool:
        """Antenne wählen.

        Args:
            antenna: z.B. 'ANT1', 'ANT2'
        """
        ...

    # ── Audio ─────────────────────────────────────────────────────

    @abstractmethod
    def get_rx_audio_callback(self) -> Optional[Callable]:
        """Callback-Funktion die Audio-Daten liefert.

        Für FlexRadio: liest VITA-49 UDP Pakete
        Für IC-7300: liest sounddevice USB Audio Stream

        Returns:
            Callable das PCM-Daten (numpy array, 12kHz mono) zurückgibt,
            oder None wenn noch kein Stream aktiv.
        """
        ...

    @abstractmethod
    def send_audio(self, pcm_data: bytes) -> bool:
        """Audio-Daten senden (TX).

        Args:
            pcm_data: PCM-Bytes (Format je nach Implementierung)
        """
        ...

    # ── Metering ──────────────────────────────────────────────────

    @abstractmethod
    def get_meter_data(self) -> dict:
        """Aktuelle Messwerte abrufen.

        Returns:
            Dict mit optionalen Keys:
            - 'swr': float — SWR-Wert (1.0 = perfekt)
            - 'fwd_power': float — Vorwärtsleistung in Watt
            - 'alc': float — ALC-Pegel (0-100%)
            - 'mic_level': float — Mikrofon-Pegel (0-100%)
        """
        ...

    # ── Antennen (abstrakt) ────────────────────────────────────────

    @abstractmethod
    def set_rx_antenna(self, ant: str) -> None:
        """RX-Antenne wählen (z.B. 'ANT1', 'ANT2')."""
        ...

    @abstractmethod
    def set_tx_antenna(self, ant: str) -> None:
        """TX-Antenne wählen (z.B. 'ANT1')."""
        ...

    # ── Gain ────────────────────────────────────────────────────

    @abstractmethod
    def set_rfgain(self, gain: int) -> None:
        """RF-Gain auf Primary Receiver setzen (0-30 dB)."""
        ...

    def set_rfgain_secondary(self, gain: int) -> None:
        """RF-Gain auf Secondary Receiver setzen (Diversity B).

        Default: No-op. Nur Radios mit 2 Empfängern überschreiben das.
        """
        pass

    def has_secondary_slice(self) -> bool:
        """True wenn 2. Empfangskanal für Diversity vorhanden."""
        return False

    # ── Power (direkt) ──────────────────────────────────────────

    def set_rfpower_direct(self, value: int) -> None:
        """RF-Power direkt setzen (ohne Safety-Checks wie max_power_level)."""
        self.set_tx_power(value)

    # ── TX-Level Properties ─────────────────────────────────────

    @property
    def last_swr(self) -> float:
        """Letzter SWR-Messwert (1.0 = perfekt)."""
        return 1.0

    @property
    def tx_raw_peak(self) -> float:
        """Audio-Peak VOR Gain (0.0-1.0) — für Clipschutz."""
        return 0.0

    @property
    def tx_audio_level(self) -> float:
        """Aktueller TX-Audiopegel (0.0-1.0)."""
        return 1.0

    @tx_audio_level.setter
    def tx_audio_level(self, value: float) -> None:
        """TX-Audiopegel setzen."""
        pass

    # ── Preamp / Gain ─────────────────────────────────────────────

    def set_preamp(self, level: int) -> bool:
        """Vorverstärker setzen (optional — nicht alle Radios haben das).

        Args:
            level: Verstärkung in dB (0, 10, 20 etc.)
        Returns:
            True wenn unterstützt und gesetzt, False wenn nicht verfügbar.
        """
        return False  # Default: nicht unterstützt

    # ── Radio-Info ────────────────────────────────────────────────

    @property
    def radio_name(self) -> str:
        """Lesbarer Name des Radios (für UI-Anzeige)."""
        return self.__class__.__name__

    @property
    def supports_diversity(self) -> bool:
        """True wenn Radio 2 Antennenanschlüsse für Diversity hat."""
        return len(self.get_antennas()) >= 2
