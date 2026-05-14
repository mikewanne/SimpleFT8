# Bundle H — V3 (Final Plan, Compact-fest)

**Basis:** V1 + V2 + R1 (7/10, 1 KRITISCH + 3 SOLLTE + 1 KÖNNTE)

## R1-Findings Übernahme

| Finding | Status | Aktion |
|---|---|---|
| **K1 (Auto+DXTuneDialog UX-Race)** | **TEILWEISE übernommen mit Begründung** | R1: „direkter `_enable_diversity` ohne `_check_diversity_preset`". **Differenzierte Position:** Mike's Spec „kein Dialog" meinte den **Wahl-Dialog** (Std/DX), NICHT den **Mess-Dialog** (DXTuneDialog für Gain-Pegelausgleich). DXTuneDialog ist FUNKTIONAL nötig wenn Gain stale — ohne Mess ist Diversity hardware-unausgewogen. **Lösung:** `_activate_diversity_with_scoring` bleibt (Cache-Dispatch inkl. ggf. DXTuneDialog). Toast erscheint VOR DXTuneDialog → User sieht Bandpilot-Wahl, dann ggf. Mess. UX-konsistent. |
| **S1 (WA_DeleteOnClose)** | ÜBERNOMMEN | Im extrahierten Dialog setzen, saubere Praxis |
| **S2 (Integration-Test echter recommend_for_hour)** | ÜBERNOMMEN | T1-Suite mit synthetischem summary_24h-Dict |
| **S3 (no_change-Fallback defensiv)** | ÜBERNOMMEN | `if rec is None or rec["decision"] == "no_change": fallback` |
| **KÖNNTE (Exception-Fallback)** | ÜBERNOMMEN | try/except bereits in V1 enthalten |

## Acceptance Criteria (12 ACs)

### Code

**AC1 (`core/mode_recommender.py::recommend_for_hour`):**
Neuer Parameter `allowed_modes: tuple[str, ...] | None = None`.
Verhalten:
- Default None → wie heute (3 CODE_MODES)
- Gesetzt → Ranking nur aus allowed_modes
- Wenn `current_mode not in allowed_modes`:
  - Tolerance-Check SKIP
  - `decision = "switch"`
  - `decision_mode = top1` (aus allowed_modes-Subset)
- Daten-Check bleibt: ein allowed_mode mit zu wenig Daten → return None

**AC2 (`core/mode_recommender.py::code_mode_to_scoring`):**
Neue Modul-Function:
```python
def code_mode_to_scoring(decision_mode: str) -> str:
    """diversity_normal → 'normal' (Std-Scoring), diversity_dx → 'dx'."""
    return "dx" if decision_mode == "diversity_dx" else "normal"
```

**AC3 (`ui/mw_radio.py::_show_diversity_choice_dialog`):**
Extrahieren des inline-Dialogs (Z.578-633) in eigene Method:
```python
def _show_diversity_choice_dialog(self, intro_text: str) -> str | None:
    """Std/DX-Wahl-Dialog mit dynamischem Intro.
    Returnt 'normal' (Std), 'dx', oder None (Abbruch).
    """
```
- WA_DeleteOnClose setzen (R1-S1)
- intro_text → QLabel
- Buttons: „Diversity Standard" → "normal", „Diversity DX" → "dx",
  „Abbruch" → None

**AC4 (`ui/mw_radio.py::_on_rx_mode_changed` Refactor):**
Inline-Dialog Z.578-633 entfernen, ersetzen durch:
```python
elif mode == "diversity":
    bp_mode = self.settings.get("bandpilot_mode", "off")
    band = self.settings.band
    utc_hour = datetime.now(timezone.utc).hour

    rec = None
    bp = getattr(self, "_bandpilot", None)  # R1-V2-L8 defensiv
    if bp is not None and bp_mode in ("auto", "manual"):
        try:
            rec = bp.recommend(
                band, utc_hour, current_mode="normal",
                allowed_modes=("diversity_normal", "diversity_dx"),
            )
        except Exception as e:
            print(f"[Bandpilot H-Path] Aggregations-Fehler: {e}")
            rec = None

    # R1-S3: defensive no_change-Behandlung (sollte bei H eh nicht
    # vorkommen weil current=normal nie in allowed_modes ist)
    if rec is not None and rec.get("decision") == "no_change":
        rec = None  # Fallback auf Mangel-Pfad

    from core.mode_recommender import code_mode_to_scoring

    if bp_mode == "auto" and rec is not None:
        scoring = code_mode_to_scoring(rec["decision_mode"])
        self._show_bandpilot_auto_toast(band, utc_hour, rec)
        self._activate_diversity_with_scoring(scoring)
        return

    if bp_mode == "manual" and rec is not None:
        # Hint im Manual-Dialog: current=None → kein „● = aktueller Modus"
        chosen = self._show_bandpilot_manual_dialog(
            band, utc_hour, rec, current=None,
        )
        if chosen is None:
            self.control_panel.set_rx_mode("normal")
            return
        scoring = code_mode_to_scoring(chosen)
        self._activate_diversity_with_scoring(scoring)
        return

    # off, oder (auto/manual + rec=None): dynamischer Wahl-Dialog
    intro_text = (
        "Nicht genug Daten für Bandpilot — bitte selbst wählen:"
        if bp_mode in ("auto", "manual")
        else "Welchen Modus verwenden?"
    )
    scoring = self._show_diversity_choice_dialog(intro_text)
    if scoring is None:
        self.control_panel.set_rx_mode("normal")
        return
    self._activate_diversity_with_scoring(scoring)
```

