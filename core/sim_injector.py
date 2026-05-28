"""SimInjector — speist Fake-Decodes in die Decoder-Signal-Kette (P64).

Teil des Sim-Modus (siehe radio/fake_radio.py). Auf einem Slot-Timer baut der
Injector realistische Fake-FT8Messages (CQ-Rufe + Inter-Stations-Wechsel,
SNR variiert inkl. schwache ≤ -24 dB) und feuert sie ueber die DECODER-
Signals in EXAKTER Reihenfolge (wie der echte Decoder, CLAUDE.md):

    cycle_decoded(messages) → pro msg message_decoded(msg) → cycle_finished()

... so dass die App (mw_cycle._on_cycle_decoded etc.) sie wie echte Decodes
verarbeitet. KEIN echtes Audio — der Decoder-Thread laeuft im Sim-Modus
gar nicht (mw_radio gated `decoder.start()`).

DeepSeek-R1 (V4-pro): direkte Emission der Decoder-Signals ist fuer ein
Test-Tool KISS-konform (kein Wiring-Umbau). Threading: QTimer laeuft im
GUI-Thread → DirectConnection-Emit, sequenziell, Reihenfolge bleibt erhalten
(echter Decoder feuert die 3 Signale ebenfalls unmittelbar hintereinander).

**GRENZEN V1** (Final-R1, dokumentiert — kein Bug):
- nur Ambient-Traffic (CQ + Fremd-Wechsel). Eine vom User/Auto-Hunt
  angerufene Station ANTWORTET (noch) nicht interaktiv — braucht qso_sm-
  Kopplung (TODO P64-B). Auto-Hunt-PICK + Anruf-Logik sind aber testbar.
- Diversity-MESSUNG nicht simuliert (braucht dual-stream = Variante C).
  Die Anzeige rendert; die Kalibrierung/Messung nicht.
- Slot-Intervall wird bei `start()` fixiert (FT8 15s). Ein FT-Modus-Wechsel
  WAEHREND der Sim laeuft aendert das Intervall nicht (Test-Tool-Edge,
  Neustart der Sim genuegt).
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import QObject, Qt, QTimer

from core.message import FT8Message

# (call, grid, base_snr) — Mix DX + EU; einige schwach (≤ -24 dB) als
# Weak-Decode-Test (zeigt P150/P152 im Sim).
_STATIONS = [
    ("OH3OJ", "KP20", -8), ("RU3X", "KO85", -11), ("YO9IAB", "KN34", -15),
    ("SP9MOC", "JO90", -13), ("EA7GUL", "IM86", -18), ("G3UAS", "IO91", -6),
    ("TI5RTZ", "EK70", -25), ("VK6AS", "OF77", -26), ("5Z4VJ", "KI88", -24),
    ("9Y4DG", "FK90", -25), ("OA4ENG", "FH17", -24), ("CE1KR", "FF46", -25),
    ("W9KEY", "EN63", -22), ("RN6LBT", "LN17", -23), ("UT7UJ", "KO50", -19),
]

_SLOT_S = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}


class SimInjector(QObject):
    """Feuert pro Slot Fake-Decodes ueber die Decoder-Signals."""

    def __init__(self, decoder, radio, my_call: str = "DA1MHH"):
        super().__init__()
        self._decoder = decoder
        self._radio = radio
        self._my_call = my_call  # reserviert fuer P64-B (interaktiver Responder)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._emit_slot)
        self._running = False

    def _slot_s(self) -> float:
        return _SLOT_S.get(getattr(self._decoder, "_mode", "FT8"), 15.0)

    def start(self) -> None:
        if self._running:
            return  # idempotent (connected-Signal kann mehrfach feuern)
        self._running = True
        self._timer.start(int(self._slot_s() * 1000))
        # Erster Slot sofort, damit die RX-Liste nicht einen vollen Slot leer bleibt.
        QTimer.singleShot(500, self._emit_slot)

    def stop(self) -> None:
        self._running = False
        self._timer.stop()

    def _emit_slot(self) -> None:
        if not self._running:
            return
        slot = self._slot_s()
        now = time.time()
        slot_start = now - (now % slot)
        # Parity wie der echte Decoder (decoder.py): int(slot_start/slot)%2==0
        tx_even = int(slot_start / slot) % 2 == 0
        msgs = self._build_messages(tx_even, slot_start)
        # Reihenfolge EXAKT wie der echte Decoder (NICHT aendern, CLAUDE.md).
        self._decoder.cycle_decoded.emit(msgs)
        for m in msgs:
            self._decoder.message_decoded.emit(m)
        self._decoder.cycle_finished.emit()

    def _build_messages(self, tx_even: bool, slot_start: float) -> list[FT8Message]:
        """Rotierende Teilmenge (6-9 Stationen), SNR-Jitter, zufaellige
        Audio-Frequenz. Mix aus CQ-Rufen und Fremd-Wechseln."""
        k = random.randint(6, 9)
        chosen = random.sample(_STATIONS, k)
        msgs: list[FT8Message] = []
        for call, grid, base in chosen:
            snr = base + random.randint(-2, 2)
            freq = random.randint(300, 2600)
            if random.random() < 0.55:
                # CQ-Ruf → Auto-Hunt-Kandidat
                m = FT8Message(raw=f"CQ {call} {grid}", field1="CQ",
                               field2=call, field3=grid, snr=snr, freq_hz=freq)
            else:
                # Fremd-Wechsel (Report an andere Station)
                other = random.choice(_STATIONS)[0]
                m = FT8Message(raw=f"{other} {call} {snr:+03d}", field1=other,
                               field2=call, field3=f"{snr:+03d}",
                               snr=snr, freq_hz=freq)
            # Dynamisch attachierte Felder die der echte Decoder auch setzt.
            m._tx_even = tx_even
            m._slot_start_ts = slot_start
            m.antenna = "A1"
            msgs.append(m)
        return msgs
