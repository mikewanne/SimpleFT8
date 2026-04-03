"""SimpleFT8 Diversity Merger — Fusioniert Dekodier-Ergebnisse von 2 Antennen.

Wartet auf beide Decoder (oder Timeout 1.5s), dann:
- Union aller Stationen
- Bei Duplikaten: staerkeren SNR behalten
- Markiert Quelle: 'A1', 'A2', 'AB' (beide)
"""

from PySide6.QtCore import QObject, Signal, QTimer


class DiversityMerger(QObject):
    """Fusioniert FT8-Dekodierungen von zwei Antennen/Decodern.

    Signals:
        merged_decoded: (list[FT8Message]) — Fusionierte Ergebnisse
    """

    merged_decoded = Signal(list)

    def __init__(self, timeout_sec: float = 1.5, parent=None):
        super().__init__(parent)
        self._timeout = timeout_sec
        self._results_a = None
        self._results_b = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_merge)

    def on_decoder_a_done(self, messages: list):
        """Decoder A (ANT1) hat einen Zyklus fertig."""
        self._results_a = messages or []
        if self._results_b is not None:
            self._timer.stop()
            self._do_merge()
        elif not self._timer.isActive():
            self._timer.start(int(self._timeout * 1000))

    def on_decoder_b_done(self, messages: list):
        """Decoder B (ANT2) hat einen Zyklus fertig."""
        self._results_b = messages or []
        if self._results_a is not None:
            self._timer.stop()
            self._do_merge()
        elif not self._timer.isActive():
            self._timer.start(int(self._timeout * 1000))

    def _do_merge(self):
        """Ergebnisse fusionieren und emittieren."""
        self._timer.stop()
        a_msgs = self._results_a or []
        b_msgs = self._results_b or []
        self._results_a = None
        self._results_b = None

        # Zusammenfuehren: Key = normalisierter Raw-Text
        merged = {}

        for msg in a_msgs:
            key = " ".join(msg.raw.split())
            msg.antenna = "A1"
            msg._snr_a1 = msg.snr
            msg._snr_a2 = None
            merged[key] = msg

        for msg in b_msgs:
            key = " ".join(msg.raw.split())
            if key in merged:
                # Duplikat: staerkeren SNR behalten, Gewinner markieren
                existing = merged[key]
                existing._snr_a2 = msg.snr
                if msg.snr > existing.snr:
                    # ANT2 war staerker → SNR von A2 nehmen
                    msg._snr_a1 = existing._snr_a1
                    msg._snr_a2 = msg.snr
                    msg.antenna = "A2>1"
                    merged[key] = msg
                else:
                    existing.antenna = "A1>2"
            else:
                msg.antenna = "A2"
                msg._snr_a1 = None
                msg._snr_a2 = msg.snr
                merged[key] = msg

        result = list(merged.values())
        if result:
            self.merged_decoded.emit(result)

    def reset(self):
        """Zustand zuruecksetzen (bei Bandwechsel etc.)."""
        self._timer.stop()
        self._results_a = None
        self._results_b = None