**AC5 (`ui/bandpilot_dialogs.py::BandpilotManualDialog` Hint):**
Bei `current=None`:
- Hint Z.195-197 ausblenden (`hint.hide()` oder Conditional skip)
- ● -Marker im Ranking nicht setzen (current vergleicht mit None →
  niemals match → keine ●, OK)

### Tests `tests/test_bundle_h.py` NEU

- **T1 (recommend_for_hour API):**
  - T1a: `allowed_modes=None` Default → 3-Wege-Ranking wie heute
  - T1b: `allowed_modes=("diversity_normal", "diversity_dx")` + alle
    Daten OK → 2-er Ranking, decision="switch" (current="normal" nicht
    in allowed_modes)
  - T1c: `allowed_modes` + 1 Mode fehlt Daten → return None
- **T2 (code_mode_to_scoring):**
  - „diversity_normal" → „normal"
  - „diversity_dx" → „dx"
  - „normal" → „normal" (Default-Fallback)
- **T3 (auto + genug Daten):** Slot zeigt Toast + activate ohne Dialog
- **T4 (auto + rec=None):** Slot zeigt dynamischen Dialog mit
  Mangel-Text
- **T5 (off):** Slot zeigt dynamischen Dialog mit Standard-Text
- **T6 (manual + genug Daten):** Slot zeigt Manual-Dialog
- **T7 (manual + rec=None):** Slot zeigt dynamischen Dialog
- **T8 (Abbruch):** `set_rx_mode("normal")` + kein activate
- **T9 (BandpilotAutoToast 2-elementig):** instanziieren mit rec mit
  2-Modi-Ranking → kein Crash, 2 Zeilen
- **T10 (no_change-Fallback):** wenn rec mit decision=„no_change"
  geliefert → behandelt wie rec=None

### Backup

**AC6:** `Appsicherungen/2026-05-14_v0.97.24_vor_bundle_h/` mit
`core/mode_recommender.py`, `ui/mw_radio.py`, `ui/bandpilot_dialogs.py`.

### Commits

- **AC7 (C1):** `core/mode_recommender.py` allowed_modes +
  code_mode_to_scoring
- **AC8 (C2):** `ui/bandpilot_dialogs.py` Hint-Anpassung current=None
- **AC9 (C3):** `ui/mw_radio.py` Refactor inline-Dialog + neuer Slot-
  Pfad
- **AC10 (C4):** `tests/test_bundle_h.py` NEU (~12 Tests)
- **AC11 (C5):** APP_VERSION → 0.97.25 + HISTORY + HANDOFF + CLAUDE
- **AC12 (C6):** Plan-Files + Memory + MEMORY.md

## Test-Bilanz

- Vor Bundle H: 1194 grün
- +~12 Tests
- Erwartung: **~1206 grün**

## Field-Test F1-F8

| # | Test | Erwartung |
|---|---|---|
| F1 | bp=off + Klick Div | Dialog „Welchen Modus verwenden?" (heute) |
| F2 | bp=auto + genug Daten + Klick Div | **Kein Wahl-Dialog**, automatisch + Toast 6s mit 2 Zeilen (🥇 + 🥈) |
| F3 | bp=auto + zu wenig Daten + Klick Div | Dialog dynamisch „Nicht genug Daten — bitte wählen" |
| F4 | bp=manual + genug + Klick Div | Manual-Dialog 2 Buttons (kein ●-Hint) |
| F5 | bp=manual + zu wenig + Klick Div | Dialog wie F3 |
| F6 | Abbruch im Dialog | Zurück zu Normal-Button |
| F7 | F2 + Gain stale | Toast erst, dann DXTuneDialog (UX-konsistent, **nicht** Bundle-H-Bug) |
| F8 | Pipeline-Lock-Schutz | F2 während Gain-Mess → Klick blockiert |

## V3 Compact-Sicherung — Code-Verifikation

- `mode_recommender.py:168+` `recommend_for_hour` Signatur
- `mode_recommender.py:49` CODE_MODES Tupel
- `mw_radio.py:578-633` inline-Dialog (wird ersetzt)
- `bandpilot_dialogs.py:195-197` Hint im Manual-Dialog
- `bandpilot_dialogs.py:202` Manual-Dialog iteriert über ranking-len
- `_gain_measure_locked`-Check in `_on_rx_mode_changed:528` greift
