# HANDOFF — SimpleFT8

## Stand 2026-05-14 morgens: v0.97.21 Bundle D — UI-Tweaks nach P50-Field-Test

**Mike-Trigger:** P50 funktioniert super (Field-Test ✓), Memory-Leak war
TTS-Server (nicht SimpleFT8). 5 UI-Feinschliffe als Bundle:

**Code v0.97.21:**
- **A** Settings „Sichtbare Bänder" Block: Spacing 6→10 + mehr Top-Padding
- **B** DT-Anzeige `+0.0`/`-0.0` → `0.0` (neuer Helper `_format_dt`)
- **C** Even/Odd-Anzeige oben → Filter-Buttons (Normal-only), live RX-Panel-
  Filterung über Signal `slot_filter_changed`, exklusive Toggle-Logik
  (3 Zustände mit 2 Buttons)
- **D** Diversity-Modus: Buttons ausgeblendet (zu komplex), QSO/Logbuch
  füllen Platz, Filter immer reset bei Modus-Wechsel
- **E** NEU Slot-Progress-Bar in Statusbar (unten rechts) — Cyan (Even)
  / Magenta (Odd), dynamische cycle_dur (FT8/FT4/FT2)

**Tests:** **1166 grün** (1155 + 11 Bundle-D T1-T11).
**Backup:** `Appsicherungen/2026-05-14_v0.97.20_vor_bundle_d/`.
**Workflow:** V1→V2 (10 Findings + 9 Fragen)→R1 7/10 (1 KRITISCH + 4
SOLLTE alle übernommen)→V3 (16 ACs Compact-fest)→Code→Final-R1 0 KP
„Push freigegeben".
**Push:** pending bis Mike's Field-Test F1-F8.

### Field-Test-Checkliste F1-F8 (Mike nach App-Restart)

| # | Test | Erwartung |
|---|---|---|
| **F1** | Settings → Tab „FT8 & Diversity" → Bänder-Block | Sichtbar mehr Luft |
| **F2** | RX-Panel DT-Spalte | Kein `+0.0`/`-0.0`, nur `0.0` für kleine Werte |
| **F3** | Normal-Modus: EVEN/ODD oben | Klickbare Buttons (orange-Highlight wenn aktiv) |
| **F4** | Klick EVEN | Nur Even-Stationen im RX-Panel sichtbar |
| **F5** | Erneut EVEN oder ODD klicken | Filter wechselt korrekt (3 Zustände) |
| **F6** | Modus → Diversity | EVEN/ODD verschwinden, QSO/Logbuch breiter |
| **F7** | Modus zurück → Normal | Filter auf „beide" zurückgesetzt |
| **F8** | Unten rechts Statusbar | 15s-Slot-Balken füllt sich, wechselt Cyan↔Magenta |

### Vorgänger-Field-Tests pending

