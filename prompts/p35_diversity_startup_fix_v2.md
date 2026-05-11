# P35.DIVERSITY-STARTUP-FIX — V2 (Self-Review nach Mike-Klaerungen)

**Status:** V2 — Self-Review von V1 mit Mike-Antworten Q1-Q3 vom 11.05.2026
**Basis:** prompts/p35_diversity_startup_fix_v1.md
**Workflow:** V2 → R1 (DeepSeek) → V3 → Plan → Code

---

## A. Mike-Klaerungen Q1-Q3 (verbindlich)

**Q1 — App-Start-Status:** Code-Verifikation zeigt `_rx_mode = "normal"`
in `main_window.__init__` Z.235. KEIN Restore aus Settings.
**Mike akzeptiert Normal-Start als Default** — „ist mir egal, ich
entscheide morgens spontan".

→ **Persistence-Implementierung out-of-scope.**

**Q2 — Vor Radio-Connect:** P26 Connect-Modal blockiert die UI komplett
bis Radio-Connect oder User-Klick auf „ohne Radio weiter".

→ **Standard-Pfad sicher** (Mike kann nicht Diversity klicken vor Radio).
→ **Edge-Case „ohne Radio weiter":** Mike kann danach Diversity klicken
ohne radio.ip → muss sauber behandelt werden.

**Q3 — Toggle-Persistenz durch Session:** Dynamic-Toggle AN soll erhalten
bleiben durch die ganze Session — auch bei Mode-Wechseln (Diversity↔DX,
Diversity↔Normal↔Diversity). Nur Mike's manuelles AUS oder App-Quit
deactiviert.

→ **Bug B5 (Diversity-Wechsel deaktiviert Dynamic) muss gefixt werden.**
→ **`settings.dynamic_diversity_enabled` ist die einzige Wahrheit fuer
  „User-Wunsch".** Interner `_dynamic_ctrl._active` folgt dem User-Wunsch
  WENN Diversity-Modus laeuft.

---

## B. Bug-Liste (jetzt 3 Bugs)

| Bug | Status | Fix-Komplexitaet |
|---|---|---|
| **A — Statik-Mess haengt bei radio.ip=None** | Standard-Pfad sicher durch P26-Modal. Edge-Case „ohne Radio weiter" muss noch | Mittel |
| **B — activate() leert Queue/current_ant nicht** | Bug-Wurzel | Klein |
| **B5 — Diversity↔Diversity-Wechsel deaktiviert Dynamic** | Mike-Q3-Klaerung neu | Klein |

---

## C. Loesungs-Strategie (Mike-konform)

### Fix 1 — Bug B: `_apply_dynamic_toggle` resettet Queue + current_ant

**Ort:** `ui/main_window.py` `_apply_dynamic_toggle`

```python
def _apply_dynamic_toggle(self, enabled: bool) -> None:
    if enabled and not self._dynamic_ctrl.is_active():
        # P35 Fix B: Queue + current_ant resetten VOR activate
        # damit alte (A1, "measure")-Eintraege weg sind und neue Slots
        # mit choose() korrekt landen.
        with self._diversity_lock:
            self._diversity_ant_queue = deque()
            self._diversity_current_ant = "A1"
        self._dynamic_ctrl.activate()
        ...  # bisherige Logik
```

**Begruendung:** Saubere Trennung — `DynamicDiversityController` hat
keine Referenz auf MainWindow-Attribute. Reset wird im UI-Layer
(main_window) gemacht, nicht im Core-Controller.

### Fix 2 — Bug B5: Dynamic-Toggle ueberlebt Diversity-Mode-Wechsel

**Ort:** `ui/mw_radio.py` `_disable_diversity` + `_activate_diversity_with_scoring`

**Pattern:** „Settings-Toggle ist die Wahrheit, interner `_active` folgt
WENN Diversity-Modus laeuft."

