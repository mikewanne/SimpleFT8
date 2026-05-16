# P61 V2 — Self-Review

## V2-Findings (selbstkritische Durchsicht V1)

### F1 — Cooldown-Key zu grob (KRITISCH)

V1 nutzt `base_call` als Key. Aber `_recent_qso` ist nicht Band-spezifisch
im Dict selbst; es wird stattdessen bei `set_band` geclear-t. Das bedeutet:

- User auf 20m macht QSO mit HA8RC → `_recent_qso["HA8RC"] = T`
- User wechselt Band auf 40m → `_recent_qso.clear()` → leer
- User wechselt zurück auf 20m → leer → HA8RC sofort wieder pickbar

**Das ist falsch:** ein QSO mit HA8RC auf 20m sollte 5 Min lang verhindern
dass HA8RC auf 20m wieder gepickt wird, AUCH WENN User zwischendurch auf
40m wechselt.

**Fix V3:** Key sollte `(base_call, band)` sein. Kein `clear()` bei
`set_band`. Mode-Trennung ist Hobby-Praxis-Frage — V1 Q1 sagte ja, also
Key `(base_call, band, mode)`. Cleanup via `_prune_recent_qso(now)`
(entferne Einträge älter als COOLDOWN_S) periodisch oder bei Zugriff.

### F2 — Race zwischen `_run_auto_hunt` und `_on_qso_complete`

V1 erwähnt die Race-Hypothese aber löst sie nicht. Reihenfolge in
`mw_cycle._on_cycle_decoded` (Z.99-128):

1. Aggregation messages
2. PSK-Logging
3. Histogramm
4. `_refresh_diversity_freq_view` (Diversity)
5. `_run_ap_lite_rescue`
6. **`_run_auto_hunt(messages)`** ← hier picked auto_hunt

Parallel feuert Decoder `cycle_decoded` → mw_cycle._on_cycle_decoded (oben).
Encoder feuert `tx_finished` (nach TX-Slot-Ende). Beide gehen via
QueuedConnection in den GUI-Thread.

`_run_auto_hunt` läuft mit messages aus dem Slot der GERADE dekodiert
wurde. Die `qso_log.add_qso`-Updates passieren im `_on_qso_complete`-
Pfad, der von `tx_finished` über `on_message_sent` → `qso_complete.emit`
verkettet ist.

**Problem:** Bei mehreren konkurrierenden Qt-Signalen ist die Reihenfolge
durch Sender-FIFO gegeben — aber Decoder und Encoder sind verschiedene
Sender. Es ist möglich dass `cycle_decoded` (Decoder) ZUERST verarbeitet
wird, dann erst `tx_finished` (Encoder).

**Wenn das zutrifft:**
- 04:59:00-04:59:13 TX RR73 läuft
- 04:59:15 Slot-Boundary
- 04:59:15 Decoder fertig → cycle_decoded emit
- 04:59:15+ε encoder.tx_finished emit
- GUI-Thread verarbeitet Slot: cycle_decoded zuerst → _run_auto_hunt(msgs)
- → select_next mit messages aus 04:59:15-Slot — HA8RC's neuer CQ
  könnte schon drin sein
- qso_log ist NOCH NICHT aktualisiert (add_qso kommt erst gleich)
- is_worked_on_band("HA8RC", "20M") → **False** → score>0 → Pick
- Erst DANACH läuft tx_finished → on_message_sent → qso_complete →
  qso_log.add_qso

**Das könnte exakt der Bug sein** den Mike sieht — Reihenfolge ist
nicht-deterministisch zwischen verschiedenen Sender-Signalen.

**V3-Fix-Option:** Die neue `_recent_qso`-Schicht ist robust gegen
diesen Race, WEIL `on_qso_complete` zu einem Zeitpunkt gerufen wird wo
TX bereits beendet — also nach `tx_finished`. Aber das ist genau das
gleiche Timing-Problem!

