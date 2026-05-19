# SimpleFT8 TODO — Stand 18.05.2026 (v0.97.53, P81 + P80 + P79 + P76 ERLEDIGT)

---

## 🆕 OFFEN — P82: „ohne Radio weiter" muss Connect immer überspringen (Mike 19.05.2026)

**Symptom:** Bei App-Start startet der Connect-Worker SOFORT parallel
zum Dialog (`ui/mw_radio.py:94` `threading.Thread(...).start()`). Wenn
das Radio antwortet bevor Mike „ohne Radio weiter" klicken kann (bei
120 km Distanz + Radio AN durchaus realistisch innerhalb 1-2s), gewinnt
`radio.connected.emit` → `dialog.accept()` → App startet MIT Radio.

**Mike-Spec (klar):** „warum muss ich das radio connecten wenn es an ist
wenn ich sage ohne radio weiter dan OHNE radio weiter und ich brauche
doch keinen connect."

→ „ohne Radio weiter" muss IMMER Demo-Modus erzwingen, egal ob Radio
antwortet oder nicht. Aktuell ist es eine Race-Condition.

**Risiko:** Wenn die App ungewollt verbindet und Mike dann TX triggert
(Auto-Hunt, CQ, TUNE), passiert echter TX auf seiner Antenne — auch
wenn Mike eigentlich Demo-Modus wollte. **Hardware-Risiko.**

**Lösungs-Ansatz (KISS, ~15 LOC):**
- ConnectStatusDialog `_on_continue_without_radio()` setzt zusätzlich
  ein `_user_cancelled = True` Flag.
- Worker-Thread (`_connect_worker`) prüft vor jeder Verbindungs-Action
  das Flag, und vor `radio.connected.emit` → wenn cancelled, NICHT
  emitten.
- Falls Worker schneller war als der Click und schon `accept()` getriggert
  hat: in `_on_continue_without_radio` zusätzlich `radio.disconnect()`
  forcieren bevor `reject()`.

**Alternative (radikaler, sauberer):** Auto-Connect entfernen, User muss
explizit „Verbinden"-Button klicken. Dann gibt's keine Race. Aber das
ist UX-Änderung (3-Button-Dialog statt 2).

**Field-Test (Mike):** App starten mit Radio AN bei 120 km → „ohne Radio
weiter" sofort klicken → App muss sicher in Demo-Modus landen, KEINE
Verbindung aufgebaut, KEINE echten Radio-Funktionen aktiv.

**Voller Workflow V1→V2→R1→V3→Code Pflicht** (Hardware-Sicherheit).

---

## ✅ P81 — Auto-Hunt-Stop-Meldung nach „✓ QSO komplett" defern ERLEDIGT (v0.97.53, 18.05.2026)

Mike-Field-Test 18.05.: „⏸ Auto-Hunt gestoppt — 5 Minuten ohne
Mausbewegung"-Meldung erschien mitten im QSO-Verlauf (zwischen RR73-Send
und finalem ✓). Mike-Wunsch: erst „✓ QSO mit XYZ komplett", DANN die
Stop-Meldung.

**Was umgesetzt:**
- State-Var `_auto_hunt_stop_msg_pending: bool` in MainWindow.
- Helper `_qso_active_for_msg_defer()` — True wenn state ∉ {IDLE, TIMEOUT,
  CQ_CALLING, CQ_WAIT}.
- Helper `_flush_auto_hunt_stop_msg()` — emittiert deferred Meldung +
  cleart Flag.
- Polling-Tick (`_on_auto_hunt_polling_tick`): bei Überschreitung +
  aktives QSO → Flag=True (defer), sonst sofort `add_info` wie bisher.
  `stop_auto_hunt` läuft IMMER (Sicherheits-Funktion bleibt).
- Anbindung in mw_qso.py an 3 QSO-Ende-Pfade:
  - `_on_qso_confirmed_visual` (Normal-Visual ✓-Pfad)
  - `_on_qso_timeout` (Hard-Timeout-Pfad, Safety-Net)
  - `_on_cancel` (HALT-Pfad — R1-F1 ROT-Fix)
- Geister-Schutz: `_on_btn_auto_hunt_toggled(True)` cleart Flag silent.

**R1-V4-pro Findings:** 1 🔴 ROT F1 HALT-Pfad-Miss (gefangen, in
`_on_cancel` integriert), 1 🟠 ORANGE F2 Thread-Race sehr gering
(dokumentiert, keine Maßnahme — Qt-Timer + State-Maschine beide
Main-Thread), 1 🟡 GELB F3 Naming + P67-T1-Test (umgesetzt).
Final-R1 „PUSH FREIGEGEBEN ✅" 0 KP.
**V4-pro 28-Cycle-Bilanz: 0 Halluzinationen.**

**Tests:** 1517 → 1533 (+16 netto). T1-T8 inkl. parametrize über alle
States. T8 deckt R1-F1 HALT-Pfad ab.

**Field-Test pending (F4 mit Radio, F1-F3+F5 ohne):**
- F1: Auto-Hunt + KEIN QSO + 5 Min Maus → sofortige Stop-Meldung.
- F2: Auto-Hunt + QSO läuft + 5 Min Maus → Meldung NACH „✓ komplett".
- F3: Auto-Hunt + QSO + 5 Min + Timeout → Meldung NACH „✗ Timeout".
- F4 (Radio): Auto-Hunt + QSO + 5 Min + HALT → Meldung NACH HALT.
- F5: Pending Flag → Manueller Restart → KEIN Geister-Emit.

---

## ✅ P80 — Unified Gain Store ERLEDIGT (v0.97.52, 18.05.2026 autonomer Workflow)

Mike-Vorschlag: 1 Messung pro Band für alle Modi (FT8/FT4/FT2 + Normal/
Diversity Std/Diversity DX). Hardware-Gain ist Antennen+Vorverstärker-
Eigenschaft, modus-unabhängig.

**Was umgesetzt:**
- Neuer Store `~/.simpleft8/kalibrierung/presets.json` mit Key=Band only.
- `ant2_calibrated`-Feld: True = echte Diversity-Messung, False = Normal-
  only-Migration → bei Diversity-Wechsel Re-Mess.
- Migration aus 3 Quellen via MAX(gain_timestamp) idempotent in
  `PresetStore.__init__`. Robust gegen korrupte JSON.
- API: alle PresetStore-Methoden nur `band` (kein ft_mode mehr).
- 6 Aufrufer in mw_radio.py refactored.
- `config/settings.normal_presets` deprecated + gepoppt.

**R1-V4-pro: 7 Findings (2 ROT F1+F2, 2 ORANGE, 3 GELB), alle eingebaut.**
**V4-pro 27-Cycle-Bilanz: 0 Halluzinationen.**

**Field-Test F1-F6 pending.**

---

---

## ✅ P79 — UI-Bundle ERLEDIGT (v0.97.51, 18.05.2026 nach Compact)

**Code fertig, Field-Test pending.** 3 von 6 Punkten code-eingespielt
(1+2+3+5+6 zusammen via Symbol-Auto-Detect; Punkt 4 ausgenommen weil
V2-F1 zeigte: schon im Code implementiert (`mw_radio:528-529` +
`:1286` + `mw_tx:710`)).

**Was umgesetzt:**

