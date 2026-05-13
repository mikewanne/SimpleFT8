# Compact-Notes — Stand vor P1.5-Workflow (2026-05-05)

Datei dient nur als Sicherung des Konversations-Kontexts vor /compact.
V1 setzt darauf auf.

## Gerade abgeschlossen: v0.95.1 ✅

- Commit `04388ef` (encoder.py + main.py) + `19ecb84` (Doku)
- **Bug v0.95.1:** TX-Slot-Tag haengt 1 Slot zurueck. encoder.py:281
  nutzte `time.time()` zur ptt_on()-Aufruf-Zeit (1.3s VOR next_boundary,
  TARGET_TX_OFFSET=-0.8 + 0.5s Stille-Padding). `floor(/15)*15` rundete
  damit auf vorherigen Slot ab.
- **Fix:** `tx_started.emit(message, _tx_even, next_boundary)` — Encoder
  uebergibt seinen bereits berechneten Ziel-Slot direkt.
- **Field-Test-Validierung 05:27-05:30 UTC** (Mike's Screenshot 1):
  - `05:27:30 [E] → Sende DA1TST DA1MHH -21`
  - `05:27:45 [O] ← Empf. DA1MHH DA1TST R+18`
  - `05:28:00 [E] → Sende DA1TST DA1MHH RR73`
  - `05:28:15 [O] ← Empf. DA1MHH DA1TST 73`
  - 2 komplette QSOs in Folge, TX `[E]` und RX `[O]` sauber getrennt.
- 756 Tests gruen
- App PID 32989 laeuft ohne Debug-Linien

## P1.5 — CQ-Reply-Bug (NEU, jetzt in Diagnose)

**Symptom Field-Test 05:30-05:33 UTC** (Screenshot 2 Mike):
FlexRadio im CQ-Modus empfaengt DA1TST-CQ-Antwort `DA1MHH DA1TST J031`,
ignoriert sie aber, sendet weiter CQ statt Report. DA1TST wiederholt
3-4 mal:
```
05:30:45 [O] → Sende CQ DA1MHH J031
05:31:15 [O] → Sende CQ DA1MHH J031
05:31:30 [E] ← Empf. DA1MHH DA1TST J031   ← IGNORIERT
05:31:45 [O] → Sende CQ DA1MHH J031        ← Sollte Report sein!
05:32:15 [O] → Sende CQ
05:32:30 [E] ← Empf. DA1MHH DA1TST J031   ← IGNORIERT
05:32:45 [O] → Sende CQ
05:33:00 [E] ← Empf. DA1MHH DA1TST J031   ← IGNORIERT
05:33:15 [O] → Sende CQ
```

**Mike's Aussage:** Das ist seit langem ein Problem ("manchmal klappt
ein QSO, manchmal nicht"). NICHT nur Test-Setup, auch im echten Betrieb.
**Es ist ein Bug, kein Feature.** (Mike's klare Ansage.)

## Bisherige Code-Verdachts-Stellen (NUR Lokalisierung, nicht verifiziert)

- `core/qso_state.py:120` `_WORKED_BLOCK_SECS = 300` — 5-Minuten-Sperre
  nach erfolgreichem QSO
- `core/qso_state.py:168-176` `_is_worked_recently()` — TS-basierte
  Sperre, prueft ob Station <300s gearbeitet
- `core/qso_state.py:178-203` `_process_cq_reply()` — verarbeitet
  `_pending_reply`, wechselt State zu TX_REPORT/TX_RR73
- `core/qso_state.py:388-396` `on_message_sent()` — wird nach TX-Ende
  vom Encoder aufgerufen, prueft `_pending_reply` und ruft
  `_process_cq_reply()`
- `core/qso_state.py:450-491` `on_message_received()` — kompletter
  CQ-Reply-Empfangs-Pfad. Bei CQ_CALLING wird `_pending_reply = msg`
  gesetzt, aber NICHT direkt verarbeitet (haengt auf TX-Ende). Bei
  CQ_WAIT/IDLE wird `_process_cq_reply()` direkt aufgerufen.
- `ui/mw_qso.py:211-214` `_on_tx_finished()` → ruft
  `self.qso_sm.on_message_sent()` (per `tx_finished`-Signal vom Encoder).

**Gegen die "_is_worked_recently zu aggressiv"-Hypothese:** Mike hatte
DA1TST gerade in :30:15 fertig. 1:15 Min spaeter waere Sperre noch aktiv.
Das WUERDE den DA1TST-Test-Effekt erklaeren. Aber Mike sagt: tritt auch
mit fremden Stationen auf, wo die Sperre nicht greift → andere/zusaetzliche
Wurzel.

## Workflow fuer P1.5 (Mike-Plan, kein Skip)

1. **Schritt 0** — Code-Verifikation: `core/qso_state.py` komplett +
   `ui/mw_qso.py` (Connect-Pfade) + `ui/mw_cycle.py:on_message_decoded`
   + tests/test_modules.py CQ-Reply-Tests + `core/encoder.py:_tx_worker`
   (wann tx_finished feuert).
2. **V1** — `prompts/cq_reply_bug_v1.md`: Symptom mit Datei:Zeile-
   Belegen, Code-Pfad-Trace eines DA1TST-Reply-Empfangs (timeline
   millisekunden-genau), Race-Condition-Kandidaten, Hypothesen-Liste
   mit Code-Evidenz. KEINE Lösung — nur Analyse.
3. **V2** — Self-Review als frische KI, GENAU. V1 Zeile fuer Zeile.
   Was fehlt, was mehrdeutig, welche Edge-Cases nicht durchdacht.
   Threading-Race (Decoder-Thread / GUI-Thread / Encoder-Thread).
4. **V3** — nochmal frische KI, V2 GENAU pruefen, optimieren, ergaenzen,
   Hypothesen mit Code-Evidenz belegen.
5. **DeepSeek-R1** — V3 + Code-Files mit `tools/deepseek_review.py`.
6. **R1-Validierung** — Halluzinations-Check, Code-grep gegen R1's
   Behauptungen.
7. **Mike vorlegen** — Diagnose + Loesungs-Optionen mit Trade-offs.

## Hardware-Setup (fuer Field-Tests)

- FlexRadio = DA1MHH (Mike's Hauptgeraet)
- IC-7300 = DA1TST (Gegenstation, manuell auf EVEN oder ODD stellbar)
- ANT1 = TX-Antenne (immer)
- ANT2 = nur RX (NIEMALS TX, Hardware-Schaden!)

## Mike's Disziplin-Anforderungen

- Keine Annahmen — Code grepen
- Keine "vielleicht ist es Feature"-Mätzchen
- Keine ja/nein-Bestätigungs-Fragen
- Code-Aenderungen erst NACH V3 + Mike-Freigabe
- Atomare Commits, einer pro logischer Schritt
- Effort=xhigh fuer P1.5
- "Wie ein Chirurg" — sauber, schrittweise

## Andere offene Punkte (TODO)

- **P1.6:** Versionsnummer-Anzeige fehlt (Mike sieht v0.95.1 nicht unten
  rechts). Trivial-Diagnose, niedrige Prio.
- **P2:** Reply-Lag durch Audio-Buffer-Latenz. Wartet auf P1.5-Diagnose.

## Memory zu beachten

- `feedback_workflow_no_exceptions.md` — JEDE Code-Aenderung V1→V2→R1→V3
- `feedback_workflow_after_failed_fix.md` — Disziplin nach Field-Test-
  Scheitern
- `feedback_app_start_single_instance.md` — bei App-Start IMMER alte
  Instanz killen, EINE neu starten
- `feedback_workflow_works_with_deepseek.md` — Mike-bestaetigt 30.04.
- `feedback_todo_history_pflicht.md` — nach jedem Fix HISTORY+HANDOFF+
  CLAUDE+Memory updaten
