# SimpleFT8 TODO — Stand 28.05.2026 (v0.98.37)

> **Strategie (Mike 28.05.):** ALLE Baustellen inkl. Multiband fertigstellen,
> DANN für Icom forken (nicht parallel). Icom-Abstraktion ist durch P121
> bereits sauber (Stubs da, Diversity/VITA-49 gated) — der echte Icom-Aufwand
> (CI-V CAT + Soundkarten-Audio + PTT) braucht aber die Hardware vor Ort.

> **Diese Datei = Backlog (aktiv-offen + frisch erledigt).**
> Vollständige Historie aller Änderungen: **HISTORY.md** (nur anhängen).
> Funktions-Doku: **FEATURES.md** (Pattern-Familien, Architektur).
> Aktueller Session-Stand: **HANDOFF.md**.

---

# 🟢 LAUFEND — Field-Test pending

## P123 — Pre-TX-Anzeige beim QSO-Start (v0.98.37, 28.05.2026)

**Was:** Auto-Hunt zeigt jetzt „Rufe X..." im QSO-Log beim Start (war
vorher der einzige stille Start-Pfad — nur debug_log). Variante A (Mike-
Wahl): kurzer Marker, kein neues Format. DeepSeek PUSH FREIGEBEN.

**Mike-Field-Test:** Auto-Hunt aktivieren → beim Picken einer Station
sollte sofort „Rufe X... (ANT1)" im QSO-Log erscheinen (nicht erst der
„Gesendet"-Eintrag ~30s später).

## P154 — Auto-TUNE SWR-Median-Fix (v0.98.36, 28.05.2026)

**Was:** Mein P153-Fix (Median statt Snapshot) saß nur im manuellen TUNE-
Pfad. Die zwei AUTO-TUNE-Pfade (`_start_auto_tune_for_band_change`,
`_start_dialog_tune_sequence`) hatten eigenes Setup ohne die Sample-
Sammlung → arbeiteten mit veralteter Startzeit → falsche Band-Sperre
(Mike-Field-Bug: „Band 20M gesperrt — SWR 8.7" obwohl real 1.4, nur
manueller TUNE funktionierte). Zwillings-Bug wie P133/P134. Fix: zentraler
Helper `_init_tune_swr_sampling` von allen 3 Pfaden + Token-Reset (R1-F1).

**Mike-Field-Test:** Bandwechsel mit automatischem TUNE → Band sollte jetzt
mit dem echten stabilen SWR bewertet werden, nicht mit einem Ausreißer.
Bei Hänger Debug-Log AN → Diagnose-Zeile „SWR-Fenster".

## P152 — Weak-Decode-Log ≤ -21 dB (v0.98.35, 28.05.2026)

**Was:** Always-on-Liste `~/.simpleft8/weak_decodes_YYYY-MM-DD.log` — jeder
Decode mit SNR ≤ -21 dB landet automatisch drin (kein Setting). Mess-
Instrument das empirisch belegt was P150 (kMin_score=4) liefert. Neues
Modul `core/weak_decode_log.py` (batched 1 File-Append/Slot, UTC, keep_days=7).
Hook in `mw_cycle._on_cycle_decoded`.

**Mike-Field-Test:** 1-2 FT8-Sessions funken → Datei schicken → ich werte
aus (Anzahl -22 bis -26 dB pro Band/Antenne). Mike sah live schon -25/-27 dB
→ P150 wirkt sichtbar.

**Format:** `HH:MM:SS | -25 dB | CALL ME -18 | 1293 Hz | 15m FT8`

## P153 — SWR-Freeze Median über stabiles Fenster (v0.98.34, 28.05.2026)

**Was:** Bandsperre-Freigabe nahm einen EINZIGEN SWR-Snapshot
(`radio.last_swr`) → erwischte Ausreißer (Tuner matchte sichtbar 2,5,
System fror >4,0 ein → Band fälschlich gesperrt). Fix: **Median über
Fenster [Dauer-3s, Dauer-1s]** (neuer Helper `_compute_match_swr()`).
<3 Samples → None → Post-Check FAIL → Band gesperrt (Hardware-Safety,
KEIN Snapshot-Fallback). Auslöser P142 (Freeze in instabile Post-Match-
Phase gezogen), P148 machte es sichtbar. Pattern-Klasse Hardware-
Sicherheit 4. Iteration (P53/P76-A/P142/P153).

