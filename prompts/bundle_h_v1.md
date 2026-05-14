# Bundle H — V1 (Plan-Entwurf)

**Datum:** 2026-05-14 mittags nach Bundle G-Push
**Trigger:** Mike-Beobachtung Bandpilot=Auto + Klick DIVERSITY → Std/DX-
Dialog erscheint trotzdem (sollte automatisch wählen).

## Mike-Spec

Beim Klick auf DIVERSITY (Normal → Diversity):

| Bandpilot | Daten | Verhalten |
|---|---|---|
| **off** | egal | Dialog „Welchen Modus verwenden?" (heute) |
| **auto** | genug | **kein Dialog** — Bandpilot wählt Std oder DX + Toast 6s mit Trophäen (nur Std vs DX im Ranking, kein Normal) |
| **auto** | zu wenig | Dialog dynamisch „Nicht genug Daten für Bandpilot — bitte selbst wählen" |
| **manual** | genug | Manual-Dialog mit Std/DX-Empfehlung (analog 3-Wege heute) |
| **manual** | zu wenig | Dialog dynamisch (Fallback wie off+Mangel-Text) |

## Architektur

### Bestehende Komponenten

- `core/mode_recommender.py::recommend_for_hour(summary, hour, current)`
  3-Wege-Vergleich (CODE_MODES = `("normal", "diversity_normal",
  "diversity_dx")`)
- `core/mode_recommender.py::HourlyBandpilot.recommend()` wrapper
- `ui/bandpilot_dialogs.py::BandpilotAutoToast` — iteriert über
  `rec["ranking"]`, funktioniert mit jeder Ranking-Länge (DeepSeek
  verifiziert)
- `ui/bandpilot_dialogs.py::BandpilotManualDialog` — Manual-Wahl mit
  3 Buttons (oder generisch je Ranking-Länge?)
- `ui/mw_radio.py:578-633` inline-Dialog „Diversity — Modus waehlen"
  (heute, hartcodiert)

### Code-Modi vs Scoring-Modi (Naming-Kollision aufpassen)

- **CODE_MODES** (in Bandpilot): `"normal"`, `"diversity_normal"`,
  `"diversity_dx"`
- **scoring_mode** (in DiversityController): `"normal"` (= Standard),
  `"dx"`

Mapping `decision_mode → scoring_mode`:
- `"diversity_normal"` → `scoring="normal"`
- `"diversity_dx"` → `scoring="dx"`

### Neue API: `allowed_modes`-Parameter

`recommend_for_hour(summary, hour, current_mode, allowed_modes=None)`:
- Default `None` → alle 3 Code-Modi (wie heute)
- `allowed_modes=("diversity_normal", "diversity_dx")` → nur diese
  zwei vergleichen
- Top-1 + Ranking nur aus allowed_modes berechnet
- Tolerance-Logik unverändert (current_mean vs top1_mean)

`HourlyBandpilot.recommend(band, hour, current, allowed_modes=None)`:
- Pass-through

### `_on_rx_mode_changed("diversity")` Refactor

Aktueller inline-Dialog (Z.578-633) entfernen, ersetzen durch:

```python
elif mode == "diversity":
    bp_mode = self.settings.get("bandpilot_mode", "off")
    band = self.settings.band
    utc_hour = datetime.now(timezone.utc).hour

    # Bandpilot-Empfehlung (Diversity-only)
    rec = None
    if bp_mode in ("auto", "manual"):
        try:
            rec = self._bandpilot.recommend(
                band, utc_hour, current_mode=None,
                # current_mode=None: kein no_change-Decision, weil
                # User explizit Wechsel will. Top-1 ist die Empfehlung.
                allowed_modes=("diversity_normal", "diversity_dx"),
            )
        except Exception as e:
            print(f"[Bandpilot] H-Path Fehler: {e}")

    if bp_mode == "auto" and rec is not None:
        # Auto: Bandpilot wählt, Toast zeigen
        target_scoring = _decision_to_scoring(rec["decision_mode"])
        self._show_bandpilot_auto_toast(band, utc_hour, rec)
        self._activate_diversity_with_scoring(target_scoring)
        return

    if bp_mode == "manual" and rec is not None:
        # Manual: Empfehlungs-Dialog mit allowed_modes
        chosen = self._show_bandpilot_manual_dialog(
            band, utc_hour, rec, current=None,
        )
        if chosen is None:
            self.control_panel.set_rx_mode("normal")  # Abbruch
            return
        self._activate_diversity_with_scoring(
            _decision_to_scoring(chosen))
        return

    # off oder (auto/manual + zu wenig Daten): dynamischer Dialog
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

### Helper-Funktion `_decision_to_scoring`

```python
def _decision_to_scoring(decision_mode: str) -> str:
    """Mappe Bandpilot-Code-Modus auf scoring_mode-String.

    diversity_normal → "normal" (Standard-Scoring)
    diversity_dx     → "dx"
    """
    return "dx" if decision_mode == "diversity_dx" else "normal"