- v0.97.20 P50 Bänder-Sichtbarkeit ✓ (Mike: „funktioniert super")
- v0.97.19 P34-Stufe2 — F1-F10
- v0.97.18 Toast-Bundle — Medaillen 🥇🥈🥉
- v0.97.17 P46 Bandpilot Normal-Reintegration

---

## Stand 2026-05-13 spätnachmittags: v0.97.20 P50 — Bänder-Sichtbarkeit

**Code:** v0.97.20 — User kann im Settings-Dialog (Tab „FT8 & Diversity")
nicht benötigte Bänder abwählen. Neue API `Settings.get/set_enabled_bands`
mit defensiver Filterung. UI: 3×3-QCheckBox-Raster, Min-1-Logik (letzte
aktive Checkbox geblockt), Reset-Button setzt alle 9 zurück. ControlPanel
`set_visible_bands` mit R1-F1-current_band-Guarantee + R1-F2-Prop-Bar-
mitverstecken. MainWindow `apply_visible_bands` wird beim App-Start und
nach Settings-Apply gerufen.

**Bandpilot NICHT angefasst** — R1-Q1-Empfehlung war Halluzination,
`recommend_for_hour()` empfiehlt nur RX-MODI (Normal/Std/DX) auf
aktuellem Band, keine Band-Wechsel.

**Tests:** **1155 grün** (1144 vor P50 + 11 neue P50-Tests T1-T11).
**Backup:** `Appsicherungen/2026-05-13_v0.97.19_vor_p50_bands_visibility/`.
**Workflow:** V1→V2 (B1-B10 + 8 Fragen)→R1 7/10 (2 KRITISCH + 2 SOLLTE)
→V3 (14 ACs)→Code (6 atomare Commits)→Final-R1 „Push freigegeben".
**Push:** pending bis Mike's Field-Test-OK.

### Field-Test-Checkliste F1-F8 (Mike nach App-Restart)

| # | Test | Erwartung |
|---|---|---|
| **F1** | Settings → Tab „FT8 & Diversity" | „Sichtbare Bänder"-Block sichtbar, alle 9 angekreuzt |
| **F2** | 60m + 80m abwählen → Speichern | Band-Panel zeigt 7 Bänder + Lücken in Zeile 2 |
| **F3** | Settings nochmal → App-Restart | 60m/80m noch abgewählt |
| **F4** | Alle bis auf 1 abwählen | Letzte Checkbox disabled + Tooltip „Mindestens ein Band muss aktiv sein" |
| **F5** | 20m aktiv, 20m abwählen → OK | 20m bleibt sichtbar (R1-F1 current_band-Guarantee) |
| **F6** | 60m aktiv mit deaktivierten Bändern → Propagation-Update | Keine Geister-Pulse auf versteckten Bändern (R1-F2) |
| **F7** | Reset-Button in Settings | Alle 9 Checkboxen wieder angekreuzt |
| **F8** | settings.json prüfen | `enabled_bands`-Key vorhanden nur wenn User Toggle gemacht hat |

### Vorgänger-Field-Tests pending

- v0.97.19 P34-Stufe2 — F1-F10 (Statik-Pipeline raus)
- v0.97.18 Toast-Bundle — Medaillen 🥇🥈🥉
- v0.97.17 P46 Bandpilot Normal-Reintegration

---

## Stand 2026-05-13 nachmittags: v0.97.19 P34-Stufe2 — Statik-Pipeline raus

**Code:** v0.97.19 — Statik-Ratio-Pipeline (Phase 3 Mess, 90 s UI-Sperre,
6-Slot-Mess-Pattern, 1 h-Re-Mess-Frist, MessStatusDialog, Settings-Toggle,
PresetStore-Ratio-API) komplett entfernt. Dynamic
(`DynamicDiversityController`) ist jetzt einziger Pfad für Ratio-
Bestimmung. ~250 LOC raus, 8 Test-Files gelöscht, 1 neuer (test_p34_stufe2).
**Tests:** **1144 grün** (1239 vor Stufe2 minus Statik-Tests plus 15 neue
P34-Stufe2-Tests).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.18_vor_p34_stufe2/`.
**Workflow V1→V2→R1→V3:** R1-F1 KRITISCH (Radio.ip + activate Race) und 6
weitere Findings alle in V3 eingearbeitet. **Final-R1:** "Keine Bugs, keine
kritischen Risiken. 6 Prüfpunkte alle erfüllt — Push freigegeben."
**Bonus:** 80m-Abbruch-Bug (13.05. Mike-Beobachtung) ist obsolet — keine
Mess-Phase mehr.
**Push:** pending bis Mike's Field-Test-OK.

### Field-Test-Checkliste F1-F10 (Mike nach App-Restart)

| # | Test | Erwartung |
|---|---|---|
| **F1** | App-Start | Wie heute — 20m FT8 Normal |
| **F2** | Normal → Diversity DX (Gain frisch) | Kein DXTuneDialog. Antennen-Panel zeigt sofort "● DYNAMISCH (live) — RX Ant1", Ratio 50:50. In ~75 s erste Dynamic-Auswertung. |
| **F3** | Normal → Diversity DX (Gain stale auf 80m) | DXTuneDialog öffnet. Cancel → kein Diversity. Bei Erfolg → wie F2. |
| **F4** | Bandwechsel mit aktiver Diversity | Sofort wieder Phase=operate, 50:50, Buffer leer. **Keine 90-Sek-Sperre mehr**. |
| **F5** | Modus-Wechsel (FT8→FT4) mit Diversity | Wie F4. |
| **F6** | scoring_mode (Standard→DX) mit Diversity | Buffer leer, Ratio 50:50, neu sammeln. |
| **F7** | 1 h ohne QSO mit Diversity AN | **Keine automatische Re-Mess.** Dynamic läuft weiter. |
| **F8** | Toggle in Einstellungen | Settings-Dialog hat **KEINEN** Toggle "Antennen-Verhältnis dynamisch anpassen" mehr. |
| **F9** | Antennen-Panel-Label | Immer "● DYNAMISCH (live) — RX Ant1/Ant2". **Niemals** "Messung X/6" oder "Diversity Neuberechnung in X Min." |
| **F10** | App-Quit mit Diversity aktiv | Saubere Abschaltung. Kein Mess-Modal-Phantom. |

### Naechste Schritte (Plan)

1. **Mike-Field-Test P34-Stufe2** — F1-F10 sauber durchchecken
2. **Bänder-Deaktivierung Feature** (separates Folgeprojekt nach P34-Stufe2)

### Tech-Debt nach Final-R1 (v0.98+)

- `control_panel.update_diversity_ratio` Signatur hat noch
  `**_ignored_legacy` als Legacy-Schluck — in v0.98 endgültig bereinigen.

---

## Stand 2026-05-13 mittags: v0.97.18 Toast-Bundle (Medaillen + 6s)

**Code:** v0.97.18 — Bandpilot-Toast/Manual-Dialog Ranking-Marker
🥇🥈🥉 statt `"1./2./3."` (Mike-Feedback nach P46-Field-Test). Toast-
Self-Close 5s → 6s. R1-SOLLTE-Defensive: Env-Var-Fallback
`SIMPLEFT8_TEXT_MARKERS=1` aktiviert Text-Marker fuer Systeme ohne
Color-Emoji-Renderer.
**Tests:** **1239 grün** (1233 + 6 Toast).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.17_vor_toast_bundle/`.
**Workflow:** V1→V2 (2 Konstanten-Findings)→R1 9/10 (1 SOLLTE Fallback)
→V3 alle uebernommen→Code→Final-R1 0 Findings „Push freigegeben".
**Push:** pending bis Mike's visuelle Bestaetigung (Bandwechsel mit
sichtbaren Medaillen).

### Naechste Schritte (Plan)

1. **Mike-Field-Test Toast** — kurz Bandwechsel, schauen ob 🥇🥈🥉
   visuell besser ist und 6s zum Lesen reichen
2. **P34-Stufe2: Statik-Pipeline raus** (Mike-OK 13.05.) — voller
   Workflow ~4-5h. Macht 80m-Abbruch-Bug obsolet
3. **Spaeter: Baender-Deaktivierung Feature** (Settings-Checkboxen
   pro Band)

---

## Stand 2026-05-13 mittags: v0.97.17 P46 Bandpilot Normal-Reintegration

**Code:** v0.97.17 — P35-Bug-E (Bandpilot blockt Normal) zurueckgenommen.
Bandpilot vergleicht 3-Wege (Normal/Std/DX), darf Normal als Empfehlung
vorschlagen, current=normal startet Bandpilot. R1-F2 Doppelaufruf-
Refactor in `_set_rx_mode_direct`, R1-F3 TX-pending mit Modus-
Konsistenz-Check.
**Tests:** **1233 grün** (1227 + 8 P46 − 2 geloeschte alte Block-Tests).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.16_vor_p46_bandpilot_normal/`.
**Workflow:** V1→V2 (16 Findings, L16-Diversity-Cleanup-Frage geklaert)
→R1 8/10 mit 1 KRITISCH + 2 SOLLTE + 1 KOENNTE → V3 alle uebernommen
→Code→Final-R1 9/10 „Push freigegeben", 0 KRITISCH, 1 KOENNTE
(Doku-Update bandpilot_de.md+en — sofort gefixt).
**Push:** pending bis Mike's Field-Test-OK.

### Field-Test (Mike braucht echte Bandwechsel)

- **F1:** Bandwechsel von Normal-Modus auf neues Band → Bandpilot
  aktiv, wenn Daten in Stunde vorhanden → Toast „wechselt zu X"
- **F2:** Bandwechsel auf neues Band mit ausreichend Daten in allen
  3 Modi und Normal als Top-1 → Auto wechselt zu Normal (zuvor
  geblockt)
- **F3:** Manuell-Dialog erscheint mit 3 Buttons, Normal-Button
  klickbar
- **F4:** Bei TX-laufend: pending wird gespeichert. Wenn User
  zwischendurch manuell Modus wechselt → pending wird verworfen
  (Print-Log `[Bandpilot] Pending verworfen — Modus zwischenzeitlich`)

---

## Stand 2026-05-13 morgens: v0.97.16 P14 DT-Werte-Symmetrie

**Code:** v0.97.16 — P14 MAD-basierter Outlier-Filter + DEADBAND-Reduktion.
Mike beobachtete im RX-Panel 11/20 negative DT-Werte mit Ausreißern bei
-1.2/-0.7/-0.4, dadurch wandert Median nach unten und zieht Korrektur
nicht auf 0 zentriert. Lösung: Hampel-Filter (k=2.5) entfernt Outliers
adaptiv vor Median-Berechnung; DEADBAND 0.05 → 0.02 verhindert
Einfrieren am Rand (R1-F1 KRITISCH).
**Tests:** **1227 grün** (1217 + 10 P14, plus 1 bestehender Test
angepasst weil DEADBAND-Wert geändert).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/`.
**Workflow:** V1→V2 (10 Self-Review-Findings)→R1 5/10 mit 2 KRITISCH
(F1 Deadband-Einfrier, F2 Wurzel nicht untersucht)→V3 alle Findings
übernommen, Trim durch MAD ersetzt→Code→Final-R1 9/10 „Push freigegeben",
0 KRITISCH, 2 nicht-blockierende Findings beide gefixt.
**Push:** pending bis Mike's mehrfache Field-Test-Bestätigung.

### Field-Test ✅ Bestätigt (13.05.2026 09:38 UTC)

Mike-Screenshots nach App-Neustart + 30 Min 30m Normal:
- Korrektur drift: 0.2705 → 0.2285 (System aktiv, kein Einfrieren)
- Verteilung: 5 negativ / 5 positiv / 10 nahe Null (vorher 11/-1/+8)
- Outliers (-0.8, -0.4) im Panel sichtbar aber NICHT in der Korrektur
  → MAD-Filter wirkt intern wie geplant
- Diversity-Slot: ebenfalls symmetrisch, A1+A2 gleich gut

**Push pending nur noch weil Bundle B' + Bundle C field-tests offen.**

---

## Stand 2026-05-13 nachts: v0.97.15 Bundle C (P10 + P13)

**Code:** v0.97.15 — 2 UI/Netz-Bugs als Bundle:
**P10 PSK-Backoff-Reset** (BACKOFF_MAX_S 60→10 Min, `_Backoff`
thread-safe via Lock, public `reset_backoff()` + `set_mode()`,
Auto-Trigger bei Band/Modus-Wechsel — Karten + Statusbar getrennt)
und **P13 RX-Panel-Slot-Times** (UTC-Spalte zeigt jetzt
Slot-Boundary statt Wall-Time; Fix in `add_message` UND
`_populate_row` plus mixed-Type-safe Sort).
**Tests:** **1217 grün** (1204 + 13 Bundle C).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.14_vor_bundle_c/`.
**Workflow:** V1→V2 (fand 2-Pfade-Bug Statusbar vs Karte)→R1 (3 KP +
3 S + 2 K + 3 H, davon 1 KP Thread-Safety-Race in `_Backoff`)→V3→
Code→Final-R1 (entdeckte zusätzlich Mode-Sync-Bug KP-1 — `_mode`
wurde nie aktualisiert nach Mode-Wechsel; sofort gefixt mit
`set_mode()`).
**Push:** 3 atomare Commits, gleich folgend.

### Nächste Schritte — Field-Test 5 Punkte (V3 §Field-Test)

- **F1:** Bandwechsel → PSK-Statusbar ~5 Sek neue Daten (statt bis
  5 Min Lag)
- **F2:** Modus-Wechsel analog F1
- **F3:** RX-Panel UTC-Spalte zeigt Slot-Boundaries (10:51:30 statt
  10:51:42) bei FT8
- **F4:** Bei FT4/FT2 entsprechende Boundaries
- **F5:** Karte bei langem PSK-Server-Outage erholt sich ≤10 Min
  statt ≤60 Min

---

## Stand 2026-05-13 nachts: v0.97.14 Bundle B' (P32 + P33)

**Code:** v0.97.14 — Bundle B' mit 2 UI-Bugs:
**P32 RX-Panel-Spalten-Persist** (Spalten-Auswahl via Rechtsklick
bleibt jetzt über App-Restart hinweg; neuer Settings-Key
`rx_panel_hidden_cols`, defensiv gegen ungültige Werte +
COL_MSG-Schutz; persistiert via Signal-Pattern wie `country_filter`)
und **P33 QSO-Komplett-Reihenfolge** (`✓ QSO mit X komplett`-Zeile
erschien NACH nächstem CQ statt davor; Fix per 2-Signal-Split
`qso_confirmed_visual` SOFORT bei 73-Empfang für UI + `qso_confirmed`
nach Courtesy-Send für alle anderen Ops wie OMNI-Resume).
**Tests:** **1204 grün** (1192 + 12 Bundle B).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.13_vor_bundle_b/`.
**Workflow:** V1→V2 (Self-Review fand OMNI-Race in V1-Variante-A)→R1
(2 KP + 2 S + 2 K)→V3→Code→Final-R1 („Push freigegeben", 0 KP, 1 S
sofort gefixt: try/except um settings.save).
**Push:** 3 atomare Commits, gleich folgend.

### Nächste Schritte (4-Punkte-Field-Test V3 §Field-Test)

- ✅ **F1:** Spalten ausblenden, App-Quit, App-Start → bleiben aus
  **(13.05.2026 09:38 UTC bestätigt)**
- 🟡 **F2:** Bei QSO `← Empf. X 73` und `✓ QSO mit X komplett` im
  SELBEN Slot, BEVOR die nächste OMNI-CQ-Zeile
- 🟡 **F3:** Nach Courtesy-73-Send: OMNI resumed wie heute, kein
  Doppel-Eintrag
- 🟡 **F4:** WAIT_73-Timeout (3 Slots ohne 73) → trotzdem ✓ ohne Hang

---

## Stand 2026-05-13 abends: v0.97.13 P48 DT-System aufräumen + tunen

**Code:** v0.97.13 — Vier zusammenhängende DT-Verbesserungen basierend
auf 10.212-Einträge-Analyse. **P48-A:** FlexRadio-Hardware-Werte
(`tx_buffer_s=1.3`, `rx_hardware_offset_default_s=0.26`) aus Code in
neuen Settings-Block `radio_timing` ausgelagert. Encoder bekommt jetzt
`tx_buffer_s`-Parameter, `TARGET_TX_OFFSET` Modul-Konstante entfernt.
**P48-B:** Cross-Modus-Fallback in `_load_for_current_key` — FT4/FT2
startet mit FT8-Wert vom gleichen Band (FT8 hat solidesten Median).
**P48-C:** Hardware-Default 0.26 als Kaltstart statt 0.0 — neuer
Band-Start liegt sofort fast am echten Wert. **P48-D:** Schnell-
Konvergenz im 1. Slot wenn ≥10 Stationen mit Stddev<0.1 → 1 statt
2 Slots (~15s statt ~30s Konvergenz auf FT8 abends).
**Wichtig:** `_is_initial`-Bug-Fix (R1-V2 Finding 1) — sonst hätte
Hardware-Default 0.26 alle Initial-Logik tot gelegt.
**Tests:** **1192 grün** (1175 + 17 P48).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`.
**Workflow:** V1→V2→R1 (1 Bug + 2 Risiken + 1 Verbesserung + 1 Refactor
angenommen)→V3→Code→Final-R1 („Push freigegeben", 9.5/10, 0 KP).
**Push:** gleich folgend (7 atomare Commits C1–C7).

### Nächste mögliche Aufgaben (TODO)

- **P49** OMNI-Pretrigger aus Settings (P48-Followup, ~30min) —
  `_OMNI_PRETRIGGER_OFFSET_S = 1.3` ist letzte hartcodierte
  FlexRadio-Konstante
- **Bundle B (UI-Persistenz)** P24 + P32 + P29 (~2.5h)
- **Bundle C (Reihenfolge & Cache)** P33 + P10 (~2h, Field-Test-light)
- **P46** Bandpilot Normal-Reintegration (2-3h)

### Vorgänger-Stand (v0.97.12, 13.05.2026 nachmittags)

## Stand 2026-05-13 nachmittags: v0.97.12 Bundle A (P43 + P20 + P18) erledigt

**Code:** v0.97.12 — Drei kleine QoL-Fixes als Bundle:
- **P43 setproctitle:** Activity Monitor zeigt jetzt „SimpleFT8 v0.97.12"
  statt „Python" (Remote-Wrapper: „SimpleFT8 (Ferienhaus)").
- **P20 Log-Rotation:** `simpleft8.log` ist jetzt Symlink → datierte
  Tagesdatei. Logs >7 Tage werden automatisch gelöscht. Mike's
  bestehende `simpleft8.log` (Wochen Historie) wandert dauerhaft nach
  `~/.simpleft8/archive/simpleft8-pre-rotation-YYYY-MM-DD.log`.
- **P18 DT-Print-Spam:** 3× identisches `[DT-Korr] ... geladen` beim
  App-Start nur noch 1×.
**Tests:** **1175 grün** (1167 + 8 Bundle A).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.11_vor_bundle_qol/`.
**Workflow:** V1→V2→R1→V3 voll durchgezogen, Final-R1 „Push freigegeben",
0 KP-Findings.
**Neue Dependency:** `setproctitle>=1.3` in `requirements.txt` (im
venv installiert v1.3.7).
**Push:** gleich folgend (6 atomare Commits C1–C6).

### Nächste mögliche Aufgaben (TODO)

- **Bundle B (UI-Persistenz)** P24 + P32 + P29 (~2.5h Workflow)
- **Bundle C (Reihenfolge & Cache)** P33 + P10 (~2h, Field-Test-light)
- **P46** Bandpilot Normal-Reintegration (2-3h Workflow)

### Vorgänger-Stand (v0.97.11, 13.05.2026 mittags)

**Code:** v0.97.11 — `audio_freq_hz` + `max_decode_freq` waren tote
UI-Settings (Encoder vom CQ-Algo überschrieben, `decoder.max_freq` nie
zur Laufzeit aktualisiert). Statusbar-`Filter:`-Anzeige war
irreführend (FT2 zeigte 100-4000 Hz, Decoder lief auf 3000 Hz). Alles
entfernt, Defaults hartkodiert.
**Tests:** **1167 grün** (1162 + 5 P47).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.10_vor_p47_dead_freq_settings/`.

### Vorgänger-Stand (v0.97.10, 13.05.2026 morgens)

**Code:** v0.97.10 — DT-Status jetzt als eigenes Permanent-Widget
`_dt_indicator` rechts neben `_stats_indicator`. Vorher hat der globale
`setStyleSheet` während DT-Korrektur die ganze Statusbar grün gefärbt.
**Tests:** **1162 grün** (1160 + 2 P44).
**Backup vor Code:** `Appsicherungen/2026-05-13_v0.97.9_vor_p44_dt_indicator/`.

### Vorgänger-Stand (v0.97.9, 12.05.2026 abends)

**Code:** v0.97.9 — OMNI-CQ wurde im `_log_stats` nicht abgefangen →
Stats-Verfälschung während OMNI-RX-Slots. Jetzt eigener Guard-Block.
**Tests:** **1160 grün** (1156 + 4 P45).
**Backup vor Code:** `Appsicherungen/2026-05-12_v0.97.8_vor_p45_omni_stats_guard/`.
**Push:** ausstehend (Mike beim Termin) — gleich nachgeholt.

### Was Mike heute anstoßte (3 Themen):
1. **DT-Korrektur grün → Statusbar grün-Bug** — in TODO als **P44**
2. **Stats-Sperren-Check für OMNI** — **P45 erledigt** (dieser Stand)
3. **Bandpilot Normal-Reintegration** — in TODO als **P46**
   (Mike+Claude+R1 einig, Schwellen MIN_DAYS_HOUR=3 / MIN_CYCLES_HOUR=20
   bereits vorhanden, nur Code-Erweiterung nötig)

### Memory-Watcher läuft weiter
Daemon PID 81237 sampelt SimpleFT8 alle 60s nach
`~/.simpleft8/memory_watch.log`. TTS-Server bleibt aus
(`launchctl unload`).

### Vorgänger-Stand (v0.97.8)

Decoder-Diagnose-Code opt-in via `SIMPLEFT8_DECODER_DIAG=1`. R1-bestätigter
Verdacht `_audio_buffer_24k` Skip-Bug. Erste Beobachtung: RSS ~270 MB
stabil, 0 Skips → Hauptverdacht entlastet, vermutlich war 124-GB-Crash
hauptsächlich TTS.

**Code:** v0.97.8 — Decoder-Diagnose opt-in via `SIMPLEFT8_DECODER_DIAG=1`.
**Tests:** **1156 grün** (1148 + 8 neue P30-Tests).
**Backup vor Code:** `Appsicherungen/2026-05-12_v0.97.7_vor_p30_diagnostic_code/`.
**Memory-Watcher-Daemon:** PID 72060 läuft, Log `~/.simpleft8/memory_watch.log`.
**Push pending:** v0.97.8-Commits noch lokal.

### Nächster Schritt — Mike aktiviert Diagnose

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
export SIMPLEFT8_DECODER_DIAG=1
./venv/bin/python3 main.py
```

→ App 1-3 Tage in Diversity laufen lassen.
→ Auswerten: `grep "P30-DIAG" ~/.simpleft8/debug_*.log | tail -50`
→ Wenn `buf_chunks` steigt + `skips_total` steigt + `busy_held > 30s`:
  Hypothese bestätigt → P30.FIX als eigener Workflow.

### Vorgänger-Stand (v0.97.7)

**Code:** v0.97.7 + P42-README-Passage + ADIF-Aufräumen + Stats neu.
**Tests:** **1148 grün**, alles auf GitHub bis `569aa9b`.
**Field-Test heute:** Mike-Bestätigung 70:30-Pattern wird eingehalten,
Adaptive Diversity läuft sauber.

## Heute 12.05. Bilanz (Mike's „Therapie-Marathon"-Tag)

**8 Versions-Bumps in einem Tag:**

| Version | Inhalt |
|---|---|
| v0.97.0 P34 | Adaptive Diversity (Hauptfeature, slot-für-slot live) |
| v0.97.1 P35 | Startup-Bugs A/B/B5 (defer/resume, Queue-Reset, Auto-Reactivate) |
| v0.97.2 P35 D/E/F | Live-Field-Fixes (App-Start IMMER 20m FT8 Normal) |
| v0.97.3 P37 | RX-Antennen-Anzeige im „● DYNAMISCH (live)"-Label |
| v0.97.4 P38 | PID-Recycling-Schutz im starter.command |
| v0.97.5 P39 | osascript Python-Process-Filter (Browser-Tab-Bug) |
| v0.97.6 P40 | P37-Komplettierung (3 weitere current_ant-Aufrufer) |
| v0.97.7 P41 | audio_streaming-Flag — OMNI-CQ Antennen-Switch entblockt |

**Plus Doku/Daten ohne Version-Bump:**
- README + Hilfe: Adaptive-Diversity-Konzept (DE + EN)
- P42 README-Passage „Why Diversity Matters for FT8" (R1-verifizierte
  Physik: Headroom-Asymmetrie + Pol-/Sektor-Diversity)
