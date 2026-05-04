"""SimpleFT8 Diversity Controller — periodische Antennen-Messung + CQ-Frequenzwahl.

Score-basierte Messung (v0.93):
  Pro Slot wird ``sum(snr+30)`` ueber alle dekodierten Stationen akkumuliert.
  Kontinuierliche Werte → Median liefert auch bei duenner Decoder-Dichte
  (z.B. FT2 mit 1-2 Stationen pro Slot) statistische Aufloesung.

  Der ``scoring_mode`` ("normal"/"dx") bestimmt aktuell nur die Sammlungs-
  strategie der Aufrufer (Standard sammelt alle Stationen, DX nur SNR<-10);
  intern wird in beiden Modi der gleiche Score gemessen.

Auswertung: Median ueber Slot-Scores (6-Slot fair 3:3), Schwelle 8 % rel.
Differenz → 70:30 bzw. 30:70, sonst 50:50.
"""

import statistics
import time
from typing import Optional


class DiversityController:
    """Periodische Antennen-Messung fuer Diversity-Modus.

    Ablauf:
    - MESS-PHASE  (6 Zyklen): 3×A1 + 3×A2 messen
    - BETRIEB     (60 Zyklen ≈ 15 Min): 70:30 oder 50:50
    - Nach 60 Zyklen ohne aktives QSO → neu messen
    Scoring: Modus-abhaengig (Normal=Stationsanzahl, DX=Top-5-SNR)
    Schwelle: 8% relative Differenz → 50:50, sonst 70:30
    """

    MEASURE_CYCLES = 6   # 3×A1 + 3×A2 (~1,5 Min Fenster, je even+odd pro Antenne)
    OPERATE_CYCLES = 60  # 15 Min Betrieb (vorher 80=20 Min)
    THRESHOLD = 0.08     # 8% relative Differenz fuer Antennen-Entscheidung
    # Score-Mindest-Peak: unter dem Wert (sehr schwacher Empfang) wird auf
    # 50:50 zurueckgefallen statt zwischen knappen Differenzen zu entscheiden.
    # 5.0 entspricht ~1 Station bei SNR -25 oder ~0.3 Stationen bei SNR -10.
    MIN_PEAK_SCORE = 5.0
    # Adaptiv-Stop Phase 3 (v0.91 Block 2 #8)
    EARLY_STOP_FRACTION = 2 / 3   # nach 2/3 von MEASURE_CYCLES pruefen
    EARLY_STOP_THRESHOLD = 0.15   # 15% rel. Differenz, ~2× THRESHOLD=8%
    # Such-Periode SLOT-SYNCHRON: pro Modus N Slots = ~60s (DeepSeek/Internet-Konsens)
    _SEARCH_INTERVAL_SLOTS = {"FT8": 4, "FT4": 8, "FT2": 16}
    _CYCLE_S = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}
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
    FREQ_BIN_HZ = 50         # Bin-Breite in Hz
    FREQ_MIN_HZ = 150        # Absolute Untergrenze (Hardware-Sicherheit)
    FREQ_MAX_HZ = 2800       # Absolute Obergrenze (Hardware-Sicherheit)
    FREQ_MIN_GAP_HZ = 150    # Mindestbreite einer freien Lücke
    SEARCH_MARGIN_BINS = 0   # KEINE Erweiterung — Suchbereich exakt min..max der Stationen

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
        self._search_slots_remaining = 4        # Slot-Counter (default FT8 = 4)
        self._recalc_count = 0                  # Zaehler: wie oft wurde CQ-Freq neu berechnet
        self._was_early_stopped = False         # Adaptiv-Stop-Flag (Cache-Schutz, v0.91 #8)

    def can_measure(self, station_count: int = 0) -> bool:
        """Phase 3 darf immer starten (v0.93).

        Frueher: ``>= MIN_MEASURE_STATIONS = 5`` blockte FT2-Pipelines mit
        duenner Stations-Dichte. Mit Score-basiertem Median (Mod 4) und
        ``MIN_PEAK_SCORE``-Fallback in ``_evaluate`` ist die Schwelle
        intrinsisch — kein Pre-Block mehr noetig. Aufrufer-Kompatibilitaet
        (``station_count``-Argument) bleibt erhalten, wird ignoriert.
        """
        return True

    @property
    def _early_stop_at(self) -> int:
        """Step ab dem Frueh-Stop geprueft wird (2/3 von MEASURE_CYCLES).

        FT8: 4, FT4: 8, FT2: 16. Bei FT4/FT2 effektiv wirkungslos wegen
        Pattern-Periode 6 — Pre-Condition len(m1)==len(m2) verhindert Stop.
        Akzeptabel da Hobby-Use 99% FT8 (siehe record_measurement-Doc).
        """
        return int(self.MEASURE_CYCLES * self.EARLY_STOP_FRACTION)

    def choose(self) -> str:
        """Antenne fuer den naechsten Zyklus waehlen.

        In der Mess-Phase bekommt jede Antenne mindestens ein zusammenhaengendes
        Even+Odd-Paar (A1: Slots 0-1, A2: Slots 2-3) damit beide Paritaeten
        empfangen werden. Slots 4-5 sind Singles (A1=even, A2=odd) zur
        Aufrundung 3:3.
        """
        if self._phase == "measure":
            # Mess-Pattern: A1,A1,A2,A2,A1,A2 — fair 3:3, Even+Odd-Paar je Antenne
            return ("A1","A1","A2","A2","A1","A2")[self._measure_step % 6]
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
        """Modus setzen — Such-Counter neu setzen (slot-synchron ~60s).

        FT8=4 Slots, FT4=8 Slots, FT2=16 Slots → effektiv ~60s.
        Bei Mode-Wechsel HARTER RESET des Counters (DeepSeek-Empfehlung).
        Aendert NICHT _current_gap_width_hz (Sticky bleibt stabil ueber Mode-Switch).
        """
        self._mode = mode
        self._search_slots_remaining = self._SEARCH_INTERVAL_SLOTS.get(mode, 4)

    def _measure_gap_around(self, bin_idx: int) -> int:
        """Breite der freien Luecke um bin_idx im aktuellen dynamischen Suchbereich.

        Wird nach Sticky-Treffer aufgerufen, damit _current_gap_width_hz die
        echte aktuelle Lueck-Breite reflektiert (nicht den Wert von der
        urspruenglichen Auswahl). Sonst wird die +50Hz-Schwelle gegen einen
        veralteten Referenzwert verglichen.

        Bounds = aktiver Bereich +/- SEARCH_MARGIN_BINS (gleiche Logik wie
        get_free_cq_freq), gefallback auf abs_min/max wenn Histogramm leer.
        """
        if not self._freq_histogram:
            return 0
        occupied_bins = list(self._freq_histogram.keys())
        abs_min = self.FREQ_MIN_HZ // self.FREQ_BIN_HZ
        abs_max = self.FREQ_MAX_HZ // self.FREQ_BIN_HZ
        min_bin = max(abs_min, min(occupied_bins) - self.SEARCH_MARGIN_BINS)
        max_bin = min(abs_max, max(occupied_bins) + self.SEARCH_MARGIN_BINS)
        if (bin_idx in self._freq_histogram
                or bin_idx < min_bin or bin_idx > max_bin):
            return 0
        left = bin_idx
        while left - 1 >= min_bin and (left - 1) not in self._freq_histogram:
            left -= 1
        right = bin_idx
        while right + 1 <= max_bin and (right + 1) not in self._freq_histogram:
            right += 1
        return (right - left + 1) * self.FREQ_BIN_HZ

    def _score_gap(self, gap_start_bin: int, gap_len_bins: int, median_bin: int) -> float:
        """Score: hoeher = besser. Auswahl per max(score), Tiebreak per Distance zum Median.

        Lueckenbreite dominiert (1 Hz = 1 Punkt), Stationen direkt im TX-Bin kosten 100 Hz
        pro Station (schlimmste Kollision), Nachbarn in +/-1 Bin kosten 50 Hz, Nachbarn in
        +/-2 Bins kosten 25 Hz. Median-Distance ist NUR Tiebreaker (0.01).
        Bei Notfall-Lueck mit max_count>=1 erlaubt → n_self bestraft Treffer im TX-Bin.
        """
        gap_width_hz = gap_len_bins * self.FREQ_BIN_HZ
        center_bin = gap_start_bin + gap_len_bins // 2
        n_self = self._freq_histogram.get(center_bin, 0)
        n_close = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-1, +1))
        n_near = sum(self._freq_histogram.get(center_bin + d, 0) for d in (-2, +2))
        neighbor_penalty_hz = 100 * n_self + 50 * n_close + 25 * n_near
        median_distance_hz = abs(center_bin - median_bin) * self.FREQ_BIN_HZ
        return gap_width_hz - neighbor_penalty_hz - 0.01 * median_distance_hz

    def get_free_cq_freq(self) -> Optional[int]:
        """Freie CQ-Frequenz im DYNAMISCHEN Suchbereich min..max der Stationen.

        Suchbereich = min(stationen)..max(stationen) +/- SEARCH_MARGIN_BINS.
        Begründung: TX gehört dort hin wo Stationen tatsaechlich zuhoeren —
        also in den belegten Aktivitätsbereich, nicht ans stille Bandende.

        GRADUELLE LUECKEN-TOLERANZ: probiert erst 150 Hz Mindestbreite, dann
        100 Hz, dann 50 Hz. So wird bei vollem Band trotzdem die beste
        verfuegbare Position gewaehlt statt auf alter (jetzt voller) Freq
        haengen zu bleiben. Erst wenn kein einziger freier Bin existiert → None.
        """
        hist_copy = dict(self._freq_histogram)
        if not hist_copy:
            # Kein RX-Verkehr → keine Auswahl moeglich (Aufrufer behaelt aktuelle Freq)
            return None

        # Such-Range dynamisch aus aktivem Bereich + Margin
        occupied_bins = list(hist_copy.keys())
        abs_min = self.FREQ_MIN_HZ // self.FREQ_BIN_HZ
        abs_max = self.FREQ_MAX_HZ // self.FREQ_BIN_HZ
        min_bin = max(abs_min, min(occupied_bins) - self.SEARCH_MARGIN_BINS)
        max_bin = min(abs_max, max(occupied_bins) + self.SEARCH_MARGIN_BINS)

        # Median ueber alle aktiven Stationen (Suchbereich-Filter unnötig, alle drin)
        all_freqs = []
        for bin_idx, count in hist_copy.items():
            freq = bin_idx * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2
            all_freqs.extend([freq] * count)
        median_freq = statistics.median(all_freqs)
        median_bin = int(median_freq // self.FREQ_BIN_HZ)

        # Stufenweise Lueck-Toleranz fuer volles Band:
        # (max_count_per_bin, min_gap_bins)
        # Stufe 1-3: nur echte Leerstellen (count=0), Breite reduziert
        # Stufe 4-5: schwach belegte Bins (count<=1) als Lueck akzeptieren
        # Score bestraft Stationen im eigenen Bereich, daher landet TX trotzdem
        # auf der ruhigsten Position
        SEARCH_STAGES = [(0, 3), (0, 2), (0, 1), (1, 3), (1, 2)]
        gaps = []
        used_max_count, used_min_bins = 0, 0
        for try_max_count, try_min_bins in SEARCH_STAGES:
            gaps = []
            current_gap_start = None
            current_gap_len = 0
            for b in range(min_bin, max_bin + 1):
                if hist_copy.get(b, 0) <= try_max_count:
                    if current_gap_start is None:
                        current_gap_start = b
                    current_gap_len += 1
                else:
                    if current_gap_len >= try_min_bins:
                        gaps.append((current_gap_start, current_gap_len))
                    current_gap_start = None
                    current_gap_len = 0
            if current_gap_len >= try_min_bins:
                gaps.append((current_gap_start, current_gap_len))
            if gaps:
                used_max_count, used_min_bins = try_max_count, try_min_bins
                break

        if not gaps:
            # Selbst mit Toleranz keine Lueck → Band wirklich dicht
            return None

        if used_max_count > 0 or used_min_bins < 3:
            print(f"[CQ-Freq] Band voll → Notfall-Toleranz: "
                  f"max {used_max_count} Stat./Bin, min {used_min_bins*self.FREQ_BIN_HZ} Hz Breite")

        # Score-basierte Auswahl (max statt min)
        best_gap = max(gaps, key=lambda g: self._score_gap(g[0], g[1], median_bin))
        best_width_hz = best_gap[1] * self.FREQ_BIN_HZ
        center_bin = best_gap[0] + best_gap[1] // 2
        freq_hz = center_bin * self.FREQ_BIN_HZ + self.FREQ_BIN_HZ // 2

        # Sticky: nur wechseln wenn signifikant breiter ODER aktuelle Lueck unbrauchbar
        # ODER aktuelle Frequenz ausserhalb des dynamischen Suchbereichs (Drift-Schutz).
        # WICHTIG: Schwelle "current_unbrauchbar" matched die Kollisions-Schwelle
        # in update_proposed_freq (n_direct >= 2 ODER n_in_band >= 3) — sonst
        # erkennt der Kollisions-Pfad was der Sticky-Pfad ueberstimmt.
        if self._cq_freq_hz is not None and self._current_gap_width_hz > 0:
            current_bin = self._cq_freq_hz // self.FREQ_BIN_HZ
            hist = self._freq_histogram
            n_direct = sum(hist.get(current_bin + d, 0) for d in (-1, +1))
            n_in_band = sum(hist.get(current_bin + d, 0) for d in (-2, -1, 0, +1, +2))
            current_unbrauchbar = (n_direct >= 2 or n_in_band >= 3)
            search_min_hz = min_bin * self.FREQ_BIN_HZ
            search_max_hz = (max_bin + 1) * self.FREQ_BIN_HZ
            aktuelle_im_suchbereich = (
                search_min_hz <= self._cq_freq_hz <= search_max_hz
            )
            significantly_better = (best_width_hz > self._current_gap_width_hz + 50)
            if aktuelle_im_suchbereich and not current_unbrauchbar and not significantly_better:
                # Sticky-Hit: aktuelle Lueck-Breite refreshen, sonst veralteter Vergleich
                self._current_gap_width_hz = self._measure_gap_around(current_bin)
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
    def seconds_until_search(self) -> int:
        """Sekunden bis zur naechsten Such-Aktion (slot-synchron berechnet).

        = remaining_slots * cycle_s. Wert friert ein bei App-Pause (gut so).
        """
        cycle_s = self._CYCLE_S.get(getattr(self, '_mode', 'FT8'), 15.0)
        return max(0, int(self._search_slots_remaining * cycle_s))

    def tick_slot(self) -> bool:
        """Pro Slot-Ende aufrufen. Returnt True wenn Such-Counter abgelaufen ist
        (Aufrufer triggert dann update_proposed_freq).
        """
        self._search_slots_remaining -= 1
        if self._search_slots_remaining <= 0:
            self._search_slots_remaining = self._SEARCH_INTERVAL_SLOTS.get(
                getattr(self, '_mode', 'FT8'), 4
            )
            return True
        return False

    def reset_search_counter(self) -> None:
        """Such-Counter auf Vollwert zuruecksetzen — bei aktivem QSO pro Slot
        aufzurufen, damit nach QSO-Ende wieder volle ~60s Karenzzeit verfuegbar
        sind und kein Mid-QSO-Frequenzsprung passiert.
        """
        self._search_slots_remaining = self._SEARCH_INTERVAL_SLOTS.get(
            getattr(self, '_mode', 'FT8'), 4
        )

    def update_proposed_freq(self, qso_active: bool = False):
        """Vorgeschlagene TX-Frequenz aktualisieren — slot-getriggert von mw_cycle.

        QSO-Schutz: kein Wechsel waehrend aktivem QSO.
        Sonst: get_free_cq_freq() ruft, Sticky-Logik in dort entscheidet ob bleiben
        oder wechseln.
        """
        if qso_active and self._cq_freq_hz is not None:
            return

        old_freq = self._cq_freq_hz
        self.get_free_cq_freq()
        self._recalc_count += 1
        if old_freq is None:
            if self._cq_freq_hz:
                print(f"[CQ-Freq] #{self._recalc_count} Erste Berechnung: →{self._cq_freq_hz}Hz")
        elif self._cq_freq_hz != old_freq:
            print(f"[CQ-Freq] #{self._recalc_count} Wechsel: {old_freq}Hz→{self._cq_freq_hz}Hz")
        else:
            print(f"[CQ-Freq] #{self._recalc_count} Bestaetigt: {self._cq_freq_hz}Hz")

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
        """Score nach Messzyklus einpflegen — evaluiert nach MEASURE_CYCLES Messungen.

        Args:
            ant: "A1" oder "A2"
            score: ``sum(snr+30)`` ueber alle dekodierten Stationen des Slots —
                kontinuierlicher Wert, treibt die Messung (v0.93).
            station_count: Legacy-Argument, wird ignoriert.
            avg_snr: Legacy-Argument, wird ignoriert.
            dx_weak_count: Legacy-Argument, wird ignoriert.

        Adaptiv-Stop (v0.91 #8): Nach 2/3 der Mess-Phase pruefen ob rel_diff
        bereits klar (>=15%). Spart ~30s bei eindeutigen Verhaeltnissen.

        Cancel-Schutz: record_measurement wird vom mw_cycle/mw_radio-Pfad
        bei Cancel/Phase-Wechsel nicht mehr aufgerufen (Phase=operate gesetzt).
        Daher kein internes _cancelled-Flag noetig.

        FT4/FT2-Hinweis: Mess-Pattern hat Periode 6. Bei FT4 (MEASURE_CYCLES=12,
        early_stop_at=8) ergibt sich 5:3 Verteilung statt balanciert — Pre-
        Condition len(m1)==len(m2) verhindert Stop. Effektiv profitiert nur
        FT8 von #8. Akzeptabel da Hobby-Use 99% FT8 (R1-bestaetigt).
        """
        if self._phase != "measure":
            return

        # Score (sum(snr+30)) speichern — kontinuierlich, robust auch bei
        # 1-2 Stationen pro Slot (FT2-Dichte). Ersetzt die diskreten
        # station_count/dx_weak_count Werte aus v0.92 (R1 Mod 4).
        self._measurements[ant].append(float(score))

        self._measure_step += 1

        # Adaptiv-Stop Phase 3 (v0.91 Block 2 #8) — nur wenn balanciert
        if (self._measure_step == self._early_stop_at
                and len(self._measurements["A1"]) == len(self._measurements["A2"])
                and len(self._measurements["A1"]) >= 2):
            if self._check_phase3_early_stop():
                return  # _evaluate wurde in _check aufgerufen

        if self._measure_step >= self.MEASURE_CYCLES:
            self._evaluate()

    def _check_phase3_early_stop(self) -> bool:
        """Pruefen ob rel-Differenz >=15% nach 2/3 der Mess-Phase.

        Bei Stop: _was_early_stopped=True, _evaluate() aufgerufen, ratio +
        dominant gesetzt. mw_cycle.py darf save_ratio() bei diesem Flag NICHT
        aufrufen (Cache-Schutz R1.4) — Adaptiv-Stop-Ratios sollen nicht
        persistiert werden weil sie auf weniger Messdaten basieren.

        Returns: True wenn Stop, False sonst.
        """
        m1 = self._measurements["A1"]
        m2 = self._measurements["A2"]
        s1 = statistics.median(m1)
        s2 = statistics.median(m2)
        peak = max(s1, s2)
        if peak <= self.MIN_PEAK_SCORE:
            return False

        rel_diff = abs(s1 - s2) / peak

        import time
        ts = time.strftime("%H:%M:%S")

        if rel_diff < self.EARLY_STOP_THRESHOLD:
            print(f"[{ts}] [Diversity] Adaptiv-Stop-Check nach {self._measure_step} Zyklen — "
                  f"rel_diff={rel_diff:.1%} < {self.EARLY_STOP_THRESHOLD:.0%} → weiter")
            return False

        # Stop! _evaluate triggern + Flag setzen
        print(f"[{ts}] [Diversity] Adaptiv-Stop nach {self._measure_step} Zyklen — "
              f"rel_diff={rel_diff:.1%} >= {self.EARLY_STOP_THRESHOLD:.0%}, ~30s gespart, NICHT gecached")
        self._was_early_stopped = True
        self._evaluate()
        return True

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
        self._was_early_stopped = False  # Cache-Schutz Flag bei Re-Measure ruecksetzen

    def on_band_change(self):
        """Bandwechsel → Neueinmessung starten."""
        self.reset()
        print("[Diversity] Bandwechsel — Neueinmessung gestartet (6 Zyklen)")

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
        # Pre-v0.90 Mess-Pattern war 4xA1 + 2xA2 (struktureller Bias zu ANT1).
        # Seit v0.90 fair 3:3 — Median-Robustheit beider Antennen gleich.
        m1 = self._measurements["A1"]
        m2 = self._measurements["A2"]

        # Median pro Antenne (robust gegen Ausreisser)
        s1 = statistics.median(m1) if m1 else 0.0
        s2 = statistics.median(m2) if m2 else 0.0
        peak = max(s1, s2)

        diff = 0.0
        if peak <= self.MIN_PEAK_SCORE:
            # Zu wenig Daten fuer zuverlaessige Entscheidung (sehr schwacher Empfang)
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
