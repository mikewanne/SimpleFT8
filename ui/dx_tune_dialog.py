"""SimpleFT8 DX Tune Dialog — Automatische Antennen + Preamp Optimierung.

Misst Empfangsqualitaet ueber FT8-Stationsstatistik:
- Top-5 staerkste Stationen pro Phase → Durchschnitts-SNR
- 3 Zyklen pro Einstellung fuer stabile Messung
- Phase 1: ANT1 vs ANT2 (RX-Antenne, TX bleibt ANT1)
- Phase 2: RF-Gain 0/10/20 auf Gewinner-Antenne
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

_FONT_MONO = QFont("Menlo", 12)
_FONT_MONO_SM = QFont("Menlo", 10)

CYCLES_PER_PHASE = 3
GAIN_VALUES = [0, 10, 20]


class DXTuneDialog(QDialog):
    """DX Tuning Dialog — misst Antenne + Preamp ueber FT8-Dekodierung."""

    def __init__(self, radio, band: str, parent=None):
        super().__init__(parent)
        self.radio = radio
        self.band = band
        self._results = {}

        # Antennen-Test mit moderatem Gain (20 dB) damit genug Stationen reinkommen
        ant_test_gain = 20

        # Phasen: (typ, label, antenne, gain)
        self._phases = [
            ("ant", "ANT1", "ANT1", ant_test_gain),
            ("ant", "ANT2", "ANT2", ant_test_gain),
        ]
        self._phase_idx = 0
        self._cycle_count = 0
        self._phase_snr_values = []   # SNR-Werte der aktuellen Phase
        self._phase_results = []       # (label, top5_avg, total_stations)
        self._cancelled = False
        self._finished = False

        self.setWindowTitle(f"DX Tuning — {band}")
        self.setFixedSize(480, 420)
        self.setModal(True)
        self._setup_ui()
        self._start_phase()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #16192b;
            }
            QLabel {
                background-color: transparent;
                color: #CCC;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)

        # Titel
        title = QLabel(f"DX Tuning — {self.band}")
        title.setStyleSheet(
            "color: #00AAFF; font-size: 18px; font-weight: bold;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("Messung dauert ca. 3–5 Minuten\nTX bleibt immer auf ANT1")
        hint.setStyleSheet("color: #FFD700; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addWidget(self._sep())

        # Phase
        self.phase_label = QLabel("Phase 1: Antenne testen")
        self.phase_label.setStyleSheet(
            "color: #00AAFF; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(self.phase_label)

        self.step_label = QLabel("ANT1 — warte auf Zyklus 1/3 ...")
        self.step_label.setFont(_FONT_MONO_SM)
        self.step_label.setStyleSheet("color: #CCC;")
        layout.addWidget(self.step_label)

        # Fortschritt
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #222; border: 1px solid #444;
                border-radius: 4px; text-align: center;
                color: #CCC; font-family: Menlo; font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #003366, stop:1 #0066AA);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress)

        layout.addWidget(self._sep())

        # Ergebnisse
        results_header = QLabel("Ergebnisse")
        results_header.setStyleSheet(
            "color: #888; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(results_header)

        self.results_text = QLabel("—")
        self.results_text.setFont(_FONT_MONO)
        self.results_text.setStyleSheet(
            "color: #CCC; background: #111; border: 1px solid #333; "
            "border-radius: 4px; padding: 8px;"
        )
        self.results_text.setMinimumHeight(100)
        self.results_text.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.results_text.setWordWrap(True)
        layout.addWidget(self.results_text)

        # Restzeit
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #666; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #440000; color: #FF6666;
                border: 1px solid #663333; border-radius: 4px;
                padding: 0 20px; font-size: 12px;
            }
            QPushButton:hover { background: #660000; }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Preset speichern")
        self.btn_save.setFixedHeight(32)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: #003300; color: #66FF66;
                border: 1px solid #336633; border-radius: 4px;
                padding: 0 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #005500; }
            QPushButton:disabled {
                background: #1a1a2e; color: #444;
                border-color: #333;
            }
        """)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        line.setFixedHeight(1)
        return line

    # ── Messlogik ───────────────────────────────────────────────

    def _start_phase(self):
        """Aktuelle Messphase starten — Radio umschalten."""
        if self._phase_idx >= len(self._phases):
            self._finish()
            return

        typ, label, ant, gain = self._phases[self._phase_idx]
        self._cycle_count = 0
        self._phase_snr_values = []

        # Radio umschalten
        s = self.radio._slice_idx
        if typ == "ant":
            self.radio._send_cmd(f"slice set {s} rxant={ant}")
            self.radio._send_cmd(f"slice set {s} rfgain={gain}")
            self.phase_label.setText("Phase 1: Antenne testen")
            self.step_label.setText(
                f"{label} — warte auf Zyklus 1/{CYCLES_PER_PHASE} ..."
            )
        else:
            self.radio._send_cmd(f"slice set {s} rfgain={gain}")
            self.phase_label.setText("Phase 2: Preamp testen")
            self.step_label.setText(
                f"Gain {gain} dB — warte auf Zyklus 1/{CYCLES_PER_PHASE} ..."
            )

        # TX bleibt IMMER ANT1!
        self.radio._send_cmd(f"slice set {s} txant=ANT1")

        self._update_progress()
        self._update_time()

    def feed_cycle(self, messages: list):
        """Vom MainWindow aufgerufen wenn ein Dekodier-Zyklus fertig ist."""
        if self._cancelled or self._finished:
            return
        if not messages:
            return

        self._cycle_count += 1

        # SNR-Werte sammeln (nur gueltige)
        snr_vals = [m.snr for m in messages if m.snr > -30]
        self._phase_snr_values.extend(snr_vals)

        # Anzeige
        typ, label, ant, gain = self._phases[self._phase_idx]
        station_info = f"({len(snr_vals)} St.)"
        if typ == "ant":
            self.step_label.setText(
                f"{label} — Zyklus {self._cycle_count}/{CYCLES_PER_PHASE} "
                f"{station_info}"
            )
        else:
            self.step_label.setText(
                f"Gain {gain} dB — Zyklus {self._cycle_count}/{CYCLES_PER_PHASE} "
                f"{station_info}"
            )

        self._update_progress()
        self._update_time()

        if self._cycle_count >= CYCLES_PER_PHASE:
            self._finish_phase()

    def _finish_phase(self):
        """Aktuelle Phase auswerten, naechste starten."""
        typ, label, ant, gain = self._phases[self._phase_idx]

        # Top-5 Durchschnitt berechnen
        sorted_snr = sorted(self._phase_snr_values, reverse=True)
        top5 = sorted_snr[:5] if len(sorted_snr) >= 5 else sorted_snr
        avg = sum(top5) / len(top5) if top5 else -30.0
        total = len(self._phase_snr_values)

        self._phase_results.append((label, avg, total))
        self._update_results()

        self._phase_idx += 1

        # Nach Antennen-Phase: Gewinner bestimmen, Gain-Phasen hinzufuegen
        if self._phase_idx == 2:
            ant1_avg = self._phase_results[0][1]
            ant2_avg = self._phase_results[1][1]
            winner = "ANT1" if ant1_avg >= ant2_avg else "ANT2"
            self._results["best_ant"] = winner
            self._results["ant1_avg"] = ant1_avg
            self._results["ant2_avg"] = ant2_avg
            # Gain-Phasen fuer Gewinner-Antenne
            for g in GAIN_VALUES:
                self._phases.append(("gain", f"Gain {g}", winner, g))

        self._start_phase()

    def _finish(self):
        """Alle Phasen fertig — Ergebnis anzeigen."""
        self._finished = True

        # Bester Gain
        gain_results = [
            (label, avg, count) for label, avg, count in self._phase_results
            if label.startswith("Gain")
        ]
        if gain_results:
            best = max(gain_results, key=lambda x: x[1])
            best_gain = int(best[0].split()[1])
            self._results["best_gain"] = best_gain
            self._results["gain_avg"] = best[1]
        else:
            self._results["best_gain"] = 0

        # Optimale Einstellungen am Radio setzen
        s = self.radio._slice_idx
        ant = self._results.get("best_ant", "ANT1")
        gain = self._results.get("best_gain", 0)
        self.radio._send_cmd(f"slice set {s} rxant={ant}")
        self.radio._send_cmd(f"slice set {s} rfgain={gain}")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")

        # UI
        self.phase_label.setText("Messung abgeschlossen!")
        self.phase_label.setStyleSheet(
            "color: #44FF44; font-size: 14px; font-weight: bold;"
        )
        self.step_label.setText(f"Optimal: {ant} (RX), Gain {gain} dB")
        self.step_label.setStyleSheet("color: #44FF44;")
        self.progress.setValue(100)
        self.time_label.setText("")
        self.btn_save.setEnabled(True)
        self.btn_cancel.setText("Verwerfen")
        self._update_results()

    # ── Anzeige-Helfer ──────────────────────────────────────────

    def _update_results(self):
        lines = []
        for label, avg, count in self._phase_results:
            marker = ""
            if label in ("ANT1", "ANT2"):
                best = self._results.get("best_ant", "")
                if label == best:
                    marker = "  ←"
            elif label.startswith("Gain") and self._finished:
                best_g = self._results.get("best_gain", -1)
                if label == f"Gain {best_g}":
                    marker = "  ←"
            lines.append(f"{label:8s} Ø {avg:+5.1f} dB  ({count} St.){marker}")
        self.results_text.setText("\n".join(lines) if lines else "—")

    def _update_progress(self):
        total = len(self._phases)
        if total == 0:
            return
        done = self._phase_idx + (self._cycle_count / CYCLES_PER_PHASE)
        pct = int((done / total) * 100)
        self.progress.setValue(min(pct, 99))

    def _update_time(self):
        remaining = len(self._phases) - self._phase_idx
        remaining_cycles = (remaining * CYCLES_PER_PHASE) - self._cycle_count
        secs = max(0, remaining_cycles * 15)
        m, s = divmod(secs, 60)
        self.time_label.setText(f"Restzeit: ca. {m:.0f}:{s:02.0f}")

    def _on_cancel(self):
        self._cancelled = True
        # Zurueck auf sichere Defaults
        s = self.radio._slice_idx
        self.radio._send_cmd(f"slice set {s} rxant=ANT1")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")
        self.radio._send_cmd(f"slice set {s} rfgain=10")
        self.reject()

    def get_results(self) -> dict:
        """Ergebnis-Dict: best_ant, best_gain, ant1_avg, ant2_avg, gain_avg."""
        return dict(self._results)
