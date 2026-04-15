"""SimpleFT8 Diversity Controller — periodische Antennen-Messung + CQ-Frequenzwahl.

Scoring-Modi:
  "normal" — Fokus auf Masse: Anzahl dekodierbarer Stationen (SNR > -20 dB)
  "dx"     — Fokus auf Qualitaet: Durchschnitts-SNR der Top-5 Stationen

Auswertung: Median ueber 4 Zyklen pro Antenne, Schwelle 8% (statt 15%).
"""

import statistics
from typing import Optional


class DiversityController:
    """Periodische Antennen-Messung fuer Diversity-Modus.

    Ablauf:
    - MESS-PHASE  (8 Zyklen): 4×A1 + 4×A2 messen
    - BETRIEB     (60 Zyklen ≈ 15 Min): 70:30 oder 50:50
    - Nach 60 Zyklen ohne aktives QSO → neu messen
    Scoring: Modus-abhaengig (Normal=Stationsanzahl, DX=Top-5-SNR)
    Schwelle: 8% relative Differenz → 50:50, sonst 70:30
    """

    MEASURE_CYCLES = 8   # 4×A1 + 4×A2 (~2 Min Fenster, je even+odd pro Antenne)
    OPERATE_CYCLES = 60  # 15 Min Betrieb (vorher 80=20 Min)
    THRESHOLD = 0.08     # 8% relative Differenz fuer Antennen-Entscheidung
    _PAT_70_A1 = ("A1","A1","A2","A1","A1","A2","A1","A1","A2","A1")  # 7×A1, 3×A2
    _PAT_70_A2 = ("A2","A2","A1","A2","A2","A1","A2","A2","A1","A2")  # 7×A2, 3×A1

    def __init__(self, scoring_mode: str = "normal"):
        self._scoring_mode = scoring_mode  # "normal" oder "dx"
        self.reset()

    # CQ-Frequenzwahl: 50-Hz-Histogramm der belegten Subfrequenzen
    FREQ_BIN_HZ = 50        # Bin-Breite in Hz
    FREQ_MIN_HZ = 150       # Untergrenze Sicherheitsabstand
    FREQ_MAX_HZ = 2800      # Obergrenze Sicherheitsabstand
    FREQ_MIN_GAP_HZ = 150   # Mindestbreite einer freien Lücke

    @property
    def scoring_mode(self) -> str:
        """Aktueller Scoring-Modus: 'normal' oder 'dx'."""
        return self._scoring_mode

    @scoring_mode.setter
    def scoring_mode(self, mode: str):
        if mode in ("normal", "dx"):
            self._scoring_mode = mode

    def reset(self):
        self._phase = "measure"
        self._measure_step = 0
        self._measurements: dict[str, list[float]] = {"A1": [], "A2": []}
        self._operate_cycles = 0
        self.ratio = "50:50"
        self.dominant = None   # "A1", "A2", oder None
        self._freq_histogram = {}  # bin_idx → Anzahl Stationen
        self._cq_freq_hz: Optional[int] = None  # Letzte berechnete CQ-Frequenz

    def choose(self) -> str:
        """Antenne fuer den naechsten Zyklus waehlen."""
        if self._phase == "measure":
            return "A2" if self._measure_step % 2 == 0 else "A1"  # A2,A1,A2,A1 (A1 war init)
        if self.ratio == "70:30":
            return self._PAT_70_A1[self._operate_cycles % 10]
        if self.ratio == "30:70":
            return self._PAT_70_A2[self._operate_cycles % 10]
        return ("A1", "A1", "A2", "A2")[self._operate_cycles % 4]  # 50:50: 2 Zyklen pro Antenne → Even+Odd beide auf jeder Antenne

    def record_freq(self, freq_hz: float):
        """Belegte Frequenz aus Messphase ins Histogramm eintragen."""
        if freq_hz < self.FREQ_MIN_HZ or freq_hz > self.FREQ_MAX_HZ:
            return
        bin_idx = int(freq_hz // self.FREQ_BIN_HZ)
        self._freq_histogram[bin_idx] = self._freq_histogram.get(bin_idx, 0) + 1

    def get_free_cq_freq(self) -> Optional[int]:
        """Freie CQ-Frequenz aus Histogramm berechnen.

        Sucht eine Luecke im AKTIVEN Bereich (wo Stationen sind).
        Bevorzugt 800-2000 Hz (Sweet Spot fuer CQ), nicht die leere Zone >2000 Hz.
        """
        if not self._freq_histogram:
            return None

        # Aktiven Bereich bestimmen: wo sind die meisten Stationen?
        # Bevorzuge 800-2000 Hz als CQ Sweet Spot (Grok/DeepSeek Konsens)
        SWEET_MIN = 800
        SWEET_MAX = 2000
        min_bin = int(SWEET_MIN // self.FREQ_BIN_HZ)
        max_bin = int(SWEET_MAX // self.FREQ_BIN_HZ)
        min_gap_bins = max(1, self.FREQ_MIN_GAP_HZ // self.FREQ_BIN_HZ)

        best_gap_start = None
        best_gap_len = 0
        current_gap_start = None
        current_gap_len = 0

        for b in range(min_bin, max_bin + 1):
            if b not in self._freq_histogram:  # leerer Bin
                if current_gap_start is None:
                    current_gap_start = b
                current_gap_len += 1
            else:  # belegter Bin
                if current_gap_len > best_gap_len:
                    best_gap_len = current_gap_len
                    best_gap_start = current_gap_start
                current_gap_start = None
                current_gap_len = 0

        # Letztes Segment prüfen
        if current_gap_len > best_gap_len:
            best_gap_len = current_gap_len
            best_gap_start = current_gap_start

        if best_gap_start is None or best_gap_len < min_gap_bins:
            return None

        # Mitte der besten Lücke
        center_bin = best_gap_start + best_gap_len // 2
        freq_hz = center_bin * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
        self._cq_freq_hz = int(freq_hz)
        return self._cq_freq_hz

    @property
    def cq_freq_hz(self) -> Optional[int]:
        """Letzte berechnete CQ-Frequenz (Hz), oder None."""
        return self._cq_freq_hz

    def get_histogram_data(self) -> dict:
        """Histogramm-Daten für Visualisierung.

        Returns:
            bins: {bin_idx: count}, cq_freq: Hz, gap_start_hz: Hz, gap_end_hz: Hz
        """
        if not self._freq_histogram:
            return {'bins': {}, 'cq_freq': self._cq_freq_hz,
                    'gap_start_hz': None, 'gap_end_hz': None}

        min_bin = int(self.FREQ_MIN_HZ // self.FREQ_BIN_HZ)
        max_bin = int(self.FREQ_MAX_HZ // self.FREQ_BIN_HZ)

        best_gap_start, best_gap_len = None, 0
        cur_start, cur_len = None, 0
        for b in range(min_bin, max_bin + 1):
            if b not in self._freq_histogram:
                if cur_start is None:
                    cur_start = b
                cur_len += 1
            else:
                if cur_len > best_gap_len:
                    best_gap_len, best_gap_start = cur_len, cur_start
                cur_start, cur_len = None, 0
        if cur_len > best_gap_len:
            best_gap_len, best_gap_start = cur_len, cur_start

        gap_start_hz = best_gap_start * self.FREQ_BIN_HZ if best_gap_start else None
        gap_end_hz = (best_gap_start + best_gap_len) * self.FREQ_BIN_HZ if best_gap_start else None

        return {
            'bins': self._freq_histogram.copy(),
            'cq_freq': self._cq_freq_hz,
            'gap_start_hz': gap_start_hz,
            'gap_end_hz': gap_end_hz,
        }

    def record_measurement(self, ant: str, score: float,
                           station_count: int = 0, avg_snr: float = -30.0,
                           dx_weak_count: int = 0):
        """Score nach Messzyklus einpflegen — evaluiert nach 8 Messungen.

        Args:
            ant: "A1" oder "A2"
            score: Legacy-Score (sum(snr+30)), fuer Rueckwaerts-Kompatibilitaet
            station_count: Anzahl dekodierbarer Stationen (SNR > -20)
            avg_snr: Durchschnitts-SNR aller Stationen
            dx_weak_count: Anzahl schwacher Stationen (SNR < -10, DX-Modus)
        """
        if self._phase != "measure":
            return

        # Modus-abhaengigen Score speichern (Einzelwert, NICHT akkumuliert)
        if self._scoring_mode == "dx":
            # DX: Anzahl schwacher Stationen (SNR < -10) — mehr = bessere DX-Antenne
            self._measurements[ant].append(float(dx_weak_count))
        else:
            # Standard: Gesamtzahl dekodierbarer Stationen — mehr = besser
            self._measurements[ant].append(float(station_count))

        self._measure_step += 1
        if self._measure_step >= self.MEASURE_CYCLES:
            self._evaluate()

    def on_operate_cycle(self):
        """Pro Betriebszyklus aufrufen."""
        if self._phase == "operate":
            self._operate_cycles += 1

    def should_remeasure(self, qso_active: bool) -> bool:
        return (self._phase == "operate"
                and self._operate_cycles >= self.OPERATE_CYCLES
                and not qso_active)

    def start_measure(self):
        self._phase = "measure"
        self._measure_step = 0
        self._measurements = {"A1": [], "A2": []}
        self._freq_histogram = {}  # Histogramm für neue Messung zurücksetzen

    def on_band_change(self):
        """Bandwechsel → Neueinmessung starten."""
        self.reset()
        print("[Diversity] Bandwechsel — Neueinmessung gestartet (4 Zyklen)")

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def measure_step(self) -> int:
        """Bereits abgeschlossene Messschritte (0..MEASURE_CYCLES)."""
        return self._measure_step

    @property
    def operate_cycles(self) -> int:
        """Bereits abgeschlossene Betriebszyklen (0..OPERATE_CYCLES)."""
        return self._operate_cycles

    def _evaluate(self):
        m1 = self._measurements["A1"]
        m2 = self._measurements["A2"]

        # Median pro Antenne (robust gegen Ausreisser)
        s1 = statistics.median(m1) if m1 else 0.0
        s2 = statistics.median(m2) if m2 else 0.0
        peak = max(s1, s2)

        diff = 0.0
        if peak <= 1.0:
            # Zu wenig Daten fuer zuverlaessige Entscheidung
            self.ratio = "50:50"
            self.dominant = None
        else:
            diff = abs(s1 - s2) / peak  # relative Differenz zum Besseren
            if diff < self.THRESHOLD:    # 8% statt 15%
                self.ratio = "50:50"
                self.dominant = None
            elif s1 >= s2:
                self.ratio = "70:30"
                self.dominant = "A1"
            else:
                self.ratio = "30:70"
                self.dominant = "A2"
        self._phase = "operate"
        self._operate_cycles = 0
        mode_tag = "DX" if self._scoring_mode == "dx" else "Normal"
        print(f"[Diversity] Messung ({mode_tag}): A1={s1:.1f} A2={s2:.1f} "
              f"diff={diff:.3f} (>{self.THRESHOLD:.0%}?) → {self.ratio} "
              f"(dominant: {self.dominant}, Werte: A1={m1} A2={m2})")
