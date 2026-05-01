# Universal Session-Lifecycle Workflow

**Version:** 2026-05-01 v1.2 (nach R1-Review von V2).

**Geltungsbereich:** Projekt-uebergreifend. Definiert Lese-/Pflege-/
Sicherungs-Pflichten ueber alle Session-Phasen.

**Ergaenzt** (nicht ersetzt) `docs/WORKFLOW.md` (Feature-Workflow
V1→V2→R1→V3). Der Feature-Workflow regelt einzelne Aufgaben — dieser
Workflow regelt die Session als Ganzes.

**Leitsatz:** „Wer beim Start nicht weiss wo er steht, plant Features
doppelt. Wer beim Ende nicht sichert, verliert Erkenntnisse." (Mike,
01.05.2026 nach 3-Releases-Tag.)

---

## R1-Bilanz V2 → v1.2

R1-Review (DeepSeek-R1) fand 3 echte Findings:

| Frage | R1-Antwort | V3-Aktion |
|---|---|---|
| P1 Lese-Reihenfolge | TRADEOFF — MEMORY vor HISTORY weil PFLICHT-Lessons | **Reihenfolge geaendert:** CLAUDE → **MEMORY** → HISTORY → HANDOFF |
| P2/P7-1 2a↔2b-Widerspruch | KRITISCH — Trivial vs 4-Datei-Update | **Trivial-Klausel** in 2b explizit |
| P3 Notfall-Save | JA — kein Overengineering | unveraendert |
| P4 Versionsbump | TRADEOFF — Patch fuer Cleanup | **Heuristik praezisiert** |
| P5 Memory-Pruning | JA — gut so | unveraendert |
| P6 cp vs symlink | JA — cp bleibt | **+ Hinweis: cp VOR Test-Count-Update** |
| P7-2 HANDOFF im Backup | nicht in V2 | **HANDOFF.md** in Backup-Liste |
| P7-3 reference-Typ ungenutzt | TRADEOFF | **Beispiel** ergaenzt statt streichen |

---

## 0. Datei-Verantwortlichkeits-Matrix

