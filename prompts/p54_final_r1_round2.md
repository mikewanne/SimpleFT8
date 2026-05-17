[deepseek] ~9887 Tokens, 2 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=12087 out=2182 total=14269
Der State-Sync-Bug ist behoben, neue Probleme entstehen nicht.

**Ursache:** Nach erfolgreichem TUNE (SWR gut, FWDPWR plausibel) speichert `_tune_post_swr_check` einen RFPreset-Stützpunkt (P54b) und ruft `_apply_rf_preset()` auf, um `_rfpower_current` zu aktualisieren. Dabei fehlte ein nachfolgender `radio.set_power()`-Aufruf, sodass der interne Zustand (z. B. 10 %) von der Hardware (noch auf dem alten `power_preset`, z. B. 15 %) abwich. In der nächsten TX-Regelung (`_auto_adjust_tx_level`) führte diese Divergenz zu falscher rfpower-Anpassung und möglichen Power-Spikes.

**Fix (Final-R1 ROT):** In `_tune_post_swr_check` wird nach dem Save und `_apply_rf_preset()` explizit `if self.radio.ip: self.radio.set_power(self._rfpower_current)` aufgerufen, sodass die Hardware mit dem aktuellen Preset-Wert synchronisiert wird.

**Verifikation:**
- Der Code in `ui/mw_tx.py` enthält den Fix exakt an der richtigen Stelle, nur innerhalb des `if swr_now <= swr_limit`‑ und `2.0 < avg_fwdpwr < 80.0`-Blocks.
- Die Tests `test_t24` und `test_t24b` stellen sicher, dass `set_power` nur nach erfolgreichem Save und nicht bei unplausiblem FWDPWR aufgerufen wird.
- Es gibt keine Race‑Conditions: Der Post‑Check-Timer läuft mit Token‑Schutz, der `set_power`-Aufruf ist idempotent und erfolgt nur bei vorhandener Radio‑Verbindung.
- Andere Stellen (`_on_power_changed`) hatten diesen Sync bereits; der Fix eliminiert die letzte Inkonsistenz.
- Die Reihenfolge `_tune_stop` → `set_power(power_preset)` → `_tune_post_swr_check` → `set_power(_rfpower_current)` ist unbedenklich, da der zweite Aufruf den ersten gezielt mit dem aktualisierten, konvergenzoptimierten Wert überschreibt – genau das gewünschte Verhalten.

Damit ist die State-Synchronisation vollständig, der Bug beseitigt, und es gibt keine Hinweise auf neu eingeführte Nebenwirkungen.
