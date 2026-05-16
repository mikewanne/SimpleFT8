# P63 V2 Self-Review — Code-Realität-Check + Findings

**Basis:** V1 = `prompts/p63_swr_block_marker_v1.md`
**Reviewer:** Claude (Self-Review, vor R1-DeepSeek)
**Datum:** 2026-05-15

---

## Halluzinations-Check (Code-Verifikation)

| V1-Behauptung | Verifikation | Status |
|---|---|---|
| `_set_gain_measure_lock(False)` existiert | `ui/mw_radio.py:1405` `def _set_gain_measure_lock(self, locked: bool)` | ✓ |
| `radio.set_rfpower_direct(10)` | `radio/flexradio.py:909` | ✓ |
| `radio.set_swr_limit` | `radio/flexradio.py:947` (P53) | ✓ |
| `radio.last_swr` Property | `radio/flexradio.py:918-920` | ✓ |
| `control_panel.last_swr()` Helper | **FEHLT** — V1-Halluzination | ✗ |
| `_check_diversity_preset` Signatur | `mw_radio.py:1213` `(self, band, ft_mode, scoring)` | ✓ |
| `_start_dx_tuning` Signatur | `mw_radio.py:1329` `(self, scoring_mode="snr")` | ✓ |
| `_assess_gain` Signatur | `mw_radio.py:1198` `(self, band, ft_mode, scoring) -> str` | ✓ |
| `_set_gain_measure_lock` sperrt btn_tune | `mw_radio.py:1428-1429 if hasattr(...btn_tune): setEnabled(not locked)` | ✓ |
| `AutoHunt.set_mode(mode)` + `mark_pick(call)` | `core/auto_hunt.py:124, 130` (P61) | ✓ |
| `omni_cq.on_cycle_start(cycle_num, is_even)` | `core/omni_cq.py:219` | ✓ |
| `Settings.get(key, default)` API | `config/settings.py:133` | ✓ |
| `Settings.set(key, value)` API | `config/settings.py:136` | ✓ |

## V2-FINDINGS

### F1 (BUG, KRITISCH): `control_panel.last_swr()` halluziniert

V1 §3.3-C ruft `self.control_panel.last_swr()`. Existiert **nicht**.
SWR-Wert kommt direkt vom Radio-Objekt: `self.radio.last_swr`
(Property in `radio/flexradio.py:918-920`, gefüttert von VITA-49-Meter-
Loop in `_meter_worker_thread` Z.1392).

**V3-Fix:** in `_tune_auto_stop_after`:

```python
swr_now = self.radio.last_swr if self.radio.ip else 1.0
```

Konsequenz für V1 §3.5: ControlPanel-Helper `last_swr` + `_last_swr_value`
**komplett streichen**. ControlPanel.update_swr-Methode unverändert lassen.

### F2 (RISIKO, GROSS): SWR-Wert kann stale sein direkt nach tune_off

Nach `tune_off()` wird PTT off — VITA-49-Meter-Loop emittet ggf. einen
letzten SWR-Wert mit Verzögerung (~50-100 ms typisch).
Wenn `_tune_auto_stop_after` *unmittelbar* nach `tune_off` `radio.last_swr`
liest, kann der Wert noch der PRE-TUNE-Wert oder ein Tune-Wert sein.

**V3-Fix:** QTimer.singleShot(300, lambda: self._check_post_tune_swr()).
300 ms ist Daumenregel (FlexRadio VITA-49 Update-Rate ~10-20 Hz =
50-100 ms pro Sample, 3× = sicheres Fenster). KISS-Alternative: `last_swr`
sofort lesen + Fenster verkleinern auf 200 ms.

Plus: `_last_swr` initial 1.0 (Konstruktor) bedeutet bei totem Radio
„SWR ok" — falsch. Defensive: wenn `radio.ip` leer ODER `last_swr`
auf Initial-Wert (1.0) bei unverbundenem Radio → keine Marker-Freigabe.
Aber: bei verbundenem Radio mit guter Antenne ist 1.0 ein realer Wert.
Test ist also „`radio.ip` truthy" als Voraussetzung für Marker-Freigabe.

