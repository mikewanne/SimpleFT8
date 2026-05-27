"""SimpleFT8 DX Tune Dialog — Interleaved Antennen + Preamp Optimierung.

Neues Verfahren (v3, Block 2 + P130):
- 12 Zyklen interleaved: ANT1@0 → ANT2@0 → ANT1@10 → ANT2@10 → ANT1@20 → ANT2@20
  × 2 Runden = 3 Minuten
- Jede Kombination bekommt 2 Zyklen (30s) verteilt ueber die Messzeit
- ANT1 und ANT2 werden bei gleichen Bandoeffnungen verglichen
- Ergebnis: optimaler Gain fuer ANT1 UND ANT2 separat
- Diversity: ANT1_gain beim Wechsel auf ANT1, ANT2_gain beim Wechsel auf ANT2
- Adaptiv-Stop nach Runde 1 (4 Schritte) wenn Antennen-Differenz klar

P74-A (v0.97.94): State-Machine TUNE → GAIN_CYCLES → FINISHED
- Wenn `with_tune_phase=True`: Dialog startet mit TUNE-Phase (analog
  AutoTuneDialog), wechselt nach Auto-Tune-Done auf GAIN_CYCLES.
  Konsolidiert Fall B aus _on_band_changed (Bandwechsel + missing
  Preset + Auto-Gain AN) auf EIN Fenster. AutoTuneDialog bleibt
  unverändert für Fall A (TUNE ohne Gain-Mess).
- Wenn `with_tune_phase=False` (Default): bisheriger Pfad ohne
  TUNE-Phase (Backwards-Compat).
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

_FONT_MONO = QFont("Menlo", 12)
_FONT_MONO_SM = QFont("Menlo", 10)

GAIN_VALUES = [0, 10, 20]  # P130 (25.05.2026): 0 dB wieder dazu —
# Mike-Frage „was wenn 0 gain das beste ist?". Low-Band-Defaults
# (160/80/60m) sind 0 dB, vorher nie gemessen. +90s Kalibrierungszeit
# akzeptiert für Vollständigkeit.
ROUNDS = 2  # 2 Runden × 6 Kombos = 12 Zyklen × 15s = 3 Min (P130-Update)

# P74-A: Backup-Grace für TUNE-Phase analog AutoTuneDialog P71.
# Phase B max 6.5 s + Post-Check 2 s + Safety 3.5 s.
_TUNE_BACKUP_GRACE_S = 12


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

    # P74-A: Signal API-kompatibel mit AutoTuneDialog. Wird vom Parent
    # via `_tune_post_swr_check` emittiert (Duck-typing über
    # `_auto_tune_dialog`-Referenz in mw_tx.py).
    auto_tune_done = Signal(bool, float, float)

    def __init__(self, radio, band: str, scoring_mode: str = "snr",
                 rx_mode: str = "diversity", parent=None,
                 prev_tune_swr: float | None = None,
                 with_tune_phase: bool = False,
                 tune_duration_s: int = 15,
                 mode: str = "FT8"):
        """P75 (v0.97.48): `prev_tune_swr` zeigt grünen Header-Banner
        wenn Dialog direkt nach erfolgreichem Auto-TUNE öffnet
        (Bandwechsel-Pipeline). Visueller Zusammenhang Phase 1 → Phase 2,
        damit User nicht 2 separate Fenster wahrnimmt.
        None → kein Banner (manueller Kalibrieren-Klick, kein Vorgänger).

        P74-A (v0.97.94): `with_tune_phase=True` aktiviert State-Machine
        TUNE → GAIN_CYCLES → FINISHED. Konsolidiert Fall B (Bandwechsel
        + missing Preset + Auto-Gain AN) auf EIN Fenster. Bei True wird
        `prev_tune_swr` ignoriert — Banner duplizieren wäre redundant.
        """
        super().__init__(parent)
        self.radio = radio
        self.band = band
        self.scoring_mode = scoring_mode  # "snr" (DX) oder "stations" (Standard)
        self.rx_mode = rx_mode            # "normal" oder "diversity"
        # P74-A: bei TUNE-Phase ist Header-Banner überflüssig (TUNE läuft
        # im Dialog selbst sichtbar → eigenes Status-Label).
        self._prev_tune_swr = None if with_tune_phase else prev_tune_swr
        self._results = {}

        # P74-A State-Machine
        self.mode = mode
        self.tune_duration_s = tune_duration_s
        self._with_tune_phase = with_tune_phase
        self._state = 'TUNE' if with_tune_phase else 'GAIN_CYCLES'
        # R1-F4: Verhindert Doppel-Trigger zwischen Backup-Timer und
        # echtem Auto-Tune-Done-Signal.
        self._tune_phase_finished = False
        self._tune_tick_timer: QTimer | None = None
        self._tune_backup_timer: QTimer | None = None
        self._tune_elapsed_s = 0

        # Messplan
        self._schedule = _build_interleaved_schedule()  # 8 Schritte
        self._step = 0          # aktueller Schritt im Schedule
        self._phase_data = {}   # (ant, gain) -> [snr_werte]
        self._cancelled = False
        self._finished = False

        _mode_label = self._get_mode_label()
        self.setWindowTitle(f"{_mode_label} — Kalibrierung {band}")
        # P75: Höhe +30 px für Banner wenn vorhanden (Phase-1-Übergang)
        # P74-A: bei TUNE-Phase brauchen wir ~50 px extra für Spinner +
        # Status-Label (in der GAIN-UI ausgeblendet).
        _height = 460
        if self._prev_tune_swr is not None:
            _height = 490
        if with_tune_phase:
            _height = 510
        self.setFixedSize(520, _height)
        self.setModal(False)  # Non-modal damit Decoder-Signale durchkommen
        self._setup_ui()

        if with_tune_phase:
            self._start_tune_phase()
        else:
            self._start_step()

    def _get_mode_label(self) -> str:
        # P146 (27.05.2026): Diversity-Modus-Trennung im Titel obsolet.
        # P80 (v0.97.52) hat den Gain-Store unified — Hardware-Gain
        # (ANT1+ANT2) wird einmal pro Band gespeichert, gilt für
        # Normal + Diversity Standard + Diversity DX gleichermassen
        # (_on_dx_tune_accepted speichert nur std_data, mw_radio.py:2051).
        # Mike-Spec 27.05.: "einmal gemessen, beide profitieren". Der
        # vorhandene Untertext "Misst gleichzeitig fuer Standard- und
        # DX-Modus" (Z. 215) wird damit konsistent zum Titel.
        # scoring_mode bleibt in Z. 534+680 funktional aktiv (Score-
        # Algorithmus-Wahl), nur die UI-Titel-Differenzierung entfaellt.
        if self.rx_mode == "normal":
            return "Gain-Messung"
        return "Diversity (Standard + DX)"

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #16192b; }
            QLabel { background-color: transparent; color: #CCC; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)

        # P75 (v0.97.48): Header-Banner wenn aus Auto-TUNE-Pipeline.
        # Visueller Übergang Phase 1 (TUNE) → Phase 2 (Gain-Messung).
        if self._prev_tune_swr is not None:
            banner = QLabel(
                f"✓ TUNE OK — SWR {self._prev_tune_swr:.1f} · "
                f"jetzt 3 Min Gain-Messung läuft"
            )
            banner.setStyleSheet(
                "background: rgba(0,150,0,0.25); color: #88FFAA; "
                "padding: 6px 10px; border-radius: 4px; "
                "font-weight: bold; font-size: 12px;"
            )
            banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(banner)

        # P74-A: Tune-Phase-UI (Spinner + Status). Sichtbar nur in
        # State 'TUNE', wird in `_apply_state_ui` ausgeblendet sobald
        # Auto-Tune fertig. Fail-Banner überschreibt das Status-Label.
        self._tune_spinner = QProgressBar()
        self._tune_spinner.setRange(0, 0)  # indeterminate
        self._tune_spinner.setTextVisible(False)
        self._tune_spinner.setFixedHeight(14)
        self._tune_spinner.setStyleSheet(
            "QProgressBar { border: 1px solid #333; border-radius: 2px; "
            "background: #1a1a1a; }"
            "QProgressBar::chunk { background: #00CCFF; border-radius: 1px; }"
        )
        layout.addWidget(self._tune_spinner)

        self._tune_status_label = QLabel(
            f"🔧 Auto-TUNE läuft — {self.band.lower()} {self.mode}"
        )
        self._tune_status_label.setStyleSheet(
            "color: #7CC; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(self._tune_status_label)

        # Titel
        title = QLabel(f"{self._get_mode_label()} — Kalibrierung {self.band}")
        title.setStyleSheet("color: #00AAFF; font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label = title  # P74-A: für state-aware Wechsel
        layout.addWidget(title)

        hint = QLabel(
            "12 Zyklen interleaved • ANT1 & ANT2 bei gleichem Gain verglichen\n"
            "Dauert ca. 3 Minuten  •  TX bleibt immer auf ANT1"
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

        # P74-A: initial UI an State angleichen
        self._apply_state_ui()

    # ── P74-A State-Machine (TUNE → GAIN_CYCLES → FINISHED) ──────

    def _apply_state_ui(self):
        """Zeigt/versteckt TUNE-Phase-UI je nach `_state`.

        TUNE: Spinner + tune_status_label sichtbar, Step/Progress/Results
        ausgeblendet (Phase 2 noch nicht aktiv).
        GAIN_CYCLES + FINISHED: TUNE-Widgets weg, bestehende Phase-2-UI
        sichtbar.
        """
        is_tune = (self._state == 'TUNE')
        self._tune_spinner.setVisible(is_tune)
        self._tune_status_label.setVisible(is_tune)
        # Phase-2-UI nur ausserhalb TUNE
        for w in (self.step_label, self.detail_label, self.mode_label,
                  self.progress, self.time_label, self.results_text):
            w.setVisible(not is_tune)

    def _start_tune_phase(self):
        """P74-A: TUNE-Phase starten — Parent macht Hardware-Sequenz.

        Aufruf-Pfad: Parent (MainWindow) öffnet Dialog → __init__ ruft
        diese Methode wenn `with_tune_phase=True`. Wir delegieren die
        Hardware-TUNE-Sequenz an `parent._start_dialog_tune_sequence()`,
        starten Tick- und Backup-Timer für die UI, verbinden das
        `auto_tune_done`-Signal mit unserem Slot. Das Signal wird vom
        Parent in `_tune_post_swr_check` emittiert (mw_tx.py:343/438/454).
        """
        # Signal-Verbindung — Parent emittiert auf self.auto_tune_done.
        self.auto_tune_done.connect(self._on_auto_tune_done)

        # Hardware-Sequenz im Parent starten.
        parent = self.parent()
        if parent is not None and hasattr(parent, '_start_dialog_tune_sequence'):
            parent._start_dialog_tune_sequence(
                self, self.band, self.mode, self.tune_duration_s)

        # Tick-Timer für Live-Anzeige (analog AutoTuneDialog._on_tick).
        self._tune_tick_timer = QTimer(self)
        self._tune_tick_timer.timeout.connect(self._on_tune_tick)
        self._tune_tick_timer.start(1000)

        # Backup-Timer — Fail-Safe wenn auto_tune_done nie kommt.
        # R1-F4: gleicher Flag `_tune_phase_finished` schützt vor Race
        # mit echtem Signal.
        self._tune_backup_timer = QTimer(self)
        self._tune_backup_timer.setSingleShot(True)
        self._tune_backup_timer.timeout.connect(self._on_tune_backup_timeout)
        self._tune_backup_timer.start(
            (self.tune_duration_s + _TUNE_BACKUP_GRACE_S) * 1000)

    def _on_tune_tick(self):
        """P74-A: 1s-Tick während TUNE-Phase.

        P76-B 2-Phasen-Label: Phase 1 (Tuner-Match) zeigt Soll-Countdown,
        Phase 2 (Closed-Loop) zeigt „Leistung wird auf 10 W eingeregelt".
        Liest live SWR + FWDPWR aus Parent.
        """
        if self._state != 'TUNE' or self._tune_phase_finished:
            return
        self._tune_elapsed_s += 1
        parent = self.parent()
        try:
            swr = float(parent.radio.last_swr) if parent else 0.0
        except (AttributeError, TypeError, ValueError):
            swr = 0.0
        try:
            fwdpwr = float(parent._fwdpwr_samples[-1]) if parent else 0.0
        except (AttributeError, IndexError, TypeError, ValueError):
            fwdpwr = 0.0
        effective_duration = max(1, self.tune_duration_s)
        if self._tune_elapsed_s <= effective_duration:
            self._tune_status_label.setStyleSheet(
                "color: #7CC; font-size: 12px; font-weight: bold;")
            self._tune_status_label.setText(
                f"🔧 Auto-TUNE {self.band.lower()} {self.mode} — "
                f"{self._tune_elapsed_s} / {effective_duration} s · "
                f"SWR {swr:.1f} · FWDPWR {fwdpwr:.1f}W"
            )
        else:
            self._tune_status_label.setStyleSheet(
                "color: #DDA; font-size: 12px; font-weight: bold;")
            self._tune_status_label.setText(
                f"🔧 Leistung wird auf 10 W eingeregelt · "
                f"{self._tune_elapsed_s} s · SWR {swr:.1f} · "
                f"FWDPWR {fwdpwr:.1f}W"
            )

    def _on_tune_backup_timeout(self):
        """P74-A R1-F4: Backup-Fail wenn echter Auto-Tune-Done hängt.

        Stumm wenn Phase bereits abgeschlossen (Race-Schutz).
        """
        if self._tune_phase_finished:
            return
        print(f"[P74-A] TUNE-Backup-Timeout {self.band} {self.mode} "
              f"nach {self.tune_duration_s + _TUNE_BACKUP_GRACE_S}s")
        self._on_auto_tune_done(False, 0.0, 0.0)

    def _on_auto_tune_done(self, success: bool, swr: float, avg_fwdpwr: float):
        """P74-A: Slot für `auto_tune_done`-Signal aus _tune_post_swr_check.

        R1-F4: Idempotent — zweiter Aufruf wird stumm ignoriert.
        Success → State auf GAIN_CYCLES + erste Messung starten.
        Fail → roter Fehler-Banner, kein State-Wechsel, nach 1.5s reject.
        """
        if self._tune_phase_finished:
            return
        self._tune_phase_finished = True
        if self._tune_tick_timer is not None:
            self._tune_tick_timer.stop()
        if self._tune_backup_timer is not None:
            self._tune_backup_timer.stop()

        if success:
            self._state = 'GAIN_CYCLES'
            self._apply_state_ui()
            # `_start_step()` setzt rxant/gain neu und schreibt das
            # Step-Label — UI ist nach setVisible(True) frisch befüllt.
            self._start_step()
        else:
            # Fail-Banner ins Status-Label (sichtbar im TUNE-State).
            self._tune_status_label.setStyleSheet(
                "color: #FF6666; font-size: 12px; font-weight: bold;"
            )
            if swr > 0:
                msg = (f"⚠ TUNE fehlgeschlagen — SWR {swr:.1f} · "
                       f"Kalibrierung abgebrochen")
            else:
                msg = "⚠ TUNE Timeout — Kalibrierung abgebrochen"
            self._tune_status_label.setText(msg)
            QTimer.singleShot(1500, self.reject)

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
        # P74-A: in TUNE-Phase keine Cycle-Daten verarbeiten — sonst
        # würde der erste Cycle während TUNE in _phase_data landen.
        if self._state != 'GAIN_CYCLES':
            return
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
        """Adaptiv-Stop nach Runde 1 wenn ANT-Differenz klar.

        Stop-Bedingung (mind. eine erfuellt):
        - Δ_SNR (Top5-Avg) ≥ 4 dB
        - Δ_STAT (Stations-Anzahl, rel.) ≥ 50 %

        Pre-Conditions (alle muessen gelten, sonst kein Stop):
        - _step == 2 * len(GAIN_VALUES) (Runde 1 GERADE abgeschlossen,
          _step wurde in feed_cycle.Z485 schon inkrementiert)
          P130 (25.05.2026): vorher hartkodiert `_step == 4` (bei
          GAIN_VALUES=[10,20], 4 Buckets/Runde). Mit GAIN_VALUES=[0,10,20]
          sind es 6 Buckets/Runde → Check bei _step == 6.
        - kein Cancel
        - alle Buckets der ersten Runde non-empty + non-overload
        - mind. 5 Stationen pro Bucket (Phase-2-eigene Schwelle, unabhaengig
          von Phase-3-Score-Logik in DiversityController seit v0.93)

        Konservativ tuned (R1-bestaetigt): lieber kein Stop als falscher Stop.
        Spart bei Trigger ~60 s Pipeline.
        """
        # P130: dynamisch auf GAIN_VALUES-Länge — Step NACH Runde-1-Ende
        # (feed_cycle inkrementiert _step VOR diesem Check)
        end_of_round1 = 2 * len(GAIN_VALUES)
        if self._step != end_of_round1:
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
        """Alle 12 Zyklen fertig — P51: BEIDE Auswertungen parallel rechnen.

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
        """P74-A: state-aware Cancel.

        TUNE: Parent über laufende TUNE-Sequenz informieren — Post-Check-
        Token invalidieren (R1-F1, sonst feuert _tune_post_swr_check
        nach Dialog-Destroy in das gelöschte Widget), Convergenz-Flag
        setzen, _tune_stop rufen.
        GAIN_CYCLES: bisheriger Pfad (Antenne+Gain auf sicheren Default).
        """
        self._cancelled = True
        if self._state == 'TUNE':
            self._tune_phase_finished = True
            if self._tune_tick_timer is not None:
                self._tune_tick_timer.stop()
            if self._tune_backup_timer is not None:
                self._tune_backup_timer.stop()
            parent = self.parent()
            if parent is not None:
                # R1-F1: Token invalidieren BEVOR _tune_stop läuft —
                # _tune_post_swr_check vergleicht via `is not token`
                # und kehrt früh zurück, kein Signal-Emit mehr.
                try:
                    parent._tune_post_check_token = object()
                except AttributeError:
                    pass
                try:
                    parent._tune_convergence_cancelled = True
                except AttributeError:
                    pass
                try:
                    parent._tune_stop(None)
                except Exception as e:
                    print(f"[P74-A] Cancel-Cleanup Fehler: {e}")
                try:
                    parent._tune_in_progress = False
                except AttributeError:
                    pass
            self.reject()
            return
        # GAIN_CYCLES / FINISHED — bisheriger Pfad
        self.radio.set_rx_antenna("ANT1")
        self.radio.set_tx_antenna("ANT1")
        self.radio.set_rfgain(10)
        self.reject()

    def get_results(self) -> dict:
        """Ergebnis-Dict: ant1_gain, ant2_gain, best_ant, best_gain, ant1_avg, ant2_avg."""
        return dict(self._results)
