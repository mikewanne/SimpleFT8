# P71 Auto-Tune Bundle (V1) — Field-Test-Bugs aus Mike 18.05.2026

## Stand-Anker (vor Compact)

- Letzter Commit: `1947a09 docs: FIELDTESTS.md`
- Tests: **1435 grün** (vor P71-Arbeit)
- APP_VERSION: 0.97.46 (vor P71)
- Mike-Field-Test-Status: F-S1.2 (Stats-Toggle weg) ✅, F-S1.3 (Logbuch-Auto-Show) ✅
- Mike unterwegs, autonomer Workflow erwartet, voller V1→V2→R1→V3 mit DeepSeek-V4-pro

## Field-Test-Befunde Mike 18.05. morgens

### Bug 1 — Auto-Tune Timeout 19s/15s trotz SWR 1.9 (im Bereich)

**Mike-Symptom (Screenshot):** AutoTuneDialog zeigt "TUNE Timeout"
nach 19s bei 15s-Setting, SWR 1.9 (unter Limit 2.5). Reproduzierbar
bei Bandwechsel 20m → 17m.

**Wurzel-Analyse Code:**

`_start_auto_tune_for_band_change` (mw_tx.py:472):
- `duration_s = 15` Default
- Phase A: `tune_on()` + `QTimer.singleShot(15s, _tune_stop)` (Z.499)

`_tune_stop` (mw_tx.py:139):
- Phase B: `_tune_converge_to_target(target_w=10)` (Z.179)
  - Initial-sample-phase: 1500 ms wait (Z.375)
  - max 5 Iter × 1000 ms = 5 s
  - **Total Phase B: 1.5 + 5 = 6.5 s** worst-case
- Nach Phase B: `tune_off()` + post-check token + 2 s QTimer

`_tune_post_swr_check` (mw_tx.py:212):
- läuft 2 s nach `_tune_stop` startet
- emittiert `auto_tune_done(...)` → Dialog accept/reject

`AutoTuneDialog._backup_timer` (auto_tune_dialog.py:119):
- `(duration_s + 5) * 1000 = 20 s` Backup

**Math:**
- Phase A: 15 s (warten bis QTimer feuert)
- Phase B: bis 6.5 s
- Post-Check: 2 s
- Total worst-case: 23.5 s
- Backup-Timer: 20 s

→ **Race wenn Phase B den 5s-Worst-Case erreicht.** Bei SWR 1.9 mit
nicht-konvergierendem FWDPWR läuft Phase B die volle 5 s + Initial 1.5 s
→ Backup feuert vor Post-Check.

**Lösung (V1-Vorschlag):**
- `_backup_timer` von `duration_s + 5` auf `duration_s + 12` erhöhen.
  Deckt Phase B worst-case (6.5 s) + Post-Check (2 s) + Display-Delay
  (0.8-1.5 s) + Sicherheits-Puffer.
- ALTERNATIV: `duration_s + max(Phase_B_max + Post_Check + 3, 10)` —
  KISS-Variante mit konstanter Erweiterung reicht.

### Bug 2 — App-Start triggert Auto-Tune (gelöst beim Mike, aber latent)

Mike: "autotune hat direkt bei start gefeuert (weil nicht vorhanden ?)
jetzt aber nicht mehr". App-Start ist 20m FT8 Normal. Wenn 10W-Anker
für 20m_FT8 fehlt, triggert Auto-Tune über `_on_band_changed` beim
initialen `_set_band("20m")`-Call.

**Wurzel:** `_on_band_changed` unterscheidet nicht zwischen "User-Band-
Wechsel" und "App-Start-Initial-Band-Set".

**Fix (V1-Vorschlag):** Guard-Flag `_initial_band_set` in MainWindow.
Bei App-Start auf True, nach init auf False. `_on_band_changed` prüft
Flag und überspringt Auto-Tune wenn Initial-Set. Mike's "jetzt nicht
mehr" bestätigt: nach erster Speicherung greift Anker.

### Bug 3 — Settings tune_duration_s aktuell 15/30, soll 5/10/15

Aktueller Code (mw_tx.py:473, settings_dialog.py): nur 15s + 30s zur
Auswahl. Mike-Spec: 5s / 10s / 15s. 30s raus.

### Bug 4 — AutoTuneDialog UX

Title-Label "Auto-TUNE läuft — 15M" (band="15m", `.upper()` → "15M").
Sieht aus wie "15 Minuten". Plus: Watt-Zahl und Antenne fehlen für
Funker-Übersicht.

**Vorschlag:**
- Title-Label: `f"🔧 Auto-TUNE läuft — {band.lower()} {mode}"` →
  "Auto-TUNE läuft — 20m FT8"
