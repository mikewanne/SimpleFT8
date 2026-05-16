# Bundle K (P57 + P59) — UI-Konsistenz

**Session:** 15.05.2026 mittags · APP_VERSION-Ziel 0.97.34 · Tests
1289 → ~1297

## Trigger

Mike-Field-Test 15.05.2026 morgens, 2 kleine UI-Tweaks:

- **P57**: SWR-Limit soll nur in 0.5-Schritten wählbar sein („1, 1.5, 2,
  2.5, 3, 3.5..."). Aktuell `QDoubleSpinBox` mit `setSingleStep(0.5)`,
  aber User kann freien Wert eingeben (z.B. 1.7) via Tastatur.
- **P59**: CQ-Button (`btn_cq`) im Normal-Modus zeigt im AKTIV-State Rot
  mit gelbem Text. Mike: „verbesserung sollte wie bei diversity modus
  auch grün werden. (einheidlich optisch nachvollziehbar)"

## P57 — SWR-Limit als feste 0.5-Schritte

### Aktuell

`ui/settings_dialog.py:206-209`:
```python
self.swr_limit = QDoubleSpinBox()
self.swr_limit.setRange(1.5, 10.0)
self.swr_limit.setSingleStep(0.5)
self.swr_limit.setDecimals(1)
```

Problem: Tastatur-Eingabe erlaubt 1.7, 2.3 etc. (Step gilt nur für
Pfeile/Scroll).

### Lösung

`QComboBox` mit 8 festen Werten:
```python
self.swr_limit = QComboBox()
_SWR_VALUES = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
for v in _SWR_VALUES:
    self.swr_limit.addItem(f"{v:.1f}", v)
# Default 3.0 (Index 3)
self.swr_limit.setCurrentIndex(3)
```

**Range-Limit oben:** 5.0 statt 10.0. Begründung: SWR >5 ist Hardware-
Notfall, kein User-Setting. Tuner-Endstufen-Schutz greift sowieso ab 3.0.
Hobby-Praxis braucht 1.5-5.0.

**Load mit Snap:** Gespeicherter Wert (z.B. 1.7 aus Vorgänger-Version)
wird auf **nächst-höheren** Listenwert gesnappt (sicherer: schärferes
Limit). Wenn >5.0 → 5.0 (Maximum). Wenn <1.5 → 1.5 (Minimum).

**Save:** `swr_limit.currentData()` (Float aus addItem-Userdata).

**Reset-Default:** 3.0 → `setCurrentIndex(3)`.

### Hardware-Sicherheit

Setter `radio.set_swr_limit(value)` in `radio/flexradio.py` clampt schon
auf `[1.5, 10.0]`. Neue Range `[1.5, 5.0]` ist Subset → kein Hardware-
Risiko, nur User-Eingrenzung.

## P59 — CQ-Button konsistent grün im Aktiv-State

### Aktuell

`ui/control_panel.py:986-995` `_mode_btn_style`:
```python
"QPushButton:checked { background: rgba(200,0,0,0.7); color: #FFD700;
border-color: rgba(255,180,0,0.7); }"
```

→ Active = ROT mit GELBEM Text. Wird von `btn_cq` und `btn_auto_hunt`
genutzt.

`_omni_btn_style` (Z.1007-1017):
```python
"QPushButton:checked { background: rgba(0,150,0,0.75); color: #FFFFFF;
border-color: rgba(0,220,0,0.75); }"
```

→ Active = GRÜN mit WEISSEM Text. Wird nur von `btn_omni_cq` genutzt.

### Lösung

`_mode_btn_style` Active-Block analog `_omni_btn_style` machen:
```python
# Bundle K (P59): einheitlich grüner Aktiv-State analog OMNI-Button
f"QPushButton:checked {{ background: rgba(0,150,0,0.75); color: #FFFFFF; "
f"border-color: rgba(0,220,0,0.75); }}"
f"QPushButton:checked:hover {{ background: rgba(0,180,0,0.85); color: #FFFFFF; }}"
```

**Wirkung:**
- `btn_cq` aktiv = grün ✓
- `btn_auto_hunt` aktiv = grün ✓ (Konsistenz innerhalb „funkt aktiv"-Buttons)
- `btn_omni_cq` aktiv = grün (bleibt wie bisher)

Alle 3 CQ/Hunt-Active-States einheitlich grün — Mike's Spec.

**Inaktiv-State bleibt dunkelrot** (Mike-Wunsch: optischer
Sicherheits-Hinweis dass TX-Funktion da ist).

### Tests P59

- T1: `_mode_btn_style` enthält grünen Active-State (Source-Level)
- T2: `_mode_btn_style` enthält NICHT mehr rot+gelb Active-State

## Code-Plan (atomar)

| Commit | Datei | Was |
|---|---|---|
| C1 | `ui/settings_dialog.py` | SWR-Limit `QDoubleSpinBox` → `QComboBox` (P57) + Load-Snap + Reset-Default |
| C2 | `ui/control_panel.py` | `_mode_btn_style` Active-Block auf grün (P59) |
| C3 | `tests/test_bundle_k.py` NEU | T1-T6 (3 P57 + 3 P59) |
| C4 | `main.py` APP_VERSION + Backup + Doku |

## Tests (Plan)

**P57:**
- T1 ComboBox enthält exakt 8 Werte 1.5..5.0
- T2 Default-Index = 3 (= 3.0)
- T3 Load mit unzulässigem Wert (1.7) snappt auf 2.0

**P59:**
- T4 `_mode_btn_style` enthält grünen Active-State (Source-Level grep)
- T5 `_mode_btn_style` enthält NICHT mehr `#FFD700` + `rgba(200,0,0,0.7)`
- T6 `_omni_btn_style` unverändert (Regressions-Schutz)

## Field-Test-Punkte für Mike

| F# | Was prüfen |
|---|---|
| F1 | Settings: SWR-Limit zeigt Combo mit 1.5/2.0/.../5.0 (kein freier Tastatur-Eingabe) |
| F2 | Settings: Wert speichern, App-Neustart → Wert bleibt |
| F3 | Settings: Reset auf Defaults → SWR auf 3.0 |
| F4 | Normal-Modus: CQ-Button rufen → aktiv = GRÜN (war rot/gelb) |
| F5 | Diversity-Modus: OMNI CQ rufen → aktiv = grün (Regression) |
| F6 | Diversity-Modus: Auto-Hunt starten → aktiv = GRÜN (war rot/gelb, jetzt konsistent) |

## Hardware-Pflicht ANT1

Keine TX-Antennen-Logik berührt. ANT1-Pflicht unverändert.

## Aus Scope

- SWR-Limit über 5.0 ermöglichen (Mike-Spec: max 5.0 reicht)
- Active-State-Farbe parametrisierbar machen (Overengineering, KISS)
- Tooltips ändern (bleibt aktueller Text)

## Klärungsfragen (intern V2-Self-Review)

- Q1: Auto-Hunt-Aktiv auch grün — implizit von Mike's „einheidlich"
  bestätigt. Alle 3 Active-States einheitlich grün.
- Q2: Snap-Richtung bei Load — nächst-höhere (sicherer). Begründung:
  wenn alter Wert 1.7 war, ist 2.0 schärferes Limit (TX bricht früher
  ab). 1.5 wäre laxer.
- Q3: Range-Oberkante 5.0 oder 10.0? → 5.0. Mike-Hobby-Praxis. Wer >5
  setzt hat eh Hardware-Problem.