| Datei | Rolle | Schreib-Frequenz | Lese-Pflicht |
|---|---|---|---|
| **CLAUDE.md** (beide Pfade) | Stabile Regeln + Header mit aktuellem Stand | Bei jedem Release | **Session-Start (PFLICHT)** |
| **MEMORY.md** | Index aller persistenten Lessons | Bei neuer Lesson | **Session-Start (PFLICHT, vor HISTORY)** |
| **HISTORY.md** | Chronologisch, append-only | Nach jedem Fix/Feature | **Session-Start (letzte 3-5 Eintraege)** |
| **HANDOFF.md** (beide Pfade) | Aktueller Snapshot + offene Punkte | Nach jedem Fix/Feature | **Session-Start (PFLICHT)** |
| **memory/*.md** | Lessons-Detail | Bei neuer Lesson | Bei Bedarf (verwiesen aus MEMORY.md) |
| **prompts/*.md** | V1/V2/V3 Archiv pro Feature | Pro Feature-Workflow | Selten (Backtracking) |
| **docs/WORKFLOW.md** | Feature-Workflow V1.1 | Stabil, selten | Bei Bedarf |
| **docs/SESSION_WORKFLOW.md** | DIESES Dokument | Stabil, selten | Bei Bedarf |
| **docs/*_DESIGN.md** | Spec-Dokumente fuer komplexe Features (z.B. OMNI_TX_DESIGN.md) | Bei Erstellung + R1-Final | Bei Arbeit am Feature |
| **auswertung/*.md** | Statistik-Auswertungen / Lueckenlisten | On-demand | Selten |
| **feierabend.md** | Pointer auf Phase 3 dieses Workflows | Stabil | Bei Trigger „Feierabend" |
| **tools/remote/start_simpleft8_nokill.py** | Wrapper fuer Bash-Background-Start | Stabil | Bei Trigger „App-Start (Fernwartung)" |

---

## Phase 1 — Session-Start (Lesen + Merken)

### 1a. Pflicht-Reihenfolge (R1-Empfehlung: MEMORY vor HISTORY)

Bei JEDEM Session-Start, in dieser Reihenfolge:

1. **CLAUDE.md** (FT8/ ODER SimpleFT8/ — identisch). Header gibt aktuellen
   Stand: Version, Test-Count, letzter Release.
2. **MEMORY.md** — Index aller Lessons. ⛔-PFLICHT-Eintraege ZUERST. Diese
   Workflow-Lessons sind strenger als Release-Verlauf, deshalb VOR HISTORY.
3. **HISTORY.md** — letzte 3-5 Eintraege. Bei sehr grossen Files (>1500
   Zeilen): gezielt mit `tail -100` oder `grep -A30 "^## "`.
4. **HANDOFF.md** — heutiger/letzter Stand, offene Punkte, Warnungen.

**Realistische Dauer:** 30-60 Sekunden. Mike merkt's nicht — er sieht
nur die Begruessung in 1c.

### 1b. Was sich Claude merken muss

Aus den 4 Files extrahieren und im aktiven Kontext halten:

- **Aktuelle Version + letzter Release** (CLAUDE.md Header).
- **PFLICHT-Memory-Lessons** (⛔-Eintraege in MEMORY.md) — z.B.
  Workflow-Pflicht, TODO-vor-Code-Verifikation, App-Start-Trigger.
- **Letzte 3-5 Releases mit Kurztitel** (HISTORY.md).
- **Offene Punkte / TODO** (HANDOFF.md) — getrennt nach „echten TODOs"
  und „Field-Test/Daten-Sammeln".
- **Heute neu beobachtet** (HANDOFF.md Sektion fuer offene Bugs vom
  Vortag).
- **Bekannte Bugs / Fallen** (CLAUDE.md + HANDOFF.md).
- **Hardware-/Domain-Pflichten** (CLAUDE.md Top: ANT1=TX, ANT2=RX-only).

### 1c. Begruessungs-Format

Erst NACH den 4 Reads:

```
Stand: vX.YY ([Kurztitel des letzten Release])
Tests: NNN gruen
[Optional] ⚠ Offen vom Vortag: [Bug X aus HANDOFF "Heute neu beobachtet"]
[Optional] 📊 Daten-Status: [z.B. "30m FT8: 56 Slots fehlen"]
Was machen wir heute?
```

Warnungs-Zeile + Daten-Status sind optional — nur wenn HANDOFF/Memory
eine Aufmerksamkeit erfordert.

### 1d. Anti-Patterns Phase 1

- ❌ Direkt mit Feature-Vorschlaegen ohne HISTORY-Read.
- ❌ TODO-Listen aus altem HANDOFF wiederholen ohne Code-Verifikation
  (Memory `feedback_todo_history_pflicht.md`).
- ❌ MEMORY.md ueberspringen — PFLICHT-Lessons werden ignoriert.
- ❌ Bei grossem HISTORY.md ALLES lesen statt gezielt letzte Eintraege.

---

## Phase 2 — Arbeit (Aufgaben durchfuehren)

### 2a. Aufgabe-Klassifizierung

| Aufgabe | Workflow | Phase 2b PFLICHT? |
|---|---|---|
| Trivial (<5 Zeilen, Tippfehler, Kommentar) | Direkt machen | **NEIN** (Trivial-Klausel) |
| Operativ (App starten, Statistik regen, Memory-Update) | Direkt, ggf. Trigger-Memory | NEIN |
| Nicht-trivial (Feature, Bugfix, Architektur, neues Modul) | **`docs/WORKFLOW.md` v1.1** | **JA** |

### 2b. PFLICHT nach JEDEM nicht-trivialen Punkt (R1-P2-Fix)

**Trivial-Klausel** (R1-P7-1): Phase 2b gilt NUR fuer nicht-triviale
Aufgaben aus 2a. Tippfehler, Kommentar-Updates, < 5-Zeilen-Patches
brauchen KEIN HISTORY/HANDOFF/CLAUDE-Update.

Fuer alle nicht-trivialen Aufgaben (Feature, Bugfix, Refactor, Cleanup,
Release): Reihenfolge IMMER in dieser Sequenz, BEVOR naechste Aufgabe:

1. **HISTORY.md** anhaengen — `## YYYY-MM-DD vX.YY — Kurztitel` + voller
   Eintrag (Workflow-Reflexion, R1-Findings, Lessons).
2. **HANDOFF.md** beide Pfade synchron — TODO-Punkt raus, neuer Stand
   rein, Test-Count.
3. **CLAUDE.md** beide Pfade synchron — Header `Aktueller Stand: vX.YY`
   + Test-Count.
4. **Memory** — neue Lesson? Eintrag schreiben + MEMORY.md-Index
   ergaenzen (mit ⛔-Marker bei PFLICHT-Eintraegen).

**Sync-Reihenfolge der beiden Pfade (R1-P6):**
`cp FT8/CLAUDE.md SimpleFT8/CLAUDE.md` IMMER NACH dem Edit der
Master-Datei (FT8/), VOR dem Test-Count-Update. So vermeidet man
divergente Test-Count-Stände.

### 2c. Versionsbump-Heuristik (R1-P4-Fix)

| Aenderung | Bump |
|---|---|
| Tippfehler/Trivial | **kein Bump** (kein Release) |
| Doku-only (HISTORY, HANDOFF, CLAUDE-Stand) | **kein Bump** (kein Release) |
| **Cleanup / Dead-Code-Removal / Refactor ohne Verhaltens-Aenderung** | **Patch (v0.X.Y+1)** ODER Mini-Bump (v0.X+1 wenn klare Workflow-Iteration) |
| **Bugfix mit Verhaltens-Aenderung** | **Minor (v0.X+1)** |
| **Feature** | **Minor (v0.X+1)** |
| **Breaking change / Public Release** | **Major (v1.0)** |

**Faustregel:** 1 atomarer Workflow-Durchlauf = 1 Minor-Bump (Default).
Cleanup-only-Releases (wie v0.85 heute) koennten Patch-Bumps werden um
Versions-Inflation zu vermeiden — Mike entscheidet pro Release.

### 2d. Erkenntnisse-Erfassung waehrend der Arbeit

Wenn waehrend der Arbeit etwas auffaellt: **NICHT bis Feierabend
warten** — sofort:

- **Bug von Mike gemeldet** → HANDOFF.md unter „Heute neu beobachtet"
  + Diagnose + Fix-Idee.
- **Pattern-Verdacht** (etwas was zwei Mal nervt, falsche Annahme,
  Tool-Marotte) → Memory-Eintrag schreiben, MEMORY.md ergaenzen.
- **Halluzinations-Erkenntnis** (TODO war erledigt, R1 hat etwas
  uebersehen) → Memory ergaenzen wenn Pattern, sonst nur HANDOFF.

### 2e. App-Start

**Explizite Trigger-Phrasen:**
- „neu starten", „restart", „App killen", „App neu" → Standard-Restart
- „SimpleFT8 am Ferienhaus", „starte am Ferienhaus" → Memory
  `project_simpleft8_ferienhaus.md` Wrapper-Routine
- „Monitor X" / „Display X" / „auf falschem Bildschirm" → Display-
  Verschieben via Window-Title `"DA1MHH"`

**Standard-Restart-Routine:**
1. `pkill -9 -f "SimpleFT8/main.py"` + `pkill -9 -f
   "start_simpleft8_nokill"`.
2. Ports 4991/4992 freiraeumen (`lsof -ti UDP:4991 | xargs kill -9`).
3. **Wenn Fernwartung-Trigger:** Wrapper-Start +
   Display-Verschieben via Memory.
4. **Wenn lokal:** Mike soll im Terminal selbst starten.

### 2f. Notfall-Save (Session bricht abrupt ab)

Trigger: „muss kurz weg", „Notruf", „Plenum jetzt", „speichere alles
sofort". ODER: Tool/Hooks-Fehler signalisieren Session-Ende.

**Quick-Save-Routine (max 60 Sekunden):**

1. Wenn Code-Aenderungen ungesichert: nicht-committed → ein
   Notfall-Commit `wip(emergency-save): [Kurztitel] — uncommitted
   changes`. NICHT pushen.
2. HISTORY.md mit „**WIP-Stand**" markieren (Format: `## YYYY-MM-DD
   WIP — [was war gerade in Arbeit]`).
3. Bestaetigung: „WIP gesichert. Naechste Session: WIP-Eintrag in
   HISTORY.md, dann ueber Wiederaufnahme entscheiden."

### 2g. Anti-Patterns Phase 2

- ❌ TODO-Liste an Mike geben ohne `git log --oneline | head -20` +
  grep-Verifikation.
- ❌ Pflicht-Reihenfolge 2b skippen weil „nur kleine Aenderung".
  Skip-Lawine: kleine Aenderung undokumentiert → naechste baut drauf
  → Halluzination-Risiko.
- ❌ Trivial-Klausel mit „Bugfix unter 10 Zeilen" verwechseln.
  Bugfixes mit Verhaltens-Aenderung sind nicht-trivial, brauchen
  Phase 2b.
- ❌ Erkenntnisse erst am Feierabend schreiben (verloren bei
  Session-Crash).
- ❌ R1-Findings blind uebernehmen ohne Schritt 2.5
  (Code-Verifikation, siehe WORKFLOW.md v1.1).
- ❌ Self-Review V2 skippen weil „Aufgabe trivial" — Aufwand-
  Klassifizierung war falsch (z.B. dieser Workflow selbst:
  V1 ohne Self-Review, Mike musste mahnen).

---

## Phase 3 — Session-Ende (Feierabend, Sichern)

### 3a. Trigger

„Feierabend", „feierabend.md", „Schluss machen", „Tag fertig",
„Feierabend-Routine".

### 3b. Verifikations-Reihenfolge

Wenn Phase 2 die HISTORY/HANDOFF/CLAUDE/Memory bereits nach jedem
nicht-trivialen Punkt aktualisiert hat (siehe 2b), ist Phase 3 nur
ein **Verifikations-Check**:

1. **HISTORY.md** — letzten Eintrag auf Vollstaendigkeit pruefen.
2. **HANDOFF.md** beide Pfade synchron + Stand auf neueste Version.
3. **CLAUDE.md** beide Pfade synchron, Header korrekt, Test-Count
   stimmt mit `pytest -q | tail -1`.
4. **MEMORY.md** + memory/*.md — alle heutigen Lessons drin?
5. **App-Status** — laeuft die App noch oder beendet? Ports frei?
6. **Bestaetigungs-Block ausgeben** (3c).

### 3c. Bestaetigungs-Block (Format)

```
✅ HISTORY.md — [N] Release-Eintraege heute (vX.AA, vX.BB, ...)
✅ HANDOFF.md — beide Pfade auf vX.YY, NNN Tests, offene Punkte gepflegt
✅ CLAUDE.md — beide Pfade auf vX.YY, Test-Count NNN
✅ MEMORY — [N] neue Lessons / [N] aktualisiert
✅ App: [Status — laeuft / beendet / weiter geplant]
✅ Morgen: cd SimpleFT8 ODER cd FT8 → claude1 → laedt automatisch
```

### 3d. Backup-Heuristik (R1-P7-2-Fix: HANDOFF.md mit drin)

Wenn Mike heute risikobehafteten Code geaendert hat:

| Aenderung | Backup? |
|---|---|
| Algorithmus (Decoder, Encoder, AGC, Diversity-Logik) | **JA** |
| TX-Pfad (PTT, Audio-Stream, Encoder-Timing) | **JA** |
| State-Machine (qso_state, on_cycle_end, on_decoder_finished) | **JA** |
| UI-only (Dialoge, Layout, Buttons) | NEIN |
| Doku/Tests/Comments | NEIN |
| Statistik-Skripte (generate_plots) | NEIN |
| Dead-Code-Cleanup | NEIN |

**Backup-Inhalt** (R1-Empfehlung HANDOFF.md mit drin — enthaelt
„Heute neu beobachtet"):

```bash
mkdir -p Appsicherungen/$(date +%Y-%m-%d)_<kurzer_grund>
cp -r core ui tests main.py HISTORY.md HANDOFF.md prompts \
  Appsicherungen/$(date +%Y-%m-%d)_<kurzer_grund>/
```

Code-only-Backups sind ~4 MB — billig.

### 3e. Anti-Patterns Phase 3

- ❌ Erkenntnisse erst am Feierabend dokumentieren (siehe 2d/2f).
- ❌ HISTORY.md skippen weil „nur eine kleine Aenderung".
- ❌ Nur einen der beiden CLAUDE.md/HANDOFF.md-Pfade aktualisieren.
- ❌ Bestaetigungs-Block weglassen.
- ❌ Backup ohne HANDOFF.md (verliert „Heute neu beobachtet").

---

## Memory-Strukturierung

`MEMORY.md` ist Index, NICHT Dokument. Jede Zeile:
`- [Titel](datei.md) — ein-Zeilen-Hook`.

### Memory-Typen

- **`user`** — Wer ist Mike, was sind seine Praeferenzen.
- **`feedback`** — Workflow-Anweisungen, Lessons aus Korrekturen.
  PFLICHT-Eintraege mit ⛔-Marker.
- **`project`** — Setup-Snapshots (Ferienhaus-Display, Antennensetup,
  Workflow-Skript-Pfade).
- **`reference`** — Externe Pointer. Beispiele:
  - „PSK-Reporter API-URL" (mit JSON-Schema-Verweis)
  - „FT8-Spec PDF: K9AN/G3WDG/K1JT 2018"
  - „HamQSL XML-Endpoint: hamqsl.com/solarxml.php"
  - GitHub-Issues-Tracker oder Linear-Project-IDs falls relevant.

Wenn `reference`-Typ ein Jahr lang ungenutzt: bei Memory-Pruning
streichen.

### Memory-Eintrag-Template

```markdown
---
name: [Kurztitel — wird im MEMORY.md-Index angezeigt]
description: [ein Satz — was diese Lesson festhaelt]
type: [user | feedback | project | reference]
---

# [optional ⛔ PFLICHT — falls Workflow-relevant]

**Auslöser:** [Datum + Kontext warum Lesson noetig wurde]

**Lesson:** [Kern-Aussage in 1-2 Saetzen]

## Why
[Begruendung — warum ist das so, was waere die Alternative?]

## How to apply
[Konkrete Aktion — was macht Claude in welcher Situation?]

## Trigger-Phrasen (wenn anwendbar)
[Was sagt Mike, das diese Lesson aktiviert]
```

### MEMORY.md-Index-Reihenfolge

PFLICHT-Eintraege (⛔-Marker) ZUERST. Dann nach Typ gruppiert
(user → feedback → project → reference).

### Memory-Pruning

Wann werden Lessons irrelevant?

- **Code-Pfad existiert nicht mehr** — Lesson zu einer entfernten
  Funktion: Eintrag entfernen ODER mit ⚠ ARCHIVIERT markieren.
- **Lesson ueberholt** — neue bessere Version: alten Eintrag
  entfernen, MEMORY.md-Index ergaenzen.
- **Reference-Pointer tot** — externes System weg: Eintrag entfernen.

Pruefung vorschlagen: Quartalsweise oder bei Memory-Index > 30
Eintraege. Aktuell ~12 Eintraege — nicht akut.

---

## CHANGELOG

### v1.2 — 2026-05-01 (R1-Review V2)

R1-Findings eingearbeitet:
- Lese-Reihenfolge **MEMORY vor HISTORY** (P1).
- **Trivial-Klausel** in 2a/2b explizit (P2/P7-1, R1's KRITISCH-Finding).
- Versionsbump-Heuristik praezisiert: Cleanup → optional Patch (P4).
- **HANDOFF.md im Backup-Inhalt** (P7-2).
- `reference`-Memory-Typ mit Beispielen (P7-3).
- Sync-Reihenfolge cp VOR Test-Count-Update (P6).
- Anti-Pattern „Trivial-Klausel-Missbrauch" in 2g.

### v2.0 — 2026-05-01 (Self-Review V1)

9 Self-Review-Verbesserungen (Notfall-Save, Versionsbump, App-Trigger,
Begruessungs-Warnungen, Backup-Heuristik, Memory-Template, etc.).

### v1.0 — 2026-05-01

Erstdokument. Mike-Anweisung 01.05. nach 3-Releases-Tag (v0.83 + v0.84
+ v0.85): Erkenntnisse + offene Punkte + Einstellungen sollen bei
Start gelesen und bei Feierabend gesichert werden.
