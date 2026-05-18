# P75 Bundle (V1) — TUNE-Button-Bug + Style-Harmonisierung + Fenster-Konsolidierung

## Trigger

Mike-Field-Test 18.05.2026 nach P71-Release. Zwei Beobachtungen + ein
Folgeauftrag aus P74-A:

1. **Bug:** TUNE-Knopf bleibt gelb-leuchtend (checked=True) nachdem
   Auto-Stop-Timer das TUNE beendet hat. Visuelle Inkonsistenz —
   Knopf zeigt „aktiv" obwohl Tunen längst vorbei.
2. **UX-Frage Button-Style:** TUNE-Button hat eigenes Farbschema
   (gelb hell/gelb dunkel). Andere Toggle-Buttons (CQ/OMNI/Auto-Hunt)
   sind seit Bundle K (P59) einheitlich „dunkelrot inaktiv → grün
   aktiv". Mike-Wunsch: TUNE auch harmonisieren, aber gelb-dezent als
   Inaktiv-Farbe (TUNE = Setup-Aktion, nicht TX-Aktion → eigenes
   Farb-Cluster sinnvoll). Aktiv: grün analog OMNI.
3. **Fenster-Konsolidierung (P74-A):** Bei Bandwechsel ohne Diversity-
   Preset poppen aktuell 2 Fenster nacheinander auf (AutoTuneDialog →
   DXTuneDialog). Mike: „viele fenster die aufploppen verwirren ... ein
   fenster was erst die aktion und das beenden anzeigt ist
   übersichtlicher."

Mike's Leitlinie: **„SimpleFT8 — Name ist Programm. So viele Infos wie
nötig, so wenig wie möglich."**

## Code-Stand vor V2 (verifiziert)

- TUNE-Button: `ui/control_panel.py` Z.893-905. Style hardcoded inline
  (gelb-checked-State `#998800`). Connect Z.1306. Toggle-Click feuert
  `tune_clicked` Signal Z.1752.
- TUNE-Pfad: `ui/mw_tx.py:_on_tune_clicked` Z.78. Auto-Stop via
  `QTimer.singleShot(duration_s * 1000, _tune_stop(_token))` Z.132-134.
- `_tune_stop` Z.139 macht alles richtig (tune_off, VFO-zurück, Power-
  Reset, Post-Check-Timer) — aber **kein** `btn_tune.setChecked(False)`.
  Daher Button stuck on checked nach Auto-Stop.
- `_omni_btn_style` Z.1012-1022 als Vorlage: `rgba(80,0,0,0.55)` inaktiv,
  `rgba(0,150,0,0.75)` aktiv. Hover-States definiert.
- AutoTuneDialog: `ui/auto_tune_dialog.py` (P71 v0.97.47). 420×140 px,
  modal-blockend via `exec()`. Schließt sich nach `auto_tune_done`-
  Signal (success/fail).
- DXTuneDialog: `ui/dx_tune_dialog.py`. Non-modal (`QDialog` ohne
  exec-block), öffnet nach Auto-TUNE wenn Preset fehlt.

## V1 Bundle-Plan

### Teil A: TUNE-Button State-Reset (Bug)

**Fix:** `_tune_stop` in `ui/mw_tx.py` ruft am Ende:
```python
# P75-A: Button-State zurücksetzen damit visuell konsistent
# Signal-Block damit kein _on_tune_clicked(False) Re-Trigger
btn = getattr(self.control_panel, 'btn_tune', None)
if btn is not None and btn.isChecked():
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
```

Idempotent — wenn schon unchecked (User-Toggle-Off-Pfad), No-op.

### Teil B: TUNE-Button Style-Harmonisierung

