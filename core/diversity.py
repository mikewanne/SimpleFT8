"""SimpleFT8 Diversity Controller — periodische Antennen-Messung + CQ-Frequenzwahl.

Scoring-Modi:
  "normal" — Fokus auf Masse: Anzahl dekodierbarer Stationen (SNR > -20 dB)
  "dx"     — Fokus auf Qualitaet: Durchschnitts-SNR der Top-5 Stationen

Auswertung: Median ueber 4 Zyklen pro Antenne, Schwelle 8% (statt 15%).
"""

import statistics
import time
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
    RECALC_INTERVAL_S = 120.0  # CQ-Freq Zeit-Fallback (statt 10 Zyklen — modus-unabhaengig)
    MIN_DWELL_S = 15.0          # Mindestdwell vor Kollisions-Reaktion (statt 3 Zyklen)
    # 67:33 Pattern (6 Slots, endlos nahtlos wiederholbar)
    # A2 bekommt abwechselnd Even+Odd durch Einzelslots an Pos 2+5
    # Max 2 hintereinander, kein Sprung am Loop-Uebergang
    _PAT_70_A1 = ("A1","A1","A2","A1","A1","A2")  # 4×A1, 2×A2 = 67:33
    _PAT_70_A2 = ("A2","A2","A1","A2","A2","A1")  # 4×A2, 2×A1 = 67:33

    def __init__(self, scoring_mode: str = "normal"):
        self._scoring_mode = scoring_mode  # "normal" oder "dx"
        self.reset()
        self.set_mode("FT8")  # Default — von mw_radio.py spaeter ueberschrieben

    # CQ-Frequenzwahl: 50-Hz-Histogramm der belegten Subfrequenzen
    FREQ_BIN_HZ = 50        # Bin-Breite in Hz
    FREQ_MIN_HZ = 150       # Untergrenze Sicherheitsabstand
    FREQ_MAX_HZ = 2800      # Obergrenze Sicherheitsabstand
    FREQ_MIN_GAP_HZ = 150   # Mindestbreite einer freien Lücke
    SWEET_SPOT_MIN_HZ = 800   # Untergrenze "wo Stationen zuhoeren"
    SWEET_SPOT_MAX_HZ = 2000  # Obergrenze "wo Stationen zuhoeren"

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
        self._freq_histogram = {}  # bin_idx → Anzahl Stationen (sync aus station_accumulator)
        self._cq_freq_hz: Optional[int] = None  # Letzte berechnete CQ-Frequenz
        self._current_gap_width_hz: int = 0     # Sticky-State: Breite der aktuellen Lueck
        self._last_recalc_time: float = 0.0    # Zeitstempel letzter Zeit-Fallback
        self._last_change_time: float = 0.0    # Zeitstempel letzter Freq-Wechsel (Dwell-Guard)
        self._last_check_time: float = 0.0     # Zeitstempel letzter Kollisions-Check (Display)
        self._recalc_count = 0                  # Zaehler: wie oft wurde CQ-Freq neu berechnet

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

    def sync_from_stations(self, stations: dict):
        """Histogramm aus aktuellen Stationen neu aufbauen (1:1 mit RX-Fenster)."""
        self._freq_histogram = {}
        for msg in stations.values():
            freq = getattr(msg, 'freq_hz', None)
            if freq and self.FREQ_MIN_HZ <= freq <= self.FREQ_MAX_HZ:
                bin_idx = int(freq // self.FREQ_BIN_HZ)
                self._freq_histogram[bin_idx] = self._freq_histogram.get(bin_idx, 0) + 1

    def set_mode(self, mode: str) -> None:
        """Modus setzen — beeinflusst Dwell-Time und Recalc-Intervall.

        Mike-Spec: FT8=4 Zyklen, FT4=8 Zyklen, FT2=16 Zyklen Min-Dwell → ~60s
        einheitlich. Recalc = 5x Min-Dwell → ~300s.
        Aufruf bei jeder Modusaenderung in mw_radio.py + bei Initialisierung.
        Aendert NICHT _current_gap_width_hz (Sticky bleibt stabil ueber Mode-Switch
        — Frequenz-Landschaft ist gleich, nur Zykluszeit aendert sich)."""
        cycle_s = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}.get(mode, 15.0)
        dwell_cycles = {"FT8": 4, "FT4": 8, "FT2": 16}.get(mode, 4)
        self._mode = mode
        self._min_dwell_s = cycle_s * dwell_cycles
        self._recalc_interval_s = 5 * self._min_dwell_s

    def _score_gap(self, gap_start_bin: int, gap_len_bins: int, median_bin: int) -> float:
        """Score: hoeher = besser. Auswahl per max(score), Tiebreak per Distance zum Median.

        Lueckenbreite dominiert (1 Hz = 1 Punkt), Nachbarn in +/-1 Bin kosten 50 Hz pro Station,
        Nachbarn in +/-2 Bins kosten halb so viel. Median-Distance ist NUR Tiebreaker (0.01).
        """
        gap_width_hz = gap_len_bins * self.FREQ_BIN_HZ
        center_bin = gap_start_bin + gap_len_bins // 2
        n_close = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-1, +1))
        n_near = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-2, +2))
        neighbor_penalty_hz = 50 * n_close + 25 * n_near
        median_distance_hz = abs(center_bin - median_bin) * self.FREQ_BIN_HZ
        return gap_width_hz - neighbor_penalty_hz - 0.01 * median_distance_hz

    def get_free_cq_freq(self) -> Optional[int]:
        """Freie CQ-Frequenz im Sweet-Spot 800-2000 Hz (wo Stationen zuhoeren).

        Sucht NUR im festen Sweet-Spot 800-2000 Hz (nicht mehr dynamisch um die
        belegten Bereiche herum). Auswahl per Score-Funktion: Lueckenbreite minus
        Nachbar-Penalty, Median-Distance nur als Tiebreaker.
        Gibt None zurueck wenn keine ausreichend breite Luecke gefunden.
        """
        hist_copy = dict(self._freq_histogram)
        if not hist_copy:
            # Kein RX-Verkehr → keine Auswahl moeglich (Aufrufer behaelt aktuelle Freq)
            return None

        # Such-Range fest auf Sweet-Spot
        min_bin = self.SWEET_SPOT_MIN_HZ // self.FREQ_BIN_HZ
        max_bin = self.SWEET_SPOT_MAX_HZ // self.FREQ_BIN_HZ
        min_gap_bins = max(1, self.FREQ_MIN_GAP_HZ // self.FREQ_BIN_HZ)

        # Median NUR auf Sweet-Spot-Stationen (sonst verzerrt sich der Tiebreaker)
        sweet_freqs = []
        for bin_idx, count in hist_copy.items():
            if min_bin <= bin_idx <= max_bin:
                freq = bin_idx * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
                sweet_freqs.extend([freq] * count)
        if sweet_freqs:
            median_freq = statistics.median(sweet_freqs)
            median_bin = int(median_freq // self.FREQ_BIN_HZ)
        else:
            # Sweet-Spot leer → Median irrelevant, nimm Mitte als Default
            median_bin = (min_bin + max_bin) // 2
            median_freq = median_bin * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2

        # Alle freien Luecken im Sweet-Spot sammeln
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
            # Keine ausreichend breite Luecke → aktuelle Frequenz behalten
            return None

        # Score-basierte Auswahl (max statt min)
        best_gap = max(gaps, key=lambda g: self._score_gap(g[0], g[1], median_bin))
        best_width_hz = best_gap[1] * self.FREQ_BIN_HZ
        center_bin = best_gap[0] + best_gap[1] // 2
        freq_hz = center_bin * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2

        # Sticky: nur wechseln wenn signifikant breiter ODER aktuelle Lueck unbrauchbar
        # ODER aktuelle Frequenz ausserhalb Sweet-Spot (Legacy/Drift-Schutz)
        if self._cq_freq_hz is not None and self._current_gap_width_hz > 0:
            current_bin = self._cq_freq_hz // self.FREQ_BIN_HZ
            n_direct = sum(self._freq_histogram.get(current_bin + d, 0) for d in (-1, +1))
            current_unbrauchbar = (n_direct >= 3)
            aktuelle_in_sweet_spot = (
                self.SWEET_SPOT_MIN_HZ <= self._cq_freq_hz <= self.SWEET_SPOT_MAX_HZ
            )
            significantly_better = (best_width_hz > self._current_gap_width_hz + 50)
            if aktuelle_in_sweet_spot and not current_unbrauchbar and not significantly_better:
                return self._cq_freq_hz  # bleiben

        gap_start_hz = best_gap[0] * self.FREQ_BIN_HZ
        gap_end_hz = (best_gap[0] + best_gap[1]) * self.FREQ_BIN_HZ
        print(f"[CQ-Freq] Median={int(median_freq)}Hz | "
              f"Luecke={gap_start_hz}-{gap_end_hz}Hz ({best_width_hz}Hz breit) | "
              f"TX={int(freq_hz)}Hz | {len(gaps)} Luecken gefunden")
        self._cq_freq_hz = int(freq_hz)
        self._current_gap_width_hz = best_width_hz
        return self._cq_freq_hz

    @property
    def cq_freq_hz(self) -> Optional[int]:
        """Letzte berechnete CQ-Frequenz (Hz), oder None."""
        return self._cq_freq_hz

    @property
    def seconds_until_recalc(self) -> int:
        """Sekunden bis zum naechsten CQ-Freq-Zeit-Fallback (modus-abhaengig)."""
        elapsed = time.time() - self._last_recalc_time
        return max(0, int(self._recalc_interval_s - elapsed))

    @property
    def seconds_until_next_check(self) -> int:
        """Sekunden bis zum naechsten Kollisions-Check (modus-abhaengiger Display-Countdown)."""
        elapsed = time.time() - self._last_check_time
        return max(0, int(self._min_dwell_s - elapsed))

    def update_proposed_freq(self, qso_active: bool = False):
        """Vorgeschlagene TX-Frequenz aktualisieren — adaptiv mit Kollisionserkennung.

        Strategie "Stable unless compelled" (zeitbasiert, modus-abhaengig):
        1. QSO-Schutz: kein Wechsel waehrend aktivem QSO
        2. Kollision: aktuelle Freq belegt → wechseln (nach _min_dwell_s)
        3. Zeit-Fallback: alle _recalc_interval_s neu berechnen
        """
        now = time.time()

        # QSO-Schutz: kein Frequenzwechsel waehrend aktivem QSO
        if qso_active and self._cq_freq_hz is not None:
            return

        # Erste Berechnung
        if self._cq_freq_hz is None:
            self.get_free_cq_freq()
            self._last_recalc_time = now
            self._last_change_time = now
            self._last_check_time = now
            self._recalc_count += 1
            if self._cq_freq_hz:
                print(f"[CQ-Freq] #{self._recalc_count} Erste Berechnung: →{self._cq_freq_hz}Hz")
            return

        # Kollisionserkennung verfeinert: 2 in +/-1 ODER 3 in +/-2 (inkl. current_bin)
        # Erst pruefen nach _min_dwell_s (verhindert sofortigen Bounce-Back)
        if now - self._last_change_time >= self._min_dwell_s:
            self._last_check_time = now  # Display-Countdown reset (unabhaengig vom Ergebnis)
            current_bin = self._cq_freq_hz // self.FREQ_BIN_HZ
            hist = self._freq_histogram
            n_direct = sum(hist.get(current_bin + d, 0) for d in (-1, +1))
            n_in_band = sum(hist.get(current_bin + d, 0) for d in (-2, -1, 0, +1, +2))
            collision = (n_direct >= 2 or n_in_band >= 3)
            if collision:
                old_freq = self._cq_freq_hz
                self.get_free_cq_freq()
                self._last_change_time = now
                self._last_recalc_time = now
                self._recalc_count += 1
                if self._cq_freq_hz != old_freq:
                    print(f"[CQ-Freq] #{self._recalc_count} Kollision! "
                          f"{old_freq}Hz→{self._cq_freq_hz}Hz "
                          f"(direkt={n_direct}, band={n_in_band})")
                return

        # Zeit-Fallback: alle _recalc_interval_s (modus-abhaengig)
        if now - self._last_recalc_time >= self._recalc_interval_s:
            old_freq = self._cq_freq_hz
            self.get_free_cq_freq()
            self._last_recalc_time = now
            self._last_change_time = now
            self._recalc_count += 1
            if self._cq_freq_hz != old_freq:
                print(f"[CQ-Freq] #{self._recalc_count} Timer {int(self._recalc_interval_s)}s: "
                      f"{old_freq}Hz→{self._cq_freq_hz}Hz")
            else:
                print(f"[CQ-Freq] #{self._recalc_count} Timer {int(self._recalc_interval_s)}s: "
                      f"{self._cq_freq_hz}Hz bestaetigt")

    def get_histogram_data(self) -> dict:
        """Histogramm-Daten für Visualisierung.

        Returns:
            bins: {bin_idx: count}, cq_freq: Hz, gap_start_hz: Hz, gap_end_hz: Hz
        """
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
