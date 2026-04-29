# HANDOFF — SimpleFT8

---

## ⛔⛔⛔ HARDWARE-WARNUNG — HOECHSTE PRIORITAET ⛔⛔⛔

### ANT1 = TX-Antenne. IMMER. Auf jedem Band.
### ANT2 = NUR Empfangs-Zusatzantenne. NIEMALS TX!

**ANT2 (Regenrinne ~15m) ist NICHT fuer Sendeleistung ausgelegt.** TX auf
ANT2 mit 100 W = Hardware-Schaden moeglich (PA, Antennen-Pfad).

| Aktion | Antenne |
|---|---|
| Manuelle CQ-Anrufe / TUNE | **ANT1** |
| OMNI CQ (passiv) | **ANT1** |
| AUTO HUNT (aktiv, v0.75) | **ANT1** |
| Diversity RX-Pattern | beide RX, **TX nur ueber ANT1** |

**Im Code (v0.75):** `set_tx_antenna("ANT1")` zentral abgesichert in
`Encoder.transmit()` (vor `ptt_on()`) UND vor jedem `tune_on()`-Aufruf
(`mw_tx.py:83`, `mw_radio.py:896/993/1078`, `dx_tune_dialog.py:192/320/382`).

---

## 2026-04-29 (v0.75) — Auto-Hunt-Modus + Hotfix

## Heute erledigt

**v0.75 Auto-Hunt-Modus** — Easter-Egg-aktivierter 10-Min-Auto-Hunt mit
Slot-Affinitaet, Race-Doppel-Check, ANT1-Pflicht zentralisiert, 6 Stop-Reasons,
5s UI-Reflexions-Cooldown, Defense-in-Depth Totmann-Hook.

**11 atomare Commits + 1 Hotfix:**
1. `fac60a0` ANT1-Guard in Encoder.transmit() + mw_tx.tune_on()
2. `385425a` AutoHunt → QObject (Signal-Foundation)
3. `b96ace2` enable/disable + _pause_remaining entfernt
4. `808de12` start/stop_auto_hunt + Signal + 10-Min-Timer (+5 Tests)
5. `4e6998e` Slot-Affinitaet + Race-Doppel-Check (+3 Tests)
6. `70ef451` Totmann-Hook → stop_auto_hunt("totmann_expired")
7. `7c6093b` Signal-Rename omni_tx → easter_egg_toggle
8. `ea7ea6e` 3-Button-Layout im QSO-Bereich
9. `81a610c` UI-Lifecycle (Easter-Egg + Countdown + 5s UI-Cooldown)
10. `75f0376` chore(release): v0.75
11. `f6d30ab` **Hotfix:** Init-Race-Guard fuer `_update_propagation_ui`
    (Latent-Bug, beim v0.75-Restart aufgetaucht)
12. `48f4864` HISTORY: Hotfix dokumentiert

**Workflow:** V1 → V2 (Self-Review, 12 Schwachstellen erkannt) → DeepSeek-R1
(31 Findings, 12 angenommen, 5 begruendet abgelehnt) → V3 → Plan-Mode-
Verifikation (1 echte Luecke `mw_tx.py:83`, 1 V3-Halluzination `_MAX_ATTEMPTS=3`)
→ 10 atomare Commits → R1-Final-Review (1 echtes Finding integriert).

**Tests:** 446 → **467 gruen** (+21 dank parametrize-Bonus ueber 6 Stop-Reasons).

## Bilanz heute

- **Backend** (Commits 1-7): Encoder-Hardware-Guard + AutoHunt komplette
  Logik-Schicht (start/stop, Timer, Signal, Slot-Affinitaet, Race-Check,
  Totmann-Integration).
- **UI** (Commits 8-9): 3-Button-Layout mutually-exclusive, Easter-Egg-Toggle
  zeigt/versteckt 2 zusaetzliche Buttons, Live-Countdown im Button-Text,
  5s-Reflexions-Cooldown nach Stop, Mode-Wechsel-Hook in `mw_radio`.
- **Doku** (Commits 10, 12): HISTORY ausfuehrlich, CLAUDE.md Header v0.75,
  Bekannte-Fallen erweitert.
- **Hotfix** (Commit 11): bestehender Init-Race-Bug aufgedeckt durch
  v0.75-Restart, defensiv via `hasattr`-Guard gefixt (5 Zeilen).

