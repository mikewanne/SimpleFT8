# P34.DIVERSITY-DYNAMIC — V3 (Final-Spec, Compact-fest)

**Status:** V3 — Verbindliche Spezifikation nach V1-NEU + V2 + R1-Review
**Datum:** 2026-05-11
**Workflow:** V3 → Mike-Freigabe → Plan-Mode → Code → Tests → Final-R1 → Field-Test

---

## 0. Einstieg fuer neue KI (Compact-Recovery)

Falls Compact diese Session unterbrochen hat: lies **NUR diese V3-Datei**.
V1-NEU und V2 sind im Archiv (`_OLD_parallel.md` sind verworfene Vorgaenger,
nicht aktuell). Alle Mike-Entscheidungen und R1-Findings sind hier
eingearbeitet — keine offenen Fragen mehr.

### 0.1 Mike's Vision in 2 Saetzen

> *„Antennen-Verhaeltnis im laufenden Betrieb live anpassen, statt einmal pro
> Stunde 90 Sekunden UI zu blockieren. ENTWEDER-ODER mit Statik: Toggle AN =
> nur Dynamic, Toggle AUS = nur Statik."*

### 0.2 Architektur-Kern

**EINE Pipeline gleichzeitig aktiv:**

- Toggle AUS → Statik wie heute (90s-Init, 1h-Re-Mess, UI-Sperren)
- Toggle AN  → Dynamic live (5er-Schiebepuffer pro Antenne, slot-fuer-slot,
  keine UI-Sperren, Statik komplett pausiert)

---

## 1. Akzeptanzkriterien (verbindlich, 16 ACs)

1. **AK1 — Statik 100% unangetastet bei Toggle AUS:**
   Bestehende Tests in `tests/test_diversity*.py` bleiben gruen ohne
   Code-Anpassung an `core/diversity.py` Mess-Pipeline.

2. **AK2 — `core/diversity.py` Aenderungen minimal:**
   - 2 Helper-Funktionen `compute_slot_score()` + `evaluate_ratio()`
     auf Modul-Ebene (NICHT in der Klasse).
   - `DiversityController._evaluate()` ruft `evaluate_ratio()` auf
     (Refactor, keine Verhaltensaenderung).
   - `DiversityController.should_remeasure()` bekommt einen Check:
     wenn `self.dynamic_active` True → returnt False.
   - Neue Property `dynamic_active` (default False, mit Setter).
   - Neues Signal `scoring_mode_changed = Signal(str)`, vom Setter emittiert.
   - Keine weiteren Aenderungen.

3. **AK3 — Toggle-Verhalten ENTWEDER-ODER:**
   - Toggle AUS → Statik aktiv, `DynamicDiversityController._active=False`,
     `DiversityController.dynamic_active=False`.
   - Toggle AN → Statik schlaeft, `DynamicDiversityController._active=True`,
     `DiversityController.dynamic_active=True`.

4. **AK4 — Toggle AUS→AN:**
   - 50:50-Reset (`DiversityController.ratio="50:50"`, `dominant=None`).
   - Schieberegister leer.
   - Falls Statik gerade in Phase=measure: **sofort abbrechen** (R1-Q7
     Variante B):
     - `_diversity_ctrl._phase = "operate"`
     - `_diversity_ctrl._last_measured_at = time.time()`
     - GUI-Lock aufheben (`_set_cq_locked(False)`, `_set_gain_measure_lock(False)`)

5. **AK5 — Toggle AN→AUS:**
   - Aktuelles Verhaeltnis bleibt (von Dynamic zuletzt gesetzt).
   - `DynamicDiversityController._active=False`.
   - `DiversityController.dynamic_active=False`.
   - **`_last_measured_at = time.time()` setzen** (Mike-Entscheidung B,
     verhindert sofortige Re-Mess direkt nach Toggle-AUS).

6. **AK6 — Schieberegister:**
   `collections.deque(maxlen=5)` pro Antenne. FIFO.

7. **AK7 — Auswertungs-Gate:**
   `_evaluate()` nur wenn beide Buffer voll (je 5 Werte).