### F3 (RISIKO, GROSS): Lock-Release im SWR-Watchdog gibt UI komplett frei

V1 §3.3-A: `_set_gain_measure_lock(False)` direkt nach Stop-Block.
Konsequenz: ALLE Buttons wieder klickbar — auch OMNI/Auto-Hunt.
Mike-Spec verlangt aber dass OMNI/Hunt blockiert bleiben, während
TUNE klickbar wird.

**Plan-Inkonsistenz aufgelöst:** Lock-Release + Marker-Set sind orthogonal.
Lock-Release macht UI klickbar → AC erfüllt für TUNE-Button.
Marker `_swr_blocked_bands` blockiert die Auto-Pfade via Pre-Check
(nicht via Disable). Die `add_info`-Zeilen in jedem Pre-Check geben
User klares Feedback dass OMNI/Hunt blockiert ist trotz klickbarem
Button. **AC8 ist die zentrale Schutzschicht**, nicht der Lock.

V1-Plan stimmt also — V2 stellt nur klar dass Mike's „inkonsistent"-
Symptom durch AC1+AC8 zusammen behoben wird. Keine Plan-Änderung.

### F4 (RISIKO): `_handle_dx_tuning` (KALIBRIEREN) Pre-Check fehlt in V1

V1 §3.3-B Liste 2 nennt nur `_check_diversity_preset` und
`_start_dx_tuning` (implizit). Aber `_handle_dx_tuning` (mw_radio.py:1263,
KALIBRIEREN-Button-Pfad) ruft `_start_dx_tuning` direkt (Z.1284). Wenn
User in Settings KALIBRIEREN klickt während Band rot, läuft die Pipeline
ohne Block durch.

**V3-Fix:** Pre-Check auch in `_handle_dx_tuning` Top, ODER in
`_start_dx_tuning` Top (1 Stelle, deckt beide Eintritts-Pfade).

KISS-Entscheidung: **Pre-Check NUR in `_start_dx_tuning` Top** (1 Stelle,
beide Caller `_check_diversity_preset` und `_handle_dx_tuning` profitieren).
Plus `_check_diversity_preset` macht eigenen UI-Hinweis VOR
`_start_dx_tuning`-Aufruf damit User klare Statusbar-Info bekommt
(sonst stiller Skip — schlechte UX).

### F5 (RISIKO): `_on_station_clicked` Pre-Check-Position

V1 §3.3-B Liste 4 schlägt Pre-Check „am Top" vor (vor TX-Check Z.145).
**Korrektur nach Re-Lesen:** Pre-Check muss VOR dem TX-Buffering passieren
(Z.146), sonst wird beim TX-aktiv-Pfad der Klick gebuffert (`_pending_station_click`)
und beim nächsten Slot-Start losgelassen — Marker-Check beim Slot-Start
existiert aber NICHT (Slot-Start kommt aus `mw_cycle._on_cycle_start`,
nicht aus `_on_station_clicked`).

Lösung: Marker-Pre-Check ist FIRST in `_on_station_clicked`:

```python
def _on_station_clicked(self, msg: FT8Message):
    # P63 Pre-Check (vor allen anderen Logik-Pfaden)
    band = self.settings.band.upper()
    if band in self._swr_blocked_bands:
        self.qso_panel.add_info(
            f"⚠ Anruf {msg.caller} blockiert — Band {band} SWR-Sperre."
        )
        return
    # ... bestehender Code ...
```

### F6 (BUG, MITTEL): `_on_cq_clicked` Pre-Check muss Button zurücksetzen

V1 §3.3-B Liste 3 schlägt vor `self.control_panel.set_cq_active(False)`
nach Skip. Korrektur nach Re-Lesen Z.275-280: `_on_cq_clicked` wird
gerufen wenn `btn_cq.isChecked()` ALREADY True (Toggle hat geklappt).
Wir müssen den Button-Zustand also wirklich zurücksetzen damit User
sieht dass CQ nicht gestartet ist. `set_cq_active(False)` macht das
korrekt (setzt Style + isChecked-Property).

V3-Update: **explizit testen** dass `btn_cq.isChecked() == False` nach
Pre-Check-Skip (Test T6).

