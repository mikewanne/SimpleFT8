"""SimpleFT8 Diversity Controller — periodische Antennen-Messung."""


class DiversityController:
    """Periodische Antennen-Messung fuer Diversity-Modus.

    Ablauf:
    - MESS-PHASE  (2 Zyklen): ANT1 dann ANT2 messen
    - BETRIEB     (40 Zyklen ≈ 10 Min): 70:30 oder 50:50
    - Nach 40 Zyklen ohne aktives QSO → neu messen
    Score = Summe (snr+30) aller dekodierten Stationen
    Δ < 15% → 50:50, sonst bessere Antenne auf 70%
    """

    MEASURE_CYCLES = 8   # 4×A1 + 4×A2 (~2 Min Fenster, je even+odd pro Antenne)
    OPERATE_CYCLES = 80  # 20 Min Betrieb mit guter Antenne
    _PAT_70_A1 = ("A1","A1","A2","A1","A1","A2","A1","A1","A2","A1")  # 7×A1, 3×A2
    _PAT_70_A2 = ("A2","A2","A1","A2","A2","A1","A2","A2","A1","A2")  # 7×A2, 3×A1

    def __init__(self):
        self.reset()

    def reset(self):
        self._phase = "measure"
        self._measure_step = 0
        self._scores = {"A1": 0.0, "A2": 0.0}
        self._operate_cycles = 0
        self.ratio = "50:50"
        self.dominant = None  # "A1", "A2", oder None

    def choose(self) -> str:
        """Antenne fuer den naechsten Zyklus waehlen."""
        if self._phase == "measure":
            return "A2" if self._measure_step % 2 == 0 else "A1"  # A2,A1,A2,A1 (A1 war init)
        if self.ratio == "70:30":
            return self._PAT_70_A1[self._operate_cycles % 10]
        if self.ratio == "30:70":
            return self._PAT_70_A2[self._operate_cycles % 10]
        return ("A1", "A2")[self._operate_cycles % 2]  # 50:50

    def record_measurement(self, ant: str, score: float):
        """Score nach Messzyklus einpflegen — evaluiert nach 2 Messungen."""
        if self._phase != "measure":
            return
        self._scores[ant] += score   # akkumulieren: even+odd pro Antenne
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
        self._scores = {"A1": 0.0, "A2": 0.0}

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
        s1, s2 = self._scores["A1"], self._scores["A2"]
        total = s1 + s2
        diff = 0.0
        if total <= 0:
            self.ratio = "50:50"
            self.dominant = None
        else:
            diff = abs(s1 - s2) / total
            if diff < 0.15:
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
        print(f"[Diversity] Messung: A1={s1:.1f} A2={s2:.1f} diff={diff:.3f} → {self.ratio} "
              f"(dominant: {self.dominant})")