8. **AK8 — Pro-Slot-Auswertung:**
   Sobald Buffer voll, nach jedem neuen Slot pruefen + ggf. Ratio setzen.

9. **AK9 — Score-Formel identisch zur Statik:**
   `compute_slot_score(messages)` = `sum(max(0, snr+30))` ueber Stationen
   mit `snr > -20`. Helper auf Modul-Ebene, von beiden Pipelines genutzt.

10. **AK10 — Reset-Trigger bei Dynamic AN:**
    - Bandwechsel
    - Modus-Wechsel (FT8↔FT4↔FT2)
    - scoring_mode-Wechsel (Standard↔DX) — ueber Signal
    - Diversity an→aus (Mode → Normal)
    → Buffer leer + Ratio auf 50:50.

11. **AK11 — Kein Reset bei:**
    - OMNI-CQ Start/Stop
    - QSO Start/Stop
    - Toggle AN→AUS (Ratio bleibt nur Modul aus, kein Reset)

12. **AK12 — Statik-1h-Frist bei Dynamic AN unterdrueckt:**
    `should_remeasure()` returnt False wenn `dynamic_active=True`.

13. **AK13 — Keine Persistenz:**
    - Buffer RAM-only (`deque(maxlen=5)`)
    - Toggle RAM-only-Property in `Settings`: `_dynamic_enabled = False`
      direkt im `__init__`, NICHT in `_data`, nicht in `save()` schreiben,
      nicht in `load()` lesen.

14. **AK14 — Anzeige im Antennen-Panel (R1-Q3 B.1.a):**
    Verhaeltnis-Label im Antennen-Panel wird **blau gefaerbt** (`#3399CC`)
    wenn `dynamic_active=True` UND Buffer voll. Sonst Standard-Farbe.
    Statusbar bleibt unangetastet.

15. **AK15 — Threading mit normalem `Lock` (R1-Q6):**
    `threading.Lock` (nicht `RLock`) im `DynamicDiversityController`.
    Schuetzt Buffer-Operationen + Active-Flag. Signal-Emit via
    `Qt.QueuedConnection`.

16. **AK16 — Hardware-Schutz ANT1=TX:**
    `radio.set_tx_antenna("ANT1")` unangetastet. Verhaeltnis nur RX.

---

## 2. Code-Aenderungen (mit Datei:Zeile)

### 2.1 `core/diversity.py` — Modul-Funktionen + minimaler Klassen-Patch

**Neue Modul-Funktionen (nach Z.20, vor `class DiversityController`):**

```python
def compute_slot_score(messages) -> float:
    """Score eines Slots: sum(max(0, snr+30)) ueber Stationen mit snr > -20.

    Gleiche Formel wie mw_cycle._handle_diversity_measure (Z.239-241).
    Beide Pipelines (Statik + Dynamic) nutzen diese Funktion.
    """
    valid = [m for m in (messages or [])
             if m.snr is not None and m.snr > -20]
    return sum(max(0.0, float(m.snr + 30)) for m in valid) if valid else 0.0


def evaluate_ratio(median_a1: float, median_a2: float,
                    threshold: float = 0.08,
                    min_peak: float = 5.0) -> tuple[str, str | None]:
    """Verhaeltnis-Entscheidung aus 2 Medianen. Gleicher Algorithmus wie
    DiversityController._evaluate() (Z.537-562).
    """
    peak = max(median_a1, median_a2)
    if peak <= min_peak:
        return "50:50", None
    rel_diff = abs(median_a1 - median_a2) / peak
    if rel_diff < threshold:
        return "50:50", None
    return ("70:30", "A1") if median_a1 >= median_a2 else ("30:70", "A2")
```

**Klassen-Aenderung 1: `dynamic_active`-Property (nach Z.70 `scoring_mode`-Setter):**

```python
@property
def dynamic_active(self) -> bool:
    """True wenn DynamicDiversityController gerade aktiv ist.
    Unterdrueckt statische Re-Mess (siehe should_remeasure)."""
    return getattr(self, '_dynamic_active', False)

@dynamic_active.setter
def dynamic_active(self, value: bool):
    self._dynamic_active = bool(value)
```