### F7 (RISIKO): `select_next` Injection-Pattern

V1 §3.3-B Liste 5: `set_blocked_bands_ref(ref)` Setter.
Alternative die ich übersehen habe: AutoHunt kennt `_band` (`set_band`)
und `_mode` (`set_mode`). Konsistent wäre **direkt prüfen via Setter**
ohne `ref`:

KISS-Alternative: `mw_cycle._run_auto_hunt` ruft Pre-Check VOR
`select_next` und gibt `None` zurück bei Sperre. AutoHunt selbst weiß
nichts vom Marker.

```python
# In mw_cycle._run_auto_hunt (Z.487):
def _run_auto_hunt(self, messages):
    band = self.settings.band.upper()
    if band in self._swr_blocked_bands:
        return  # silent skip — no select_next call
    candidate = self._auto_hunt.select_next(messages, ...)
    ...
```

Vorteile: AutoHunt-API unverändert, keine Cross-Modul-Reference,
Encapsulation sauber. Nachteil: zusätzliche Code-Stelle (aber `_run_auto_hunt`
ist eh die einzige Stelle die `select_next` aufruft → keine Streuung).

**V3-Entscheidung:** **Option B (Pre-Check in mw_cycle) wählen**, KISS
schlägt Injection.

### F8 (RISIKO): `omni_cq` Pre-Check ähnliches Pattern

V1 §3.3-B Liste 6: OMNI ähnliche Injection. Mit F7-KISS-Lösung dann:

Mw_cycle._on_cycle_start ruft `_omni_cq.on_cycle_start(...)` Z.545.
Pre-Check davor:

```python
# In mw_cycle._on_cycle_start vor on_cycle_start-Call:
band = self.settings.band.upper()
if band not in self._swr_blocked_bands:
    self._omni_cq.on_cycle_start(cycle_num, is_even)
# else: silent skip, OMNI bleibt "armed" aber sendet nicht
```

Aber: OMNI-State (Toggle-Button = aktiv) bleibt damit irreführend
„grün/aktiv" obwohl nichts passiert. Better UX: bei Marker-Set
einmalig in OMNI eine Pause-Marker setzen → analog zum bestehenden
`_pause_omni_if_active`. Aber das ist Overengineering — beim Stop-Block
in `_on_swr_alarm` wird OMNI bereits via `_omni_cq.stop("swr_block")`
gestoppt (mw_tx.py Z.169). Also: wenn SWR-Alarm OMNI stoppt, ist der
Toggle-Button NICHT mehr aktiv → kein Re-Start-Problem.

Bestätigung: bei `_on_swr_alarm` wird `self._omni_cq.stop("swr_block")`
(Z.169) UND `_auto_hunt.stop_auto_hunt("swr_block")` (Z.171). Marker
verhindert dann NUR den **erneuten User-Klick** auf OMNI/Hunt-Toggle.
Also: Pre-Check für OMNI braucht es nur am `_on_omni_cq_clicked`-
**Toggle-Handler** (analog `_on_cq_clicked`), NICHT im on_cycle_start-
Pfad. Same für `_on_auto_hunt_clicked`.

**V3-Korrektur:** Pre-Check in den **Toggle-Handlern** (Klick-Handler
für OMNI-Button + Auto-Hunt-Button), nicht in `on_cycle_start` /
`select_next`. Das ist einfacher (1 Stelle pro Feature) und korrekt
weil Stop bei SWR-Alarm schon passiert.

V3-Liste der Pre-Checks (revidiert):

1. `_start_dx_tuning` Top (deckt Auto-Pipeline + KALIBRIEREN)
2. `_check_diversity_preset` Top (UI-Hinweis bei manuellem Diversity-Klick)
3. `_on_station_clicked` Top (Hunt)
4. `_on_cq_clicked` Top (Normal-CQ)
5. `_on_omni_cq_clicked` Top (OMNI) — Stelle suchen
6. `_on_auto_hunt_clicked` Top (Auto-Hunt) — Stelle suchen

→ 6 Pfade, KISS.

