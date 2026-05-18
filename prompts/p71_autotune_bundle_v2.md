# P71 Auto-Tune Bundle (V2 — Self-Review) — 18.05.2026

## Methodik

V1-Plan (`prompts/p71_autotune_bundle_v1.md`) gegen echten Code verifiziert:
- `ui/auto_tune_dialog.py` (komplett gelesen, 190 LOC)
- `ui/mw_tx.py:130-510` (_tune_stop / _tune_post_swr_check / _start_auto_tune_for_band_change / _tune_converge_to_target)
- `ui/mw_radio.py:380-535` (_on_band_changed inkl. P54-Hook)
- `ui/settings_dialog.py:331-340, 605, 765` (ComboBox tune_duration_s)
- `ui/main_window.py:90-123` (Init-Reihenfolge Radio-Start vs. _set_band)

## V1-Annahmen — Status

### ✅ Bug 1 (Backup-Race) — V1 bestätigt

- `auto_tune_dialog.py:119` → `(duration_s + 5) * 1000` = 20 s Backup ✓
- `mw_tx.py:179` Phase B → `_tune_converge_to_target(target_w=10)` mit
  Initial 1500 ms (Z.375) + max 5×1000 ms = **6.5 s worst-case** ✓
- `mw_tx.py:205-207` Post-Check → 2 s nach `_tune_stop` startet ✓
- Race-Math 15 + 6.5 + 2 = **23.5 s > 20 s Backup** → reproduzierbar bestätigt.

### ⚠️ Bug 2 (App-Start triggert Auto-Tune) — V1 unvollständig

**V1 sagt:** Wurzel = `_on_band_changed` ohne User/Init-Unterscheidung.

**Code-Realität:**
1. `main_window.__init__` Z.103 → `control_panel._set_band(settings.band)`
2. `control_panel.band_changed.connect(_on_band_changed)` erst Z.736 (NACH _set_band).
   → Sollte initial NICHT feuern wenn signal-connect später kommt.
3. `_start_radio()` Z.100 deferred via `QTimer.singleShot(0, ...)` → läuft NACH
   `__init__`-return.
4. `_on_band_changed:498-501` prüft `radio.ip` → bei App-Start `None` → Auto-Tune
   skippt eigentlich.

**Lücke:** Mike sagt „feuerte direkt bei start (weil nicht vorhanden?), jetzt
nicht mehr". Der genaue Trigger-Pfad ist **nicht eindeutig identifiziert**.
Hypothesen für DeepSeek-R1:
- (H1) Bandpilot ruft `_set_rx_mode_direct(...)` / `_set_band(...)` nach
  Radio-Connect mit jetzt-gesetztem `radio.ip` → `band_changed.emit` → Auto-Tune.
- (H2) Nach `apply_ft8_preset` in `_on_band_changed:471` feuert irgendwas
  Recursive ein zweites `band_changed`.
- (H3) `control_panel._set_band(settings.band)` Z.103 feuert das Signal
  **doch** (z.B. weil Setter `band_changed.emit` auch bei initialem
  identischen Set ruft) UND der Slot ist connect-bar weil `band_changed`
  ist ein Class-Attribute des Slots der schon existiert.

**V3-Empfehlung:** R1 soll prüfen ob `band_changed.emit` von ControlPanel
**während des __init__** mit unconnected-Signal silently dropped wird oder
nicht — und ob es einen post-connect Re-Trigger gibt.

**Fix-Strategie KISS (unabhängig von genauem Trigger):** Guard-Flag
`_initial_band_set` (Init: True, gesetzt auf False am Ende von `__init__`
nach `apply_visible_bands()`). `_on_band_changed:498` skipt Auto-Tune wenn
Flag True. **Belt-and-suspenders** falls H1 zutrifft: bei radio.ip-Pfad
auch prüfen ob `RFPresetStore` für das Band-+10W schon Werte hat — wenn
ja, kein Auto-Tune nötig (10W-Anker existiert). Das deckt Mike's
„jetzt nicht mehr"-Beobachtung erklärbar ab.