`__init__` muss `self._dynamic_active = False` setzen (vor `self.reset()`).

**Klassen-Aenderung 2: `scoring_mode_changed`-Signal:**

`DiversityController` muss von `QObject` erben (aktuell normale Klasse).
**Alternative ohne Qt-Dependency:** wir setzen den `scoring_mode`-Setter
direkt als Callback-Liste statt Signal:

```python
# Im DiversityController.__init__:
self._scoring_mode_listeners: list = []  # Callable[[str], None]

# Im scoring_mode.setter:
@scoring_mode.setter
def scoring_mode(self, mode: str):
    if mode in ("normal", "dx"):
        old = self._scoring_mode
        self._scoring_mode = mode
        if old != mode:
            for cb in self._scoring_mode_listeners:
                try:
                    cb(mode)
                except Exception as exc:
                    print(f"[Diversity] scoring_mode listener error: {exc}")
```

→ `DynamicDiversityController.__init__` registriert sich:
```python
self._diversity_ctrl._scoring_mode_listeners.append(
    lambda mode: self.reset()
)
```

**Begruendung:** Vermeidet `DiversityController` zur QObject zu machen
(verhindert Folge-Refactoring in Tests etc). Callback-Liste ist KISS, einfach
zu testen, kein Qt-Dependency.

**Klassen-Aenderung 3: `should_remeasure()` Z.478 (Dynamic-Check):**

```python
def should_remeasure(self, qso_active: bool, cq_active: bool = False) -> bool:
    if self.dynamic_active:  # NEU: Dynamic AN → keine Statik-Re-Mess
        return False
    if self._phase != "operate":
        return False
    # ... Rest unveraendert
```

**Klassen-Aenderung 4: `_evaluate()` Z.536-569 (Refactor auf Helper):**

```python
def _evaluate(self):
    m1 = self._measurements["A1"]
    m2 = self._measurements["A2"]
    s1 = statistics.median(m1) if m1 else 0.0
    s2 = statistics.median(m2) if m2 else 0.0
    new_ratio, new_dominant = evaluate_ratio(
        s1, s2, threshold=self.THRESHOLD, min_peak=self.MIN_PEAK_SCORE
    )
    self.ratio = new_ratio
    self.dominant = new_dominant
    self._phase = "operate"
    self._operate_cycles = 0
    self._last_measured_at = time.time()
    mode_tag = "DX" if self._scoring_mode == "dx" else "Normal"
    print(f"[Diversity] Messung ({mode_tag}): A1={s1:.1f} A2={s2:.1f} "
          f"→ {self.ratio} (dominant: {self.dominant}, Werte: A1={m1} A2={m2})")
```

→ 26 Zeilen reduziert auf 17, exakt gleiches Verhalten.

### 2.2 `core/dynamic_diversity.py` — NEU