- ADIF-Cleanup: Master-ADIFs in Backup, Jahresarchiv 2026 erstellt
- Statistiken regeneriert (DE+EN PDFs, alle PNGs)
- QRZ-Upload-Analyse + Diagnose

**Workflow-Disziplin:** **alle 9 Aufgaben** voll V1→V2→R1→V3 mit
DeepSeek durchgezogen. R1 fand kritische Fehler in:
- P41 (abort-Race mit FlexRadio-Buffer-Latenz)
- P42 (Pol-Diversity als Hauptmechanismus, nicht primaer Headroom)
- P35-AK5 (Cache-Reuse-Respekt)
- P26-K2 (Modal-exec singleShot-Defer)

## Field-Test Status

✅ Adaptive Diversity live verifiziert (70:30-Pattern eingehalten,
   slot-für-slot Wechsel)
✅ OMNI-CQ + Adaptive zusammen funktional (P41 entblockt Antennen-Switch)
✅ App-Start IMMER 20m FT8 Normal (P35-F)
✅ RX-Antennen-Label wechselt korrekt im Adaptive-Modus (P37+P40)

## Offene Punkte (nicht heute, aus TODO.md)

**🔥 Hoch:**
- **P30** MEMORY-LEAK 124 GB nach Tagen Laufzeit (KRITISCH, Diagnose
  steht aus)
