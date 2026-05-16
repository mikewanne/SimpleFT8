## R1 Final Review — P63 SWR-Block per Band-Marker

### 1. Halluzinationen & Code‑Realität

| V1‑Behauptung | Verifikation | Status |
|---------------|--------------|--------|
| `_set_gain_measure_lock(False)` existiert | `mw_radio.py:1405` — ja, setzt `_gain_measure_locked=False` und entriegelt Buttons | ✓ |
| `radio.set_rfpower_direct(10)` | `radio/flexradio.py:909` — ok | ✓ |
| `radio.last_swr` | `radio/flexradio.py:918‑920` — Property | ✓ |
| `control_panel.last_swr()` | **existiert nicht** (V2‑F1 korrekt erkannt) | ✗ |
| `_check_diversity_preset`‑Signatur `(band, mode, scoring)` | `mw_radio.py:1213` — korrekt | ✓ |
| `_start_dx_tuning(scoring_mode=…)` | `mw_radio.py:1329` — korrekt | ✓ |
| `_handle_dx_tuning` (KALIBRIEREN) | `mw_radio.py:1263` — existiert | ✓ |
| `btn_tune.setVisible` / `set_tuner_present` | `control_panel.py` hat noch **keine** Methode — muss hinzugefügt werden | (neu) |

**Ergebnis**: Die von V2 gefundenen Halluzinationen sind korrekt; es gibt keine weiteren falschen API‑Namen. Der benötigte `control_panel.last_swr()`‑Getter wird nicht gebraucht (stattdessen `radio.last_swr`), die ControlPanel‑Änderung beschränkt sich auf das Ein‑/Ausblenden des TUNE‑Buttons.

### 2. Neue Findings (über V2 hinaus)

#### F‑R1‑1 — Kritisches Timing‑Rennen: `_tune_auto_stop_after` muss SWR‑Wert asynchron lesen (Sicherheitsrisiko)
**Was:** Nach `tune_off()` ist der letzte SWR‑Wert im Radio möglicherweise noch der Wert **während** des TUNEs (stark schwankend) oder ein veralteter RX‑Wert. Direktes Lesen von `radio.last_swr` unmittelbar nach dem `tune_off`‑Befehl (im gleichen GUI‑Thread‑Zyklus) führt zu einem falschen Prüfwert.

**Wo:** Geplante Methode `_tune_auto_stop_after` in `ui/mw_tx.py`.

**Wirkung:** Guter SWR kurz nach TUNE‑Ende wird fälschlich als „gut“ erkannt, obwohl die Antenne noch nicht resonant ist; oder umgekehrt. Im Worst‑Case wird ein tatsächlich zu hohes SWR nicht bemerkt und die Sperre fälschlich aufgehoben, mit HW‑Schäden.

**Empfehlung:** Wie in V2‑F2 vorgeschlagen, **nicht** blind 200‑300 ms warten, sondern das Metadaten‑Signal abwarten. FlexRadio sendet Meter‑Updates (`meter_update`) alle 100 ms. Der sicherste Weg:  
1. `tune_off()` rufen  
2. `_tune_in_progress = False` **sofort** zurücksetzen (damit Watchdog für normale TX wieder aktiv ist)  
3. **Nicht** selbst den SWR‑Wert lesen, sondern den bereits existierenden `_on_swr_alarm`‑Slot nutzen: Sobald der nächste Meter‑Update einen SWR ≥ Limit meldet, wird der Watchdog‑Alarm ausgelöst und **dann** kann der Marker gesetzt werden.  
   Falls der SWR nach TUNE‑Ende dauerhaft ≤ Limit bleibt, soll der Marker **nach Ablauf einer kurzen Beruhigungszeit** (z. B. 2 s ohne Alarm) aufgehoben werden.  
   Dieser Ansatz vermeidet die Race‑Condition vollständig und ist hardware‑sicher.

Da dies für Mike eine sicherheitskritische Funktion ist, muss die Entscheidung gut dokumentiert werden. Ein simpler `QTimer.singleShot(2000, …)` der nach 2 Sekunden den letzten SWR‑Wert checkt (weil bis dahin mehrere Meter‑Updates erfolgt sind) ist ein akzeptabler Kompromiss, solange der Watchdog während dieser 2 s auch scharf ist (er wird es, da `_tune_in_progress` auf False gesetzt wurde). **Diese Empfehlung ist die V3‑Entscheidung, bitte im Commit umsetzen.**

#### F‑R1‑2 — Verpasstes Lock‑Release bei SWR‑Alarm während Auto‑TUNE in `_start_dx_tuning`
**Was:** Der aktuelle Post‑TUNE‑Check (nach 3 s) in `mw_radio.py::_start_dx_tuning` (Z. 1366) zeigt bei hohem SWR ein Modal, ruft aber **nicht** `_set_gain_measure_lock(False)` auf. Die Pipeline‑Sperre bleibt aktiv, das UI ist dauerhaft blockiert.

**Wo:** `ui/mw_radio.py` ~ Z. 1366‑1375.