```python
"""SimpleFT8 DynamicDiversityController — Live-Antennen-Verhaeltnis-Anpassung.

ENTWEDER-ODER zur statischen DiversityController-Pipeline:
- Toggle AUS → Statik laeuft, DynamicDiversityController._active=False
- Toggle AN  → Dynamic uebernimmt, Statik-Re-Mess unterdrueckt

Slot-fuer-Slot-Erfassung in 5er-Schiebepuffer pro Antenne. Auswertung nach
jedem Slot (sobald beide Puffer voll, je 5 Werte). Schwelle 8% identisch
zur Statik. Median-basiert (robust gegen Ausreisser).

Lifecycle (verbindlich):
- activate()     → _active=True, 50:50-Reset, Buffer leer, ggf. Statik-Mess abbrechen
- deactivate()   → _active=False, Ratio bleibt, _last_measured_at refresh
- record_slot(ant, score) → in Buffer schieben, ggf. _evaluate()
- reset()        → Buffer leer, Ratio 50:50 (bei Band/Mode/scoring-Wechsel)

Thread-Safety: threading.Lock schuetzt Buffer + Active-Flag. Signal-Emit
mit Qt.QueuedConnection an GUI-Thread.
"""
from __future__ import annotations

import collections
import logging
import statistics
import threading
import time
from PySide6.QtCore import QObject, Signal

from core.diversity import evaluate_ratio  # Modul-Funktion

logger = logging.getLogger(__name__)


class DynamicDiversityController(QObject):
    BUFFER_SIZE = 5
    THRESHOLD = 0.08
    MIN_PEAK_SCORE = 5.0

    ratio_changed_dynamic = Signal(str)  # neue Ratio z.B. "70:30"

    def __init__(self, diversity_ctrl):
        super().__init__()
        self._diversity_ctrl = diversity_ctrl
        self._lock = threading.Lock()
        self._buffer = {
            "A1": collections.deque(maxlen=self.BUFFER_SIZE),
            "A2": collections.deque(maxlen=self.BUFFER_SIZE),
        }
        self._active = False
        # scoring_mode-Wechsel → reset
        diversity_ctrl._scoring_mode_listeners.append(
            lambda mode: self.reset()
        )

    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        """Toggle AUS→AN: 50:50-Reset, Buffer leer, ggf. Statik-Mess abbrechen."""
        with self._lock:
            self._active = True
            self._buffer["A1"].clear()
            self._buffer["A2"].clear()
            self._diversity_ctrl.dynamic_active = True
            # AK4: Falls Statik gerade misst, abbrechen
            if self._diversity_ctrl.phase == "measure":
                self._diversity_ctrl._phase = "operate"
                self._diversity_ctrl._last_measured_at = time.time()
                logger.info("[Dynamic] Statik-Mess-Phase abgebrochen")
            # 50:50-Reset
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
        logger.info("[Dynamic] Aktiviert (Buffer leer, Ratio 50:50)")

    def deactivate(self) -> None:
        """Toggle AN→AUS: aktuelles Ratio bleibt, _last_measured_at refresh
        (verhindert sofortige Statik-Re-Mess)."""
        with self._lock:
            self._active = False
            self._diversity_ctrl.dynamic_active = False
            self._diversity_ctrl._last_measured_at = time.time()  # Mike B-Option
        logger.info("[Dynamic] Deaktiviert (Ratio bleibt, Statik-Frist refresht)")

    def reset(self) -> None:
        """Buffer leer + 50:50. Bei Band/Modus/scoring-Wechsel."""
        with self._lock:
            self._buffer["A1"].clear()
            self._buffer["A2"].clear()
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
        logger.info("[Dynamic] Reset (Buffer leer, Ratio 50:50)")

    def record_slot(self, ant: str, score: float) -> None:
        """Ein Slot-Score in Buffer schieben. Wenn beide voll: auswerten."""
        if not self._active:
            return
        if ant not in ("A1", "A2"):
            return
        with self._lock:
            self._buffer[ant].append(float(score))
            if (len(self._buffer["A1"]) == self.BUFFER_SIZE
                    and len(self._buffer["A2"]) == self.BUFFER_SIZE):
                self._evaluate_locked()

    def _evaluate_locked(self) -> None:
        """Auswertung — MUSS unter Lock laufen. Setzt ggf. neues Ratio."""
        m1 = statistics.median(self._buffer["A1"])
        m2 = statistics.median(self._buffer["A2"])
        new_ratio, new_dominant = evaluate_ratio(
            m1, m2, threshold=self.THRESHOLD, min_peak=self.MIN_PEAK_SCORE
        )
        old_ratio = self._diversity_ctrl.ratio
        old_dominant = self._diversity_ctrl.dominant
        if new_ratio == old_ratio and new_dominant == old_dominant:
            return
        self._diversity_ctrl.ratio = new_ratio
        self._diversity_ctrl.dominant = new_dominant
        logger.info(
            "[Dynamic] Ratio-Wechsel: %s → %s (m1=%.1f m2=%.1f, "
            "diff=%.1f%%)", old_ratio, new_ratio, m1, m2,
            abs(m1 - m2) / max(m1, m2, 1.0) * 100
        )
        self.ratio_changed_dynamic.emit(new_ratio)
```

**~120 LOC. Klar, eigenstaendig, getrennte Klasse.**

