"""SimpleFT8 Diversity Controller — Antennen-Pattern + CQ-Frequenzwahl.

P34-Stufe2 (v0.97.19, 2026-05-13): Statik-Mess-Pipeline (Phase 3) komplett
entfernt. Die Ratio-Berechnung uebernimmt jetzt der
``DynamicDiversityController`` (Live-Mess slot-fuer-slot, 5er-Schiebepuffer).

Hier verbleibt:
- Modul-Helper ``compute_slot_score()`` und ``evaluate_ratio()`` (von
  Dynamic-Pipeline genutzt).
- ``DiversityController``: Pattern-Generator fuer 50:50/70:30/30:70 RX-
  Antennenwechsel und CQ-Frequenz-Such-System (Histogramm + Sticky-Gap +
  graduelle Lücken-Toleranz).

NICHT mehr hier: Mess-Phase, _phase-State-Machine, _measurements, 1h-Re-
Mess-Frist, MessStatusDialog-Coupling, Settings-Toggle.
"""

import statistics
from typing import Optional


# ── Modul-Helper (P34): von DynamicDiversityController genutzt ───────

def compute_slot_score(messages) -> float:
    """Score eines Slots: sum(max(0, snr+30)) ueber Stationen mit snr > -20.

    Identische Formel wie historisch in der Statik-Mess-Phase. Wird seit
    P34-Stufe2 ausschliesslich von ``DynamicDiversityController`` (via
    ``mw_cycle._on_cycle_decoded``) aufgerufen.
    """
    valid = [m for m in (messages or [])
             if m.snr is not None and m.snr > -20]
    return sum(max(0.0, float(m.snr + 30)) for m in valid) if valid else 0.0


def evaluate_ratio(median_a1: float, median_a2: float,
                    threshold: float = 0.08,
                    min_peak: float = 5.0) -> tuple[str, Optional[str]]:
    """Verhaeltnis-Entscheidung aus 2 Medianen.

    Liefert ``(ratio, dominant)``:
      - "50:50", None  → Differenz < threshold oder peak <= min_peak
      - "70:30", "A1"  → ANT1 dominiert
      - "30:70", "A2"  → ANT2 dominiert
    """
    peak = max(median_a1, median_a2)
    if peak <= min_peak:
        return "50:50", None
    rel_diff = abs(median_a1 - median_a2) / peak
    if rel_diff < threshold:
        return "50:50", None
    return ("70:30", "A1") if median_a1 >= median_a2 else ("30:70", "A2")


class DiversityController:
    """Antennen-Pattern-Generator + CQ-Frequenz-Such.

    P34-Stufe2: Reine Betriebs-Logik. KEINE Statik-Mess-Phase mehr. Die
    Felder ``ratio`` und ``dominant`` werden vom
    ``DynamicDiversityController`` (Live-Mess) gesetzt.
    """

    THRESHOLD = 0.08     # 8% relative Differenz fuer Ratio-Entscheidung
    MIN_PEAK_SCORE = 5.0  # Score-Mindest-Peak fuer Ratio-Entscheidung
    # Such-Periode SLOT-SYNCHRON: pro Modus N Slots = ~60s
    _SEARCH_INTERVAL_SLOTS = {"FT8": 4, "FT4": 8, "FT2": 16}
    _CYCLE_S = {"FT8": 15.0, "FT4": 7.5, "FT2": 3.8}
    # 67:33 Pattern (6 Slots, endlos nahtlos wiederholbar)
    # A2 bekommt abwechselnd Even+Odd durch Einzelslots an Pos 2+5
    # Max 2 hintereinander, kein Sprung am Loop-Uebergang
    _PAT_70_A1 = ("A1", "A1", "A2", "A1", "A1", "A2")  # 4×A1, 2×A2 = 67:33
    _PAT_70_A2 = ("A2", "A2", "A1", "A2", "A2", "A1")  # 4×A2, 2×A1 = 67:33

    # CQ-Frequenzwahl: 50-Hz-Histogramm der belegten Subfrequenzen
    FREQ_BIN_HZ = 50         # Bin-Breite in Hz
    FREQ_MIN_HZ = 150        # Absolute Untergrenze (Hardware-Sicherheit)
    FREQ_MAX_HZ = 2800       # Absolute Obergrenze (Hardware-Sicherheit)
    FREQ_MIN_GAP_HZ = 150    # Mindestbreite einer freien Lücke
    SEARCH_MARGIN_BINS = 0   # KEINE Erweiterung — Suchbereich exakt min..max der Stationen

    def __init__(self, scoring_mode: str = "normal"):
        self._scoring_mode = scoring_mode  # "normal" oder "dx"
        self.reset()
        self.set_mode("FT8")  # Default — von mw_radio.py spaeter ueberschrieben

    @property
    def scoring_mode(self) -> str:
        """Aktueller Scoring-Modus: 'normal' oder 'dx'."""
        return self._scoring_mode

    @scoring_mode.setter
    def scoring_mode(self, mode: str):
        if mode in ("normal", "dx"):
            self._scoring_mode = mode

    def reset(self):
        """Histogramm + CQ-Such-Counter + Ratio auf Initialwerte.

        P34-Stufe2: kein _phase / _measurements / _last_measured_at mehr.
        """
        self.ratio = "50:50"
        self.dominant = None   # "A1", "A2", oder None
        self._operate_cycles = 0
        self._freq_histogram = {}  # bin_idx → Anzahl Stationen
        self._cq_freq_hz: Optional[int] = None
        self._current_gap_width_hz: int = 0
        self._search_slots_remaining = 4  # Slot-Counter (default FT8 = 4)
        self._recalc_count = 0  # Zaehler: wie oft wurde CQ-Freq neu berechnet

    def on_operate_cycle(self):
        """Pro Betriebszyklus aufrufen — inkrementiert Pattern-Counter."""
        self._operate_cycles += 1

    def choose(self) -> str:
        """Antenne fuer den naechsten Zyklus (50:50/70:30/30:70 Pattern).

        P34-Stufe2: nur noch Operate-Pattern (Mess-Phase existiert nicht
        mehr).
        """
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