- **P12** QSO-Postprocessing-Hang (Partial-Fix da, sauberer Async-Refresh
  weiter offen)
- **P27** MESS-GUARD Radio-Verbunden-Check vor Antennen-Mess
- **P25** RADIO-IP-LATE-SETTING prüfen ob obsolet

**📋 Mittel:**
- **P34-Stufe2** Statik-Pipeline komplett raus (nach 2-3 Wochen Adaptive
  Field-Test)
- **P32** RX-Panel-Spalten-Persist, **P33** QSO-fertig-Reihenfolge,
  **P24** Last-RX-Mode-Persist

**🛠 Niedrig:** P18, P20, P29

## „2-Unsichtbare-Instanzen"-Bug

Bei Debug-Sessions vor heute hatte Mike gelegentlich eine 2. Instanz im
Hintergrund laufen sehen. **NICHT identisch mit P38/P39 PID-Recycling/
Browser-Tab-Bug.** Vermutlich `atexit._release_lock_on_exit()` greift
unter Qt-Window-Close manchmal nicht. Eigener Workflow noetig — als
„offen" vorgemerkt.

## Workflow-Lessons heute

- P40 wurde Folgefix zu P37 weil Memory-Lesson `feedback_partial_fix_
  check_other_paths.md` nicht direkt angewendet — bei P40 nachgezogen.
  Bei Methoden-Signatur-Erweiterungen IMMER grep ueber alle Aufrufer.
