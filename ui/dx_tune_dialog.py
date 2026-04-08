"""SimpleFT8 DX Tune Dialog — Interleaved Antennen + Preamp Optimierung.

Neues Verfahren (v2):
- 18 Zyklen interleaved: ANT1@0 → ANT2@0 → ANT1@10 → ANT2@10 → ANT1@20 → ANT2@20
  × 3 Runden = 4,5 Minuten
- Jede Kombination bekommt 3 Zyklen (45s) verteilt ueber die Messzeit
- ANT1 und ANT2 werden bei gleichen Bandoeffnungen verglichen
- Ergebnis: optimaler Gain fuer ANT1 UND ANT2 separat
- Diversity: ANT1_gain beim Wechsel auf ANT1, ANT2_gain beim Wechsel auf ANT2
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

_FONT_MONO = QFont("Menlo", 12)
_FONT_MONO_SM = QFont("Menlo", 10)

GAIN_VALUES = [0, 10, 20]
ROUNDS = 3  # 3 Runden × 6 Kombos = 18 Zyklen × 15s = 4,5 Min


def _build_interleaved_schedule() -> list:
    """Interleaved Messplan: ANT1/ANT2 bei gleichem Gain in benachbarten Zyklen."""
    schedule = []
    for _round in range(ROUNDS):
        if _round % 2 == 0:
            # Gerade Runden: ANT1 zuerst
            for gain in GAIN_VALUES:
                schedule.append(("ANT1", gain))
                schedule.append(("ANT2", gain))
        else:
            # Ungerade Runden: ANT2 zuerst (noch fairer)
            for gain in GAIN_VALUES:
                schedule.append(("ANT2", gain))
                schedule.append(("ANT1", gain))
    return schedule  # 18 Eintraege


class DXTuneDialog(QDialog):
    """DX Tuning Dialog — Interleaved Messung, per-Antenne Presets."""

    def __init__(self, radio, band: str, parent=None):
        super().__init__(parent)
        self.radio = radio
        self.band = band
        self._results = {}

        # Messplan
        self._schedule = _build_interleaved_schedule()  # 18 Schritte
        self._step = 0          # aktueller Schritt im Schedule
        self._phase_data = {}   # (ant, gain) -> [snr_werte]
        self._cancelled = False
        self._finished = False
        self._skip_first = True  # ersten angebrochenen Zyklus ueberspringen

        self.setWindowTitle(f"DX Tuning — {band}")
        self.setFixedSize(520, 460)
        self.setModal(False)  # Non-modal damit Decoder-Signale durchkommen
        self._setup_ui()
        self._start_step()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #16192b; }
            QLabel { background-color: transparent; color: #CCC; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)

        # Titel
        title = QLabel(f"DX Tuning — {self.band}")
        title.setStyleSheet("color: #00AAFF; font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(
            "18 Zyklen interleaved • ANT1 & ANT2 bei gleichem Gain verglichen\n"
            "Dauert ca. 4,5 Minuten  •  TX bleibt immer auf ANT1"
        )
        hint.setStyleSheet("color: #FFD700; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addWidget(self._sep())

        # Aktueller Schritt
        self.step_label = QLabel("Starte Messung...")
        self.step_label.setStyleSheet("color: #00AAFF; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.step_label)

        self.detail_label = QLabel("")
        self.detail_label.setFont(_FONT_MONO_SM)
        self.detail_label.setStyleSheet("color: #AAA;")
        layout.addWidget(self.detail_label)

        # Fortschritt
        self.progress = QProgressBar()
        self.progress.setRange(0, len(self._schedule))
        self.progress.setValue(0)
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setFormat(f"%v / {len(self._schedule)} Zyklen")
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

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #666; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        layout.addWidget(self._sep())

        # Ergebnisse
        results_header = QLabel("Zwischenergebnisse  (Top-5 SNR-Schnitt pro Kombination)")
        results_header.setStyleSheet("color: #888; font-size: 10px; font-weight: bold;")
        layout.addWidget(results_header)

        self.results_text = QLabel("—")
        self.results_text.setFont(_FONT_MONO_SM)
        self.results_text.setStyleSheet(
            "color: #CCC; background: #111; border: 1px solid #333; "
            "border-radius: 4px; padding: 8px;"
        )
        self.results_text.setMinimumHeight(120)
        self.results_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.results_text.setWordWrap(False)
        layout.addWidget(self.results_text)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background: #440000; color: #FF6666;
                border: 1px solid #663333; border-radius: 4px;
                padding: 0 20px; font-size: 12px; }
            QPushButton:hover { background: #660000; }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Preset speichern")
        self.btn_save.setFixedHeight(32)
        self.btn_save.setStyleSheet("""
            QPushButton { background: #003300; color: #66FF66;
                border: 1px solid #336633; border-radius: 4px;
                padding: 0 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background: #005500; }
            QPushButton:disabled { background: #1a1a2e; color: #444;
                border-color: #333; }
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

    def _start_step(self):
        """Naechsten Messpunkt im Schedule starten."""
        if self._step >= len(self._schedule):
            self._finish()
            return
        if self._cancelled:
            return

        ant, gain = self._schedule[self._step]
        s = self.radio._slice_idx

        # Antenne + Gain setzen, TX bleibt ANT1
        self.radio._send_cmd(f"slice set {s} rxant={ant}")
        self.radio._send_cmd(f"slice set {s} rfgain={gain}")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")

        round_num = self._step // (len(GAIN_VALUES) * 2) + 1
        pos_in_round = self._step % (len(GAIN_VALUES) * 2) + 1
        self.step_label.setText(
            f"Runde {round_num}/3 — {ant}  Gain {gain} dB"
        )
        self.detail_label.setText(
            f"Schritt {self._step + 1}/{len(self._schedule)}  "
            f"({pos_in_round}/{len(GAIN_VALUES) * 2} in dieser Runde)"
        )
        self.progress.setValue(self._step)
        self._update_time()
        self._update_results_display()

    def feed_cycle(self, messages: list):
        """Vom MainWindow aufgerufen wenn ein Dekodier-Zyklus fertig ist."""
        if self._cancelled or self._finished:
            return
        if self._skip_first:
            self._skip_first = False
            self.detail_label.setText("Warte auf naechsten vollen Zyklus...")
            return
        if self._step >= len(self._schedule):
            return

        ant, gain = self._schedule[self._step]
        key = (ant, gain)

        if key not in self._phase_data:
            self._phase_data[key] = []

        snr_vals = [m.snr for m in messages if m.snr is not None and m.snr > -35]
        self._phase_data[key].extend(snr_vals)

        # ADC-Uebersteuerung pruefen: viele sehr starke Signale = Clipping
        overloaded = self._detect_overload(messages)
        if overloaded:
            self._phase_data[key].append(None)  # Marker fuer Uebersteuerung
            self.detail_label.setText(
                f"⚠ Schritt {self._step + 1}: ADC-Uebersteuerung erkannt bei "
                f"{ant} Gain {gain} dB"
            )
            self.detail_label.setStyleSheet("color: #FF8800;")

        self._step += 1
        self._start_step()

    def _detect_overload(self, messages: list) -> bool:
        """Erkennt ADC-Uebersteuerung: zu viele Signale >+20 dB oder SNR-Varianz zu niedrig."""
        if not messages:
            return False
        snr_vals = [m.snr for m in messages if m.snr is not None]
        if not snr_vals:
            return False
        strong = sum(1 for s in snr_vals if s > 20)
        if strong > 8:
            return True
        if len(snr_vals) >= 5:
            avg = sum(snr_vals) / len(snr_vals)
            variance = sum((s - avg) ** 2 for s in snr_vals) / len(snr_vals)
            if variance < 1.5:
                return True
        return False

    def _top5_avg(self, key) -> float | None:
        """Top-5 SNR-Schnitt fuer eine (ant, gain) Kombination."""
        vals = self._phase_data.get(key, [])
        clean = [v for v in vals if v is not None]  # None = Uebersteuerung ignorieren
        if not clean:
            return None
        sorted_vals = sorted(clean, reverse=True)
        top5 = sorted_vals[:5]
        return round(sum(top5) / len(top5), 1)

    def _has_overload(self, key) -> bool:
        vals = self._phase_data.get(key, [])
        return None in vals

    def _finish(self):
        """Alle 18 Zyklen fertig — besten Gain pro Antenne bestimmen."""
        self._finished = True

        for ant in ("ANT1", "ANT2"):
            best_gain = GAIN_VALUES[0]
            best_avg = None
            for gain in GAIN_VALUES:
                key = (ant, gain)
                avg = self._top5_avg(key)
                if avg is None:
                    continue
                if self._has_overload(key):
                    continue  # Uebersteuerung: ignorieren
                if best_avg is None or avg > best_avg:
                    best_avg = avg
                    best_gain = gain
            self._results[f"{ant.lower()}_gain"] = best_gain
            self._results[f"{ant.lower()}_avg"] = best_avg if best_avg is not None else -30.0

        # Beste Antenne gesamt (fuer DX Tuning Modus Abwaertskompatibilitaet)
        ant1_avg = self._results.get("ant1_avg", -30.0)
        ant2_avg = self._results.get("ant2_avg", -30.0)
        if ant1_avg >= ant2_avg:
            self._results["best_ant"] = "ANT1"
            self._results["best_gain"] = self._results["ant1_gain"]
        else:
            self._results["best_ant"] = "ANT2"
            self._results["best_gain"] = self._results["ant2_gain"]

        # Optimale Einstellungen am Radio setzen (beste Antenne mit bestem Gain)
        s = self.radio._slice_idx
        ant = self._results["best_ant"]
        gain = self._results["best_gain"]
        self.radio._send_cmd(f"slice set {s} rxant={ant}")
        self.radio._send_cmd(f"slice set {s} rfgain={gain}")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")

        # UI
        ant1_gain = self._results["ant1_gain"]
        ant2_gain = self._results["ant2_gain"]
        self.step_label.setText("Messung abgeschlossen!")
        self.step_label.setStyleSheet("color: #44FF44; font-size: 13px; font-weight: bold;")
        self.detail_label.setText(
            f"ANT1: optimaler Gain {ant1_gain} dB  |  "
            f"ANT2: optimaler Gain {ant2_gain} dB"
        )
        self.detail_label.setStyleSheet("color: #44FF44;")
        self.progress.setValue(len(self._schedule))
        self.time_label.setText("")
        self.btn_save.setEnabled(True)
        self.btn_cancel.setText("Verwerfen")
        self._update_results_display()

    # ── Anzeige-Helfer ──────────────────────────────────────────

    def _update_results_display(self):
        lines = []
        for ant in ("ANT1", "ANT2"):
            ant_lines = []
            for gain in GAIN_VALUES:
                key = (ant, gain)
                avg = self._top5_avg(key)
                count = len([v for v in self._phase_data.get(key, []) if v is not None])
                overload = self._has_overload(key)
                if avg is not None:
                    marker = " ⚠OVL" if overload else ""
                    # Nach Messung: Gewinner markieren
                    if self._finished:
                        best_g = self._results.get(f"{ant.lower()}_gain")
                        marker += "  ←" if gain == best_g and not overload else ""
                    ant_lines.append(
                        f"  {ant} Gain {gain:2d} dB:  Ø {avg:+5.1f} dB  "
                        f"({count} St.){marker}"
                    )
                elif key in self._phase_data:
                    ant_lines.append(f"  {ant} Gain {gain:2d} dB:  (keine Daten)")
            if ant_lines:
                lines.append(f"{ant}:")
                lines.extend(ant_lines)
        self.results_text.setText("\n".join(lines) if lines else "—")

    def _update_time(self):
        remaining = len(self._schedule) - self._step
        secs = remaining * 15
        m, s = divmod(secs, 60)
        self.time_label.setText(f"Restzeit: ca. {m:.0f}:{s:02.0f} min")

    def _on_cancel(self):
        self._cancelled = True
        s = self.radio._slice_idx
        self.radio._send_cmd(f"slice set {s} rxant=ANT1")
        self.radio._send_cmd(f"slice set {s} txant=ANT1")
        self.radio._send_cmd(f"slice set {s} rfgain=10")
        self.reject()

    def get_results(self) -> dict:
        """Ergebnis-Dict: ant1_gain, ant2_gain, best_ant, best_gain, ant1_avg, ant2_avg."""
        return dict(self._results)