```python
# In _disable_diversity (Z.1079):
def _disable_diversity(self):
    # P35 Fix B5: Dynamic-Aktiv-Status nur PAUSIEREN, nicht User-Wunsch
    # zuruecksetzen. Bei naechstem _activate_diversity_with_scoring wird
    # Dynamic automatisch wieder aktiviert wenn settings-Toggle AN.
    if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
        self._dynamic_ctrl.deactivate()  # bleibt — Mode→Normal = kein Vergleich
    ...
```

```python
# In _activate_diversity_with_scoring (Z.581):
def _activate_diversity_with_scoring(self, scoring: str):
    self._rx_mode = "diversity"
    ...
    self._check_diversity_preset(band, ft_mode, scoring)
    # P35 Fix B5: Wenn Settings-Toggle AN → Dynamic auto-aktivieren.
    # Mike-Wunsch (Q3): Toggle ueberlebt Mode-Wechsel.
    if (getattr(self.settings, 'dynamic_diversity_enabled', False)
            and not self._dynamic_ctrl.is_active()):
        self._apply_dynamic_toggle(True)
```

**Wichtig:** `_apply_dynamic_toggle(True)` wird hier WIEDER aufgerufen,
das macht den Fix-1-Queue-Reset → saubere Kette.

### Fix 3 — Bug A: Statik-Mess bei radio.ip=None aufschieben

**Ort:** `ui/mw_radio.py` `_enable_diversity` (Z.831) + `_on_radio_connected` (Z.134)

**Variante 2a aus V1:** `_pending_diversity_init`-Flag.

```python
# In _enable_diversity am Anfang nach dem Setup:
def _enable_diversity(self, scoring_mode="normal", *, cached_ratio=None, ...):
    ...
    # Setup-Code bis Z.870 unangetastet
    ...
    # P35 Fix A: Wenn Radio noch nicht da, Init aufschieben
    if not getattr(self.radio, 'ip', None):
        self._pending_diversity_init = scoring_mode
        self._diversity_ctrl._phase = "operate"  # kein Mess-Haengen
        self._diversity_ctrl.ratio = "50:50"
        self._set_cq_locked(False)
        self._set_gain_measure_lock(False)
        print(f"[Diversity] Radio nicht verbunden — Init aufgeschoben "
              f"(scoring={scoring_mode})")
        debug_log("DIV-EN", f"Aufgeschoben scoring={scoring_mode}")
        return
    # ... Rest unveraendert
```

```python
# Am Ende von _on_radio_connected (Z.134-174):
def _on_radio_connected(self):
    ...
    # Bestehender Init-Code bis Z.174
    ...
    # P35 Fix A: aufgeschobene Diversity-Init nachholen
    pending = getattr(self, "_pending_diversity_init", None)
    if pending is not None:
        self._pending_diversity_init = None
        print(f"[Diversity] Radio verbunden — aufgeschobene Init holen "
              f"(scoring={pending})")
        debug_log("DIV-EN", f"Resume scoring={pending}")
        self._enable_diversity(scoring_mode=pending)
```

**Idempotenz:** `_pending_diversity_init = None` BEVOR `_enable_diversity`
aufgerufen wird → Re-Entry-sicher.

---

## D. Akzeptanzkriterien (V2, korrigiert)

