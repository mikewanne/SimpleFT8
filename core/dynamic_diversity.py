"""SimpleFT8 DynamicDiversityController — Live-Antennen-Verhaeltnis-Anpassung.

P34 (v0.97.0, 2026-05-11). ENTWEDER-ODER zur statischen DiversityController-
Pipeline:
- Toggle AUS → Statik laeuft, DynamicDiversityController._active=False
- Toggle AN  → Dynamic uebernimmt, Statik-Re-Mess unterdrueckt

Slot-fuer-Slot-Erfassung in 5er-Schiebepuffer pro Antenne. Auswertung nach
jedem Slot (sobald beide Puffer voll, je 5 Werte). Schwelle 8% identisch
zur Statik. Median-basiert (robust gegen Ausreisser).

Lifecycle (verbindlich):
- activate()     → _active=True, 50:50-Reset, Buffer leer, ggf. Statik-Mess abbrechen
- deactivate()   → _active=False, Ratio bleibt, _last_measured_at refresh
- record_slot(ant, score) → in Buffer schieben, ggf. _evaluate()
- reset()        → Buffer leer, Ratio 50:50 (bei Band/Mode/scoring-Wechsel)

Thread-Safety: threading.Lock schuetzt Buffer + Active-Flag. Signal-Emit
mit Qt.QueuedConnection an GUI-Thread.

Verbindliche Spec: prompts/p34_diversity_dynamic_v3.md
"""
from __future__ import annotations

import collections
import logging
import statistics
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from core.diversity import evaluate_ratio  # Modul-Funktion (P34 Helper)
from core.debug_log import debug_log

logger = logging.getLogger(__name__)