### F9 (RISIKO): `_start_dx_tuning` Tuner=False Refactor

V1 §3.4 schlägt vor `if not tuner_present: _proceed_to_gain_measure()`.
Code-Realität (`mw_radio.py:1329-1381`):

- Z.1354 `if self.radio.ip:` — Auto-TUNE-Pfad
- Z.1379-1381 `else:` — direkter `_open_dx_tune_dialog()` (kein Radio)

**KISS-Lösung:** denselben Else-Pfad nutzen bei `tuner_present=False`:

```python
if self.radio.ip and self.settings.get("tuner_present", True):
    # ... Auto-TUNE ...
else:
    # Kein Radio ODER Tuner=NEIN → direkt Gain-Mess
    self._open_dx_tune_dialog()
```

Vorteil: keine Helper-Extraktion, 1-Zeilen-Änderung.

### F10 (RISIKO): `_tune_auto_stop_token` Re-Entry-Schutz

V1 §3.3-C nutzt Token-Pattern damit zweiter TUNE-Click vorhandenen
Timer-Callback invalidiert. Korrekt. Aber: User-Stop (Toggle off)
ruft `_tune_auto_stop_after(None)`. Mit `token is None` ist der
Token-Check trivial unbedingt-stop. Plus: was wenn QTimer schon
gefeuert hat (Race)? Dann ist `_tune_active=False` und der Funktion
returnt früh — sicher.

**V3-Klarstellung:** Token-Pattern + `_tune_active`-Check ist robust.
Plus: bei `tuner_present=False` darf `btn_tune` gar nicht klickbar
sein (hidden) → User kann den Pfad nicht triggern.

### F11 (HINWEIS): Auto-TUNE-Pfad (`_start_dx_tuning` Z.1354) hat eigenen Post-SWR-Check

Z.1366-1375 prüft schon SWR>limit nach Auto-TUNE und macht
QMessageBox + `_on_rx_mode_changed("normal")`. Bei **P63**: das ist
auch ein „SWR-Hängen"-Symptom — Mike's 17m-Band hat Auto-TUNE
gemacht, dann SWR>Limit gesehen. Frage: löste das den Watchdog aus
ODER den Post-Check?

Wahrscheinlich BEIDES (Watchdog feuert während TUNE wenn SWR-Threshold
überschritten ist, Post-Check liest `last_swr` aus). Erst Watchdog
(stoppt sofort), dann Post-Check (sieht hohen SWR).

**P63-Frage:** soll der Post-Check (Z.1366-1375) auch einen Marker
setzen wenn er SWR>Limit sieht? Heute setzt er nichts und ruft nur
`_on_rx_mode_changed("normal")` (Diversity → Normal). Sinnvoll wäre:
auch hier Marker setzen damit der Re-Diversity-Versuch geblockt wird.

**V3-Ergänzung (AC11):** Z.1366-1375 setzt zusätzlich
`_swr_blocked_bands.add(band.upper())` wenn `tuner_present=True`.

### F12 (HINWEIS): `_tune_in_progress` ggf. auch für Auto-TUNE setzen

V1 §3.3-D: Watchdog-Bypass via `_tune_in_progress`. Aktuell nur für
manuellen TUNE. Soll der Bypass auch für Auto-TUNE (im Gain-Mess-
Pfad) gelten?

**Argumente dagegen:**
- Auto-TUNE läuft mit `tune_power=10` und 3s — typische Match-Werte
- Watchdog ist SICHERHEIT, gerade bei Auto-TUNE sinnvoll
- Wenn Auto-TUNE SWR>Limit sieht, ist das ein legitimer Stop
- Mike-Spec sagt explizit „manueller TUNE bleibt klickbar" — nicht
  „Auto-TUNE bypassed Watchdog"

**Argumente dafür:**
- Während TUNE läuft, Hilft Watchdog nicht — Antenne wird gerade
  gestimmt, SWR variiert stark
- Würde False-Positive-Stops verhindern (Tuner schwingt sich ein)

**V3-Entscheidung:** **Auto-TUNE BLEIBT mit aktivem Watchdog** (Mike-Spec
strict). `_tune_in_progress` nur für manuelle TUNE-Klicks. Wenn Auto-
TUNE wegen SWR>Limit unterbrochen wird → setzt Marker via F11.

