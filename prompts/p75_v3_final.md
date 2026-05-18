# P75 — V3 Final Spec (R1-V4-pro übernommen)

## R1-Findings-Übernahme

| # | Klassif. | Status | Lösung |
|---|----------|--------|--------|
| F1 | 🟡 | ÜBERNOMMEN | `blockSignals`-Pattern in `_tune_stop` |
| F2 | ⚪ | ÜBERNOMMEN | Eigenes TUNE-Style-Cluster (gelb-dezent inaktiv) |
| F3 | EMPF. | **Variante A** | DXTuneDialog `prev_tune_swr`-Param + Banner |
| F4 | 🟡 | ÜBERNOMMEN | QMessageBox → `qso_panel.add_info` |
| F5 | ⚪ | UNVERÄNDERT | FWDPWR behalten (KISS-OK, Hobby-Funker findet nützlich) |
| F6 | 🟡 | ÜBERNOMMEN | +3 Tests (Race, prev_tune_swr=None, QMessageBox-Absence) |

**Variante B verworfen** — KISS hat Vorrang, 3-4 h Refactor nicht
gerechtfertigt für Mike's Hauptproblem („viele Fenster die aufploppen
verwirren"). Header-Banner reicht.

## Acceptance-Criteria

**AC1:** `_tune_stop` ruft am Ende:
```python
btn = getattr(self.control_panel, 'btn_tune', None)
if btn is not None and btn.isChecked():
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
```

**AC2:** TUNE-Button in `control_panel.py` Z.897-905 ersetzt durch
eigenes `_tune_btn_style`-Cluster:
```python
_tune_btn_style = (
    f"QPushButton {{ background: rgba(60,50,0,0.55); color: #BBA060; "
    f"border: 1px solid rgba(150,120,40,0.5); border-radius: 5px; "
    f"font-weight: bold; font-family: {_FONT}; font-size: 11px; "
    f"padding: 2px 6px; }}"
    f"QPushButton:checked {{ background: rgba(0,150,0,0.75); color: #FFFFFF; "
    f"border-color: rgba(0,220,0,0.75); }}"
    f"QPushButton:hover {{ background: rgba(90,70,0,0.6); color: #DDD; }}"
    f"QPushButton:checked:hover {{ background: rgba(0,180,0,0.85); color: #FFFFFF; }}"
    f"QPushButton:disabled {{ background: #2a2a2a; color: #666666; "
    f"border: 1px solid #444444; }}"
)
self.btn_tune.setStyleSheet(_tune_btn_style)
```

**AC3:** `DXTuneDialog.__init__` neuer Parameter
`prev_tune_swr: Optional[float] = None`. Wenn nicht None: Header-Banner
am Layout-Top:
```python
banner = QLabel(
    f"✓ TUNE OK — SWR {prev_tune_swr:.1f} · jetzt 2 Min Gain-Messung läuft"
)
banner.setStyleSheet(
    "background: rgba(0,150,0,0.25); color: #88FFAA; "
    "padding: 6px 10px; border-radius: 4px; "
    "font-weight: bold; font-size: 12px;"
)
banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
layout.insertWidget(0, banner)  # ganz oben
```

**AC4:** `mw_radio._check_diversity_preset` Aufruf von DXTuneDialog
übergibt `prev_tune_swr=self.radio.last_swr` wenn `_auto_tune_running`
war ODER `_tune_in_progress` kürzlich erfolgreich war. KISS: einfach
immer `radio.last_swr` übergeben wenn `<= swr_limit`, sonst `None`.

**AC5:** `_tune_post_swr_check` SWR-bad-Branch (mw_tx.py:321):
QMessageBox raus, stattdessen `qso_panel.add_info(...)` mit `⚠`-Prefix.

**AC6 (F5):** Status-Label im AutoTuneDialog BLEIBT wie P71 — kein
Rollback der FWDPWR-Anzeige.

## Tests (10 P75-Tests, T1-T10)

- T1: `_tune_stop` ruft `btn_tune.setChecked(False)` mit blockSignals
- T2: TUNE-Button-Style enthält neuen `_tune_btn_style` (gelb-dezent
      `rgba(60,50,0,...)`)
- T3: Alter `#998800`-Style raus
- T4: Auto-Stop nach Timer setzt Button zurück, keine `tune_clicked`-
      Signal-Emission (Signal-Block)
- T5 (R1-F6 Race): User-Toggle-Off + Auto-Stop-Timer gleichzeitig →
      keine Doppel-Stop, keine State-Korruption
- T6: DXTuneDialog mit `prev_tune_swr=2.1` zeigt Banner mit korrektem
      Text
- T7 (R1-F6): DXTuneDialog mit `prev_tune_swr=None` zeigt KEIN Banner
- T8: `_tune_post_swr_check` SWR-bad manueller Pfad: `qso_panel.add_info`
      aufgerufen, KEIN QMessageBox
- T9 (R1-F6): SWR-bad Auto-Tune-Pfad: weder QMessageBox noch
      qso_panel.add_info (Signal an Dialog)
- T10: Style-Konsistenz: TUNE-Aktiv-Hintergrund = OMNI-Aktiv-Hintergrund
       (`rgba(0,150,0,0.75)`)

## Code-Plan (7 atomare Commits)

- **C1:** `ui/control_panel.py` — TUNE-Button-Style umstellen.
- **C2:** `ui/mw_tx.py` — Button-State-Reset in `_tune_stop` +
  QMessageBox raus + `qso_panel.add_info` rein.
- **C3:** `ui/dx_tune_dialog.py` — `prev_tune_swr`-Param + Banner.
- **C4:** `ui/mw_radio.py` — DXTuneDialog-Aufruf erweitert um
  `prev_tune_swr`-Übergabe.
- **C5:** `tests/test_p75_button_modal.py` NEU — 10 Tests.
- **C6:** `main.py` APP_VERSION 0.97.47 → 0.97.48.
- **C7:** HISTORY + HANDOFF + CLAUDE + TODO + FIELDTESTS Update.

## Field-Test (V3 §5)

- **F1 (kein Radio):** Settings öffnen → TUNE-Knopf ist sichtbar in
  dezent-gelb (`#BBA060`-Text auf dunkel). KEIN heller Gelb.
- **F2 (Radio):** Manueller TUNE klicken → Button wird grün (aktiv).
  Nach Auto-Stop (15 s) → Button wird **automatisch zurück auf dezent-
  gelb**. (Bug-Fix.)
- **F3 (Radio):** Bandwechsel auf neues Band ohne Preset → AutoTuneDialog
  läuft → DXTuneDialog öffnet mit **grünem Banner ganz oben:** „✓ TUNE
  OK — SWR X.X · jetzt 2 Min Gain-Messung läuft".
- **F4 (Radio):** Manueller TUNE bei schlechtem SWR (z.B. abgezogene
  Antenne) → **KEIN Popup** mehr, stattdessen rote Zeile im QSO-Log:
  „⚠ Tuner konnte nicht matchen — SWR X.X. ..."
- **F5:** Status-Label im AutoTuneDialog zeigt weiterhin FWDPWR live
  (KISS-Check passed, R1 sagt Hobby-Funker findet's nützlich).
