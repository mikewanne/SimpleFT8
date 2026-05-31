# HANDOFF — SimpleFT8

**Aktueller Stand:** v0.98.48 (30.05.2026) — **P164 Klick auf uns-rufende Station
generalisiert** (P158-Nachfolger). Tests 2212 grün. **Lokal committet (9034884),
NICHT gepusht.**

---

## Letzte Session (30.05.2026)

### P164 — eine Station die UNS ruft ist im QSO-Log IMMER klickbar (NEU, v0.98.48)

Voller DeepSeek-Workflow (V1→V2→R1→V3→Code→Final-R1, alle Runden v4-pro).
**Final-R1 Runde 2: PUSH FREIGEBEN, 0 Blocker.** Commit `9034884`.

**Was:** Generalisierung von P158. Vorher war die `← Empf.`-Zeile im QSO-Log nur
klickbar wenn Auto-Hunt aktiv + anderes QSO lief — Mikes Field-Fall (YO60GW rief
während manuellem EG5SUN-QSO) fiel durchs Raster. Jetzt: klickbar sobald eine
Station uns ruft (+ kein 73/rr73 + nicht CQ-Modus + nicht der aktuelle Partner =
Doppel-Ruf-Schutz). Klick-Wirkung state-abhängig: IDLE→sofort rufen, aktives QSO
mit A→A zu Ende, dann B einschieben. Doktrin „Höflichkeit > Stationszahl".

**Architektur:** Merker `_insert_pending_call` aus `auto_hunt` ENTFERNT → ersetzt
durch `_qso_pending_insert` in MainWindow (vom Auto-Hunt entkoppelt). Ein
Klickbar-Prädikat, ein Merker, ein Start-Pfad (`_on_station_clicked` — alle
Safety-Guards inkl. ANT1-TX-Verriegelung intakt). Alias `ACTIVE_QSO_STATES =
HASH_RESOLVE_STATES`.

**DeepSeek-Verlauf:** Plan-R1 NO-GO→GO (F2 🔴 HALT-Null, F4 Alias). Final-R1 Runde 1
NACHBESSERN (2 🔴: HALT-Null fehlte noch, IDLE-Sofort-Ruf nutzte `clear()` statt
`pop(call)`). Beide behoben. Final-R1 Runde 2 PUSH FREIGEBEN.

**Geänderte Code-Dateien:** `core/qso_state.py` (Alias), `core/auto_hunt.py` (alte
API + Dead Code raus), `ui/mw_cycle.py` (Klickbar-Prädikat + state-abhängiger
Klick-Handler + Import), `ui/mw_qso.py` (maybe_start entkoppelt + HALT-Null),
`ui/main_window.py` (Merker-Init), `ui/mw_radio.py` (Cleanup Band/Mode/RX).
Plus Tests + FEATURES §17 + HISTORY + CLAUDE-Header + Memory.

**Tests:** `test_p158_insert_pending_call.py` komplett auf P164 (34 Tests).
Volle Suite **2212 passed, 0 Regression**.

### Vorher gleiche Session: P162-Rücknahme (v0.98.47)

P162 war eine Fehldiagnose (kein U+2212-Bug; YO60GW rief blind während wir EG5SUN
riefen, Code war immer korrekt). Phantom-Fix entfernt, kein TODO-Eintrag.
Commit `cd91712`.

---

## ⛔ OFFEN — Push-Freigabe einholen (3 lokale Commits, NICHT gepusht)

origin/main = `e6426ec` (Stand mit v0.98.46 + der P162-Falschbehauptung „GELÖST").
Lokal voraus:
1. `cd91712` — P162-Revert (korrigiert die öffentliche Falschbehauptung).
2. `9034884` — P164 (neues Feature).

**Beides braucht Mike-Freigabe zum `git push`** (Standing-Regel: push nur auf
explizite Anfrage). Empfehlung: pushen, damit die öffentliche Doku nicht weiter
einen nie-existierten Fix behauptet (Mike-Prinzip „nur behaupten was verifizierbar
ist").

---

## Nächste Schritte

1. **Push-Freigabe** für cd91712 + 9034884 (siehe oben).
2. **P164 Field-Test** (Mike): während manuellem QSO ODER im IDLE eine
   uns-rufende Station im QSO-Log anklicken → IDLE = sofort gerufen, aktives QSO
   = nach dem QSO eingeschoben. Doppelklick-Hinweis: P164-Zeile ist ein
   Einzelklick-Link (QTextBrowser anchorClicked), NICHT der RX-Listen-Doppelklick.
3. Optional zurückgestellt: 30m-README-Publikation (Standard +18%, CI +2-+38%).

---

## ⚠ Tooling-Warnung (diese Session durchgehend aktiv)
Bash/Read-Ausgaben zeitweise trunkiert/verzögert/vermischt; ganze parallele
Tool-Gruppen brachen durch einen Einzelfehler ab. Dateien selbst sind korrekt —
Verifikation NUR über Python-Counts + pytest-Returncode in Datei, nie der Anzeige
trauen. Diese Session entlarvte 2 Phantom-Bugs (vermeintlich „doppelter Import" +
„take_pending_insert im Body") als reine Anzeige-Artefakte. Lesson für Tests:
Methoden-Extraktions-Regex `(?=\n    def )` läuft über @decorator-Methoden hinaus
→ `(?=\n    (?:def |@))` nutzen.