**Wirkung:** Nach einem gescheiterten Auto‑TUNE kann der Benutzer keine Bänder wechseln, keinen manuellen TUNE starten oder andere Aktionen ausführen – der gesamte Control Panel ist blockiert.

**Empfehlung:** Im `if swr > swr_limit`‑Zweig vor dem Modal `self._set_gain_measure_lock(False)` aufrufen. Zusätzlich den Marker setzen, wenn `tuner_present=True` (AC11 aus V2‑F11).

#### F‑R1‑3 — Fehlender Preset‑Reset bei `tuner_present=False` in `_start_dx_tuning`
**Was:** Wenn `tuner_present=False` und wir direkt `_open_dx_tune_dialog()` aufrufen (wie in V2‑F9 vorgeschlagen), wird vorher kein `set_power` auf einen sicheren Wert zurückgesetzt. Im aktuellen Code erfolgt nach Auto‑TUNE `self.radio.set_power(self.settings.get("power_preset", 15))`; im Skip‑Branch fehlt das.

**Wo:** `ui/mw_radio.py` ~ Z. 1377‑1381 (geplanter Skip).

**Wirkung:** Nach dem Aufruf (via KALIBRIEREN‑Button) kann die TX‑Leistung auf einem ungewollten Wert bleiben, falls der Benutzer vorher manuell die Leistung geändert hat.

**Empfehlung:** Im `else`‑Zweig (kein Radio oder `tuner_present=False`) ebenfalls `self.radio.set_power(self.settings.get("power_preset", 15))` aufrufen, **bevor** der Dialog geöffnet wird.

#### F‑R1‑4 — `_on_btn_omni_cq_toggled` und `_on_btn_auto_hunt_toggled` brauchen Pre‑Check gegen geblocktes Band
**Was:** V2‑F8 schlägt vor, die Marker‑Sperre in den Toggle‑Handlern zu prüfen, nicht erst im `on_cycle_start`/`select_next`. Das ist korrekt, aber die Umsetzung muss sicherstellen, dass der Button **nicht** in den „checked“‑Zustand gerät, wenn das Band gesperrt ist.

**Wo:** `ui/main_window.py` Z. 764 (OMNI), Z. 854 (Auto‑Hunt).

**Wirkung:** Ohne Pre‑Check klickt der Benutzer OMNI oder AUTO HUNT an, der Button bleibt aktiv (gechecked), aber es passiert nichts – was zu Verwirrung führt.

**Empfehlung:** Am Anfang der Toggle‑Methoden:
```python
if checked and (band in self._swr_blocked_bands):
    btn.blockSignals(True)
    btn.setChecked(False)
    btn.blockSignals(False)
    self.qso_panel.add_info(f"⚠ OMNI blockiert …")  # passender Text
    return
```
Analog für Auto‑Hunt. Das entspricht KISS und vermeidet stillen Fehlzustand.

#### F‑R1‑5 — `_on_station_clicked` Pre‑Check muss auch bei **pending** click greifen
**Was:** Die geplante Prüfung am Anfang von `_on_station_clicked` verhindert einen direkten Anruf einer Station. Wenn aber der Klick während eines laufenden TX gebuffert wird (`_pending_station_click`), wird der Pre‑Check erst viel später (beim Abarbeiten des Buffers in `_on_tx_finished`) wirksam – zu spät, um den Aufruf zu blockieren.

**Wo:** `ui/mw_qso.py` Z. 143 und `_on_tx_finished` Z. 292.

**Wirkung:** Während eines TX (z. B. CQ) klickt der Benutzer eine Station auf einem gesperrten Band – der Klick wird gebuffert und nach TX‑Ende trotz Sperre ausgeführt, der Alarm erscheint dann erst nach dem tatsächlichen TX‑Start (oder Watchdog) und sorgt für Verwirrung.

**Empfehlung:**
1. In `_on_station_clicked` bei TX‑aktiv den Buffer‑Block **vor** dem Setzen von `_pending_station_click` prüfen:
   ```python
   if self.encoder.is_transmitting:
       band = self.settings.band.upper()
       if band in self._swr_blocked_bands:
           self.statusBar().showMessage(f"TX läuft — {msg.caller} gesperrt (Band {band} SWR)", 3000)
           return  # kein Buffer
       # sonst normal buffern
   ```
2. In `_on_tx_finished`, bevor der gebufferte Klick ausgeführt wird, erneut den Marker prüfen und ggf. verwerfen.

#### F‑R1‑6 — `_tune_auto_stop_token`-Pattern kann bei schnellem Doppelklick Race erzeugen
**Was:** Das Token‑Muster mit `_tune_auto_stop_token` und `QTimer.singleShot` ist grundsätzlich korrekt. Wenn der Benutzer jedoch innerhalb kürzester Zeit `tune_on()` → Timer‑Erzeugung (z. B. 15 s) → **schnelles manuelles Stoppen** per Button (Toggle off) → und dann **sofort wieder** `tune_on()`, kann der alte Timer dennoch das neue Token sehen? Nein, weil der `_tune_auto_stop_token` beim neuen Start auf ein neues `object()` gesetzt wird und der alte Timer noch das alte Token prüft (`if … is not _token: return`). Das ist korrekt. Kein Race.

