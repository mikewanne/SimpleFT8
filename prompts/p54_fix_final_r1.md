[deepseek] ~32644 Tokens, 4 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=37902 out=7362 total=45264
## Senior-Review P54-FIX (V3-Spec) — Prüfbericht

**Prüfobjekt:** `ui/mw_tx.py`, `ui/auto_tune_dialog.py`, `ui/main_window.py` (State-Init), `tests/test_p54_fix.py`  
**Tests:** 1395 → 1414 grün (19 neue Tests in test_p54_fix.py, 4 angepasst)  

---

### 1. Prüfpunkte R1-F1 bis R1-F6  
- **R1-F1 (set_power nach _apply_rf_preset):** ✅ **erfüllt.** In `_tune_post_swr_check` wird nach `_apply_rf_preset()` explizit `self.radio.set_power(self._rfpower_current)` aufgerufen.  
- **R1-F2 (Cancel-Race):** ✅ **erfüllt.** Cancel-Flag wird im `AutoTuneDialog._on_cancel_clicked` / `_on_backup_timeout` gesetzt, in `_tune_converge_to_target` geprüft und in `_on_tune_clicked` / `_start_auto_tune_for_band_change` zurückgesetzt.  
- **R1-F3 (State-Var Init):** ✅ **erfüllt.** `_tune_converged_rf` und `_tune_convergence_cancelled` sind in `MainWindow.__init__` deklariert und initialisiert (Typannotationen + Defaults).  
- **R1-F4 (Konvergierter Save):** ✅ **erfüllt.** `rf_preset_store.save` verwendet `_tune_converged_rf`, Fallback hart 10 nur bei `None`.  
- **R1-F5 (Plausibilität):** ✅ **erfüllt.** `if 3 <= rf_to_save <= 50` schützt vor unrealistischen Werten.  
- **R1-F6 (SWR vor Phase B):** ✅ **erfüllt.** `_tune_stop` prüft `swr_after_match` gegen Limit und überspringt Phase B bei SWR > Limit oder User-Cancel.

### 2. Weitere Prüfpunkte  
- **Hardware-Pflicht ANT1:** ✅ Kein `set_tx_antenna`-Aufruf in Phase‑B oder Krücke; ANT1 bleibt aus der Initialisierungsphase erhalten.  
- **Phase‑B‑Timer:** ✅ Convergenz läuft synchron im `_tune_stop`-Aufruf; Auto‑Stop‑Token verhindert Doppelauslösung; Backup‑Timeout im Dialog berücksichtigt die zusätzlichen max. 5 s.  
- **Krücken‑Faktor:** ✅ Formel `anchor_rf × (target_w / anchor_watt) × 0.9` korrekt implementiert und getestet.  
- **Manuelle vs. Auto‑TUNE:** ✅ Beide Pfade nutzen dieselbe Phase‑B‑Logik und `_tune_post_swr_check` (Save, Plausibilität). Unterscheidung nur für Signal‑Routing (QMessageBox vs. `auto_tune_done`).

### 3. Gefundene Mängel  

#### **ROT‑F1: Race‑Condition bei manuellem Cancel während Phase‑B**  
- **Pfad:** `_on_tune_clicked(off)` → `_tune_stop(None)` kann parallel zu einem bereits laufenden `_tune_stop` (ausgelöst durch Auto‑Stop‑Timer) auf den gleichen Stack gelangen, weil `_tune_converge_to_target` über `_wait_with_event_loop` einen lokalen Event‑Loop öffnet und dadurch GUI‑Events (Button‑Klick) verarbeitet werden können.  
- **Wurzel:** `_tune_stop` besitzt **keine Re‑Entrant‑Sperre**. Ein zweiter Aufruf mit `token=None` überspringt die Token‑Prüfung und ruft `tune_off` sowie Frequenz‑/Power‑Reset auf, während der erste Aufruf noch in der Schleife steckt und später ebenfalls `tune_off` und Zustands‑Cleanup ausführt.  
- **Auswirkung:** Doppelte `tune_off`/`set_frequency`/`set_power`-Befehle können das Radio in einen inkonsistenten Zustand versetzen (z. B. VFO‑Rücksetzen während Phase‑B noch läuft, undefiniertes Verhalten bei parallelen Radio‑Calls).  

#### **GELB: FWDPWR‑Sample‑Verlust für Logging in `_tune_post_swr_check`**  
- **Pfad:** `_tune_converge_to_target` leert `_fwdpwr_samples` in jeder Iteration. Nach erfolgreicher Convergenz sind die Samples daher meist leer, sodass `avg_fwdpwr` in `_tune_post_swr_check` 0.0 ist. Dieses `avg_fwdpwr` wird nur für Log‑Statements und die `auto_tune_done`‑Signalnutzlast verwendet – **kein funktionaler Fehler**, aber irreführende Anzeige für den User. Kein ROT, da keine Speicher‑ oder Hardware‑Sicherheits‑Verletzung.

### 4. Test‑Status  
Alle 19 neuen Tests (`test_p54_fix.py`) bestehen. Sie decken Convergenz, Cancel, Plausibilität, Krücke, Init korrekt ab. Ein **fehlender Test** für das manuelle Cancel‑Race ist zu empfehlen, kann aber nicht automatisiert werden (Event‑Loop‑Race).

---

### Push‑Status: **BLOCKIERT**  
Begründung: ROT‑F1 ist eine Race‑Condition, die bei manuellem TUNE‑Cancel zu inkonsistenten Hardware‑Zuständen führen kann. **Fix‑Vorschlag:**  
- `_tune_stop` mit einem Flag `_tune_stop_active` schützen: bei `True` sofort return.  
- Alternativ `_tune_stop(None)` nur das `_tune_convergence_cancelled`‑Flag setzen und die eigentliche Stop‑Logik über den laufenden Event‑Loop‑Aufruf beenden lassen; dazu müsste der Auto‑Stop‑Timer den Cancel erkennen und den laufenden `_tune_converge_to_target`-Durchlauf abbrechen.  

**Klare Empfehlung:** Re‑Entrant‑Sperre implementieren, danach Freigabe.
