"""SimpleFT8 Timing — UTC-Takt und Fenster-Synchronisation."""

import time
import threading
from PySide6.QtCore import QObject, Signal


class FT8Timer(QObject):
    """Verwaltet FT8/FT4 Timing-Zyklen.

    Signals:
        cycle_tick: Emitted jede 100ms mit (seconds_in_cycle, cycle_duration)
        cycle_start: Emitted am Anfang eines neuen Zyklus mit (cycle_number, is_even)
        tx_window: Emitted wenn TX-Fenster beginnt
    """

    cycle_tick = Signal(float, float)   # (seconds_in_cycle, cycle_duration)
    cycle_start = Signal(int, bool)     # (cycle_number, is_even)
    tx_window = Signal()

    # Zyklusdauer pro Modus
    CYCLE_DURATIONS = {
        "FT8": 15.0,
        "FT4": 7.5,
        "FT2": 3.75,
    }

    def __init__(self, mode: str = "FT8"):
        super().__init__()
        self.mode = mode
        self.cycle_duration = self.CYCLE_DURATIONS[mode]
        self._running = False
        self._thread = None
        self._cycle_count = 0
        self._ntp_offset = 0.0  # Offset zu System-Clock

    def set_mode(self, mode: str):
        self.mode = mode
        self.cycle_duration = self.CYCLE_DURATIONS[mode]

    def utc_now(self) -> float:
        """Aktuelle UTC-Zeit mit NTP-Korrektur."""
        return time.time() + self._ntp_offset

    def seconds_in_cycle(self) -> float:
        """Sekunden seit Beginn des aktuellen Zyklus."""
        return self.utc_now() % self.cycle_duration

    def seconds_until_next_cycle(self) -> float:
        """Sekunden bis zum nächsten Zyklus-Start."""
        return self.cycle_duration - self.seconds_in_cycle()

    def current_cycle_number(self) -> int:
        """Aktueller Zyklus seit Epoch."""
        return int(self.utc_now() / self.cycle_duration)

    def is_even_cycle(self) -> bool:
        return self.current_cycle_number() % 2 == 0

    def sync_ntp(self):
        """NTP-Offset berechnen (optional, macOS synced automatisch)."""
        try:
            import ntplib
            client = ntplib.NTPClient()
            response = client.request("pool.ntp.org", version=3)
            self._ntp_offset = response.offset
        except Exception:
            self._ntp_offset = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _tick_loop(self):
        last_cycle = -1
        while self._running:
            now = self.utc_now()
            sic = now % self.cycle_duration
            cycle_num = int(now / self.cycle_duration)

            if cycle_num != last_cycle:
                last_cycle = cycle_num
                self._cycle_count += 1
                is_even = cycle_num % 2 == 0
                self.cycle_start.emit(self._cycle_count, is_even)

            self.cycle_tick.emit(sic, self.cycle_duration)
            time.sleep(0.1)