### ✅ Bug 3 (Settings 5/10/15) — V1 bestätigt + Migration-Detail

- `settings_dialog.py:331-333`: addItem "15 s"=15, "30 s"=30 ✓
- `mw_tx.py:473`: `duration_s in (15, 30)` ✓
- `settings_dialog.py:606`: `setCurrentIndex(0 if _dur == 15 else 1)` —
  **muss auf 3-Item-Logik umgestellt werden** (z.B. via `findData(_dur)`).
- `settings_dialog.py:765`: `currentData()` bei Save → unverändert OK.
- `settings_dialog.py:813`: Reset `setCurrentIndex(0)` → bleibt 5s falls
  Items-Reihenfolge 5/10/15, oder neu auf Default-Item.

**Migration:** Settings.load() popped alte Werte 30 → fallback 15 (analog
P47/P52-Pattern). Defensiv im Setter UND mw_tx.py-Whitelist-Fallback.

### ✅ Bug 4 (UX) — V1 bestätigt + Live-FWDPWR-Detail

- `auto_tune_dialog.py:86`: `band.upper()` → "15M" Verwirrung ✓
- `auto_tune_dialog.py:98, 131`: Status-Label hat ANT1 + 10W bereits ✓

**Erweiterung Live-FWDPWR:**
- `_on_tick` liest aktuell `self._parent.radio.last_swr`.
- FWDPWR-Sampling läuft in mw_tx.py via `_fwdpwr_samples` während
  `_tune_active=True`. Letzter Sample-Wert: `_fwdpwr_samples[-1]` (falls vorhanden).
- Dialog soll lesen: `self._parent._fwdpwr_samples[-1]` (mit
  try/except für leere Liste) ODER neue Property `radio.last_fwdpwr`.
- Status-Format: `f"ANT1, 10W → {band.lower()} {mode} — {elapsed}/{total} s · SWR {swr:.1f} · FWDPWR {fwdpwr:.1f}W"`

### ✅ Bug 5 (Logging) — V1 bestätigt

Aktueller Stand:
- `mw_tx.py:495`: `[P54a] Auto-TUNE {band} 10 W {duration_s}s` (Start) ✓
- `mw_tx.py:279`: `[P54-FIX] RFPreset gespeichert: ...` (Save) ✓
- `mw_tx.py:292`: `[P54-FIX] Stuetzpunkt verworfen: ...` (rf out of range) ✓
- `mw_tx.py:181`: `[P54-FIX] Phase B SKIP — SWR ...` ✓

**Fehlt:** klarer DONE-Block bei Auto-Tune. Logische Stellen:
- `_tune_post_swr_check` SWR-OK + Auto: `[P54a] DONE OK band=... swr=... fwdpwr=... rf=... duration=...s`
- `_tune_post_swr_check` SWR-bad + Auto: `[P54a] DONE FAIL (swr_bad) band=... swr=...`
- `auto_tune_dialog._on_cancel_clicked`: `[P54a] DONE FAIL (cancelled) band=...`
- `auto_tune_dialog._on_backup_timeout`: `[P54a] DONE FAIL (timeout) band=... after {duration_s+12}s`

Format-Vorschlag: 1-Zeilen-Log mit key=value-Paaren für grep-Suche.
Nutzung: `print(...)` reicht (geht in datierte Log-Datei via P20-Rotation).

## Neue V2-Findings

### V2-F1: Backup-Timer-Konstante mit Begründung statt magic +12

V1 sagt: `(duration_s + 12) * 1000`. Sauberer:

```python
# Phase B worst-case: 1.5s initial + 5×1.0s iter = 6.5s
# Post-Check delay: 2.0s
# Safety buffer: 3.5s (display delay + Qt-loop slack)
_BACKUP_GRACE_S = 12  # = 6.5 + 2.0 + 3.5
self._backup_timer.start((duration_s + _BACKUP_GRACE_S) * 1000)
```