Konsequenz Doku: in `_on_tune_clicked` setzen wir `_tune_in_progress=True`
am START, in `_tune_auto_stop_after` am ENDE auf False. In `_on_swr_alarm`
Top der Bypass-Check. Das ist sauber.

---

## V2-Plan-Updates (für V3)

| § | Original V1 | V2-Korrektur |
|---|---|---|
| 3.3-C | `control_panel.last_swr()` | `radio.last_swr` (F1) |
| 3.5 | ControlPanel-Helper-Section | **komplett streichen** (F1) |
| 3.3-B | 6 Pre-Check-Pfade mit Injection | 6 Pre-Check-Pfade in Toggle-Handlern (F7+F8) |
| 3.3-B | AutoHunt + OMNI Injection | Pre-Check in mw_cycle / Toggle-Handler (KISS, F7+F8) |
| 3.4 | Helper `_proceed_to_gain_measure` | KISS: gleicher Else-Branch nutzen (F9) |
| neu | F11 — Auto-TUNE Post-Check Marker-Set | AC11 |

## V2-Test-Updates

- T5 wird **„AutoHunt-Pre-Check via mw_cycle.\_run_auto_hunt"** (statt `select_next`-Injection)
- T4 (OMNI-Block) wird **„OMNI-Toggle-Handler Pre-Check"** (statt `on_cycle_start`)
- T11 bleibt: `_tune_in_progress` Watchdog-Bypass
- NEU T16: Auto-TUNE-Post-Check (`_start_dx_tuning` Z.1366) setzt Marker bei SWR>Limit
- NEU T17: Statusbar-Verzögerung 200-300ms vor Post-SWR-Check
- T-Count: 15 → **17**

## V2-AC-Updates

- AC8 revidiert: 6 Toggle-Handler-Pre-Checks (statt 6 Pipeline-Pre-Checks)
- NEU **AC11:** Auto-TUNE-Post-Check (`_start_dx_tuning` Z.1366-1375) setzt
  `_swr_blocked_bands.add(band)` wenn `tuner_present=True`

## V2-Konfidenz-Check

| Bereich | Konfidenz |
|---|---|
| Settings-API | HOCH — verifiziert |
| Watchdog-Lock-Release | HOCH — Z.1413 + Z.1428 gelesen |
| Marker-Pre-Checks | MITTEL — 6 Stellen, Implementierung im Detail R1 prüfen |
| Manueller TUNE 10W + Dauer | HOCH — `set_rfpower_direct(10)` + QTimer.singleShot |
| Auto-TUNE Tuner=False-Skip | HOCH — KISS-Else-Branch (F9) |
| Post-Tune SWR-Read (Race) | MITTEL — Timing 200-300ms (F2), R1 soll Wert nennen |
| TUNE-Button-Hide | HOCH — `setVisible` Pattern |

## V2-Open-Points für R1

1. **F2 Post-Tune Delay:** 200ms genug? Oder besser auf `meter_update`-
   Signal warten? R1 soll Trade-off bewerten.
2. **F11 AC11:** soll der bestehende Z.1366-Post-Check auch Marker
   setzen? KISS-Frage: doppelte Marker-Setz-Stellen sauber?
3. **F7 KISS vs. Encapsulation:** AutoHunt-Pre-Check in mw_cycle
   (F7-Lösung) — ist das wirklich besser als Injection? R1-Architektur-
   meinung.
4. **`_on_omni_cq_clicked`-Stelle:** wo genau wird der OMNI-Toggle
   gehandhabt? V3 muss diese Stelle suchen.
5. **`tuner_present=False` Pipeline:** wenn `_start_dx_tuning` ohne
   Auto-TUNE läuft, ist `set_rfpower_direct(tune_power)` (Z.1357) im
   Skip-Branch nicht ausgeführt. Power-State danach unverändert. Korrekt?
   Oder muss explizit `set_power(power_preset)` gesetzt werden vorher?

→ R1 mit allen 8 Touch-Files plus diese Open-Points.