**Trotzdem Hinweis:** Das Token sollte **vor** dem `tune_on()` gesetzt werden, damit der Watchdog den Bypass erkennt. Im aktuellen Entwurf setzen wir `_tune_in_progress=True` zuerst, das ist in Ordnung.

### 3. Architektur‑Entscheidungen (KISS‑Check)

| Entscheidung | Bewertung |
|--------------|-----------|
| Pre‑Check in Toggle‑Handlern (OMNI, Auto‑Hunt) statt in `on_cycle_start`/`select_next` | **Richtig.** Einfacher, verhindert Button‑Zustands‑Inkonsistenz und braucht keine Fremd‑Injection. |
| Pre‑Check in `_start_dx_tuning` für alle Gain‑Mess‑Pfade | **Richtig.** Deckt `_check_diversity_preset` und `_handle_dx_tuning` mit einer einzigen Zeile ab. |
| Marker (`_swr_blocked_bands`) als einfaches `set`, kein Persist | **OK.** Mike‑Spec eingehalten, kein unnötiger Code. |
| Manuelles TUNE 10 W fest, Dauer 15/30 s konfigurierbar | **Hardware‑sicher und einfach.** |
| `tuner_present`‑Setting und TUNE‑Button‑Hide | **Einfach und klar.** |

**KISS‑Urteil:** Keine Über‑Abstraktion. Der Plan ist fokussiert auf das Problem.

### 4. Hardware‑Sicherheit (ANT1‑Pflicht)

- `_on_swr_alarm` stoppt TX antennen‑neutral (kein Antennenwechsel), ANT1 bleibt → **in Ordnung**.
- `_on_tune_clicked` ruft `radio.set_tx_antenna("ANT1")` → **erfüllt**.
- `_start_dx_tuning` setzt **kein** `set_tx_antenna`; es baut auf der bereits gesetzten ANT1 auf, die beim Verbindungsaufbau gesetzt wurde. Das ist **potentiell unsicher**, wenn z. B. eine vorherige Aktion die Antenne geändert hat.  
  **Empfehlung:** Vor dem TUNE in `_start_dx_tuning` **explizit** `self.radio.set_tx_antenna("ANT1")` ausführen, um sicherzustellen, dass ANT1 für TX verwendet wird. (Kostet keinen messbaren Aufwand, erhöht Sicherheit.)

### 5. Offene Fragen aus V2

- **F‑R1‑1** hat die Post‑Tune‑SWR‑Lesung bereits behandelt → `QTimer.singleShot(2000, check_swr)` ist der praktikable Weg.
- **F‑R1‑2** und **F‑R1‑3** geben Antworten zu Auto‑TUNE‑Marker und Power‑Reset.
- **F11/AC11:** Der Auto‑TUNE‑Post‑Check soll den Marker setzen → **ja**, implementieren (siehe F‑R1‑2).
- **`_tune_in_progress` nur für manuelles TUNE:** Bleibt so. Auto‑TUNE behält Watchdog; das ist sicherer.

### 6. Tests und Abdeckung

Die in V1/V2 geplanten Tests T1‑T15 sind sinnvoll, aber es fehlen:
- **T18:** Test für F‑R1‑1 (`_tune_auto_stop_after` liest SWR nach 2 s, nicht sofort).
- **T19:** Test für Marker‑Set im Auto‑TUNE‑Post‑Check (F‑R1‑2).
- **T20:** Test für Power‑Wiederherstellung bei `tuner_present=False` (F‑R1‑3).

Diese sollten im Test‑Modul ergänzt werden.

### 7. Push‑Empfehlung

**Ja, Push nach Umsetzung der folgenden Punkte freigegeben:**

1. **V3‑Anpassungen** gemäß dieser Review einarbeiten:
   - Post‑TUNE‑SWR‑Check mit 2 s Timer und Watchdog‑Scharfstellung (F‑R1‑1).
   - Lock‑Release nach Auto‑TUNE‑Fehler (F‑R1‑2).
   - Power‑Reset im `tuner_present=False`‑Pfad (F‑R1‑3).
   - Pre‑Check und Button‑Reset in OMNI/Auto‑Hunt‑Toggled (F‑R1‑4).
   - Pending‑Click‑Schutz gegen geblocktes Band (F‑R1‑5).
   - Explizites `set_tx_antenna("ANT1")` vor Auto‑TUNE (Hardware‑Sicherheit).
   - Alle offenen Punkte aus V2 in die V3‑final einfließen lassen.
2. **Tests** T18‑T20 ergänzen (optional für ersten Push, aber dringend empfohlen).
3. **Field‑Tests F1‑F10** nach Push durchführen (Mike‑Spec).

Der Code‑Plan (11 Commits) ist technisch solide und die Architektur bleibt verständlich. Mit den obigen Ergänzungen ist das System robust und hardware‑sicher.