### 2.3 `ui/mw_cycle.py` — Hook nach Z.97

```python
# Nach: self._handle_diversity_operate(messages, ant)  Z.97
if (self._rx_mode == "diversity"
        and was_phase == "operate"
        and getattr(self, "_dynamic_ctrl", None) is not None
        and self._dynamic_ctrl.is_active()
        and messages):
    from core.diversity import compute_slot_score
    score = compute_slot_score(messages)
    self._dynamic_ctrl.record_slot(ant, score)
```

### 2.4 `ui/mw_radio.py` — Reset-Hooks

In `set_band()` (Bandwechsel) + `set_mode()` (Modus-Wechsel) + `_enable_diversity(False)`
jeweils einfuegen:

```python
if getattr(self, "_dynamic_ctrl", None):
    self._dynamic_ctrl.reset()  # bei Band/Mode
    # ODER fuer _enable_diversity(False):
    self._dynamic_ctrl.deactivate()
```

(scoring_mode-Wechsel laeuft automatisch ueber den Callback-Listener,
kein extra Hook noetig.)

### 2.5 `ui/main_window.py` — Init + Toggle-Handler + Panel-Faerbung

**`__init__` (nach `_diversity_ctrl`-Init):**

```python
from core.dynamic_diversity import DynamicDiversityController
self._dynamic_ctrl = DynamicDiversityController(self._diversity_ctrl)
self._dynamic_ctrl.ratio_changed_dynamic.connect(
    self._on_dynamic_ratio_changed, Qt.QueuedConnection
)
```

**Neuer Slot:**

```python
@Slot(str)
def _on_dynamic_ratio_changed(self, new_ratio: str):
    """Wenn Dynamic ein neues Ratio setzt: Panel-Faerbung + Update."""
    self.control_panel.update_diversity_ratio(
        new_ratio, self._diversity_ctrl.phase,
        scoring_mode=self._diversity_ctrl.scoring_mode,
        is_dynamic=True,  # NEU: triggert Blau-Faerbung
    )
```

**Toggle-Handler (im Settings-Dialog-Apply-Pfad):**

```python
def _apply_dynamic_toggle(self, enabled: bool):
    if enabled and not self._dynamic_ctrl.is_active():
        self._dynamic_ctrl.activate()
    elif not enabled and self._dynamic_ctrl.is_active():
        self._dynamic_ctrl.deactivate()
```

### 2.6 `ui/control_panel.py` — Faerbungs-Parameter

`update_diversity_ratio()` bekommt neuen Parameter `is_dynamic=False`:

```python
def update_diversity_ratio(self, ratio, phase, *,
                            measure_step=None, measure_total=None,
                            operate_seconds_remaining=None,
                            scoring_mode="normal",
                            is_dynamic=False):  # NEU
    # ... bestehender Code ...
    if is_dynamic:
        self.label_ratio.setStyleSheet("color: #3399CC; font-weight: bold")
    else:
        self.label_ratio.setStyleSheet("")  # Standard
```

### 2.7 `config/settings.py` — RAM-only Property

In `Settings.__init__()` direkt nach `self._data = {}`:

```python
self._dynamic_enabled = False  # RAM-only, NICHT persistiert
```

Property + Setter:

```python
@property
def dynamic_diversity_enabled(self) -> bool:
    return self._dynamic_enabled

@dynamic_diversity_enabled.setter
def dynamic_diversity_enabled(self, value: bool):
    self._dynamic_enabled = bool(value)
```

**KEIN Aufruf von `self.save()`** im Setter — bewusst nicht persistiert.
`load()` muss `_dynamic_enabled` ignorieren falls in alter settings.json
faelschlich drin (defensive Migration).

### 2.8 `ui/settings_dialog.py` — Toggle + Tooltip

Im Diversity-Bereich:

