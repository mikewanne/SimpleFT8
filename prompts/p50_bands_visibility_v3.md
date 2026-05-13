# P50.BANDS-VISIBILITY — Plan V3 (Compact-fest, finale Marschrute)

**Datum:** 2026-05-13 nachmittags
**Status:** V3 (final, geht ins Code-Schreiben)
**Trigger:** Mike-Wunsch nach P34-Stufe2 „Bänder zum Abwählen"

V1: `prompts/p50_bands_visibility_v1.md`
V2: `prompts/p50_bands_visibility_v2.md`
R1: `prompts/p50_bands_visibility_r1.md`

V3 ist die finale Marschrute mit ALLEN R1-Entscheidungen + F1/F2-Fixes.
Bei Compact mid-Code muss eine neue Session aus diesem File alleine
weitermachen können.

---

## 1. Ziel + Scope

User kann im Settings-Dialog (Tab „Sonstiges") wählen welche Bänder im
Band-Panel angezeigt werden. Default: alle 9 aktiv. Persistent über
App-Restart. Live-Update beim Settings-OK.

**Out-of-Scope:** Statistik-Filter, Auto-Switch bei Deaktivierung.

---

## 2. R1-verbindliche Antworten (eingearbeitet)

| Q | Entscheidung |
|---|---|
| Q1 Bandpilot-Filter | **JA** — `core/mode_recommender.py` filtert |
| Q2 Grid-Layout | **Variante A** — Lücken akzeptieren (Prop-Bars mit-versteckt) |
| Q3 Live-Update-Mechanismus | **Signal** `visible_bands_changed` |
| Q4 Default-Persist | **NEIN** — idempotenter Default |
| Q5 Settings-UI-Stil | **QCheckBox-Standard** |
| Q6 Statusbar-Hinweis | **NEIN** |
| Q7 Initial-Band-Konflikt | **Zwangs-aufnehmen** in enabled_bands |
| Q8 Prop-Bar-Test | **Pflicht** T9 |

---

## 3. Akzeptanzkriterien (final 14 ACs)

- **AC1** Settings-Dialog Tab „Sonstiges" hat QGroupBox „Sichtbare Bänder"
  mit 9 QCheckBox in 3×3-Grid (Zeile1: 10/12/15, Z2: 17/20/30, Z3: 40/60/80).
- **AC2** Default = alle 9 Bänder. Backward-kompatibel mit existierenden
  settings.json (kein Migration-Eintrag).
- **AC3** Mindestens 1 Band muss aktiv sein. Letzte aktive Checkbox →
  `setEnabled(False)` + Tooltip „Mindestens ein Band muss aktiv sein".
- **AC4** Live-Update via Signal `visible_bands_changed(list[str])` aus
  `settings_dialog.py`. `main_window` connectet im __init__.
- **AC5 (R1-F1)** Aktuelles Band wird AUTOMATISCH in enabled_bands
  aufgenommen wenn `current_band not in enabled_bands`. Triggert sowohl
  bei `set_visible_bands()` als auch beim App-Start.
- **AC6** Persistierung Key `enabled_bands` in `~/.simpleft8/settings.json`
  als `list[str]`.
- **AC7** Defensive Load-Filter: ungültige Werte (kein String, Band nicht
  in `BAND_FREQUENCIES`, Duplikate) werden ignoriert.
- **AC8** Empty-Fallback: leere Liste oder nur ungültige Werte → Default
  alle 9.
- **AC9 (R1-F2)** Prop-Bars werden mit dem Band-Button mit-versteckt:
  für jedes deaktivierte Band `prop_bars[b].setVisible(False)`.
- **AC10 (R1-Q2)** Grid-Layout-Lücken werden akzeptiert (`setVisible(False)`
  belässt Spalten-Stretch). Kein Re-Layout.
- **AC11 (R1-Q1)** Bandpilot (`core/mode_recommender.py`) filtert
  deaktivierte Bänder aus seinen Empfehlungen. Wenn keine Bänder mehr
  übrig: kein Empfehlung.
- **AC12 (R1-S3)** Settings-Dialog Reset-Button setzt enabled_bands auf
  Default zurück (alle 9).
- **AC13** Aktuelles Band kann nicht durch Deaktivieren „verschwinden":
  Test T10 prüft App-Start mit `current_band="60m"` + `enabled_bands=["20m"]`
  → 60m wird in enabled_bands aufgenommen → Button sichtbar.
- **AC14** Bandpilot-Empfehlung für deaktiviertes Band → Toast NICHT
  anzeigen (Filter in `_apply_bandpilot_*`).

---

## 4. Implementations-Reihenfolge (atomare Commits)

### C1 — Settings: enabled_bands API + Default
**Files:** `config/settings.py`

```python
# Neuer Default in load() oder am Klassen-Init:
DEFAULT_ENABLED_BANDS = list(BAND_FREQUENCIES.keys())

def get_enabled_bands(self) -> list[str]:
    """Return list of enabled bands, defensively filtered."""
    raw = self._data.get("enabled_bands", DEFAULT_ENABLED_BANDS)
    if not isinstance(raw, list):
        return list(DEFAULT_ENABLED_BANDS)
    valid = []
    seen = set()
    for b in raw:
        if isinstance(b, str) and b in BAND_FREQUENCIES and b not in seen:
            valid.append(b)
            seen.add(b)
    if not valid:
        return list(DEFAULT_ENABLED_BANDS)
    return valid

def set_enabled_bands(self, bands: list[str]) -> None:
    """Set enabled bands list (defensively filtered + saved)."""
    valid = [b for b in bands if isinstance(b, str) and b in BAND_FREQUENCIES]
    if not valid:
        valid = list(DEFAULT_ENABLED_BANDS)
    self._data["enabled_bands"] = valid
    # save() ggf. von Caller
```

**LOC:** ~30 Zeilen + Tests-Hooks.

### C2 — ControlPanel: set_visible_bands + Prop-Bar-Sync + current_band-Guarantee
**Files:** `ui/control_panel.py` (`ModeBandCard`)

```python
def set_visible_bands(self, bands: list[str]) -> None:
    """Set which band buttons are visible.

    F1-Guarantee: das aktuelle Band bleibt sichtbar, auch wenn es
    nicht in `bands` enthalten ist. F2: Prop-Bars werden mit-versteckt.
    """
    # F1-Guarantee
    visible = set(bands)
    if self._current_band and self._current_band not in visible:
        visible.add(self._current_band)
    # Apply visibility to buttons + prop bars
    for b, btn in self.band_buttons.items():
        is_visible = b in visible
        btn.setVisible(is_visible)
        # F2: Prop-Bars mit-verstecken
        if b in self.prop_bars:
            self.prop_bars[b].setVisible(is_visible and self.prop_bars[b]._has_data)
            # Hinweis: Prop-Bars haben heute schon eigene Visibility-Logik
            # (setVisible(False) bei kein-Daten). Wir verstecken hier
            # zusätzlich wenn das Band deaktiviert ist.
```

**LOC:** ~30 Zeilen.

**Hinweis:** `_PulseBar._has_data` ist nur Pseudocode — die echte Prop-Bar-
Logik im Code prüfen. Beim Code-Schreiben mit grep auf `prop_bars[*].setVisible`
verifizieren wie die heutige Bar-Visibility-Steuerung läuft.

### C3 — SettingsDialog: UI-Block + Signal + Reset-Hook
**Files:** `ui/settings_dialog.py`

- Neue QGroupBox „Sichtbare Bänder" in Tab „Sonstiges".
- 9 QCheckBoxes in 3×3-QGridLayout.
- Auf load: `get_enabled_bands()` lesen, Checkboxes setzen.
- Auf apply: `set_enabled_bands(checked_list)` + Signal
  `visible_bands_changed(list[str])` emit.
- Min-1-Logik: in `_on_band_cb_toggled()` zählen wieviele checked, wenn
  nur noch eine übrig → diese disable + Tooltip.
- Reset-Button (`_reset_defaults()`): alle Checkboxes auf True.

```python
self.visible_bands_changed = Signal(list)  # in __init__-Pattern

def _build_visible_bands_group(self) -> QGroupBox:
    grp = QGroupBox("Sichtbare Bänder")
    grid = QGridLayout(grp)
    self._band_checkboxes = {}
    bands_grid = [["10m", "12m", "15m"],
                  ["17m", "20m", "30m"],
                  ["40m", "60m", "80m"]]
    for row, row_bands in enumerate(bands_grid):
        for col, b in enumerate(row_bands):
            cb = QCheckBox(b)
            cb.stateChanged.connect(self._on_band_cb_toggled)
            self._band_checkboxes[b] = cb
            grid.addWidget(cb, row, col)
    return grp

def _on_band_cb_toggled(self):
    checked = [b for b, cb in self._band_checkboxes.items() if cb.isChecked()]
    if len(checked) <= 1:
        # Disable the last remaining checked one
        only = checked[0] if checked else None
        for b, cb in self._band_checkboxes.items():
            if b == only:
                cb.setEnabled(False)
                cb.setToolTip("Mindestens ein Band muss aktiv sein")
            else:
                cb.setEnabled(True)
                cb.setToolTip("")
    else:
        for cb in self._band_checkboxes.values():
            cb.setEnabled(True)
            cb.setToolTip("")
```

**LOC:** ~80 Zeilen.

### C4 — MainWindow: Signal-Connect + Initial-Apply + apply_visible_bands
**Files:** `ui/main_window.py`

```python
def apply_visible_bands(self, bands: list[str] | None = None) -> None:
    """Apply visible_bands setting to the control panel.

    Args: bands — wenn None, aus Settings holen.
    """
    if bands is None:
        bands = self.settings.get_enabled_bands()
    # F1-Guarantee: current_band ist in bands wird in ControlPanel.set_visible_bands erzwungen
    self.control_panel.set_visible_bands(bands)

# In __init__, NACH self.control_panel = ControlPanel(...):
self.apply_visible_bands()

# Settings-Dialog Signal-Connect:
self.settings_dialog.visible_bands_changed.connect(self.apply_visible_bands)
```

**LOC:** ~15 Zeilen.

### C5 — Bandpilot: enabled_bands-Filter
**Files:** `core/mode_recommender.py` (oder wo Bandpilot lebt)

```python
def recommend(self, band, hour, enabled_bands: list[str] | None = None):
    """... existing docstring ...

    enabled_bands: wenn gesetzt, Empfehlungen für nicht in der Liste
    enthaltene Bänder werden gefiltert.
    """
    # ... bestehende Logik ...
    if enabled_bands is not None and band not in enabled_bands:
        return None
    # ...
```

**Caller-Anpassung:** `mw_radio.py` ruft `recommend(band, hour)` →
mit `enabled_bands=self.settings.get_enabled_bands()` erweitern.

**LOC:** ~15 Zeilen.

### C6 — Tests T1-T11
**Files:** `tests/test_p50_bands_visibility.py` NEU

| # | Test | Was wird verifiziert |
|---|------|---|
| T1 | Settings load — kein Key | Default alle 9 Bänder |
| T2 | Settings load — ungültige Bänder | defensive Filter ignoriert |
| T3 | Settings load — leere Liste | Default Fallback |
| T4 | control_panel.set_visible_bands | Buttons werden versteckt |
| T5 | set_visible_bands — current_band-Guarantee (F1) | bleibt sichtbar |
| T6 | settings_dialog Mindest-1 | letzte Checkbox geblockt |
| T7 | settings_dialog roundtrip | Toggle → Save → Load → identisch |
| T8 | settings_dialog Apply | Signal emit + main_window connected |
| **T9 (R1-F2)** | Prop-Bar Visibility | prop_bars[b].setVisible(False) für deaktivierte |
| **T10 (R1-Q7)** | App-Start mit current_band außerhalb enabled_bands | wird zwangs-aufgenommen |
| **T11 (R1-Q1)** | Bandpilot mit deaktiviertem Band | recommend returnt None |
| **T12 (R1-S3)** | Reset-Button setzt enabled_bands zurück | alle 9 |

**LOC:** ~320 Zeilen.

### C7 — APP_VERSION + HISTORY + HANDOFF + CLAUDE + TODO + Memory + Backup
**Files:** `main.py` (APP_VERSION), `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`,
`TODO.md`, Memory (`project_p50_bands_visibility.md` + MEMORY.md Index),
`Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/` Backup.

**APP_VERSION:** 0.97.19 → 0.97.20

---

## 5. Field-Test-Checkliste F1-F8 (für Mike nach Push)

- **F1** Settings öffnen → Tab „Sonstiges" → „Sichtbare Bänder"-Block sichtbar mit 9 Checkboxen, alle aktiv?
- **F2** 60m + 80m abwählen → OK → Band-Panel zeigt 7 Bänder (Zeile 2: 30m, 40m, [Lücke, Lücke])?
- **F3** Settings wieder öffnen → 60m/80m abgewählt? App neu starten → noch abgewählt?
- **F4** Alle bis auf 1 abwählen → letzte Checkbox ist deaktiviert + Tooltip?
- **F5** Auf 20m wechseln, dann 20m abwählen → 20m bleibt sichtbar als aktives Band?
- **F6** Bandpilot empfiehlt deaktiviertes Band → Toast erscheint NICHT (Logfile: kein „Wechsel zu 60m")?
- **F7** Reset-Button in Settings → alle 9 wieder aktiv?
- **F8** settings.json öffnen → `enabled_bands` Key existiert nur wenn User Toggle gemacht hat?

---

## 6. Edge-Case-Liste

- **E1** Bandwechsel via Tastenkürzel (falls existiert) zu deaktiviertem
  Band → `set_visible_bands` muss current sicherstellen.
- **E2** Auto-Hunt auf aktuellem Band — nicht betroffen (kein Bandwechsel).
- **E3** Settings.json mit zukünftigem Band-Name (`"6m"`) → defensiver Filter
  ignoriert.
- **E4** Concurrent Write durch zwei App-Instanzen — nicht möglich
  (Single-Instance-Lock, plus GUI-Thread only).
- **E5** Korrupte settings.json → bestehender try/except in
  `Settings.load()` fängt. enabled_bands fällt auf Default.

---

## 7. Doku-Update am Ende

- `HISTORY.md` `## 2026-05-13 v0.97.20 — P50 Bänder-Sichtbarkeit (Settings-Toggle)`
- `HANDOFF.md` neuen Stand + Field-Test-Liste
- `CLAUDE.md` Header v0.97.20 + Test-Count
- `TODO.md` „Bänder-Deaktivierung Feature" als ERLEDIGT
- `Memory/project_p50_bands_visibility.md` + MEMORY.md Index-Eintrag
- `Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/` Backup vor Code-Schreiben

---

## 8. Compact-Fest-Check

Diese V3 enthält:
- ✅ Alle 14 ACs explizit nummeriert
- ✅ Alle R1-Findings F1+F2+S3+S4 als KRITISCH/SOLLTE-Lösung integriert
- ✅ Q1-Q8 final entschieden (3.)
- ✅ 7 atomare Commits C1-C7 mit Code-Schnipseln (nicht nur Beschreibung)
- ✅ 12 Tests T1-T12 inkl. R1-eingeforderten T9-T12
- ✅ 8 Field-Test-Punkte F1-F8 für Mike
- ✅ 5 Edge-Cases E1-E5
- ✅ Doku-Liste in 7
- ✅ Backup-Pfad benannt

**Wenn Compact passiert:** neue Session kann mit
„`prompts/p50_bands_visibility_v3.md` lesen + Schritt 5 (Code)" weitermachen.