→ R1: ist 3.5 s Safety-Puffer zu klein? Bei 5-s-TUNE wäre Phase B + Post-Check
+ Safety = 12 s ABSOLUT (also Backup 17 s = 5+12). Sicher genug.

### V2-F2: Mode-Param im AutoTuneDialog

V1: `__init__(parent, band, duration_s, mode)`. Caller
`_start_auto_tune_for_band_change` muss `self.settings.mode` durchreichen.
Sauber.

### V2-F3: Re-Entry-Schutz bereits da (mw_radio.py:397-402)

`_on_band_changed` blockt bei `_tune_active=True` schon. Bei Bug 2 (App-Start)
hilft das aber nicht weil `_tune_active` zum Initial-Zeitpunkt noch False ist.
Guard-Flag `_initial_band_set` bleibt nötig.

### V2-F4: Settings-Migration im Setter UND Load

P47/P52-Pattern: `Settings.load()` popped alte Keys. Hier:
- Alter Wert `tune_duration_s=30` → setze auf 15 beim Load.
- `mw_tx.py:473` Whitelist-Fallback bleibt als Belt-and-suspenders.
- ComboBox-Load `setCurrentIndex` muss via `findData(_dur)` arbeiten
  damit fehlende Werte Default-Index 0 zurückgeben.

### V2-F5: `_on_meter_update` FWDPWR-Sample muss auch im AutoTuneDialog-Tick lesbar sein

`_fwdpwr_samples` ist eine deque (oder Liste) in mw_tx.py. Dialog liest nur
`radio.last_swr` aktuell. Erweiterung: Helper-Property `radio.last_fwdpwr`
ODER `parent._fwdpwr_samples[-1]` mit try/except.

**KISS-Vorschlag:** im `_on_tick` einen try/except-Block um
`self._parent._fwdpwr_samples[-1]`. Bei IndexError/AttributeError → "0.0".

## Code-Plan V2 (8 atomare Commits, V1 bestätigt)

**C1:** `ui/auto_tune_dialog.py`
- `__init__` Signatur: `(parent, band: str, duration_s: int = 15, mode: str = "FT8")`
- `_title_label`: `f"🔧 Auto-TUNE läuft — {band.lower()} {mode}"` (Bug 4)
- Status-Label-Format mit FWDPWR (V2-F5)
- Backup-Timer `_BACKUP_GRACE_S = 12` konstant, Begründung im Comment (V2-F1)
- `_on_cancel_clicked` Logging `[P54a] DONE FAIL (cancelled)` (Bug 5)
- `_on_backup_timeout` Logging `[P54a] DONE FAIL (timeout)` (Bug 5)

**C2:** `ui/mw_tx.py`
- `_start_auto_tune_for_band_change` ruft Dialog mit `mode=self.settings.mode` (C1)
- Whitelist `duration_s in (15, 30)` → `duration_s in (5, 10, 15)` (Bug 3)
- Default 15 bleibt
- `_tune_post_swr_check` Auto-OK-Branch: Logging `[P54a] DONE OK ...` (Bug 5)
- `_tune_post_swr_check` Auto-Bad-Branch: Logging `[P54a] DONE FAIL (swr_bad)` (Bug 5)

**C3:** `ui/settings_dialog.py`
- ComboBox `tune_duration_s` Items 5/10/15 statt 15/30 (Bug 3)
- `setCurrentIndex` umgestellt auf `findData()` (V2-F4)
- Reset-Default-Index für 15 s (mittleres Item = index 2, oder Default-Wahl
  via `findData(15)`)