→ **Bessere Wurzel-Lösung:** `_recent_qso` updaten SOFORT in `start_qso`
(also wenn Auto-Hunt eine Station picked und qso_sm.start_qso ruft), NICHT
erst in `on_qso_complete`. Damit ist der Cooldown PRO PICK gesetzt, nicht
pro Erfolg. Das verhindert sowohl Re-Pick während laufendem QSO als auch
nach Erfolg.

**Aber:** Wenn QSO fehlschlägt (Timeout) und ein anderer Versuch nötig
ist — soll der Cooldown trotzdem greifen?
- Pro: ja, weil QSO-Etikette (nicht spammen)
- Contra: Auto-Hunt hat eigenen Cooldown für Fail (`_cooldown` mit
  COOLDOWN_SECS) → bereits abgedeckt
- → Cooldown SETZEN beim Pick. Bei Erfolg/Fail beide Pfade haben dann
  ihren eigenen Schutz (`_recent_qso` aus Pick + `_cooldown` aus Fail).

### F3 — Wo genau Cooldown setzen — Pick-Helper

V1 setzt Cooldown in `on_qso_complete`. V2-F2 sagt: in `start_qso`-
Trigger (vor allem im `_run_auto_hunt` Pfad, NICHT in qso_sm.start_qso
das wäre Mode-übergreifend).

**Saubere Stelle:** unmittelbar BEFORE `self.qso_sm.start_qso(...)` in
`mw_cycle._run_auto_hunt` (Z.508). Aber: dann nicht mehr im auto_hunt-
Modul selbst.

**Alternative (zentraler):** Methode `mark_pick(call)` in `AutoHunt`
hinzufügen, in `mw_cycle._run_auto_hunt` nach erfolgreichem `select_next`-
Return aufrufen. Das hält die Logik in `core/auto_hunt.py` zentral.

**V3-Entscheidung:** `mark_pick(call)` in AutoHunt, gerufen in
`mw_cycle._run_auto_hunt` nach `if not _candidate: return` Z.498. Plus:
auch in `on_qso_complete` belassen als Belt-and-Suspenders (falls
externer Pick-Pfad existiert).

### F4 — Mode-Mischung im Key

V1 Q1 sagte: Key sollte `(call, band, mode)` sein. V2-F1 bestätigt.

Konkret:
- 20m FT8 QSO mit HA8RC → Eintrag `("HA8RC", "20M", "FT8")`
- 20m FT4 QSO mit HA8RC → Eintrag `("HA8RC", "20M", "FT4")`
- Beide unabhängig (5min Cooldown pro Tupel)

Praktisch sinnvoll: Hobby-Funker macht durchaus Mode-Hopping.

### F5 — Test-Suite-Coverage Lücke

V1 listet T1-T6, aber kein Test für **F2-Race** (Pick UND Erfolg liegen
zeitlich auseinander). Test sollte:
- Pick → mark_pick → select_next danach gibt None auch BEVOR
  on_qso_complete läuft
- Erst nach 5+ Min wieder pickbar

**V3-Test T7:** `select_next` returns None unmittelbar nach `mark_pick`
für selbe Station — kein on_qso_complete dazwischen.

### F6 — Bug-Schutz-Source-Level-Test

V1 T6 prüft `_recent_qso` exists. Besser: prüfen dass `select_next`-
Body den Cooldown-Check VOR dem `_cooldown`-Check enthält (Reihenfolge
wichtig sonst hat fehlgeschlagener QSO Vorrang).

**V3-Test T8:** `inspect.getsource(AutoHunt.select_next)` enthält
`_recent_qso` VOR `_cooldown` (regex-Reihenfolge-Check).

### F7 — `_prune_recent_qso` Performance