class DynamicDiversityController(QObject):
    """Live-Antennen-Verhaeltnis-Anpassung im laufenden Betrieb.

    Signals:
        ratio_changed_dynamic: (new_ratio: str)
            Bei jedem Verhaeltnis-Wechsel via Dynamic-Auswertung. GUI-Slot
            soll via Qt.QueuedConnection verbunden werden.
    """

    BUFFER_SIZE = 5
    THRESHOLD = 0.08
    MIN_PEAK_SCORE = 5.0

    ratio_changed_dynamic = Signal(str)

    def __init__(self, diversity_ctrl):
        super().__init__()
        self._diversity_ctrl = diversity_ctrl
        self._lock = threading.Lock()
        self._buffer = {
            "A1": collections.deque(maxlen=self.BUFFER_SIZE),
            "A2": collections.deque(maxlen=self.BUFFER_SIZE),
        }
        self._active = False
        # P34: scoring_mode-Wechsel → automatisch reset
        diversity_ctrl._scoring_mode_listeners.append(
            lambda mode: self.reset()
        )

    # ── Public API ────────────────────────────────────────────────────

    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        """Toggle AUS→AN: 50:50-Reset, Buffer leer, ggf. Statik-Mess abbrechen.

        AK4: Falls Statik gerade in Phase=measure laeuft, wird sie sofort
        abgebrochen (Phase→operate, _last_measured_at refresh). Mike-Field-
        Erwartung: sofortige Reaktion auf Toggle, keine 60s Wartezeit.

        Hinweis: GUI-Lock-Aufhebung (_set_cq_locked etc) macht der Toggle-
        Handler im main_window — dieser Controller weiss nichts vom GUI.
        """
        with self._lock:
            self._active = True
            self._buffer["A1"].clear()
            self._buffer["A2"].clear()
            self._diversity_ctrl.dynamic_active = True
            # AK4: Statik-Mess-Phase abbrechen
            if self._diversity_ctrl.phase == "measure":
                self._diversity_ctrl._phase = "operate"
                self._diversity_ctrl._last_measured_at = time.time()
                logger.info("[Dynamic] Statik-Mess-Phase abgebrochen "
                            "(Toggle AN waehrend measure)")
                debug_log("DYNAMIC", "Statik-Mess-Phase abgebrochen")
            # 50:50-Reset
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
        logger.info("[Dynamic] Aktiviert (Buffer leer, Ratio 50:50)")
        debug_log("DYNAMIC", "activate -> Buffer leer, Ratio 50:50")

    def deactivate(self) -> None:
        """Toggle AN→AUS: aktuelles Ratio bleibt stehen, _last_measured_at
        refresh.

        AK5 + Mike-B-Option: _last_measured_at = time.time() verhindert
        dass die Statik direkt nach Toggle-AUS in eine sofortige Re-Mess
        rutscht. Das aktuelle (Dynamic-gesetzte) Verhaeltnis ist ja
        vernuenftig — neue 1h-Frist startet jetzt.
        """
        with self._lock:
            self._active = False
            self._diversity_ctrl.dynamic_active = False
            self._diversity_ctrl._last_measured_at = time.time()  # Mike B-Option
            _ratio = self._diversity_ctrl.ratio
        logger.info("[Dynamic] Deaktiviert (Ratio bleibt, Statik-Frist refresht)")
        debug_log("DYNAMIC",
                  f"deactivate -> ratio={_ratio} bleibt, Statik-Frist refresht")

    def reset(self) -> None:
        """Buffer leer + 50:50. Bei Band/Modus/scoring-Wechsel.

        AK10: Wird aus mw_radio.set_band/set_mode + scoring_mode-Callback
        aufgerufen. Auch waehrend Dynamic aktiv ist — Active-Flag bleibt
        wie es ist (kein deactivate).

        AK11: Kein Auto-Reset bei OMNI-CQ, QSO Start/Stop, Toggle AN→AUS.
        """
        with self._lock:
            self._buffer["A1"].clear()
            self._buffer["A2"].clear()
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
        logger.info("[Dynamic] Reset (Buffer leer, Ratio 50:50)")
        debug_log("DYNAMIC", "reset -> Buffer leer, Ratio 50:50")

    def record_slot(self, ant: str, score: float) -> None:
        """Ein Slot-Score in Buffer schieben.

        Aufgerufen aus mw_cycle._on_cycle_decoded (Decoder-Thread).
        Wenn beide Puffer voll: _evaluate_locked() wird inline aufgerufen.

        Args:
            ant: "A1" oder "A2" — aus DiversityController.choose()/Queue
            score: sum(max(0, snr+30)) aus compute_slot_score(messages)

        No-Op wenn:
            - _active=False (Toggle AUS oder Diversity-Aus)
            - ant nicht in ("A1", "A2")
        """
        if not self._active:
            return
        if ant not in ("A1", "A2"):
            return
        with self._lock:
            self._buffer[ant].append(float(score))
            _n1 = len(self._buffer["A1"])
            _n2 = len(self._buffer["A2"])
            debug_log("DYNAMIC",
                      f"record_slot ant={ant} score={score:.1f} "
                      f"buffer A1={_n1}/5 A2={_n2}/5")
            if (_n1 == self.BUFFER_SIZE and _n2 == self.BUFFER_SIZE):
                self._evaluate_locked()

    # ── Internal ──────────────────────────────────────────────────────

    def _evaluate_locked(self) -> None:
        """Auswertung — MUSS unter _lock laufen.

        Liest beide Median-Werte aus dem Buffer, ermittelt neues Ratio via
        evaluate_ratio Helper. Setzt DiversityController.ratio/dominant
        DIREKT (atomar unter Lock) und emittet ratio_changed_dynamic Signal
        wenn sich etwas geaendert hat.
        """
        m1 = statistics.median(self._buffer["A1"])
        m2 = statistics.median(self._buffer["A2"])
        new_ratio, new_dominant = evaluate_ratio(
            m1, m2, threshold=self.THRESHOLD, min_peak=self.MIN_PEAK_SCORE
        )
        old_ratio = self._diversity_ctrl.ratio
        old_dominant = self._diversity_ctrl.dominant
        peak = max(m1, m2)
        diff = abs(m1 - m2) / peak if peak > 0 else 0.0
        # Jede Auswertung loggen — auch wenn kein Wechsel (zur Beobachtung)
        debug_log("DYNAMIC",
                  f"evaluate m1={m1:.1f} m2={m2:.1f} diff={diff * 100:.1f}% "
                  f"-> {new_ratio} (current: {old_ratio})")
        if new_ratio == old_ratio and new_dominant == old_dominant:
            return
        self._diversity_ctrl.ratio = new_ratio
        self._diversity_ctrl.dominant = new_dominant
        logger.info(
            "[Dynamic] Ratio-Wechsel: %s → %s (m1=%.1f m2=%.1f, diff=%.1f%%)",
            old_ratio, new_ratio, m1, m2, diff * 100
        )
        debug_log("DYNAMIC",
                  f"RATIO-WECHSEL {old_ratio} -> {new_ratio} "
                  f"(A1-Buffer={list(self._buffer['A1'])} "
                  f"A2-Buffer={list(self._buffer['A2'])})")
        self.ratio_changed_dynamic.emit(new_ratio)

    # ── Test-Helper (nur Tests, nicht prod) ───────────────────────────

    @property
    def buffer_a1(self):
        """Read-only Zugriff auf A1-Buffer (Tests)."""
        with self._lock:
            return list(self._buffer["A1"])

    @property
    def buffer_a2(self):
        """Read-only Zugriff auf A2-Buffer (Tests)."""
        with self._lock:
            return list(self._buffer["A2"])
