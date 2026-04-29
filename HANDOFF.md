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

### 🆕 Aus v0.76-Field-Test (29.04.2026 — Mike beobachtet)

**Geplant als v0.77 Bug-Fix-Release** (3 atomare Commits, alle trivial-Pfad-tauglich):

1. **🟡 Bug:** RX-Tabelle zeigt waehrend Diversity-Kalibrierung alle Eintraege
   als „A1" — Hardware schaltet aber laut `dx_tune_dialog._schedule[step]`
   zwischen ANT1/ANT2. Tag-Logik im DX-Tune-Pfad
   (`ui/mw_cycle.py:_handle_dx_tune_mode` oder `ui/dx_tune_dialog.feed_cycle`)
   bekommt aktive Antenne nicht mit. Fix: `msg.antenna = self._schedule[
   self._step][0]` vor `add_message()` setzen. Nach Kalibrierung wieder
   korrekt — also UI-only-Bug, Mess-Algorithmus ist sauber.
   (~5 Zeilen)

2. **🟠 UX:** Bestaetigungsfenster „Kalibrierung abgeschlossen"
   (`ui/mw_radio.py:_show_calibration_done`, Z.925) ist explizit
   `setWindowModality(NonModal)` + nur `dlg.show()`, kein
   `WindowStaysOnTopHint`. Folge: Klick auf Hauptapp → Dialog wandert in
   Hintergrund, Bestaetigung bleibt offen aber unsichtbar. Fix:
   `setModal(True)` + `Qt.WindowStaysOnTopHint` + `dlg.exec()`.
   Kommentar „blockiert nichts" ist irrefuehrend — Decoder-Thread laeuft
   eh weiter, nur User-Interaktion blockiert. (~3 Zeilen)

3. **🔴 Hardware-Schutz:** App-Start Warn-Dialog mit OK/Abbruch ergaenzen.
   Inhalt: „ANT1 = IMMER TX, ANT2 = IMMER nur RX. TX auf ANT2 = Hardware-
   Schaden moeglich." OK → App startet normal. Abbruch → `sys.exit(0)`.
   Pflicht-Acknowledgment pro App-Start. Mike+Claude einig: 2-Sekunden-
   Klick-Aufwand vertretbar gegen irreversiblen PA-Schaden, keine
   „heute-nicht-mehr-zeigen"-Checkbox (wuerde Schutz unterminieren).
   Position in `main.py` vor `MainWindow.show()`. (~10-15 Zeilen)

### 🆕 Aus v0.76 hinzugekommen

1. **20m FT8 Datensammlung — Ziel: 5 Tage flaechendeckend**
   (Mike+Claude+R1 abgestimmt 2026-04-29, dokumentiert in
   `prompts/...` zukuenftig).

   **Status (Stand 2026-04-29):** 2-3 Tage je Stunde-Modi-Slot, mit Luecken
   (z.B. Stunde 13 UTC bei Diversity_Normal = 0 Tage).

   **Ziel:** alle 24 Stunden × 3 Modi (Normal, Diversity_Normal,
   Diversity_Dx) auf **5 Tage flaechendeckend** (nicht 7 — siehe
   R1-Diskussion: Diminishing Returns ab 5, 7 Tage = Overengineering
   fuer Hobby-Aufwand).

   **Strategie:** „Welcher-Modus-jetzt"-Ratgeber (Claude liest
   `statistics/<Modus>/20m/FT8/*.md`-Files, zaehlt Tage je Stunde,
   schlaegt schwaechsten Slot vor). Lueckenliste schlaegt mehr-Tage-an-
   bekannter-Stelle.

   **Aufwand:** ~3 Wochen Funkbetrieb (3-4 h/Tag, durchwechseln).

   **Goldstandard 7 Tage:** explizit verworfen — nur 15% Standard-Error-
   Reduktion gegenueber 5, ~5 Wochen Aufwand. Hobby-Aufwand-Nutzen-Ratio
   stimmt nicht.

2. **Field-Test v0.75** — Easter-Egg → AUTO HUNT 10 Min → manueller HALT →
   Bandwechsel-Stop → Totmann-Stop. 6 Verifikationsschritte siehe
   `prompts/auto_hunt_v3.md` „Verifikation am Ende".
3. **Phase 2: `btn_omni_cq`-Handler** — Button hat aktuell keinen eigenen
   `clicked`-Handler (OMNI laeuft weiter ueber bisherige Logik). Saubere
   mutually-exclusive Modus-Aktivierung als Phase 2.
4. **Reset-Vervollstaendigung in `SettingsDialog._reset_defaults`**
   (R1-Final-Review v0.76, out-of-scope) — `radio_ip`, `language`,
   `stats_cb`, `debug_console_cb` werden aktuell NICHT zurueckgesetzt.
5. **Push v0.75 + v0.76 nach GitHub** (~14 Commits lokal, wartet auf
   Mike-OK)

### 🔥 Aus frueheren Releases

6. **Field-Test v0.74** Diversity-Bandwechsel-Bug-Fix (auch ausstehend)
7. **Migration `main_window._psk_worker` → `core/psk_reporter`** (Konsolidierung)

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
