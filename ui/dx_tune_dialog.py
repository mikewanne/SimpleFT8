"""SimpleFT8 DX Tune Dialog — Interleaved Antennen + Preamp Optimierung.

Neues Verfahren (v3, Block 2):
- 8 Zyklen interleaved: ANT1@10 → ANT2@10 → ANT1@20 → ANT2@20
  × 2 Runden = 2 Minuten
- Jede Kombination bekommt 2 Zyklen (30s) verteilt ueber die Messzeit
- ANT1 und ANT2 werden bei gleichen Bandoeffnungen verglichen
- Ergebnis: optimaler Gain fuer ANT1 UND ANT2 separat
- Diversity: ANT1_gain beim Wechsel auf ANT1, ANT2_gain beim Wechsel auf ANT2
- Adaptiv-Stop nach Runde 1 (4 Schritte) wenn Antennen-Differenz klar
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

_FONT_MONO = QFont("Menlo", 12)
_FONT_MONO_SM = QFont("Menlo", 10)

GAIN_VALUES = [10, 20]
ROUNDS = 2  # 2 Runden × 4 Kombos = 8 Zyklen × 15s = 2 Min (v0.91 Block 2 #6)


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
    return schedule  # 8 Schritte (ROUNDS × 2 Antennen × 2 Gain-Stufen)


class DXTuneDialog(QDialog):
    """DX Tuning Dialog — Interleaved Messung, per-Antenne Presets."""

    def __init__(self, radio, band: str, scoring_mode: str = "snr", rx_mode: str = "diversity", parent=None):
        super().__init__(parent)
        self.radio = radio
        self.band = band
        self.scoring_mode = scoring_mode  # "snr" (DX) oder "stations" (Standard)
        self.rx_mode = rx_mode            # "normal" oder "diversity"
        self._results = {}

        # Messplan
        self._schedule = _build_interleaved_schedule()  # 8 Schritte
        self._step = 0          # aktueller Schritt im Schedule
        self._phase_data = {}   # (ant, gain) -> [snr_werte]
        self._cancelled = False
        self._finished = False

        _mode_label = self._get_mode_label()
        self.setWindowTitle(f"{_mode_label} — Kalibrierung {band}")
        self.setFixedSize(520, 460)
        self.setModal(False)  # Non-modal damit Decoder-Signale durchkommen
        self._setup_ui()
        self._start_step()

    def _get_mode_label(self) -> str:
        if self.rx_mode == "normal":
            return "Gain-Messung"
        return "Diversity DX" if self.scoring_mode == "snr" else "Diversity Standard"

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
        title = QLabel(f"{self._get_mode_label()} — Kalibrierung {self.band}")
        title.setStyleSheet("color: #00AAFF; font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(
            "8 Zyklen interleaved • ANT1 & ANT2 bei gleichem Gain verglichen\n"
            "Dauert ca. 2 Minuten  •  TX bleibt immer auf ANT1"
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

        # P51 (v0.97.28): Hinweis dass Messung gleichzeitig fuer beide Modi gilt.
        self.mode_label = QLabel("Misst gleichzeitig für Standard- und DX-Modus")
        self.mode_label.setStyleSheet("color: #66AACC; font-style: italic; font-size: 11px;")
        layout.addWidget(self.mode_label)

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

        # Antenne + Gain setzen, TX bleibt ANT1
        self.radio.set_rx_antenna(ant)
        self.radio.set_rfgain(gain)
        self.radio.set_tx_antenna("ANT1")

        round_num = self._step // (len(GAIN_VALUES) * 2) + 1
        pos_in_round = self._step % (len(GAIN_VALUES) * 2) + 1
        self.step_label.setText(
            f"Runde {round_num}/{ROUNDS} — {ant}  Gain {gain} dB"
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

        # Adaptiv-Stop Phase 2 (v0.91 Block 2 #7) — nach Runde 1 pruefen
        if self._check_phase2_early_stop():
            self._finish()
            return

        self._start_step()

    def _check_phase2_early_stop(self) -> bool:
        """Adaptiv-Stop nach Runde 1 (Schritt 4) wenn ANT-Differenz klar.

        Stop-Bedingung (mind. eine erfuellt):
        - Δ_SNR (Top5-Avg) ≥ 4 dB
        - Δ_STAT (Stations-Anzahl, rel.) ≥ 50 %

        Pre-Conditions (alle muessen gelten, sonst kein Stop):
        - _step == 4 (genau Runde 1 Ende)
        - kein Cancel
        - alle 4 Buckets non-empty + non-overload
        - mind. 5 Stationen pro Bucket (Phase-2-eigene Schwelle, unabhaengig
          von Phase-3-Score-Logik in DiversityController seit v0.93)

        Konservativ tuned (R1-bestaetigt): lieber kein Stop als falscher Stop.
        Spart bei Trigger ~60 s Pipeline.
        """
        if self._step != 4:
            return False
        if self._cancelled:
            return False

        keys = [(ant, gain) for ant in ("ANT1", "ANT2") for gain in GAIN_VALUES]

        # Pre-Conditions: alle 4 Buckets non-empty + non-overload + min 5 St.
        for k in keys:
            if not self._phase_data.get(k):
                return False
            if self._has_overload(k):
                return False
            if self._station_count(k) < 5:
                return False

        use_snr = (self.scoring_mode == "snr")

        def best_for(ant: str) -> int:
            best_g, best_s = GAIN_VALUES[0], None
            for gain in GAIN_VALUES:
                if use_snr:
                    score = self._top5_avg((ant, gain))
                else:
                    score = self._station_count((ant, gain))
                if score is None:
                    continue
                if best_s is None or score > best_s:
                    best_s, best_g = score, gain
            return best_g

        ant1_g = best_for("ANT1")
        ant2_g = best_for("ANT2")
        a1_snr = self._top5_avg(("ANT1", ant1_g)) or -30.0
        a2_snr = self._top5_avg(("ANT2", ant2_g)) or -30.0
        a1_n = self._station_count(("ANT1", ant1_g))
        a2_n = self._station_count(("ANT2", ant2_g))

        delta_snr = abs(a1_snr - a2_snr)
        peak_n = max(a1_n, a2_n)
        delta_pct = abs(a1_n - a2_n) / peak_n if peak_n > 0 else 0.0

        stop = (delta_snr >= 4.0) or (delta_pct >= 0.50)

        # Monitoring-Log (R1-Empfehlung) — Schwellen-Tuning post-Feldtest
        import time
        ts = time.strftime("%H:%M:%S")
        if stop:
            print(f"[{ts}] [DX-Tune] Adaptiv-Stop nach Runde 1 — "
                  f"Δ_SNR={delta_snr:.1f}dB Δ_STAT={delta_pct:.0%} → Stop, ~60s gespart")
        else:
            print(f"[{ts}] [DX-Tune] Adaptiv-Stop-Check nach Runde 1 — "
                  f"Δ_SNR={delta_snr:.1f}dB Δ_STAT={delta_pct:.0%} → weiter")

        return stop

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

    def _station_count(self, key) -> int:
        """Gesamtzahl Stationen fuer eine (ant, gain) Kombination."""
        vals = self._phase_data.get(key, [])
        return len([v for v in vals if v is not None])

    def _best_for(self, ant: str, use_snr: bool) -> dict:
        """P51: Liefert {gain, avg, count} fuer eine scoring-Variante.

        use_snr=True  → DX-Optimum (bestes Top-5-SNR pro Gain-Stufe).
        use_snr=False → Standard-Optimum (meiste Stationen pro Gain-Stufe).

        Aus identischen _phase_data ergeben sich zwei unterschiedliche
        Optima — beide ableitbar ohne neue Messung (P51-Vereinheitlichung).
        """
        best_gain = GAIN_VALUES[0]
        best_score = None
        for gain in GAIN_VALUES:
            key = (ant, gain)
            if self._has_overload(key):
                continue
            score = self._top5_avg(key) if use_snr else self._station_count(key)
            if score is None:
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_gain = gain
        avg = self._top5_avg((ant, best_gain))
        count = self._station_count((ant, best_gain))
        return {
            "gain": best_gain,
            "avg": avg if avg is not None else -30.0,
            "count": count,
        }

    def _build_scoring_result(self, use_snr: bool) -> dict:
        """P51: vollstaendiger Result-Satz fuer einen scoring-Modus.

        Returns dict mit ant1_gain, ant2_gain, ant1_avg, ant2_avg,
        best_ant, best_gain — gleiche Struktur wie pre-P51 Single-Result.
        """
        a1 = self._best_for("ANT1", use_snr)
        a2 = self._best_for("ANT2", use_snr)
        if a1["avg"] >= a2["avg"]:
            best_ant, best_gain = "ANT1", a1["gain"]
        else:
            best_ant, best_gain = "ANT2", a2["gain"]
        return {
            "ant1_gain": a1["gain"],
            "ant2_gain": a2["gain"],
            "ant1_avg":  a1["avg"],
            "ant2_avg":  a2["avg"],
            "best_ant":  best_ant,
            "best_gain": best_gain,
        }

    def _finish(self):
        """Alle 8 Zyklen fertig — P51: BEIDE Auswertungen parallel rechnen.

        P51 (v0.97.28): Aus identischen _phase_data werden beide Optima
        bestimmt — Standard (meiste Stationen) UND DX (bester SNR). Beide
        Saetze liegen in self._results["standard"] und self._results["dx"].
        Top-Level-Felder spiegeln den aktiven scoring_mode (Backwards-
        Compat fuer Code der nur 1 Satz erwartet — z.B. set_rfgain am
        Radio).
        """
        self._finished = True

        # P51: beide Auswertungen parallel
        std_result = self._build_scoring_result(use_snr=False)
        dx_result  = self._build_scoring_result(use_snr=True)
        self._results = {
            "standard": std_result,
            "dx":       dx_result,
        }
        # Top-Level = aktive Variante (Backwards-Compat fuer set_rfgain etc.)
        active = dx_result if self.scoring_mode == "snr" else std_result
        for k, v in active.items():
            self._results[k] = v

        # Optimale Einstellungen am Radio setzen (beste Antenne mit bestem Gain)
        ant = self._results["best_ant"]
        gain = self._results["best_gain"]
        self.radio.set_rx_antenna(ant)
        self.radio.set_rfgain(gain)
        self.radio.set_tx_antenna("ANT1")

        # UI kurz aktualisieren, dann automatisch schliessen
        ant1_gain = self._results["ant1_gain"]
        ant2_gain = self._results["ant2_gain"]
        std_a1 = self._results["standard"]["ant1_gain"]
        std_a2 = self._results["standard"]["ant2_gain"]
        dx_a1  = self._results["dx"]["ant1_gain"]
        dx_a2  = self._results["dx"]["ant2_gain"]
        self.step_label.setText("Messung abgeschlossen!")
        self.step_label.setStyleSheet("color: #44FF44; font-size: 13px; font-weight: bold;")
        # P51: Display zeigt beide Auswertungen (Std + DX)
        self.detail_label.setText(
            f"Standard: ANT1={std_a1} dB  ANT2={std_a2} dB  |  "
            f"DX: ANT1={dx_a1} dB  ANT2={dx_a2} dB\n"
            f"Bewertet nach SNR (DX) UND Stationsanzahl (Standard)"
        )
        self.detail_label.setStyleSheet("color: #44FF44;")
        self.progress.setValue(len(self._schedule))
        self.time_label.setText("")
        self.btn_cancel.setVisible(False)
        self._update_results_display()
        # Automatisch speichern und Dialog schliessen (Programm laeuft sofort weiter)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.accept)

    # ── Anzeige-Helfer ──────────────────────────────────────────

    def _update_results_display(self):
        lines = []
        # P51: pro (ant, gain) markieren ob Std-Optimum, DX-Optimum oder beides
        std_set = self._results.get("standard") if self._finished else None
        dx_set  = self._results.get("dx") if self._finished else None
        for ant in ("ANT1", "ANT2"):
            ant_lines = []
            ant_key = ant.lower()
            std_best = std_set.get(f"{ant_key}_gain") if std_set else None
            dx_best  = dx_set.get(f"{ant_key}_gain") if dx_set else None
            for gain in GAIN_VALUES:
                key = (ant, gain)
                avg = self._top5_avg(key)
                count = len([v for v in self._phase_data.get(key, []) if v is not None])
                overload = self._has_overload(key)
                if avg is not None:
                    if overload:
                        marker = "  ⚠ (ausgeschlossen – Übersteuerung)" if self._finished else "  ⚠ OVL"
                    else:
                        marker = ""
                    if self._finished and not overload:
                        is_std = std_best is not None and gain == std_best
                        is_dx  = dx_best is not None and gain == dx_best
                        if is_std and is_dx:
                            marker += "  ←(Std+DX)"
                        elif is_std:
                            marker += "  ←(Std)"
                        elif is_dx:
                            marker += "  ←(DX)"
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
        self.radio.set_rx_antenna("ANT1")
        self.radio.set_tx_antenna("ANT1")
        self.radio.set_rfgain(10)
        self.reject()

    def get_results(self) -> dict:
        """Ergebnis-Dict: ant1_gain, ant2_gain, best_ant, best_gain, ant1_avg, ant2_avg."""
        return dict(self._results)