1. **AK1 — Bug A behoben (Edge-Case „ohne Radio weiter"):**
   `_enable_diversity` bei `radio.ip=None` → Phase=operate, kein
   Mess-Haengen. Statik-Mess wird erst getriggert wenn Radio kommt
   (via `_pending_diversity_init`).

2. **AK2 — Bug B behoben:** Toggle Dynamic AN → Queue + current_ant
   resetten → record_slot bekommt korrekte (A1, A2) basierend auf
   choose().

3. **AK3 — Bug B5 behoben (Toggle ueberlebt Mode-Wechsel):**
   `settings.dynamic_diversity_enabled = True` → bei jedem
   `_activate_diversity_with_scoring` wird Dynamic auto-aktiviert.
   Bei `_disable_diversity` (Mode→Normal) bleibt Settings-Toggle
   unangetastet, nur `_dynamic_ctrl._active = False`.

4. **AK4 — Standard-Pfad unangetastet:**
   Mike's normaler Flow (Normal-Start → Radio-Connect → Diversity-Klick)
   funktioniert wie heute, KEINE Verzoegerung.

5. **AK5 — Statik-Pipeline unangetastet:** Bestehende Tests bleiben gruen.

6. **AK6 — P34-Pipeline unangetastet:** P34-Tests bleiben gruen.

7. **AK7 — Idempotenz:** `_on_radio_connected` darf mehrfach feuern
   (Reconnect) → `_pending_diversity_init` darf nicht zu Doppel-Init
   fuehren.

8. **AK8 — Hardware-Schutz ANT1=TX:** unveraendert.

9. **AK9 — Settings-RAM-Property: Wahrheit fuer User-Wunsch:**
   `dynamic_diversity_enabled` ist die einzige Quelle fuer „Mike will
   Dynamic". Internal `_active`-Flag folgt nur wenn Diversity-Modus aktiv.

10. **AK10 — Regression-Tests:** Neue Tests fuer jeden der 3 Bugs.

---

## E. Lifecycle-Tabelle (verbindlich)

| Ereignis | `settings.dynamic_diversity_enabled` | `_dynamic_ctrl._active` | `_diversity_ctrl.phase` | Notiz |
|---|---|---|---|---|
| App-Start | False (RAM-Default) | False | "measure" (init) | Default |
| Radio-Connect, _rx_mode=normal | False | False | "measure" | Statik inaktiv (Normal) |
| Klick Diversity vor Radio-Connect (Edge) | False | False | "operate" | **Fix A: kein Haengen** |
| Radio kommt → aufgeschobene Init triggert | False | False | "measure" → "operate" via _evaluate | Statik laeuft jetzt |
| Klick Diversity nach Radio-Connect | False | False | "measure" → "operate" | Standard, Statik laeuft |
| Toggle Dynamic AN | True | True (via activate) | "operate" | **Fix B: Queue reset** |
| Slot in Diversity + Dynamic AN | True | True | "operate" | record_slot mit korrekter Antenne |
| Wechsel Diversity Standard → DX | True | False (transient) → True (auto-reactivate) | "measure" oder Cache-Reuse | **Fix B5: auto-reactivate** |
| Wechsel Diversity → Normal | True | False (deactivate) | n/a | Mode-Coupling, Settings-Toggle bleibt |
| Wechsel Normal → Diversity | True | False → True (auto-reactivate) | "measure" oder Cache-Reuse | **Fix B5: auto-reactivate** |
| Toggle Dynamic AUS | False | False | unveraendert | Mike's explizites AUS |
| App-Quit | (egal, RAM weg) | (egal) | (egal) | Toggle nicht persistiert |

---

## F. R1-Pruefauftraege (V2 fuer DeepSeek-R1)

R1, du bekommst V2 + V1 + 4 Code-Files. **Kritisiere V2-Prompt, nicht
loese.** Konkret 8 Punkte:

1. **R1-Q1 — `_pending_diversity_init`-Flag Race-Condition:**
   `_on_radio_connected` ruft `_enable_diversity` auf. Wenn das Modal
   noch laeuft (P26): Race mit User-Klick? Wenn Reconnect mid-flight:
   Doppel-Init?

2. **R1-Q2 — Idempotenz `_apply_dynamic_toggle` in `_activate_diversity_with_scoring`:**
   `_apply_dynamic_toggle(True)` ruft `_dynamic_ctrl.activate()` was
   wiederum `_diversity_ctrl._phase = "operate"` setzt — auch wenn
   Phase schon operate ist (Cache-Reuse). Side-Effect? Verschluckt
   `_last_measured_at` Update?

3. **R1-Q3 — Settings-Toggle als Wahrheit:**
   Ist `settings.dynamic_diversity_enabled` wirklich die einzige
   Wahrheit? Was wenn das Settings-Dialog parallel zu `_disable_diversity`
   aenderbar ist?

4. **R1-Q4 — Cache-Reuse + Dynamic-Auto-Reactivate:**
   Mike's Flow: Diversity DX mit Gain+Ratio Cache fresh →
   `_check_diversity_preset` → `_try_diversity_cache_reuse` → Cache wird
   genutzt → Ratio=70:30. DANN `_activate_diversity_with_scoring` ruft
   `_apply_dynamic_toggle(True)` → reset auf 50:50. Ist das gewollt?

   → V2-Vorschlag: bei Auto-Reactivate via `_activate_diversity_with_scoring`
   das `_apply_dynamic_toggle(True)` NACH Cache-Reuse durchlaufen lassen.
   Buffer bleibt leer, in ~3 Min uebernimmt Dynamic mit eigenem Ratio.
   ZWISCHENZEITLICH gilt Cache-Ratio (70:30). Akzeptabel?

5. **R1-Q5 — Queue-Reset in `_apply_dynamic_toggle`:**
   `_diversity_lock` ist der MainWindow-Lock fuer Diversity-Slot-Race.
   Auch fuer Queue/current_ant der richtige Lock? Brauchen wir
   `_diversity_in_operate=False`?

6. **R1-Q6 — Test-Coverage V3 (verbindliche Liste):**
   Welche Tests muessen geschrieben werden? Mindestens:
   - Bug A: `_enable_diversity` mit radio.ip=None → Phase=operate
   - Bug A: `_on_radio_connected` mit pending_diversity_init → resume
   - Bug B: `_apply_dynamic_toggle(True)` → Queue gelloescht + current_ant=A1
   - Bug B5: `_activate_diversity_with_scoring` mit Settings-Toggle AN →
     auto-activate
   - Bug B5: `_disable_diversity` mit Settings-Toggle AN → Settings bleibt
   - Idempotenz: 2x `_on_radio_connected` mit pending → nur 1x Init
   - Regression: Mike's Workaround Normal→Diversity funktioniert weiter
   - Regression: P34-Tests bleiben gruen
   - Regression: Statik-Tests bleiben gruen

7. **R1-Q7 — _check_diversity_preset Verhalten bei radio.ip=None:**
   Aktuell returnt es sofort (Z.1186-1187). Mein Fix A laesst
   `_enable_diversity` mit Phase=operate weiterlaufen. Stellt sich das
   `_rx_mode = "diversity"` aber `_check_diversity_preset` returned
   inkonsistent?

8. **R1-Q8 — Backwards-Compatibility:**
   Aenderung von `_disable_diversity` (Dynamic-deactivate bleibt, aber
   Settings-Toggle nicht resetten) — bricht das was anderes? P34-Tests
   `test_diversity_dynamic_integration.py:test_deactivate_keeps_ratio`
   etc. — bestaetigen sie das neue Verhalten?

---

## G. Was V3 enthalten muss

1. Verbindliche Spec basierend auf V2 + R1-Findings (alle 8 Punkte)
2. Implementierungs-Plan: ~4 atomare Commits (Fix1, Fix2, Fix3 + Doku)
3. Test-Liste konkret (~10 Tests mit Namen + Datei)
4. Field-Test-Checkliste fuer Mike (~5 Punkte)
5. 1-Seiten-Zusammenfassung in einfacher Sprache fuer Mike

---

## H. Anhang-Files fuer R1

- `ui/mw_radio.py` (Hauptaenderungen: `_enable_diversity`, `_on_radio_connected`,
  `_activate_diversity_with_scoring`, `_disable_diversity`)
- `ui/mw_cycle.py` (Queue-Pop + slot-handling)
- `ui/main_window.py` partial (`_apply_dynamic_toggle`)
- `core/dynamic_diversity.py` (activate/deactivate)
- `core/diversity.py` (Statik-Pipeline)
- `config/settings.py` (RAM-Property)
- `tests/test_diversity_dynamic_integration.py` (P34-Tests fuer Regression)
