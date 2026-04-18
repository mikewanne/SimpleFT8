"""SimpleFT8 Diversity Controller — periodische Antennen-Messung + CQ-Frequenzwahl.

Scoring-Modi:
  "normal" — Fokus auf Masse: Anzahl dekodierbarer Stationen (SNR > -20 dB)
  "dx"     — Fokus auf Qualitaet: Durchschnitts-SNR der Top-5 Stationen

Auswertung: Median ueber 4 Zyklen pro Antenne, Schwelle 8% (statt 15%).
"""

import statistics
import threading
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
    MIN_MEASURE_STATIONS = 5  # Mindestanzahl Stationen fuer Messung
    # 67:33 Pattern (6 Slots, endlos nahtlos wiederholbar)
    # A2 bekommt abwechselnd Even+Odd durch Einzelslots an Pos 2+5
    # Max 2 hintereinander, kein Sprung am Loop-Uebergang
    _PAT_70_A1 = ("A1","A1","A2","A1","A1","A2")  # 4×A1, 2×A2 = 67:33
    _PAT_70_A2 = ("A2","A2","A1","A2","A2","A1")  # 4×A2, 2×A1 = 67:33

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
        self._hist_lock = threading.Lock()  # Thread-Safety fuer Histogram
        self._cq_freq_hz: Optional[int] = None  # Letzte berechnete CQ-Frequenz
        self._cycles_since_recalc = 0  # Zaehler fuer Neuberechnung
        self._recalc_interval = 20     # Alle 20 Zyklen neu berechnen (FT8 = 5 Min)
        self._recalc_count = 0         # Zaehler: wie oft wurde CQ-Freq neu berechnet

    def load_preset(self, preset: dict):
        """Gespeichertes Preset laden — sofort Betrieb ohne Messung."""
        self.ratio = preset.get("ratio", "50:50")
        self.dominant = preset.get("dominant")
        self._phase = "operate"
        self._operate_cycles = 0
        self._measure_step = 0
        self._measurements = {"A1": [], "A2": []}
        print(f"[Diversity] Preset geladen: {self.ratio} (dominant: {self.dominant})")

    def can_measure(self, station_count: int) -> bool:
        """Genug Stationen fuer zuverlaessige Messung?"""
        return station_count >= self.MIN_MEASURE_STATIONS

    def choose(self) -> str:
        """Antenne fuer den naechsten Zyklus waehlen.

        WICHTIG: Jede Antenne bekommt IMMER mindestens 2 aufeinanderfolgende
        Slots (Even+Odd Paar) damit beide Paritaeten empfangen werden.
        """
        if self._phase == "measure":
            # Messung: A2,A1,A1,A2 (6-Slot nahtlos, beide Paritaeten)
            return ("A2","A1","A1","A2","A1","A1")[self._measure_step % 6]
        if self.ratio == "70:30":
            return self._PAT_70_A1[self._operate_cycles % 6]
        if self.ratio == "30:70":
            return self._PAT_70_A2[self._operate_cycles % 6]
        return ("A1", "A1", "A2", "A2")[self._operate_cycles % 4]  # 50:50

    def record_freq(self, freq_hz: float):
        """Belegte Frequenz aus Messphase ins Histogramm eintragen."""
        if freq_hz < self.FREQ_MIN_HZ or freq_hz > self.FREQ_MAX_HZ:
            return
        bin_idx = int(freq_hz // self.FREQ_BIN_HZ)
        with self._hist_lock:
            self._freq_histogram[bin_idx] = self._freq_histogram.get(bin_idx, 0) + 1

    def get_free_cq_freq(self) -> Optional[int]:
        """Freie CQ-Frequenz INNERHALB des belegten Bereichs (Sweetspot).

        Sucht die Luecke die am naechsten am Median liegt, aber NUR
        innerhalb des tatsaechlich belegten Frequenzbereichs.
        Vermeidet Frequenzen ausserhalb des Hotspots.
        """
        with self._hist_lock:
            hist_copy = dict(self._freq_histogram)
        if not hist_copy:
            return None

        # Median der Aktivitaet berechnen
        all_freqs = []
        for bin_idx, count in hist_copy.items():
            freq = bin_idx * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
            all_freqs.extend([freq] * count)
        if not all_freqs:
            return None

        median_freq = statistics.median(all_freqs)

        # Search-Window = tatsaechlich belegter Bereich (NICHT ±600Hz vom Median)
        occupied_bins = sorted(hist_copy.keys())
        occupied_min_hz = occupied_bins[0] * self.FREQ_BIN_HZ
        occupied_max_hz = (occupied_bins[-1] + 1) * self.FREQ_BIN_HZ
        SEARCH_MIN = max(self.FREQ_MIN_HZ, occupied_min_hz)
        SEARCH_MAX = min(self.FREQ_MAX_HZ, occupied_max_hz)
        min_bin = int(SEARCH_MIN // self.FREQ_BIN_HZ)
        max_bin = int(SEARCH_MAX // self.FREQ_BIN_HZ)
        min_gap_bins = max(1, self.FREQ_MIN_GAP_HZ // self.FREQ_BIN_HZ)

        # Alle Luecken innerhalb des belegten Bereichs sammeln
        gaps = []  # [(start_bin, length)]
        current_gap_start = None
        current_gap_len = 0
        for b in range(min_bin, max_bin + 1):
            if b not in hist_copy:
                if current_gap_start is None:
                    current_gap_start = b
                current_gap_len += 1
            else:
                if current_gap_len >= min_gap_bins:
                    gaps.append((current_gap_start, current_gap_len))
                current_gap_start = None
                current_gap_len = 0
        if current_gap_len >= min_gap_bins:
            gaps.append((current_gap_start, current_gap_len))

        if not gaps:
            # Fallback: Median-Frequenz ±25Hz (Bin-Mitte)
            fallback = int(median_freq // self.FREQ_BIN_HZ) * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
            self._cq_freq_hz = fallback
            return self._cq_freq_hz

        # Luecke waehlen die am naechsten am Median liegt
        median_bin = int(median_freq // self.FREQ_BIN_HZ)
        best_gap = min(gaps, key=lambda g: abs((g[0] + g[1] // 2) - median_bin))
        center_bin = best_gap[0] + best_gap[1] // 2
        freq_hz = center_bin * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
        gap_start_hz = best_gap[0] * self.FREQ_BIN_HZ
        gap_end_hz = (best_gap[0] + best_gap[1]) * self.FREQ_BIN_HZ
        print(f"[CQ-Freq] Median={int(median_freq)}Hz | "
              f"Luecke={gap_start_hz}-{gap_end_hz}Hz ({best_gap[1]*self.FREQ_BIN_HZ}Hz breit) | "
              f"TX={int(freq_hz)}Hz | {len(gaps)} Luecken gefunden")
        self._cq_freq_hz = int(freq_hz)
        return self._cq_freq_hz

    @property
    def cq_freq_hz(self) -> Optional[int]:
        """Letzte berechnete CQ-Frequenz (Hz), oder None."""
        return self._cq_freq_hz

    def update_proposed_freq(self, qso_active: bool = False):
        """Vorgeschlagene TX-Frequenz aktualisieren — adaptiv mit Kollisionserkennung.

        Strategie "Stable unless compelled":
        1. QSO-Schutz: kein Wechsel waehrend aktivem QSO
        2. Kollision: aktuelle Freq belegt → sofort wechseln
        3. Zeit-Fallback: alle 10 Zyklen neu berechnen
        4. Minimum Dwell: mind. 3 Zyklen auf einer Freq bleiben
        """
        self._cycles_since_recalc += 1

        # QSO-Schutz: kein Frequenzwechsel waehrend aktivem QSO
        if qso_active and self._cq_freq_hz is not None:
            return

        # Erste Berechnung
        if self._cq_freq_hz is None:
            self.get_free_cq_freq()
            self._cycles_since_recalc = 0
            self._recalc_count += 1
            if self._cq_freq_hz:
                print(f"[CQ-Freq] #{self._recalc_count} Erste Berechnung: →{self._cq_freq_hz}Hz")
            return

        # Kollisionserkennung: ist unsere aktuelle Freq jetzt belegt?
        if self._cycles_since_recalc >= 3:  # Minimum Dwell Time
            with self._hist_lock:
                current_bin = self._cq_freq_hz // self.FREQ_BIN_HZ
                neighbors = sum(self._freq_histogram.get(current_bin + d, 0)
                               for d in [-1, 0, 1])
            if neighbors >= 3:
                old_freq = self._cq_freq_hz
                self.get_free_cq_freq()
                self._cycles_since_recalc = 0
                self._recalc_count += 1
                if self._cq_freq_hz != old_freq:
                    print(f"[CQ-Freq] #{self._recalc_count} Kollision! "
                          f"{old_freq}Hz→{self._cq_freq_hz}Hz ({neighbors} Nachbarn)")
                return

        # Zeit-Fallback: alle 10 Zyklen (~2.5 Min)
        if self._cycles_since_recalc >= 10:
            old_freq = self._cq_freq_hz
            self.get_free_cq_freq()
            self._cycles_since_recalc = 0
            self._recalc_count += 1
            if self._cq_freq_hz != old_freq:
                print(f"[CQ-Freq] #{self._recalc_count} Timer: "
                      f"{old_freq}Hz→{self._cq_freq_hz}Hz (10 Zyklen)")
            else:
                print(f"[CQ-Freq] #{self._recalc_count} Timer: "
                      f"{self._cq_freq_hz}Hz bestaetigt (10 Zyklen)")

    def get_histogram_data(self) -> dict:
        """Histogramm-Daten für Visualisierung.

        Returns:
            bins: {bin_idx: count}, cq_freq: Hz, gap_start_hz: Hz, gap_end_hz: Hz
        """
        with self._hist_lock:
            bins_copy = dict(self._freq_histogram)
        if not bins_copy:
            return {'bins': {}, 'cq_freq': self._cq_freq_hz,
                    'gap_start_hz': None, 'gap_end_hz': None}

        min_bin = int(self.FREQ_MIN_HZ // self.FREQ_BIN_HZ)
        max_bin = int(self.FREQ_MAX_HZ // self.FREQ_BIN_HZ)

        best_gap_start, best_gap_len = None, 0
        cur_start, cur_len = None, 0
        for b in range(min_bin, max_bin + 1):
            if b not in bins_copy:
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
            'bins': bins_copy,
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
