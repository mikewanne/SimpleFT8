# SimpleFT8 TODO — Stand 27.05.2026 (v0.98.28)

> **Diese Datei = Backlog (aktiv-offen + frisch erledigt).**
> Vollständige Historie aller Änderungen: **HISTORY.md** (nur anhängen).
> Funktions-Doku: **FEATURES.md** (Pattern-Familien, Architektur).
> Aktueller Session-Stand: **HANDOFF.md**.

---

# 🟢 LAUFEND — Field-Test pending

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

# ⏸ AUFGESCHOBEN — Hardware-Repro nötig (Mike vor Ort)

## P142 — Bandsperre-Freigabe meldet falschen SWR-Wert (Mike Field 26.05. 17:24)

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

## 🎨 P123 — Status-Text Tempora + QSO-Start-Anzeige (UX, Mike 25.05.2026)

> ⚠️ Kein Bug, sondern UX-Verbesserung. Mike-Wunsch: erst mit DeepSeek
> brainstormen (2-3 Varianten), Mike-Decision, DANN Workflow + Code.

**Hinweis 27.05.:** P137 hat den Tempora-Fix „Sende"→„Gesendet" bereits
umgesetzt für das QSO-Log. Was bleibt: **Pre-TX-Anzeige beim QSO-START**.

**Mike-Wunsch:** beim QSO-START vor dem ersten TX eine Status-Meldung
anzeigen die signalisiert „wir senden jetzt", damit Benutzer sieht
dass QSO gleich anfängt.

**Brainstorm-Themen für DeepSeek:**
1. Pre-TX-Meldung als eigener Log-Eintrag oder Statusbar-Toast?
2. Format A: „⏳ Bereit: Sende SX20RCK DA1MHH -15 in 0.3s" (Pre) +
   „✓ Gesendet: SX20RCK DA1MHH -15" (Post)
3. Format C: Symbol-Auto (P79-Pattern) → ⏳ während TX, ✓ nach TX

**Severity:** ⚪ UX-Polish, kein Bug. Autonom-tauglich + Remote.

---

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

## 🆕 AP-Lite QSO-Abschluss (Konzept dokumentiert)

Erweiterung von AP-Lite (Option D = v0.97.90 erledigt). Vollständiges
Vorgehen + gestaffelter Plan in HISTORY.md „Konzept: AP-Lite QSO-Abschluss"
(22.05.2026). Reihenfolge:
1. Breites Rapport-Kandidaten-Fenster
2. Feld-Beobachtung mit `AP = (x)`-Zähler
3. ERST danach Auto-Abschluss/Loggen

Schritt 3 nicht vorab bauen — die Beobachtung ist die Validierung.

---

## 🆕 P64 — Simulations-Modus für Tests ohne Radio (Mike 16.05.2026)

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

## 🆕 DeepSeek-Code-Vorschläge sichten (GitHub-Review 16.05.2026)

DeepSeek hat bei einem GitHub-Code-Review mehrere kleine Vorschläge
gemacht. Liste ist ungesichtet. Pro Vorschlag prüfen:
- Noch relevant nach P121 Multi-Radio + P116 FIFO-Cleanup + P132-134
  Single-Instance-Refactor?
- KISS-konform?
- Hardware-Sicherheit OK?

Erwartet: viele kleine Wins, einige obsolet, ein paar wertvoll.

---

# ⚠️ ALTE OFFENE TICKETS — Status unklar, Sichtung nötig

> Diese Tickets stammen vom 10.-11.05.2026 und stehen unverändert in der
> alten TODO. Status muss geprüft werden — manches könnte durch spätere
> Refactoring-Workflows obsolet geworden sein.

| ID | Was | Vermutlicher Status |
|---|---|---|
| ~~P30~~ | MEMORY-LEAK 124 GB | ✅ **ERLEDIGT 13.05.** — Wurzel war TTS, nicht SimpleFT8 (HISTORY.md) |
| P12 | QSO-POSTPROCESSING-ASYNC (logbook.refresh-Hang) | **PARTIAL-FIX 11.05.** Logbuch nur letzte 500. Sauberer Async-Refresh noch offen — Status mit Mike klären |
| P27 | MESS-GUARD — vor Antennen/Diversity/Gain-Mess prüfen ob Radio verbunden | Unklar — könnte durch P82 (Connect-Worker-Abort) oder Multi-Radio-Refactor abgedeckt sein |
| P25 | RADIO-IP-LATE-SETTING | Wahrscheinlich obsolet — Mike 10.05.: „radio ist nicht spät, wird normal gesucht und gefunden" |

**Empfehlung:** bei nächster Doku-Session diese 4 mit Mike durchgehen
und entscheiden: bleiben / erledigt / verworfen.

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