```python
self.cb_dynamic = QCheckBox("Antennen-Verhaeltnis dynamisch anpassen (Testphase)")
self.cb_dynamic.setToolTip(
    "Statt 1× pro Stunde wird das Verhaeltnis im laufenden Betrieb "
    "kontinuierlich nachjustiert (~jede Minute). Nur im Diversity-Modus aktiv.\n"
    "Status wird nicht gespeichert — bei jedem App-Start aus."
)
self.cb_dynamic.setChecked(self.settings.dynamic_diversity_enabled)
# Im OK-Handler:
self.settings.dynamic_diversity_enabled = self.cb_dynamic.isChecked()
self.parent()._apply_dynamic_toggle(self.cb_dynamic.isChecked())
```

---

## 3. Test-Liste (26 Tests, R1-Vorschlag)

### 3.1 Datei: `tests/test_diversity_dynamic.py` (Unit-Tests, ~15 Tests)

| # | Name | Beschreibung |
|---|---|---|
| 1 | `test_init_defaults` | Controller erzeugt, Buffer leer, `is_active()` False |
| 2 | `test_activate_sets_active` | `activate()` setzt `_active=True` + `dynamic_active` Flag |
| 3 | `test_activate_resets_ratio` | `activate()` setzt Ratio auf 50:50 |
| 4 | `test_activate_aborts_measure_phase` | Falls `phase=="measure"`, wird auf "operate" gesetzt |
| 5 | `test_deactivate_keeps_ratio` | `deactivate()` setzt `_active=False`, Ratio bleibt |
| 6 | `test_deactivate_refreshes_remeasure_timestamp` | `_last_measured_at` neu gesetzt |
| 7 | `test_record_slot_a1` | 1 Slot für A1 → Buffer[A1] hat 1 Eintrag |
| 8 | `test_record_slot_inactive` | Wenn `_active=False`, kein Eintrag |
| 9 | `test_buffer_maxlen` | 6 Slots → nur letzte 5 bleiben |
| 10 | `test_evaluate_not_called_before_full` | 4+4 Slots → kein evaluate |
| 11 | `test_evaluate_called_when_full` | 5+5 Slots → evaluate trifft |
| 12 | `test_evaluate_70_30` | A1 stark, A2 schwach → ratio="70:30" |
| 13 | `test_evaluate_30_70` | A2 stark, A1 schwach → "30:70" |
| 14 | `test_evaluate_50_50_below_threshold` | <8% diff → "50:50" |
| 15 | `test_evaluate_50_50_below_min_peak` | Beide <5 → "50:50" |

### 3.2 Datei: `tests/test_diversity_helpers.py` (Helper, ~3 Tests)

| # | Name | Beschreibung |
|---|---|---|
| 16 | `test_compute_slot_score_basic` | Messages mit verschiedenen SNRs → korrekte Summe |
| 17 | `test_compute_slot_score_snr_filter` | SNR<=-20 wird ausgefiltert |
| 18 | `test_evaluate_ratio_thresholds` | Verschiedene Median-Paare → korrekte Entscheidung |

### 3.3 Datei: `tests/test_diversity_dynamic_integration.py` (~8 Tests)

| # | Name | Beschreibung |
|---|---|---|
| 19 | `test_reset_clears_buffer` | `reset()` leert beide Buffer, Ratio=50:50 |
| 20 | `test_scoring_mode_change_triggers_reset` | Callback ausgeloest, Buffer leer |
| 21 | `test_should_remeasure_false_when_active` | DiversityController returnt False |
| 22 | `test_should_remeasure_normal_when_inactive` | Statik-Pfad unangetastet |
| 23 | `test_static_evaluate_refactor_no_behavior_change` | Statische Tests bleiben gruen |
| 24 | `test_settings_toggle_not_persisted` | Setter setzt, `save()` schreibt nicht in JSON |
| 25 | `test_signal_emitted_on_ratio_change` | `ratio_changed_dynamic` Signal trifft 1× pro Wechsel |
| 26 | `test_thread_safety_concurrent_record` | 2 Threads rufen record_slot parallel, kein Crash |

**Mock-Strategie:** `DiversityController` per Test echt (kein Mock noetig
da kein Radio/Decoder beteiligt), `FT8Message`-Mocks fuer Messages.

---

## 4. Implementierungs-Plan (9 atomare Commits)