V1 erwähnt periodisches Cleanup. Bei Hobby-Tool (max ~50 QSOs/Tag) ist
dict-Größe trivial. KISS: Cleanup nur bei `set_band`/`set_mode`/`stop_auto_hunt`,
ODER beim Filter-Check selbst (`if now - last_qso < COOLDOWN: continue;
elif last_qso > 0: del self._recent_qso[base_key]`).

**V3-Entscheidung:** Lazy-Cleanup im Filter-Check (KISS, kein Timer
nötig).

### F8 — `set_band` und `set_mode` jetzt KEIN `clear` mehr

V1 Z.4.2 sagte clear bei Bandwechsel. V2-F1 widerlegt das (Key ist jetzt
band-/mode-spezifisch). V3: `set_band`/`set_mode` NICHT mehr `clear` —
die Einträge sind eh band-/mode-getaggt und werden lazy gepruned.

ABER: was wenn Mike auf Band Y und Auto-Hunt picked X (cooldown gesetzt),
dann wechselt er auf Band X-Cooldown-frei Band Z, dann zurück? Mit dem
Key `(call, band, mode)` ist X auf Y immer noch geblockt — korrekt.

## V2 → V3 Übersicht der Änderungen

| V1 | V3 |
|---|---|
| Key = `base_call` | Key = `(base_call, band, mode)` |
| Set in `on_qso_complete` | Set in `mark_pick` (vor `start_qso`) + redundant in `on_qso_complete` |
| `set_band`/`set_mode` clear | KEIN clear (Key ist getaggt) |
| 6 Tests T1-T6 | 8 Tests T1-T8 (T7 Race, T8 Reihenfolge-Source-Level) |

## V2-Risiko-Analyse

- **Wiederherstellbarkeit:** Komplett zurückrollbar via Backup
- **Tests:** Reine Unit-Tests, kein Hardware-Eingriff
- **Hardware-Pflicht ANT1:** unverändert
- **Workflow-Konsistenz:** keine Architektur-Änderung, nur additive Logik
- **Performance:** Dict-Lookup O(1), keine Sorgen
- **Field-Test-Risiko:** Mike könnte legitimes 2. QSO nicht machen
  können wenn Gegenstation um Wiederholung bittet. KORREKTUR: Mike kann
  bei Bedarf MANUELL klicken — manueller Klick geht durch `_on_station_clicked`,
  nicht durch `select_next` — Cooldown blockt nur Auto-Hunt-Auto-Pick.

## V2-Validierung der Bug-Schutz-Hypothese

Mit Pick-Zeitpunkt-Cooldown:
- 04:59:00 Auto-Hunt picked HA8RC → `mark_pick("HA8RC", "20M", "FT8", T0)`
- 04:59:00-04:59:13 TX RR73
- 04:59:15 Slot-Boundary, cycle_decoded läuft
- _run_auto_hunt → select_next: filter prüft `_recent_qso[("HA8RC", "20M", "FT8")]`
  = T0 → now-T0 < 300s → SKIP
- Auch wenn `qso_log.add_qso` NIE läuft (Hypothese A), blockt Cooldown
- Auch wenn Race-Reihenfolge anders (Hypothese B), blockt Cooldown

✓ Robust gegen beide Wurzel-Hypothesen.

## V2-Verifikation Code-Stellen

Ich habe diese Stellen im Code geprüft:
- `core/auto_hunt.py:187-298` — `select_next` und `_score`
- `core/auto_hunt.py:304-315` — `on_qso_complete` und `on_qso_timeout`
- `ui/mw_cycle.py:487-513` — `_run_auto_hunt`
- `ui/mw_qso.py:440-510` — `_on_qso_complete` und ADIF-Schreiben
- `log/qso_log.py:43-59` — `add_qso` und `is_worked*`
- `core/qso_state.py:475-542` — `on_message_sent` mit qso_complete.emit
- `main_window.py:332-333` — `set_qso_log` und `set_band`

Alle Pfade verifiziert. V3 kann Code-Phase ohne weitere Recherche starten.