- Status-Label (war: `"10 W auf ANT1 — {n}/{m} s · SWR {x}"`):
  bleibt OK, ANT1 + 10W stehen schon drin. Erweiterung:
  `f"ANT1, 10 W, {mode} — {elapsed}/{total} s · SWR {swr:.1f} · "
  f"FWDPWR {fwdpwr:.1f} W"` → mehr Übersicht.

### Bug 5 — Logging für Auto-Tune-Diagnose

Mike-Wunsch "logdatei eintrag für autotune". Aktuell:
- `[P54a] Auto-TUNE {band} 10 W {duration_s}s` (Start)
- `[P54-FIX] Iter {n}: ...` (Convergenz)
- `[P54b] RFPreset-Stuetzpunkt: ...` (Save)

Fehlt: klarer Endzustand-Log mit Success/Fail-Status + Reason. Plus:
log() in core/log_setup-Datei statt nur print().

**Vorschlag:** Neue Log-Zeilen:
- `[P54a] DONE OK: SWR=1.9 FWDPWR=8.5 rf_converged=12 → saved 20m_10W`
- `[P54a] DONE FAIL (timeout): backup_timer fired after 20s`
- `[P54a] DONE FAIL (swr_bad): SWR=4.2 > Limit 2.5, Phase B skipped`
- `[P54a] DONE FAIL (cancelled): User-Cancel during {phase}`

## V1 Code-Plan (atomare Commits)

**C1:** `ui/auto_tune_dialog.py`:
- `__init__`-Param `mode: str` zusätzlich
- Title-Label `f"🔧 Auto-TUNE läuft — {band.lower()} {mode}"` (Bug 4)
- Status-Label-Format mit FWDPWR (Bug 4)
- Backup-Timer auf `duration_s + 12` (Bug 1)

**C2:** `ui/mw_tx.py`:
- `_start_auto_tune_for_band_change` ruft Dialog mit `mode` (C1)
- `duration_s in (15, 30)` → `duration_s in (5, 10, 15)` (Bug 3)
- Default bleibt 15
- Initial-Band-Guard ggf. hier oder in `_on_band_changed`
- Logging-Erweiterung (Bug 5)

**C3:** `ui/settings_dialog.py`:
- ComboBox `tune_duration_s` Optionen 5/10/15 (Bug 3)
- Migration: alter Settings-Wert 30 → 15

**C4:** `ui/main_window.py` ODER `ui/mw_radio.py`:
- `_initial_band_set` Guard-Flag setzen vor `_set_band` (Bug 2)
- `_on_band_changed` Auto-Tune-Skip wenn Flag True

**C5:** `config/settings.py`:
- Settings-Defaults bleiben; `tune_duration_s in (5, 10, 15)` defensiv
  filtern (Migration)

**C6:** `tests/test_p71_autotune_bundle.py` NEU:
- T1: Backup-Timer-Wert = `(duration_s + 12) * 1000`
- T2: Title-Label-Format
- T3: Status-Label enthält Mode-Token
- T4: Settings tune_duration_s Migration 30→15
- T5: Settings tune_duration_s defensiv filtern (4 → fallback 15)
- T6: `_initial_band_set` Flag korrekt gesetzt
- T7: App-Start triggert kein Auto-Tune (Guard greift)
- T8: User-Bandwechsel triggert Auto-Tune (Guard greift nicht)

**C7:** `main.py` APP_VERSION 0.97.46 → 0.97.47

**C8:** HISTORY.md, HANDOFF.md, CLAUDE.md, TODO.md Update

## Workflow

V1 → V2 (Self-Review) → R1 (DeepSeek-V4-pro) → V3 → Code → Final-R1.

## Aus Scope (NICHT in P71)

- Bug 2-Connect-Cancel (Ohne-Radio-verbindet-trotzdem) — separater
  Workflow P72 weil unterschiedlicher Code-Bereich
- ALC-Pegel-Regelung — bleibt P70 (radio-pflichtig)
- Iter-Update-Pipeline mit Live-Progress im Dialog — overkill für KISS,
  Status-Label mit Sekunden + FWDPWR reicht

## Field-Test (nach Code)

- F1: App-Start, prüfen dass KEIN Auto-Tune mehr feuert (Bug 2)
- F2: Bandwechsel 20m → 17m → Auto-Tune läuft mit 15s, schließt vor
  20s Backup (Bug 1). Title zeigt "17m FT8", Status zeigt Mode/Watt/SWR/
  FWDPWR. (Bug 4)
- F3: Settings → tune_duration_s ComboBox zeigt 5/10/15 (Bug 3)
- F4: Console-Log nach Auto-Tune-Run zeigt klare `[P54a] DONE OK/FAIL ...`-
  Zeile (Bug 5)
- F5: Wechsel auf SWR-blockiertes Band → Marker greift, kein Dialog
- F6: Cancel-Button während TUNE → sauber, keine Race
- F7: User-Bandwechsel triggert Auto-Tune (Regression-Schutz Bug 2)