**C4:** `ui/main_window.py` ODER `ui/mw_radio.py`
- `_initial_band_set` Guard-Flag (Bug 2):
  - Init in `main_window.__init__` als instance-attr `self._initial_band_set = True`
  - Am Ende von `__init__` (nach `apply_visible_bands()`): `self._initial_band_set = False`
  - `_on_band_changed` ergänzt: bei Auto-Tune-Trigger (Z.498) zusätzlich
    `if self._initial_band_set: skip` ODER besser: anchor-Check im
    RFPresetStore (Belt-and-suspenders gegen H1-Bandpilot)

**C5:** `config/settings.py`
- `Settings.load()` defensive Migration `tune_duration_s` 30 → 15 (V2-F4)
- Anker-Check-Helper `has_rf_preset(band, watt=10) -> bool` neu in
  `core/rf_preset_store.py` (Belt-and-suspenders für Bug 2 Fix)

**C6:** `tests/test_p71_autotune_bundle.py` NEU
- T1: Backup-Timer-Wert = `(duration_s + 12) * 1000`
- T2: Title-Label-Format `f"... — {band.lower()} {mode}"`
- T3: Status-Label enthält Mode + FWDPWR-Token
- T4: Settings tune_duration_s Migration 30 → 15
- T5: Settings tune_duration_s defensiv filtern (4 → fallback 15)
- T6: ComboBox-Items sind {5, 10, 15} (currentData)
- T7: `_initial_band_set` Flag korrekt initialisiert/geclearted
- T8: App-Start triggert KEIN Auto-Tune (Flag True greift)
- T9: User-Bandwechsel triggert Auto-Tune (Flag False, alle anderen Bedingungen wahr)
- T10: Auto-Tune skippt wenn 10W-Anker existiert (Belt-and-suspenders)
- T11: Logging `[P54a] DONE OK/FAIL/cancelled/timeout` (capsys-Capture)

**C7:** `main.py` APP_VERSION 0.97.46 → 0.97.47

**C8:** HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md Update,
       FIELDTESTS.md erweitern (P71-F1...F7).

## Aus Scope (NICHT in P71)

- P72 Connect-Cancel-Fix („Ohne Radio weiter") → eigener Workflow.
- ALC-Pegel-Regelung → P70 (radio-pflichtig).
- Iter-Update-Pipeline mit Live-Convergenz-Anzeige → overkill für KISS,
  FWDPWR-Live im Status reicht.

## Field-Test (V3 §5)

- F1: App-Start ohne Settings → **KEIN** Auto-Tune-Dialog (Bug 2 Fix). Statusbar
  zeigt nur "Verbinden ... bereit". (kein Radio nötig — radio.ip=None Pfad)
- F2: Radio verbunden, Bandwechsel 20m → 17m → Auto-Tune läuft mit 15s,
  schließt VOR 20 s Backup auch bei langsamer Convergenz (Bug 1). Title zeigt
  "17m FT8", Status zeigt Mode/Watt/SWR/FWDPWR (Bug 4). (Radio nötig)
- F3: Settings → tune_duration_s ComboBox zeigt 5/10/15. Default 15. Save +
  Reopen behält Wert (Bug 3). (kein Radio nötig)
- F4: Settings-Migration: 30 in JSON manuell setzen → App-Start → Settings zeigt
  15. (kein Radio nötig)
- F5: Console-Log nach Auto-Tune-Run zeigt klare `[P54a] DONE OK band=...
  swr=... fwdpwr=... rf=... duration=...s` Zeile (Bug 5). (Radio nötig)
- F6: SWR-blockiertes Band → Marker greift, kein Auto-Tune-Dialog (bestehende
  P63-Logik, Regression-Schutz). (Radio nötig)
- F7: Cancel-Button während TUNE → sauber, Backup-Timer aus, `[P54a] DONE FAIL
  (cancelled)`-Log. (Radio nötig)

## Workflow-Reihenfolge

V2 → R1 (V4-pro via `tools/deepseek_review.py`) → V3 → Code C1-C8 → Tests →
Final-R1 → HISTORY+HANDOFF+CLAUDE+TODO+FIELDTESTS Update → P72 separater
Workflow.