**Mike-Field-Test:** beim nächsten TUNE-Hänger Debug-Log aktivieren →
Diagnose-Zeile „SWR-Fenster …" zeigt Median vs. alter Snapshot.

## P150 — Decoder-Empfindlichkeit kMin_score 10 → 4 (v0.98.32, 27.05.2026)

**Was:** `ft8_lib/libft8simple.c` Z. 114 (FT8-Pfad) Sync-Pattern-Schwelle
von 10 auf 4 gesenkt → Decoder versucht auch sehr schwache Sync-Patterns
zu retten (WSJT-X „Deep"-Niveau). FT4/FT2 bleiben bei 10 (Costas-Pattern-
Längen unterschiedlich, Score-Skala nicht 1:1).

**Mike-Field-Test:**
1. App-Neustart auf v0.98.32+
2. 1-2 FT8-Sessions auf schwierigen Bändern (40m abends, 15m flau)
3. Logbuch beobachten:
   - **Best Case:** mehr -22/-24 dB QSOs, vielleicht erstmals -25/-26 dB
   - **Worst Case:** zu viele Junk-Decodes (fremde Calls in unpassenden
     Mustern) → Schwelle auf 5 oder 6 anheben

**Rollback:** Backup unter `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/libft8simple.dylib` —
einfach zurückkopieren, App-Restart.

**Folge-Schraube falls P150 zu wenig bringt:** `SUBTRACT_MIN_SNR=-18 → -22`
in `core/decoder.py` (schwächere Signale subtrahieren → noch tiefere darunter
freilegen).

## P151 — AP-Lite vollständig ausgebaut (v0.98.33, 27.05.2026)

**Was:** AP-Lite-Feature komplett aus dem Code entfernt. DeepSeek-V4-pro-
Konsens: Matched Filter über LDPC-Decoder hat keine Nische, Konzept
trägt nicht. Mike-Felddaten 27.05.: 0/16 MATCH bestätigte das.

**Entfernt:** `core/ap_lite.py`, 3 Test-Files, 2 Doc-Files,
`generate_reference_wave` in Encoder, `last_pcm_12k`-Buffer im Decoder,
`partner_last_snr`-Field in QSOData, 4 Settings-Keys, GroupBox + Help-Eintrag,
Statusbar-Counter, alle Aufrufer.

**Backup:** `Appsicherungen/2026-05-27_v0.98.31_vor_p150_p151/ap_lite.py` —
falls je wiederbelebt werden soll.

---

## P148 — SWR-Anzeige nur während TX/TUNE (v0.98.28, 27.05.2026)