- R1-Findings haben heute MEHRFACH kritische Fehler gefangen die ich
  uebersehen haette — Mike-Anweisung „DeepSeek IMMER bei nicht-trivialen
  Aufgaben" hat sich klar bewaehrt.
- Saubere Compact-feste Plan-Files (`prompts/p3[4-9]_*.md`,
  `prompts/p4[0-2]_*.md`) ermoeglichen nahtlose Session-Wiederaufnahme.

## Stand 2026-05-12 morgens: v0.97.7 P41 audio_streaming-Flag

**Code:** v0.97.7 lokal — OMNI-CQ blockierte Antennen-Switch ueber 20
Slots wegen zu grobem `is_transmitting`-Check. Feinerer Flag
`is_audio_streaming` (nur von ptt_on bis ptt_off True) fixt das.
**Tests:** **1148 grün** (+8 P41).
**Push:** done.

## P41 fixt OMNI-CQ Antennen-Switch-Blockade

Mike-Field-Test 12.05. morgens mit OMNI-CQ + Adaptive Diversity 30:70:
Antennen wechselten 5 Minuten lang nicht, Adaptive-Buffer einseitig
gefuellt, Label statisch „RX Ant1".

**Wurzel:** `encoder.is_transmitting` blieb durchgaengig True ueber
ganzem Worker-Lauf (Setup + Sleep + Audio). Bei OMNI-CQ alle 30s neuer
Worker → keine True-Luecke zwischen den Slots.