| # | Commit | Dateien | Inhalt | Tests |
|---|---|---|---|---|
| **C1** | Helper-Funktionen + `_evaluate()` Refactor | `core/diversity.py` | `compute_slot_score()` + `evaluate_ratio()` Modul-Funktionen + `_evaluate()` ruft Helper auf | 16-18, 23 |
| **C2** | DiversityController Hooks | `core/diversity.py` | `dynamic_active`-Property + Setter, `_scoring_mode_listeners`, `should_remeasure()` Dynamic-Check, `__init__` Init | 21-22 |
| **C3** | `core/dynamic_diversity.py` NEU | (neue Datei) | Komplette DynamicDiversityController-Klasse | 1-15 |
| **C4** | `config/settings.py` RAM-Property | `config/settings.py` | `_dynamic_enabled` + Property | 24 |
| **C5** | UI-Hooks mw_cycle + mw_radio | `ui/mw_cycle.py`, `ui/mw_radio.py` | Hook in `_on_cycle_decoded`, Reset bei Band/Mode/Diversity-aus | 19, 20, 25 |
| **C6** | main_window Init + Toggle-Handler | `ui/main_window.py` | Controller-Instanz, Signal-Connect, Toggle-Handler | (Smoke) |
| **C7** | control_panel Faerbungs-Parameter | `ui/control_panel.py` | `is_dynamic` Param, StyleSheet-Update | (Smoke) |
| **C8** | settings_dialog Toggle + Tooltip | `ui/settings_dialog.py` | QCheckBox + Connect-Logic | (Smoke) |
| **C9** | APP_VERSION + Doku-Updates | `main.py`, `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md` | Version-Bump 0.96.10 → 0.97.0, alle 4 Pflicht-Dateien | (keine Code-Tests) |

**Reihenfolge wichtig:** C1+C2 zuerst (Statik-Tests muessen weiter gruen
bleiben). Dann C3 (Dynamic-Klasse). C4-C8 in beliebiger Reihenfolge. C9 zuletzt.

**Geschaetzter Zeitaufwand ohne Workflow-Pausen: 6-8h.**

---

## 5. Field-Test-Checkliste (Mike nach Code-fertig)

Nach App-Start mit der neuen Version testen:

| # | Test | Erwartung |
|---|---|---|
| **F1** | App-Start mit Toggle AUS (Default) | 100% wie heute. Statik misst, 90s-Init, Ratio nach Mess. |
| **F2** | Toggle AN nach Init | Antennen-Panel Verhaeltnis **wird blau**, sobald Buffer voll (~3 Min). Ratio aendert sich live. |
| **F3** | Toggle AN waehrend Statik-Mess | Statik **bricht sofort ab**, Ratio sofort auf 50:50, kein UI-Sperrer mehr. |
| **F4** | Bandwechsel mit Dynamic AN | **Keine 90s-Sperre.** Ratio sofort 50:50, in ~3 Min wieder Dynamic aktiv. |
| **F5** | Modus-Wechsel (FT8→FT4) mit Dynamic AN | Wie F4. |
| **F6** | scoring_mode (Standard→DX) mit Dynamic AN | Buffer leer, Ratio 50:50, neu sammeln. |
| **F7** | 1h ohne QSO mit Dynamic AN | **Keine 90s-Statik-Re-Mess.** Dynamic bleibt aktiv. |
| **F8** | Toggle AN→AUS mid-Betrieb | Ratio bleibt beim Dynamic-Wert. Panel wird wieder weiss. **Keine sofortige Statik-Mess** (Mike B-Option). |
| **F9** | OMNI-CQ + Dynamic AN | OMNI laeuft normal, Dynamic sammelt im Hintergrund. |
| **F10** | App-Quit + Neustart | Toggle ist AUS (nicht persistiert), Statik laeuft. |
| **F11** | Toggle AN bei Normal-Mode (kein Diversity) | Kein Crash, aber Dynamic ist faktisch wirkungslos. |
| **F12** | Lange Beobachtung (mehrere Stunden, Dynamic AN) | Ratio passt sich Wetter/Tages-Effekten an, gleitend nach jedem Slot. |

