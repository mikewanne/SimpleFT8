[deepseek] ~68073 Tokens, 6 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=75027 out=4438 total=79465
## Review P53 SWR-Live-Watchdog (v0.97.29)

### 1. `radio/base_radio.py` – Default‑Pass
`set_swr_limit()` als **No‑Op** definiert. Radios ohne SWR‑Schutz implementieren es nicht – **korrekt**.

### 2. `radio/flexradio.py` – Setter mit Clamp
`set_swr_limit()` clampt den Wert auf `[1.5, 10.0]` und speichert ihn in `_swr_limit`. Der alte (ungültige) Wert aus Settings kann die Endstufe nicht mehr gefährden – **korrekt**.

### 3. `ui/main_window.py` – Initialisierung
In `_init_diversity_state()` (aus `__init__` aufgerufen) werden `_swr_spike_count=0` und `_swr_first_alarm_t=0.0` initialisiert – **korrekt**.

### 4. `ui/mw_radio.py` – set_swr_limit nach Connect
In `_on_radio_connected()` folgen aufeinander:
```python
self.radio.swr_alarm.connect(self._on_swr_alarm)
self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
```
Der Wert wird **nach** der Signal‑Verbindung ans Radio propagiert – **korrekt**.

### 5. `ui/mw_tx.py` – Neuer `_on_swr_alarm`
- **Pre‑Check** mit `self.encoder.is_transmitting` → fängt Alarme vor oder nach TX ab.
- **Spike‑Counter (500 ms)**: erst ab dem zweiten Alarm innerhalb von 0.5 s wird gestoppt. Löst PTT‑on‑Glitches und Einzel‑Peaks aus.
- **Stop‑Block** (nur wenn nötig):
  - `encoder.abort()` + `ptt_off()`
  - CQ/QSO stoppen (`stop_cq()`, `cancel()`, `set_cq_active(False)`)
  - OMNI‑TX und Auto‑Hunt beenden
  - **KEIN** `set_tx_antenna` – ANT1 bleibt unangetastet.
- **Info vor Modal**: `qso_panel.add_info()` wird **vor** dem blockierenden `QMessageBox.warning` aufgerufen, damit der Eintrag sofort im GUI sichtbar ist.
- **KISS** und **ANT1‑Pflicht** eingehalten – **korrekt**.

### 6. `ui/settings_dialog.py` – Propagierung ans Radio
In `_save_and_close()`:
```python
self.settings.set("swr_limit", self.swr_limit.value())
if parent.radio.ip:
    parent.radio.set_swr_limit(self.swr_limit.value())
```
Neuer SWR‑Grenzwert wird **direkt** an das verbundene Radio übergeben – **korrekt**.

### Race‑Conditions & Thread‑Safety
- `swr_alarm` wird aus dem UDP‑Lesethread emittiert, läuft aber über Qt‑QueuedConnection sicher im GUI‑Thread.
- `_swr_spike_count`, `_swr_first_alarm_t` und der gesamte Stop‑Block werden **ausschließlich im GUI‑Thread** verwendet – keine Races.
- Stop‑Block ruft keine asynchronen Operationen auf, die verschränkte Zustände verursachen könnten.

### Tests
Referenz: Tests 1245–1258 grün (Live‑Code wird nicht verändert, Neuerungen sind von Tests abgedeckt).

### Push‑Empfehlung
✅ **Alle Änderungen sind korrekt, KISS und Race‑Condition‑Frei, ANT1‑Schutz ist durchgängig gewährleistet.**
**PUSH empfohlen – FINAL‑R1 freigeben.**