**Fix:** neuer feiner Flag `is_audio_streaming` der NUR von `ptt_on()`
bis `ptt_off()` True ist. Deckt 1.3s FlexRadio-Buffer-Latenz mit ab.

R1-KRITISCH: `abort()` darf Flag NICHT setzen (Race mit noch laufender
send_audio im FlexRadio-Buffer). Worker-finally setzt Flag zurueck.

## Workflow

V1 → V2 (Self-Review) → R1 (1 KRITISCH umgesetzt + 1 SOLLTE umgesetzt +
1 SOLLTE verworfen weil Bug-Wiederherstellung) → V3 → Code.
Plan-File: `prompts/p41_audio_streaming_flag_r1.md`.

**Backup vor Aenderung:** `Appsicherungen/2026-05-12_v0.97.6_vor_p41_omni_antenna_fix/`.

## Stand 2026-05-12 nachts: v0.97.6 P40 P37-Komplettierung

**Code:** v0.97.6 lokal — 3 weitere Aufrufer von `update_diversity_ratio`
reichen jetzt `current_ant` durch. Adaptive-Label zeigt RX-Antenne
verlaesslich auch bei Ratio-Wechseln.
**Tests:** **1140 grün** (+4 P40 vs v0.97.5).
**Push:** pending.

## P40 fixt P37-Partial-Fix

Mike-Field-Test 12.05. abends: Label „● DYNAMISCH (live)" zeigte den
RX-Antennen-Suffix nicht. P37 hatte nur 1 von 4 Aufrufern angefasst
(klassischer Partial-Fix, Memory-Lesson verfehlt).

**3 gefixte Stellen:**
- `main_window.py:1357` `_on_dynamic_ratio_changed` (Haupt-Übeltäter,
  bei jedem Ratio-Wechsel getriggert)
- `mw_radio.py:990` Adaptive-Aktivierung
- `mw_cycle.py:290` Mess-Pfad

## Workflow

V1 → V2 (Self-Review + Memory-Lesson zitiert) → R1 (DeepSeek, 0 KRITISCH,
1 SOLLTE→Integration-Test umgesetzt) → V3 → Code.
Plan-File: `prompts/p40_p37_completion_r1.md`.

## Stand 2026-05-12 nachts: v0.97.5 P39 Window-Title-Check Python-Filter