**Was:** Filter in `mw_tx.py:_on_meter_update` SWR-Branch — Update nur
wenn `encoder.is_transmitting OR _tune_active`. Bei Bandwechsel
`reset_swr_display()` (grauer Reset auf „SWR —"). Letzter echter
TX/TUNE-Wert bleibt im RX sichtbar statt mit Sensor-Default 1.0
überschrieben.

**Mike-Field-Test:** beobachten ob die SWR-Anzeige nach TUNE/QSO den
echten Wert behält und bei Bandwechsel auf „—" zurückspringt.

**Hardware-Sicherheit:** P53 SWR-Watchdog komplett unbeeinflusst (liest
direkt `radio._last_swr` aus FlexRadio, nicht UI).

---

## P139 — Auto-Hunt-60s-Start-Delay (Field-Beobachtung)

**Beobachtung Mike 26.05.:** Auto-Hunt aktiviert → sprang erst nach
~60s (4 Slots) an. **Heute 27.05.:** 1× nach 15s gesehen (Mike: „vlt
war das mit autohund dann nur ein programm irrläufer noch nicht
abhacken ich kucke dann noch 2 oder 3 mal lieber okay").

**Diagnose-Tool da:** P139 Event-Logging (v0.98.20) — alle Auto-Hunt-
Events landen in `~/.simpleft8/debug_YYYY-MM-DD.log` wenn „Debug-Log
schreiben" in Settings aktiv. Bei Wiederauftreten Log-Snippet liefern,
dann gezielt fixen.

**Mögliche Ursachen (Hypothesen, alle ungetestet):**
- Keine `is_cq`-Stationen mit SNR ≥ MIN_SNR in den ersten Slots
- Decoder-Buffer-Aufbau in den ersten 2 Slots nach Kalibrierung
- `_recent_qso` 5-Min-Cooldown auf gerade dekodierte Stationen
- `_dx_tune_dialog`-Close-Race
- Stats-Warmup 6 Zyklen

**Severity:** 🟡 — kein Bug bewiesen, möglicherweise Normalverhalten.

---

# ✅ ERLEDIGT 27.05.2026 — P142 SWR-Freeze VOR Phase B (v0.98.29)

Mike-Field-Reproduktion 12:08-12:10: Bandsperre triggered → manueller
TUNE → Log meldete „freigegeben — SWR 1.0" obwohl Live-Widget 2.5
zeigte. Fix Variante C (R1-empfohlen): Freeze VOR Phase B nehmen
(`swr_after_match` als `_tune_last_valid_swr`). R1-ORANGE-Catch:
Cancel-während-Phase-B Edge-Case behoben (Hardware-Sicherheit).

Final-R1 PUSH FREIGEBEN „sehr KISS-konform". Tests 2138→2149 (+11
P142, 3 alte P76-A-Tests angepasst). Pattern-Klasse Hardware-
Sicherheit 3. Iteration (P53/P76-A/P142).

**Field-Test pending.**

---

## (alte AUFGESCHOBEN-Sektion war hier, jetzt erledigt)

## P142 — Bandsperre-Freigabe meldet falschen SWR-Wert (Mike Field 26.05. 17:24) — JETZT ERLEDIGT

**Mike-Anweisung 27.05.:** „radio ist zwar an ich bin aber nicht vor
ort wir müssen das aus eis legen bis ich einmal schlechtes swr
simulieren kann stecker ab dann bandsperre dann stecker dran und
tune drücken das müssen wir aufschieben".

**Repro-Schritte (wenn Mike wieder vor Ort am Radio ist):**
1. Antennen-Stecker am Radio abziehen (SWR künstlich verschlechtern)
2. TX provozieren → Bandsperre triggern (SWR-Watchdog feuert)
3. Stecker wieder dran (Match jetzt OK, SWR ~1.3 wäre echt)
4. TUNE-Button drücken → beobachten:
   - Live im Radio-Widget: SWR-Wert während TUNE (z.B. 2.5)
   - Im QSO-Log nach 2s: „Band freigegeben — SWR X.X"
   - Bug-Symptom: Log meldet 1.0 statt Live-Wert
5. Wenn Bug auftritt → Fix Variante C umsetzen (siehe unten)

**Root Cause (vollständige Analyse in FEATURES.md §9):**

TUNE-Pipeline hat 3 Stufen — Phase A (Tuner-Match bei voller Power) →
Phase B (Closed-Loop-Power-Konvergenz auf 10W) → SWR-Freeze + Post-Check.
Vermutung: Phase B regelt `rfpower` runter, SWR-Sensor sieht zu wenig
Träger → clamped auf 1.0. SWR-Freeze NACH Phase B friert die falsche
1.0 ein statt der echten 2.5 nach Phase A.

**Fix-Optionen:**
- **A:** SWR-Freeze VOR Phase B nehmen (direkt nach Tuner-Match)
- **B:** Phase-A-SWR UND Phase-B-SWR → `max()` als Freigabe-Kriterium
- **C (empfohlen):** SWR-Wert für Freigabe-Bewertung KOMMT NUR aus
  Phase A; Phase B nur für RF-Stützpunkt-Speicherung

**Severity:** 🟠 — bei Mike's swr_limit=3.0 harmlos. Aber Hardware-
Risiko-Potenzial wenn echtes SWR knapp über Limit + Clamp-Bug greift
→ Band wird fälschlich freigegeben → nächster TX defekte Antenne.

**Workflow-Pflicht:** ja. Code-Stelle `ui/mw_tx.py:255-275`. Mehrere
Phase-B-Pfade (manuell + Auto-TUNE bei Bandwechsel). FEATURES.md §9
für vollständige Pipeline-Doku.

---

# 🆕 BACKLOG — anpackbar

## 🔧 P155 — Gain-Mess-TUNE SWR-Median statt Snapshot (DeepSeek-R1-F2 aus P154)

> ⛔ **Nur vor Ort am Radio** — TUNE-Pfad, Hardware-Safety.

**Was:** Der Gain-Mess-TUNE (`_start_dx_tuning._after_tune`, mw_radio.py)
nutzt noch `swr = self.radio.last_swr` (Einzel-Snapshot) und sperrt das
Band bei `swr > swr_limit`. Gleiche Snapshot-Fragilität wie P153/P154 (ein
Ausreißer-Tick kann fälschlich sperren oder freigeben). Bei P154 bewusst
ausgegliedert (eigene 3s-Struktur, kein `_tune_stop` → kein gemeinsamer
Pfad). DeepSeek-R1-F2: separates Ticket, Scope-Creep vermeiden.

**Aufwand:** Sampling im 3s-Tune-Fenster aufsetzen
(`_init_tune_swr_sampling(3)` vor `tune_on`) + `_after_tune` auf
`_compute_match_swr()` umstellen statt `radio.last_swr`. Fenster bei 3s
Dauer ist [0, 2] (Test T7 in P153 deckt das ab). Voller Workflow Pflicht.

**Severity:** 🟠 — selteneres Szenario (KALIBRIEREN, User vor Ort), aber
gleiche Hardware-Risiko-Klasse. Konsistenz-Gewinn.

## 🆕 P119 — RFPreset/Krücke entfernen, Live-Loop reicht (Mike 25.05.2026)

> ⛔ **Nur vor Ort am Radio anpacken** — TUNE-Pfad ist sicherheitskritisch
> (ANT1-Pflicht, SWR-Watchdog). Falls TUNE-Verhalten kippt: Power-Cycle
> nötig, Remote nicht heilbar.

**Mike-Erkenntnis:** Die Live-Regelung `_auto_adjust_tx_level`
(`mw_tx.py:780`) lernt sowieso den richtigen Slider-Wert pro `(Band, Watt)`
beim ersten FT8-TX und speichert in `rf_preset_store`. Slider ist
Maximum-Begrenzer der PA → kann nie mehr senden als erlaubt. Beim Erst-TX
einfach `Slider = Watt-Zahl` → 1-2 Slot Anpassung beim allerersten Mal,
danach identisch zu heute. FT8 lebt von -20 dB SNR — Lücke praktisch null.

**Damit wird obsolet:**
- `_tune_converge_to_target` (`mw_tx.py:489-561`, ~75 LOC) — Phase-B-
  Convergenz die heute ohnehin nicht greift (FWDPWR bleibt bei 11.6W
  obwohl Soll 10W, Mike-Screenshot 25.05.)
- `_kruecken_skalierung` (`mw_tx.py:563-…`, ~50 LOC) — Premature
  Optimization
- Phase-B-Block in `_tune_stop`
- P76-B Phase-2-Label „Leistung wird auf 10 W eingeregelt …"

**Was bleibt:**
- TUNE = reiner ATU-Match-Vorgang (10W Träger, konfigurierte Dauer,
  tune_off + 2s Post-SWR-Check)
- P76-A SWR-Freeze, P63 SWR-Watchdog — Hardware-Safety
- Per-(Band, Watt) Slider-Speichern beim Live-FT8-TX

**Aufwand:** ~200 LOC netto Lösch + Test-Anpassung. Voller Workflow
Pflicht. Folge-Vorteil: massiv weniger Code = weniger Bug-Fläche
(P54+P54-FIX+P76-A+P76-B+P74-A waren alle Reaktionen auf Phase-B-
Komplexität).

---

## 🆕 Multiband-Integration (Mike 24.05.2026)

> ⛔ **NUR vor Ort am Radio anpacken** — niemals aus der Ferne.
> Grund: Slice-B aktivieren kann FlexRadio in einen Zustand bringen
> der nur per Power-Cycle / SSDR-Neustart heilbar ist.

**Status Konzept:** vollständig + DeepSeek-V4-pro-geprüft („Umsetzung
empfohlen, kein Overengineering"). Spec liegt in `multiband.md` —
Bänder-Auswahl-Modell (3-Stufen-Cycle OFF/RX/TX), Antennen-Modell
(ANT1 fix, keine Diversity), Senden Fall A/B, QSO-Puffer, TUNE-
Auslösung, 6h-Cache, F1–F7 Design-Entscheidungen.

**Umsetzungs-Phasen (jede eigener Workflow-Zyklus):**
1. **Phase A** — Slice-B-Plumbing reaktivieren (RX-only, kein UI-Switch)
2. **Phase B** — Band-Cycle-UI (3-Stufen OFF/RX/TX)
3. **Phase C** — Gemeinsame RX-Liste mit Band-Spalte + Band-Filter
4. **Phase D** — Sende-Serialisierung (TX-Flag-Swap, ATU-Recall)
5. **Phase E** — QSO-Puffer + Station-Klick-Verhalten
6. **Phase F** — TUNE-Auslösung beim Band-Hinzufügen + 6h-Cache

**Vor Phase A:** Tag `v0.98.X-pre-multiband` setzen, Push, lokales
Backup. Rollback-Anker fix.

**Berührt:** Slice-B-Code (unten — wird ADAPTIERT statt gelöscht).

---

## ⛔ NICHT LÖSCHEN — „Toter" Slice-B-Code in flexradio.py (Reserviert für Multiband, Mike 22.05.2026)

> ⛔⛔⛔ **DIESER CODE BLEIBT — SCHEINT NUR TOT** ⛔⛔⛔
>
> Slice-B-Diversity in `radio/flexradio.py` ist **NICHT zu entfernen**.
> Er ist die fertige Plumbing für das **Multiband-Feature** (siehe
> Multiband-TODO oben + `multiband.md`). Bei Multiband-Umsetzung wird
> dieser Code **adaptiert, nicht gelöscht**.
>
> **Mike-Anweisung (27.05.2026, wiederholt):** „der tote code darf
> nicht raus … wir brauchen den noch dafür nicht das der entfernt wird"
>
> **Selbst-Check für Claude:** Bei Backlog-Übersicht NIEMALS diesen
> Punkt als „auto-tauglich Refactor" empfehlen — Slice-B ist reserviert.

`radio/flexradio.py` enthält eine **zweite, unbenutzte** Diversity-
Implementierung („beide Antennen gleichzeitig" via 2. Slice + 2.
Panadapter + 2. Audio-Stream). Projektweit **kein einziger Aufrufer**
in heutiger Codebase.

**Code-Block (Zeilen-Anker Stand v0.97.90):**
- `__init__` Vars: Z. 83–87 — `_diversity_mode`, `_slice_idx_b`,
  `_rx_stream_id_b`, `_panafall_b`, `on_audio_callback_b`
- `enable_diversity()`: Z. 775–882
- `disable_diversity()`: Z. 884–920
- `set_frequency()` toter Zweig: Z. 929–930
- `set_rfgain_secondary()`: Z. 959–965
- `has_secondary_slice()`: Z. 967–969
- VITA-49-Dispatch toter Zweig: Z. 1331–1332

---

## 🆕 P64 — Simulations-Modus für Tests ohne Radio (Mike 16.05.2026) — 🔵 PRIO SEHR NIEDRIG (Mike 28.05.2026)

> 🔵 **Priorität sehr niedrig** (Mike 28.05.2026) — nice-to-have, kein
> Druck. Erst anpacken wenn nichts Wichtigeres ansteht.

**Use-Case (Mike):** ohne Radio-Zugriff trotzdem UI-Tests / Bug-Fixes /
neue Features visuell prüfen können. Künstliche Werte einspeisen.

**KISS-Vorschlag (V0 nicht spezifiziert):**

| Was | Komplexität | Aufwand |
|---|---|---|
| SWR-Wert simulieren via Env-Var | einfach | 1-2h |
| Einzelne fake Decoder-Messages | mittel | 0.5 Tag |
| Komplette QSO-Simulation | mittel-hoch | 1-2 Tage |
| Fake-Radio als RadioInterface-Subclass | hoch (Architektur) | 2-3 Tage |

Mike-Frage 16.05.: „können wir später zustände auch simulieren wie
imaginäre swr werte oder empfangende stationen oder zu komplex?"

**Aktuelle Lage 27.05.:** Multi-Radio-Refactor P121 hat die
RadioInterface-Architektur sauberer gemacht — Subclass-Variante wäre
jetzt einfacher umsetzbar.

---

## 🆕 P74-Rest — UX-Konsolidierung + Autogain-Konzept (Mike 18.05.2026)

P74-A (Modal-Konsolidierung) ist erledigt v0.97.94. Rest des P74-Bundles
(UX-Konsolidierung + Autogain) noch offen — Spec aus DeepSeek-Diskussion
18.05. in `prompts/p74_discussion.md`. Vor Workflow erneut Mike-Wunsch
schärfen — viel davon könnte durch P80 (Unified Gain Store) bereits
abgedeckt sein.

---

## 🆕 DeepSeek-Code-Vorschläge GitHub-Review 16.05.2026 — Sichtung 27.05.2026

Bei der README-Überarbeitung (v0.97.42 GitHub-Push) hat DeepSeek-V4-pro
in 6 Brainstorm-Runden **3 Code-Vorschläge** abgesetzt. Sichtung
27.05.2026 (autonom, Git-Diff `f19d748` und HISTORY Z. 14486-14492
verifiziert):

| Vorschlag | Status |
|---|---|
| **P67** — Auto-Hunt-Cap an Operator-Presence binden | ✅ **ERLEDIGT 16.05.2026** v0.97.43 als „P67 Auto-Hunt Mouse-Inactivity-Schicht (Variante C)". 5-Min-Mouse-Inactivity zusätzlich zur 10-Min-Hard-Cap. HISTORY Z. 4012. |
| **P69** — Konfidenz-Intervalle für Diversity-Tabellen (Bootstrap) | ✅ **ERLEDIGT 17.05.2026** v0.97.46 als „P69 Block-Bootstrap-Konfidenz-Intervalle". README + PDF mit 95%-CI. HISTORY Z. 3733. |
| **P68** — OMNI-CQ continuous gap re-evaluation innerhalb Paritäts-Block | ⏸ **NICHT UMGESETZT** — bewusste KISS-Entscheidung. Aktuell: `omni_cq.py:240` ruft `_init_audio_freq()` nur EINMAL pro Session (Sticky). DeepSeek-Argument („Worst-Case 10 OMNI-Nutzer gleiche Frequenz") ist hypothetisch — OMNI ist deaktiviert + Mike hat keine Field-Symptome gemeldet. Komplexitäts-Increase ohne Bug-Druck. |

**Resultat:** 2 von 3 erledigt, 1 bewusst verworfen. Liste komplett
abgearbeitet — Ticket kann zu.

---

# ⚠️ ALTE OFFENE TICKETS — Sichtung 27.05.2026

> Stand 27.05.2026 (autonome Sichtung): Code-Verifikation aller 4 Tickets
> durchgeführt. Ergebnisse unten — alle alten Tickets sind erledigt oder
> obsolet, keine offenen Architektur-Lücken mehr.

| ID | Was | Status (verifiziert 27.05.2026) |
|---|---|---|
| ~~P30~~ | MEMORY-LEAK 124 GB | ✅ **ERLEDIGT 13.05.** — Wurzel war TTS, nicht SimpleFT8 |
| ~~P12~~ | QSO-POSTPROCESSING-ASYNC (logbook.refresh-Hang) | ✅ **ERLEDIGT durch P12-Fix 11.05.** — `_LOGBOOK_MAX_ROWS=500` (`ui/logbook_widget.py:23`). 500 Zeilen sind synchron unkritisch (~10-50ms). Kein Hang mehr seit Fix; "Sauberer Async-Refresh" wäre Architektur-Verbesserung ohne Bug-Druck → **verworfen als KISS-Verletzung**. |
| ~~P27~~ | MESS-GUARD — vor Antennen/Diversity/Gain-Mess prüfen ob Radio verbunden | ✅ **ERLEDIGT durch P63 (AC9/AC13) + P82** — `_start_dx_tuning` hat 3-fach-Guard (`band in _swr_blocked_bands`, `radio.ip`, `tuner_present`). `_start_tune_only` returnt früh ohne `radio.ip` (`mw_radio.py:1700`). Re-Check vor `tune_off` (Z. 1721) deckt Offline-Race ab. Multi-Radio-Refactor P121 hat Architektur sauberer gemacht. |
| ~~P25~~ | RADIO-IP-LATE-SETTING | ✅ **OBSOLET** — `auto_connect()` läuft als Worker mit max_retries=10. P82 (Late-Connect-Override), P90 (Worker-Abort), P91 (Dialog-Lifecycle) decken alle Race-Fenster ab. Mike-Statement 10.05.: „wird normal gesucht und gefunden" weiterhin gültig. |

**Resultat:** alle 4 Alt-Tickets können aus dem aktiven Backlog raus.

---

# ✅ Frisch erledigt (24.-27.05.2026) — kompakt mit Versions-Anker

> Details + R1-Findings + Field-Validations: **HISTORY.md** (lückenlos)
> oder Memory `~/.claude-account1/.../project_pXXX_done.md`.

## 27.05.2026 (heute, 5 Workflows autonom)

| Version | Punkt | Field-Status |
|---|---|---|
| **v0.98.28** | P148 SWR-Anzeige nur während TX/TUNE | ⏳ Pending |
| **v0.98.27** | P145 Pattern-Check-Skript mode-aware Symmetrie | ✓ Selbst-validiert (Tool) |
| **v0.98.26** | P144 Auto-Hunt busy-station Filter | ✓ Field-validiert 08:50 (EA8UP-Skip) |
| **v0.98.25** | P147 HALT stoppt Auto-Hunt SOFORT (Hardware-Sicherheits-Fix) | ⏳ Pending |
| **v0.98.24** | P146 Kalibrierungstext mode-agnostisch | ✓ Field-validiert 08:50 |
| — | P140 73-vor-✓ Field-Test | ✓ Field-validiert 07:03 (KF0MSJ-Screenshot) |
| — | P141 Sterne-Diversity Field-Test | ✓ Field-validiert 06:30 |
| — | P106 QRZ-Confirmed-Bug | ✓ Field-validiert (QRZ bestätigt QSOs) |

## 26.05.2026 (vorige Session, 8 Workflows)

| Version | Punkt |
|---|---|
| v0.98.23 | P141 Sterne-Anzeige Diversity-Pfad (mode-aware Symmetrie 4. Iteration) |
| v0.98.22 | P143 QSO-Log-Resurrection nach Bandwechsel (Helper `clear_log_completely`) |
| v0.98.21 | P140 Cooldown-Trigger umgehängt (qso_complete → qso_confirmed_visual) |
| v0.98.20 | P139 Auto-Hunt Event-Logging (Diagnose-Tool, debug_log-Framework) |
| v0.98.19 | P138 P129-Whitelist entfernt („beendet ist beendet") |
| v0.98.18 | P137 „Sende" → „Gesendet" Tempora-Fix |
| v0.98.17 | P136 Call-Validation Auto-Hunt + Parser-Fix (`>=3` statt `==4`) |
| v0.98.16 | P135 Decode-Statusbar akkumuliert (mode-aware) |
| v0.98.15 | P131 Sende-Log bei Bandwechsel verwerfen (Defense-in-Depth) |
| v0.98.14 | P134 Python-Sweep entfernt (Pattern-Killing-Bug-Klasse beseitigt) |
| v0.98.13 | P132/P133 Single-Instance Architektur-Refactor (fcntl.flock + lsof-CWD) |
| v0.98.12 | P126 Send-nach-Timeout TX-Pipeline-Race-Fix |

## 25.05.2026

| Version | Punkt |
|---|---|
| v0.98.11 | P130 GAIN_VALUES = [0, 10, 20] zurück (Low-Band-Default) |
| v0.98.10 | P129 P128-Whitelist für 73/RR73 (Live-Field-Bug-Fix) |
| v0.98.09 | P120 Sterne-Schwellen FT8-realistisch |
| v0.98.08 | P127 Sende-Log bei SWR-Abbruch verwerfen |
| v0.98.07 | P128 Empf.-Eintrag 60s blocken nach ✓ QSO |
| v0.98.06 | P124 Hash-Call `<...>` kontextuell aus QSO auflösen (Mike-KISS-Idee) |
| v0.98.05 | P122 Auto-Hunt-Stop-Defer bei aktivem QSO |
| v0.98.04 | P121 Multi-Radio-Refactor Variante A (IC-7300/IC-7100 Vorbereitung) |

## 24.05.2026

| Version | Punkt |
|---|---|
| v0.98.03 | P118 Band-Activity Berliner Zeit (DST-aware via zoneinfo) |
| v0.98.02 | P117 Band-Aktivitäts-Übersicht-Script + Shell-Wrapper |
| v0.98.01 | P116 FIFO-Sliding-Window Stats-Cleanup |
| v0.98.00 | P115 Empfangsfenster bleibt bei RX-Mode-Switch/Kalibrierung |
| v0.97.99 | P114 MODUS+BAND Status-Suffix |
| — | Diagramm-Legende Tage-Coverage ehrlicher |

## 23.05.2026

| Version | Punkt |
|---|---|
| v0.97.98 | P113 Stale-Gain-Warning bei Bandwechsel |
| v0.97.97 | P102 Antennen-Kachel-Status-Sync (mode-aware Symmetrie 1. Iteration) |
| v0.97.96 | P100 Partial-Log bei R-Report-Empfang |
| v0.97.95 | P99 WAIT_RR73 Message-Cap |
| v0.97.94 | P74-A Modal-Konsolidierung (DXTuneDialog State-Machine) |
| v0.97.93 | Re-Mess-Countdown-Anzeige pro Slot |

---

# 📚 Historie + Doku-Verweise

- **HISTORY.md** — lückenlose Versions-Historie. Bei Versions-Recherche
  oder „wann wurde X gefixt": grep dort.
- **FEATURES.md** — funktionales Lexikon mit Lookup-Tabelle. Bei Bug-
  Analyse oder „wie hängt X mit Y zusammen": ZUERST hier.
- **HANDOFF.md** — aktueller Session-Stand + nächste 1-2 Schritte.
- **CLAUDE.md** — Workflow-Regeln, Architektur, Pattern-Familien.
- **multiband.md** — Multiband-Spec (DeepSeek-V4-pro-geprüft).
- **auswertung.md** — Statistik-Methodik + Diagramm-Generierung.

**Memory-Index:** `~/.claude-account1/projects/-Users-mikehammerer-Documents-KI-N8N-Projekte-FT8/memory/MEMORY.md`
— Cycle-Memories pro Workflow mit V1/V2/R1/V3-Findings.

---

# 📊 Tag-Bilanz 27.05.2026

- **Tests:** 2075 → **2138 grün** (+63 heute)
- **Versionen:** v0.98.22 → v0.98.28 (6 Bumps)
- **DeepSeek-Verbrauch:** ~$0.08 (~7 R1-Reviews)
- **GitHub-Commits gepusht:** 9 atomare Commits
- **V4-pro-Bilanz heute:** 5 Workflows, 0 Halluzinationen
- **Field-Validierungen:** P140, P141, P144, P146, P106
- **Hardware-Sicherheits-Fix:** P147 (HALT-Notbremse Mike-Vertrauen-Restore)

---

*Stand 27.05.2026 08:50 — TODO komplett aufgeräumt (vorher 6859 Zeilen).
Erledigte Tickets vor 24.05. archiviert in HISTORY.md.*