## Statistiken aktualisiert

`scripts/generate_plots.py` ausgefuehrt — DE+EN PDFs + 8 PNGs neu generiert
in `auswertung/` und `auswertung/en/`.

## Offen / Naechste Schritte (priorisiert)

### 🆕 Aus v0.75 hinzugekommen

1. **Field-Test v0.75** — Easter-Egg → AUTO HUNT 10 Min → manueller HALT →
   Bandwechsel-Stop → Totmann-Stop. 6 Verifikationsschritte siehe
   `prompts/auto_hunt_v3.md` „Verifikation am Ende".
2. **Phase 2: `btn_omni_cq`-Handler** — Button hat aktuell keinen eigenen
   `clicked`-Handler (OMNI laeuft weiter ueber bisherige Logik). Saubere
   mutually-exclusive Modus-Aktivierung als Phase 2.
3. **Push v0.75 nach GitHub** (12 Commits lokal, wartet auf Mike-OK)

### 🔥 Aus frueheren Releases

4. **Field-Test v0.74** Diversity-Bandwechsel-Bug-Fix (auch ausstehend)
5. **Settings-Dialog auf Tabs** (1-2 h) — passt nicht auf Mike's 1440×900
6. **Migration `main_window._psk_worker` → `core/psk_reporter`** (Konsolidierung)

### ⚙️ Mittelfristig

- F) Audio-Export per Slot (<1 Tag, optional)
- TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker (nicht reproduzierbar)
- Even/Odd dedizierter Timer (FT2 kritisch)
- Gain-Bias beheben (Normal-Modus Gain-Messung erzwingen)
- Tertile-Analyse Statistik
- AP-Lite Test-Pipeline (synthetische E2E-Tests)
- Per-Station DT-Offset TX
- IC-7300 Fork (TARGET_TX_OFFSET separat messen)
- Warteliste-Screenshot (sobald DL3AQJ antwortet)

## Warnungen & Fallen (v0.75-spezifisch)

- **`_auto_hunt_timer` UNABHAENGIG vom Totmannschalter** — Maus/Tastatur
  reset ihn NICHT (Bot-Tarn-Schutz). Nach jedem Stop ist Pflicht-Restart
  (User-Klick), kein Auto-Resume in `_reset_presence`.
- **Race-Doppel-Check in `select_next`** ist ethische Belt-and-suspenders
  zur 10-Min-Hard-Cap. Auch wenn DeepSeek-R1 sagt „im single-threaded GUI
  redundant" — NICHT entfernen.
- **`_MAX_ATTEMPTS = 3`** in `core/auto_hunt.py:45` ist Modul-Konstante OHNE
  Verwendung in der Klasse. 3-Versuche-Logik liegt in `qso_state.py`.
  V3 hat das halluziniert, Plan-Mode-Verifikation hat es gefangen.
- **`_pause_remaining` GIBT ES NICHT MEHR** (v0.75 entfernt). Falls in
  altem Code Verweis auftaucht: durch `active=False` redundant.
- **`btn_omni_cq` ohne `clicked`-Handler** (Phase 2 — siehe oben).
- **Init-Race-Bug in `_update_propagation_ui`** durch `hasattr`-Guard
  gefixt. Bei zukuenftigem Init-Refactor: saubere Reihenfolge wieder-
  herstellen, aber Guard belassen als Defense-in-Depth.

## Test-Suite Status

```
./venv/bin/python3 -m pytest tests/ -q
467 passed in ~7s
```

Neu seit v0.74:
- `tests/test_auto_hunt_extended.py` (10 Test-Funktionen, 21 Test-Cases
  inkl. parametrized ueber 6 Stop-Reasons)

## Letzter bekannter guter Zustand

- **Branch:** main, lokal 12 Commits ahead vom letzten Push (`668b1ed`)
- **HEAD:** `48f4864` docs(history): v0.75 Post-Release Hotfix dokumentiert
- **Tag:** kein neuer Tag (Mike entscheidet nach Field-Test)
- **Tests:** 467/467 gruen
- **App-Start:** OK (PID 8267 lief stabil heute Vormittag)
- **App-Version:** v0.75
- **Backup:** `Appsicherungen/2026-04-29_vor_auto_hunt/` (214 MB)

---

Morgen: `cd SimpleFT8` ODER `cd FT8` → `claude1` → laedt automatisch alle Memories + CLAUDE.md.