```

### Inline-Dialog → reusable Method

Den inline-Dialog (mw_radio.py:578-633) extrahieren in
`_show_diversity_choice_dialog(intro_text: str) -> str | None`:
- Returnt `"normal"` (Standard) / `"dx"` / `None` (Abbruch)
- intro_text als Parameter → dynamisch je Bandpilot-Mode

### `current_mode=None` für Bandpilot bei H-Pfad

`recommend_for_hour` lehnt heute `current_mode=None` ab (Z.198-199).
Bei H-Pfad ist User aktuell Normal, will aber explizit Div — daher
„kein aktueller Mode für Tolerance-Berechnung". `current_mode="normal"`
übergeben + `allowed_modes=Diversity-only` → ranking enthält Normal
NICHT, current_mode-Check schlägt fehl → `None` returnt.

**Lösung:** Bei `allowed_modes` gesetzt + `current_mode not in
allowed_modes` → ignoriere current_mode-Tolerance, gib einfach Top-1
zurück mit `decision="switch"`.

ODER neue API `recommend_top_of(allowed_modes)` ohne Tolerance.

**V2-Frage:** welche Variante?

## Tests `tests/test_bundle_h.py` NEU

- T1: `recommend_for_hour` mit `allowed_modes=Div-only` → ranking
  nur 2-elementig
- T2: Bandpilot=auto + Klick Div + genug Daten → Toast + activate(top1)
- T3: Bandpilot=auto + Klick Div + zu wenig Daten → Dialog Mangel-Text
- T4: Bandpilot=off + Klick Div → Dialog Standard-Text
- T5: Bandpilot=manual + Klick Div + genug Daten → Manual-Dialog
- T6: Bandpilot=manual + Klick Div + zu wenig Daten → Dialog Mangel-Text
- T7: Dialog-Abbruch → set_rx_mode("normal") + kein activate
- T8: `BandpilotAutoToast` mit 2-elementigem Ranking → 2 Zeilen, kein Crash
- T9: `_decision_to_scoring` Mapping korrekt

## Atomare Commits

| C | Datei | Inhalt |
|---|---|---|
| C1 | `core/mode_recommender.py` | `allowed_modes`-Parameter |
| C2 | `ui/mw_radio.py` | `_on_rx_mode_changed` Refactor + `_show_diversity_choice_dialog` + `_decision_to_scoring` |
| C3 | `tests/test_bundle_h.py` NEU | 9 Tests |
| C4 | APP_VERSION → 0.97.25 + Doku |
| C5 | Plan-Files |

## V2-Fragen

- Q1: `current_mode`-Handling bei `allowed_modes` (Tolerance ignorieren
  oder neue API)?
- Q2: Manual-Dialog mit 2-elementigem rec — funktioniert
  `BandpilotManualDialog`? Aktuell 3 Buttons hartcodiert (Z.203+)?
- Q3: Decision-Mode bei H-Pfad ist immer „switch" (User will wechseln) —
  brauchen wir das `decision`-Feld noch?
- Q4: Toast bei `bp=manual` zusätzlich? Eher nicht — Manual-Dialog ist
  schon User-Aktion.
- Q5: `_decision_to_scoring` ist trivial — Modul-Function oder im Slot?

## Field-Test (V3)

- F1: bp=off + Klick Div → Dialog Standard-Text (heute)
- F2: bp=auto + Klick Div + genug Daten → automatisch, Toast 2 Zeilen
- F3: bp=auto + Klick Div + zu wenig Daten → Dialog Mangel-Text
- F4: bp=manual + Klick Div + genug Daten → Manual-Dialog 2 Buttons
- F5: bp=manual + Klick Div + zu wenig Daten → Dialog Mangel-Text
- F6: Dialog Abbruch → zurück zu Normal-Button
- F7: Toast bei Auto → 6s, dann Auto-Close
- F8: Race-Schutz: Während Toggle Bandwechsel → Pipeline-Lock greift
