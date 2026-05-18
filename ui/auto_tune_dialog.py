"""P54 (v0.97.44) — AutoTuneDialog: Modal-Dialog während Auto-TUNE.

WindowModal, blockt Bandwechsel-Logik bis TUNE fertig (oder Cancel/
Timeout). Wird vom Helper `_start_auto_tune_for_band_change` (mw_tx.py)
gestartet, empfängt das Signal `auto_tune_done(bool, float, float)`
und entscheidet accept()/reject().

P71 (v0.97.47):
- Backup-Grace `_BACKUP_GRACE_S = 12` s (Phase B max 6.5 + Post-Check 2
  + Safety 3.5). Vorher 5 s → Race mit erfolgreichem TUNE bei langsamer
  Convergenz (Mike-Field-Test 18.05.).
- Title `band.lower() + mode` statt `band.upper()` (Mike: "15M" sah aus
  wie 15 Minuten).
- Status zeigt zusätzlich Mode + Live-FWDPWR.
- DONE FAIL-Logging bei Cancel/Timeout für grep-Diagnose.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


# P71 (v0.97.47): Konstante mit Begründung statt magic number.
# Phase B max 6.5 s (1.5 s initial + 5×1.0 s iter)
# Post-Check delay 2.0 s
# Safety buffer 3.5 s (Display-Delay + Qt-Loop slack)
_BACKUP_GRACE_S = 12


_STYLE = """
QDialog {
    background-color: #16192b;
    border: 1px solid #2a2f4a;
}
QLabel {
    color: #CCC;
    font-family: Menlo, monospace;
}
QPushButton {
    background-color: #2a2f4a;
    color: #CCC;
    border: 1px solid #444;
    padding: 4px 12px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #3a3f5a;
}
QProgressBar {
    border: 1px solid #333;
    border-radius: 2px;
    background: #1a1a1a;
    text-align: center;
    color: #CCC;
    height: 14px;
}
QProgressBar::chunk {
    background: #00CCFF;
    border-radius: 1px;
}
"""


class AutoTuneDialog(QDialog):
    """Modaler Dialog während Auto-TUNE nach Bandwechsel.

    Wird vom Helper geöffnet, blockt mit `exec()`. Schließt sich
    automatisch bei `auto_tune_done`-Signal aus `_tune_post_swr_check`,
    oder per Cancel-Button (User), oder per Backup-Timeout.
    """

    # Wird extern emittiert wenn TUNE fertig (success, swr, avg_fwdpwr).
    auto_tune_done = Signal(bool, float, float)

    def __init__(self, parent, band: str, duration_s: int = 15, mode: str = "FT8"):
        super().__init__(parent)
        self._parent = parent
        self._band = band
        self._duration_s = duration_s
        self._mode = mode
        self._elapsed_s = 0

        self.setWindowTitle("Auto-TUNE")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(420, 140)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Titel — P71: band.lower() + mode statt band.upper()
        self._title_label = QLabel(
            f"🔧 Auto-TUNE läuft — {band.lower()} {mode}")
        self._title_label.setStyleSheet("color: #7CC; font-size: 14px; font-weight: bold;")
        layout.addWidget(self._title_label)

        # Spinner (indeterminate progress bar)
        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)  # indeterminate
        self._spinner.setTextVisible(False)
        self._spinner.setFixedHeight(14)
        layout.addWidget(self._spinner)

        # Status — P71: erweitert um Mode + Live-FWDPWR
        self._status_label = QLabel(
            f"ANT1, 10W → {mode} — 0 / {duration_s} s")
        self._status_label.setStyleSheet("color: #AAA; font-size: 11px;")
        layout.addWidget(self._status_label)

        # Cancel-Button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Abbrechen")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        # Tick-Timer fuer Status-Update
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)

        # Backup-Timeout (R1-F4) — P71: Grace 5 → 12 s gegen Phase-B-Race
        self._backup_timer = QTimer(self)
        self._backup_timer.setSingleShot(True)
        self._backup_timer.timeout.connect(self._on_backup_timeout)
        self._backup_timer.start((duration_s + _BACKUP_GRACE_S) * 1000)

        # Result-Signal an internen Slot
        self.auto_tune_done.connect(self._on_auto_tune_done)

    def _on_tick(self):
        """1 s — Restzeit-Anzeige. P71: erweitert um Mode + Live-FWDPWR."""
        self._elapsed_s += 1
        try:
            swr = float(self._parent.radio.last_swr)
        except (AttributeError, TypeError, ValueError):
            swr = 0.0
        try:
            fwdpwr = float(self._parent._fwdpwr_samples[-1])
        except (AttributeError, IndexError, TypeError, ValueError):
            fwdpwr = 0.0
        self._status_label.setText(
            f"ANT1, 10W → {self._mode} — {self._elapsed_s} / "
            f"{self._duration_s} s · SWR {swr:.1f} · FWDPWR {fwdpwr:.1f}W"
        )

    def _on_auto_tune_done(self, success: bool, swr: float, avg_fwdpwr: float):
        """Slot fuer auto_tune_done-Signal aus _tune_post_swr_check."""
        self._tick_timer.stop()
        self._backup_timer.stop()
        if success:
            self._status_label.setText(
                f"✓ TUNE OK — SWR {swr:.1f} · FWDPWR {avg_fwdpwr:.1f} W"
            )
            QTimer.singleShot(800, self.accept)
        else:
            if swr > 0:
                msg = f"⚠ TUNE fehlgeschlagen — SWR {swr:.1f}"
            else:
                msg = "⚠ TUNE Timeout"
            self._status_label.setText(msg)
            QTimer.singleShot(1500, self.reject)

    def _on_cancel_clicked(self):
        """User klickte Abbrechen — TUNE stoppen + Cleanup."""
        self._tick_timer.stop()
        self._backup_timer.stop()
        # P71: DONE FAIL cancelled-Log fuer grep-Diagnose
        print(f"[P54a] DONE FAIL reason=cancelled "
              f"band={self._band} mode={self._mode}")
        # P54-FIX R1-F2 ROT: Cancel-Flag setzen damit Convergenz-Schleife
        # in _tune_converge_to_target sich beendet.
        try:
            self._parent._tune_convergence_cancelled = True
        except AttributeError:
            pass
        try:
            self._parent._tune_stop(None)
        except Exception as e:
            print(f"[AutoTuneDialog] Cancel-Cleanup Fehler: {e}")
        # R1-F4: explicit cleanup (Watchdog wieder scharf, Flag clearen)
        try:
            self._parent._tune_in_progress = False
        except AttributeError:
            pass
        self.reject()

    def _on_backup_timeout(self):
        """Backup-Timer (duration + _BACKUP_GRACE_S s) — falls QTimer aus
        mw_tx haengt.

        R1-F4: setzt _tune_in_progress=False explizit.
        P54-FIX R1-F2: setzt _tune_convergence_cancelled=True.
        P71: DONE FAIL timeout-Log + Grace 5 → 12 s.
        """
        self._tick_timer.stop()
        print(f"[P54a] DONE FAIL reason=timeout "
              f"band={self._band} mode={self._mode} "
              f"after={self._duration_s + _BACKUP_GRACE_S}s")
        try:
            self._parent._tune_convergence_cancelled = True
        except AttributeError:
            pass
        try:
            self._parent._tune_in_progress = False
        except AttributeError:
            pass
        # Selbst-Trigger Fail-Pfad
        self.auto_tune_done.emit(False, 0.0, 0.0)