**Eigenes Style-Cluster** für TUNE (nicht denselben roten Style wie CQ
nehmen — TUNE ist Setup-Aktion, nicht TX-Aktion):

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
```

Inaktiv: dezent dunkel-gelb (Hinweis „Setup-Funktion bereit").
Aktiv: grün analog OMNI/CQ-Aktiv.

### Teil C: Fenster-Konsolidierung — 2 Varianten zur Wahl

**Mikes Wunsch:** „ein fenster was erst die aktion und das beenden
anzeigt". Konkrete Reise: Bandwechsel auf neues Band ohne Preset →
aktuell AutoTuneDialog (Auto-TUNE 15s) → schließt → DXTuneDialog
(Gain-Mess 2 Min) → schließt mit Ergebnissen.

**Variante A: Light-Touch (KISS-Plus, ~30 Min Code)**
- AutoTuneDialog bleibt eigenständig (manueller TUNE-Pfad braucht ihn).
- DXTuneDialog erhält **Header-Banner** ganz oben mit „✓ TUNE OK — SWR
  X.X · jetzt 2 Min Gain-Messung läuft" (3-Zeilen-Block, gelb-grün,
  fixiert). Visuell als Fortsetzung erkennbar.
- AutoTuneDialog-Ergebnis (success, swr) wird per Konstruktor an
  DXTuneDialog übergeben → Banner-Text generiert.
- SWR-bad QMessageBox raus → Banner im AutoTuneDialog selbst zeigt
  Fehlertext 1500 ms vor reject() (existiert bereits via Z.146-151).
- Trade-off: zwei separate Dialoge bleiben, aber visuell als „Phase 1
  → Phase 2" erkennbar.

**Variante B: State-Machine-Dialog (Refactor, ~3-4 h Code)**
- DXTuneDialog wird erweitert um State `TUNE` (Phase 1). AutoTuneDialog
  bleibt nur für manuellen TUNE-Button (eigener Pfad).
- `_state ∈ ('TUNE', 'GAIN_CYCLES', 'FINISHED')`.
- `mw_radio._on_band_changed` bei `auto_tune_on_band_change AND no preset`
  → öffnet direkt erweiterten DXTuneDialog mit State `TUNE`.
- Cancel-Button durchgehend verfügbar. Race-Schutz via `_tune_token`-
  Pattern.
- Trade-off: sauberere UX (echtes 1-Fenster), aber mehr Code +
  Race-Risiken.

**V1-Empfehlung:** Variante A (KISS) für ersten Wurf. Variante B als
Folge-Bundle wenn Mike nach Field-Test sagt „reicht nicht".

Open Question für R1: lohnt Variante A oder direkt B? Mike sagte KISS,
das spricht für A.

### Teil D: SWR-bad QMessageBox eliminieren

Aktuell im `_tune_post_swr_check` (mw_tx.py:321): bei SWR-bad UND nicht
Auto-Tune-Pfad öffnet `QMessageBox.warning(...)` „Tuner konnte nicht
matchen". Das ist ein 3. Fenster (manueller TUNE-Pfad).

**KISS-Fix:** Statt Modal → `qso_panel.add_info(f"⚠ Tuner konnte nicht
matchen — SWR {swr_now:.1f}. TUNE wiederholen oder Antenne prüfen.")`.
Bleibt als rote Zeile im Live-Log sichtbar, kein Fenster-Pop.

### Teil E: AutoTuneDialog FWDPWR-Info reduzieren (KISS-Check)

P71 hat den Status-Label erweitert: `ANT1, 10W → FT8 — N/Ms · SWR x.x ·
FWDPWR x.xW`. Mike sagt jetzt „so wenig wie möglich".

**Frage R1:** Ist die FWDPWR-Live-Anzeige während TUNE wirklich nötig
für Hobby-Funker, oder ist sie Power-User-Overkill? Mike's KISS-Leitlinie
spricht für: Status reduzieren auf `ANT1 10W · N/Ms · SWR x.x`.

## Test-Plan

**T1:** `_tune_stop` ruft `btn_tune.setChecked(False)` mit Signal-Block.
**T2:** TUNE-Button-Style: inaktiv-State enthält gelb-dezent
(`rgba(60,50,0,...)`), aktiv-State grün (`rgba(0,150,0,...)`).
**T3:** TUNE-Button kein `#998800` mehr (alter Style raus).
**T4:** Bei Auto-Stop nach Timer: Button geht auf unchecked, aber kein
Re-Trigger von `_on_tune_clicked` (durch Signal-Block).
**T5:** (Variante A) DXTuneDialog Header-Banner zeigt
„✓ TUNE OK ..." wenn `prev_tune_swr` übergeben.
**T6:** SWR-bad-Fall: `qso_panel.add_info` statt `QMessageBox.warning`.
**T7:** (KISS-Check) Status-Label im AutoTuneDialog: FWDPWR-Reduktion
falls R1 zustimmt.

## Workflow

V1 → V2 (Self-Review) → R1 (DeepSeek-V4-pro Architektur-Entscheidung
Variante A vs B) → V3 → Code in 5-6 atomaren Commits → Tests → Final-R1
→ HISTORY+HANDOFF+CLAUDE+TODO+FIELDTESTS Update.

Mike's autonomes Mandat: keine Rückfragen, KISS-Vorrang, Bug + UX
abschließen bis er zurück ist.
