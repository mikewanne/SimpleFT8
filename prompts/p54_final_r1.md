[deepseek] ~52931 Tokens, 5 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=60299 out=10048 total=70347
## Senior-Review P54

**Push-Status:** BLOCKIERT  
**Kritikalität:** KP 3 (aktiver Regelungs-Bug, manifestiert sich bei manuellem TUNE sofort)

### ✅ R1‑F1 / R1‑F2 / R1‑F3 – korrekt umgesetzt
- **R1‑F1 (watt=10):** `_tune_post_swr_check` ruft *immer* `rf_preset_store.save(…, 10, 10)` auf, unabhängig vom gemessenen FWDPWR‑Mittelwert. Tests T8/T8b bestätigen das.
- **R1‑F2 (Signal statt QMessageBox):** Im Auto‑Tune‑Pfad wird ausschließlich `auto_tune_done` emittiert; `QMessageBox` erscheint nur im manuellen Pfad. T14/T15 decken das ab.
- **R1‑F3 (Diversity‑Resume):** `_check_diversity_preset` wird nur aufgerufen, wenn `is_auto=False`. T16 belegt dies.

### ✅ V2‑F1 / V2‑F3 / Hardware‑ANT1 / Cleanup
- **V2‑F1 (Re‑Apply):** Nach erfolgreichem Save wird `_apply_rf_preset()` sofort aufgerufen, damit der gespeicherte Stützpunkt live wirkt (T17).
- **V2‑F3 (Re‑Entry):** `_on_band_changed` verweigert den Wechsel, solange `_tune_active=True` – schützt auch vor parallelem Auto‑Tune.
- **HW‑Pflicht ANT1:** `set_tx_antenna("ANT1")` steht im Helper vor `tune_on()`. Quelltext‑Test T21 bestätigt die Reihenfolge.
- **Cleanup‑Pfade:** Cancel, Backup‑Timeout und Verbindungsverlust setzen `_auto_tune_running`, `_tune_in_progress` und ggf. das Dialog‑Signal zuverlässig zurück.

### ✅ Bandwechsel‑Flow nach Auto‑Tune
`_on_band_changed` durchläuft nach Rückkehr aus dem blockierenden Dialog alle restlichen Schritte (Frequenz, Preset, Bandpilot, Diversity‑Check). Doppel‑Aufrufe sind durch die bereits vorhandenen State‑Variablen (`_tune_active`, Token) ausgeschlossen.

---

### 🔴 ROT‑Finding – Inkonsistenter RF‑Power‑State nach manuellem TUNE

**Betroffene Stelle:** `_tune_post_swr_check`, Aufruf von `_apply_rf_preset()` *ohne* nachfolgendes `radio.set_power()`.  
**Pfad:** manueller TUNE (User klickt TUNE‑Button), nicht der Auto‑Tune‑Pfad.

**Ablauf:**
1. Manueller TUNE läuft mit 10 W. `_tune_stop` setzt das Radio nach `tune_off` zurück auf `power_preset` (z. B. 15 W), **ohne** `_rfpower_current` anzupassen.
2. 2 s später feuert `_tune_post_swr_check` und führt bei plausiblen FWDPWR‑Werten aus:
   ```python
   self._apply_rf_preset()   # lädt RFPreset für 10 W → _rfpower_current = 10
   ```
3. Das Radio bleibt auf 15 W, `_rfpower_current` wird aber 10. Die nächste TX‑Regelung (`_auto_adjust_tx_level`) sieht daher einen viel zu niedrigen `_rfpower_current` und wird die Leistung hochregeln, obwohl das Radio schon 15 W liefert – es entsteht kurzzeitig eine Übersteuerung.

**Warum das ein Problem ist:**  
Die Auto‑TX‑Regelung stützt sich auf `_rfpower_current` als Abbild des tatsächlichen Radio‑Werts. Eine Divergenz führt zu mindestens einem Zyklus falscher Stellbefehle und kann bei empfindlichen Endstufen zu einem ungewollten Leistungsspike führen. Der Bug ist deterministisch bei jedem manuellen TUNE nach dem Einbau von P54.

**Gegenmaßnahme:**  
- Entweder `_apply_rf_preset()` nur im `is_auto`‑Pfad aufrufen, oder  
- Unmittelbar nach `_apply_rf_preset()` ein `self.radio.set_power(self._rfpower_current)` anfügen.  
Damit wäre der interne State wieder synchron mit der Hardware.

**Warum wurde es nicht bemerkt?**  
Test T12 prüft nur, dass `save` aufgerufen wird, nicht den `_rfpower_current`‑Zustand. Ein zusätzlicher Test, der den Radio‑Aufruf verifiziert, fehlt.

---

### 🟠 ORANGE – Mehrfacher `_apply_rf_preset`-Aufruf im Auto‑Tune‑Pfad
Im Auto‑Pfad wird `_apply_rf_preset()` einmal in `_tune_post_swr_check` und später erneut in `_on_band_changed` aufgerufen. Das ist funktional harmlos (idempotent), erzeugt aber unnötige Log‑Ausgaben und eine leichte Code‑Unklarheit. Kein Fehler, aber für Wartbarkeit sollte eine der beiden Stellen entfallen.

---

**Fazit:**  
Das ROT‑Finding erzwingt eine Nachbesserung, bevor die Version released werden kann. Alle anderen Prüfpunkte sind bestanden. Mit der Korrektur des State‑Bugs wird P54 freigegeben.
