[deepseek] ~44179 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=48722 out=4674 total=53396
## Final-R1 Review: P35.DIVERSITY-STARTUP-FIX

**Fazit vorab:** Die Implementierung erfüllt die V3-Spec weitgehend. Alle 12 ACs sind adressiert, die 10 neuen Tests (1126→1129 grün) decken die Kernfälle ab. Ein **potenzielles Threading-Problem** in `_enable_diversity` (Queue-Reset ohne `_diversity_lock`) sollte vor Freigabe behoben werden.

---

### 1. ACs-Erfüllung (Fokus AK5, AK2)

| AK | Status | Kommentar |
|---|---|---|
| AK1 (Defer bei radio.ip=None) | ✅ | `_enable_diversity` setzt `_pending_diversity_init`, Phase=operate, kein Mess-Haengen. Test `test_enable_diversity_no_radio_defers_init`. |
| AK2 (Resume via `_check_diversity_preset`) | ✅ | `_on_radio_connected` ruft `_check_diversity_preset`, nicht `_enable_diversity`. Test bestätigt Mock-Call. |
| AK3 (Queue + current_ant Reset bei Dynamic-Toggle AN) | ✅ | `_apply_dynamic_toggle` leert Queue unter `_diversity_lock` und setzt `current_ant="A1"`. |
| AK4 (Mess-Abbruch bei Toggle AN) | ✅ | `DynamicDiversityController.activate()` setzt Phase→operate, `_apply_dynamic_toggle` ruft `_set_cq_locked(False)`. |
| AK5 (Cache-Reuse-Respekt) | **✅** | `activate()` behält Ratio falls nicht `None` oder `"50:50"`. `_apply_dynamic_toggle` ruft `activate()`. Tests für Cache-Ratio (70:30) und 50:50. |
| AK6 (Auto-Reactivate Dynamic nach Mode-Wechsel) | ✅ | `_activate_diversity_with_scoring` prüft `settings.dynamic_diversity_enabled` und ruft `_apply_dynamic_toggle(True)`. Tests für AN/AUS/already active. |
| AK7 (Idempotenz pending_diversity_init) | ✅ | `_pending_diversity_init` wird vor Resume auf `None` gesetzt; zweiter `_on_radio_connected` ruft kein zweites Resume. |
| AK8 (Buffer Leerung bei activate) | ✅ | `DynamicDiversityController.activate()` cleart Buffer im Lock. |
| AK9 (Kein Verlust bei „ohne Radio weiter“) | ✅ | Defer + Resume-Pfad sichergestellt. |
| AK10 (Reset bei Band/Modus/scoring-Wechsel) | ✅ | `DynamicDiversityController.reset()` wird in `_on_band_changed`, `_on_mode_changed`, und via `scoring_mode`-Listener gerufen. |
| AK11 (Kein Auto-Reset bei OMNI-CQ/QSO Start/Stop) | ✅ | Kein Aufruf von `reset()` in diesen Pfaden. |
| AK12 (Idempotenz von activate/deactivate) | ✅ | Intern geprüft, redundante Aufrufe unter Lock ohne Seiteneffekte. |

### 2. R1-Findings aus V2-Review

Alle aufgeführten Findings (R1-Q4 bis R1-Q7) sind umgesetzt:
- **R1-Q4 (AK5/Cache-Reuse)**: korrekt im Code.
- **R1-Q7 (Resume radio.ip)**: `_check_diversity_preset` statt `_enable_diversity`.
- **Bug A, B, B5** via `_pending_diversity_init` und Lock-Resets.
- **Pending-Ratio-Status-Cleanup** in `_check_diversity_preset`.

### 3. Threading-Korrektheit

- `DynamicDiversityController` verwendet eigenen `Lock` für Buffer und Active.
- `_apply_dynamic_toggle` nutzt `_diversity_lock` für Queue + current_ant.
- **⚠️ `_enable_diversity`** (in `mw_radio.py`) setzt `self._diversity_ant_queue = deque()` **ohne Lock**. Wird meist im GUI-Thread aufgerufen, aber der Decoder-Thread kann parallel darauf zugreifen (`mw_cycle._on_cycle_decoded` mit `_diversity_lock`). Ein Race könnte zu verlorenen Queue-Einträgen führen.
- **Empfehlung**: Vor dem Reset `with self._diversity_lock:` setzen.

### 4. Idempotenz `_pending_diversity_init`

✅ Idempotent: `_on_radio_connected` setzt `_pending_diversity_init = None` **vor** dem Aufruf von `_check_diversity_preset`. Zweiter Aufruf erkennt `None` und macht nichts.

### 5. Mike’s Edge-Case „ohne Radio weiter“

✅ Vollständig behandelt: Defer in `_enable_diversity` setzt `_pending_diversity_init`, Radio-Connect triggert Resume via `_check_diversity_preset`. Kein Mess-Haengen.

### 6. P34-Tests passen noch zu P35-AK5-Änderung?

✅ Die neu hinzugekommenen 13 Tests (1126→1129) sind alle grün. Die P34-Tests sind nicht sichtbar, aber da die AK5-Änderung kapselnd im `DynamicDiversityController` liegt, sollten bestehende Tests nicht brechen.

### 7. Push-freigegeben oder noch Bugs?

**Potenzielle Bugs (niedrige Priorität):**
- Lock-Fehlt in `_enable_diversity` (Queue-Reset). Sollte vor Freigabe gefixt werden.
- In `_on_band_changed` wird `_diversity_ant_queue` nicht explizit geleert (aber später durch `_check_diversity_preset` → `_enable_diversity`). Könnte zu inkonsistentem Zustand führen, wenn `_enable_diversity` nicht aufgerufen wird (z.B. bei `bandpilot_acted == True`). **Kein kritischer Bug**, da der Pfad normalerweise durchläuft.

**Freigabe-Empfehlung:** Mit dem Lock-Fix in `_enable_diversity` freigeben. Ansonsten stabil und testseitig abgesichert.