**Bestanden wenn:** F1-F8 sauber. F9-F12 als Beobachtung, kein Bug-Kriterium.

---

## 6. 1-Seiten-Zusammenfassung fuer Mike (einfache Sprache)

### Was wir bauen

Ein zweites System fuer das Antennen-Verhaeltnis. Heute misst die App
einmal am Anfang + alle Stunde nochmal — das blockiert die UI fuer
90 Sekunden. Mit dem neuen System laeuft die Anpassung **live im
Hintergrund**, Slot fuer Slot.

### Wie sieht das aus

Du kriegst einen Schalter in den Einstellungen:
**„Antennen-Verhaeltnis dynamisch anpassen (Testphase)"**

- **Aus** = Status quo (Statik wie heute)
- **An** = Neue Live-Anpassung

Wenn der Schalter an ist:
- Antennen-Panel zeigt das Verhaeltnis **in Blau** (= dynamisch gesetzt)
- Kein 90-Sek-Hang mehr alle Stunde
- Wenn sich Bedingungen aendern (Wind, Wetter), passt sich das Verhaeltnis
  innerhalb von ~1-3 Minuten an

Wenn der Schalter aus ist:
- Alles laeuft wie heute, **keine Aenderung sichtbar**

### Wichtige Details

- Schalter **wird nicht gespeichert** — beim App-Neustart steht er auf AUS.
  Du musst aktiv einschalten fuer den Test. (Verhindert dass du vergisst
  und Bugs falsch zuordnest.)
- **Sicherheit:** TX-Antenne bleibt IMMER ANT1 — keine Aenderung am
  Hardware-Schutz.
- **Statik bleibt unberuehrt** — wenn Dynamic spinnt, einfach Schalter
  aus und alles laeuft wie heute.

### Was du nach Code-Fertig testest

12 Punkte (siehe Field-Test-Checkliste Sektion 5). Wichtigste:
1. Toggle AUS = wie heute (keine Aenderung)
2. Toggle AN = Verhaeltnis wird blau, passt sich an
3. Bandwechsel mit Toggle AN = keine 90-Sek-Sperre mehr
4. 1h ohne QSO = keine automatische Re-Mess mehr

Wenn alles gruen → Stufe 2 spaeter: Statik komplett raus, Dynamic wird
Standard.

---

## 7. Naechster Schritt

Mike-Freigabe holen. Dann:
1. Plan-Mode mit ExitPlanMode (kein Code in Plan-Mode)
2. Atomare Commits C1-C9 in Reihenfolge
3. Tests-Pruefung (1070 → erwartet 1095-1100 gruen)
4. Final-R1 nach Code-fertig
5. Field-Test-Checkliste an Mike

---

## 8. Anhang: Was hat sich gegenueber V2 geaendert (R1-Findings eingearbeitet)

| Aenderung | Begruendung |
|---|---|
| `RLock` → `Lock` | R1-Q6: kein Re-Entrancy noetig |
| Signal `scoring_mode_changed` → Callback-Listener-Liste | Vermeidet `DiversityController` → `QObject` Aenderung |
| `setattr(diversity_ctrl, '_dynamic_active', ...)` → Property | R1-Q4: saubere API |
| Toggle AN mid-measure: Variante B (abbrechen) statt A (warten) | R1-Q7: Mike erwartet sofortige Reaktion |
| Kein `_skip_next_slot`-Flag | R1-Q8: KISS, Median glaettet Outlier |
| Modulname: `core/dynamic_diversity.py` (vorher `diversity_dynamic.py`) | R1-Q10: konsistent mit `diversity_merger.py` |
| **Mike-B-Option:** `_last_measured_at = time.time()` bei `deactivate()` | Verhindert sofortige Statik-Re-Mess nach Toggle-AUS |
| Anzeige: Antennen-Panel Faerbung (B.1.a) statt Statusbar | R1-Q3 + V2-B.1: Verhaeltnis ist gar nicht in Statusbar |
| Test-Liste: 26 konkrete Tests mit Datei + Name | R1-Q9: explizite Test-Coverage |

---

**V3 ist Compact-fest. Eine neue KI kann allein damit den Code schreiben.**
