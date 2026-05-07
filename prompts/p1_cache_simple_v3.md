# P1.CACHE-SIMPLE V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-07.
**Workflow:** V1 → V2 → R1 ✅ („Plan freigegeben mit konkreten Empfehlungen") → **V3** → Compact → Code.

**Mike's Vision (NICHT verhandelbar):** Diversity-Cache und Gain-Cache
komplett entkoppelt. Beide eigene Frist (Ratio 60 Min, Gain 6h).
Keine Modal-Wahl-Dialoge. Bei Ablauf:
- Diversity → automatisch neu messen (still)
- Gain → DXTuneDialog auf, Messung läuft sofort, NUR Abbruch-Button

**Compact-fest:** Diese Datei enthält ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings übernommen

| R1-Empfehlung | Status |
|---|---|
| DXTuneDialog wiederverwenden (V2-L1) | ✅ — kein neuer Dialog |
| Cancel-Pfad: `store.get()` + `_enable_diversity(cached_ratio=...)` | ✅ — Stale-Acceptance |
| Option B (Gain-Dialog + Ratio aus Cache) bei Ratio-frisch + Gain-stale | ✅ |
| `_assess_ratio`/`_assess_gain` Helpers + Dispatch in `_check_diversity_preset` | ✅ |
| Keine PresetStore-API-Erweiterung | ✅ — `store.get()` reicht |
| 10 Tests (4 zusätzliche zu V1-6) | ✅ |
| `_set_gain_measure_lock` bleibt für Race-Schutz | ✅ |

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `ui/mw_radio.py` Bundle: Toast bereits weg + Cache-Reuse + Refactor

**Status der Toast-Sachen** (un-committed, müssen jetzt mit-committed werden):
- `ui/diversity_cache_toast.py` — gelöscht
- `tests/test_diversity_cache_reuse.py:177-189` — Toast-Smoke-Test entfernt
- `mw_radio.py:957-968` — Toast-Aufruf entfernt
- `mw_radio.py:946` — `scoring_label`-Variable entfernt

**1a — `_try_diversity_cache_reuse` Z.917-960 — Gain-Check raus:**

```diff
     def _try_diversity_cache_reuse(self, band: str, ft_mode: str,
                                    scoring: str) -> bool:
         """Pruefen ob Ratio-Cache < 1h alt ist und ggf. anwenden (v0.93).

-        Bei Erfolg: ``_enable_diversity`` aufrufen, Phase=operate setzen,
-        ratio + dominant aus Cache, Toast zeigen, ``_last_measured_at``
-        passend setzen. Returnt True → Aufrufer ueberspringt Pipeline/Dialog.
-
-        Pre-Condition: Standard-Modus (gain UND ratio im Cache). Wenn nur
-        gain valid ist (1h < age <= 6h) → False, Standard-Dialog uebernimmt.
+        P1.CACHE-SIMPLE (v0.95.13): Gain-Check entfernt — Ratio und Gain
+        komplett entkoppelt. Bei frischer Ratio wird geladen, auch wenn
+        Gain abgelaufen ist. Gain-Refresh wird vom Caller (`_check_diversity_
+        preset`) separat behandelt.
         """
         store = (getattr(self, '_dx_store', None) if scoring == "dx"
                  else getattr(self, '_standard_store', None))
         if not store:
             return False
         if not store.is_valid_ratio(band, ft_mode):
             return False
-        # Gain muss auch valid sein (ohne Gain kann der RX-Verstaerker nicht
-        # korrekt eingestellt werden — Cache-Reuse-Pfad braucht beides).
-        if not store.is_valid_gain(band, ft_mode):
-            return False
         entry = store.get(band, ft_mode)
         ratio = entry.get("ratio")
         dominant = entry.get("dominant")
         if not ratio:
             return False
         age_min = store.get_ratio_age_minutes(band, ft_mode) or 0
         age_sec = age_min * 60

         print(f"[Diversity] Cache-Reuse {band}/{ft_mode}: {ratio} "
               f"(dominant: {dominant or 'A1'}, vor {age_min} Min.) — Phase 3 skip")

         self._enable_diversity(
             scoring_mode=scoring,
             cached_ratio=ratio,
             cached_dominant=dominant,
             cached_age_seconds=age_sec,
         )
-        # P1.CACHE-TOAST-WEG (v0.95.13): Toast bei Cache-Reuse entfernt —
-        # Mike-Feedback 07.05.: "wenn Wert noch gültig ist, warum schreiben
-        # dass er gültig ist? Wie 'Computer fährt runter — OK?'". Aktuelle
-        # Werte stehen sowieso im Diversity-Display der Antennen-Kachel.
         return True
```

**1b — Neue Helper-Methoden vor `_check_diversity_preset`:**

```python
def _assess_ratio(self, band: str, ft_mode: str, scoring: str) -> str:
    """P1.CACHE-SIMPLE: Ratio-Cache-Status fuer band+mode bewerten.

    Returns: "fresh" (< 60 Min), "stale" (>= 60 Min, vorhanden), "missing".
    """
    store = self._get_diversity_store(scoring)
    if not store:
        return "missing"
    if store.is_valid_ratio(band, ft_mode):
        return "fresh"
    entry = store.get(band, ft_mode)
    if entry and entry.get("ratio"):
        return "stale"
    return "missing"

def _assess_gain(self, band: str, ft_mode: str, scoring: str) -> str:
    """P1.CACHE-SIMPLE: Gain-Cache-Status fuer band+mode bewerten.

    Returns: "fresh" (< 6h), "stale" (>= 6h, vorhanden), "missing".
    """
    store = self._get_diversity_store(scoring)
    if not store:
        return "missing"
    if store.is_valid_gain(band, ft_mode):
        return "fresh"
    entry = store.get(band, ft_mode)
    if entry and "gain_timestamp" in entry:
        return "stale"
    return "missing"

def _get_diversity_store(self, scoring: str):
    """Helper: PresetStore je nach scoring-Modus."""
    return (getattr(self, '_dx_store', None) if scoring == "dx"
            else getattr(self, '_standard_store', None))
```

**1c — `_check_diversity_preset` Z.987-1063 — komplett refactoren:**

```python
def _check_diversity_preset(self, band: str, ft_mode: str, scoring: str) -> None:
    """P1.CACHE-SIMPLE (v0.95.13): Diversity- und Gain-Cache komplett
    entkoppelt. Keine Modal-Wahl-Dialoge mehr.

    Logik:
    - Gain stale  → DXTuneDialog (Gain-only, danach Ratio aus Cache wenn fresh)
    - Gain missing → volle Pipeline (Gain + Ratio)
    - Gain fresh + Ratio fresh → Cache-Reuse (still)
    - Gain fresh + Ratio stale → stille Auto-Ratio-Messung
    - Gain fresh + Ratio missing → stille Auto-Ratio-Messung
    """
    if not getattr(self, 'radio', None) or not self.radio.ip:
        return

    ratio_status = self._assess_ratio(band, ft_mode, scoring)
    gain_status = self._assess_gain(band, ft_mode, scoring)
    print(f"[Diversity] Cache-Status {band}/{ft_mode}: "
          f"ratio={ratio_status}, gain={gain_status}")

    if gain_status == "stale":
        # Gain abgelaufen → DXTuneDialog (auto-start, nur Abbruch).
        # Wenn Ratio fresh: nach Gain-OK Cache-Reuse.
        # Wenn Ratio stale/missing: nach Gain-OK Phase 3.
        self._pending_ratio_status = ratio_status
        self._pending_diversity_scoring = scoring
        gain_scoring = "snr" if scoring == "dx" else "stations"
        self._start_dx_tuning(scoring_mode=gain_scoring)
        self._update_statusbar()
        return

    if gain_status == "missing":
        # Komplett unkalibriert → volle Pipeline (Gain + Ratio).
        gain_scoring = "snr" if scoring == "dx" else "stations"
        self._pending_dx_diversity = True
        self._pending_diversity_scoring = scoring
        self._start_dx_tuning(scoring_mode=gain_scoring)
        return

    # gain_status == "fresh":
    if ratio_status == "fresh":
        # Beides frisch → Cache-Reuse (still, kein Toast).
        if self._try_diversity_cache_reuse(band, ft_mode, scoring):
            self._update_statusbar()
        return

    # Ratio stale/missing, Gain fresh → stille Auto-Ratio-Messung.
    print(f"[Diversity] Ratio {ratio_status} mit Gain fresh → "
          f"automatische Ratio-Messung (Phase 3)")
    self._enable_diversity(scoring_mode=scoring)
    # _enable_diversity startet Phase=measure → Phase 3 läuft automatisch
```

**1d — `_on_dx_tune_accepted` Z.1233+ — Pending-Ratio-Status berücksichtigen:**

In `_on_dx_tune_accepted` muss der neue `_pending_ratio_status`-Pfad
behandelt werden: wenn Ratio-fresh aus Cache verfügbar → Cache-Reuse
nach Gain-OK statt Phase 3.

```python
# Im _on_dx_tune_accepted, vor dem _pending_dx_diversity-Block:
pending_ratio = getattr(self, '_pending_ratio_status', None)
if pending_ratio == "fresh":
    # P1.CACHE-SIMPLE: Gain neu, Ratio aus Cache übernehmen
    self._pending_ratio_status = None
    band = self.settings.band
    ft_mode = self.settings.mode
    scoring = self._pending_diversity_scoring or "standard"
    print(f"[Diversity] Gain neu OK → Ratio aus Cache (Phase 3 skip)")
    if self._try_diversity_cache_reuse(band, ft_mode, scoring):
        self._update_statusbar()
        return
    # Fallback: wenn Cache-Reuse plötzlich failt → Phase 3 als Sicherheitsnetz
    self._pending_dx_diversity = True
elif pending_ratio in ("stale", "missing"):
    # Phase 3 nötig → wie bisher
    self._pending_ratio_status = None
    self._pending_dx_diversity = True
```

**1e — `_on_dx_tune_rejected` Z.1364-1383 — Stale-Acceptance:**

```python
def _on_dx_tune_rejected(self):
    """DX Tuning abgebrochen — P1.CACHE-SIMPLE: Stale-Acceptance.

    Bei Cancel mit alten Werten weiterarbeiten (Risiko-Akzeptanz).
    Wenn alte Werte vorhanden: laden ohne Neu-Messung.
    Wenn nichts da: Diversity deaktivieren.
    """
    self._dx_tune_dialog = None
    self._set_gain_measure_lock(False)
    self._pending_dx_diversity = False
    self._pending_diversity_scoring = None
    self._pending_ratio_status = None  # P1.CACHE-SIMPLE

    if self.encoder.is_transmitting:
        self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()

    if self._rx_mode == "diversity" and self.radio.ip:
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        # P1.CACHE-SIMPLE: Stale-Acceptance — alte Werte laden statt
        # Pipeline neu zu starten (Endlos-Schleife verhindern).
        band = self.settings.band
        ft_mode = self.settings.mode
        store = self._get_diversity_store(scoring)
        entry = store.get(band, ft_mode) if store else None
        if entry and entry.get("ratio"):
            ratio = entry["ratio"]
            dominant = entry.get("dominant")
            ratio_age_sec = (time.time()
                             - entry.get("ratio_timestamp", time.time()))
            print(f"[Diversity] Cancel → Stale-Acceptance: lade {ratio} "
                  f"(Alter ignoriert)")
            self._enable_diversity(
                scoring_mode=scoring,
                cached_ratio=ratio,
                cached_dominant=dominant,
                cached_age_seconds=ratio_age_sec,
            )
        else:
            # Keine Werte vorhanden → Diversity deaktivieren
            print(f"[Diversity] Cancel ohne Werte → Diversity AUS")
            self._disable_diversity()
            self.control_panel.set_rx_mode("normal")
```

**1f — `_activate_diversity_with_scoring` (Z.755-790 nach R1)
prüfen ob analoger Wahl-Dialog drin ist und entfernen.**

### Diff 2 — `tests/test_diversity_cache_reuse.py` Updates

**Bestehende Tests die Gain-Pflicht erwarteten — invertieren:**

```python
def test_cache_reuse_loads_ratio_only_if_fresh():
    """P1.CACHE-SIMPLE: Cache-Reuse braucht NUR Ratio-Frische, kein Gain-Check."""
    store = PresetStore("test_p1_cache_simple.json")
    store.save(...)  # Ratio fresh, Gain stale
    mw = MockMwRadio(store=store)
    result = mw._try_diversity_cache_reuse("40m", "FT8", "standard")
    assert result is True  # Vorher (Bug): False
```

### Diff 3 — `tests/test_p1_cache_simple.py` (NEU, 6 Tests + 4 zusätzliche)

```python
"""Tests fuer P1.CACHE-SIMPLE — Diversity/Gain entkoppelt + UX-Cleanup.

Mike-Vision 2026-05-07: getrennte Fristen, keine Wahl-Dialoge.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import pytest
from PySide6.QtWidgets import QApplication

from core.preset_store import PresetStore


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# Tests:
# 1. test_assess_ratio_fresh_stale_missing
# 2. test_assess_gain_fresh_stale_missing
# 3. test_check_preset_dispatch_gain_stale_opens_dialog
# 4. test_check_preset_dispatch_gain_missing_full_pipeline
# 5. test_check_preset_dispatch_both_fresh_cache_reuse_silent
# 6. test_check_preset_dispatch_ratio_stale_gain_fresh_auto_remeasure
# 7. test_dx_tune_accepted_with_pending_ratio_fresh_uses_cache
# 8. test_dx_tune_rejected_loads_stale_values
# 9. test_dx_tune_rejected_no_values_disables_diversity
# 10. test_no_modal_dialog_in_normal_paths
```

(Konkrete Test-Implementierungen folgen im Code — V3 listet nur die
Coverage. Bestehende Mocks aus `test_diversity_cache_reuse.py` und
`test_settings_dialog_smoke.py:_FakeSettings` wiederverwenden.)

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen:**
   - `prompts/p1_cache_simple_v3.md` (diese Datei)
   - `ui/mw_radio.py:917-1063` (alte Methoden)
   - `ui/dx_tune_dialog.py` (Dialog-Verhalten)
   - `core/preset_store.py:120-160` (API)
   - `tests/test_diversity_cache_reuse.py` (Mocks)

2. **Diff 1a** — `_try_diversity_cache_reuse` Gain-Check raus + Toast-
   Cleanup (bereits applied, nur Code-Verifikation nötig)

3. **Diff 1b** — `_assess_ratio` + `_assess_gain` + `_get_diversity_store`
   Helpers vor `_check_diversity_preset` einfügen

4. **Diff 1c** — `_check_diversity_preset` komplett ersetzen mit
   Dispatch-Logik

5. **Diff 1d** — `_on_dx_tune_accepted`: `_pending_ratio_status`-Pfad
   einbauen

6. **Diff 1e** — `_on_dx_tune_rejected`: Stale-Acceptance + Disable
   wenn nichts da

7. **Diff 1f** — `_activate_diversity_with_scoring` prüfen + ggf.
   Wahl-Dialog raus

8. **Diff 2** — bestehende Tests invertieren

9. **Diff 3** — `tests/test_p1_cache_simple.py` NEU mit 10 Tests

10. **Tests laufen:** erwartet 852 + Delta = ca. **862 grün**

11. **Final-R1-Codereview** (Skill Schritt 5b):
    ```bash
    echo "Reviewe P1.CACHE-SIMPLE v0.95.13 — mw_radio.py + Tests. \
    Race-Conditions, Stale-Acceptance, Dispatch-Logik?" | \
    ./venv/bin/python3 tools/deepseek_review.py ui/mw_radio.py \
    tests/test_p1_cache_simple.py tests/test_diversity_cache_reuse.py
    ```

12. **APP_VERSION** in `main.py` 0.95.12 → 0.95.13

13. **Atomare Commits:**
    - Code+Tests: `P1.CACHE-SIMPLE (v0.95.13): Diversity/Gain entkoppelt + UX-Cleanup`
    - Doku: `docs (v0.95.13): P1.CACHE-SIMPLE HISTORY+TODO+HANDOFF+CLAUDE`

14. **Doku-Updates:**
    - `HISTORY.md` v0.95.13 Eintrag (Toast-Cleanup + Wahl-Dialog raus + Entkopplung)
    - `HANDOFF.md` beide Pfade
    - `CLAUDE.md` Header beide Pfade + Test-Count
    - `TODO.md` P1.CACHE-SIMPLE als ERLEDIGT
    - Memory `project_p1_cache_simple_in_progress.md` auf erledigt umflaggen

15. **Push** (NUR nach Mike-Freigabe — explizit fragen!)

16. **Lessons-Learned** (3 Fragen)

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] _try_diversity_cache_reuse Gain-Check raus
- [ ] _assess_ratio + _assess_gain Helpers
- [ ] _check_diversity_preset Dispatch-Refactor
- [ ] _on_dx_tune_accepted: pending_ratio_status-Pfad
- [ ] _on_dx_tune_rejected: Stale-Acceptance + Disable-Fallback
- [ ] Toast-Klasse + Smoke-Test gelöscht (bereits)
- [ ] Wahl-Dialog "Weiter / Neu messen" raus
- [ ] _pending_ratio_status-Attribut sauber initialisiert
- [ ] tests/test_p1_cache_simple.py mit 10 Tests
- [ ] Bestehende Cache-Reuse-Tests invertiert wo nötig
- [ ] ~862 Tests gesamt grün
- [ ] Final-R1-Codereview ohne 🔴-Findings
- [ ] APP_VERSION 0.95.12 → 0.95.13
- [ ] HISTORY/TODO/HANDOFF/CLAUDE updated
- [ ] Atomare Commits erstellt
- [ ] Mike-Freigabe für Push EXPLIZIT eingeholt
- [ ] Lessons-Learned beantwortet
```

---

## 5. Risiken & Notbremse

- **Race bei Cancel + Bandwechsel** während `_set_gain_measure_lock(False)`
  → R1 hält für unwahrscheinlich. Falls auftritt: Lock erst NACH
  `_enable_diversity` freigeben.
- **`_pending_ratio_status`-State-Leak:** wenn Methode zwischendurch
  Exception wirft → Flag bleibt gesetzt, nächster Bandwechsel-Trigger
  fehlerhaft. Mitigation: try/finally in `_on_dx_tune_accepted` oder
  zentrales Reset in `_check_diversity_preset` als erste Aktion.
- **Stale-Werte-Risiko:** bei Antennen-Tausch + Cancel-Pfad → schlechte
  Diversity. KALIBRIEREN-Button als Notbremse.
- **Test-Mocks:** PresetStore-Mock muss frische + alte Timestamps
  exakt setzen. `monkeypatch.setattr(time, 'time', ...)` oder
  `freezegun` empfohlen.
- **Compact-Risiko:** Diese Datei MUSS alle Diffs konkret enthalten.
  Falls etwas fehlt: V3 erweitern, re-loop.

---

## 6. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.CACHE-SIMPLE überraschend?
2. Was würde ich rückblickend anders machen?
3. Welches Memory soll geschrieben werden? (Vorschlag: feedback-Memory
   „UX-Cleanups bündeln statt einzeln" als Pattern für zukünftige
   Hobby-Tool-UX-Verbesserungen)

---

**Plan-V3 Ende. Bereit für Mike-Freigabe + Compact + Code.**