**Code:** v0.97.5 lokal — osascript filtert jetzt nur Python-Prozesse
(Browser-Tabs mit „SimpleFT8" im Titel matchen nicht mehr).
**Tests:** 1136 unveraendert (Bash-Script-Edit).
**Push:** mit P38-P39 zusammen pending.

## P39 fixt den eigentlichen Bug

P38 war PID-Recycling-Schutz im Fallback — korrekt, aber griff nicht
beim aktuellen Browser-Tab-Fall, weil osascript-Primaer-Check schon
falsch matcht. P39 fixt die Wurzel: nur Python-Prozesse werden gepruefte.

**Live-verifiziert 12.05.:** Chrome-Tab mit GitHub-Repo offen → osascript
returnt leer → Starter laeuft sauber durch.

## Workflow

V1 → V2 (Self-Review) → R1 (0 KRITISCH, 2 KOENNTE/SOLLTE praktisch
irrelevant) → V3 (V2 + 1 Kommentar zur PyInstaller-Zukunft) → Code.
Plan-File: `prompts/p39_window_title_python_filter_r1.md`.

## Stand 2026-05-12 nachts: v0.97.4 P38 PID-Recycling-Schutz im Starter

**Code:** v0.97.4 lokal — PID-Recycling-Bug im `starter.command` gefixt.
**Tests:** 1136 unveraendert (Bash-Aenderung, keine Python-Module).
**Push:** zusammen mit v0.97.3 P37 nach Mike-OK.

## Was P38 fixt

Mike-Screenshot 12.05.2026: Starter zeigte „SimpleFT8 laeuft bereits"
mit Process-Info `/Applications/Google Chrome.app/...`. Chrome hatte
PID 23196 vom beendeten SimpleFT8 recycled bekommen, `kill -0` meldete
„lebt", Mike wurde am Neustart gehindert.

**Fix:** `ps -p $LOCK_PID -o command=` + `grep` auf `SimpleFT8.*main\.py`
hinter dem `kill -0`. Wenn PID nicht zu SimpleFT8 gehoert → Lock
loeschen + starten.

**Wichtige Nicht-Identitaet:** Das ist NICHT der alte „2 unsichtbare
Instanzen"-Bug von Mike's Debug-Sessions. Der hatte einen Cleanup-Issue
(atexit unter Qt-Close nicht zuverlaessig) und ist ein separates
Folgeprojekt.

## Workflow

V1 → V2 (Self-Review) → R1 (0 KRITISCH, 1 SOLLTE bereits quoted) → V3 → Code.
Plan-File: `prompts/p38_pid_recycling_starter_r1.md`.

## Stand 2026-05-12 nachts: v0.97.3 P37 RX-Antennen-Anzeige im Adaptive-Label

**Code:** v0.97.3 lokal — Mike-Wunsch 12.05. nach Live-Test:
Adaptive-Phase-Label um aktive RX-Antenne erweitert.
**Tests:** **1136 grün** (+5 P37 vs v0.97.2).
**Push:** pending bis Mike OK gibt.

## Was P37 macht

Im Antennen-Panel wird das blaue Label jetzt:
- **„● DYNAMISCH (live) — RX Ant1"** wenn aktueller Slot ANT1 hört
- **„● DYNAMISCH (live) — RX Ant2"** wenn aktueller Slot ANT2 hört
- Update slot-für-slot (alle 15 s bei FT8)
- Statik-Modus unverändert (kein RX-Anhang)

So sieht Mike live dass das Diversity-Pattern wirklich slot-für-slot
wechselt und nicht starr auf einer Antenne hängt.

## Workflow V1→V2→R1→V3 (alle Schritte)

- V1+V2 (Self-Review): Spec + Code-Verifikation + Race-Check
- R1: DeepSeek-Reasoner Review → 0 KRITISCH, 1 Verbesserung (5 Tests
  statt 1) → in V3 übernommen
- V3 = V2 + erweiterte Test-Coverage
- Code: 2 Files, ~6 Zeilen
- 5 Tests grün (T1-T5 R1-Coverage)

## Plan-Files

- `prompts/p37_rx_antenna_label_r1.md` — R1-Review-Auftrag + V2-Plan

## Stand 2026-05-11 abends: v0.97.2 P35 Bug D+E+F Live-Field-Test läuft

**Code:** v0.97.2 lokal — Bug D+E+F nach v0.97.1 noch nachgezogen (Mike-
Live-Diagnose während Field-Test 11.05. abends).
**Tests:** **1131 grün** (+2 P35-Bug-E-Tests gegenüber v0.97.1).
**Push:** pending bis Mike kompletten Field-Test grün gibt.

## Mike-Live-Field-Test 11.05. abends (in Progress)

- ✅ **App-Start**: 20m FT8 Normal — kein „messen 0/6"-Hänger (Bug F greift)
- ✅ **Normal → Diversity DX**: beide Antennen aktiv, Statik-Mess sauber
- 🔄 **Dynamic-Toggle**: blau angezeigt, Buffer füllen sich
  (Log `[DYNAMIC] record_slot` zeigt Scores 99-117, A1=2/5 + A2=1/5
  bei `:55:57` — wartet auf 5/5 + 5/5 für erste evaluate)

## Was Bug D+E+F dazu fixten (v0.97.2)

- **Bug D**: `_on_band_changed` löst `on_band_change()` nur noch bei
  `rx_mode=diversity` UND `radio.ip` aus. Sonst Fallback Phase=operate.
- **Bug E**: Bandpilot überschreibt NIE Normal-Modus. Skipt wenn
  current=normal ODER target=normal. Mike-Vision: Bandpilot wählt nur
  zwischen Diversity Standard ↔ DX.
- **Bug F**: App-Start IMMER 20m FT8 Normal (hardcoded in `__init__`).
  Settings-Restore für band+mode entfernt. Mike-Anweisung 11.05.

Commits: `6347c0a` Bug D, `18db03f` Bug D+E + Tests, `91728f7` Bug F.

## Was P35 fixt

3 Bugs die Mike beim P34-Field-Test entdeckte:

- **Bug A:** Statik-Mess hing bei radio.ip=None → Antennen-Switch nur auf
  ANT1. Fix: bei radio.ip=None Init aufschieben, nach Radio-Connect via
  `_check_diversity_preset` nachholen.
- **Bug B:** `_apply_dynamic_toggle` leerte Queue + current_ant nicht →
  P34-Hook bekam alte (A1, "measure")-Einträge, Buffer A2 blieb leer.
  Fix: Queue + current_ant unter Lock VOR activate() resetten.
- **Bug B5:** Toggle verlor bei Mode-Wechsel. Mike-Q3-Wunsch: Toggle
  überlebt Session. Fix: `_activate_diversity_with_scoring` ruft
  `_apply_dynamic_toggle(True)` wenn Settings-Toggle AN.

**Plus AK5 (R1-Q4 KRITISCH):** `activate()` respektiert Cache-Reuse-Ratio.
Cache 70:30 wird NICHT mehr auf 50:50 zurückgesetzt beim Toggle AN.

## 5 atomare Commits

| # | Inhalt | Datei |
|---|---|---|
| C1 | `activate()` AK5 Cache-Reuse-Respekt + 2 Test-Anpassungen | `core/dynamic_diversity.py` + `tests/test_diversity_dynamic.py` |
| C2 | `_apply_dynamic_toggle` Queue+current_ant Reset + 11 P35-Tests | `ui/main_window.py` + `tests/test_p35_startup_bugs.py` NEU |
| C3+C4 | `_enable_diversity` Defer + Resume + Auto-Reactivate | `ui/mw_radio.py` |
| C5 | APP_VERSION 0.97.0→0.97.1 + Doku + Final-R1-Lock-Fix | `main.py`, HISTORY/HANDOFF/CLAUDE |

## Field-Test F1-F8 (Mike)

V3 §6 — Auszüge:
- **F2:** „ohne Radio weiter"-Pfad → Diversity startet sauber wenn Radio kommt
- **F4:** Cache 70:30 + Toggle AN → **bleibt 70:30** (kein 50:50-Reset)
- **F6+F7:** Toggle überlebt Mode-Wechsel (Diversity↔Diversity↔Normal)

**Bestanden wenn F1-F4 sauber, F5-F8 wie spezifiziert.**

## Plan-Files (Compact-fest)

- `prompts/p35_diversity_startup_fix_v1.md` — Initial-Entwurf
- `prompts/p35_diversity_startup_fix_v2.md` — Self-Review nach Mike-Q1-Q3
- `prompts/p35_diversity_startup_fix_r1.md` — DeepSeek-R1-Kritik
- `prompts/p35_diversity_startup_fix_v3.md` — **FINAL** mit 12 ACs + 11 Tests
- `prompts/p35_diversity_startup_fix_final_r1.md` — Final-R1 nach Code

## Push pending

v0.95.16 → v0.96.10 → v0.97.0 → v0.97.1 alle lokal. Push nach Mike's
Field-Test-OK.

## Stand 2026-05-11 nachmittags: P34.DIVERSITY-DYNAMIC v0.97.0 Code fertig

**Code:** v0.97.0 lokal — neuer Live-Modus für Antennen-Verhältnis.
**Tests:** **1111 grün** (1070 → 1111, +41).
**Push:** pending bis Mike Field-Test 12-Punkte (V3 §5) bestätigt.

## Was P34 ist

Antennen-Verhältnis (50:50 / 70:30 / 30:70) kann jetzt **im laufenden
Betrieb live** angepasst werden statt nur 1× pro Stunde mit 90-Sek-
UI-Sperre.

**Architektur ENTWEDER-ODER** (kein Parallel-Betrieb):
- Toggle AUS in Settings → Statik wie heute (100% unangetastet)
- Toggle AN → Dynamic übernimmt, Statik 1h-Frist unterdrückt

**Wo der Toggle steht:** Einstellungen → „FT8 & Diversity" → Checkbox
„Antennen-Verhältnis dynamisch anpassen (Testphase)". NICHT persistiert
— bei jedem App-Start auf AUS.

**Visuell:** Antennen-Panel Phase-Label wird **blau** („● DYNAMISCH (live)")
wenn aktiv, sonst Standard-Text „Diversity Neuberechnung in X Min."

## 9 atomare Commits — alle drin

| # | Inhalt | Datei |
|---|---|---|
| C1 | Modul-Helper + `_evaluate()` Refactor | `core/diversity.py` |
| C2 | DiversityController Hooks (`dynamic_active`, `_scoring_mode_listeners`, `should_remeasure` Check) | `core/diversity.py` |
| C3 | DynamicDiversityController NEU | `core/dynamic_diversity.py` |
| C4 | RAM-only Property `dynamic_diversity_enabled` | `config/settings.py` |
| C5 | UI-Hooks für Reset + Slot-Datenerfassung | `ui/mw_cycle.py`, `ui/mw_radio.py` |
| C6 | main_window Init + Slots + Toggle-Handler | `ui/main_window.py` |
| C7 | control_panel `is_dynamic` Param + Blau-Färbung | `ui/control_panel.py` |
| C8 | settings_dialog Toggle + Tooltip | `ui/settings_dialog.py` |
| C9 | APP_VERSION + Doku | `main.py`, HISTORY/HANDOFF/CLAUDE |

## Test-Bilanz

- `tests/test_diversity_helpers.py` NEU — 14 Tests für Modul-Funktionen
- `tests/test_diversity_dynamic.py` NEU — 15 Unit-Tests für Controller
- `tests/test_diversity_dynamic_integration.py` NEU — 12 Integration-Tests
- Statische Tests bleiben grün (AK1 erfüllt: Pipeline unangetastet)

**Total: 1070 → 1111 grün** (+41, V3-Prognose war ~1095-1100).

## Plan-Files (Compact-fest)

- `prompts/p34_diversity_dynamic_v1.md` (ENTWEDER-ODER-Spec)
- `prompts/p34_diversity_dynamic_v2.md` (Self-Review)
- `prompts/p34_diversity_dynamic_r1.md` (DeepSeek-R1, neue Architektur)
- `prompts/p34_diversity_dynamic_v3.md` (FINAL, 16 ACs, Field-Test-Checkliste)
- `prompts/p34_diversity_dynamic_*_OLD_parallel.md` (verworfene Vorgänger)

## Field-Test-Checkliste F1-F12 (Mike)

V3 §5 — Auszüge:
- F1: Toggle AUS → 100% wie heute
- F2: Toggle AN → Antennen-Panel wird blau, Ratio passt sich live an
- F3: Toggle AN während Statik-Mess → Mess bricht ab, sofort 50:50
- F4: Bandwechsel mit Toggle AN → **keine 90-Sek-Sperre mehr**
- F7: 1h ohne QSO mit Dynamic AN → keine 90-Sek-Statik-Re-Mess
- F8: Toggle AN→AUS → **keine sofortige Statik-Mess** (Mike B-Option)

**Bestanden wenn F1-F8 sauber.**

## Weiter offen (nach P34)

- ⛔ **P30 MEMORY-LEAK 124 GB nach Tagen** — eigener Workflow nötig.
  Live-Check bestätigt: RAM nicht Disk. Verdächtige Pfade in TODO P30.
- 📋 P12 sauberer Async-Refresh (Partial-Fix ist drin)
- 📋 P27 Mess-Guard (aus P26-Spec)
- 📋 **Stufe 2 P34** — Statik komplett entfernen (eigener Workflow später
  wenn Mike sich mit Dynamic wohlfühlt)

## Push pending

v0.95.16 → v0.96.10 → v0.97.0 alle lokal gesammelt. Vor Push:
1. Mike Field-Test F1-F12 für P34
2. Entscheidung P30 (angehen oder als „acceptable" abhaken)

## App starten

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
./venv/bin/python3 main.py
```

Single-Instance-Schutz aktiv (Window-Title-Check via osascript).

## Tests laufen lassen

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q
```

→ **1111 grün** Stand v0.97.0.

## Nicht vergessen

- **Symlinks aktiv:** `FT8/CLAUDE.md` + `FT8/HANDOFF.md` sind Links auf
  `SimpleFT8/CLAUDE.md` + `SimpleFT8/HANDOFF.md`. KEIN Doppel-Edit.
- **Push pending** bis Mike Field-Test grün.
- **Toggle AN beim Test:** muss jedes Mal aktiv eingeschaltet werden
  (NICHT persistiert — Mike-Wunsch fürs Testen).