1. ✅ `mw_tx.py:401-405` Text-Erweiterung: 3 Handlungsoptionen
   („Antenne pruefen ODER SWR-Limit in Einstellungen anpassen ODER
   manueller TUNE zum Freischalten")
2. ✅ `qso_panel.add_info` Symbol-Auto-Detect: ⚠ orange, ✓ grün,
   ✗ rot, ⏳ cyan. Variante B KISS — nur Symbol gefärbt, Rest grau
   (keine Call-Site-Migration der 30 Aufrufer).
3. ✅ Konsistenz automatisch durch Symbol-Konvention.
4. ⏸ **Ausgenommen** (V2-F1: alle bekannten add_info-Pfade existieren
   bereits). Field-Test entscheidet ob spätere Ergänzung nötig.
5. ✅ `mw_radio._show_calibration_done` Modal raus (50 LOC → 8 LOC)
   ersetzt durch `add_info` + Statusbar-Echo 3s (R1-F6: deckt Tab-
   Wechsel + Auto-Trim).
6. ✅ Farbpalette an Codebasis angepasst (#FFAA00/#44FF44/#FF4444/#44BBFF).

**Field-Test F1-F6 pending** (alle ohne Radio durchfuehrbar).

---

---

## ✅ P76-C — TUNE-bad setzt Band-Marker proaktiv (P63-Luecke) — ERLEDIGT v0.97.50

**Umgesetzt 18.05.2026** autonom mit DeepSeek-V4-pro. Voller
V1→V2→R1→V3→Code→Final-R1-Workflow.

- Mike-Field-Test mit Limit=1.5: TUNE-bad logged korrekt aber CQ blieb klickbar
- Root: `_tune_post_swr_check` else-Branch hatte KEIN `_swr_blocked_bands.add` —
  P63-Luecke (Marker wurde heute nur vom Watchdog beim TX-Alarm gesetzt)
- Fix (Variante A, ~10 LOC): Marker-Set im else-Branch wenn tuner_present=True,
  VOR is_auto-Abzweigung (manuell + Auto-Tune konsistent)
- R1 12 Findings, 0 ROT, 4 🟡 (alle uebernommen). Final-R1 „PUSH FREIGEGEBEN"
- Tests 1474→1484 (+10 P76-C). Plus 1 P75-Test angepasst (Kommentar-Marker)
- Was bleibt klickbar: Bandwechsel + manueller TUNE (Freischalt-Pfade)

**Field-Test pending bei Mike** (alle Radio-pflichtig):
- F1: Limit=1.5, TUNE 40m → SWR-bad → CQ-Klick SOFORT blockiert
- F2: OMNI-Klick blockiert
- F3: Auto-Hunt-Klick blockiert
- F4: Manueller TUNE bei besserem SWR → Marker geloescht
- F5: Bandwechsel auf 17m bleibt erlaubt

---

## ✅ P76-A — SWR-Safety-Bug (False-OK durch FlexRadio-Clamp) — ERLEDIGT v0.97.49

**Umgesetzt 18.05.2026 nach Compact** autonom mit DeepSeek-V4-pro.
Voller V1→V2→R1→V3→Code→Final-R1-Workflow.

- Mike-Field-Test 17m: SWR 2.7 (>Limit 2.5) wurde als „TUNE OK SWR 1.0" 3× geloggt
- Root: `_tune_post_swr_check` las `radio.last_swr` 2 s NACH `tune_off()` —
  FlexRadio Meter-Loop liefert Werte <1.0 → `_handle_meter` Clamp auf 1.0 →
  `_last_swr` ueberschrieben
- Fix (Variante A, KISS, ~15 LOC): State-Var `_tune_last_valid_swr`,
  Freeze direkt vor `tune_off()`, Read+Reset im Post-Check, FAIL bei
  None oder <1.0
- R1-V4-pro F5/F6/F13 alle uebernommen (F6 war echter ROT Disconnect-Stale)
- Final-R1 V4-pro „PUSH FREIGEGEBEN" 0 KP
- **Tests 1463→1474 (+11 P76-A)**

**Field-Test pending bei Mike** (siehe FIELDTESTS.md):
- F1 (Radio): 17m TUNE → „⚠ Tuner konnte nicht matchen — SWR 2.7" + Marker rot
- F2 (Radio): 40m TUNE SWR-niedrig → echter Wert im Log, NICHT 1.0
- F3 (Radio): Auto-Tune-Dialog zeigt echten SWR
- F4 (Radio): Disconnect-Re-Connect → kein Stale-State

---

## 🐛 P76-B — Auto-TUNE-Dauer länger als eingestellt (Mike-Field-Test 18.05. nach P75)

**Symptom (Mike-Field-Test 18.05.):** Auto-TUNE bei Bandwechsel auf
10m mit Setting `tune_duration_s=5` hat „wesentlich länger als 5 s"
gedauert (gefühlt ~9 s).

**Vermutete Wurzel (kein Bug, aber UX-Diskrepanz):**
- Phase A (Tuner-Match): 5 s wie eingestellt
- Phase B (Closed-Loop-Convergenz bis FWDPWR ≈ 10W): max 1.5 s Initial
  + 5 × 1.0 s Iter = **bis 6.5 s zusätzlich**
- Post-Check-Delay: 2 s
- **Total bis Dialog zumacht: bis 5 + 6.5 + 2 = 13.5 s worst-case**

Dialog-Status-Label zeigt aber nur „0 / 5 s" → User erwartet 5 s,
sieht 9-13 s und denkt: Setting greift nicht.

**Fix-Idee (UX):** Status-Label im AutoTuneDialog erweitern:
- Phase A: „TUNE-Match: N / 5 s"
- Phase B: „Power-Convergenz: N / max 6.5 s"
- Post-Check: „SWR-Verifikation: 2 s"

ODER (KISS-Variante): einfacheres Label „TUNE läuft — bitte warten",
keine N/Ms-Angabe → keine falschen Erwartungen.

DeepSeek-Diskussion beim Fix.

---

## ✅ P75 — TUNE-Button-Bug + Style + Fenster-Konsolidierung (Variante A) — ERLEDIGT v0.97.48

**Umgesetzt 18.05.2026** autonom mit DeepSeek-V4-pro. Voller
V1→V2→R1→V3-Workflow. R1 entschied **Variante A** (Header-Banner)
statt State-Machine-Refactor (KISS-Vorrang, 30 Min vs 3-4 h).

- TUNE-Button bleibt nach Auto-Stop visuell aktiv → Fix mit
  `blockSignals + setChecked(False)` in `_tune_stop`.
- TUNE-Style-Harmonisierung: eigenes `_tune_btn_style`-Cluster
  (dezent-gelb inaktiv `#BBA060`, grün aktiv analog OMNI/CQ).
- Modal-Konsolidierung Variante A: DXTuneDialog kriegt
  `prev_tune_swr`-Param + grünen Header-Banner als Phase-1→Phase-2-
  Übergang. AutoTuneDialog bleibt eigenständig für manuellen TUNE.
- SWR-bad-manueller-TUNE-Pfad: QMessageBox.warning → `qso_panel.add_info`.

**Tests 1453→1463 (+10)**. APP_VERSION 0.97.47→0.97.48.

**P74-B Autogain (Stale-Hinweis + Cross-Band-Interpolation) bleibt
offen** als separater Workflow.

---

## 🆕 P74 — UX-Konsolidierung + Autogain-Konzept (Mike-Wunsch 18.05. nach P71-Field-Test)

### P74-A: Mess-/TUNE-Status in EINEM Fenster konsolidieren

**Mike-Beobachtung 18.05.:** Nach Auto-TUNE-Abschluss bei Bandwechsel
30m → ploppt der DX-Kalibrierungs-Dialog (kein Preset → 8 Zyklen Mess-
Sequenz). Nach Kalibrierungs-Ende möglicherweise weiteres Modal. Mike:
„viele Fenster die aufploppen verwirren. Ein Fenster was erst die
Aktion und das Beenden anzeigt ist übersichtlicher."

**Aktueller Zustand:**
- AutoTuneDialog (Auto-TUNE bei Bandwechsel) schließt sich nach
  Erfolg/Misserfolg sauber.
- Wenn danach kein Diversity-Preset existiert → `_check_diversity_preset`
  öffnet DXTuneDialog (8 Zyklen, 2 Min Messung).
- SWR-bad-Pfad: zusätzliches QMessageBox „Tuner konnte nicht matchen"
  (`_tune_post_swr_check` Z.321).

**Lösungs-Vorschlag (KISS):**
- AutoTuneDialog am Ende NICHT sofort schließen, sondern Erfolgs-Banner
  zeigen + Button „Kalibrierung jetzt starten" / „Später".
- Bei „Jetzt starten": AutoTuneDialog wechselt in Kalibrierungs-Phase
  (gleicher Dialog, anderer Inhalt). Am Ende: Banner „Fertig — N
  Stützpunkte gespeichert" + Schließen-Button.
- Bei SWR-bad: Modal wegfallen lassen, Info-Banner im AutoTuneDialog
  selbst (auch nur 1 Fenster).

**Aufwand:** mittel (1-2 Stunden). UI-Refactor von 2 Dialogs zu 1
State-Machine-Dialog. Voller V1→V2→R1→V3-Workflow Pflicht.

### P74-B: Autogain prüfen — wie weit verwirklichbar?

**Mike-Wunsch 18.05.:** „Lass uns prüfen wie weit wir Autogain
verwirklichen können."

**Aktueller Zustand (Recap):**
- Diversity-Gain-Kalibrierung läuft via DXTuneDialog: 8 Zyklen × 15s = 2
  Min, interleaved über ANT1/ANT2 × Gain 10/20 dB. User clickt
  „Kalibrieren" oder es triggert bei fehlendem Preset automatisch.
- Ergebnis: pro `(band, FT-Mode)` ein Std-Preset + ein DX-Preset
  gespeichert (P51-Bundle).
- Gain wird NICHT automatisch nachgeregelt während des Betriebs —
  Preset bleibt fix bis User neu kalibriert.

**Frage:** Kann das so weit „autogain" werden, dass:
- (a) **Auto-Re-Kalibrierung** wenn alte Mess-Werte unzuverlässig sind
  (Drift, andere Tageszeit, andere Solar-Conditions)?
- (b) **Live-Gain-Adjustment** während des Betriebs (z.B. wenn Stations-
  Anzahl plötzlich einbricht → Gain hochregeln, oder umgekehrt)?
- (c) **Smart Initial-Gain** beim Band-Switch ohne Preset, statt 2-Min-
  Mess-Pflicht?

**Trade-offs:**
- (a) ist machbar via Decay-Timer („Preset > 7 Tage alt → Vorschlag
  Neu-Kalibrieren") — KISS.
- (b) ist überengineered für Hobby-Kontext (siehe Projekt-Philosophie
  in CLAUDE.md). Kann Funkverkehr stören.
- (c) wäre möglich via Cross-Band-Interpolation (analog `_kruecken_
  skalierung` aus P54-FIX): wenn 40m+20m kalibriert, 30m schätzen.

**Aktion:** DeepSeek-Diskussion über Machbarkeit + Mike-Spec klären
bevor Code-Plan. Wahrscheinlich Hybrid (a) + (c), (b) verwerfen.

**Aufwand:** unklar bis Konzept steht (1-3 Tage je nach Scope).

---

## 🤖 DeepSeek-V4-pro-Empfehlung 18.05.2026 (`prompts/p74_discussion.md`)

### P74-A — Modal-Konsolidierung: KLARES JA

**Empfehlung:** **DXTuneDialog um TUNE-Phase erweitern** (State-Machine
`TUNE → GAIN_CYCLES → FINISHED`). EIN Fenster für gesamten Pipeline-
Pfad bei Bandwechsel ohne Preset. AutoTuneDialog bleibt nur für
manuellen TUNE-Button.

**KISS-Check:** ✓ ja, weniger UI-Refactor als komplett neuer Wizard.

**Architektur-Skizze:**
- `DXTuneDialog._state ∈ ('TUNE', 'GAIN_CYCLES', 'FINISHED')`
- `_start_tune_phase()` ruft `radio.tune_on(10W)` + 15s-Timer
- `_on_tune_finished(success, swr)` → SWR-OK → State `GAIN_CYCLES` +
  `_start_step()`; SWR-bad → Fehler-Banner + Schließen
- `mw_radio._start_dx_tuning()` überspringt separaten AutoTuneDialog,
  ruft direkt erweiterten DXTuneDialog
- `_tune_token` aus MainWindow im Dialog speichern (Race-Schutz bei
  schnellen Bandwechseln)
- `radio.connected`-Signal weiterhin im MainWindow verfolgen → Dialog
  per `reject()` bei Disconnect

**Race-Trade-off:** TUNE-Phase muss Cancel + Verbindungsverlust sauber
abfangen (mehr State-Mgmt).

### P74-B — Autogain: 2-PHASEN-PLAN

**Phase 1: Stufe (a) Auto-Re-Kalibrierungs-HINWEIS**
- Beim Bandwechsel: `gain_timestamp > 14 Tage` → dezenter Statusbar-
  Hinweis „⚠ Gain-Kalibrierung 16 d alt — KALIBRIEREN empfohlen"
- **Kein** automatischer Start (User-Unterbrechung vermeiden)
- KISS-trivial: Lese-Check + Toast

**Phase 2: Stufe (c) Cross-Band-Interpolation**
- Neue Methode `PresetStore._interpolate_gain(band, ft_mode)`
- Lineare Interpolation über Mittenfrequenz aus 2 nächsten kalibrierten
  Bändern (z.B. 40m+20m → 30m schätzen)
- Markiert als `"interpolated": true`, **nicht** als valid gespeichert —
  echte Messung überschreibt später
- Bei nur 1 Nachbar: Krücke (Werte kopieren) analog `_kruecken_skalierung`
  aus P54-FIX
- In `_check_diversity_preset`: bei `missing` zuerst Interpolation
  versuchen → bei Erfolg `_enable_diversity` mit Warn-Statusbar „Gain
  geschätzt — KALIBRIEREN zur Optimierung"

**Stufen (b) Live-Adjustment + (d) SNR-Feintuning: VERWORFEN**
für Hobby-Kontext (Funkverkehr-Risiko, Komplexität, Projekt-Philosophie).

**Implementierungs-Reihenfolge:**
1. P74-A zuerst (1-2 h, sauberer UX-Win, Voraussetzung für späteren
   Interpolations-Pfad)
2. P74-B Phase 1 (1 h, Statusbar-Hinweis bei stale Preset)
3. P74-B Phase 2 (3-4 h, Interpolations-Methode + Pipeline-Hook)

Alle drei: voller V1→V2→R1→V3-Workflow PFLICHT (CLAUDE.md).

---

## 🆕 P73 — Settings-UX-Bundle (für spätere Besprechung mit Mike)

**Mike-Wunsch 18.05.2026 nach P71-Field-Test:**

### P73-A: TUNE-Einstellungen gemeinsamer Tab
**Aktuell:** TUNE-Dauer (5/10/15 s) im Tab „FT8 & Diversity", TUNE-Leistung
in anderem Tab. Mike: „der Übersichtlichkeit halber besser unter einem Tab
organisieren".

**Vorschlag:** Eigenen Tab „TUNE" oder Untergruppe „TUNE-Einstellungen"
mit:
- TUNE-Dauer (5/10/15 s)
- TUNE-Leistung
- Auto-TUNE bei Bandwechsel (Toggle)
- Tuner vorhanden (Toggle)
- SWR-Limit (separat? oder hier?)

**Aufwand:** 30-60 Min (UI-Reorganisation, kein Logik-Eingriff). Voller
V1→V2→R1→V3-Workflow trotzdem PFLICHT (CLAUDE.md).

### P73-B: Mess-Zyklen-Anzahl klären
**Mike-Beobachtung:** AutoTuneDialog/DX-Tune-Dialog zeigt aktuell „8 Zyklen
interleaved" (Code `ROUNDS=2 × 2 Antennen × 2 Gain-Stufen`). Mike erinnert
sich „manchmal mit 6 Zyklen". Vermutung: alter Code-Stand vor P51-Refactor
(P51 v0.97.28 hatte aus zwei Mess-Sessions à 8 = 16 → eine Session à 8
gemacht, also 50% gespart).

**Klärung:** War vor P51 mal 6 Zyklen geplant/im Code? Git-History prüfen.
Oder ist 6 Zyklen eine UX-Idee für noch schnellere Messung (z.B.
`ROUNDS=1.5` durch Skip einer Gain-Stufe wenn früh klar)?

**Aktion:** mit Mike besprechen bevor Code-Änderung.

---

## ✅ P71 — Auto-Tune Bundle (5 Bugs aus Mike-Field-Test 18.05.) — ERLEDIGT v0.97.47

**Umgesetzt 18.05.2026** autonom während Mike unterwegs mit DeepSeek-V4-pro.
Voller V1→V2→R1→V3-Workflow. R1 fand 5 Findings, davon 3 blocking
(F1+F2+F3) + F5 angenommen, F4 KISS-akzeptiert.

- **Bug 1 (F1 🔴):** Backup-Timer-Race: Grace 5 → 12 s.
- **Bug 2 (F2 🟠):** App-Start triggert Auto-Tune ungewollt: Belt-and-
  suspenders Guard-Flag `_initial_band_set` + `RFPresetStore.has_anchor()`.
- **Bug 3 (F3 🟡):** Settings tune_duration_s 5/10/15 s (war 15/30 s),
  findData-Fallback + Settings.load()-Migration.
- **Bug 4:** Title `band.lower()+mode`, Status mit Live-FWDPWR (KISS-
  Coupling via `_fwdpwr_samples[-1]`).
- **Bug 5 (F5 🟡):** 5 DONE-Logs in `_tune_post_swr_check` und Dialog
  (OK + 4× FAIL: swr_bad, disconnect, cancelled, timeout).

**Tests 1435→1452 grün (+17)**. APP_VERSION 0.97.46→0.97.47. Backup
`Appsicherungen/2026-05-18_v0.97.46_vor_p71/`. **V4-pro 22-Cycle-Bilanz:
0 Halluzinationen, 1 ROT-Bug F1 gefangen, F2-Wurzel-H3 sauber widerlegt.**

**Field-Test pending (siehe FIELDTESTS.md):**
- F1+F3+F4 ohne Radio (App-Start ohne Auto-Tune-Trigger, ComboBox-Items,
  Settings-Migration 30 → 15).
- F2+F5+F6+F7 mit Radio (Backup-Race-Fix, DONE-Logs, SWR-Marker, Cancel).

---



---

## 🆕 OFFEN — Code-Vorschläge aus DeepSeek-Diskussion 16.05.2026 (GitHub-Review)

Während der kontroversen DeepSeek-Diskussion über die GitHub-Präsentation
sind drei mögliche Code-Änderungen aufgekommen. KEIN sofortiger Fix —
Mike entscheidet pro Punkt.

### ✅ P67 — Auto-Hunt 5-Min-Maus-Inaktivitäts-Schicht (Variante C) — ERLEDIGT v0.97.43

**Umgesetzt 16.05.2026 nach Mike-Entscheidung Variante C:** Auto-Hunt
10-Min-Hard-Cap bleibt unverändert, ZUSÄTZLICHE Schicht „5 Min ohne
Mausbewegung → Auto-Hunt stoppt". Beide parallel, wer zuerst greift
gewinnt. Voller V1→V2→R1→V3→Code→Final-R1 mit DeepSeek-V4-pro.
Reason `mouse_inactive_5min`. Kein `_abort_active_tx` (laufendes QSO
darf zu Ende). Tests 1352→1367 (+15). Field-Test F1-F5 pending.

---

### P68 — OMNI-CQ Continuous Gap Re-Evaluation innerhalb eines Paritäts-Blocks

**Aktuell:** OMNI-CQ pickt die TX-Frequenz EINMALIG am ersten TX eines
Paritäts-Blocks. Innerhalb der 10/20/40 Versuche bleibt es bei der einmal
gewählten Frequenz, auch wenn andere Stationen dort einsteigen.

**Vorschlag:** Vor jedem TX innerhalb eines Blocks die existierende
`_refresh_diversity_freq_view()`-Logik nutzen um zu prüfen ob die aktuelle
Frequenz noch gut ist. Bei größerer Kollision: spätestens nach 2 weiteren
TX-Versuchen auf neue Lücke wechseln.

**Begründung:** DeepSeek R4-Punkt: „Sticky-Frequenz ist nicht QRM-konform"
— Worst-Case wenn 10 OMNI-Nutzer dieselbe Frequenz picken und nie ausweichen.

**Pro:** Bessere Co-Existenz mit anderen Stationen.
**Contra:** Komplexität — Spec-Erweiterung in `core/omni_cq.py`.
Aktueller Sticky-Ansatz ist KISS.

**Aufwand:** ~1 Tag inkl. Tests.

---

### ✅ P69 — Konfidenz-Intervalle für Diversity-Mess-Tabellen — ERLEDIGT v0.97.46

**Umgesetzt 17.05.2026 autonom während Mike unterwegs.** Voller
V1→V2→R1→V3-Workflow mit DeepSeek-V4-pro. R1 fand 6 Findings, alle
adressiert.

- `scripts/bootstrap_ci.py` NEU: Block-Bootstrap über (date, hour)-Blöcke,
  5000 Iterationen, Percentile-CI. Threshold n < 15 → „insufficient",
  15 ≤ n < 25 → „limited", n ≥ 25 → „ok". F-DIV0 ROT-Bug aus R1
  abgefangen (Resample verwerfen wenn normal_mean == 0).
- `scripts/print_ci_for_readme.py` NEU: Helper für künftige
  README-Updates.
- PDF-Tabelle Seite 3 zeigt jetzt 2-zeilig „Punktschätzer + 95%-CI".
- 6 README-Tabellen (DE+EN, 40m+20m+30m) auf aktuelle Daten + CI gebracht.

**Wichtigste Erkenntnis:** Daten haben sich seit alter README
weiterentwickelt. 40m Std fiel von +126% auf +62% (CI +32-+102%,
signifikant). 20m+30m CIs enthalten 0 → kein signifikanter Effekt
nachweisbar. Ehrlicher als die alten Punktschätzer.

Tests 1415 → 1435 (+20). Push pending bis Mike-Freigabe.

**Followup-Idee P69b (optional, niedrig priorisiert):** BCa-Bias-
Korrektur für Edge-Case n < 25 implementieren wenn Datenbasis bei
einem Band längere Zeit unter Threshold bleibt. Aktuell nicht nötig
weil 40m+20m+30m alle n ≥ 25 haben.

---

### P70 — ALC-Pegel-Überwachung und -Korrektur (Mike-Idee 17.05.2026)

**Aktuell:** Closed-Loop regelt `rfpower` (Endstufen-Ausgangsleistung)
gegen Ziel-Watt via FWDPWR-Feedback. `tx_audio_level` ist statisch auf
maximal 0,75 begrenzt (CLIP_LIMIT in `mw_tx.py:648`), Software-Peak
wird angezeigt („Clipschutz X%"). **Was fehlt:** der vom Radio
gemeldete `HWALC`-Pegel (via VITA-49 Meter) wird empfangen, an
`control_panel.update_alc()` weitergereicht — und die Methode ist
`pass` (Z. 1769-1771). Wir wissen also nicht ob die Eingangsstufe
des Flex in ALC-Kompression läuft.

**Mike-Vergleich zum Icom-Setup:** Beim Icom hat Mike den USB-Audio-
Pegel am Mac so eingestellt dass die ALC-Lampe gerade eben zuckt —
maximale lineare Modulation ohne Übersteuerung. Das macht das Flex
heute nicht, weil wir nur den End-Pegel (rfpower) regeln, nicht die
Eingangs-Modulation.

**Vorschlag (V0-Spec, nicht final):**
- HWALC-Wert in der Statusleiste anzeigen (analog SWR/FWDPWR)
- Schwellwert in Settings (z. B. „ALC max. 3 dB" als Default)
- Closed-Loop erweitern: bei ALC > Schwelle → `tx_audio_level`
  reduzieren BEVOR rfpower erhöht wird
- Beim Stabilität-Pendel: ALC eben gerade messbar = optimal
  (analog Mike's Icom-Justage)

**Begründung:** Linearitäts-Spielraum sicherstellen. Aktuelle
Software-Peak-Anzeige sagt nichts darüber ob das Radio intern
komprimiert (= mehr IMD/Splatter ins Nachbarband).

**Pro:** Sauberes Sendesignal über alle Bänder, ehrliches HF-
Verhalten, kein „verstecktes Übersteuern". Lehrreich für Hobby-
Funker die das vom Icom kennen.
**Contra:** Komplexität — zwei verkoppelte Regler (audio-level
+ rfpower) brauchen sauberes Anti-Windup. Konvergenz darf nicht
oszillieren.

**Aufwand:** ~2-3 Tage inkl. V1→V2→R1→V3-Workflow, neue
HWALC-UI-Anzeige, Closed-Loop-Erweiterung, Tests + Field-Test
F1-F5 (Hardware-pflichtig).

**Offene Fragen für V1:**
- HWALC-Skala beim Flex: was ist „0 dB" vs. „eben sichtbar"? Erst
  empirisch messen.
- Reihenfolge: erst audio runter, dann rfpower hoch? Oder
  symmetrisch?
- Pre-TX-Test (Tune-artig) oder echte Live-Regelung im QSO?

---

## ✅ 16.05.2026 erledigt — P52: Statistik-Toggle raus + 90-Tage-Rolling-Window v0.97.41

**Trigger:** Mike-Klärung 14.05.: Stats-Toggle macht keinen Sinn weil
Bandpilot ohne Stats blind ist und Auswertungen sie brauchen. Plus Stats
wuchsen unbegrenzt (~1 MB/Tag).

**Voller V1→V2→R1→V3→Code→Final-R1-Workflow autonom mit DeepSeek-V4-pro.**

**Architektur:** `core/stats_cleanup.py` NEU mit zwei Regex-Pattern
(Stunden + Tag) und rekursivem rglob. Cutoff aus Dateinamen-Datum (NICHT
mtime — Backup-robust). Settings-Migration via Pop in `Settings.load()`
analog P47.

**R1-V4-pro:** 0 Bug, 3 Risiko (alle bearbeitet), 2 Verb, 1 Hinweis.
**Final-R1 V4-pro:** „Push-bereit, sauber, KISS, gut getestet." 0 KP.
**V4-pro 16-Cycle-Bilanz:** 0 Halluzinationen.

**Tests 1339 → 1347 (+8 P52)**. Backup `Appsicherungen/2026-05-16_v0.97.40_vor_p52/`.

**Plan-Files:** `prompts/p52_stats_toggle_remove_v[1,2].md`.

**Field-Test pending (kein Radio):** F1-F4 — siehe HANDOFF.md.

---

## ✅ 16.05.2026 erledigt — Bundle-L-Revert: Bypass = Demo-Modus v0.97.40

Bundle L Punkt B (v0.97.38) hatte `_on_continue_without_radio` auf quit()
umgestellt — UX-Logik-Bug, beide Buttons machten dasselbe. Plus Crash-Pfad.
Revert: Bypass wieder Demo-Modus (reject only), Beenden bleibt Quit
(Hotfix v0.97.39 Reihenfolge bleibt). Tests 1339→1339 (T4 invertiert,
T7 reduziert). Mike-Klärung 16.05.: „häää ne eigendlich nicht…".

---

## 🆕 OFFEN — P64: Simulations-Modus für Tests ohne Radio (Mike 16.05.2026)

**Trigger:** Mike's Frage 16.05.: „können wir später zustände auch simulieren
wie imaginäre swr werte oder empfangende stationen oder zu komplex?"

**Mike-Use-Case:** 4 Wochen ab 16.05.2026 ohne Radio-Zugriff (Mike weit weg
vom FlexRadio). Damit UI-Tests, Bug-Fixes und neue Features trotzdem
visuell prüfbar sind: künstliche Werte einspeisen.

**Aufwand-Einschätzung Claude 16.05.:**

| Was | Komplexität | Aufwand |
|---|---|---|
| SWR-Wert simulieren | einfach | 1-2 h |
| Einzelne fake Decoder-Messages | mittel | 0.5 Tag |
| Komplette QSO-Simulation | mittel-hoch | 1-2 Tage |
| Fake-Radio als Subclass von RadioInterface | hoch (Architektur) | 2-3 Tage |

**KISS-Vorschlag (V0 nicht spezifiziert):**

1. **SWR-Simulator:** Env-Var `SIMPLEFT8_SIM_SWR=5.2` triggert
   `swr_alarm.emit(5.2)` 30s nach App-Start für Watchdog-Tests
2. **Decoder-Simulator:** Env-Var `SIMPLEFT8_SIM_STATIONS=path/to/csv`
   liest pro Slot fake Messages, zeigt sie im RX-Panel an
3. **Debug-Menü** (Settings-Tab „Daten & Tools"): Buttons
   „SWR-Alarm auslösen", „Fake QSO complete", „Fake Station hinzufügen"
4. **Fake-Radio (optional Stufe 2):** `radio_type: "sim"` in Settings,
   `radio/sim_radio.py` als minimaler Stub (set_*/get_* no-ops, alle
   Meter returnen plausible Werte)

**Vor Beginn:** V1→V2→R1→V3 Workflow. KISS-Frage besonders wichtig —
nur was Mike in 4 Wochen wirklich braucht, nicht universal simulator.

**Aufwand-Estimate Mike-Auswahl-abhängig:** Stufe 1 (Env-Vars + Debug-
Menü) = ~1 Tag. Stufe 2 (Fake-Radio) = +1-2 Tage.

---

## 🆕 OFFEN — P65: Light-Mode (Settings-Toggle Dark↔Light) (Mike 16.05.2026)

**Trigger:** Mike 16.05.: „mit deepseek besprechen wie kompliziert es ist
in einstellungen den darkmodus umschaltbar machen in normalen modus
(farben normale app grau , welche farben für anzeigen. darkmode ist so
top, normaler modus grau windows standart app mäßig)".

**Mike-Spec klargestellt:**
- Default bleibt **Dark-Mode** (aktuell, „top")
- Neuer Light-Mode: Windows-Standard-Stil, hellgrau, default-system-look
- Settings-Toggle in Tab „Daten & Tools" oder „Allgemein"
- App-Restart erforderlich oder live-switch? — Klären

**Erste Aufwandseinschätzung Claude 16.05.:**

Aktuell hat die App **inline Stylesheets** an vielen Stellen verstreut
(grep zeigt ~50+ setStyleSheet-Aufrufe in `ui/main_window.py`,
`control_panel.py`, `rx_panel.py`, `qso_panel.py`, `connect_status_dialog.py`,
`bandpilot_dialogs.py`, `dx_tune_dialog.py` etc.). Plus Farb-Konstanten
wie `#00CC44` (Cyan-Akzent), `#FF66CC`/`#FFAA00` (Slot-Bar), `#16192b`
(Dialog-BG), `#7CC` (Title-Cyan).

**Zwei Wege:**

**Weg A — Theme-Konstanten + Mode-Switch:**
- Modul `ui/theme.py` mit `THEME_DARK` und `THEME_LIGHT` Dicts
- Alle inline-Hexcodes durch `theme.cyan_accent` etc. ersetzen
- App-Restart-Pflicht (Qt-Stylesheet-Hot-Reload ist tricky)
- **Aufwand:** mittel-hoch, ~2-3 Tage. ~50 Stylesheet-Stellen umstellen +
  Theme-Modul + Settings-Hook + Tests

**Weg B — Qt-Stil-Override (`QApplication.setStyle("Fusion")`)**:
- Bei Light-Mode globaler `setStyle("windowsvista")` oder `"fusion"`
- Bestehende Stylesheets aber bleiben (überschreiben den nativen Look)
- Funktioniert nur teilweise — sieht hybrid aus
- **Aufwand:** klein, 0.5 Tag — aber Ergebnis vermutlich nicht „windows-
  standard" sondern „windows-mit-Cyan-Akzenten"

### DeepSeek-V4-pro Brainstorm (16.05.2026)

**Empfehlung: KEINEN sauberen Light-Mode bauen — KISS-Pragmatismus.**

| Weg | Aufwand | Bewertung |
|---|---|---|
| **A — Theme-Modul + 259 Stellen umstellen** | 3-5 Tage | Overengineering für 5%-Use-Case |
| **B — Globaler QStyle-Wechsel** | 1-2 h | Unbrauchbar — hybride Optik, Stylesheets dominieren weiter |
| **C — Hybrid (nur äußere Widgets hell)** | 2-3 Tage | Halbfertig-Optik durch dunkle Inseln (FrequencyHistogram etc.) |
| **D — „Hell-Taste" Notlösung** | **1 Tag** | Nur Haupt-BG + Card-BG + Text-Farbe wechseln, Rest dark belassen. Bewusst als Not-Theme akzeptieren |

**Essenzielle Farben für minimalen Light-Mode:**
- BG `#16192b` → `#F0F0F0`
- Card-BG `#06060c` → `#FFFFFF` + Border
- Text `#CCC` → `#333`/`#222`
- Buttons `#2a2f4a` → `#E0E0E0` + dunkler Rand
- Cyan `#7CC` → ggf. `#0066AA` (Kontrast auf Weiß)
- Grün/Orange/Magenta-Akzente: meist OK

**Live-Switch:** Restart-Pflicht — Qt-Stylesheet-Hot-Reload zur Laufzeit
ist fehleranfällig (viele Widgets setzen Style im Konstruktor).

**Fallen:** CustomPainted Widgets (`FrequencyHistogramWidget`) haben
hardgecodete `QColor`s in `paintEvent()` → bleiben dunkle Inseln. Card-
Konstanten in `control_panel.py` (`_CARD_SS_BLUE` etc.) müssten
dynamisch werden — der Knackpunkt für Weg A.

### Mike-Entscheidung pending

Optionen:
1. **Skip** — Light-Mode kommt nicht (DeepSeek-Empfehlung, KISS)
2. **Not-Theme (1 Tag)** — Hell-Taste mit 4-5 Farb-Swaps, dunkle Inseln
   bleiben, als bewusste Notlösung dokumentiert
3. **Sauberes Theme-Modul (3-5 Tage)** — wenn Mike es wirklich will

Default-Empfehlung: **Skip**. Zeit lieber in echte Features stecken.

---

## ✅ 15.05.2026 erledigt — Bundle L: Display-3-Auto-Move + Bypass-Button=Beenden v0.97.38

Mike-Wünsche während Remote-Fernwartung bis 10.06.2026. **A:** App-
Hauptfenster automatisch auf Display 3 (2944,0) bei jedem Start, mit
defensivem QScreen-Check (R1-F1). **B:** `_on_continue_without_radio`
ruft `QApplication.quit() + reject()` statt Demo-Modus.

Voller V1→V2→R1→V3→Code→Final-R1-Workflow. R1 5 Hinweise alle
übernommen. Final-R1 V4-pro 0 KP „Push freigegeben." **V4-pro
14-Cycle-Bilanz: 0 Halluzinationen.** Tests 1332→**1338** (+6).
⛔ Revert nach 10.06.2026 — Code hat Datums-Kommentare.

**Plan-Files:** prompts/bundle_l_display3_bypass_v[1,2,3].md + _r1.md
+ _final_r1.md.

Push pending bis Mike App-Start visuell bestätigt.

---

---

## ✅ 15.05.2026 erledigt — P63 SWR-Block per Band-Marker + Tuner-Settings + Lock-Release v0.97.36

**Trigger:** Mike-Field-Test 15.05. nachmittags 17m-Band — SWR-Watchdog
feuerte, danach 3 Bugs gleichzeitig sichtbar (Lock hing → TUNE gesperrt,
OMNI/Hunt klickbar trotz SWR-Sperre, inkonsistent). Mike-Spec: Band-Marker
pro Band in-memory, blockiert Auto-Pfade, manueller TUNE bleibt klickbar.

**Voller V1→V2→R1→V3→Code→Final-R1-Workflow** mit DeepSeek-V4-pro.

**V2-Findings:** 12 (F1 Halluzination `control_panel.last_swr()` → `radio.last_swr`).
**R1-Findings:** 6 (3 kritisch: F-R1-1 Post-Tune-SWR-Race-Condition,
F-R1-2 Auto-TUNE-Fehler ohne Lock-Release, F-R1-5 Pending-Click-Schutz).
**Final-R1 V4-pro:** „Push freigegeben." 0 KP, 0 Findings.

**V4-pro 12-Cycle-Bilanz:** 0 Halluzinationen, 100% verifizierbar.

**Code:**
- `config/settings.py` DEFAULTS: `tuner_present=True`, `tune_duration_s=15`
- `ui/settings_dialog.py` Tab „FT8 & Diversity" Checkbox + ComboBox + Load + Save + Reset
- `ui/main_window.py` Init `_swr_blocked_bands`/`_tune_in_progress` + Token-Pattern + 2 Toggle-Pre-Checks (OMNI + Auto-Hunt)
- `ui/mw_tx.py:_on_swr_alarm` Lock-Release + Marker-Set + Watchdog-Bypass
- `ui/mw_tx.py:_on_tune_clicked` + `_tune_stop` + `_tune_post_swr_check` 10W FEST, Dauer 15/30s, 2s-Beruhigungszeit
- `ui/mw_radio.py:_check_diversity_preset` + `_start_dx_tuning` Marker-Pre-Check + ANT1 + Tuner=False-Skip + Auto-TUNE-Fehler-Lock-Release
- `ui/mw_qso.py:_on_station_clicked` Pre-Check FIRST + `_on_tx_finished` Pending-Click-Schutz + `_on_cq_clicked` Pre-Check
- `ui/control_panel.py:set_tuner_present` + Init-Flag
- `main.py` APP_VERSION 0.97.36

**11 atomare Commits.** Tests **1306 → 1327** (+21: 18 V3-AC-Tests + 3 Bonus
Source-Level + 0 P53-Mock-Anpassungen + 1 OMNI-Mock-Fix).

**Backup:** `Appsicherungen/2026-05-15_v0.97.35_vor_p63/`.

**Field-Test F1-F10 pending** (siehe TESTPLAN_15.05.2026_p63.md). Push pending.

---

## ✅ 15.05.2026 erledigt — Display-3-Move für Remote-Starter (Mike-Wunsch 15.05.-10.06.2026)

Memory `project_simpleft8_ferienhaus.md` aktualisiert: Display 2 → Display 3
(Position (1024,0) → (2944,0)). osascript-Block im Memory zeigt jetzt
Display 3 als Ziel. Bei erster Verwendung Mike prüfen lassen ob Position
stimmt (Quartz-Check im Memory falls falsch).

P63-Plan-Details (Spec, AC1-AC13, 15 Tests, 10 Field-Tests, LDG-Recherche)
→ `prompts/p63_swr_block_marker_v[1,2,3].md` + `_r1.md` + `_final_r1.md`.

---

## ✅ 15.05.2026 erledigt — P62 Bandwechsel→Gain-Messung UX-Pause (1s) v0.97.35

**Trigger:** Mike-Field-Test P60-F6 vormittags. DeepSeek-V4-pro hat P62
für autonomen 30-Min-Slot ausgewählt.

**Fix:** 1s `QTimer.singleShot` vor `_start_dx_tuning` in
`_check_diversity_preset` stale/missing-Branch. Lock SOFORT + Statusbar.
KALIBRIEREN-Button ohne Pause. Race-Schutz via `_gain_measure_locked`.

**R1-V4-pro:** „Push freigegeben (V3-Phase OK)" 0 KP.
**Final-R1 V4-pro:** „Push freigegeben." 0 KP.
**V4-pro 11-Cycle-Bilanz:** 0 Halluzinationen.

**5 atomare Commits.** Tests 1300 → **1306 grün** (+6 P62).
**Backup:** `Appsicherungen/2026-05-15_v0.97.34_vor_p62/`.
**Field-Test F1-F5 pending** (HANDOFF).

---

## ✅ 15.05.2026 erledigt — P55 Easter-Egg + Diversity-CQ-Code-Leichen entfernt v0.97.30

**Trigger:** Mike-Spec 15.05.: in Diversity nur OMNI CQ (kein Normal-CQ
auch nicht versteckt), Easter-Egg-Funktion komplett raus.

**Voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro.**

**Code-Removal:**
- `_on_easter_egg_toggle`-Methode + `_easter_egg_active`-Variable raus
  (`main_window.py`)
- `easter_egg_toggle_clicked`-Signal + `_omni_active`-Flag +
  Version-Label-Click-Handler raus (`control_panel.py`)
- `btn_cq` OMNI-Label-Branches raus — jetzt reiner Normal-CQ-Button
- 5× `_easter_egg_active`-Verweise + `hasattr`-Gates in `mw_radio.py`
- `core/auto_hunt.py` Doc-String-Verweise auf `easter_egg_off` (R1-F1)
- 8 irreführende Doku-Kommentare in 4 Files aktualisiert
- 6 Source-Level-Regressions-Tests T1-T6 NEU

**R1-V4-pro:** 5 Findings, 4 angenommen + 1 Doku-Akzeptanz,
Halluzinations-Rate 0/5. F1 sehr stark (`core/auto_hunt.py` in V2
vergessen). Final-R1 „PUSH uneingeschränkt freigeben" 0 KP.

**V4-pro 5-Cycle-Bilanz:** 30 Findings total, 0 Halluzinationen.

**8 atomare Commits** (C1-C7+C7b). **Tests 1258 → 1262** (+4: -2
parametrize, +6 P55-Regression).

**Backup:** `Appsicherungen/2026-05-15_v0.97.29_vor_p55/`.

**Field-Test F1-F8 pending** (siehe HANDOFF).

---

## ✅ 14.05.2026 erledigt — P53 SWR-Live-Watchdog (Hardware-Sicherheit) v0.97.29

**Trigger:** Mike-Field-Test 14.05.: nasse Antenne nach Regen → SWR>30 bei
70W, `swr_limit` greift nicht im normalen TX-Pfad. FlexRadio-Hardware-
Schutz + Tuner haben gerettet.

**Voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro.**

**Wurzel-Bugs:** (1) SWR-Check nur vor Gain-Messung (`mw_radio.py:1336`).
(2) `swr_alarm`-Signal feuerte aber Handler `mw_tx.py:99-105` zeigte nur
Statusbar — stoppte nichts. (3) `Settings.swr_limit` nirgends an
FlexRadio propagiert — `_swr_limit=3.0` hardcoded.

**Architektur:** Statt neuem QTimer-200ms-Polling reagiert Watchdog auf
**bestehendes `swr_alarm`-Signal** (VITA-49-Meter-Loop) — KISS.

**Code:**
- `radio/base_radio.py`: `set_swr_limit(value)` Default-Pass-Stub.
- `radio/flexradio.py`: Setter mit Clamp `[1.5, 10.0]`.
- `ui/main_window.py`: `_swr_spike_count=0` + `_swr_first_alarm_t=0.0`
  explizit init (R1-F2).
- `ui/mw_radio.py`: nach `swr_alarm.connect()` ruft
  `radio.set_swr_limit(settings.swr_limit)`.
- `ui/mw_tx.py:_on_swr_alarm` Komplett-Rewrite:
  - Pre-Check `encoder.is_transmitting` (R1-AC3, gegen Pre-TX-Alarm)
  - Spike: 2 Alarms innerhalb 500ms via `time.monotonic`
  - Reset spike_count=0 SOFORT vor Stop-Calls
  - Stop-Block antennen-neutral (encoder.abort + ptt_off + stop_cq +
    cancel + set_cq_active + omni.stop + hunt.stop)
  - `qso_panel.add_info` VOR Modal (Modal blockt sonst Event-Loop)
  - `QMessageBox.warning` modal, kein Auto-Resume
- `ui/settings_dialog.py`: Save-Hook propagiert live wenn `radio.ip`.

**Field-Test F1-F7 pending:**
- F1: Settings → SWR-Limit 2.5 → Konsole zeigt FlexRadio-Set
- F2: App-Neustart → Set direkt nach Connect
- F3: TX mit guter Antenne → kein Falsch-Alarm
- F4: Antenne ab + CQ → Pre-PTT-Block, kein Modal
- F5: Tuner verstellt während TX → ~500ms Modal + Panel-Eintrag
- F6: OMNI + Block → OMNI stoppt sauber
- F7: Nach Modal: kein Auto-Resume

**R1-V4-pro:** 4 Findings (2 Bug, 2 Risiko), 4/4 angenommen,
**Halluzinations-Rate 0/4**. Final-R1 „PUSH empfohlen", 0 KP.

**V4-pro 4-Cycle-Bilanz:** 25 Findings total, 0 Halluzinationen, 100%
verifizierbar.

**7 atomare Commits:** C1 (`8270e2b`) C2 (`0d898e1`) C3 (`287ae25`)
C4 (`29133c3`) C5 (`b38de1d`) C6 (`835b7f0`) C7 (`38ea473`).

**Tests 1245 → 1258 (+13).** T5 ist Hardware-Pflicht-Test (set_tx_antenna
NIE im Stop-Pfad). T3 ist Pre-TX-Alarm-Schutz. T13 ist
AttributeError-Schutz für Spike-State.

**Backup:** `Appsicherungen/2026-05-14_v0.97.28_vor_p53/`.

---

## ✅ 14.05.2026 erledigt — P51 Gain-Messung vereinheitlichen (1 Messung, 2 Auswertungen) v0.97.28

Mike-Beobachtung 14.05.: 20m FT8 hat Std-Werte 10/10 und DX-Werte 20/10
weil zu unterschiedlichen Zeitpunkten gemessen. V1→V2→R1→V3-Workflow
mit DeepSeek-V4-pro voll-autonom.

**Code:** `DXTuneDialog._finish` rechnet jetzt **beide** Auswertungen
aus identischen `_phase_data`. Helper `_best_for(ant, use_snr)` extrahiert
scoring-Logik. `_results` hat Sub-Keys `"standard"` + `"dx"` mit je 6
Feldern + Top-Level-Spiegel (Backwards-Compat). Display zeigt
`←(Std)`/`←(DX)`/`←(Std+DX)`-Marker. `_on_dx_tune_accepted` schreibt
beide Stores parallel mit Fallback auf Single-Store wenn Dialog ohne
Dual-Result (verhindert Daten-Korruption R1-F4). `settings.save_dx_preset`
komplett raus (R1-F6: tote API, `get_dx_preset` wird nirgends im
Live-Code gerufen). APP_VERSION 0.97.27→0.97.28.

**R1-V4-pro:** 9 Findings (1 Bug rot Code-Realität-Check, 4 Risiko,
2 Verbesserung, 2 Hinweis). 6 angenommen, 3 abgelehnt mit Begründung.
Bug F1 fand 8 vs 18 Zyklen Code-Realität — P51 spart trotzdem 50% (16→8).
Risiko F4 kritisch: Fallback-Korruption DX-Store mit Std-Werten →
`has_dual`-Check verhindert das.

**Final-R1 V4-pro „Push freigegeben." 0 KP**, 3 INFO (Kommentar-Drift
auf 8 Schritte gefixt).

**Tests:** 1235 → 1245 (+10). T5 ist kritischer Anti-Korruption-Test
(Fallback bei has_dual=False schreibt NICHT in DX-Store).

**Praktischer Effekt:** Heute 2 Mess-Sessions à 8 Zyklen = 16 Zyklen für
beide Modi. Künftig 1 × 8 Zyklen, beide Stores aus derselben Mess-
Situation, instant Mode-Switch im 6h-Fenster.

Push pending bis Field-Test F1-F7.

---

## ✅ 14.05.2026 erledigt — Bundle J (Connect-Modal-Branding + SimpleHelpDialog + RX-Label + Intent-Klausel) v0.97.27

Vier orthogonale UI/Doku-Tweaks aus Mike-Klärungsgespräch nach Bundle I —
voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro. Final-R1 V4-pro
„Push freigegeben." 0 KP.

**Punkt 1:** Connect-Modal Footer unten rechts „SimpleFT8 v0.97.27 · MIT
License" via Konstruktor-Parameter `app_version` (Lazy-Import in `mw_radio`,
kein Circular). setFixedSize 352×176 → 352×196.

**Punkt 2:** Einheitlicher `SimpleHelpDialog` mit 700×600 resizable +
QTextBrowser + Scrollbar + WindowModal + komplettes Stylesheet (R1-F3).
Helper `show_simple_help(parent, title, text, *, markdown=False)`.
`_make_info_btn` + `_show_bandpilot_help` umgestellt. Mike-Designentscheidung
„Konsistenz > Optimum-pro-Dialog" — R1-F2 Overengineering-Vorwurf
abgelehnt mit Begründung.

**Punkt 3:** `_antenna_pref_label` ANT2-Zweige mit `RX:`-Prefix —
`(RX: ANT2 ↑X.X dB)` bzw. `(RX: ANT2)` (R1-F5 delta<0.05). ANT1 bleibt
überall ohne Prefix (Symmetrie zu Normal-Modus).

**Punkt 4:** Intent-Klausel im Hardware-Disclaimer — „dient ausschließlich
dem persönlichen Gebrauch und der Verifikation technischer Möglichkeiten."
+ Höhe 540×300 → 540×340.

**Tests:** 1220 → 1235 (+15). Memory-Update folgt nach Field-Test.
Push pending bis F1-F7.

**Punkt 3 (Pre-TX ANT1-Guard) abgehakt:** Code-Verifikation 14.05.:
`core/encoder.py:389` + `ui/mw_tx.py:83` rufen `set_tx_antenna("ANT1")`
VOR jedem `ptt_on()` / `tune_on()` — bereits safe, keine Code-Änderung.

---

## ✅ 14.05.2026 erledigt — Bundle I (Settings-Spacing + QSO-Reihenfolge + OMNI-Race) v0.97.26

Drei orthogonale Befunde aus Mike-Field-Test 14.05.2026 nachmittags
zusammen einspielen — voller V1→V2→R1→V3-Workflow mit DeepSeek-V4-pro
(Erstnutzung), Final-R1 „Push freigegeben" 0 Findings.

**Punkt 1:** Settings „Sichtbare Bänder" Spacing 10→16, Margins
(12,8,12,10)→(16,16,16,16), Stylesheet `QCheckBox::indicator 18×18` lokal
auf `bands_group` (Scope-Begrenzung).

**Punkt 2:** `qso_confirmed_visual.emit` von `on_message_received`
WAIT_73-Branch (Z.692) in `on_message_sent` TX_73_COURTESY-Branch (Z.538)
verschoben — Reihenfolge im QSO-Panel: Empf. 73 → Sende 73 → ✓ QSO komplett.

**Punkt 4 (OMNI-Race):** Stop-Block in `_on_rx_mode_changed`
(`ui/mw_radio.py:541-560`) erweitert analog Bandwechsel-Pattern:
`stop_cq + cancel + set_cq_active(False) + encoder.abort + ptt_off`.
R1-V4-pro Finding 1: `qso_sm.stop_cq()` allein reicht nicht.

**Tests:** 1205 → 1220 (+15). Memory `project_bundle_i_settings_qso_omni.md`.
Push pending bis Field-Test F1-F7.

---

## 📋 ARCHIVIERT (Plan-Detail) — Bundle J Spec: Connect-Modal-Branding + Help-Dialog + Pre-TX-Guard + RX-Label

> **Status: ERLEDIGT 14.05.2026 spätnachmittags (v0.97.27) — siehe oben.**
> Plan-Detail bleibt zur Doku stehen.

**Trigger:** Mike-Field-Test 14.05.2026 nachmittags + Klärungs-Gespräch.
**Aufwand-Schätzung:** klein, ~1 Tag inkl. Tests + Workflow.
**Komplettes Bundle:** 4 UI-/Sicherheits-Tweaks die einzeln zu klein
für eigenen Workflow sind aber zusammen gut gebündelt werden können.

### J-Punkt 1 — Connect-Modal Version + MIT-Lizenz unten rechts

**Wo:** P26-Connect-Modal (Antennen-Animations-Dialog beim App-Start
während FlexRadio-Verbindung).

**Was rein:**
- Versionsnummer + MIT-Lizenz unten rechts in der Ecke
- Format: `v{APP_VERSION} · MIT License` (synchron mit `main.py:APP_VERSION`, kein Hardcode)
- Schrift klein (z.B. 9-10pt), halb-transparent, dezent
- `setAlignment(Qt.AlignBottom | Qt.AlignRight)` auf einem Label

**Sichtbarkeitszeit:** 5-7 Sek während Connect-Phase → genug Zeit dass User es lesen kann.

**Zusätzlich:** `LICENSE`-Datei mit MIT-Text im Repo-Root anlegen falls noch nicht vorhanden.

### J-Punkt 2 — Einheitlicher Help-Dialog mit Scrollbar

**Trigger-Problem:** Aktuell sind alle `?`-Buttons im Settings-Dialog mit
`QMessageBox` realisiert (siehe `ui/settings_dialog.py:_show_bandpilot_help`
+ andere). `QMessageBox` ist **nicht resizable**, Größe richtet sich nach
Text-Länge → bei langem Markdown (Bandpilot-Hilfe!) wird's schmal +
hoch → unten abgeschnitten + KEINE Scrollbar möglich. Mike-Screenshot
14.05. zeigt Bandpilot-Hilfe nicht lesbar.

**Lösung:** Eigener Help-Dialog `ui/help_dialog.py`:
- `QDialog` mit `QTextBrowser` (Markdown-fähig + automatischer Scrollbalken)
- Modal (`setWindowModality(Qt.ApplicationModal)`)
- Feste Mindest-Größe **700×600 px**, resizable nach oben
- Hintergrund-Farbe **synchron mit App-Theme** (dunkel — nicht weiß abgesetzt wie bei QMessageBox)
- Schließen: Esc + Close-Button
- Helper-Funktion `show_help(parent, title, markdown_text)` — überall reinrufbar

**Wo umstellen:** Alle `?`-Buttons in `ui/settings_dialog.py` (Rufzeichen,
Sendeleistung, Tune-Leistung, SWR-Limit, Anrufversuche, Bandpilot, etc.) +
ggf. weitere `_show_*_help`-Methoden. Einheitlich für KURZE und LANGE Texte.

**Wichtig:** Konsistenz > Optimum-pro-Dialog — auch kurze Erklärungen
landen im 700×600-Fenster mit Weißraum. Das ist OK, schadet nichts.

### J-Punkt 3 — Pre-TX ANT1-Guard (Hardware-Sicherheit)

**Trigger-Befund:** Code-Verifikation 14.05. zeigte: `set_tx_antenna("ANT1")`
wird **nur an 3 Stellen** im Code aufgerufen (`mw_radio.py:1486, 1618, 1703`)
— bei RX-Mode-Wechsel + Preset-Laden. **NICHT vor jedem TX-Slot.**

**Problem:** Wenn User mid-session am SmartSDR/Radio die TX-Antenne
manuell auf ANT2 schaltet → App weiß davon nichts → nächster TX-Slot
sendet über ANT2 (Regenrinne) → **Hardware-Risiko**.

**Mike-Frage 14.05. nachmittags zu diesem Szenario.**

**Lösung Variante A (Mike's Wahl, KISS):**
Vor jedem `encoder.start_tx(...)` (oder direkt vor `send_message.emit`)
zwingend `radio.set_tx_antenna("ANT1")` setzen. Defensiv, idempotent,
kostet pro TX-Slot ~1 SmartSDR-Command (~ms).

**Wo einbauen:** Vermutlich `ui/mw_qso.py` direkt vor jedem
`encoder.start_tx`-Aufruf — Pfade prüfen, Helper-Methode wenn mehrere
Stellen.

**NICHT umgesetzt (Variante B, abgelehnt):** Polling-Watchdog der die
Antenne live überwacht und auto-zurücksetzt. Für Mike als Single-User
overkill, Variante A reicht.

### J-Punkt 4 — RX-Antennen-Label Klarheit

**Trigger-Befund Screenshot 14.05.:**
```
HALT - alles gestoppt
Rufe Y060GW... (ANT2 +1.0 dB)
```

Das Label `(ANT2 +1.0 dB)` liest sich wie „TX über ANT2", ist aber
tatsächlich die **bessere RX-Antenne** für diese Station (Antenna-
Preference aus `core/antenna_pref.py`). Gefährlich nahe an Hardware-
Verstoß-Wahrnehmung.

**Fix:** Label-Prefix `RX:` ergänzen — Mike's Wahl Variante A.

**Wo:** `ui/mw_qso.py:_antenna_pref_label()` (gibt heute `"(ANT2, +1.0 dB)"`).
Auch alle RX-Panel-Zeilen wo `(ANT2 ↑1.0 dB)` steht → konsistent
`RX:` davor.

**Neue Notation:**
- Diversity-Modus: `(RX: ANT2, +1.0 dB)`
- Normal-Modus: **unverändert** `(ANT1)` (kein RX-Prefix nötig weil
  nur eine Antenne existiert — Mike-Klärung: „egal weil immer ANT1")

**Nebeneffekt:** Demonstrations-Wirkung deutlich besser — andere Funker
sehen sofort „boah, der empfängt mit Regenrinne als zweite Antenne".

### Tests + Workflow

- Volle Workflow-Pflicht (V1→V2→R1→V3 mit DeepSeek-V4-pro).
- Tests: pro Punkt 2-4 neue Tests (Bundle-J-Suite).
- Backup `Appsicherungen/2026-05-15_v0.97.26_vor_bundle_j/` (oder
  passende Datierung) vor Code-Start.
- Field-Test F1-F4 für jeden Punkt einzeln.

---

## ✅ 15.05.2026 erledigt — P62 Bandwechsel→Gain-Messung UX-Pause (1s) v0.97.35

**Trigger:** Mike-Field-Test P60-F6 vormittags: Bandwechsel auf neues
Band ohne Preset → Gain-Mess-TUNE startet direkt nach TX-Stop → visuell
„80W → 10W" statt „TX aus → neue Messung". Mike: „besprich das mit
deepseek".

**DeepSeek-V4-pro Auswahl:** P62 für autonomen 30-Min-Slot (niedriges
Risiko, klare Spec).

**Voller V1→V2→R1→V3-Workflow autonom mit DeepSeek-V4-pro.**

**Fix:** `_check_diversity_preset` stale/missing-Branch:
1. `_set_gain_measure_lock(True)` SOFORT (sperrt UI)
2. Statusbar „TX gestoppt — Gain-Messung startet in 1s ..."
3. `QTimer.singleShot(1000, lambda: _start_dx_tuning(...))`

**Greift NUR bei Bandwechsel**, NICHT bei KALIBRIEREN-Button.

**R1-V4-pro:** „Push freigegeben (V3-Phase OK)" — 0 KP.
**Final-R1 V4-pro:** „Push freigegeben." 0 KP.
**V4-pro 11-Cycle-Bilanz:** 0 Halluzinationen.

**5 atomare Commits:**
- C1 ui/mw_radio.py (Lock+Statusbar+QTimer)
- C2 main.py APP_VERSION 0.97.35
- C3 tests/test_p62_bandchange_ux.py NEU 6 Tests T1-T6
- C4 tests/test_p1_cache_simple.py 2 alte Tests angepasst (QTimer-Mock)
- C5 Doku

**Tests:** 1300 → **1306 grün** (+6 P62).

**Backup:** `Appsicherungen/2026-05-15_v0.97.34_vor_p62/`.

**Field-Test F1-F5 pending** (HANDOFF).

---

## 🗄️ HISTORIE — P62: Bandwechsel→Gain-Messung UX-Übergang (ERLEDIGT v0.97.35)

**Trigger:** Mike-Field-Test P60-F6 15.05. vormittags: Bandwechsel 30m→20m
während Auto-Hunt-TX. Code bricht TX korrekt ab (`mw_radio._on_band_changed`
ruft `encoder.abort() + ptt_off()`), aber direkt danach startet Gain-
Messung mit TUNE = 10W. **Aus Funker-Sicht sieht das aus wie „80W → 10W"
statt sauberes „TX aus → neue Messung".**

Mike: „eigendlich wäre pause sinnvoll? keine ahnung 1 sekunde bis tx auf
null ist anstatt von 80 auf 10 watt zu gehen? keine ahnung besprich das
mit deepseek."

**Mike-Vorschlag:** 1 Sekunde Pause zwischen TX-Stop und Gain-Mess-TUNE,
damit visuell klar wird dass alter TX aus ist.

**Code-Verifikation:** `ui/mw_radio.py:416-419` — `encoder.abort()` +
`radio.ptt_off()` werden gerufen. Anschließend ruft `_enable_diversity()`
die Gain-Mess-Pipeline an (TUNE 10W) sobald Mess-Bedingungen erfüllt
(neues Band ohne Preset).

**Aus Scope:** Bandwechsel-Stop-Logik selbst (funktioniert sauber).

**Vorgehen:** Voller V1→V2→R1-V4-pro-Workflow.
- V1: Optionen Pause-Zeit (1s/2s) oder visueller Indikator (Status-Toast
  „TX gestoppt → Gain-Messung startet")
- V2-Self-Review: Risiken (TX-Buffer-Latenz FlexRadio 1.3s, ist 1s
  vielleicht zu kurz?)
- R1-V4-pro: pro/contra Pause-Zeit, Alternative UX-Patterns, KISS-
  Bewertung
- V3 → Code → Final-R1

**Priorität:** Niedrig (Field-Test nicht blockiert, Bandwechsel
funktioniert sauber). Nach P61+P59 angehen.

---

## 🆕 OFFEN — P56: Gain-Messung kollabieren auf pro-Band (Mike 15.05.2026 morgens, DeepSeek-V4-pro bestätigt Option A)

**Trigger:** Mike-Beobachtung 15.05.: Wenn auf FT4/FT2 die Gain-Messung
fällig wird (6h-Frist abgelaufen) und nicht genug Stationen empfangbar
sind → Mess-Hänger. Aber Gain ist Hardware-Eigenschaft pro Antenne und
identisch für FT8/FT4/FT2 auf demselben Band → unnötige Mode-Trennung.

**DeepSeek-V4-pro-Empfehlung (Brainstorm 15.05.):** Option A „Nur FT8
misst" klar gegen Option B „Auto-Switch zu FT8". KISS-Weg. „Gain-Messung
ist ein Setup-Schritt, der typischerweise beim ersten Start auf einem
Band in FT8 erledigt wird — danach ist der Wert da und alle Modi
profitieren." Option B = Kanonen auf Spatzen wegen QSO-Race + Encoder-
State-Restore.

**Mike-Spec (Klärung 15.05.):** „6 Stunden gelten ab heute nur Grenze
wenn FT8-Betrieb ist, wenn FT4 und FT2 keine Relevanz, so haben wir
einen Bandwert für alle 3 Modis."

**Präzedenz:** P48-B (v0.97.13) — Cross-Modus-Fallback existiert bereits
für DT-Korrektur (`FT4/FT2 → FT8` vom gleichen Band).

### Was tun

1. **PresetStore-Key vereinheitlichen** auf nur Band: `40m` statt
   `40m_FT8`/`40m_FT4`/`40m_FT2`. Ein Datensatz pro Band für alle 3 Modi.
2. **Mess-Trigger nur in FT8**:
   - Aktiver Modus FT8 + Wert für Band fehlt/älter 6h → Mess-Dialog.
   - Aktiver Modus FT4/FT2: **immer den existierenden Wert nehmen**,
     auch wenn 9h/24h/7 Tage alt. **Keine 6h-Frist in FT4/FT2.**
3. **Erstnutzung auf FT4/FT2 ohne FT8-Wert:** passiver Hinweis (Statusbar
   oder QSO-Panel.add_info: „Bitte einmal auf FT8 wechseln zum Messen —
   Werte gelten dann für alle FT-Modi auf diesem Band"). **Kein
   Auto-Mode-Switch** (Mike: „bin ich nicht für").
4. **Migration alter Datei:** alte `40m_FT8`-Einträge werden zu `40m`
   umbenannt (FT8 als Quelle weil meiste Daten). FT4/FT2-Einträge werden
   verworfen.
5. **Mess-Texte modus-neutral:** schon heute weitgehend OK (geprüft —
   `dx_tune_dialog.py` und `mw_radio.py` haben keine FT8/FT4/FT2-
   namentlichen Strings in Mess-Phase).

### Wo umsetzen

- `core/preset_store.py`: Key-Format von `band_mode` auf nur `band`.
  Migration in `load()` analog DT-Korrektur. `get_gain(band)` ohne
  mode-Parameter.
- `ui/mw_radio.py:_check_diversity_preset`: Mess-Trigger prüft
  `settings.mode == "FT8"`. Sonst silent existierenden Wert nehmen +
  Hinweis falls leer.
- `ui/dx_tune_dialog.py`: Save unter `band`-Key statt `band_mode`.
- Status-Indikator: einmaliger Hinweis „Bitte auf FT8 wechseln" wenn
  Diversity-Aktivierung in FT4/FT2 ohne FT8-Wert.
- Tests: 5-6 Tests (Migration, Mode-Trigger-Gate, FT4-mit-altem-FT8-
  Wert, FT4-ohne-FT8-Wert-Hinweis, idempotenter Save).

**Aufwand:** klein-mittel, 0.5-1 Tag. Workflow Pflicht (PresetStore-API-
Eingriff + Migration).

---

## ✅ 15.05.2026 erledigt — P60: User-Stop-Pfade Slot-Abbruch + Click-Puffer v0.97.32

3 User-Toggle-Stop-Pfade (OMNI/Auto-Hunt/Normal-CQ) brachen TX-Slot
nicht sofort ab — Helper `_abort_active_tx` in mw_tx.py NEU + HALT-
Refactor. R1-V4-pro-F1 ROT Klassiker-Catch: `_pending_station_click`
auch leeren. SWR-Watchdog F3-1-Zeiler Konsistenz. 6 Commits. Tests
1268→1279 (+11). Field-Test F1-F6 pending. Siehe HISTORY.md v0.97.32.

---

## 🗄️ HISTORIE — P60 (Mike-Field-Test 15.05.2026 morgens, ERLEDIGT v0.97.32)

## ✅ 15.05.2026 erledigt — P61 Auto-Hunt Recent-QSO-Cooldown v0.97.33

**Trigger:** Mike-Field-Test 15.05. morgens (Screenshot): Auto-Hunt
picked HA8RC 30s nach abgeschlossenem QSO → 89s verschwendetes 2. QSO
→ Funkverkehr-Etikette-Verletzung.

**Wurzel:** existierende `qso_log.is_worked_on_band`-Filterung versagte
(Race Decoder/Encoder oder ADIF-Exception denkbar, nicht reproduzierbar).

**Fix:** Belt-and-Suspenders Cooldown-Schicht direkt in `AutoHunt`:
- Konstante `_RECENT_QSO_COOLDOWN_S=300` (5 Min)
- Feld `_mode: str = "FT8"` + Methode `set_mode()`
- Dict `_recent_qso: dict[(call,band,mode), float]`
- Methode `mark_pick(call)` — setzt Cooldown SOFORT bei Pick
- Filter in `select_next` VOR `_cooldown`-Check + Lazy-Cleanup
- `on_qso_complete` ruft `mark_pick` (redundant für manuelle QSOs)
- `mw_cycle._run_auto_hunt` ruft `mark_pick` NACH `select_next` BEVOR
  `start_qso` (primärer Race-Schutz)
- `mw_radio._on_mode_changed` + `main_window.__init__` → set_mode
  verkabelt

**R1-V4-pro:** 7 Findings, 5 angenommen + 2 begründet abgelehnt
(F3 KISS-Vorschlag getrennt klarer, F7 ADIF-try/except gegen Mike-Spec).
Halluzinations-Rate 0/7.

**Final-R1 V4-pro:** „Push freigegeben." 0 KP.

**5 atomare Commits:**
- C1 core/auto_hunt.py (Konstante + Feld + Methoden + Filter)
- C2 ui/mw_cycle.py (mark_pick vor start_qso)
- C3 ui/mw_radio.py + ui/main_window.py (Mode-Verkabelung)
- C4 tests/test_p61_autohunt_recent_qso.py NEU 10 Tests T1-T10
- C5 main.py APP_VERSION + Backup + Doku

**Tests:** 1279 → **1289 grün** (+10 P61).

**Backup:** `Appsicherungen/2026-05-15_v0.97.32_vor_p61/`.

**Field-Test F1-F7 pending** (HANDOFF).

---

## 🗄️ HISTORIE — P61: Auto-Hunt nimmt gerade abgeschlossene Station SOFORT WIEDER (ERLEDIGT v0.97.33)

**Trigger:** Mike-Field-Test mit Auto-Hunt 15.05. zeigte: nach
erfolgreichem QSO + Courtesy-73 wird DIESELBE Station sofort wieder
angerufen — doppeltes QSO mit identischem Call! ADIF-Duplikat-Schutz
greift („9A2G Duplikat (89s) — kein ADIF-Eintrag"), aber TX läuft
komplett raus (2 Min Funkzeit verschwendet pro Dup, Etikette-
Verletzung, Antennen-Verschleiß).

**Beweis aus Screenshot 04:55-05:00 UTC:**
```
04:56:30 Sende 9A2G 73 ✓ komplett        (QSO #1)
04:57:00 Sende 9A2G -17                   ← Auto-Hunt picks 9A2G WIEDER
04:58:00 Sende 9A2G 73 ✓ komplett        (QSO #2 mit selber Station)
04:58:30 Sende HA8RC -14                  (HA8RC #1)
04:59:30 Sende HA8RC 73 ✓ komplett
05:00:00 Sende HA8RC -16                  ← HA8RC WIEDER
05:00:30 HA8RC Duplikat (89s) — kein ADIF
```

**Wurzel-Vermutung:** `core/auto_hunt.py` `select_next()` filtert die
gerade abgeschlossene Station nicht aus der Kandidaten-Liste — sie
ruft im nächsten Slot weiter CQ und wird wieder als „rufst-mich"-
Match gewertet, bevor `_active_qso_targets` clearen oder Cooldown
greift.

**Was tun:**
1. `core/auto_hunt.py` Kandidaten-Liste: kürzlich abgeschlossene Calls
   (z.B. letzte 5 Min via `qso_log` oder eigener Recent-Set) ausschließen
2. Plus: Pre-TX-Check vor `encoder.transmit` — wenn Ziel-Call im
   ADIF-Cache der letzten X Min → TX abbrechen (Cooldown-Belt-Suspenders)
3. Mike entscheiden: Cooldown-Dauer (Vorschlag: 5-10 Min, FT8-Etikette
   sagt „kein 2. QSO im selben Slot")
4. Tests: T1 Auto-Hunt skipt gerade abgeschlossene Station, T2 ADIF-
   Recent-Cooldown, T3 Bug-Schutz mit Screenshot-Sequenz nachgebaut

**Aufwand:** mittel, ~1-2h Code + Mike-Klärung Cooldown-Dauer.
**Workflow Pflicht.** Wurzel-Analyse vor V1 (`core/auto_hunt.py` +
`core/qso_state.py` Pfad genau verstehen).

**Hinweis Hardware:** ANT1-TX bleibt unverändert (Stop-Pfad), nur
Pre-TX-Filter eingreifen.

---

## 🆕 OFFEN — P60: Alle 3 User-Stop-Pfade brechen laufenden TX-Slot nicht ab (Mike-Field-Test 15.05.2026 morgens)

**Trigger:** Mike-Test P55-F6: OMNI-CQ während aktivem TX-Slot per
Toggle-Klick gestoppt — Button wird sofort rot, ABER der laufende
15s-Slot wird komplett zu Ende gesendet. Mike: „Toggle = an/aus,
nicht slot-schalter. Ich würde ja nicht im CQ-Ruf drücken wenn ich
nicht wollte das es nicht mehr sendet."

**Mike-Folge-Wunsch:** „bitte auch bei normal cq ruf überprüfen" —
Code-Audit bestätigt: **alle 3 User-Toggle-Stop-Pfade** haben denselben
Bug.

**Wurzel — 3 Stellen ohne `encoder.abort()` + `ptt_off()`:**

1. **OMNI-CQ:** `ui/main_window.py:791-792` `_on_btn_omni_cq_toggled`
   ```python
   elif not checked and self._omni_cq.is_active():
       self._omni_cq.stop("manual_halt")  # ← nur Flags, kein TX-Stop
   ```

2. **Auto-Hunt:** `ui/main_window.py:862-863` `_on_btn_auto_hunt_toggled`
   ```python
   elif not checked and self._auto_hunt.active:
       self._auto_hunt.stop_auto_hunt("manual_halt")  # ← nur Flags
   ```

3. **Normal-CQ:** `ui/mw_qso.py:311-317` `_on_cq_clicked` Stop-Pfad
   ```python
   else:
       count = self.qso_sm.cq_qso_count
       self.qso_panel.add_info(f"CQ-Modus gestoppt ({count} QSOs)")
       ...
       self.qso_sm.stop_cq()  # ← nur State-Wechsel, kein TX-Stop
       self.control_panel.update_qso_counter(0)
   ```

Im Vergleich `_on_cancel` (HALT-Button) macht es richtig:
```python
if self.encoder.is_transmitting:
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
```

**Was tun:** Alle 3 Stop-Pfade um abort+ptt_off ergänzen — guarded mit
`if self.encoder.is_transmitting:` damit nur dann eingreifen wenn TX
wirklich läuft (sonst no-op).

**Zentralisierung empfohlen:** Helper-Methode `_abort_active_tx()` in
einem Mixin (mw_tx.py?) — single source of truth gegen Drift in Zukunft.

**Tests:**
- T1: OMNI-Stop ruft abort+ptt_off wenn encoder.is_transmitting
- T2: Auto-Hunt-Stop analog
- T3: Normal-CQ-Stop analog
- T4: Wenn encoder.is_transmitting=False → kein unnötiger abort-Call
- T5: SWR-Watchdog-Stop bleibt unverändert (Regression-Schutz)
- T6: HALT-Pfad bleibt unverändert

**Aufwand:** klein-mittel, ~45 Min Code + Workflow Pflicht (TX-Pfad-
Eingriff über 3 Stellen, Audit nötig).

---

## ✅ 15.05.2026 erledigt — Bundle K (P57 SWR-Combo + P59 CQ-Button-Grün) v0.97.34

**Trigger:** Mike-Field-Test 15.05. morgens, 2 UI-Tweaks als gemeinsames
Bundle:
- P57: SWR-Limit nur 0.5-Schritte (verhindert 1.7-Eingabe per Tastatur)
- P59: CQ-Button (+ Auto-Hunt) aktiv = grün analog OMNI (Konsistenz)

**Voller V1→V2→R1-V3-Workflow autonom mit DeepSeek-V4-pro.**

**R1-V4-pro:** „Push freigegeben (V3-Phase OK)" — **0 Findings**.

**Code:**
- `ui/settings_dialog.py`: `_SWR_VALUES` Liste + `_swr_value_to_index`
  Helper (Snap nächst-höher) + `QComboBox` mit 8 Werten 1.5..5.0 +
  Load mit Snap-print + Save `currentData()` + Reset `setCurrentIndex(3)`
- `ui/control_panel.py`: `_mode_btn_style` Active von rot/gelb auf grün
  analog `_omni_btn_style` (wirkt auf btn_cq + btn_auto_hunt)

**Hardware:** ANT1-Pflicht unverändert. Keine TX-Logik berührt.

**Final-R1 V4-pro:** „Push freigegeben." 0 KP. Optionale None-Edge-Test-
Lücke akzeptiert (Config-Default 3.0 schützt).

**5 atomare Commits:**
- C1 ui/settings_dialog.py (SWR-Combo)
- C2 ui/control_panel.py (Active-Style grün)
- C3 main.py APP_VERSION 0.97.34
- C4 tests/test_bundle_k.py NEU 11 Tests
- C5 Doku

**Tests:** 1289 → **1300 grün** (+11 Bundle K).

**Backup:** `Appsicherungen/2026-05-15_v0.97.33_vor_bundle_k/`.

**Field-Test F1-F6 pending** (HANDOFF).

---

## 🗄️ HISTORIE — P59: CQ-Button visuelle Konsistenz Normal vs. Diversity (ERLEDIGT als Bundle K v0.97.34)

**Trigger:** Mike-Field-Test P55: btn_cq in Normal wechselt zu „CQ AKTIV ■"
korrekt — aber bleibt visuell rot/standard. OMNI CQ in Diversity wird grün
wenn aktiv. **Inkonsistenz** — Mike: „sollte wie bei Diversity-Modus auch
grün werden. (einheitlich optisch nachvollziehbar)".

**Was tun:** btn_cq bei `active=True` gleichen grünen Style anwenden wie
btn_omni_cq. `set_cq_active(True)` in `ui/control_panel.py:1822` muss
zusätzlich `setStyleSheet(active_green_style)` setzen, bei `False` zurück
auf Default-Style.

**Wo umsetzen:**
- `ui/control_panel.py:1809+1822` `set_cq_active` erweitern
- Style-Konstante einmal definieren (Z.~1000 Bereich) damit beide Buttons
  dasselbe Grün nutzen — `_cq_active_green_style` als Modul/Klassen-Konst.
- Falls btn_omni_cq inline-Style hat: nach oben ziehen, beide Buttons nutzen
  dieselbe Konstante.

**Aufwand:** klein, ~15 Min Code. Workflow Pflicht (UI-Style-Eingriff über
mehrere Stellen).

---

## ✅ 15.05.2026 erledigt — P58: SWR-Limit Save-Hook Live-Propagation v0.97.31

Fix per V2-Self-Review-Erkenntnis: bereits etabliertes Pattern in Code
(set_power/tx_audio_level werden NACH dialog.exec() im MainWindow
propagiert). P53 hatte als einziger Pfad Inline-Propagation im Dialog
gebaut — das hatte den Bug. Fix: 1 Zeile raus aus settings_dialog,
1 Zeile rein in main_window + alle 3 Live-Setter unter gemeinsamem
`if self.radio.ip:`-Guard (R1-V4-pro-F1). Tests 1262→1268 (+6).
Field-Test F1-F3 pending. Siehe HISTORY.md v0.97.31.

---

## 🗄️ HISTORIE — P58: SWR-Limit Save-Hook propagiert nicht zur laufenden App (Mike-Field-Test 15.05.2026 morgens)

**Trigger:** Mike-P53-Field-Test 15.05.: SWR-Limit auf 1.5 in Settings
gespeichert während App lief — Watchdog greift NICHT (TX läuft mit
SWR 1.9 durch). Nach App-Neustart `[FlexRadio] SWR-Limit auf 1.5
gesetzt` korrekt im Terminal → Connect-Hook funktioniert, Save-Hook
nicht.

**Wurzel-Hypothese:** `ui/settings_dialog.py:680-683`
```python
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```
`self.parent()` returnt vermutlich QApplication/None statt MainWindow,
weil SettingsDialog evtl. ohne expliziten Parent-Arg konstruiert wird.
Oder `parent.radio.ip` ist None obwohl Radio verbunden.

**Was tun:**
1. Verifizieren mit `print(f"[P58-DBG] parent={type(parent).__name__} hasattr_radio={...} radio.ip={...}")` direkt vor Save-Hook
2. SettingsDialog-Konstruktor in `main_window.py` checken — wird `parent=self` übergeben?
3. Fix-Optionen:
   - Direkter Zugriff statt via `parent()`: SettingsDialog könnte Radio-Referenz im Konstruktor bekommen
   - Signal-Pattern: SettingsDialog emittet `settings_saved`, MainWindow connectet und propagiert
4. Beide Wege: zentralisieren — alle "live-relevanten" Settings (swr_limit, evtl. mehr in Zukunft) gehen über einen einzigen Apply-Pfad

**Aufwand:** klein, ~20 Min Code. **Workflow Pflicht** weil Konstruktor-API-Eingriff.

---

## 🗄️ HISTORIE — P57: SWR-Limit auf feste 0.5-Schritte begrenzen (ERLEDIGT als Bundle K v0.97.34)

**Trigger:** Mike-Test 15.05. P53-SWR-Watchdog: wollte 1.2 als Limit
testen → wird im FlexRadio-Setter auf 1.5 geclampt (P53). UI erlaubt
aber freie Float-Eingabe via `QDoubleSpinBox(1.5..10.0, step=0.5)` —
User kann beliebige Zwischenwerte tippen (z.B. 1.2, 4.7, 8.3). Plus
Range bis 10 ist unsinnig hoch (jeder Wert >3.5 = Hardware-Risiko).

**Mike-Spec:** „nur einstellbar in 0,5er-Schritten und keine anderen
zulassen also 1 / 1,5 / 2 / 2,5 / 3 / 3,5"

### Was tun

1. **`ui/settings_dialog.py:206-209`** `QDoubleSpinBox` → `QComboBox`
   mit festen Werten `[1.0, 1.5, 2.0, 2.5, 3.0, 3.5]`. Anzeige als
   `"1.0"`/`"1.5"` etc., Value-Cast über `float(combo.currentText())`.
2. **`radio/flexradio.py:947-951`** `set_swr_limit` Clamp-min von
   `1.5` → `1.0` damit UI-Wert 1.0 durchgeht (sonst Drift UI ≠ Radio).
3. **`config/settings.py`** Default bleibt 3.0 (mittiger sicherer Wert).
4. **Tests:** 2-3 Tests: ComboBox-Werte-Liste, Setter akzeptiert 1.0,
   Setter clamped >3.5 nicht (max 10.0 bleibt — Defensive bei kaputtem
   Settings-File mit altem 5.0-Wert, Migration via Load-Coerce auf
   nächsten erlaubten Wert).

### Wo umsetzen

- `ui/settings_dialog.py` Block ~Z.206-213 + `_save_and_close` Z.679
- `radio/flexradio.py:947-951`
- Settings-Load-Coerce in `config/settings.py` (alte Werte 4.0/5.0 →
  nächstkleinerer erlaubter Wert: 3.5)
- Tests: `tests/test_p57_swr_limit_steps.py` NEU

**Aufwand:** klein, ~30 Min Code. **Workflow Pflicht** (UI + Radio-API +
Settings-Migration = 3 Files = nicht trivial).

---

## 🆕 OFFEN — P52: Statistik-Toggle raus + 90-Tage-Rolling-Window (Mike 14.05.2026 nachmittags)

**Trigger:** Mike-Klärung 14.05.: Settings-Toggle „Statistik-Erfassung
aktivieren" macht keinen Sinn weil **Bandpilot ohne Stats blind** ist
und **Auswertungen** sie brauchen. Plus: Stats wachsen unbegrenzt
(~1 MB/Tag bei 40m-FT8-24h-Betrieb) → nach Jahren unübersichtlich.

### Was tun

1. **Toggle komplett raus** aus `ui/settings_dialog.py` (Block
   „Statistik-Erfassung aktivieren" entfernen)
2. **Stats sind immer an** — kein Settings-Key mehr, keine Wahl mehr
3. **Rolling-Window 90 Tage:** Dateien in `statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`
   die älter als 90 Tage sind beim **App-Start** automatisch löschen
   (analog Log-Rotation Bundle A P20, leise, atomar)
4. **Settings-Migration:** alter Key `stats_enabled` beim Load
   idempotent gepoppt damit alte Configs sauber wandern (analog P47-Pattern)

### Warum 90 Tage

| Use-Case | Lookback |
|---|---|
| Bandpilot Live-Empfehlung | 24h |
| Bundle-D Slot-Bar / Quick-Stats | ~1 Woche |
| Pooled-Mean-Analysen (Mike's Diagramme) | 5-7 Tage Soll, 2-4 Wochen verteilt |
| Reserve / Vergleich Jahreszeiten | ~30 Tage |
| **Total mit Puffer** | **90 Tage** |

→ Genug Puffer für saisonale Vergleiche, aber Disk-Footprint bleibt
~30 MB max. Wenn Mike länger will → später hochsetzen.

### Wo umsetzen

- `core/log_setup.py` oder neue `core/stats_cleanup.py`: Funktion
  `cleanup_stats_older_than_days(stats_dir, days=90)` analog
  `cleanup_old_logs`
- `main.py` beim App-Start: cleanup-Call (vor App-Init oder im
  Hintergrund-Thread um Start nicht zu verzögern)
- `ui/settings_dialog.py`: Toggle + zugehöriger Code raus
- `config/settings.py`: `stats_enabled`-Key beim Load entfernen
  (idempotent)
- Tests: cleanup-Funktion (Datei-Mock), Settings-Migration

**Aufwand:** klein-mittel, ~0.5-1 Tag. Workflow nötig.

---

## 📋 ARCHIVIERT (Plan-Detail) — P53: SWR-Live-Watchdog (Hardware-Sicherheit) — ERLEDIGT v0.97.29

**Trigger:** Mike-Field-Test 14.05.: nasse Antenne nach Regen → SWR>30
bei sofortigem TX mit 70W. **`swr_limit` (3.0) in Settings hat NICHT
gegriffen** weil der Check nur vor der Gain-Messung läuft
(`mw_radio.py:1334`), nicht im normalen TX-Pfad. FlexRadio-Hardware-
Schutz + Tuner haben Mike's Hardware gerettet — Glück gehabt, aber
Lücke im App-Code.

### Architektur

**SWR ist LIVE während TX verfügbar** (FlexRadio VITA-49-Telemetrie,
`radio.last_swr` wird kontinuierlich aktualisiert).

**Live-Watchdog während TX:**
1. Während `encoder.is_transmitting=True`: Timer alle **200 ms**
   `radio.last_swr` lesen
2. **Spike-Schutz:** 2 aufeinanderfolgende Messungen > `swr_limit`
   (~400 ms Bestätigung) — schützt gegen PTT-on-Glitch (50-100 ms
   Einschwing-Spike)
3. Bei Auslösung:
   - `encoder.abort()` + `radio.ptt_off()` SOFORT (mid-slot)
   - Watchdog-Timer stoppt mit PTT-off
4. **Modal-Dialog** (Mike's Wahl, kein nicht-modal):
   - Text: „**TX abgebrochen — SWR X.X (Limit Y.Y)**. Antenne tunen
     oder SWR-Limit in Einstellungen prüfen."
   - User muss bewusst wegklicken (nicht übersehen)
5. **Komplett-Stop** (Mike's Wahl, „keine Lücken in der Bedienung"):
   - `qso_sm.stop_cq()` + `cancel()` + `set_cq_active(False)`
   - `_omni_cq.stop("swr_block")`
   - `_auto_hunt.stop_auto_hunt("swr_block")`
6. **Wiederaufnahme nur bewusst** durch User (CQ-Klick / OMNI-Klick) —
   kein Auto-Resume, kein Cooldown
7. **QSO-Panel-Eintrag** zur Historie: `⚠ TX abgebrochen — SWR X.X`

### Hardware-Sicherheit

- Stop-Block darf **KEINE Antennen-Umschaltung** triggern
  (`set_tx_antenna` nicht aufrufen — ANT1 bleibt ANT1, CLAUDE.md
  HARDWARE-WARNUNG)
- `encoder.abort()` + `ptt_off()` sind antennen-neutral

### Wo umsetzen

- `ui/mw_tx.py` oder eigene `ui/swr_watchdog.py`-Klasse: `QTimer`
  während TX, Spike-Counter
- Hook in `encoder.start_tx`-Pfad (Watchdog start) und
  `_on_tx_finished` (Watchdog stop)
- Stop-Block-Pattern analog Bundle I (mit `stop_cq + cancel +
  set_cq_active(False) + encoder.abort + ptt_off`)
- Tests: Mock-Spike-Szenario, Spike-Schutz, modal-Dialog-Trigger,
  Antennen-NICHT-umgeschaltet (`set_tx_antenna`-Spy)

**Aufwand:** mittel, 1-1.5 Tage. Threading + Race-Conditions + Spike-
Robustheit → voller Workflow Pflicht.

---

## ✅ 16.05.2026 erledigt — P54: Auto-Tune bei Bandwechsel + RFPreset-Stützpunkt (Bundle) v0.97.44

Mike-Idee 16.05.: TUNE bei Bandwechsel speichert sofort 10-W-Stützpunkt.
Voller V1→V2→R1→V3→Code→Final-R1 (+Round 2 nach ROT-Fix) autonom mit
DeepSeek-V4-pro. R1 fand 2 ROT-Bugs (F1 Klassiker-Catch `watt=10`
statt round(avg), F2 Signal statt QMessageBox). Final-R1 fand 1 ROT
(State-Sync — `radio.set_power` nach `_apply_rf_preset` für Power-Spike-
Schutz). Tests 1367→1395 (+28). **V4-pro 19-Cycle-Bilanz: 0
Halluzinationen, 2 echte ROT-Bugs gefangen.** Field-Test F1-F8 pending
(alle Radio-pflichtig).

---

## 🗄️ HISTORIE — P54 Spec (Mike 14.05.2026 nachmittags, ERLEDIGT als v0.97.44)

**Trigger:** Eng verwandt mit P53 — zusätzliche Sicherheit/Komfort
bei Bandwechsel. Mike's Wahl: NUR Bandwechsel (20m→40m), NICHT
Modus-Wechsel (FT8↔FT4) und NICHT Normal↔Diversity.

### Settings-Block

Neuer Block in `ui/settings_dialog.py` Tab „TX & Schutz":

| Setting | Werte | Default |
|---|---|---|
| Auto-Tune bei Bandwechsel | Checkbox An/Aus | **AN** |
| Tune-Timeout | Sekunden-Eingabe (z.B. 5-60) | **15 s** |

Tune-Power kommt aus bereits existierendem `tune_power`-Setting
(5W / 10W / 20W).

### Ablauf

1. Bandwechsel löst aus → `_on_band_changed` läuft heute schon
2. Nach Band-Setup + vor erstem TX: **Auto-Tune-Modal öffnen** wenn
   Setting aktiv
3. Modal-Inhalt:
   - Spinner + Text „Auto-Tune läuft… (SWR X.X)"
   - **Auto-Close** wenn Tune fertig (SWR < `swr_limit`) ODER
     Timeout erreicht
   - Kein OK-Button — User muss nicht klicken
4. Bei Timeout (Default 15 s, einstellbar):
   - Modal schließt automatisch
   - **Warning-Dialog** „**Auto-Tune fehlgeschlagen** — SWR konnte
     nicht unter X gebracht werden. Antenne prüfen, manuelles
     Eingreifen nötig."
   - **TX-Block** (analog P53 Komplett-Stop)
   - User muss bewusst weitermachen

### Wichtig

- Tune-Power kommt aus Settings (`tune_power`) — nicht hardcoded
- Tuning läuft über bestehende Radio-API (`radio.tune(power_watts)`)
- Wenn `radio.ip` nicht gesetzt (kein Radio verbunden) → Auto-Tune
  silent skip
- Hardware-Pflicht: TX läuft während Tune über ANT1 (existiert
  schon in Tune-Pfad)

### Wo umsetzen

- `ui/auto_tune_dialog.py` NEU — Modal mit Spinner + Timer
- `ui/mw_radio.py:_on_band_changed`: nach Band-Setup Auto-Tune-Hook
  einfügen wenn Settings-Toggle aktiv
- `config/settings.py`: neue Keys `auto_tune_enabled`, `auto_tune_timeout_s`
- `ui/settings_dialog.py`: Setting-Block einbauen
- Tests: Auto-Tune-Trigger bei Bandwechsel, Auto-Tune-NICHT bei
  Mode-Wechsel, Timeout-Verhalten, Settings-Toggle-Effekt

**Aufwand:** mittel, 1-1.5 Tage. Modal-Dialog + Timeout-Handling +
TX-Block-Integration. Workflow Pflicht.

---

## ✅ 15.05.2026 erledigt — Intent-Klausel im App-Start-Disclaimer v0.97.37

Mike-Vorbereitung für eventuelle GitHub-Veröffentlichung. Disclaimer-Text
im Hardware-Warnungs-Dialog (`main.py:_show_hardware_warning`) erweitert
um DA1MHH-Bastel-Tool-Intent + MIT-Lizenz + Funklizenz-Verstöße als
Haftungs-Ausschluss. Höhe 540×340 → **540×400** (R1-V4-pro-F2 HiDPI-Puffer).

**Voller V1→V2→R1→V3-Workflow** trotz Trivial-Patch. R1 3 Findings, alle
übernommen (Wortlaut tragfähig, Höhe 400 statt 380, KISS in main.py).
Final-R1 V4-pro: „Push-Freigabe: Ja." 0 KP. **V4-pro 13-Cycle-Bilanz:**
0 Halluzinationen.

**Code:** 6 Zeilen Diff in `main.py` + APP_VERSION 0.97.36→0.97.37.
**Tests:** 1327→**1332** (+5: T1-T4 + Bonus, 1 Bundle-J-Test angepasst).
**Plan-Files:** prompts/intent_klausel_v[1,2,3].md + _r1.md + _final_r1.md.

Push pending bis Mike App-Start visuell bestätigt (kein Radio nötig).

---

## 🗄️ HISTORIE — Intent-Klausel-Spec (Mike 14.05.2026 nachmittags, ERLEDIGT)

**Trigger:** Mike-Sorge bei eventueller Veröffentlichung — Belt-and-
suspenders zur MIT-Lizenz: Intent-Klausel im bestehenden
Hardware-Warnungs-Bestätigungsdialog erweitern.

### Wortlaut

> „Dieses Projekt entstand als persönliches Bastel-Tool für meinen eigenen
> Funkbetrieb (DA1MHH). Der Quellcode steht unter MIT-Lizenz zur freien
> Verwendung — die Nutzung erfolgt jedoch ausschließlich auf eigene Gefahr.
> Keine Gewährleistung, keine Haftung für Hardware-Defekte, Funklizenz-
> Verstöße oder andere Folgen. ANT1 = TX-Antenne (immer). ANT2 = nur RX
> (NIEMALS TX, Regenrinne nicht für Sendeleistung geeignet)."

### Wo

`ui/startup_disclaimer_dialog.py` (oder wo das aktuell lebt) — Text
des Bestätigungsdialogs erweitern. „Verstanden"-Button bleibt wie
heute. Persistenz „nicht mehr zeigen wenn bestätigt" bleibt wie
heute.

**Aufwand:** trivial, ~5 Min. Könnte mit Bundle J gebündelt werden
weil thematisch zum Connect-Modal-Branding passt (beides Lizenz +
Disclaimer-Thema). Oder als atomarer eigener Commit.

---

## ⚠️ ALT — Bundle H Bandpilot-Aware Diversity-Klick (v0.97.25, 14.05.2026 mittags, Field-Test pending)

## ✅ ERLEDIGT 15.05.2026 — DeepSeek-Lessons-Files entfernt (Mike-Entscheidung)

V4-pro empirische Bilanz nach 5 Cycles (Bundle I + J + P51 + P53 + P55):
**30 Findings, 0 Halluzinationen, 100% verifizierbar.** Mike-Entscheidung
15.05.: Lessons-Files entfernen — V3-Schwächen-Liste nicht mehr relevant,
V4-pro hat keine bekannten Schwächen. Bilanz bleibt in CLAUDE.md-Header
dokumentiert. Falls V4-pro je halluziniert → ad-hoc Notiz im jeweiligen
Cycle-Memory.

Gelöscht:
- `docs/deepseek_lessons.md`
- Memory `feedback_deepseek_strengths_weaknesses.md`
- `docs/SESSION_WORKFLOW.md` Punkt 5 (Lessons-Update bei Feierabend)
- `CLAUDE.md` „Vor jedem R1-Prompt"-Hinweis

---

## 📋 ARCHIVIERT (Plan-Detail) — P51 Spec: Gain-Messung vereinheitlichen

> **Status: ERLEDIGT 14.05.2026 abends (v0.97.28) — siehe oben.**
> Plan-Detail bleibt zur Doku stehen.

**Mike's Beobachtung:** Aktuell wird die Gain-Messung pro Scoring-Modus
separat durchgeführt — d.h. wenn ich zufällig Standard messe um 10:00 und
5 Minuten später auf DX wechsle, muss ich nochmal komplett einmessen.
Beide Messungen werden in getrennten Stores abgelegt (`presets_standard.json`
und `presets_dx.json`) und können divergieren (siehe 20m FT8 14.05.: Std
ANT1=10/ANT2=10, DX ANT1=20/ANT2=10).

**Architektur-Klarstellung (Code-Analyse 14.05.):** Die 18-Zyklus-
Roh-Messung im `DXTuneDialog` ist scoring-UNABHÄNGIG — sie misst pro
Slot+Antenne+Gain-Stufe die Antennen-Pegel. Nur die **Auswertung** ist
scoring-spezifisch:
- **Standard-Scoring (`'normal'`):** „welche Gain-Stufe gibt mehr **Stationen**"
- **DX-Scoring (`'snr'`):** „welche Gain-Stufe gibt bessere **SNR**, besonders SNR<-10"

→ Aus identischen Roh-Daten ergeben sich **zwei** unterschiedliche optimale
Gain-Werte — beide aber sind aus EINER Messung ableitbar.

**Gewünschtes Verhalten:**

| Aktuell | Geplant |
|---|---|
| Gain-Messung läuft mit `_gain_scoring_mode` | gleiche Messung, aber **beide Auswertungen** parallel rechnen |
| Schreibt nur in 1 Store (Std oder DX) | Schreibt in **beide** Stores |
| Modus-Wechsel ≤ Gain-Validität: trotzdem neu messen | Modus-Wechsel ≤ Gain-Validität: **direkt nutzen** ohne Neu-Messung |

**Umsetzung (skizziert, kein Plan):**

1. `DXTuneDialog.get_results()` erweitern um beide Auswertungen zurückzugeben
   (z.B. `{"standard": {...}, "dx": {...}}`) statt nur den einen aktiven
   Scoring-Modus.
2. `_on_dx_tune_accepted` in `ui/mw_radio.py` (Z.1406+): beide Stores
   (`_standard_store` und `_dx_store`) mit jeweiligem Werte-Satz beschreiben.
3. `_gain_scoring_mode` bleibt aber wird nur noch für die UI-Anzeige
   verwendet („welche Bewertung wird gerade ausgespielt"), nicht für die
   Speicher-Entscheidung.
4. Statusbar/Dialog-Text während Messung: „Messung läuft (gilt für beide
   Modi)" statt „Messung Standard / Messung DX".
5. Tests: `DXTuneDialog` returns beide Sätze; mw_radio schreibt in beide
   Stores; bestehende Stage/Commit-Pipelines bleiben atomar.

**Begründung (warum lohnt sich das):**

- **50% weniger Mess-Zeit im Alltag.** Heute: 18 Zyklen × 2 Modi = 36
  Zyklen pro Band+FT_Mode. Künftig: 18 Zyklen total.
- **Konsistente Werte über Modi-Wechsel.** Heute können Std-Werte aus
  Vormittag und DX-Werte aus Nachmittag mit komplett anderen Bedingungen
  (Sonne, Storungen, Antennen-Pattern) verheiratet sein. Künftig: beide
  Werte aus derselben Mess-Situation.
- **Weniger Friktion für den Funker.** Mode-Wechsel mid-session ist heute
  ein 90-Sek-Block. Künftig: instant.
- **Schließt sich an P34-Stufe2 (Statik-Pipeline raus) an** — auch dort
  war das Ziel weniger Mess-Aufwand. Hier geht's um den Gain-Teil der
  noch da ist.

**Edge-Cases zum Aufpassen (DeepSeek-R1-Prüfung später):**

- **Migration bestehender Werte:** Mike's 20m hat heute Std 10/10 und
  DX 20/10. Bei nächster Messung: beide Stores werden überschrieben →
  divergierter Zustand verschwindet. Kein Reset nötig, aber im V1 prüfen
  ob das wirklich der erwünschte Weg ist.
- **Bug-Risiko bei nur-einer-Bewertung:** Wenn die Standard-Auswertung
  einen Bug hat (z.B. crash bei zu wenigen Stationen) aber die Roh-Daten
  ok sind, darf das nicht die DX-Auswertung mitreißen. Try/Except pro
  Auswertung.
- **`_gain_scoring_mode` als Settings-Key:** wird der Modus-Toggle (Std↔DX)
  überhaupt noch im Dialog gebraucht? Mike's Idee impliziert „immer beides
  rechnen" — der Toggle entfällt vielleicht ganz.

**Aufwand:** mittel, 1-2 Tage inkl. Test-Refactor. Workflow nötig (DXTune-
Dialog ist sensitive Strecke).

---

## 🆕 OFFEN_HISTORICAL — Bundle H: Bandpilot-Aware Diversity-Klick (Mike 14.05.2026 mittags)

**Mike's Beobachtung:** Bandpilot=Auto + Klick auf DIVERSITY → Std/DX-
Dialog erscheint trotzdem. Aber im Auto-Modus sollte Bandpilot SELBST
entscheiden ohne User-Dialog.

**Verhalten gewünscht beim DIVERSITY-Klick (Normal → Diversity):**

| Bandpilot | Daten | Verhalten |
|---|---|---|
| **off** | egal | Dialog „Welchen Modus verwenden?" (heute) |
| **auto** | genug | **kein Dialog** — Bandpilot wählt + Toast 6s (nur Std/DX im Ranking, kein Normal weil User explizit Div gewählt) |
| **auto** | zu wenig | Dialog mit dynamischem Intro „Nicht genug Daten für Bandpilot — bitte selbst wählen" |
| **manual** | genug | Manual-Dialog mit Std/DX-Empfehlung (analog 3-Wege heute) |
| **manual** | zu wenig | Dialog wie off (Fallback) |

**Architektur (Claude + DeepSeek einig, KISS):**

1. **1 dynamischer Dialog** statt 2-3 separat (nur Intro-Text variiert)
2. `BandpilotAutoToast` UNVERÄNDERT — iteriert eh über `rec["ranking"]`,
   2-Modi-Ranking automatisch (kein Subclass)
3. `recommend()` um `allowed_modes`-Parameter erweitern statt neue
   Methode (Default = alle 3, Diversity-only = 2-er Liste)
4. Dialog-Intro dynamisch `intro_label.setText(...)`

**Edge-Cases (R1):**
- Pipeline-Lock-Check
- `decision == "no_change"` bei auto → trotzdem Toast (anders als
  Bandwechsel-Pfad)
- Race bei gleichzeitigem Band+Mode-Wechsel

**Aufwand:** klein, 1-2 Tage. Sofort umsetzen.

---

## ✅ 14.05.2026 erledigt — Bundle G Diversity Std↔DX Toggle (v0.97.24)

2. Klick auf DIVERSITY-Button bei Bandpilot=Aus → direkter Toggle Std↔DX
(kein Dialog). Bei Auto/Manual: no-op. OMNI+Hunt-Stop bei Toggle.
11 Tests. Memory `project_bundle_g_diversity_toggle.md`.

Field-Test pending (Mike-Beobachtung „Dialog im Auto-Modus unerwünscht"
führte zu Bundle H — separater Pfad: Normal→Div Klick, nicht 2. Div-Klick).

---

### [HISTORISCH] Wunsch 1 — Diversity Std ↔ DX Toggle (Bundle G ERLEDIGT)

**Mike-Klarstellung 14.05.2026 vormittags (nach erstem TODO-Entwurf):**

> „Bei Bandpilot Auto entscheidet er eh, da keine Änderung. Bei Aus
> müsste der Dialog erscheinen NUR wenn ich von Normal auf Diversity
> klicke. Bin ich Diversity DX und klicke nochmal Diversity, soll
> direkt auf Standard wechseln ohne Rückfrage. Bin ich Standard und
> klicke nochmal Diversity → direkt zu DX. Weil sonst würde ich
> Normal klicken."

**Logik-Matrix (Bandpilot=Aus):**

| Aktueller Modus | Klick auf | Aktion |
|---|---|---|
| Normal | NORMAL | no-op |
| Normal | DIVERSITY | **Dialog Std/DX** (bereits implementiert) |
| Div Standard | DIVERSITY | **direkt → Div DX** (Toggle, kein Dialog) |
| Div DX | DIVERSITY | **direkt → Div Standard** (Toggle, kein Dialog) |
| Div (egal) | NORMAL | → Normal (heute schon) |

**Bandpilot=Auto:** keine Änderung in `_on_rx_mode_clicked` (Bandpilot
entscheidet via `_apply_bandpilot_auto` programmatisch).

**Architektur:**
- `control_panel._on_rx_mode_clicked` (Z.1487+): early-exit
  `if mode == self._current_rx_mode: return` ersetzen durch
  Toggle-Branch:
  - bei `mode == "diversity"` UND already-diversity UND
    `bandpilot_mode == "off"` → emit neues Signal
    `diversity_subtoggle_requested`
- `mw_radio` empfängt Signal, prüft aktuellen `scoring_mode`,
  ruft `_activate_diversity_with_scoring(opposite)` (existiert).
- Settings-Check `bandpilot_mode == "off"` braucht Lookup über
  `self.settings.get_bandpilot_mode()`.

**Edge-Cases:**
- Bandpilot=Auto + Div-Klick → kein Toggle (Auto entscheidet selbst).
  Anzeige neutral, keine User-Verwirrung.
- Während Mess-Phase (DXTuneDialog modal) → Klick blockiert (Dialog
  fängt alle Inputs).
- Bandpilot pending (Toast offen) während User klickt → Bandpilot
  cancelt sich selbst via existierende Logik (R1-F3 Bundle E).

**DeepSeek-Bewertung:** ✅ KISS, ~10-15 Zeilen, Risiken minimal.
Mike's Logik ist *konsistenter* als Dialog-Variante (weniger Klicks,
keine Pseudo-Wahl wenn nur 1 Option sinnvoll).

### Wunsch 2 — Gain-Sharing zwischen Std/DX-Store (Mittel, abhängig W1)

**Symptom:** Bei Sub-Modus-Wechsel Std↔DX wird Gain-Messung erneut
gemacht obwohl Gain Hardware-Eigenschaft ist (Antennen-Pegelausgleich).
**Wunsch:** Eine Mess-Reihe → beide Stores.

**Code-Verifikation (core/preset_store.py):**
- `presets_standard.json` + `presets_dx.json` haben beide
  `ant1_gain`/`ant2_gain` (zusätzlich zu `ratio`/`dominant`).
- Gain ist scoring-unabhängig (Hardware-Pegelausgleich).
- Ratio + dominant bleiben getrennt (scoring-spezifisch).

**Pragma-Lösung (DeepSeek):** beim `commit_gain` in Store A automatisch
auch in Store B schreiben (gleicher Timestamp). 10-15 Zeilen.

**Edge-Cases:**
- User kalibriert nur einen Modus neu → überschreibt anderen
  (logisch korrekt: Hardware-Wert).
- Bestehende getrennte Einträge bleiben erhalten, beim ersten Sync
  vereinheitlicht.
- DeepSeek: „grenzwertig overengineering, zentraler Gain-Store wäre
  sauberer aber Datenmodell-Änderung". Claude-Position: pragmatisch
  reicht für Mike-only-Hobby.

**Reihenfolge:** W1 zuerst (trivial), dann W2.

---



> **Mike-Regel 07.05.2026:** Offene Aufgaben gehoeren AUSSCHLIESSLICH
> in diese Datei. Nicht in CLAUDE.md, nicht in HANDOFF.md. Diese Datei
> ist die einzige Quelle fuer Backlog/Bugs/Feature-Wuensche.

---

# 🟢 STATUS-ÜBERSICHT (für neue Session)

**Aktuelle Version:** v0.97.22 (14.05.2026)
**Tests:** 1179 grün
**App-Stand:** Bundle E TX-Slot-Lock Refactor (Mike-Korrektur Bundle-D:
Even/Odd = TX-Slot-Lock SmartSDR-Style, nicht RX-Filter) ERLEDIGT,
Field-Test F1-F9 pending. Davor Bundle D UI-Tweaks (Settings-Padding,
DT-Vorzeichen, Slot-Progress-Bar bleiben unverändert). P50 Bänder-Sichtbarkeit Field-Test ✓ (Mike:
„funktioniert super"). Memory-Leak P30 resolved (war TTS-Server, nicht
SimpleFT8). Davor: P34-Stufe2 Statik-Pipeline raus (v0.97.19), Toast-
Bundle (v0.97.18), P46 Bandpilot Normal-Reintegration (v0.97.17), P14 DT-
Symmetrie (v0.97.16), Bundle C P10+P13 (v0.97.15)
ERLEDIGT, Field-Test 5 Punkte pending. Bundle B' (P32+P33) zuvor
erledigt (Field-Test pending). Veraltete Punkte aus TODO bereinigt:
- **P29 OMNI-CQ-Parity-Trennung** war seit 11.05.2026 commit `5498f0d`
  erledigt — TODO veraltet, jetzt bestätigt.
- **P49 OMNI-Pretrigger** wurde durch P48 automatisch mit-erledigt
  (Encoder.target_tx_offset_s aus tx_buffer_s).
- **P24 Last-RX-Mode-Persist** widerspricht Mike's P35-Bug-F-Vision
  (App-Start IMMER 20m FT8 Normal). Nicht implementieren.

## ✅ 14.05.2026 erledigt — Bundle E TX-Slot-Lock Refactor (v0.97.22)

Mike-Korrektur nach Bundle-D: „ich wollte nicht filtern, sondern TX-Slot
festlegen (SmartSDR-Style)." Refactor:

- Settings `tx_slot_lock` ∈ {"none","even","odd"} persistiert
- Helper `resolve_tx_slot(their_even, lock_status, rx_mode)` in
  `core/qso_state.py` als Modul-Funktion (R1-S3 zentral)
- 3 TX-Pfade gepatcht: Hunt (Pre-Validierung), CQ-Start, CQ-Reply
- Lock greift NUR Normal-Modus, in Diversity Buttons aus + State
  bleibt in Settings
- Bundle-D RX-Filter-Code komplett zurückgebaut
- Signal `slot_filter_changed` → `tx_slot_lock_changed`
- Bei Mode-Wechsel zu Normal: UI aus Settings geladen
- Mismatch-Klick → `add_info("Klick auf X ignoriert — Slot-Lock=Y, ...")`

R1-Pragma:
- F1 Thread-Safety: GIL atomar reicht
- S2 Auto-Hunt-Pause: nicht nötig (10-Min-Hard-Cap)

Final-R1 „0 Findings, Push freigegeben". Tests 1166 → 1179 (+13).
Field-Test F1-F9 pending.

## ✅ 14.05.2026 erledigt — Bundle D UI-Tweaks (v0.97.21)

5 UI-Feinschliffe nach P50 Field-Test als atomares Bundle:

- **A** Settings-Block „Sichtbare Bänder" luftiger (Spacing 6→10 +
  ContentsMargins)
- **B** DT-Anzeige `+0.0`/`-0.0` → `0.0` (Mike: „ist 0.0 :-)"). Neuer
  Helper `_format_dt` in `ui/rx_panel.py`. Edge-Cases: ±0.04→`0.0`,
  ±0.05→`+0.1`/`-0.1`, -0.0 zentral abgefangen.
- **C** Even/Odd oben → Filter-Buttons (Normal-only). Signal
  `slot_filter_changed`, exklusive Toggle-Logik (3 Zustände mit 2 Buttons),
  RXPanel `apply_slot_filter` blendet Zeilen aus.
- **D** Diversity: Buttons via `set_slot_buttons_visible(False)`
  ausgeblendet, QSO/Logbuch füllen Platz, Filter immer reset bei Modus-
  Wechsel (R1-Q4).
- **E** Statusbar `_slot_progress_bar` (NEU): QProgressBar 80×14 px,
  Cyan `#00CCFF` für Even / Magenta `#FF66CC` für Odd (R1-Q5),
  dynamische cycle_dur, sekündliches Update.

R1-F1 KRITISCH Signal-Verdrahtung umgesetzt. Final-R1 „0 KP, Push
freigegeben". Tests 1155 → 1166 (+11 T1-T11). Field-Test F1-F8 pending.

**P50 Field-Test ✓** (Mike: „funktioniert super").
**P30 Memory-Leak resolved** (war TTS-Server, nicht SimpleFT8).

## ✅ 13.05.2026 erledigt — P50 Bänder-Sichtbarkeit (v0.97.20)

- **Mike-Wunsch:** im Settings-Dialog Bänder abwählbar damit sie aus dem
  Band-Panel verschwinden
- **Settings-API:** `Settings.get_enabled_bands()` + `set_enabled_bands(list)`
  mit defensiver Filterung (kein String/nicht in BAND_FREQUENCIES/Duplikate)
- **UI:** QGroupBox „Sichtbare Bänder" in Tab „FT8 & Diversity",
  3×3-QCheckBox-Raster, Min-1-Logik (AC3), Reset setzt zurück
- **ControlPanel.set_visible_bands** mit R1-F1 current_band-Guarantee +
  R1-F2 Prop-Bar-mitverstecken
- **MainWindow.apply_visible_bands** beim App-Start und nach Settings-Apply
- **Bandpilot NICHT angefasst** — R1-Q1 war Halluzination (recommend
  empfiehlt MODI, keine Bänder)
- Voller Workflow V1→V2 (10 Findings)→R1 7/10 (2 KRITISCH + 2 SOLLTE)→V3
  (14 ACs Compact-fest)→Code→Final-R1 0 KP „Push freigegeben"
- 11 neue P50-Tests T1-T11 inkl. T5 F1 + T8 F2 + T10 S3
- Tests 1144 → 1155 grün
- Backup `Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/`
- Push pending bis Mike's Field-Test F1-F8

## ✅ 13.05.2026 erledigt — Toast-Bundle (v0.97.18)

- Bandpilot-Toast + Manual-Dialog Ranking-Marker 🥇🥈🥉 statt `1./2./3.`
- `_TOAST_DISPLAY_MS = 6000` (war 5000) — Mike-Lesezeit
- R1-SOLLTE-Defensive: Env-Var `SIMPLEFT8_TEXT_MARKERS=1` → Text-Fallback
- Voller Workflow V1→V2→R1 9/10→V3→Code→Final-R1 0 Findings „Push freigegeben"
- 6 neue Tests inkl. T6 importlib.reload-Pattern
- Tests 1233 → 1239 grün
- Backup `Appsicherungen/2026-05-13_v0.97.17_vor_toast_bundle/`
- Push pending bis Mike's visuelle Bestaetigung

## ✅ 13.05.2026 erledigt — P46 Bandpilot Normal-Reintegration (v0.97.17)

- **P46** P35-Bug-E zurueckgenommen, 3-Wege-Bandpilot (Normal/Std/DX)
- `ui/mw_radio.py:774-779` + `:811-816` Skip+Block-Bloecke geloescht
- R1-F2 `_set_rx_mode_direct` Doppelaufruf-Refactor
- R1-F3 `_bandpilot_pending` 5-Tupel mit current + Konsistenz-Check
- Voller Workflow V1→V2→R1 8/10→V3→Code→Final-R1 9/10 „Push freigegeben"
- 8 neue P46-Tests inkl. T7 (R1-F4 rec=None) + T8 (R1-F3 Modus-Race)
- 2 alte P35-Bug-E-Tests geloescht, 4 Workaround-Kommentare bereinigt
- Tests 1227 → 1233 grün
- Doku `docs/explained/bandpilot_de.md`+`.md` (EN) Hinweis ergaenzt
- Backup `Appsicherungen/2026-05-13_v0.97.16_vor_p46_bandpilot_normal/`
- **P35-Bug-F unveraendert** (App-Start IMMER 20m FT8 Normal)
- Push pending bis Mike's Field-Test-OK

## ✅ 13.05.2026 erledigt — P14 DT-Werte-Symmetrie (v0.97.16)

- **P14** MAD-basierter Outlier-Filter (Hampel, k=2.5) in `core/ntp_time.py`
- DEADBAND 0.05 → 0.02 (R1-F1 KRITISCH Anti-Einfrier)
- DAMPING bleibt 0.7 (R1-F4 KISS)
- Opt-in Debug-Log via `SIMPLEFT8_DT_DEBUG=1`
- Voller Workflow V1→V2→R1 5/10→V3→Code→Final-R1 9/10
- 10 neue Tests inkl. T7 Sanity-Anker (R1-F2-Anti-Symptom-Fix)
- Tests 1217 → 1227 grün
- Backup `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/`
- Field-Test asynchron — Mike schickt Screenshots
- Push pending bis Mike's mehrfache Bestätigung

## ✅ 13.05.2026 erledigt

| Version | Was |
|---|---|
| **v0.97.15** | **Bundle C** — P10 PSK-Backoff-Reset (MAX 60→10 Min, thread-safe `_Backoff` mit Lock, public `reset_backoff()` + `set_mode()`, Auto-Trigger bei Band/Modus-Wechsel im Statusbar + Karten-Pfad). P13 RX-Panel-Slot-Times (UTC-Spalte = Slot-Boundary statt Wall-Time; Fix in `add_message` + `_populate_row` + mixed-Type-safe Sort). V2 fand 2-Pfade-Bug, Final-R1 fand zusätzlich Mode-Sync-Bug (`_mode` wurde nie aktualisiert). 13 neue Tests. |
| **v0.97.14** | **Bundle B'** — P32 RX-Panel-Spalten persistiert über App-Restart (Settings-Key `rx_panel_hidden_cols`, defensiv gefiltert + COL_MSG-Schutz, Signal-Pattern wie country_filter). P33 `✓ QSO komplett`-Zeile erscheint jetzt direkt nach 73-Empfang (vor nächstem CQ) — 2-Signal-Split `qso_confirmed_visual` SOFORT + `qso_confirmed` nach Courtesy-Send. V2-Self-Review fand OMNI-Race in V1-Variante-A. 12 neue Tests. Final-R1 „Push freigegeben". |
| **v0.97.13** | **P48 DT-System aufräumen + tunen** (4 Teile) — A: Hardware-Werte in Settings `radio_timing` (`tx_buffer_s=1.3`, `rx_hardware_offset_default_s=0.26`), Encoder kriegt `tx_buffer_s`-Parameter, `TARGET_TX_OFFSET` weg. B: Cross-Modus-Fallback FT4/FT2→FT8 gleiches Band. C: Hardware-Default 0.26 als Kaltstart. D: Schnell-Konvergenz im 1. Slot bei ≥10 Stationen+Stddev<0.1. **Kritischer Bug-Fix**: `_is_initial = _saved.get(_mode_key()) is None` (R1-V2 Finding 1). 17 neue Tests + 3 angepasst. Final-R1 9.5/10, 0 KP. 7 atomare Commits gepusht. |
| **v0.97.12** | **Bundle A (P43+P20+P18)** — setproctitle (Activity Monitor), Log-Rotation (datierte Tagesdateien + Symlink + 7-Tage-Cleanup + archive/), DT-Print-Dedup. Neues Modul `core/log_setup.py`. 8 neue Tests. Final-R1 „Push freigegeben". |
| **v0.97.11** | **P47 Tote Frequenz-Settings** — `audio_freq_hz` + `max_decode_freq` raus (UI ohne Wirkung), Statusbar-Filter-Anzeige raus. Defaults hartcodiert. 5 neue Tests. |
| **v0.97.10** | **P44 Statusbar DT-Label** — eigenes Permanent-Widget statt globaler setStyleSheet (kein grüner Statusbar-Hintergrund mehr). 2 neue Tests. |

## ✅ 11.05.2026 erledigt (v0.97.1)

| Version | Was |
|---|---|
| **v0.97.1** | **P35.DIVERSITY-STARTUP-FIX** — 3 Bugs aus P34-Field-Test gefixt. **Bug A:** `_enable_diversity` bei radio.ip=None defer + Resume via `_check_diversity_preset`. **Bug B:** `_apply_dynamic_toggle` resettet Queue+current_ant unter Lock. **Bug B5:** Settings-Toggle überlebt Session (Auto-Reactivate). **AK5 R1-Q4 KRITISCH:** activate() respektiert Cache-Reuse-Ratio (70:30 bleibt). 5 atomare Commits. Tests 1116 → 1129 (+13). Plan-Files prompts/p35_diversity_startup_fix_v[1,2,3]+r1+final_r1.md. Field-Test V3 §6 F1-F8 pending. Push pending. |
| **v0.97.0** | **P34.DIVERSITY-DYNAMIC** — Antennen-Verhältnis live im Betrieb anpassen (statt 1× pro Stunde 90s-UI-Sperre). ENTWEDER-ODER zur Statik (Toggle in Settings, NICHT persistiert). Modul `core/dynamic_diversity.py` NEU + 2 Helper-Funktionen in `core/diversity.py`. Antennen-Panel Phase-Label wird **blau** wenn aktiv. 9 atomare Commits. Tests 1070 → 1111 (+41). Plan-Files prompts/p34_diversity_dynamic_v[1,2,3]+r1.md (Compact-fest). Field-Test V3 §5 F1-F12 pending. Push pending. |

## ✅ Heute erledigt (10.05.2026)

| Version | Was |
|---|---|
| **v0.96.5** | P16.UI-CLEANUP-BUNDLE (P9+P11+P15: Remess-Countdown, Statusbar-Refresh, Antennen-Label) |
| **v0.96.6** | P22.PRESET-ATOMARITAET + **P8.MESS-MODAL** (atomares Speichern Gain+Ratio + WindowModal-Sperre während Mess) |
| **v0.96.7** | P23.OMNI-COUNTER-EIGEN (eigener Down-Counter pro Modus, sichtbar als `↻10` in TX-Display) |
| **v0.96.8** | P21.DEBUG-LOG + DIV-MEAS-RADIO-GUARD (an/aus in Settings, Skip wenn radio.ip=False) |
| **v0.96.9** | **P26.CONNECT-MODAL** (Modal beim App-Start mit Spinner + „Versuch X von 10" + „ohne Radio weiter" + „Beenden". R1-K2-Goldwert: `_start_radio` deferred via singleShot. R1-K1-Race-Fix: lokale Dialog-Referenz + try/except RuntimeError. Final-R1 „Push freigegeben") |

## 🔥 OFFEN — Hohe Priorität

| ID | Was | Aufwand | Hinweis |
|---|---|---|---|
| **P30** | MEMORY-LEAK 124 GB nach Tagen Laufzeit — Mike musste App killen | 2-3h Diagnose | **KRITISCH**. Verdacht: AP-Lite Sound-File-Aufzeichnung auf SSD. Detail unten. |
| **P12** | QSO-POSTPROCESSING-ASYNC — App hängt 1 Min nach QSO (logbook.refresh ist Wurzel) | **PARTIAL-FIX 11.05.** Logbuch nur letzte 500 (commit folgt). Sauberer Async-Refresh weiter offen | Mike-Diagnose 11.05.: logbook.refresh() lädt 20 MB ADIF jedes Mal neu |
| **P27** | MESS-GUARD — vor Antennen/Diversity/Gain-Mess prüfen ob Radio verbunden (Mike-Wunsch 10.05. 17:35: „BVOR MESSUNG SIND WIR ÜBERHAUPT VERBUNDEN?") | 1.5h Workflow | aus P26-Spec ausgegliedert |
| **P25** | RADIO-IP-LATE-SETTING — Wurzel warum `radio.ip` spät gesetzt wird | 2h Diagnose | Mike 10.05. ~18:00: „radio ist nicht spät, wird normal gesucht und gefunden" → evtl. obsolet, vor Push prüfen |

## 📋 OFFEN — Mittlere Priorität

| ID | Was | Aufwand |
|---|---|---|
| ~~P34-Stufe2~~ | ~~Statik-Pipeline KOMPLETT entfernen~~ ✅ **ERLEDIGT v0.97.19 (13.05.2026 nachmittags)** — Voller Workflow autonom, ~250 LOC raus, 8 Test-Files gelöscht, 1 neu. Final-R1 "Push freigegeben" 0 Bugs. Field-Test F1-F10 pending. |
| ~~P32~~ | ~~RX-Panel Spalten-Konfiguration persistieren~~ ✅ **ERLEDIGT v0.97.14 Bundle B' + Field-Test ✅ (13.05.2026 09:38 UTC)** |
| ~~P33~~ | ~~QSO-fertig-Meldung Reihenfolge-Bug~~ ✅ **ERLEDIGT v0.97.14 Bundle B' (13.05.2026)** |
| ~~P24~~ | ~~Letzten RX-Mode merken~~ ❌ **VERWORFEN** — widerspricht Mike's P35-Bug-F-Vision (App-Start IMMER 20m FT8 Normal) |
| ~~P10~~ | ~~PSK-Backoff-Reset~~ ✅ **ERLEDIGT v0.97.15 Bundle C (13.05.2026)** |
| ~~P14~~ | ~~DT-WERTE-ASYMMETRISCH — NTP-Korrektur-Issue~~ ✅ **ERLEDIGT v0.97.16 + Field-Test ✅ (13.05.2026 09:38 UTC)** Mike: Korrektur drift 0.2705→0.2285, Verteilung 5+/5-/10≈0 symmetrisch (vorher 11-/1+/8≈0) |
| ~~P13~~ | ~~RX-Panel-Slot-Times~~ ✅ **ERLEDIGT v0.97.15 Bundle C (13.05.2026)** |

## 🛠 OFFEN — Niedrige Priorität

| ID | Was | Aufwand |
|---|---|---|
| ~~P18~~ | ~~DT-KORR-3X-RELOAD~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| ~~P20~~ | ~~LOG-ROTATION simpleft8.log~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| ~~P29~~ | ~~OMNI-CQ Paritäts-Anzeige Leerzeile + Even-Slot dunkler~~ ✅ **ERLEDIGT 11.05.2026** commit `5498f0d` (TODO war veraltet, verifiziert 13.05.) |
| ~~P49~~ | ~~OMNI-Pretrigger aus Settings~~ ✅ **ERLEDIGT durch P48 v0.97.13** (OMNI nutzt Encoder.target_tx_offset_s aus tx_buffer_s, keine separate Konstante mehr) |
| ~~P43~~ | ~~setproctitle für Activity-Monitor-Erkennbarkeit~~ ✅ **ERLEDIGT v0.97.12 Bundle A (13.05.2026)** |
| ~~P44~~ | ~~Statusbar DT-Korrektur grün-Bug~~ ✅ **ERLEDIGT v0.97.10 (13.05.2026)** |
| ~~P46~~ | ~~Bandpilot Normal wieder reinholen → 3-Wege-Vergleich Normal/Std/DX~~ ✅ **ERLEDIGT v0.97.17 (13.05.2026 mittags)** R1 8/10→9/10, Tests 1227→1233, Field-Test pending |
| ~~P47~~ | ~~Tote Frequenz-Settings + Statusbar-Filter-Anzeige entfernen~~ ✅ **ERLEDIGT v0.97.11 (13.05.2026)** |

## 📋 P47.TOTE-FREQUENZ-SETTINGS-ENTFERNEN (Mike+Claude+R1 13.05.2026)

**Konsens:** Beide Frequenz-Settings + Statusbar-Anzeige raus.

**Begründung (R1-Originalton):**

> „Tote Settings sind toter Code und verletzen das Prinzip der geringsten
> Überraschung. Steuerbarkeit vortäuschen, die nicht existiert."

**Was entfernt wird:**

1. **TX Audio-Frequenz** (Setting + UI-Eingabe + Default-Wert)
   - Wird vom CQ-Such-Algorithmus eh dynamisch überschrieben
   - File: `config/settings.py` (Key entfernen), `ui/settings_dialog.py`
     (Eingabe-Feld Tab „FT8 Diversity" raus)

2. **Max. Decode-Frequenz** (Setting + UI-Eingabe + Default-Wert)
   - Beim Modus-Wechsel automatisch gesetzt (FT8/4 → 3000, FT2 → 4000)
   - User-Eingabe wird sofort überschrieben
   - Gleiche Files wie 1.

3. **Statusbar-Anzeige „100-3100 Hz"**
   - File: `ui/main_window.py` `_update_statusbar()` — `_FILTERS` Dict
     + `filter_str`-Aufbau raus
   - Auch der `filter_str`-Einsatz im Statusbar-Text

**Migration alter Configs:**
Keine eigene Migrationslogik nötig. Settings-Objekt ignoriert unbekannte
Keys beim Laden, schreibt sie beim Save nicht zurück → alte
`tx_audio_freq` / `max_decode_freq` werden stillschweigend weggespült.

**Tests:**
- Tests die explizit auf diese Settings testen müssen entfernt werden
- grep `tx_audio_freq` und `max_decode_freq` über Tests-Verzeichnis
- Settings-Smoke-Tests bleiben sonst grün

**Aufwand:** 1-2h Workflow (V1→V2→R1→V3 + Code + Tests + Doku).

**Risiko:** LOW — beide Settings sind ohnehin wirkungslos, kein
Verhalten ändert sich für aktive Nutzung.

**Plan-File: P47-Workflow wird bei Umsetzung angelegt.**

---

## 📋 P46.BANDPILOT-NORMAL-REINTEGRATION (Mike+Claude+R1 12.05.2026)

**Aktueller Stand:** Bandpilot vergleicht nur Diversity Standard vs DX.
Mike's Vision: „ganz oder gar nicht" — wenn schon Pilot, dann alle 3 Modi.

**Konsens Mike + Claude + R1:**

> Normal wieder rein. Architektonisch sauber, UX-konsistent, fairere
> Pilot-Entscheidung. R1: „95 % der Bänder verliert Normal — aber die
> 5 % Spezialfälle (dünne Datenbasis 17m/12m, resonante 20m-Antenne in
> ruhigen Stunden, Single-Antenna-Setups) rechtfertigen den Aufwand."

**Schwellen (bereits vorhanden!):**

`core/mode_recommender.py`:
```python
MIN_DAYS_HOUR = 3        # Mindest-Messtage pro Stunde
MIN_CYCLES_HOUR = 20     # Mindest-Zyklen pro Modus
```

→ Für Normal-Reintegration: **gleiche Schwellen verwenden.** Wenn
Normal ≥3 Tage × ≥20 Zyklen pro Stunde hat, wird's in den Vergleich
aufgenommen. Sonst 2-Wege-Vergleich (Std vs DX) wie heute.

→ Ausreißer-Glättung: bereits durch Pooled Mean über alle Zyklen
gewährleistet. Bei R1's Bedenken zu „nur 2-3 Datenpunkte" greift
`MIN_CYCLES_HOUR=20` als Sicherung.

**Aufwand:** 2-3h Workflow (V1→V2→R1→V3 + Code in `core/mode_recommender.py`
+ Tests + UI-Update Settings-Dialog).

**Geplante Aenderungen:**

1. `core/mode_recommender.py` — `compare_modes()` Normal-Slot reinholen
2. `ui/main_window.py` bzw. Bandpilot-Handler — 3-Wege-Switch
3. Settings-Dialog: Bandpilot-Beschreibung anpassen
4. Tests: Normal-Wins-Szenario + Normal-Schwellen-Fail-Szenario

---

## 📋 P43.PROCTITLE — Activity-Monitor-Erkennbarkeit

**Hintergrund (12.05.2026):** Bei der P30-Memory-Leak-Diagnose tauchte
das Problem auf dass macOS Activity Monitor sowohl SimpleFT8 als auch
Qwen3-TTS als „Python" anzeigt — beide nutzen das gleiche Python-Binary.
→ Bei „128 GB Python" konnten wir nicht unterscheiden welcher Prozess
schuld war. Stellte sich raus: TTS, nicht SimpleFT8.

**Lösung — `setproctitle`-Modul:**

In `main.py` ganz oben (nach den ersten Imports):
```python
try:
    import setproctitle
    import os
    setproctitle.setproctitle(f"SimpleFT8 DA1MHH PID:{os.getpid()}")
except ImportError:
    pass  # optionales Modul, App läuft auch ohne
```

→ Activity Monitor zeigt dann `SimpleFT8 DA1MHH PID:12345` statt
nur „Python". Sofort erkennbar gegen TTS und andere Python-Apps.

**Installation:**
```bash
./venv/bin/pip install setproctitle
```
Plus Eintrag in `requirements.txt` falls vorhanden.

**Test:**
1. App starten, `ps -axo pid,command | grep SimpleFT8` → Name sollte
   `SimpleFT8 DA1MHH PID:NNN` zeigen
2. Activity Monitor öffnen → Spalte „Prozessname" zeigt es

**Aufwand:** ~30 min (5 Zeilen Code + pip install + 1 Test + Doku).

**Trivial-Klausel:** ja → KEIN voller V1→V2→R1→V3-Workflow nötig.
Direkt umsetzen wenn wir das nächste Mal eh Code anfassen.

**Risiko:** keins. `setproctitle` ist Standard-PyPI-Modul, weit
verbreitet, no-op wenn fehlt (try/except).

## 📦 Push pending

KEIN Push seit v0.95.16. Lokal gesammelt: **v0.95.16 → v0.96.9 + P2-Tool +
P3-Audio-Dump + P21-Debug-Log + P26-Connect-Modal**. Push erst wenn
Mike alle Field-Tests abgenommen hat. Aktueller Stand: P22/P23/P21/P16
field-getestet OK; P26 Field-Test ausstehend (V3 §8 6 Punkte).

## ✅ 11.05.2026 RESOLVED

- **P12 Logbuch-Hang nach QSO:** behoben via Partial-Fix (500-Cap, commit
  `d61accc`). Mike-Bestätigung 11.05. ~05:55: „Einfrieren nach qso fehler
  behoben gerade qso erfolgreich beendet. können wir abhaken."
- **P28 PSK-Bug:** OMNI-TX hat `_has_sent_cq` nicht gesetzt, PSK-Worker
  fragte nie ab. Fix in `_on_tx_started` (commit `708a521`). Mike-Field-
  Test 11.05.: „psk reporter zeigt ansehr sehr gut".
- **P31 Counter-Bug ↻9 statt ↻10:** OMNI-Counter zeigte post-decrement
  statt pre-decrement Wert + post-Flip-Parity-Race in QSO-Panel. Fix in
  `core/omni_cq.py` (commit folgt) — neues Display-Property
  `cq_remaining_display` + `cq_tx_even_display`, mw_qso + Statusbar
  lesen Display-Wert. Sequenz jetzt: ↻10 → ↻9 → ... → ↻1 → Flip → ↻10.

## ✅ Heute RESOLVED (zur Klarheit)

- **P17** (DX-Init-Hang): aufgelöst durch erfolgreichen Phase-2-Mess + P22
  Half-State-Reject + P21 Radio-Guard
- **P19** (DX-Cache-Ignoriert): gleiche Wurzel wie P17, gleiche Lösung
- **P9** (Remess-Countdown): in P16-Bundle erledigt
- **P11** (Statusbar-Parity-Refresh): in P16-Bundle erledigt
- **P15** (Antennen-Label): in P16-Bundle erledigt
- **P21** (Strukturiertes-Debug-Log): heute in v0.96.8 implementiert
- **P22** (Preset-Atomaritaet): in v0.96.6 implementiert + field-getestet
- **P23** (OMNI-Counter-Eigen): in v0.96.7 implementiert + field-getestet

---

# 📋 OFFENE WORKFLOWS (Detail-Beschreibungen)

## 🔥 P30.MEMORY-LEAK 124 GB (Mike-Notfall 11.05. ~05:25)

**🎯 KONKRETER VERDACHT (12.05. Diagnose-Sitzung):** Skip-Bug in
`core/decoder.py` Z.174-188 — `_audio_buffer_24k`-Liste wird NICHT
geleert wenn ein Decode-Slot übersprungen wird (vorheriger Decode
nicht fertig). 720 KB pro Skip-Slot, Wachstum ~432 MB/h bei
Diversity passt zu Mike's Screenshot-Math (540 MB/h). Memory-Watcher
läuft als Daemon (PID 72060), 1-2 Tage Korrelation abwarten dann
voller Workflow Fix. Detail-Diagnose: siehe HISTORY 2026-05-12.

**Symptom:** Mike musste App beenden — **124 GB Speicher**
(„speicherleak"). Problem besteht seit Tagen.

**Mike-Verdacht:** App schreibt Sound-Files zur AP-Lite-Analyse
auf SSD. Vermutlich Datei-Handles nicht geschlossen ODER Audio-
Buffer im RAM gehalten statt freigegeben.

**Klärung nach Live-Check 11.05.: RAM, NICHT Disk.**
- `~/.simpleft8/` ist 45 MB (sauber)
- `audio_dump/` existiert nicht (P3 Audio-Dump aus)
- → 124 GB sind echtes RAM-Leak, nicht SSD-Voll
- Math-Eingrenzung: ~720 KB Audio-Slot × 172.000 Slots ≈ 30 Tage
  durchgehend → passt zu „seit Tagen"

**Verdächtige Pfade (Reihenfolge nach Wahrscheinlichkeit):**
- **`core/locator_db.py` `_calls`-Dict** — wächst monoton mit jedem
  CQ-Decode, kein Cleanup. Bei Mike's Setup vermutlich riesig.
- **`log/qso_log.py` records** — alle QSOs in-memory, akkumuliert?
- **`decoder.last_audio_24k`** — wird überschrieben, aber evtl. von
  Qt-Signal-Subscribern festgehalten (`audio_dump_signal` oder
  Cycle-Pipeline)
- **`_recent_logged_calls`-Dict** (P1.7 Dedup, mw_qso) — 300s Window,
  aber wird das je gepruned?
- **AP-Lite `_buffers`** — Cap exists, aber 720 KB pro Buffer
- **`qso_panel.log_view` QTextEdit** — `_auto_trim_by_age` läuft alle
  30s, prüfen ob wirklich greift

**Diagnose-Schritte:**
1. App neu starten, Activity Monitor offen lassen, RAM-Verlauf beobachten
2. Welche Files wachsen auf SSD? `du -sh ~/.simpleft8/` und
   `du -sh audio_dump/` und `du -sh statistics/`
3. AP-Lite-Recording-Pfad finden + Output-Größe prüfen
4. Memory-Profiling via `tracemalloc` (Python-Builtin) — App startet,
   nach 30 Min Snapshot
5. **Sofort-Mitigation:** AP-Lite-Recording oder Audio-Dump
   temporär deaktivieren bis Wurzel geklärt

**Aufwand:** 2-3h Diagnose + ggf. Fix.

**Schweregrad:** **KRITISCH** — App-Crash nach Tagen, Mike kann nicht
durchgehend laufen lassen, blockt Push.

---

## 📋 P32.RX-PANEL-COLUMN-PERSIST (Mike-Wunsch 11.05. ~05:55)

**Symptom:** Im RX-Panel (Empfangsfenster) kann der User per Rechtsklick
auf die Spaltenüberschrift auswählen welche Spalten angezeigt werden
(z.B. km, dt, Zeit, Land etc.). Aber bei App-Restart geht die Auswahl
verloren — Default-Spalten kommen zurück.

**Mike-Wunsch:** Auswahl bei jedem Klick speichern, bei App-Start laden.

**Files (vermutet):**
- `ui/rx_panel.py` — `RxPanel` Klasse, Spalten-Definition + Rechtsklick-
  Menü-Handler
- `config/settings.py` — Settings-Key `rx_panel_visible_columns` (list[str])
- `ui/main_window.py` `closeEvent` — Save vor Quit
- App-Init — Load + Anwenden auf RX-Panel

**Aufwand:** ~1h Lite. Pattern wie andere Settings-Persistenz (band,
mode, power_preset, etc.).

**Schweregrad:** Niedrig — UX-Annoyance, keine Funktion betroffen.

---

## 📋 P33.QSO-COMPLETE-DISPLAY-ORDER (Mike-Wunsch 11.05. ~05:55)

**Symptom:** Im QSO-Panel erscheint die `✓ QSO mit X komplett`-Zeile
NACH dem nächsten `→ Sende CQ ↻N`-Eintrag statt davor. Beispiel
(Mike-Screenshot):
```
03:53:30 [E] ← Empf. EC3A 73       ← Empfang des 73 (QSO done)
03:54:00 [E] → Sende CQ DA1MHH ↻9  ← schon nächster CQ-TX
         ✓ QSO mit EC3A komplett   ← KOMMT ERST HIER
03:55:00 [E] → Sende CQ DA1MHH ↻8
```

**Mike-Erwartung:** `✓ QSO komplett` direkt nach Empfang-73, vor
nächstem CQ-Send.

**Wurzel (unbestätigt):** `qso_confirmed`-Signal feuert erst in
`on_message_sent` für `TX_73_COURTESY` (NACH Höflichkeits-73-Send).
Bis dahin ist der nächste Slot-Start schon getriggert und OMNI hat
einen CQ losgeschickt. Plus `add_qso_complete` hat keinen Zeitstempel
— Append-Reihenfolge im QTextEdit kann nicht durch Slot-Zeit
korrigiert werden.

**Lösungs-Optionen:**
- `qso_confirmed.emit` SOFORT bei 73-Empfang (nicht nach
  Höflichkeits-73) — aber das bricht Mike's P1.10-Fix (IC-7300
  Auto-Sequence wartet auf Höflichkeits-73)
- `add_qso_complete` mit Slot-Time-Stempel + cleverer Insertion-Order
  via QTextCursor (komplex)
- Pre-resume von OMNI verzögern bis nächster-übernächster Slot
- Eigener Workflow V1→V2→R1→V3 nötig (mehrere Abhängigkeiten:
  qso_state TX_73_COURTESY-Pfad, OMNI-Resume-Timing, qso_panel
  Append-Logik).

**Aufwand:** 1-2h Workflow.

**Schweregrad:** Niedrig (kosmetisch).

---

## 📋 P29.OMNI-CQ-PANEL-PARITY-SEPARATION (Mike-Wunsch 11.05. ~05:15)

**Symptom:** OMNI-CQ sendet im Even- UND Odd-Slot, im QSO-Panel laufen
die `→ Sende CQ DA1MHH JO31 ↻N`-Zeilen ohne optische Trennung
hintereinander. Mike will auf einen Blick sehen welche Paritäts-Phase
gerade läuft.

**Soll:**
1. Bei **Paritäts-Wechsel** (Even-Block → Odd-Block oder umgekehrt)
   eine **Leerzeile** zwischen den TX-Zeilen einfügen.
2. **Even-Sende-Zyklus etwas dunklere Farbe** (Mike: „ein wenig dunkler,
   nicht ganz dunkel — Farbe sollte beibehalten werden"). Aktuelle TX-
   Farbe ist `#FFAA00` (Orange) — Even-Variante z.B. `#CC8800` oder
   `#E09600` (selber Hue, niedrigere Lightness).

**Files (vermutet):**
- `ui/qso_panel.py` `add_tx(message, omni_remaining=None, ant_label=...)`
  bekommt neuen Param `tx_even: bool` und detektiert Paritäts-Wechsel
  via internem `_last_omni_parity`-State.
- ggf. Helper `_append_blank_line()` für die Trennzeile.

**Aufwand:** ~1h Lite — Style + State. Trivial-Klausel vermutlich
greifend (kleine UI-Änderung, keine Architektur).

**Schweregrad:** Niedrig — reine UX, keine Funktion.

---

## 📋 P24.LAST-RX-MODE-PERSIST (Mike-Wunsch 10.05. 17:10)

**Symptom:** App startet IMMER in Normal-Modus, egal in welchem Modus
sie beendet wurde (Diversity Standard / Diversity DX).

**Mike-Zitat:** „nicht schöner fix aber ein fix" (kommentiert das
aktuelle Verhalten dass NORMAL nach Restart erzwungen wird).

**Soll:** App speichert beim Beenden den aktuellen RX-Mode (`normal`,
`diversity_standard`, `diversity_dx`) in Settings und stellt ihn beim
nächsten Start wieder her.

**Files (vermutet):**
- `config/settings.py` neue Key `last_rx_mode`
- `ui/main_window.py` `closeEvent` speichert
- `ui/main_window.py` Init liest + setzt RX-Mode

**Aufwand:** ~1h Workflow-Lite (V1 + Code, kein R1 weil trivial).

**Schweregrad:** Mittel — UX-Annoyance, kein Daten-Verlust.

---

## 📋 P25.RADIO-IP-LATE-SETTING (Wurzel-Diagnose 10.05.)

**Symptom:** Beim App-Start ist `self.radio.ip` falsy (False/leer)
obwohl Audio-Stream (DAX) bereits Stationen liefert. Dauer unklar
(Sekunden? Minuten?). Trigger fuer den heute via Skip-Fix umgangenen
0/6-Hänger.

**Workaround heute (P21 v0.96.8):** `_handle_diversity_measure` skipped
wenn `radio.ip=False` → wartet bis Connection da. Sobald `radio.ip` True
wird, läuft Mess natürlich an.

**Wurzel-Frage:** WARUM ist `radio.ip` lange False?
- Reconnect-Loop läuft im Hintergrund?
- Audio-DAX-Stream und TCP-Connect sind separate Pfade?
- Initialisierungs-Reihenfolge in `MainWindow.__init__`?

**Files (vermutet):**
- `radio/flexradio.py` Connect-Logik + ip-Property
- `ui/mw_radio.py` Init + Reconnect-Mechanik

**Aufwand:** ~2h Diagnose + ggf. Fix.

**Schweregrad:** Niedrig (Workaround greift) — aber Wurzel-Bug bleibt
und kann anderswo Probleme machen.

---

## 📋 P26.MODAL-RADIO-CONNECT (Mike-Wunsch 10.05. 17:15)

**Symptom:** Während FlexRadio gesucht/verbunden wird, sieht Mike das
nicht prominent — kleine Statusmeldung rechts im UI „beachtet keiner".

**Mike-Spec:**
- Modal-Dialog im Vordergrund während Connect läuft
- KEIN OK-Button, KEIN Abbruch — nur Info „FlexRadio wird verbunden"
- Sobald Radio verbunden → Dialog ausblenden
- Alternativ ODER zusätzlich: prominente Statusmeldung rechts
  (gross, sichtbar) — aber Modal ist Mike's bevorzugte Variante

**Pattern:** analog `MessStatusDialog` aus P22/P8 — WindowModal (NICHT
ApplicationModal weil Reconnect-Logik im Hintergrund laufen muss).
Auto-Close bei Connect-Erfolg via `radio.connected`-Signal.

**Files (vermutet):**
- `ui/connect_status_dialog.py` NEU (analog `mess_status_dialog.py`)
- `ui/mw_radio.py` Open-Hook beim Connect-Start, Close-Hook bei
  `radio.connected`-Signal

**Aufwand:** ~1.5h V1+Code+Test. KEIN voller Workflow weil Pattern aus
P22 kopiert.

**Schweregrad:** Mittel — UX (verhindert Confusion bei langen
Connect-Zeiten und löst möglicherweise auch P21-Problem).

**Claude-Hinweis 17:30 UTC:** P26 löst nebenbei vermutlich auch
P25-Symptome — wenn Mike den Modal-Dialog sieht statt zu denken
„App ist tot", weiß er warum die Mess wartet. Plus: das Modal könnte
selbst die Mess-Start-Steuerung übernehmen (Mess startet erst NACH
Connect-Erfolg, sauber statt Skip-Workaround). Beim Bauen von P26
würde ich vorschlagen P21-Skip-Fix beizubehalten als Defense-in-Depth,
aber das Modal wäre der primäre Schutz. → **Wenn P26 gebaut wird,
P25 evtl. komplett obsolet.**

---

## 🔥 TOP — P7 Field-Test (Mike, post-Code)

**Status:** Code fertig (v0.96.4), Final-R1 „Push freigegeben"
(0 KRITISCH/SOLLTE/KOENNTE). Tests **1008 grün**. App gestoppt —
Mike startet selbst für Field-Test.

**Field-Test 8-Punkte-Plan (V3 §6 F1-F8):**

| F | Test | Erwartung |
|---|---|---|
| F1 | App start, Diversity, OMNI toggeln | OMNI-Start-Log + CQ-Audiofreq-Set + erster CQ in aktuellem Slot |
| F2 | 5-10 Min beobachten | CQ-Ruf in EINER Paritaet (z.B. nur Even-Slots :30/:00). Andere Slots leer im qso_panel. **Diversity-Anzeige zeigt beide Antennen wechselnd** (kein „nur eine"). |
| F3 | Statusbar checken | `Ω CQ=X (E)` oder `(O)` zeigt aktuellen Stand |
| F4 | 10 Min weiterlaufen lassen | Paritaets-Wechsel automatisch (Log: „Paritaets-Wechsel auf Odd"). qso_panel zeigt ab dann CQ in anderer Paritaet (z.B. nur Odd :45/:15) |
| F5 | Antwort kommt waehrend OMNI | OMNI pausiert, QSO laeuft normal. Nach QSO: OMNI resumed in alter Paritaet |
| F6 | 1h warten → Diversity Re-Mess (90s) | OMNI sendet **nicht** waehrend Mess. Nach Mess: OMNI sendet wieder |
| F7 | Bandwechsel mid-OMNI | OMNI auto-stop (band_change), App stabil |
| F8 | Mode-Wechsel auf Normal | OMNI auto-stop (mode_change), App stabil |

**Bestanden wenn:** F1-F4 sauber + F2 zeigt Diversity beide Antennen.

## 🚀 Push (zusammen mit Field-Test-Freigabe)

KEIN Push (origin) seit v0.95.16. Lokal gesammelt seit dann:
**v0.95.16-0.96.4 + P2-Tool**. Push erst nach Mike-Field-Test-OK
mit `git push origin main`.

---

## 📋 P8.MESS-STATUS-DIALOG (geplant nach P7)

**Mike-Wunsch 10.05.2026:** Modal-Dialog während Diversity-Mess-Phase.

**Spec:**
- Trigger: `_diversity_ctrl.start_measure()` aufgerufen → Dialog öffnen
- Modal blockierend (sperrt UI dauerhaft im Vordergrund)
- Inhalt:
  - Titel: "Diversity-Antennen werden neu eingemessen"
  - Aktuelle Antenne (A1/A2)
  - Slot-Counter (z.B. "Slot 3 von 6")
  - Restzeit (z.B. "~45s")
  - Optional: bisheriger Ratio + Live-Werte
- Schließt automatisch wenn `_diversity_ctrl.phase` zurück auf "operate"

**Workflow:** eigener V1→V2→R1→V3 nach P7 abgeschlossen.

**Files:**
- NEU `ui/mess_status_dialog.py` (QDialog Subclass analog zu existing dx_tune_dialog.py)
- `ui/mw_cycle.py` Hook nach `start_measure()` → Dialog öffnen
- `ui/mw_cycle.py` Phase-Wechsel "measure" → "operate" → Dialog schließen

**Aufwand:** ~1-2h V1+V2+R1+V3+Code

---

## 📋 P9.REMESS-COUNTDOWN-UI (Field-Test 10.05. Mike)

**Symptom:** Re-Mess-Countdown in Antennen-Panel springt in 10-Min-Blöcken
(58 → 48 → 38) statt jede Minute zu aktualisieren. Irritierend.

**Soll:** Countdown updated alle 60s (oder noch häufiger), Format
`XX min YY s` damit User Fortschritt sieht.

**Files (vermutet):**
- `ui/control_panel.py` oder `ui/antenna_card.py` — Countdown-Display
- Trigger: `_diversity_ctrl.seconds_until_search` oder analog für Re-Mess

**Aufwand:** ~30 Min (trivialer UI-Fix, vermutlich ohne vollen Workflow)

---

## 📋 P10.PSK-BACKOFF-RESET (Field-Test 10.05. Mike)

**Symptom:** App's PSK-Reporter-Polling geht bei Server-Errors (502/503/
Timeout) in exponentielles Backoff bis 60 Min. Wenn Server wieder läuft,
fragt App stundenlang nicht mehr — Anzeige bleibt leer obwohl Mike
gehört wird (Direct-API-Test 10.05.: 15 Stationen weltweit hörten DA1MHH).

**Soll (Optionen — Mike entscheidet im V1):**
1. BACKOFF_MAX von 3600s auf 300s (5 Min) senken
2. Manueller Reset-Button in UI
3. Auto-Reset bei OMNI-Start oder Mode-Wechsel

**Files:**
- `core/psk_reporter.py:42-43` BACKOFF-Konstanten
- ggf. `ui/control_panel.py` für Reset-Button
- `ui/main_window.py` für Auto-Reset-Hook

**Workaround sofort:** App neu starten → Backoff resettet.

**Aufwand:** ~1h V1→V2→R1→V3+Code

---

## 📋 P11.STATUSBAR-PARITY-REFRESH (Field-Test 10.05. Mike, P7-Folge)

**Symptom:** Nach OMNI-Paritäts-Wechsel zeigt Statusbar `Ω CQ=X (O)`
weiterhin alte Parität, obwohl `_cq_tx_even` korrekt geflipped ist.
TX-Anzeige im qso_panel ist korrekt (zeigt neue Parität).

**Diagnose:** `parity_flipped`-Signal wird emit + `_on_omni_parity_flipped`
ruft `_update_statusbar()`. Aber UI-Refresh hängt evtl. an QTimer der
zu selten läuft, oder `_update_statusbar` nutzt veraltete Werte.

**Files:**
- `ui/main_window.py` `_update_statusbar` + `_on_omni_parity_flipped`
- ggf. statusbar-Refresh-Timer prüfen

**Aufwand:** ~30 Min (UI-Bug, trivial)

---

## 📋 P12.QSO-POSTPROCESSING-ASYNC (besteht seit Wochen, Mike 10.05.)

**Symptom:** Nach jedem QSO-Ende hängt GUI 1-2 Min ("Beachball"). App
läuft weiter (Decoder-Thread arbeitet, 35-84% CPU), aber UI-Thread
ist blockiert.

**Vermutete Ursachen (alle parallel):**
- `core/psk_reporter.py` Polling im GUI-Thread mit 30-90s Timeouts
- ADIF-Save (`log/adif.py`) Disk-I/O blocking
- QRZ-Upload-Trigger (HTTPS-POST mit Timeout)
- Locator-DB-Save (atomic-Write)
- Statistik-Logging

**Soll:** Alle blocking I/O nach QSO-Ende in Worker-Thread auslagern
(`QThread` oder `concurrent.futures.ThreadPoolExecutor`).

**Files:**
- `ui/mw_qso.py` QSO-End-Handler
- `core/psk_reporter.py` (separat von P10)
- `log/adif.py`
- `core/locator_db.py`

**Aufwand:** ~2-3h V1→V2→R1→V3+Code (komplex weil mehrere Pfade)

---

## 📋 P13.RX-PANEL-SLOT-TIMES (Field-Test 10.05. Mike, besteht seit v0.95.16+)

**Symptom:** RX-Panel zeigt krumme Wall-Time-Zeiten (z.B. 10:51:42)
statt FT8-Slot-Boundaries (10:51:30 oder 10:51:45). Mike erinnert
sich an Slot-Zeiten in vorigen Versionen.

**Diagnose:** `ui/rx_panel.py:280` nutzt `msg._utc_display` oder
Fallback `time.strftime("%H%M%S", time.gmtime())`. Wenn der Decoder
`_utc_display` nicht setzt, kommt Wall-Time durch.

**Files:**
- `ui/rx_panel.py` (letzte Aenderung Commit `7e8df00` v0.95.16)
- `core/decoder.py` setzt `msg._utc_display` / `_utc_str` / `_slot_start_ts`?
- ggf. `core/message.py` Format

**Aufwand:** ~1-2h (Decoder-Pfad muss verstanden werden)

---

## 📋 P20.LOG-ROTATION (Mike-Wunsch 10.05.2026)

**Symptom:** `~/.simpleft8/simpleft8.log` wird append-only geschrieben.
Datei waechst unendlich, nach Wochen MB-gross. Bug-Diagnose im alten
Log schwierig (nicht klar welcher Tag was war).

**Soll:**
- Eine Datei pro Tag: `simpleft8-2026-05-10.log`
- Aelter als N Tage (z.B. 7) automatisch loeschen
- Aktueller Tag: `simpleft8.log` Symlink → heutige Datei

**Files:**
- `main.py:32` `_log_file = open(...)` durch `TimedRotatingFileHandler`
  oder Custom-Lösung ersetzen

**Aufwand:** ~1h

---

## 📋 P21.STRUKTURIERTES-DEBUG-LOG (Mike-Wunsch 10.05.2026)

**Symptom:** Bug-Diagnose schwierig weil Log-Eintraege oft kontextlos
sind (z.B. `[Diversity] 48 St. | A1>A2: 0` ohne Antenne/Uhrzeit).

**Soll:** An wichtigen Stellen strukturierte Eintraege mit:
- Datum + Uhrzeit (statt nur HH:MM:SS)
- Aktive Antenne (A1/A2)
- Aktuelle Mode/Band/Mess-Phase
- Encoder-Status (TX/RX/idle)

**Files:**
- `core/diversity.py` Antennen-Switch-Pfad
- `core/decoder.py` Mess-Pass-Output
- `core/encoder.py` TX-Pfad
- `core/ntp_time.py` DT-Korrektur-Pfad

**Aufwand:** ~2h Diagnose + Refactor (welche Stellen brauchen mehr Kontext?)

---

## 📋 P22.PRESET-ATOMARITAET (Mike-Analyse 10.05. nach P17/P19-Resolve)

**Mike-Analyse 14:35:** „wenn eine von beiden eintraegen verstaerkung
und/oder diversity fehlt oder fehlerhaft ist und nur einer geladen
werden kann kommt es vermutlich zu den fehler weil die app entweder
beide oder keinen wert erwartet"

**Architektur-Schwaeche:** `presets_dx.json` / `presets_standard.json`
speichert `gain_timestamp` und `ratio_timestamp` separat. Wenn Phase 1
(Verstaerker) erfolgreich aber Phase 2 (Antennenvergleich) haengt,
verbleibt Half-State (gain fresh, ratio stale). Bei jedem Restart wird
Phase 2 wieder versucht → wenn die Wurzel-Bedingung nicht weg ist
(z.B. Race), Endlos-Schleife.

**Loesungs-Optionen:**

1. **Atomares Speichern:** beide Felder zusammen oder gar nicht.
   Phase 1 schreibt nichts in File bis Phase 2 fertig ist (gespeichert
   im Memory). Wenn Phase 2 hängt → kein Disk-Write → Restart fängt
   sauber wieder vorne an.

2. **Robustheit-Fallback:** wenn Phase 2 nach N Versuchen (oder Timeout
   90s) fehlschlaegt → Default-Ratio 50:50 mit aktuellem
   ratio_timestamp speichern. App nicht in Endlos-Schleife stecken.

3. **Beides:** atomares Speichern PLUS Fallback bei Phase-2-Fehlschlag.

**Files:**
- `core/preset_store.py` `update_gain` + `update_ratio`
- `ui/mw_radio.py` `_check_diversity_preset` Half-State-Logik
- `ui/mw_cycle.py` Phase-3-Erfolgs-Pfad

**Aufwand:** ~2-3h V1→V2→R1→V3+Code.

**Schweregrad:** Hoch (latenter Bug, kann jederzeit wieder auftreten
wenn Phase 2 mal wieder haengt).

---

## ✅ P17 + P19 RESOLVED (10.05.2026 ~14:30 Field-Test Mike)

**Aufloesung:** P17 (DX-Init-Hang) und P19 (DX-Cache-Ignoriert) waren
beide Folge davon dass Phase 2 (Antennenvergleichs-Mess) NIE sauber
abgeschlossen hat fuer DX-Mode → ratio_timestamp blieb auf Default
50:50, beim Restart triggert App immer wieder Phase 2-Versuch.

**Auflöser:** Heute lief Phase 2 erstmals erfolgreich durch (ratio=30:70,
dominant=A2 in presets_dx.json gespeichert mit aktuellem
ratio_timestamp).

**Test-Bestätigung Mike 14:30:**
- App-Restart in Normal ✓
- Wechsel zu DX → alles wie es sein soll ✓
- Wechsel zu Normal → alles gut ✓
- Wechsel zu Diversity Standard → beide Antennen aktiv ✓

**Offen:** WARUM Phase 2 vorher nicht durchlief. Vermutung: zu frueher
Mode-Wechsel oder Race bei Antennen-Switch. Wenn Bug nochmal auftritt
→ Re-Diagnose.

---

## 📋 P19.DX-CACHE-IGNORIERT-BEI-MODE-WECHSEL (Field-Test 10.05. Mike) [RESOLVED]

**Symptom:** NORMAL → DIVERSITY DX wechseln macht **komplette Neu-
kalibrierung** obwohl gueltiger Cache da sein sollte (Cache 2h gueltig
laut CLAUDE.md, Mike erinnert sich an 6h).

**Soll:** Cache pruefen → wenn vorhanden + nicht stale → laden + Kali-
brierung ueberspringen. Erst wenn stale → neu kalibrieren.

**Mike-Zitat:** „die ja speichern soll und die dann 6 stunden oder so
gueltig ist er juenger wird die geladen und kalibrirung uebersprungen"

**Files (vermutet):**
- `ui/mw_radio.py` Mode-Switch zu DIVERSITY DX
- `core/diversity.py` oder `core/preset_store.py` Cache-Lade-Logik
- ggf. zusammen mit P17 (auch Diversity-DX-Init-Issue)

**Aufwand:** ~1-2h Diagnose + Fix. Vermutlich ueberlappt mit P17.

**Schweregrad:** Hoch — verhindert produktiven Wechsel zu DX.

---

## 📋 P17.DIVERSITY-DX-START-INIT-BUG (Field-Test 10.05. Mike, BLOCKIEREND)

**Symptom:** Bei App-Start direkt in **DIVERSITY DX**-Modus haengt Mess
bei `MESSEN 0/6`. Antennen-Switch greift nicht — alle Stationen werden
nur auf A1 empfangen, A2=0.

**Log-Beweis:**
```
[Diversity] 48 St. | A1>A2: 0 | A2>A1: 0 (0%) | Nur A1: 48 | Nur A2: 0
[Diversity] 50 St. | A1>A2: 0 | A2>A1: 0 (0%) | Nur A1: 50 | Nur A2: 0
```

**Konsequenz:**
- A2 sammelt keine Decode-Daten
- `_measure_step` inkrementiert nie (in `add_measurement` nur bei
  Antennen-Switch-Decode)
- Mess haengt ewig 0/6
- OMNI kann nicht senden (V2-L12 Schutz: phase != "operate")

**Workaround:** NORMAL → DIVERSITY STANDARD wechseln + Kalibrieren →
laeuft. Aber DIVERSITY DX direkt nach Start = Bug.

**Reproduzierbar:** Mike heute zweimal beobachtet (ca. 11:00 + 13:45).

**Files (vermutet):**
- `ui/mw_radio.py` Mode-Switch-Logik bei DX
- `core/diversity.py` Mess-Initialisierung
- ggf. fehlt eine Antennen-Init beim ersten Slot in DX

**Aufwand:** ~2-3h (Diagnose + Fix + Test). VORSICHT: Mike-Spec
"Diversity ist UNANTASTBAR" — nur das Init-Verhalten beim DX-Start
fixen, keine Hauptlogik aendern.

**Schweregrad:** **BLOCKIEREND** — verhindert ProduktivOnut von OMNI in DX-Modus.

---

## 📋 P18.DT-KORR-3X-RELOAD (Field-Test 10.05. Mike, Diagnose)

**Symptom:** Beim App-Start wird DT-Korrektur fuer aktuelles Band 3×
aus File geladen:
```
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
[DT-Korr] FT8_20m: Gespeicherter Wert +0.650s geladen
```

**Vermutung:** Initial-Load + Bandwechsel-Reload + Mode-Setup-Reload =
3×. Funktional egal (Wert ist deterministisch), aber ineffizient + irritiert
beim Log-Lesen.

**Aufwand:** ~30 Min Diagnose (wer ruft `_load_for_current_key()` 3×?)
+ ggf. Konsolidierung auf 1 Aufruf.

**Schweregrad:** Niedrig (kosmetisch, keine Regression).

---

## 📋 P15.ANT-LABEL-VERTAUSCHT (Field-Test 10.05. Mike)

**Symptom:** "(ANT2 ↑2.0 dB)"-Label erscheint hinter **Sende**-Eintrag
im qso_panel. FALSCH — Hardware sendet IMMER ANT1 (verriegelt). Label
gehört hinter **Empfangs**-Eintrag um zu zeigen welche Antenne RX
besser war.

**Diagnose:** `ui/mw_qso.py:90-129`:
- `_antenna_pref_label(call)` liefert " (ANT2 ↑2.0 dB)"
- Wird in `qso_panel.add_tx(message, ant_label, ...)` als ant_label
  uebergeben → Label hinter Sende-Eintrag
- Soll: `qso_panel.add_rx(message, ..., ant_label=...)` Label hinter
  Empf.-Eintrag

**Files:**
- `ui/mw_qso.py:121-129` — Label bei add_tx weg, statt bei add_rx zufuegen
- `ui/qso_panel.py:add_rx` — neuer optionaler ant_label-Param

**Aufwand:** ~30 Min trivialer UI-Fix

---

## 📋 P14.DT-WERTE-ASYMMETRISCH (Field-Test 10.05. Mike)

**Symptom:** RX-Stationen zeigen DT fast alle im Minus (-0.1 bis -1.7),
sollten ausgeglichen zwischen + und - sein. Statusbar zeigt
`DT: +0.40s (n=17)` aktive Korrektur — funktioniert nicht symmetrisch.

**Diagnose:** `core/ntp_time.py` DT-Korrektur konvergiert evtl. zu
weit in eine Richtung. Beobachtung passt nicht zu Erwartungswert
(Korrektur sollte RX-DT auf 0 zentrieren).

**Files:**
- `core/ntp_time.py` Median-Berechnung + Damping
- `core/decoder.py` `DT_BUFFER_OFFSET` (FT8=2.0)
- ggf. `dt.md` Doku als Referenz

**Aufwand:** ~2h Diagnose + Fix (Audio-Buffer-Timing-Issue)

---

## 🛠️ META: CLAUDE.md + Memory Restrukturierung

> **Analyse 09.05.2026** — CLAUDE.md ist 673 Zeilen (Ziel: ~120 Zeilen). Memory hat 57 Dateien, Index 73 Zeilen.

### Ursachen des Bloats (identifiziert)

1. **`feedback_todo_history_pflicht.md`-Regel**: "nach jedem Task → CLAUDE.md Header updaten" → nach 20+ Features
   reines Anhängen ohne Kürzen → "Aktueller Stand"-Block wächst unbegrenzt.
2. **Workflow dreifach beschrieben**: V1→V2→R1→V3 steht in CLAUDE.md (Z. 5-30), nochmal Z. 161-170,
   nochmal in 4 Memory-Feedback-Dateien + docs/WORKFLOW.md. Quelle der Wahrheit: docs/WORKFLOW.md.
3. **Philosophie + Leitsätze in CLAUDE.md**: Z. 133-199+ gehören in docs/PHILOSOPHY.md (bestehend?),
   nicht in die Kontext-Datei.
4. **DeepSeek-Tool-Details in CLAUDE.md**: Z. 109-131 (Helper-Skript, Kosten, Tabelle) → Memory oder
   docs/DEEPSEEK_WORKFLOW.md.
5. **Memory-Index-Bloat**: ~30 ✅-ERLEDIGT Project-Einträge belegen Index-Zeilen. Completed → archivieren.

### Plan (4 Schritte, KEIN Workflow nötig — das ist Doku, kein Code)

**Schritt 1 — CLAUDE.md auf ~120 Zeilen schrumpfen:**
- Behalten (fett): Workflow-Pflicht-Block (Z. 5-30), Hardware-Warnung ANT1/ANT2 (Z. 32-57),
  Session-Lifecycle-Kurzfassung (Z. 60-94), Aktueller-Stand-Header (1 kompakte Zeile), Start-Befehl.
- Raus (mit Verweis): Philosophie → `docs/PHILOSOPHY.md`, Leitsätze → `docs/PHILOSOPHY.md`,
  DeepSeek-Tool-Details → Memory `feedback_workflow_works_with_deepseek.md`,
  Feature-Workflow-Abschnitt → `docs/WORKFLOW.md` (Verweis genügt).
- Neue Prune-Regel: "Aktueller Stand = max 3 Zeilen. Alte Stände raus."

**Schritt 2 — docs/ Dateien anlegen/aktualisieren:**
- `docs/PHILOSOPHY.md` — Projekt-Philosophie + Programmier-Leitsätze (bestehende Datei prüfen)
- `docs/ARCHITECTURE.md` — Modul-Übersicht, Klassen, Signal-Flow (bestehende Datei prüfen)
- `docs/KNOWN_BUGS.md` — Offene Bugs mit Diagnose (statt in CLAUDE.md)

**Schritt 3 — Memory-Index bereinigen:**
- Alle ✅-ERLEDIGT project_*.md Einträge aus MEMORY.md entfernen (die Dateien selbst behalten)
- Nur noch ⏳-pending + ⚠️-aktiv + ⛔-PFLICHT im Index → Ziel < 40 Zeilen

**Schritt 4 — `feedback_todo_history_pflicht.md` Prune-Ergänzung:**
- Zusatz: "Beim CLAUDE.md-Update: Aktueller-Stand-Block auf max 3 Zeilen begrenzen, alten Stand raus."

### Trigger
"claude.md restrukturieren" oder "meta aufräumen" → diesen Plan ausführen.

---

## 📌 OFFEN — TOP-PRIORITAET (zuerst angehen)

### 🟡 Splashtop-Doppelklick + Single-Klick verschluckt (NEU 2026-05-08)
- **Symptom:** Mike steuert von Linux Mint Notebook fern. Im RX-Panel
  reagiert kein Klick (Hunt-Klick auf Station, Antwort-Button). In
  ForkLift kein Doppelklick zum Datei-Oeffnen. Zuhause direkt am Mac
  geht alles. → Splashtop-Client-Side-Problem auf Linux Mint, NICHT
  SimpleFT8-Bug.
- **Versuche bisher:** HID-File `/Users/Shared/SplashtopStreamer/
  com.splashtop.input.hid` Anlegen scheiterte (Permission denied,
  sudo nicht moeglich aus Claude-Sitzung).
- **Naechste Schritte:** Linux-Mint-Side: Doppelklick-Timeout in
  System-Settings auf 800ms hochsetzen, anderen Browser/Splashtop-
  Client probieren. Mac-Side: HID-File anlegen wenn Mike das selber
  via Terminal-sudo machen kann.

### 🟡 Memory-Wachstum 32 GB (NEU 2026-05-08, Diagnose laufend)
- **Symptom:** Alte App PID 31564 (v0.95.20) hatte nach ~40 Min
  Laufzeit 32 GB RSS gefressen. vmmap zeigte: 4.2M Allocations,
  96 % Heap-Fragmentation, MALLOC_SMALL (empty) 30.7 GB resident,
  Physical-Footprint-Peak 109.3 GB. KEIN klassischer Leak im Code,
  sondern **chronische Heap-Fragmentation**.
- **Aktueller Stand:** Neu gestartete v0.95.21 PID 39362 stabilisiert
  bei ~670 MB nach 38 Min — **Faktor 50× besser**. Memory-Watcher
  laeuft im Hintergrund (`/tmp/simpleft8_memwatch/memwatch_*.csv`),
  loggt alle 60 s RSS/CPU + alle 5 Min vmmap-Detail.
- **Vermutete Ursache:** ueber Stunden akkumulierte Allocations
  (Decoder-Pipeline ~1700/s) ohne Object-Pools. Kein klarer Trigger.
- **Naechste Schritte:** App 1-2 h aktiv nutzen lassen (sobald
  Splashtop-Klick wieder geht), Wachstumskurve auswerten. Wenn
  > 5 GB → V1→V2→R1→V3 fuer Object-Pool oder periodischer
  `gc.collect()`-Timer. Wenn stabil < 2 GB → kein Bug.

### Field-Test v0.95.22 P1.OMNI-START + Push-Freigabe (NEU 2026-05-08)
- [ ] **Mike-Field-Test (V3 §6, 7+1 Punkte):** Diversity, Easter-Egg an,
      btn_omni_cq sichtbar; Klick → CQ sofort auf Even, Statusbar
      `Ω Even=1 Odd=0`; naechster Slot Odd, dann 3 RX, Block-Wechsel
      nach 80; CQ-Reply → QSO normal → nach RR73 OMNI-Resume; Toggle
      off → CQ stoppt; HALT mit OMNI → alles gestoppt, Button
      entriegelt; Bandwechsel → OMNI stoppt automatisch; OMNI waehrend
      WAIT_REPORT → blockiert + Statusbar 4 s.
- [ ] Bei OK: Push-Bundle v0.95.16-22 + P2-Tool + P3 zusammen.

### Field-Test v0.95.15 P1.QRZ-UPLOAD-UI-2 + Push-Freigabe
- [ ] Mike testet im Feld: Title-Update, Statusbar-Cancel, File-Move,
      JSONL-Log, Rate-Limit-Cooldown, App-Close waehrend Cooldown
- [ ] Bei OK: Mike-Freigabe einholen → `git push origin main`
      (Commits `d8f86b6` Code+Tests + `d313b1a` Doku + `f456d04` TODO)

### P2.ADIF-ARCHIVE — Standalone Helper-Script (✅ ERLEDIGT 08.05.)
- [x] `tools/adif_archive.py` geschrieben — konsolidiert Tagesdateien aus
      `adif/hochgeladen/` in Jahresarchive `adif/archiv/YYYY.adi`.
      Voller V1→V2(15 Lessons)→R1(1 KRITISCH + 2 WICHTIG)→V3→Compact→
      Code→Final-R1(0 KP). Tests 955 → 978 gruen (+23). Tool-only,
      kein APP_VERSION-Bump. Hardware-frei testbar via `--dry-run`.

---

## ✅ P1-Bugs ERLEDIGT (08.05.2026 v0.95.18+19)

- [x] **P1.7** ✅ — Lokaler Duplikat-Filter ADIF/Logbuch (v0.95.19 Bundle2)
- [x] **P1.8** ✅ — Report-SNR-Bug `_last_snr` statt `msg.snr` (v0.95.18 Bug-C)
- [x] **P1.11** ✅ — `wait_73_retries` von `rr73_retries` entkoppelt (v0.95.19 Bundle2)
- [x] **P1.13** ✅ — TX-Frequenz-Spinbox-Sync im Normal-Modus (v0.95.19 Bundle2)

---

## 🛠 OFFEN — Quality-of-Life (alte TODOs, weiterhin gueltig)

- [ ] Even/Odd dedizierter Timer — unabhaengig vom Decoder-Thread (FT2 kritisch)
- [ ] Gain-Bias beheben — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
- [x] **CQ-Zusammenfassung Dead-Code raus** (08.05.2026): _cq_count und
      _cq_flash_timer-Reste in qso_panel.py + mw_qso.py entfernt. User-
      sichtbare Zusammenfassung war schon weg (HISTORY:2378), nur 4 Zeilen
      Backwards-compat noch vorhanden. Keine Verhaltens-Aenderung.
- [ ] Tertile-Analyse Statistik — kein Datencropping, alle Werte in 3 Drittel
<!-- VERWORFEN 07.05.2026 (Mike-Entscheidung):
     Per-Station DT-Offset TX hat keinen Nutzwert. Globaler -0.8s Offset
     reicht (FT8-Decoder-Toleranz ±2.5s). Per-Station-Offset wuerde
     symmetrische HW-Drift voraussetzen — falsche Pramisse, Risiko >
     Nutzen. -->

- [ ] IC-7300 Fork — TARGET_TX_OFFSET dort separat messen (eigener Branch)
- [x] **F) Audio-Export per Slot** ✅ ERLEDIGT 08.05.2026 (v0.95.20
      P3.AUDIO-DUMP-DEBUG): Toggle in Settings „Daten & Tools" Block 4
      + Spinbox Max-Files (50-1000, Default 200, FIFO-Cleanup). NUR FT8.
      `audio_dump/{band}_FT8/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`. Architektur
      Pull-Pattern (R1-KRITISCH adressiert). Tests 978 → 992. Field-Test
      ausstehend.
- [ ] TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker
      (NEU 26.04., noch nicht reproduzierbar)

---

## 🗺 OFFEN — Karten-Folgemassnahmen (v0.66)

- [ ] Migration `main_window._psk_worker` → `core/psk_reporter`
- [ ] Karten-Live-Test im Feld (40m FT8 abends mit RX-Layer)
- [ ] TX-Modus Live-Test (CQ rufen + TX-Toggle, schauen ob Marker erscheint)
- [x] Mobile-Filter-Edge-Case dokumentieren (08.05.2026): bereits in
      `core/direction_pattern.py:65-72` als Code-Kommentar — Region-Calls
      wie `K1ABC/W2` werden bewusst rausgefiltert (akzeptabel laut Doku).

---

## 📊 OFFEN — Statistik & Analyse (Prio NIEDRIG)

- [ ] Diagramm-Auswertung 20m fuer GitHub (wenn genug Daten)
- [ ] ANT1 vs ANT2 SNR direkt loggen (ant1_snr, ant2_snr, delta pro Station)
- [ ] Statistik-Diagramme fuer GitHub (matplotlib aus statistics/*.md)
- [ ] Auswertung per Tertile-Analyse (Entscheidung final, kein Datencropping)
- [ ] RX-Liste: Spalten-Konfig in Settings (RX-Spalten ein/ausblendbar
      + gespeichert, Slot/Ant/DT/etc.)
- [ ] CQ-Zusammenfassung im RX-Panel ueberarbeiten (aktuell „CQ ×N" kaum sichtbar)

---

## ✅ ERLEDIGT (Aufraeum-Snapshot 07.05.2026)

- B) Band-Indikatoren live mit PSK-Reporter ✅ — v0.69 deckt Use-Case ab
- C) Richtungs-Keulen TX-Pattern-Karte ✅ — v0.66
- D) Richtungs-Keulen ANT2 RX-Rescue ✅ — v0.66
- E) CSV-Export Diversity-Daten ✅ — v0.65
- AP-Lite Test-Pipeline ✅ — v0.95.9 (P1.AP) + v0.95.10 (P1.AP-FIX)
- DT-Drift Wurzel-Fix ✅ — v0.95.7 (P1.18, `_DT_OFFSETS["FT8"]=3.0`)
- Warteliste-Screenshot ✅ — DL3AQJ-Freigabe + Einbau erledigt

---

## 🗂 ARCHIV (chronologisch, ERLEDIGTE Punkte aus alten Sessions unten)

---

## ✅ P1.24 (06.05.2026 v0.95.9) — ERLEDIGT (Field-Test bestaetigt)

**Folge-Fix zu P1.14:** TX-Klick wurde komplett ignoriert wenn
`encoder.is_transmitting=True` (während CQ-TX oder Hunt-TX_CALL). Mike
musste HALT druecken um Station-Wechsel zu erzwingen.

**Fix:** Buffer-Logik. Klick waehrend TX → State-Cleanup (stop_cq oder
cancel) sofort + Buffer + Statusbar; nach TX-Ende rekursiv neu triggern.
Aktueller TX-Slot laeuft durch, im naechsten Slot wird Station angerufen.

Code: `ui/main_window.py` (1 Attribut), `ui/mw_qso.py` (3 Stellen).
Tests 812 → 816 gruen (+4 in `tests/test_p1_24_pending_click.py`).

---

## ✅ P1.14 + P1.23 (06.05.2026 v0.95.8) — ERLEDIGT (Field-Test bestaetigt)

**P1.14 Station-Wechsel-Bug** (voller Workflow V1→V2→R1→V3 Diagnose +
Plan-V1→V2→R1→V3): 6 Bug-Wurzeln W1-W6 gefixt:
- W1: `start_qso` resetete keine Pendings bei `state != IDLE`
- W2: `_caller_queue` enthielt manuell-gewaehlte Station (Doppel-QSO)
- W3: `_active_qso_targets` wuchs monoton bei Wechseln
- W4/KP6: `_was_cq` State-Machine-extern korrigiert (BEHALTEN)
- W5: TX-Klick silent ignoriert (Statusbar-Toast 3s)
- W6: `auto_hunt._manual_override` wurde NIE zurueckgesetzt
  (Fix in `_on_cancel`, `_on_qso_confirmed`, `_on_qso_timeout`)

Tests 802 → 812 gruen (+10 in `tests/test_p1_14_station_switch.py`).

**P1.23 Status-UI:** Label „Lokale Empfangsqualitaet:" (statt „Lokaler
Empfang:"), Schriftgroessen 11→10px, Sterne 15→13px.

---

## ✅ P1.18 + P1.21 (06.05.2026 v0.95.7) — ERLEDIGT

**P1.18 DT-Drift-Wurzel:** `_DT_OFFSETS["FT8"]` 2.0 → 3.0 (Sync mit
`_WAKE_OFFSETS["FT8"]=2.5` + 0.5s WSJT-X-Protokoll). `dt_corrections.json`
reset. Erwartung: DT zurueck auf -0.1 bis +0.2 wie 23.04.

**P1.21 Sterne-UX-Refactor:** Label `Empfang:`, Gold #FFD700 statt Cyan,
RichText fuer enge Sterne, Score nur SNR (-10/-14/-18/-22 dB).
Mike-Szenario 48×-25 dB jetzt 1 Stern (war 5).

**Field-Test (Mike) ausstehend:**
- DT-Korrektur konvergiert auf ~0.24s (`dt_corrections.json` zeigt klein,
  nicht 1.0)
- Stationen zeigen DT -0.1 bis +0.2
- Sterne reagieren auf Conditions (bei -25 dB sollten 1-2 Sterne sein)
- Sterne-Optik passt zum STATUS-Block (Gold, eng zusammen)

---

## ✅ P1-Bundle1 (06.05.2026 v0.95.6) — ERLEDIGT

5 UI-Cleanups thematisch gebuendelt + voller Diagnose-Workflow + Plan-Workflow.
Tests 777 → 796 gruen (+19). Field-Test ausstehend.

- ✅ **P1.6** Versionsnummer Color #333 → #666
- ✅ **P1.12** NEU-Button (`btn_remeasure`) entfernt (6 Stellen)
- ✅ **P1.15** Statusbar `→ Call | RX: ANT` raus
- ✅ **P1.16** QSO-Panel zeitbasiertes 5-Min-Rolling-Window (statt 40 Zeilen)
- ✅ **P1.19** 5-Sterne-Anzeige `★★★☆☆` ersetzt SNR-Label

**Field-Test (Mike) noch offen:**
- App startet ohne Fehler, Versionsnummer rechts unten lesbar
- KALIBRIEREN funktioniert weiter (statt NEU)
- Bei aktivem QSO: keine `→ Call`-Anzeige
- Nach 5+ Min Funken: alte QSO-Eintraege weg
- Sterne reagieren auf Conditions (sollten zwischen 2-4 schwanken)

---

## ⭐ ALS NÄCHSTES (Priorität)

### ✅ P1.8 — Report-SNR-Bug `_last_snr` statt `msg.snr` (ERLEDIGT 2026-05-08, v0.95.18 + v0.95.21)

Wir sendeten Reports mit schlechteren dB-Werten als wir empfangen.
`_last_snr` wurde fuer jede msg im Slot ueberschrieben → letzte/schwaechste
msg-SNR gewann. v0.95.18 fixte `_process_cq_reply` (qso_state.py:214,229).
**v0.95.21 P1.HUNT-SNR** fixte den Hunt-Pfad: `start_qso(their_snr)` +
Aufrufer (mw_qso, mw_cycle) reichen `msg.snr`/`_candidate.snr` durch.
Plus `advance()` WAIT_REPORT-Branch nutzt `qso.our_snr` (R1-SOLLTE).

### 🟡 P1.11 — `rr73_retries`-Counter shared

Bestehender Bug, NICHT durch P1.10 verschaerft. `qso.rr73_retries` wird
in WAIT_RR73 UND WAIT_73-Hoeflichkeits-Pfad inkrementiert/getestet.
Fix: separates Feld `wait_73_retries` oder Reset bei WAIT_73-Eintritt.

### 🟡 P1.13 — TX-Frequenz-Spinbox-Sync Normal-Modus

Spinbox spiegelt Klick-Frequenz nicht immer korrekt (alt aus 05.05.).

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch

Folgebug-Risiko aus P1.5: bekannte Station < 5 Min nach RR73 ruft erneut →
zweites QSO + zweiter ADIF-Eintrag. QRZ.com filtert serverseitig, aber
lokal nicht.

### ✅ P1.CACHE-SIMPLE — Diversity/Gain entkoppelt + UX-Cleanup (ERLEDIGT 2026-05-07 v0.95.13)

Mike-Vision: Diversity-Cache (Ratio, 60 Min) und Gain-Cache (6h)
komplett entkoppelt. Keine Modal-Wahl-Dialoge fuer Routine.

**4 Probleme gefixed:**
- A) Cache-Reuse-Toast raus (Mike: „Computer faehrt runter — OK?"-Pattern)
- B) Modal-Wahl-Dialog „Weiter / Neu messen" raus an 2 Stellen
- C) Frische Ratio mit altem Gain ignoriert (Cross-Dependency-Bug)
- D) Volle Pipeline ohne Ankuendigung — jetzt Stale-Acceptance bei Cancel

**Architektur (`_check_diversity_preset` Dispatch):**
- Gain stale → DXTuneDialog auto-start (nur Abbruch). Wenn Ratio fresh:
  nach Gain-OK Cache-Reuse statt Phase 3.
- Gain missing → volle Pipeline (Gain + Ratio).
- Gain fresh + Ratio fresh → Cache-Reuse (still, kein Toast).
- Gain fresh + Ratio stale/missing → stille Auto-Ratio-Messung.

Plus Stale-Acceptance bei `_on_dx_tune_rejected`-Cancel: alte Werte
werden geladen statt Pipeline-Restart. Wenn nichts da: Diversity AUS.

**Voller Workflow:** V1 (4 Probleme) → V2 (12 Lessons) → R1 (8 Pruefauf-
traege beantwortet, kein Veto) → V3 (Compact-fest, 6 Diffs konkret) →
Compact → Code → Final-R1 („Keine KP-Findings, Code ist robust und
entspricht der Mike-Vision. ✅"). Plan-Files: `prompts/p1_cache_simple_v[1-3].md`.

**Tests 852 → 862 gruen** (+10 NEU in `tests/test_p1_cache_simple.py` +
1 invertiert in `test_diversity_cache_reuse.py`). Atomare Commits
`4af2e9e` (Code+Tests, 5 Files +508/-277) + Doku-Commit. APP_VERSION
0.95.12 → 0.95.13.

**Field-Test ausstehend.** Push noch nicht gemacht — Mike-Freigabe
einholen.

### ✅ P1.FORCESEND — btn_advance state-aware + WAIT_73-Branch (ERLEDIGT 2026-05-07 v0.95.12)

Mike-Use-Case 06.05.: bei stuck-Gegenstation manuell RR73 oder 73
senden statt 3-Min-Timeout. Bestehender `btn_advance` wird state-aware:
Label dynamisch (`R+Report` / `RR73` / `73` / `Weiter →`), Enabled in
{WAIT_REPORT, WAIT_RR73, WAIT_73} AND nicht cq_mode AND nicht
diversity_locked. `advance()` neuer WAIT_73-Branch sendet 73 mit
`courtesy_73_sent=True` VOR send (R1-KP-3 asynchron) + idempotent-
Return wenn Auto-Pfad schneller war (Final-R1 Race-Fix).

**Voller Workflow:** V1 → V2 (10 Lessons, Bug-A-Halluzination
eingestanden) → R1 („Plan freigegeben + 5 KP", KP-1 als Halluzination
verworfen) → V3 (Compact-feste Diffs) → Code → Final-R1 („Push
freigegeben mit Vorbehalt: idempotent-Return" → sofort umgesetzt).
Plan-Files: `prompts/p1_forcesend_v[1-3].md`.

**Tests 841 → 852 gruen** (+11 in `tests/test_p1_forcesend.py`).
Atomare Commits `c8bf5bb` (Code+Tests+main.py 5 Files +177/-2) +
Doku-Commit. APP_VERSION 0.95.11 → 0.95.12.

**Lesson:** V1-Halluzination-Risk auch nach 2 Jahren — grep zu eng,
`_on_state_changed`-Hook in mw_qso.py übersehen. V2-Self-Review fing
es ab.

---

### ✅ P1.ANTENNE-COLLAPSE — Antennen-Kachel einklappbar (ERLEDIGT 2026-05-06 v0.95.11)

Mike-Designentscheidung 06.05.: `_AntenneCard` (`ui/control_panel.py:421`)
WIRD einklappbar. DeepSeek hatte abgeraten — Mike überschrieb explizit
(SimpleFT8 ist Hobby-Tool, kein Contest). Hobby-Use-Case: stundenlang
auf einem Band+Modus, Antennen-Status selten gebraucht → wegklappen,
Platz für QSO/RX-Panel. Bei Bedarf aufklappen.

**Architektur:** Header-Row mit Toggle-Button `▼`/`▶` + `_body_widget`-
Container für alle bisherigen Body-Widgets. API `set_collapsed(bool)` /
`is_collapsed()` / `_toggle_collapsed()`. Signal `collapse_changed` NUR
bei User-Klick (Init-Loop-Schutz). `ControlPanel._ant_card` exposed,
forwardet via `antenne_collapse_changed.emit`. `MainWindow` lädt
Initial-State aus Settings + persistiert via Slot.

**Voller Workflow:** V1 → V2 (16 Lessons) → R1 („Plan freigegeben +
5 KP", neue Befunde KP-7 bis KP-11) → V3 (Compact-feste Diffs) → Code →
Final-R1 („Push freigegeben mit optionalem Debounce-Vorbehalt").
Plan-Files: `prompts/p1_antenne_collapse_v[1-3].md`.

**Tests 831 → 841 gruen** (+10 in `tests/test_antenne_card.py`). Atomare
Commits `a0ce1ae` (Code+Tests+main.py 4 Files +209/-9) + Doku-Commit.
APP_VERSION 0.95.10 → 0.95.11.

**Settings-Key:** `antenne_card_collapsed` (bool, default False = aufgeklappt).

---

### ✅ P1.AP-FIX — AP-Lite Kandidaten-Format-Bug (ERLEDIGT 2026-05-06 v0.95.10)

`core/ap_lite.py:126` produzierte 4-Token-Strings (`OWN THEIR LOC SNR`).
FT8 erlaubt nur 3 Tokens → ft8lib `rc=5` → State-1-Rescue scheiterte
IMMER silent seit Implementierung.

**Fix (1 Zeile, KISS):** Locator weglassen, Report-only:
```python
candidates.append(f"{own_callsign} {their_callsign} {r:+03d}")
```
Plus Code-Kommentar Z.121-131 fachlich aktualisiert.

**Voller Workflow:** V1→V2(9 Lessons)→R1("Plan freigegeben")→V3(5
Compact-feste Diffs)→Compact→Code→Final-R1("Push freigegeben").
Plan-Files: `prompts/p1_ap_fix_v[1-3].md`.

**Tests 830 → 831 gruen** (+1 ft8lib_compatible als maschineller
Format-Schutz). Atomare Commits `17b7237` (Code+Tests+main.py) +
Doku-Commit. APP_VERSION 0.95.9 → 0.95.10.

**Field-Test:** post-Kur. Erwartung Rescue-Rate steigt. Notbremse
`AP_LITE_ENABLED=False`.

---

### ✅ P1.AP — AP-Lite synthetische E2E Test-Pipeline (ERLEDIGT 2026-05-06 v0.95.9)

`tests/test_ap_lite_e2e.py` NEU — 14 Tests mit echtem ft8lib-Encoding +
Gaussian-Rauschen. Decken correlate_candidate (clean/noisy/wrong/unrelated),
align_buffers (dt/shape/range), try_rescue E2E (-30dB fail, State-2-Ranking,
APLiteResult), Stats-Counter ab. Tests 816 → 830 gruen.

**Findings dokumentiert:**
- AP-Lite State-1-Generator ist kaputt (4-Token-Bug → P1.AP-FIX)
- Costas-Referenz-Implementation findet auch identische Buffer mit Offset
  (vereinfachte Naeherung, Code-TODO-Kommentar bestaetigt)
- SCORE_THRESHOLD=0.75 wird auch von sauberen RR73-Buffern nicht erreicht
  (~0.42), aber Ranking-Logik funktioniert

---

### ✅ P1.20 — Workflow-Template institutionalisieren (ERLEDIGT 2026-05-06 v0.95.9)

Skill `.claude/skills/ft8_workflow.md` mit explizitem Trigger-Block
erweitert (Mike-Phrasen + Auto-Trigger + Trivial-Klausel). Slash-Command
`.claude/commands/workflow.md` angelegt → `/workflow [bug-name]` startet
Skill direkt. CLAUDE.md beide Pfade verweisen auf Triggers + Slash-Command.

### ✅ P1.17 — RX-SNR-Bias (ERLEDIGT 2026-05-06 v0.95.9)

War Folge von P1.18 DT-Drift. Mike Field-Test bestaetigt: DT bei 0,26s,
SNR-Werte normal, alles gruen.

### ✅ P1.18 / P1.14 / P1.21 — alle ERLEDIGT (v0.95.7-9, Field-Test bestaetigt)

Mike 2026-05-06: „Sterne reagieren, DT-Zeit-Korrektur bei 0,26 Sekunden,
alles gruen, erledigt."

---

## 🗂 ALTE TODO-Eintraege (vor Bundle1 — zu konsolidieren)

### 🟢 P1.12 — NEU-Button im Diversity-Panel entfernen (NEU 2026-05-05)

KALIBRIEREN-Button macht seit v0.94 Phase 2 (Gain) + Phase 3 (Diversity)
automatisch. Der NEU-Button (`btn_remeasure` in `ui/control_panel.py:516`)
ist redundant — er macht nur Phase 3 alleine, was im Hobby-Funker-Alltag
selten gebraucht wird.

**Aufgabe:**
- `ui/control_panel.py:516-525` — `btn_remeasure` löschen
- `ui/control_panel.py:1023-1024` — `remeasure_clicked` Signal-Connect raus
- `ui/main_window.py:530` — Connect zu `_on_diversity_remeasure` raus
- `ui/mw_radio.py:985-997` — `_on_diversity_remeasure` Methode löschen

**Aufwand:** ~10 Zeilen, KISS, kein Workflow nötig.

---

### 🔴 P1.14 — Station-Wechsel via Klick funktioniert nicht (NEU 2026-05-06)

**Symptom (Field-Test Mike, 22:01 + 22:09 UTC):**

Mehrere kaputte Pfade — gemeinsame Wurzel: Klick auf neue Station im
RX-Panel waehrend aktiver TX bricht den laufenden TX nicht ab.

**Pfad 1 — nach Hunt-Timeout:**
- Hunt UN0GY 6× ohne Antwort → `× UN0GY — Timeout`
- Doppelklick MM8FKF (RX-Panel-Markierung) → **NICHTS**
- App sendet weiter CQ statt MM8FKF zu rufen

**Pfad 2 — waehrend laufendem CQ-Modus:**
- CQ_CALLING aktiv (CQ DA1MHH JO31)
- Doppelklick auf andere CQ-rufende Station → **NICHTS**
- Mike muss erst manuell HALT druecken, dann Station anwaehlen

**Pfad 3 — waehrend laufendem Hunt:**
- TX_CALL / WAIT_REPORT aktiv mit Station A
- Mike entscheidet sich um, klickt Station B → **NICHTS**

**Erwartetes Verhalten in ALLEN Pfaden:**
- Klick auf neue Station bricht aktuellen Zustand sauber ab
- (CQ-Modus / Hunt-QSO / Timeout)
- Bei naechstem TX-Slot wird neue Station angerufen

**Code-Pfad zu pruefen:**
- `ui/mw_qso.py:_on_station_clicked` (Z.65+) — hat zwar
  `_cq_was_active`-Logik aber Hunt-Abbruch fehlt
- `core/qso_state.py:start_qso` (Z.236+) — `state not in (IDLE, CQ_WAIT)`
  Branch wird vermutlich gar nicht erreicht
- RX-Panel Click-Handler — wird Doppelklick im aktiven QSO ueberhaupt
  weitergegeben?

**Diagnose-Schritt 1:** Logging hinzufuegen in `_on_station_clicked`
Eingang + RX-Panel-Click-Emit. Pruefen ob Event ueberhaupt durchkommt.

**Workflow:** voller V1→V2→R1→V3 — beruehrt State-Machine + UI-Click-
Handling + Encoder-Abort, mehrere Akzeptanzkriterien.

---

### 🔴 P1.18 — DT-Korrektur konvergiert nicht (Wurzel-Bug, 2026-05-06)

**Wurzel:** `core/ntp_time.py:36` `_MAX_CORR["FT8"] = 1.0` — Limit
zu eng. Mike's FlexRadio + Hardware-Setup braucht **+1.2s** Korrektur,
clamp in Z.213 reduziert auf 1.0s → DT-Korrektur „stuck" bei 1.0s.

**Beweis im Log:**
```
Feinkorrektur: Median=+0.240s ×0.7 → Δ+0.168s → Korrektur=+1.168s
Neue Messphase (Korrektur=+1.000s)  ← clamped!
Feinkorrektur: ... → Korrektur=+1.220s
Neue Messphase (Korrektur=+1.000s)  ← clamped!
```

Jede Feinkorrektur erreicht ~+1.18-1.22s, wird auf +1.000s zurueck-
geclampt. **Konvergenz unmoeglich.**

**Konsequenz — vermutlich Wurzel von P1.17 + P1.8:**
- DT-Korrektur 200ms zu klein
- Decoder samplet mit 200ms Versatz
- FT8-Decoder hochempfindlich auf Timing → alle SNR-Werte mehrere
  dB reduziert → P1.17 (alle Stationen -17 bis -25)
- Reports an Gegenstationen ebenfalls pessimistisch → P1.8

**Fix (1 Zeile):**
```python
_MAX_CORR = {"FT8": 2.0, "FT4": 1.0, "FT2": 0.5}
```

oder `_MAX_CORR["FT8"] = MAX_CORRECTION` (= 2.0, schon definiert Z.31).

**Plus:** `~/.simpleft8/dt_corrections.json` zuruecksetzen (alle Werte
1.0 sind clamped, neu konvergieren lassen).

**Aufwand:** 5 Min Code + Field-Test + Vergleich der SNR-Werte vorher/
nachher. Falls SNR um >3 dB besser → P1.17 + P1.8 gleich miterledigt.

**Workflow:** voller V1→V2→R1→V3 — kritischer Wurzel-Fix mit weit-
reichenden Konsequenzen, mehrere Akzeptanzkriterien (SNR-Verbesserung,
DT-Konvergenz, RX-Panel sauber).

---

### 🟡 P1.17 — RX-SNR-Bias verdaechtig (alle Stationen -17 bis -25 dB) (NEU 2026-05-06)
**Vermutlich GELOEST durch P1.18 — Field-Test nach P1.18-Fix.**

**Symptom (Field-Test Mike 22:09 UTC):**
22 Stationen im RX-Panel, ALLE zwischen -17 und -25 dB. Selbst nahe
Stationen schwach:
- England 415km → -21
- England 630km → -23
- Polen 846km → -18
- Bulgarien 1700km → -17

Erwartung 40m FT8 Abend: Mix aus -5 (gut) bis -24 (Decode-Schwelle).
Komplettes Fehlen besserer Werte ist verdaechtig.

**Mike's Argument:** externe Software-Vergleich (SDR-Control / IC-7300)
nicht moeglich weil andere SNR-Berechnung. Wir muessen selbst pruefen.

**Mike's Trost:** falls systematischer Bias vorliegt — **Diagramme
(Diversity vs Normal) bleiben aussagekraeftig** weil RELATIVE Vergleiche.
Aber: ABSOLUTE Werte (gemeldete Reports an Gegenstationen, Reichweite-
Stats) sind dann verfaelscht.

**Diagnose-Optionen:**

1. **PSK-Reporter-Asymmetrie:** App empfaengt PSK-Reporter-Daten
   (was andere fuer DA1MHH reporten). Vergleichen mit unseren RX-Werten
   fuer dieselben Stationen. Wenn andere uns mit -10 hoeren und wir
   sie mit -22 → asymmetrischer RX-Bias.
2. **AGC-Pegel im Log pruefen:** RMS-Ziel ist -12 dBFS. Wenn AGC
   saturiert (zu viel Verstaerkung) wird Signal vorm Decoder platt.
3. **Decoder-SNR-Berechnung Code-Review:** wo wird `msg.snr` berechnet?
   ft8lib oder eigener Code? Gibt es einen Offset der subtrahiert wird?
4. **Vergleich Diversity ANT2 (Regenrinne):** ANT2 ist viel schwaecher
   als ANT1, sollte 10-15 dB schlechter sein. Wenn ANT1 und ANT2
   aehnliche Werte zeigen → Verstaerker-/AGC-Bug.

**Auswirkung wenn Bug:**
- Reports an Gegenstationen 5-10 dB zu pessimistisch
- Reichweite-Statistiken systematisch zu niedrig
- Diversity-Vergleich bleibt valide (relativ)

**Aufwand:** Diagnose 1-2h. Falls Bug bestaetigt: Fix je nach Wurzel.

---

### 🟢 P1.20 — Workflow-Template als Standard-Pattern in Skill (NEU 2026-05-06)

**Idee Mike:** der heutige Bundle1-Workflow war besonders sauber. Das
konkrete Template als Standard-Pattern in `.claude/skills/ft8_workflow.md`
festhalten damit Claude immer gleich-strukturiert vorgeht.

**Was heute gut war (zu institutionalisieren):**

1. **Compact-Strategie:** nach V2, vor R1 — Token-effizient + Persistenz
2. **V1 = Code-Verifikation FIRST:** alle Datei:Zeile-Refs **bevor**
   Diagnose geschrieben wird (verhindert Spekulation)
3. **V2 = Tabelle der V1-Luecken:** explizit dokumentiert was V1 verpasst,
   nicht nur „erweitert"
4. **R1-Pruefauftraege konkret:** mit Nummerierung 6.1, 6.2 etc., nicht
   „schau mal drueber"
5. **Bundle-Strategie:** mehrere kleine Fixes als gemeinsamer Workflow
   wenn thematisch zusammenhaengend (z.B. UI-Cleanup)
6. **Pre-Compact-Check als eigener Task:** Files-Liste verifizieren,
   nichts darf verloren gehen
7. **Akzeptanzkriterien getrennt:** Code-Akzeptanz vs Field-Test als
   zwei Listen
8. **Workflow-Plan numeriert** mit Status-Markern (✅/→/Mike-Freigabe)

**Aufgabe:**
- `.claude/skills/ft8_workflow.md` erweitern um „Workflow-Template"-Sektion
- Bundle1 + P1.10 als Beispiele referenzieren
- Klare Vorgabe: V1 IMMER mit Code-Verifikation, V2 IMMER mit Luecken-
  Tabelle, R1 IMMER mit nummerierten Pruefauftraegen
- Compact-Trigger-Punkt explizit benennen
- Bundle-Kriterium: wann sammeln, wann separat?

**Trigger:** Nach Bundle1-Abschluss (heute Nacht oder morgen) — dann
haben wir 2 vollstaendige Workflow-Beispiele zum Destillieren.

**Aufwand:** 30 Min Skill-Erweiterung, KISS, kein eigener Workflow.

---

### 🟢 P1.19 — Lokale Conditions als Sterne-Anzeige (NEU 2026-05-06)

**Idee Mike:** SNR-Wert „-25 dB" im Status ist fuer User nicht intuitiv —
auch Mike kann nach 4 Wochen nicht spontan einordnen. Ersetzen durch
**5-Sterne-Anzeige** „Lokale Conditions" mit dunkler Outline fuer
inaktive Sterne (sichtbare Skala).

**Wichtige Abgrenzung:**
- **Bandanzeige oben (gruen/gelb/rot):** GLOBAL aus PSK-Reporter
- **Lokale Conditions (NEU):** was DU gerade empfaengst (Antenne, lokales
  Rauschen, lokale Tageszeit-Skip)
- Beide ergaenzen sich (Band gruen + lokal rot = Hardware-Problem!)

**Berechnung (KISS, 2 Faktoren):**

| Sterne | Stationen (Aging-Fenster) | Median-SNR der besten Haelfte |
|---|---|---|
| ★★★★★ | 25+ | > -12 dB |
| ★★★★☆ | 15-24 | > -15 dB |
| ★★★☆☆ | 8-14 | > -18 dB |
| ★★☆☆☆ | 3-7 | > -22 dB |
| ★☆☆☆☆ | < 3 | egal (Antenne checken) |

Schwellen werden ODER-verknuepft (eines reicht zum Hochstufen).

**UI:**
- Aktive Sterne: Neon-Cyan (#00DDFF) mit weichem Glow (passt zum Theme)
- Inaktive Sterne: dunkle Outline (#3a3a4e) — sichtbar, klare Skala
- Tooltip beim Hover: „12 Stationen, Median -16 dB"
- Position: ersetzt aktuellen `SNR: -25 dB` Eintrag im Status-Block

**Intern:** SNR-Wert weiter berechnen (Reports, DT-Korrektur, Statistik)
— nur die UI-Anzeige aendert sich.

**Wichtige Reihenfolge:** **erst P1.18 fixen** (DT-Clamp). Sonst zeigt
die Sterne-Skala mit dem aktuellen Bias systematisch zu schlechte
Werte.

**Aufwand:** ~30 Min Implementation (Berechnungs-Funktion + UI-Widget +
Theme-Styling). Voller Workflow nicht zwingend — KISS-Feature, lokal.

---

### 🟢 P1.16 — QSO-Panel-Log: 5-Min-Rolling-Window (NEU 2026-05-06)

**Symptom:** QSO-Panel-Log fuellt sich Eintrag fuer Eintrag, nach laengerer
Session unleserlich/zugemuellt. Mike's Beobachtung 22:07 UTC: 9 Minuten
Verlauf sichtbar, aelter Material ist nicht mehr relevant.

**Mike's Idee (KISS):** alle Eintraege aelter als 5 Min automatisch oben
loeschen. Juengere Eintraege ruetschen nach oben. So bleibt der Last-5-Min-
Verlauf immer sichtbar, ohne manuelles Aufraeumen.

**Code-Pfad:** `ui/qso_panel.py` — alle `add_info` / `add_rx` / `add_tx` /
`add_qso_complete` / Trenn-Linien zu Eintraegen mit Timestamp speichern.
Periodisch (z.B. via QTimer alle 30s ODER bei jedem `add_*`) Eintraege
mit `now - timestamp > 300s` entfernen.

**Edge Cases:**
- Trenn-Linien („─────"): nicht standalone loeschen, sondern mit
  zugehoerigem QSO-Block
- „CQ-Modus laeuft weiter..." sollte erhalten bleiben wenn QSO im
  Window ist
- Scroll-Position: User-Scroll respektieren (kein Auto-Reset bei Cleanup)

**Aufwand:** ~30 Zeilen, moderates Refactoring (zentrale add-Funktion +
Timestamp-Tracking + Cleanup-Timer). Voller V1→V2→R1→V3 nicht zwingend
(lokal in qso_panel.py, single Akzeptanzkriterium), aber Edge-Cases
brauchen Sorgfalt.

---

### 🟢 P1.15 — Statusbar-Anzeige „→ Call | RX: ANT" entfernen (NEU 2026-05-06)

Mike: *„die macht mich irre"*. Statusbar-Eintrag unten links zeigt
`→ SP5LST | RX: ANT1` — wird nicht gebraucht, soll komplett weg.

**Code-Pfad:** `ui/main_window.py` Statusbar-Update — Mike's Active-QSO-
Anzeige in Statusbar. Wahrscheinlich `_update_statusbar()` oder
`statusBar().showMessage()`.

**Aufwand:** ~5 Zeilen, KISS, kein Workflow.

---

### 🟡 P1.13 — TX-Frequenz-Spinbox-Sync im Normal-Modus (NEU 2026-05-05)

**Symptom:** Wenn User im Normal-Modus auf eine Station klickt (Hunt),
wird `encoder.audio_freq_hz` auf die Station-Frequenz gesetzt + Histogramm-
Marker (gelb) zeigt korrekt die neue Freq. **Aber die TX-Freq-Spinbox
in der UI zeigt weiterhin den alten manuell gesetzten Wert.**

→ User sieht TX-Freq-Spinbox=1150 Hz, Histogramm-Marker=800 Hz.

Das hatte heute (05.05.) bei der Diagnose des „Frequenz-Wechsel-Bugs"
stundenlang Verwirrung verursacht — der vermeintliche Bug war ein
UI-Sync-Issue zwischen Spinbox und Encoder.

**Code-Pfad:** `ui/mw_qso.py:_on_station_clicked` setzt
`encoder.tx_even` aber NICHT `control_panel._tx_freq_spin.setValue()`.
Ähnlich `_on_send_message` für CQ-Reply-Pfad in Diversity-Modus.

**Fix-Idee (KISS):** in `_on_station_clicked` nach `start_qso` die
Spinbox synchronisieren:
```python
if self._rx_mode == "normal" and msg.freq_hz:
    self.encoder.audio_freq_hz = msg.freq_hz
    spin = self.control_panel._tx_freq_spin
    spin.blockSignals(True)
    spin.setValue(msg.freq_hz)
    spin.blockSignals(False)
```

**Aufwand:** ~15 Zeilen (Hunt-Pfad + CQ-Reply-Pfad). Voller V1→V2→R1→V3
NICHT nötig (single Akzeptanzkriterium, lokaler Patch in einer Methode).

---

### ✅ P1.5 — CQ-Reply-Recognition-Bug (ERLEDIGT 2026-05-05, v0.95.2)

5-Min-Sperre `_WORKED_BLOCK_SECS = 300` an 3 Block-Stellen entfernt.
Voller V1→V2→R1→V3 Diagnose + Plan, R1 zwei Mal bestaetigt ohne
Halluzinationen. Tests 756 → 759 gruen. Atomarer Commit `43dd062`.
Field-Test bestaetigt: 4 QSOs in Folge, Warteliste-Pop ✓. Siehe
`HISTORY.md` v0.95.2.

---

### ✅ P1.9 — First-Reply-Lost-Bug (ERLEDIGT 2026-05-05, v0.95.3)

Decoder-Encoder-Timing-Race behoben. Atomarer Commit `20c7fe7` (Code+Tests,
+282/-29 in 7 Files) + Doku-Commit. Voller V1→V2(12 Findings A-L)→R1(6
Pruefauftraege KORREKT)→V3 Plan-Workflow. Fix-Kombination:
- `core/decoder.py:138` — `_WAKE_OFFSETS["FT8"]` 1.5 → 2.5 (SNR<0.1 dB R1)
- `core/encoder.py` — `request_replace` API + Loop + `tx_finished.emit`
  Encode-Fehler-Pfad (V2 FINDING-F)
- `core/qso_state.py` — Signal `try_replace_pending_tx` + Defense-in-Depth
  in `_send_cq()`
- `ui/mw_qso.py` — `_on_try_replace_pending_tx` Slot (V2 FINDING-A/B/C/D)
- `ui/main_window.py:543` — Connect

Tests 759 → 764 gruen (+5: 3 Encoder API + 2 SM Logik). Siehe HISTORY.md
v0.95.3. **🟡 Field-Test bei Mike ausstehend.**

---

### ✅ P1.10 — End-of-QSO Icom-73-Loop (ERLEDIGT 2026-05-05, v0.95.4)

**Code-Commit:** `9783583` (Code+Tests+Workflow-Files, 13 Files,
+3439/-14) + Doku-Commit.

**Field-Test:** ✅ BESTAETIGT 16:59 UTC mit EA2BHE Spanien (IN83) — nach
unserem Courtesy-73 KEIN weiteres 73 von Gegenstation, Auto-Sequence
sauber gestoppt. IC-7300/DA1TST Test-Setup ist Quirk (enger getakteter
Decoder), kein SimpleFT8-Bug.

**Bug-Wurzel:** IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes
Hoeflichkeits-73 von uns. SimpleFT8 sendete bisher kein Courtesy-73 →
IC-7300 retried 5× `73`. Andere FT8-Apps (WSJT-X, JTDX, MSHV) senden
Courtesy-73 als Funkalltag-Standard.

**Fix:** neuer State `TX_73_COURTESY` + Feld `qso.courtesy_73_sent`
(max 1× pro QSO), Branch in WAIT_73 (`qso_state.py:582-597`) +
on_message_sent + 3-Min-Timeout-Ausschluss + mw_qso state-abhaengig
(Panel-Info nur bei CQ-Reply, NICHT bei Courtesy-73).

**Workflow:** voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3
Diagnose + Cross-Check Zweit-KI + V1→V2(6 Plan-V1-Luecken)→R1(3 wichtige
+ 3 optionale Findings)→V3 Plan. Tests 764 → 777 gruen (+13 neu, 2
angepasst).

---

### 🟡 P1.11 — `rr73_retries`-Counter shared (NEU 2026-05-05, aus Plan-R1 F1)

**Bestehender Bug, NICHT durch P1.10 verschaerft.**

`qso.rr73_retries` wird in WAIT_RR73 (`qso_state.py:346`) UND in
WAIT_73-Hoeflichkeits-Pfad (`qso_state.py:589-590`) inkrementiert/
getestet. Wenn QSO viele WAIT_RR73-Retries hatte (z.B. 2 von 3),
bleibt fuer WAIT_73-R-Report-Hoeflichkeit nichts uebrig.

**Fix-Idee:** separates Feld `wait_73_retries: int = 0` in QSOData
oder Reset bei WAIT_73-Eintritt (`_set_state` Branch).

**Aufwand:** ~1 Stunde, KISS.

**Workflow:** trivialer Bugfix mit klarem Code-Pfad — V1 reicht
laut WORKFLOW.md (single Akzeptanzkriterium).

---

### 🟢 P1.6 — Versionsnummer-Anzeige fehlt (2026-05-05)

Mike sieht `SimpleFT8 v0.95(.1)` unten rechts im Control-Panel nicht mehr.
Code ist unveraendert (`ui/control_panel.py:1086`). Vermutlich Layout-
Glitch, evtl. durch Display-2-Setup oder Resize abgeschnitten.

**Trivial-Diagnose:** Resize-Test, evtl. Layout-Anchoring pruefen.

---

### 🟢 P1.7 — Lokaler Duplikat-Filter ADIF/Logbuch (2026-05-05)

**Hintergrund:** P1.5-Fix entfernt 5-Min-Sperre nach QSO. Bekannte Stationen
duerfen wieder anrufen (Mike's Funker-Entscheidung-Philosophie). Aber:
wenn dieselbe Station < 5 Min nach RR73 nochmal anruft (z.B. ihr 73 ist
nicht angekommen), wuerde ein zweites QSO entstehen → zweiter ADIF-Eintrag
+ zweiter qso_log-Eintrag.

**QRZ.com filtert serverseitig** (Duplikat-Check Call+Band+Mode+Date+Time
liefert `RESULT=FAIL REASON=duplicate` zurueck, im Code in
`ui/mw_qso.py:386-392` als `dup` gezaehlt). Aber **lokal sind die Eintraege
trotzdem da**.

**Aufgabe:**
- Duplikat-Check in `log/adif.py` vor `log_qso()`-Schreiben.
- Logik: gleicher Call + gleiches Band + gleicher Modus binnen 60 Min
  → entweder updaten (latest wins) oder skip + Info-Log.
- UI-Hinweis im QSO-Panel ("Doppel-QSO mit X erkannt — uebersprungen").
- `qso_log.add_qso` analog absichern.

**Trivial-Mittel:** ~1 Tag Aufwand. Kein eigener Workflow — KISS.

---

### 🟡 P1.8 — Report-SNR-Bug: `_last_snr` statt `msg.snr` (NEU 2026-05-05)

**Symptom (Field-Test 09:35-:44):** wir senden Reports mit deutlich
schlechteren dB-Werten als die Gegenstation uns gibt:

| QSO | Wir senden | Gegenstation an uns | Diff |
|---|---|---|---|
| SP6AXW | -24 | R-17 | 7 dB |
| DA1TST | -23 | R+19 | **42 dB** |

42 dB-Differenz ist **zu gross** fuer reine Hardware-Asymmetrie (Mike's
ANT1=Kelemen-Dipol vs. Icom-Antenne). Mike's Frage: *„wir senden raport
mit wesendlich schlechtere wert als wir ihn empfangen?"*

**Code-Wurzel-Verdacht:** `core/qso_state.py:218` und `:233` in
`_process_cq_reply`:
```python
report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
```

`self._last_snr` wird in `ui/mw_cycle.py:751` fuer **jede** dekodierte
Message gesetzt:
```python
self.qso_sm.set_last_snr(msg.snr)
```

Decoder emit'd messages in **dekodierter Reihenfolge** (decoder.py:258-267,
nach `_decode_with_subtraction` → starkes Signal zuerst, schwaches zuletzt).
Der LAST-emit-msg setzt `_last_snr` final → das ist die SCHWAECHSTE
Station im Slot, nicht die antwortende.

**Beispiel:** im :39:00-Slot werden 5 Stationen dekodiert (HA1BF -16,
GB8VED -15, EC3A -18, DA1TST **-10**, schwache Russland-Station -23).
`_last_snr=-23` zur Zeit `_process_cq_reply` laeuft → Report fuer DA1TST
ist `-23` statt korrekt `-10`. **42 dB Bug erklaert!**

**Live-Beweis 2026-05-05 21:58 UTC (Mike-Screenshot):**
- RX-Panel: UN0GY MN83 mit dB=-16 (im :57:57-Slot dekodiert)
- TX-Sequenz: `21:58:15 UN0GY DA1MHH -23` ← falscher Report!
- Differenz 7 dB — UN0GY hat -16, wir senden -23
- Slot enthielt ~20 Stationen, schwaechste war TL8BNW JN34 mit -23
- → `_last_snr=-23` bei `_process_cq_reply` → Bug bestaetigt

**Fix:** in `_process_cq_reply` (Z. 218 + 233) `self._last_snr` durch
`msg.snr` ersetzen (msg ist der DA1TST-Reply). Analog im
`tx_slot_for_partner.emit(msg)`-Pfad checken.

**Plus:** auch in `start_qso()` (Z. 263) nutzt `_last_snr` — das ist OK
weil bei Hunt der User klickt und KEIN Slot-spezifisches msg vorliegt.

**Workflow:** voller V1→V2→R1→V3. Nicht trivial — der Pfad geht durch
die State-Machine, mehrere Stellen pruefen. **R1 muss bestaetigen ob
`msg.snr` an allen relevanten Stellen die richtige Quelle ist.**

**Prio:** mittel — kosmetisch wirkend, aber FT8-Reciprocity-Praxis ist
wichtig (echte Stationen verlassen sich auf akkurate Reports). Nicht
blockierend, aber sollte NACH P1.9 (Anfang-Bug) und P1.10 (Ende-Bug) kommen.

---

### ✅ ERLEDIGT P1 — v0.95 + v0.95.1 QSO-Panel Slot-Tag/Zeit-Display-Fix (2026-05-05)

7 atomare Commits (``dac4a73``..``5d4b767``). Decoder als single source
of truth fuer Slot-Quelle. Tests 742 → 756 gruen. Voller V1→V2→R1→V3-
Workflow zweimal. Field-Test offen (siehe HANDOFF.md).

Original-Beschreibung (zur Doku):

### 🔴 P1 (war offen) — QSO-Panel Slot-Tag/Zeit-Display falsch (2026-05-05)

**Symptom Field-Test 03:38-:40 UTC:** RX und TX erscheinen mit identischem
Slot-Tag `[E]` und Zeit, obwohl FT8 das physikalisch ausschliesst. QSO mit
DA1TST/R6OK/PY7ZZ liefen real korrekt (IC-7300 DT 0.0-0.1 s) — reine
Anzeige-Anomalie. RX-Eintraege haengen 1 Slot hinterher und vergeben das
EVEN-Tag des Folge-Slots statt das ODD-Tag des TX-Slots der Nachricht.

**Root Cause (R1-bestaetigt + Log-verifiziert):**
- `ui/qso_panel.py:147-177` `_slot_tag()` + `add_rx()` nutzen
  `time.time()` zum Decoder-Output-Zeitpunkt
- Decoder-Output kommt 1 Slot zu spaet weil Audio-Buffer-Lag (FlexRadio
  VITA-49). Decode selbst <0.2 s, aber `Zu wenig Audio: X < 90000` im Log
  → Skip, Decode dann erst im Folge-Slot
- `time.time()` zur Decode-Output-Zeit liegt damit im Folge-Slot

**Loesung Option A (R1-Empfehlung, von uns erweitert):**
- Decoder ermittelt `slot_start_ts` aus Wake-Zeit und setzt es als
  Attribut auf jede Message (sichere Quelle, unabhaengig von GUI-Lag)
- `_assign_slot_parity` nutzt Decoder-gesetzten Wert statt
  `is_even_cycle()` zur Aufruf-Zeit
- `add_rx`/`add_tx` bekommen `tx_even` + `slot_start_ts` durchgereicht

**Dokumente:**
- V1: `prompts/qso_panel_slot_display_v1.md`
- V2: `prompts/qso_panel_slot_display_v2.md`
- R1: `prompts/qso_panel_slot_display_r1.md`
- V3: noch zu schreiben → Mike-Freigabe vor Code

**Stats-Risiko:** R1-bewertet < 0.1 % falsche Slots am Stundenrand,
symmetrisch verteilt → kein Bias in Pooled-Mean. **Historische Daten
nicht korrigieren.**

---

### 🟡 P2 — Reply-Lag durch Audio-Buffer-Latenz (2026-05-05)

**Beobachtung Field-Test:** Bei R6OK-QSO antwortet DA1MHH mit Report erst
:45:30 statt :45:00 (1 Slot zu spaet). Folge: R6OK haelt Mike's Antwort
fuer ausgeblieben und sendet seinen CQ-Reply :45:15 ODD nochmal — wirkt
fuer Mike wie „doppelte Antwort".

**Vermutete Wurzel:** Selbe wie P1 — Audio-Buffer-Lag bei FlexRadio
VITA-49. Decoder-Output kommt 1 Slot zu spaet → State-Machine-Reaktion
+ TX-Pipeline-Trigger landen im uebernaechsten Slot statt im naechsten.

**Wichtig:** Erst nach P1-Fix angreifen — das korrekte Slot-Display
zeigt erst dann zuverlaessig wieviel Lag wirklich da ist und ob die
Hypothese „selbe Wurzel" stimmt. Vielleicht reduziert sich der Reply-
Lag bereits auf < 1 Slot wenn die Anzeige stimmt.

**Mogliche Eingriffe (sofern nach P1 noch noetig):**
- Wake-Offset im Decoder vergroessern (aktuell `_WAKE = SLOT - 1.5s`,
  evtl. SLOT - 2.5s) — gibt Audio-Buffer mehr Zeit voll zu werden
- VITA-49 Jitterbuffer-Konfiguration im FlexRadio-Connector pruefen
- Audio-Pre-Fetch / Buffer-Pacing untersuchen

**Risiko hoch** — Hardware-naher Eingriff, eigener Workflow nach P1.

---

### ✅ ERLEDIGT — v0.90 Mess-Pattern-Bug-Fix (2026-05-04)

`core/diversity.py:86` auf fair 3:3 (``("A1","A1","A2","A2","A1","A2")``)
korrigiert — Option C aus V3. 3 atomare Commits, Tests 664 gruen.
Voller Workflow V1→V2→R1→V3 mit 2 R1-KRITISCH-Findings (End-to-End-Test,
Bandwechsel-Race-Hinweis behalten). Siehe HISTORY.md v0.90-Eintrag und
``prompts/v090_v3.md`` fuer Details.

**Statistik-Disclaimer:** Alle Pre-v0.90 Diversity-Daten haben strukturellen
Mess-Bias 4:2. Pooled-Mean +88 %/+124 % bleibt valide; absolute ANT2-Win-Rate
war konservativ unterschaetzt. Field-Test-Erwartung: ANT2-Win-Rate steigt
von ~4 % auf ~15-25 % auf 40 m FT8.

---

### ✅ ERLEDIGT — v0.92 Lock-Audit (2026-05-04)

Atomarer Commit `9b9303d` + Doku-Sync. R1-Audit-Findings adressiert.

**5 Edits in `ui/mw_radio.py`:**
1. `_set_gain_measure_lock` — setzt `self._gain_measure_locked` Flag
2. `_on_band_changed` — Frueh-Return wenn Flag aktiv
3. `_on_mode_changed` — gleiches
4. `_on_rx_mode_changed` — gleiches (R1-NEU-Finding!)
5. `_enable_diversity` — Lock VOR `_diversity_ctrl.reset()`

**Tests +6** in `tests/test_lock_coverage.py` (NEU): 675 → 681 gruen.

**R1-Halluzinationen verworfen:** btn_rx-Schutz (kein btn_rx im Code),
Bandpilot-Pending (KISS-Argument).

**Bandwechsel-Race aus v0.90 R1-Verdacht final geloest.**

**Diskussions-Trail:** `prompts/lock_audit_v1.md`, `_v2.md`, `_r1.md`, `_v3.md`
**Memory:** `project_lock_audit_pending.md`

---

### 🟢 v0.93 Cache-Reuse + Mess-Refactor — Plan steht, Implementation pending (2026-05-04)

**Status:** Voller V1→V2→R1→V3-Workflow + Folge-R1 zur FT2-Statistik.
Mike's Vision konsequent durchziehen mit R1's 4 Modifikationen.
Reihenfolge: NACH v0.92 Lock-Audit.

**Mike's Vision (R1-bestaetigt):**
1. **1 h Auto-Refresh** statt 15 Min Zyklen-Counter (atmosphärisch korrekt)
2. **Cache-Reuse pro Band+Modus** bei Bandwechsel (5-s-Toast, kein Klick)
3. **Normal-Modus raus** aus Cache-System („Normal ist normal")
4. **OPERATE_CYCLES Konstante weg** + Settings-Option `diversity_operate_cycles` weg
5. **`_MULT` für OPERATE_CYCLES weg** (zeit-basiert obsolet)
6. **Pattern fair 3:3 bleibt** unverändert (v0.90)

**R1's 4 KRITISCHE Modifikationen:**
- **Mod 1:** `_MULT` für MEASURE_CYCLES BEHALTEN (FT8=6, FT4=12, FT2=24)
  — FT2 in 6 Zyklen × 3.8 s = 23 s waere zu kurz fuer Statistik
- **Mod 2:** PresetStore zwei Timestamps (`gain_timestamp` 6h + `ratio_timestamp` 1h)
- **Mod 3:** CQ-Lock zusätzlich zu QSO-Lock in `should_remeasure()`
- **Mod 4 (KILLER):** `score` (= sum(snr+30)) statt `station_count` speichern
  — adressiert Mike's FT2-Sorge (1-2 Stationen pro Slot → diskrete Werte
  {0,1,2} → keine Auflösung). Mit Score: kontinuierliche Werte, Median
  statistisch robust auch bei dünner Dichte. **Eine Zeile umstellen**
  (`record_measurement` Z.381) — Score wird schon übergeben, nur ignoriert.

**R1's Bonus-Modifikationen:**
- **Mod 5:** `MIN_MEASURE_STATIONS = 5` ENTFERNEN (`can_measure()` immer True)
  — bei FT2 oft Block-Trigger, mit Score-Umstellung obsolet
- **Mod 6 (optional):** `scoring_mode` vereinheitlichen — DX-Modus obsolet
  weil SNR-Score eh feiner als `dx_weak_count`. Kann später separat.

**Code-Stellen:**
```
core/diversity.py:27       OPERATE_CYCLES = 60          → ENTFERNEN
core/diversity.py:29       MIN_MEASURE_STATIONS = 5     → ENTFERNEN
core/diversity.py:374-385  record_measurement           → score statt station_count
core/diversity.py:421-453  _evaluate                    → peak-Schwelle anpassen (5.0)
core/diversity.py:461      should_remeasure(qso_active) → +cq_active
core/preset_store.py:19    VALIDITY_SECONDS = 6*3600    → splitten in gain/ratio
core/preset_store.py:99    is_valid()                   → ratio/gain unterscheiden
core/preset_store.py:139   save_ratio()                 → ratio_timestamp setzen
ui/main_window.py:822      OPERATE_CYCLES aus Settings  → ENTFERNEN
ui/mw_radio.py:821-824     _MULT für OPERATE_CYCLES    → ENTFERNEN (MEASURE_CYCLES bleibt)
ui/mw_radio.py:_on_band_changed   → Cache-Check VOR _diversity_ctrl.on_band_change()
ui/mw_cycle.py:220        save_ratio() bereits da, _was_early_stopped-Schutz aus v0.91 #8
```

**Aufwand:** ~4.5 h (V3 + Code + Tests + Doku-Sync v0.93).

**Trigger nach Compact:** „Refactor starten" oder „v0.93 starten" oder
„Score zuerst" (nur Mod 4 als Quick-Win).

**Diskussions-Trail:**
- V1: `prompts/cache_reuse_refactor_v1.md`
- V2: `prompts/cache_reuse_refactor_v2.md` (7 Self-Review-Findings)
- R1: `prompts/cache_reuse_refactor_r1.md` (Mike-Vision + 3 Mods)
- Dichte-V1: `prompts/cache_reuse_dichte_problem.md` (FT2-Statistik-Problem)
- Dichte-R1: `prompts/cache_reuse_dichte_r1.md` (Score-Insight!)

**Memory:** `project_diversity_cache_reuse.md`

**Was BLEIBT unveraendert:**
- Phase 2 Gain-Messung (separate 6 h Validity)
- Phase 3 fair 3:3 Pattern (v0.90)
- v0.91 Adaptiv-Stops (Phase 2 + Phase 3)
- v0.91 Cache-Schutz (`_was_early_stopped`)
- Manueller „NEU"-Button

---

### ✅ GELÖST durch v0.93-Refactor — OPERATE_CYCLES wird komplett entfernt

Aufgenommen in den Cache-Reuse + Mess-Refactor-Plan (siehe oben).
Mike's Vision: 1 h Auto-Refresh atmosphärisch korrekt, OPERATE_CYCLES
und `_MULT`-Skalierung weg, Settings-Option weg. R1-bestaetigt.

Wird mit v0.93 erledigt — Trigger „Refactor starten" / „v0.93 starten".

---

### 🆕 Radio-Erreichbarkeits-Check beim App-Start (2026-05-04, Mike)

**Problem:** Wenn das FlexRadio aus ist, startet die App still und versucht
nur via Reconnect-Loop alle 60 s neu zu verbinden. User merkt das erst nach
einer Weile (Log-Eintrag `[Radio] FlexRadio Verbindung fehlgeschlagen: timed
out` + `[FlexRadio] Reconnect #N in 60s ...`).

**Gewuenschtes Verhalten:**
- Beim App-Start einmal pruefen ob konfiguriertes Radio erreichbar ist
  (TCP-Connect zur Radio-IP/Port mit kurzem Timeout, z. B. 2-3 s).
- Falls nicht erreichbar: nicht-modalen Dialog/Toast oben anzeigen
  („FlexRadio nicht erreichbar — Radio einschalten und auf Verbindung
  warten" o. ä.). Nicht blockierend (App soll weiterlaufen, Reconnect
  weiterversuchen).
- Bei spaeterem Erfolg-Verbinden den Hinweis automatisch verschwinden lassen.

**Code-Stellen (V1-Skizze, R1 in eigenem Workflow):**
- `radio/flexradio.py` — neue Methode `is_reachable(timeout=2.0)` die einen
  TCP-Connect-Test macht ohne Login.
- `ui/main_window.py` `_init_radio()` oder direkt nach Settings-Load —
  Reachability-Check + Toast.
- Toast-Klasse evtl. wiederverwendbar (z. B. aehnlich `BandpilotAutoToast`
  aber persistent bis Verbinden klappt).

**Aufwand:** ~30-60 min Code + Workflow V1→V3.
**Status:** OPEN — eigener V1→V3-Zyklus nach Block-2-Erfolg.

---

### ✅ ERLEDIGT — Block 2 Kalibrier-Pipeline-Optimierung (v0.91, 2026-05-04)

Pipeline ~4:31 Min (v0.89/v0.90) → typisch ~3:20 Min, Best-Case ~2:30 Min.

**3 atomare Commits:**
- `eef4369` ROUNDS 3→2 (#6, -60 s, Schedule 12→8 Eintraege)
- `3068919` Adaptiv-Stop Phase 2 nach Runde 1 (#7, -30 bis -60 s,
  Δ_SNR≥4 dB ODER Δ_STAT≥50 %, +6 Tests)
- `f090097` Adaptiv-Stop Phase 3 nach 4 Zyklen + Cache-Schutz
  (#8, -30 s, EARLY_STOP_THRESHOLD=0.15, Cache-Schutz R1.4 KRITISCH, +5 Tests)

**Voller V1→V2→R1→V3-Workflow durchgezogen.** R1-Findings adressiert:
Cache-Schutz, Monitoring-Log mit Timestamp, FT4/FT2-Doku, Cancel-Flag dokumentiert.

**Tests:** 664 → 675 gruen.

**Schwellen konservativ tuned (R1-bestaetigt):** Field-Test liefert
Daten fuer evtl. Senken auf 12 % (R1-Empfehlung). Monitoring-Log mit
ISO-Timestamp eingebaut.

**FT4/FT2-Hinweis:** Pattern-Periode 6 verhindert balancierte Verteilung
bei MEASURE_CYCLES=12/24, Pre-Condition len-equal verhindert Stop —
effektiv profitiert nur FT8 (Hobby-Use 99 % FT8, R1-akzeptiert).

**Status:** ERLEDIGT. Field-Test Block 1+2 wartet auf Mike.

---

### 🆕 Reiter „Geraet" in Settings — Sauberer Remote-Shutdown + Auto-Start (03.05.2026)

**Hintergrund (Web-Recherche 2026-05-03):**
- KEIN offizieller SmartSDR-API-Befehl fuer Power-On/Off (FlexRadio
  Staff bestaetigt, Daemon "In Review" seit Dez 2019, nicht umgesetzt).
- KEIN offizieller SSH-Zugang zum Linux des Radios.
- **Saubere Linux-Shutdown-Methode = REM ON Jack Open-Circuit.** Das
  ist KEIN AC-Cut, sondern ein Soft-Trigger an die Radio-CPU
  (~15-20s sauberer Shutdown, dann safe).
- Empfohlene Hardware: **Shelly 1 / Shelly Plus 1** (~15€,
  ESP-basiert, lokale HTTP-API ohne Cloud-Zwang) als IP-Relais
  am REM ON Jack.

**Mike's offene Frage:** welche Hardware (Shelly schon vorhanden?
neu kaufen? andere Marke?). RCA-Adapter mit Drahtenden zu
Relais-Kontakten — fertig kaufen oder loeten?

**Geplanter Tab „Geraet" (nach Mike-Entscheidung Hardware):**

```
Tab "Geraet":
- Sauber herunterfahren (Shelly Relais am REM ON):
  - Shelly-IP + Auth-Token (optional)
  - "Verbindung testen"-Button
  - "Radio sauber herunterfahren"-Button
    -> Stoppt TX, schliesst Decoder, oeffnet REM ON via HTTP,
       wartet 20s auf Linux-Shutdown
- Auto-Start nach Stromausfall:
  - Hardware-Setting im Shelly: "Restore last state" oder
    "Always on" -> Relais bei Stromrueckkehr "zu" -> REM ON
    shorted -> Radio bootet automatisch
  - "Setup-Anleitung oeffnen"-Button
```

**Aufwand-Schaetzung (nach V1->V2->R1->V3-Workflow):**
- core/shelly_client.py: HTTP-Client mit Auth, ~80-120 Zeilen
- ui/settings_dialog.py: neuer Tab "Geraet", ~80 Zeilen
- core/safe_shutdown.py: TX-Stop + Decoder-Close + Shelly-
  Trigger + 20s-Warten, ~60 Zeilen
- tests/test_shelly_client.py: HTTP-Mock, ~60 Zeilen
- docs/explained/remote-shutdown_de.md + .md: Setup-Anleitung
  + Hardware-Skizze
- Hardware-Setup (Mike): Shelly konfigurieren, RCA-Adapter
  loeten oder Adapter-Kit, im Settings IP eintragen
- Gesamt: ~3-4h Code + Hardware-Beschaffung Mike

**Status: WAITING fuer Mike's Hardware-Entscheidung.**

---

**Mike's offene Map-UI-Punkte aus v0.68-Field-Test — ALLE ERLEDIGT:**
- ✅ Punkt 3 (Zeit-Dropdown) — erledigt v0.68
- ✅ Punkt 4 (Band-Dropdown) — erledigt v0.68
- ✅ Punkt 5 (Sektor-Rotation) — erledigt v0.68 + Folgekorrektur
- ✅ Punkt 1 (Propagations-Balken Pulsieren) — erledigt v0.69
- ✅ Punkt 6 (Stations-Count Tooltip "37 / 46 Stationen") — erledigt v0.70
- ✅ Punkt 2 (PSK-Reporter Reichweiten-Sektoren TX) — erledigt v0.71

**v0.73 Release-Bilanz (28.04.2026):**
- 💾 **Persistenter RX-History-Cache:** pro (band, mode) 60 Min Empfangs-
  daten in `~/.simpleft8/cache/rx_history/{band}_{mode}.json`. Karte zeigt
  beim Open + Bandwechsel sofort die letzte Stunde — auch nach App-Restart.
- 🧹 **Karten-UI-Aufraeumung:** Time-Window-Combo + Band-Combo raus
  (waren tote/halbtote UI-Deko). simpleFT8-Style: Karte zeigt aktives
  Band, 60 Min hardcoded.
- 🧪 6 atomare Commits, 430 → 442 Tests gruen, V1→V2→V3 mit DeepSeek-
  Reviewer (5 echte Findings uebernommen, 4 verworfen).

**v0.72 Release-Bilanz (28.04.2026):**
- 🎨 **Karten-Theme-Toggle (Aurora / Dark):** QComboBox in DirectionMapDialog,
  Aurora bleibt Default. Dark-Mode = schwarzes Land + mittel-graues BG +
  flacher Disk + dezent graue Coastlines (Mike-Inspiration aus QSO-Landkarte
  mit VP8FLY/ZL4AS-Verbindungen).
- 💾 Settings-Key `direction_map_theme` persistiert ueber App-Restarts.
- 🛡️ DeepSeek-Findings (4): AK harmonisiert, Aliase belassen, disk_fill statt
  Skip, QComboBox statt Toggle-Button, Commits 2→3 aufgeteilt.
- 🧪 4 neue Tests, 426 → 430 gruen.

**v0.71 Release-Bilanz (27.04.2026):**
- 🌍 **TX-Reichweiten-Sektoren:** Karten-TX-Modus zeigt Sektor-Wedge-Laenge
  jetzt nach max-Distanz pro Sektor statt Cluster-Dichte. VK6-Spot (16000 km)
  erzeugt langen Wedge, dichter Iberien-Cluster bleibt bescheiden.
- 🛡️ NaN/Inf-Guard in `SectorBucket.max_distance_km` — DeepSeek-Review hat
  echten Edge-Case gefunden (NaN propagiert sonst durch paintEvent).
- 🧪 4 neue Tests, 422 → 426 gruen.

**v0.70 Release-Bilanz (27.04.2026):**
- 🐛 **Kritischer Bugfix:** `is_grid` Property-Aufruf mit Klammern → seit v0.67
  silent TypeError, Live-Locator-Feed komplett tot. **Jetzt aktiv** — DB
  waechst live mit jedem CQ/Antwort.
- 💾 Auto-Save LocatorDB alle 5 Min — kein Datenverlust bei Hard-Kill
- 🪟 Ant-Spalte 'A1' im Normal-Modus
- 🔍 Stations-Count Tooltip auf Karte
- 📊 LocatorDB-Stand: **7.991 Calls** aus DA1MHH+DO4MHH-ADIF (854 KB JSON)

**Naechstes Feature:**
- 🔜 **Settings-Dialog auf Tabs umstellen** (28.04.2026) — aktuell 6 GroupBoxes
  vertikal gestapelt (Station/TX/RF-Presets/FT8/Export/Karte), Hoehe ~900-1000 px,
  passt nicht auf Mike's 1440×900 Display. Plan: 3 Tabs (Station / TX / FT8)
  mit max 500-600 px pro Tab. Aufwand 1-2 h. *Nach Bug-Fix Diversity-
  Bandwechsel.*

**Andere offene TODOs:** siehe Liste unten.

**ENTFALLEN — Feature B (PSK-Reporter Band-Indikatoren) gestrichen:**
Bei der V1→V2-Workflow-Diskussion am 27.04. mit Mike kam raus, dass das
gesuchte „pulsierende Bandoeffnungs/-schliessungs"-Feature bereits in
**v0.69** vollstaendig implementiert ist:
- Saison-Fenster pro Band+Saison in `core/propagation.py:_SEASONAL_SCHEDULE`
- Lookahead 60 Min via `get_conditions_at(60)`
- Pulsation NUR fuer aktives Band, andere statisch
- Cross-Fade Ist-Farbe ↔ Trend-Farbe

PSK-Reporter Live-Daten sind dafuer **nicht noetig**. Wenn HamQSL-Daten
ungenau wirken: Saison-Fenster in `_SEASONAL_SCHEDULE` justieren (rein
Werte-Aenderung, kein Code).

**Field-Test BESTANDEN ✅ (28.04.2026, Mike):**
- ✅ **v0.69-Pulsation auf 40m sichtbar** — Mike hat den Bandwechsel-
  Pulse beim Wechsel auf 40m im Feld bestaetigt. Feature funktioniert
  wie spezifiziert.
- ✅ **v0.72 Dark-Mode auf Karte** — „erdkugel map sieht geil aus
  funktioniert auch super" (Mike-Original-Quote). Theme-Toggle +
  Persistenz live verifiziert.

**Pulsations-Zeiten Spring (April-Mai), Berlin-Zeit UTC+2 (Referenz):**
  | Band | Oeffnen | Schliessen |
  |------|---------|------------|
  | 10m  | 10-11 MESZ | 18-19 MESZ |
  | 12m  | 09-10 MESZ | 19-20 MESZ |
  | 15m  | 08-09 MESZ | 21-22 MESZ |
  | 17m  | 07-08 MESZ | 22-23 MESZ |
  | 20m  | 06-07 MESZ | 23-00 MESZ |
  | 30m  | 04-05 MESZ | 00-01 MESZ |
  | 40m  | 16-17 MESZ | 09-10 MESZ |
  | 80m  | 18-19 MESZ | 08-09 MESZ |
  Caveat: Pulse triggert nur wenn HamQSL fuer dieses Band innerhalb-
  Fenster „good" oder „fair" liefert (sonst poor↔poor = kein Wechsel
  sichtbar).

**Field-Test offen:**
- ✅ **v0.67 Locator-DB Praezisionstest:** sichtbar in der Karte — 50/53
  Stationen mit Position nach Restart, Ø Genauigkeit 74 km. JSON
  persistiert. Erfolgreich.
- **v0.69 Pulsier-Animation:** subjektiv-Test bei Tageszeit-Uebergang
  (z.B. 16-17 UTC fuer 40m winter close): fuehlt sich der Cross-Fade
  beruhigend an? Falls zu auffaellig: `fade=2000`/`hold=4000` in
  `_start_pulse` (`ui/control_panel.py:_ModeBandCard._start_pulse`).
- **v0.70 Live-Locator-Feed:** ueber laengere Empfangs-Session
  beobachten ob die DB sichtbar waechst. Erwartung: pro Stunde 5-15
  neue Calls mit prec_km=5 (CQ-Calls + Antworten mit Grid).
- **v0.71 TX-Reichweiten-Pattern:** Karte → SENDEN-Modus an einer
  guten 40m-Abend-Session. Erwartung: dunkler-orange Iberien-Wedge
  (kurze Distanz, viele Stationen), leuchtend-gelber USA-Wedge (lange
  Distanz, weniger Spots). Falls TX-Sektoren bei wenigen Spots zu
  unruhig wirken: Min-Floor (z.B. 20% max_wedge_r) erwaegen.

---

## 🔬 Antennen-Diversity Daten-Sammlung (Prio NIEDRIG, Stand 27.04.2026)

**Stand der Erkenntnis (n=2 Baender):**
- 40m FT8 (off-band fuer ANT1 Kelemen Trap-Dipol): Diversity Standard
  +88 %, Diversity DX +124 % vs Normal. Robuste Datenbasis (~22.700 Zyklen).
- 20m FT8 (resonant ANT1): Diversity Standard −23 %, Diversity DX −33 %.
  Daten noch duenn (~3.000-3.600 Zyklen je Modus, schiefe Stunden).

**Mike-These:** „Auf resonanter ANT1 verliert Diversity, off-band gewinnt
sie." DeepSeek-Bedenken (gerechtfertigt):
- Pol-Diversity bei HF-Skywave ist durch Faraday-Rotation eh randomisiert
  → vert/horz-Argument schwaecher als gedacht
- Regenrinne 15 m hat band-abhaengige Pattern (1.4 λ auf 20m vs 2.1 λ auf
  15m) — koennte ANT2-Performance pro Band stark verschieben
- Wetter (nasse Rinne) verschiebt Wirkungsgrad um 1-2 dB → schwer zu
  isolieren ohne Wetter-Tracking

**Test-Roadmap (kein Zeitdruck — Daten sammeln wenn Mike sowieso funkt):**

| Band | ANT1-Status | Erwartung | Prio | Daten-Soll |
|---|---|---|---|---|
| **17m FT8** | off-band | Diversity gewinnt (wie 40m) | hoch | 3+ Tage, 06–22 UTC |
| **15m FT8** | **resonant** | Diversity verliert (wie 20m) — kritischer Test | hoch | 3+ Tage, 08–18 UTC |
| **12m FT8** | off-band | Diversity gewinnt | mittel | 2+ Tage |
| **80m FT8** | off-band | Diversity gewinnt | mittel | 2+ Tage Nacht |
| **10m FT8** | resonant | nur bei Bandoeffnung — Spo-E saisonal | niedrig | gelegentlich |

Wichtig: **Statistik-Filter v0.63 prueft nur 20m/40m FT8.** Fuer die anderen
Baender muss Mike entscheiden ob das geaendert wird (Filter erweitern auf
{17m, 15m, 12m, 80m, 10m}) oder ob die Daten als CSV-Export reichen.
→ **TODO bei Beginn der 17m-Phase:** Stats-Filter erweitern.

**Entscheidungs-Punkt nach 5 Baendern:**
Wenn die Heuristik „off-band gewinnt, resonant verliert" sich
bestaetigt → kleinen Info-Tooltip an Diversity-Aktivierung
(neutral formuliert, kein Verhaltenseingriff). Wenn nicht → gar nichts
implementieren, App bleibt neutral.

DeepSeek-Empfehlung dokumentiert: **Tooltip-Text wenn implementiert wird:**
> „Der Diversity-Vorteil haengt stark von deiner Antennen-Kombination,
> Band, Wetter und Tageszeit ab. Am besten testest du selbst pro Band,
> ob es dir hilft."

---

## NEXT FEATURES — Plan vom 26.04.2026 (Brainstorming Mike + Claude + DeepSeek)

Reihenfolge nach Priorität. Quick-Wins zuerst, USP-Killer-Features parallel als Strategie.

---

### A0) Locator-DB persistent (v0.67) — ✅ **ERLEDIGT 27.04.2026**

Persistenter Locator-Cache aus CQ/PSK/ADIF mit Source-Priority. 6 atomare
Commits, 28 Tests, DeepSeek-codereviewed. Karte und rx_panel ziehen aus
der DB. Save bei App-Close (atomar). Siehe HISTORY.md v0.67.

---

### A) Aging in Slots statt Sekunden (Bug-Fix) — ✅ **ERLEDIGT v0.64 (26.04.2026)**

Umgesetzt mit Werten 7/14/20 (DeepSeek-Korrektur, 5/10/20 waere auf FT4 zu aggressiv).

---

### A-OLD-DOC) Aging Original-Plan (zur Doku)

**Problem:** `core/station_accumulator.py` nutzt Aging in Sekunden:
- 75s normal / 150s active_qso / 300s CQ-Rufer
- FT8 (15s/Slot) → 5/10/20 Slots ✓
- FT4 (7.5s) → 10/20/40 Slots ✓
- FT2 (3.8s) → **20/40/79 Slots** ❌ deutlich zu lang!

**Fix:** Aging in SLOTS umrechnen. Konstanten:
```python
AGING_SLOTS_NORMAL    = 5   # 5 Slots = 75s FT8 / 37.5s FT4 / 19s FT2
AGING_SLOTS_ACTIVE    = 10
AGING_SLOTS_CQ_CALLER = 20
```
Bei jedem Decode-Cycle aktuelle Slot-Nummer einfließen lassen statt timestamp.

**Test:** Es gibt bereits Aging-Tests — anpassen (Slot-Counter statt time.time).

---

### B) Band-Indikatoren live mit PSK-Reporter ergänzen — ✅ **GESTRICHEN 27.04.2026** (v0.69 deckt Use-Case bereits ab)

> Mike's eigentlicher Wunsch (pulsierende Bandoeffnungs-/Schliessungs-
> Indikatoren am aktiven Band) ist bereits in v0.69 vollstaendig
> implementiert via `core/propagation.py:_SEASONAL_SCHEDULE` + Lookahead
> 60 Min. Live-PSK-Daten sind dafuer **nicht noetig**. Bei ungenauen
> HamQSL-Werten: Saison-Fenster in `_SEASONAL_SCHEDULE` justieren.
> Original-Plan unten zur Doku, NICHT umsetzen.

**[Original-Plan zur Doku] Foundation ist mit v0.66 schon da:** `core/psk_reporter.py` (XML-Polling, Cache,
Backoff, Threading) ist wiederverwendbar. Brauchen nur eine zweite Query-Variante
mit `mode=FT8&lastMinutes=5` (ohne senderCallsign-Filter) für Aktivitaets-
Aggregat pro Band — das passt in eine erweiterte `PSKReporterClient.fetch_activity()`-
Methode.

**Status quo:** Bestehende kleine Balken UNTER den Band-Buttons (rot/gelb/grün)
basieren nur auf HamQSL Solar Flux + Tageszeit + saisonale Korrektur (`core/propagation.py`).

**Neu:** PSK-Reporter Live-Aktivität dazu:
- Zeigt nicht nur "theoretisch sollte das offen sein" sondern "weltweit X Stationen GERADE aktiv, Trend ↗/↘"

**API (verifiziert mit DeepSeek):**
- Endpoint: `https://pskreporter.info/cgi-bin/psk-find.pl?mode=FT8&lastMinutes=5&callback=json`
- 1 Request liefert ALLE Bänder → Client-seitig pro Band aggregieren
- Polling: alle 2 Min (safe, JTAlert/GridTracker machen es genauso)
- Pro Spot: `senderCallsign`, `band`, `timestamp`, `receiverLocator`, `snr`

**Trend-Erkennung:**
- 2-Fenster-Approach: `last_5_min` vs `prev_5_min` (unique Calls)
- Ratio > 1.15 → "rising" (Band öffnet)
- Ratio < 0.85 → "falling" (Band macht zu)

**Visualisierung — neu (Mike's Idee):**
- Bestehende Farb-Balken bleiben (HamQSL-Berechnung)
- Bei steigendem Trend → **pulsierender Balken**, je näher zur "Öffnung" desto schneller
- `QPropertyAnimation` auf eigenes `QWidget.paintEvent` (kein setStyleSheet wegen Performance)
- Speed: 300-2000ms Cycle, mit Trend-Stärke skaliert

**Code-Skeleton aus DeepSeek:**
```python
# core/psk_reporter.py — neu
class PSKReporterClient:
    POLL_S = 120
    URL = "https://pskreporter.info/cgi-bin/psk-find.pl"
    
    def fetch_global_activity(self, mode="FT8", minutes=5):
        # JSONP parsen, Spots pro Band aggregieren
        ...
    
    def get_band_trend(self, band): ...  # rising/falling/stable
    def get_band_count(self, band): ...  # aktuelle unique Calls
```

```python
# ui/band_indicator.py — neu
class BandIndicatorWidget(QWidget):
    pulse_factor = Property(float, ...)
    def set_trend(self, strength: float): ...  # -1.0 bis +1.0
    def paintEvent(self, e): ...  # Alpha-pulsierende Farbe
```

---

### C) Richtungs-Keulen-Karte — TX-Pattern — ✅ **ERLEDIGT v0.66 (26.04.2026)**

Umgesetzt als Variante (b) **Weltkarte mit Sektor-Overlay** (Azimuthal-Equidistant-
Projektion mit JO31 als Center, 16 Sektoren à 22.5°, Coastlines aus Natural Earth
110m). TX-Modus nutzt PSK-Reporter Reverse-Lookup (`senderCallsign=...&mode=FT8`).
SNR-Skala dunkles Orange → Hellgelb. Aufruf via Settings → "Karte oeffnen ..."

Architektur in 10 atomaren Commits (siehe HISTORY.md v0.66):
- `core/geo.py` erweitert (Bearing, Projektion, safe_locator)
- `core/psk_reporter.py` (Polling, Cache, Backoff, Call-Normalisierung)
- `core/direction_pattern.py` (Sektor-Aggregation, Mobile-Filter)
- `core/antenna_pref.py` Thread-Safe (RLock + snapshot)
- `assets/ne_110m_land_antimeridian_split.geojson` (116 KB, 5143 Punkte)
- `tools/build_coastlines.py` (Pure-Python, kein shapely-Dev-Dep)
- `ui/direction_map_widget.py` (MapCanvas + DirectionMapDialog)
- Hook in `mw_cycle._handle_diversity_operate` + `_handle_normal_mode`
- Cross-Thread-Signal `direction_map_signal` mit Qt.QueuedConnection

+141 Tests (220 → 361). Alle Module DeepSeek-codereviewed.

---

### C-OLD-DOC) TX-Pattern-Karte Original-Plan (zur Doku)

**Idee Mike:** Statt PSK-Reporter Punkte/Kreise zu zeigen → Stationen nach **Großkreis-Richtung gruppieren in 16 Sektoren** (à 22.5°). Jeder Sektor wird zu einer **Keule**.

**Was du daraus lernst:**
- "Heute Süd-Ausbreitung dominiert — 25 Stationen, max 8000 km"
- "Nichts nach W → 10m sinnlos"
- "Skip-Zone heute bei 1500-3000km in Sektor 4"

**Datenquelle: PSK-Reporter Reverse-Lookup**
- Endpoint: `?callsign=DA1MHH&mode=FT8&lastMinutes=60` → wer hat MICH gehört
- Pro Spot: `receiverLocator` + `snr`
- Sub-Minute Latenz (5-30s typisch)

**Algorithmus:**
1. Maidenhead-Locator → Lat/Lon (Standard-Formel)
2. Großkreis-Azimut von JO31 → empfänger-Lat/Lon
3. Sektor-Bin: `int(bearing / 22.5) % 16`
4. Pro Sektor: Anzahl Empfänger, Ø SNR, max Entfernung

**Rendering (Optionen, Mike entscheidet):**
- (a) **Polar-Diagramm** (Rosenkreis): kompakt, sauber
- (b) **Weltkarte mit Sektor-Overlay**: Keulen vom Zentrum (Herne) als gefüllte Kegel
- (c) **Hybrid**: Karte mit Punkten + Polar-Histogramm in der Ecke
- Empfehlung: **(b) — visuell stärkster Effekt**, QPainter-basiert

**Bonus: TX-Pattern zeigt was ANT1 (Sender) leistet** — durch Resonanz zeigt die TX-Keule auch die optimal genutzten Lobes des Kelemen-Dipols.

---

### D) Richtungs-Keulen — ANT2 RX-Pattern — ✅ **ERLEDIGT v0.66 (26.04.2026)**

Als EMPFANG-Modus im selben Karten-Widget umgesetzt. Live-Daten kommen
aus `mw_cycle` (Diversity + Normal). Antenna-Farbcode pro Station:
- Blau `#4488FF` = nur ANT1
- Cyan-Grün `#00CCAA` = ANT2 dominiert
- Leuchtgrün `#44FF44` = Rescue (snr_a1 ≤ -24 UND snr_a2 > -24)

Sektor-Wedges mischen Antennen-Farben gewichtet. LocatorCache merkt sich
Locator pro Call ueber die Session (FT8 hat Locator nur in CQ-Nachrichten).

---

### D-OLD-DOC) RX-Pattern Original-Plan (zur Doku)

**Idee Mike:** Für ANT2 KEINE PSK-Reporter-Daten (wir senden nicht über ANT2!) sondern **lokale Rescue-Daten** visualisieren.

**Was zeigen:**
- Wo hört ANT2 was ANT1 NICHT hört? (= Rescue: ANT1 < -24 dB, ANT2 dekodiert)
- Diese Stationen pro Sektor zählen → Keule

**Datenquelle (lokal!):**
- `core/antenna_pref.py` hat bereits `_snr_a1` / `_snr_a2` pro Call
- `statistics/Diversity_*/{band}/FT8/stations/*.md` hat Rescue-Spots historisch
- Filter: `a1_snr <= -24 AND a2_snr > -24`

**Rendering:**
- Gleiches Sektor-Diagramm wie C, aber mit ANT2-Farbe (kontrastierend zu TX-Pattern)
- Idealerweise im **selben Diagramm** überlagert: ANT1-TX-Keule + ANT2-RX-Rescue-Keule
- Zeigt sofort: "ANT1 strahlt nach SO, aber ANT2 fängt Norden ab"

**Algorithmus-Code-Skeleton (DeepSeek):**
```python
# core/rx_pattern.py — neu
class RXPatternAnalyzer:
    SECTORS = 16
    
    def update_from_rescue_spots(self, decoded_stations):
        for s in decoded_stations:
            if not s.locator: continue
            bearing = grid_bearing(MY_GRID, s.locator)
            sector = int(bearing / (360 / self.SECTORS)) % self.SECTORS
            if s.snr_ant1 <= -24 and s.snr_ant2 > -24:
                self.sectors[sector]["rescue"] += 1
```

---

### E) CSV-Export Diversity-Daten — ✅ **ERLEDIGT v0.65 (26.04.2026)**

Umgesetzt: Standalone-Script `scripts/export_diversity_csv.py` PLUS UI-Integration
im Settings-Dialog mit QFileDialog → Verzeichnis-Wahl. 4 CSVs, 675 Datensaetze.

---

### E-OLD-DOC) CSV-Export Original-Plan (zur Doku)

**Idee:** Pro QSO eine CSV-Zeile mit allen Diversity-Metadaten:
```
callsign, mode, band, timestamp_utc, freq_hz, ant1_snr, ant2_snr, 
selected_ant, delta_db, dt_correction, qso_complete
```

**Use Cases:**
- Wissenschaftliche Auswertung (Paper über 79-86% ANT2-Win-Rate trotz resonanter ANT1!)
- Externe Visualisierungs-Tools (Excel, Tableau, Pandas)
- Antennen-Optimierungs-Hinweise sammeln

**Implementierung:**
- Erweitern: `core/station_stats.py` um `export_diversity_csv(path, band, mode, days)`
- Menüpunkt im UI: "Datei → Diversity-Daten exportieren..."
- Default-Pfad: `~/Documents/SimpleFT8_Export/diversity_{band}_{date}.csv`

**ADIF-Vendor-Extension VERWERFEN** (DeepSeek-Vorschlag): andere Tools wie HRD/DXLab ignorieren das eh. Reines CSV reicht.

---

### F) Audio-Export per Slot (für Forschung/Debug) — **<1 Tag**

**Idee:** Roh-IQ pro Slot (4 sec PCM WAV) optional mitschneiden.

**Use Cases:**
- AP-Lite Feldtest: "warum hat AP-Lite die Station verpasst?" → Audio nachhören
- Antennen-Vergleich: Slot von ANT1 + Slot von ANT2 als WAV → Spektrum-Analyse offline
- Inspectrum / Audacity / Matlab Forschung

**Implementierung:**
- Toggle in Settings: "Roh-IQ-Audio mitschreiben (groß!)"
- Pfad: `audio_dump/{band}_{mode}/{YYYY-MM-DD_HH-MM-SS}_{ant}.wav`
- 4 Sekunden Slot-Capture-Buffer im `radio/flexradio.py` ergänzen
- Ringpuffer mit max 7 Tagen (alte Files automatisch löschen)
- Alternativ: nur bei "interessanten" Decodes (Rescue, neuer DXCC, Mike's Wahl)

---

## ABHAENGIGKEITEN / REIHENFOLGE

```
A (Aging-Bug)              ✅ erledigt v0.64
B (PSK-Indikatoren)        ←  als nächstes — Foundation steht (psk_reporter.py)
C (TX-Pattern-Karte)       ✅ erledigt v0.66
D (RX-Pattern ANT2)        ✅ erledigt v0.66 (im selben Widget)
E (CSV-Export)             ✅ erledigt v0.65
F (Audio-Export)           ←  unabhängig, jederzeit
```

**Aktueller Stand 26.04.2026:** 4 von 6 Plan-Features umgesetzt. Verbleibend:
- **B** als Nächstes (1-2 Tage) — Live-Aktivitaets-Indikatoren unter den
  Band-Buttons. Foundation `core/psk_reporter.py` ist da.
- **F** als optionales Forschungs-Feature.

---

## NICHT WEITERVERFOLGT (verworfen am 26.04.2026)

- ❌ Smart CQ Prediction (DeepSeek): Daten zu dünn, würde False-Confidence erzeugen
- ❌ RX-Mute Anzeige während TX (DeepSeek): unnötig, FT8-Funker wissen das eh
- ❌ Cross-Band-Empfehlung "geh auf 40m": Architektur unterstützt nur 1 Band aktiv
- ❌ ADIF-Vendor-Extension: andere Tools ignorieren proprietäre Felder
- ❌ DT-Heatmap im Histogramm: für FT8 bei DT<2s nicht praxis-kritisch (zurückgestellt, evtl. später)
- ❌ Antennen-Pref Hysterese auf 2 dB anheben: nach Feldtest entscheiden, aktuell `>=` 1 dB OK
- ❌ Band-Aktivität Sparkline (15-min): Idee von DeepSeek, durch B+Pulsation faktisch schon ersetzt

---

## OFFENE TODO (alte Liste, weiter aktuell)

### Karten-Feature v0.66 — Folgemassnahmen
- [ ] **Migration `main_window._psk_worker` → `core/psk_reporter`** —
  bewusst zurueckgestellt im Karten-Sprint (out-of-scope-Markierung im Code).
  Beide Pfade nutzen jetzt parallel die XML-API. Konsolidierung sinnvoll
  bevor Feature B (Band-Indikatoren) das dritte Mal denselben Code braucht.
- [ ] **Karten-Live-Test im Feld** — App starten, RX-Modus auf 40m FT8 abends,
  prüfen: Coastlines korrekt orientiert? Punkte plausible Locator-Position?
  Antenna-Farbcode wechselt sichtbar zwischen Stationen?
- [ ] **TX-Modus Live-Test** — DA1MHH/CQ rufen, dann TX-Toggle, schauen ob
  PSK-Reporter Spots in 1-2 Min erscheinen.
- [ ] **Mobile-Filter-Edge-Case dokumentieren** — Region-Calls wie `K1ABC/W2`
  werden mit-gefiltert (regex `/[A-Z0-9]{1,4}$`). Bewusst akzeptiert, im
  Docstring vermerkt. Falls in Praxis ein Region-Call regelmaessig fehlt:
  Whitelist statt Regex.

### Andere offene TODOs (Bereinigt 07.05.2026)
- [ ] Even/Odd dedizierter Timer — unabhängig vom Decoder-Thread (FT2 kritisch)
- [ ] Gain-Bias beheben — Normal-Modus Gain-Messung wenn Stats aktiv erzwingen
- [ ] CQ-Zusammenfassung RX-Liste — DeepSeek-Idee: ins QSO-Panel verschieben oder ganz raus
- [ ] Tertile-Analyse Statistik — kein Datencropping, alle Werte in 3 Drittel
- [x] **AP-Lite Test-Pipeline** — ✅ ERLEDIGT v0.95.9 (P1.AP synthetische E2E)
      + v0.95.10 (P1.AP-FIX 4-Token-Bug)
- [ ] Per-Station DT-Offset TX — encoder._station_dt_offset (nach mehr Feldtest-Daten)
- [ ] IC-7300 Fork — TARGET_TX_OFFSET dort separat messen! (eigener Branch)
- [x] **Warteliste-Screenshot** — ✅ ERLEDIGT (DL3AQJ-Freigabe + Einbau)
- [x] **DT-Korrektur konvergiert nicht** — ✅ ERLEDIGT v0.95.7 (P1.18 Wurzel-
      Fix `_DT_OFFSETS["FT8"]=3.0` Sync mit Wake-Offset)
- [ ] **NEU 26.04.:** TX-Frequenz Normal-Modus manchmal ohne Histogramm-Marker (Bug, noch nicht reproduzierbar)
- [x] **NEU 07.05. → ✅ ERLEDIGT 08.05.:** P2.ADIF-ARCHIVE Standalone-
      Helper `tools/adif_archive.py` fuer Jahresarchive aus
      `adif/hochgeladen/`. Voller Workflow durchgezogen.

---

## HEUTE ERLEDIGT (15.04.2026)

### Bugs gefixt
- [x] FT4 Einmessen: `CYCLE_SAMPLES_12K` → `self._slot_samples`
- [x] FT2 C-Library: `FTX_PROTOCOL_FT2` nativ (288 sps, kein Resample), Decodium-kompatibel bestaetigt
- [x] Diversity 50:50: Einzelmessungen, Median, 8% Schwelle, Standard/DX Modi
- [x] QSO komplett + Timeout: `WAIT_73` in Ausnahmeliste
- [x] RR73 Hoeflichkeit: max 2x wiederholen wenn Station weiter R-Report sendet
- [x] Detail-Overlay: schliesst bei Tab-Wechsel, Delete-Signal verbunden
- [x] DT-Korrektur bei Modus-Wechsel: Wert wird jetzt BEHALTEN (`keep_correction=True`)

### Neue Features
- [x] Diversity Standard/DX: Button zeigt "DIVERSITY DX", DX zaehlt schwache Stationen (SNR<-10)
- [x] Info-Dialoge: Gain-Messung + Diversity mit "Nicht mehr anzeigen"
- [x] CQ Sweet Spot: 800-2000 Hz statt gesamter Bereich
- [x] OMNI-TX: CQ-Button zeigt "OMNI CQ" wenn aktiviert
- [x] Even/Odd Spalte: "E"/"O" in RX-Liste
- [x] FT2 Frequenzen: DXZone Community-Frequenzen (40m=7.052, 20m=14.084, etc.)
- [x] RX-Filter automatisch: FT8/FT4=100-3100Hz, FT2=100-4000Hz beim Modus-Wechsel
- [x] Button "EINMESSEN" → "GAIN-MESSUNG"
- [x] DT-Korrektur beschleunigt: 2 Zyklen statt 4, 10 Betrieb statt 20, 70% Daempfung

---

## PRIO NIEDRIG — Doku/Test-Pipeline (Stand 2026-04-25)

> Mike-Entscheidung: „lassen wir so weil es super und robust schon seit Tagen läuft."
> Nur Doku korrigieren wenn ohnehin am GitHub gearbeitet wird; Test-Pipeline später,
> wenn AP-Lite real angefasst wird. Code bleibt unverändert.

### 1. Doku korrigieren: „UCB1 Bandit" ist im Code NICHT implementiert
**Betroffen:** `docs/DIVERSITY_DE.md`, `docs/DIVERSITY.md`, `README.md`, `README_DE.md` (alle GitHub-sichtbar!)

**Problem:** Doku verkauft die Diversity-Antennen-Wahl als „UCB1 (Upper Confidence Bound) Multi-Armed-Bandit". Tatsächlich implementiert `core/diversity.py::_evaluate()` jedoch **Median über 4 Messungen pro Antenne + 8 %-Schwellwert** (siehe Zeile 348-378). Kein Reward-Tracking, keine Confidence-Bound-Formel, kein kontinuierliches Lernen.

**Was tatsächlich passiert:**
- 8 Mess-Zyklen (4× A1, 4× A2)
- Median pro Antenne (robust gegen Ausreißer)
- `|s1-s2|/peak < 8%` → 50:50, sonst 70:30 zur besseren Antenne
- Nach 60 Operate-Zyklen → Neueinmessung

**Aufgabe:**
- DIVERSITY_DE.md / DIVERSITY.md: Abschnitt „UCB1 Adaptives Verhältnis" umschreiben → ehrlich „Median + 8 %-Schwellwert" benennen
- README.md / README_DE.md: gleiche Stellen prüfen + korrigieren
- UEBERGABE.md: Erwähnung „Temporal Polarization Diversity" bleibt (ist OK), nur Bandit-Sprache raus
- **Marke „Temporal Polarization Diversity" bleibt** — das Antennen-Wechsel-Konzept stimmt, nur die Bezeichnung der Entscheidungslogik ist Marketing-Quark

**Begründung Code lassen:** Aktuelle Logik läuft seit Tagen robust und stabil; UCB1 würde bei nur 2 Antennen + hoher Reward-Varianz (Fading) keinen spürbaren Vorteil bringen, aber Wartung erschweren.

**Tests:** Bereits ab v0.55 abgesichert — 7 neue Tests in `tests/test_modules.py` decken `_evaluate()` ab (Threshold-Verhalten, A1/A2-Dominanz, DX-Mode, Phase-Übergänge, Operate-Filter).

**Aufwand:** ~30 Min reine Doku-Arbeit, kein Code.

---

### 2. AP-Lite v2.2 Test-Pipeline bauen (vor jeglichem Code-Fix!)
**Betroffen:** `core/ap_lite.py`, `tests/test_modules.py` (neue Datei `tests/test_ap_lite_pipeline.py` denkbar)

**Problem:** AP-Lite ist live (`AP_LITE_ENABLED = True`) aber laut eigenem Docstring + CLAUDE.md komplett ungetestet. Im Code stehen drei explizite TODOs vom Autor:
1. `_build_costas_reference`: „Aktuell: vereinfachte Näherung" — kein echtes 7×3-Costas-Pattern mit FSK-Tönen
2. `align_buffers`: „Validieren! Insbesondere Phasenkorrektur für kohärente Addition" — Phase wird aktuell NICHT korrigiert; bei kohärenter Addition kritisch (sonst Auslöschung statt Verstärkung)
3. `SCORE_THRESHOLD = 0.75` — geraten, nie kalibriert
4. Zusatz-Verdacht: `encoder.generate_reference_wave()` muss echte FT8-Symbole produzieren — Stub-Verhalten würde Korrelation zu Müll machen

**Reihenfolge unverhandelbar:**
1. **ZUERST** synthetische End-to-End-Tests bauen — verrauschtes FT8-Signal generieren → 2 Slots erzeugen → durch `try_rescue` schicken → prüfen ob die richtige Nachricht rauskommt
2. Dann zeigen die Tests welcher der 4 Verdachtspunkte tatsächlich Bugs sind
3. Dann gezielt fixen mit Test als Schutznetz
4. Erst dann Feldtest

**Warum nicht direkt fixen:** Ohne Test ist jede „Verbesserung" Schuss ins Blaue — könnte einen funktionierenden Teil kaputt machen oder einen anderen Bug übersehen.

**Aufwand Pipeline:** ~1-2 h. Brauchen FT8-Signal-Generator (vermutlich über vorhandenen `Encoder.generate_reference_wave`), AWGN-Rauschen-Helfer, Test-Cases mit unterschiedlichen SNR-Bereichen.

**Aufgabe für nächste Session:** Test-Pipeline aufsetzen und als Baseline laufen lassen — dann sehen wir was wirklich kaputt ist.

---

## OFFEN — Naechste Schritte

### CQ-Frequenz-Algorithmus (core/diversity.py)
- [x] **Auswahllogik Score-basiert (v0.58):** `_score_gap()` ersetzt Median-Distance — Lückenbreite
  dominiert (1 Hz = 1 Punkt), Nachbarn ±1 Bin = 50 Hz Strafe pro Station, ±2 Bins halb so viel,
  Median-Distance nur als 0.01-Tiebreaker.
- [x] **Fester Sweet-Spot 800-2000 Hz (v0.58):** `SWEET_SPOT_MIN_HZ=800` / `MAX_HZ=2000` —
  TX-Frequenz nur noch im Sweet-Spot. Median wird nur über Sweet-Spot-Stationen berechnet.
- [x] **Modus-abhängige Dwell + Recalc (v0.58):** `set_mode()` setzt FT8=4z, FT4=8z, FT2=16z
  Dwell (~60 s einheitlich), Recalc = 5 × Dwell = ~300 s.
- [~] **Frequenzwechsel im Statistics-Modus sperren — VERWORFEN (Mike-Entscheidung 25.04.2026):**
  Variance, kein Bias. Wechsel mitteln sich über 22.000+ Zyklen raus, treffen alle Modi gleich.
  Sticky-Gap (50 Hz) + verfeinerte Kollision reduzieren Wechsel-Frequenz ausreichend.
- [x] **Kollisionserkennung verfeinert (v0.58):** `n_direct >= 2` ODER `n_in_band >= 3`
  (n_in_band inkl. current_bin). QSO-Schutz unverändert.
- [x] **Sticky Gap (v0.58):** Bleibt bei aktueller Frequenz wenn im Sweet-Spot, keine
  Kollisions-Schwelle erreicht und neue Lücke nicht > +50 Hz breiter. `_measure_gap_around()`
  refresht aktuelle Lück-Breite nach Sticky-Hit. `reset()` setzt `_current_gap_width_hz=0`.

### Propagation (core/propagation.py)
- [x] **60m Propagations-Balken:** Interpolation aus 40m+80m implementiert in
  `core/propagation.py::_fetch_raw()` (L181-190). Mittelwert per _CONDITION_ORDER-Index,
  day+night getrennt. (23.04.2026 erledigt)

### UI-Verbesserungen (SPAETER)
- [x] **Statusbar DT-Anzeige:** Zeigt `DT: —` / `DT: Korrektur` (grün) / `DT: Aktiv` —
  kein exakter Wert mehr. Implementiert in main_window.py::_update_statusbar() (Zeile 558-565).
- [x] **Statusbar Mode+Filter:** Zeigt `FT8 40m | 14074.000 kHz | Filter: 100-3100 Hz` —
  Filter-String pro Modus in _FILTERS dict. Implementiert in _update_statusbar() (Zeile 573-609).
- [ ] **Spalten-Konfig in Settings:** RX-Spalten ein/ausblendbar + gespeichert/geladen (Slot, Ant, DT, etc.)

### RX-Liste (UI)
- [x] **Sortierung UTC absteigend:** Bereits implementiert — `rx_panel.py:276` sorted insert mit absteigendem HHMMSS-Vergleich + `_set_sort("time", reverse=True)`. (2026-04-25 verifiziert)
- [ ] **CQ-Zusammenfassung ueberarbeiten:** Aktuell werden CQ-Rufe zu "CQ ×N" zusammengefasst — kaum sichtbar.
  Optionen (Mike entscheidet):
  (a) CQ-Rufe ins QSO-Panel verschieben: erste Zeile "CQ", ab 5× nur noch "CQ ×6" mit aktualisierter Zahl
  (b) CQ-Rufe komplett aus RX-Liste entfernen (sauberere Liste, weniger Ablenkung)
- [x] **Alte CQ-Rufe automatisch loeschen:** CQ-Rufer bekommen 300s Aging (5 Min) in
  `core/station_accumulator.py::remove_stale`, nicht-CQ bleibt bei 75s, active_qso bei 150s.
  Test: `test_accumulator_cq_longer_aging`. (23.04.2026 erledigt)

- [x] **Answer-Me Highlighting (DeepSeek-Idee):** Wenn eine Station unser Callsign in ihrer Nachricht
  sendet (z.B. "DA1MHH -07"), Zeile in der RX-Liste GELB hinterlegen. Verhindert dass wir ein QSO-Angebot
  uebersehen wenn gerade viel Traffic ist. Prio: hoch — direkter Nutzwert beim Pileup.
  (25.04.2026 erledigt — v0.57: Farbe `#5A4A10` Gold + Bold an 3 Stellen in `ui/rx_panel.py`)

### Statistik & Analyse (nach mehr Messdaten)
- [ ] **DIAGRAMM-AUSWERTUNG 20m — für GitHub (wenn genug Daten vorhanden):**
  Zwei Diagramme, Skripte fertig unter `tools/`:
  1. `tools/plot_20m_stations.py` — Stationsanzahl über Zeit: Normal / Div Standard / Div DX
     Aufruf: `./venv/bin/python3 tools/plot_20m_stations.py --date 2026-04-21`
  2. `tools/plot_ant2_performance.py` — ANT2 Performance stündlich:
     Oben: Ant2 Win-Rate % (wie oft ANT2 besser als ANT1)
     Unten: Ø ΔSNR gesamt + Ø ΔSNR wenn A2 gewinnt (in dB)
     Aufruf: `./venv/bin/python3 tools/plot_ant2_performance.py --band 20m --date 2026-04-21`
  **Wann ausführen:** Nach A/B-Test 20m (alle 10 Min Normal ↔ Div DX ab ~10:00 UTC).
  Mind. 3 Stunden Daten → dann Diagramme generieren + in STATISTICS.md oder README einbetten.
  Vorläufige Ergebnisse (2026-04-20, wenig Daten):
    Normal Ø 35.4 St. | Div Standard Ø 37.7 (+6%) | Div DX Ø 41.5 (+17%)
    ANT2 Win-Rate 20m: ~27-29% | 40m Nacht: 21-31% | Ø ΔSNR -0.29 dB (A1 leicht dominant)

- [ ] **ANT1 vs ANT2 SNR direkt loggen:** Pro Station beide SNR-Werte erfassen (ant1_snr, ant2_snr, delta).
  Aktuell: nur "Ant2 Wins" als Zaehler. Ziel: "ANT2 war im Schnitt +X dB besser bei Y% der Stationen".
- [ ] **Statistik-Diagramme fuer GitHub:** matplotlib-Script das aus statistics/*.md automatisch
  SVG/PNG-Charts generiert (Normal vs Diversity_Normal vs Diversity_Dx, pro Band + Uhrzeit).
  Einbetten in README oder eigene STATISTICS.md.
- [ ] **Auswertung per Tertile-Analyse — KEIN Datencropping (Entscheidung final):**
  Alle Messwerte behalten, in drei gleich grosse Drittel aufteilen, Normal vs Diversity pro Tertile
  separat vergleichen. Kein Wegwerfen von Extremwerten.
  - Unteres Drittel (33%): Schlechte Bedingungen — bringt Diversity ueberhaupt was?
  - Mittleres Drittel (33%): Alltagsbetrieb — typischer Gewinn im Normalbetrieb
  - Oberes Drittel (33%): Spitzentage / Sporadic-E — steigert Diversity noch weiter oder Saettigung?
  Begruendung: Gerade die oberen Messtage (DX-Oeffnungen) zeigen den groessten Diversity-Effekt.
  Die wegzuwerfen wuerde das erreichte Ergebnis beschneiden. Tertile behält ALLE Daten, basiert
  auf Raengen — bimodale Verteilung (Normal-Tage vs Sporadic-E) kein Problem.
  Implementierung: pandas.qcut(stations, q=3) → pro Label [low/medium/high] Mittelwert + Diff %.
  Script liest aus statistics/*.md, vergleicht Modi pro Tertile, gibt Tabelle aus.
- [ ] **WICHTIG — Gain-Bias beheben (faire Vergleiche!):** DX-Modus macht VOR dem Start IMMER
  automatisch eine Gain-Messung (optimierter Empfangspegel). Normal-Modus nur freiwillig.
  → DX startet systematisch mit besserem Gain → DX sieht im Vergleich kuenstlich besser aus.
  Fix: Wenn Statistik-Erfassung aktiv ist, Gain-Messung fuer ALLE Modi erzwingen (nicht nur DX).
  Wahrscheinlich nur ein Flag in der Gain-Logik — geringer Aufwand, grosser Effekt auf Fairness.

- [ ] **Gain-Bias Compensator (DeepSeek-Idee):** Parallel-Dekodierungen (beide Antennen hören gleiche
  Station) nutzen um systematischen SNR-Offset zwischen ANT1 und ANT2 zu messen. Über viele Stationen
  mitteln → Offset in dB speichern → bei Diversity-Auswahl-Schwelle abziehen. Macht Vergleich fair
  auch OHNE vorher beide Gain-Messungen abzugleichen. Komplex aber elegant — für spätere Phase.

### Bugs
- [ ] **VERMUTLICHER BUG — Freie TX-Frequenz im Normal-Modus (unregelmäßig):**
  Beobachtung (Mike, 2026-04-25): Im Normal-Modus wird die freie TX-Frequenz aus dem
  Histogramm manchmal NICHT gesetzt — kein Marker im Histogramm sichtbar, TX bleibt auf
  alter Frequenz. Im CQ-Modus funktioniert `get_free_cq_freq()` + Histogramm-Marker
  zuverlässig (`mw_qso.py:109–115`).
  Verdacht: Timing-Problem oder Überschneidung mit Band/Modus-Wechsel — noch nicht
  reproduzierbar. **Kein Code-Fix bis weiteres Auftreten dokumentiert ist.**
  Nächste Schritte: Konsolen-Ausgabe `[CQ] TX-Frequenz auf X Hz` beobachten, ob
  `get_free_cq_freq()` None zurückgibt oder der Wert gleich dem aktuellen ist.

- [x] **RX-Liste + QSO-Fenster nicht geleert bei Wechsel (BUG):**
  Jetzt gelöscht in: Band-Wechsel, Modus-Wechsel, Normal↔Diversity
  (_on_rx_mode_changed), _enable_diversity, _disable_diversity,
  RX ON/OFF (_on_rx_panel_toggled). (23.04.2026 erledigt)

- [ ] **Even/Odd Slot-Anzeige asynchron (FT2/FT4/FT8 pruefen):** Die Even/Odd-Anzeige oben im
  QSO-Fenster springt bei FT2 (3,75s Zyklen) moeglicherweise nicht exakt mit der echten Slot-Zeit um.
  Bei FT8 (15s) und FT4 (7,5s) ebenfalls verifizieren. Anzeige muss IMMER exakt der Slot-Zeit
  entsprechen, sonst ist sie wertlos.
  DeepSeek-Verdacht: Timing/Threading-Problem (nicht Logik-Fehler). FT2 hat kuerzestes Fenster
  (3,75s), daher dort am kritischsten. Loesung: eigenen dedizierten Timer fuer Slot-Anzeige,
  unabhaengig vom Decoder-Thread.
- [x] **Warteliste:** Queue akzeptiert jetzt Grid + Report (EA3FHP-Fix, v0.36)
- [x] **Logbuch-Loeschen:** Funktioniert (bestaetigt 15.04)
- [x] **km Fallback:** Callsign-Prefix Naeherung (~km) im Logbuch eingebaut (v0.37)

### Gain-Messung Scoring (UNTERSUCHEN)
- [ ] **Scoring-Logik pruefen:** Zeigt "optimal" Gain mit WENIGER Stationen als andere Gains.
  Aktuell: waehlt nach bestem Top-5 SNR. Aber Stationsanzahl wird daneben angezeigt → verwirrend.
  Optionen: (a) Scoring klar beschriften "Bester SNR", (b) Stationsanzahl statt SNR als Kriterium,
  (c) Kombination aus beiden, (d) Alle Zyklen-Durchschnitt pruefen (nur letzte Messung oder Schnitt?)
- [x] **Logging:** Jede Messung protokollieren fuer spaetere Analyse
  (25.04.2026 erledigt — v0.57: `_log_gain_result()` in `ui/mw_radio.py`, append-only `~/.simpleft8/gain_log.md`,
  loggt Normal-Kalibrierung + Diversity-Messung mit UTC + Band/Mode + ANT1/ANT2 Gains + Ø SNRs)

### Feldtest (NUR MIT RADIO)
- [ ] **FT2 Feldtest:** Ein bestätigtes QSO gefahren (Decodium-kompatibel bestaetigt). Ausführliches Testen auf 40m (7.052 MHz) / 20m (14.084 MHz) steht noch aus — DT-Korrektur, Timing-Randfahlle, laengere Sessions.
- [ ] **DT-Korrektur v2:** Konvergenz pruefen (soll jetzt 3-6 Min statt 12-18 Min dauern)
- [ ] **AP-Lite Threshold:** 0.75 kalibrieren → dann `AP_LITE_ENABLED = True`
- [ ] **OMNI-TX + Auto-Hunt:** Integriert (Easter Egg: Klick auf Versionsnummer). Feldtest ausstehend.
  GitHub: Darf als Feature "Optimierter CQ-Ruf (OMNI-TX)" erwaehnt werden, aber NICHT wie man es aktiviert.
  TODO: EN+DE README/Hilfe-Seite erstellen mit: Was ist OMNI-TX, wie funktioniert es (Even+Odd abwechselnd),
  was erwartet man (mehr Chancen gehoert zu werden), Einschraenkungen (Double-TX-Pausen).

### TX-Optimierungen — PRIO NIEDRIG
- [ ] **Per-Station DT-Offset beim QSO-Anruf (encoder._station_dt_offset):**
  Wenn Station X mit DT=+1.2s angerufen wird, die eigene TX um +1.2s verschieben →
  Signal landet im Zentrum ihres Decode-Fensters. Globale DT-Korrektur (ntp_time) bleibt
  unberührt. Nach QSO-Ende/Abbruch automatisch reset auf 0.0.
  Implementierung: `encoder._station_dt_offset = station.dt` beim Ansprechen,
  `encoder._station_dt_offset = 0.0` in qso_state auf IDLE/TIMEOUT.
  Kein Diversity-Feature — reine TX-Pfad-Optimierung.
  > Mike-Entscheidung 2026-04-25: PRIO NIEDRIG — erst nach mehr Feldtest-Daten.

### Langfristig
- [ ] IC-7300 Fork: `radio/ic7300.py` implementieren
- [ ] QSO-Resume bei App-Neustart

> "Band Map (visuelle Frequenz-Belegung)" gestrichen 2026-04-25 — das vorhandene
> Diversity-Histogramm mit TX-Cursor (control_panel) deckt den FT8-relevanten
> 100–1550 Hz-Bereich bereits ab. Ein separater Wasserfall über das gesamte Band
> ist für FT8 nicht nötig.
- [x] **RF-Power-Presets pro Band+Watt (lernendes System):** ERLEDIGT in v0.56 (2026-04-25)
  Implementierung: `core/rf_preset_store.py` mit Hybrid-Lade-Strategie (exakter Treffer →
  lineare Interpolation/Extrapolation → Default), atomic JSON-Write, Plausibilitäts-Warnung,
  Migration aus altem `rfpower_per_band`-Eintrag. Pro Radio (FlexRadio jetzt, IC-7300 später)
  separate Tabelle. UI: SettingsDialog-Section "RF-Presets" mit Tabelle + Reset-Buttons
  (disabled während aktivem TX). Selbstheilend: bei jedem Konvergenz-Übergang wird
  überschrieben. Tests 178 → 197 grün. Siehe HISTORY.md "v0.56".

---

## ERLEDIGTE FEATURES (Kurzform)

### 15.04.2026
- FT2 nativ + Decodium-kompatibel (Source Code verifiziert: NN=103, NSPS=288, 4-GFSK)
- FT2 QSO erfolgreich abgeschlossen (Empfang + Senden funktioniert)
- Diversity Standard/DX Modi + DX-Score (schwache Stationen <-10dB)
- QSO-Bugs: WAIT_73 Timeout, RR73 Hoeflichkeit (max 2x), Overlay
- DT-Korrektur v2: schneller, gedaempft, pro Modus gespeichert (~/.simpleft8/dt_corrections.json)
- RX-Filter automatisch pro Modus (FT8/FT4=3100Hz, FT2=4000Hz)
- CQ Frequenz Sweet Spot (800-2000 Hz)
- OMNI-TX CQ Button, Even/Odd Spalte RX + QSO-Panel [E]/[O]
- CQ-Zeilen zusammengefasst (CQ ×24 statt 24 Einzelzeilen)
- QSO-Panel Auto-Trim (max 40 Zeilen)
- Even/Odd Anzeige modus-abhaengig (nicht mehr hardcoded 15s)
- FT2 Frequenzen DXZone (40m=7.052, 20m=14.084)
- Info-Dialoge mit "Nicht mehr anzeigen"

### 14.04.2026
- FT4/FT2 Integration (Decoder, Encoder, Timing, UI)
- DT-Korrektur kumulative Strategie
- Presence Timer, Auto-Hunt, Diversity Fixes

### 13.04.2026
- Propagation-Balken (HamQSL), Radio-Abstraktion getestet
- AGC deaktiviert (kollidiert mit Noise-Floor-Norm)
- Drift-Kompensation entfernt (0 Nutzen)

### 12.04.2026
- Radio-Abstraktion komplett (v0.25-v0.28)
- main_window.py Split (1755→473 Zeilen, 4 Mixins)
- AP-Lite v2.2, OMNI-TX Hooks, DeepSeek Full Review
