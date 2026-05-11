# P35.DIVERSITY-STARTUP-FIX — V3 (Final-Spec, Compact-fest)

**Status:** V3 — Verbindliche Spec nach V1 + V2 + R1-Findings
**Datum:** 2026-05-11
**Workflow:** V3 → Mike-Freigabe → Plan-Mode → Code → Tests → Final-R1 → Field-Test

---

## 0. Einstieg fuer neue KI (Compact-Recovery)

Falls Compact unterbricht: lies **NUR diese V3-Datei**. V1 und V2 sind
Vorgaenger-Archiv. Alle Mike-Klaerungen + R1-Findings sind hier
eingearbeitet — keine offenen Fragen mehr.

### 0.1 Worum geht's

3 Bugs nach P34.DIVERSITY-DYNAMIC Feld-Test 11.05.:

- **Bug A:** Statik-Mess haengt bei `radio.ip=None` (Edge-Case nach
  „ohne Radio weiter"-Button im P26-Modal)
- **Bug B:** Mein `_apply_dynamic_toggle` leert `_diversity_ant_queue`
  + `_diversity_current_ant` nicht → alte (A1, "measure")-Eintraege
  blockieren P34-Hook
- **Bug B5:** Diversity↔Diversity-Wechsel deaktiviert Dynamic — Mike-
  Wunsch (Q3): Toggle ueberlebt Session, nur App-Quit/manuelles AUS

### 0.2 Mike-Klaerungen (verbindlich)

- **Q1:** App-Start in Normal-Modus OK (kein Persistence-Bedarf)
- **Q2:** P26-Modal blockiert Klicks bis Radio-Connect → Standard-Pfad
  sicher, Edge-Case „ohne Radio weiter" muss noch
- **Q3:** Dynamic-Toggle bleibt AN durch ganze Session, auch ueber
  Mode-Wechsel. Nur App-Quit + manuelles AUS deaktiviert.

---

## 1. Akzeptanzkriterien (12, R1-adressiert)

1. **AK1 — Bug A:** `_enable_diversity` bei `radio.ip=None` → Phase=operate
   sofort, kein Mess-Haengen. Statik-Mess wird via `_pending_diversity_init`
   aufgeschoben.

2. **AK2 — Bug A R1-Q7:** Resume in `_on_radio_connected` ruft die volle
   Init-Kaskade auf (`_check_diversity_preset` statt `_enable_diversity`
   direkt) — damit Gain geladen wird + Cache-Reuse moeglich.

3. **AK3 — Bug B:** `_apply_dynamic_toggle(True)` resettet
   `_diversity_ant_queue=deque()` + `_diversity_current_ant="A1"` BEVOR
   `activate()` laeuft. Unter `_diversity_lock`.

4. **AK4 — Bug B5 (Mike Q3):** `_activate_diversity_with_scoring` ruft
   am Ende `_apply_dynamic_toggle(True)` wenn `settings.dynamic_diversity_
   enabled==True`. Damit ueberlebt Toggle Mode-Wechsel.

5. **AK5 — R1-Q4 Cache-Reuse-Respekt (KRITISCH):**
   `DynamicDiversityController.activate()` UND `_apply_dynamic_toggle`
   duerfen `_diversity_ctrl.ratio` NICHT auf "50:50" zuruecksetzen wenn
   das aktuelle Ratio von Cache-Reuse stammt (`!= "50:50"`).
   - Bei Toggle-AN ohne Cache-Reuse → 50:50-Reset (wie P34)
   - Bei Auto-Reactivate nach Cache-Reuse → bestehendes Ratio behalten
   - Buffer immer leer (frischer Start), aber das angezeigte Ratio
     bleibt bis Buffer voll → dann Dynamic-Auswertung

6. **AK6 — Settings als Wahrheit:** `settings.dynamic_diversity_enabled`
   ist die einzige Quelle fuer User-Wunsch. `_dynamic_ctrl._active`
   folgt nur wenn Diversity-Modus aktiv. `_disable_diversity` setzt
   `_active=False` ABER laesst Settings-Toggle unangetastet.

7. **AK7 — Idempotenz `_pending_diversity_init`:**
   `_on_radio_connected` setzt Flag auf None BEVOR Resume-Aufruf →
   Re-Entry-sicher. Mehrfach-Connect fuehrt nicht zu Doppel-Init.

8. **AK8 — Standard-Pfad unangetastet:** Mike's normaler Flow
   (Normal-Start → Radio-Connect → Diversity-Klick) funktioniert
   bit-identisch wie heute, keine Verzoegerung.

9. **AK9 — Statik-Pipeline unangetastet:** Bestehende Tests gruen.

10. **AK10 — P34-Pipeline unangetastet (mit semantischer Aenderung
    AK5):** P34-Tests muessen angepasst werden weil `activate()` jetzt
    Ratio nur bei 50:50 zuruecksetzt. Bewusst.

11. **AK11 — Hardware-Schutz ANT1=TX:** unveraendert.

12. **AK12 — `_diversity_in_operate` Verhalten:** wird in
    `_apply_dynamic_toggle` NICHT zurueckgesetzt (R1-Q5 OK).
    Bei Bandwechsel/Mode-Wechsel reset via `_enable_diversity` wie heute.

---

## 2. Code-Aenderungen (mit Datei:Zeile)

### 2.1 `ui/main_window.py` `_apply_dynamic_toggle` — Bug B Fix

```python
def _apply_dynamic_toggle(self, enabled: bool) -> None:
    if enabled and not self._dynamic_ctrl.is_active():
        # P35-Fix B: Queue + current_ant resetten BEVOR activate
        from collections import deque
        with self._diversity_lock:
            self._diversity_ant_queue = deque()
            self._diversity_current_ant = "A1"
        # P35-AK5: ratio bleibt erhalten wenn Cache-Reuse-Wert vorhanden;
        # activate() prueft das intern.
        self._dynamic_ctrl.activate()
        # ... bisherige GUI-Lock-Aufhebung
        try:
            self._set_cq_locked(False)
            self._set_gain_measure_lock(False)
        except Exception:
            pass
        # Panel-Update mit aktuellem Ratio (kann 50:50 ODER Cache-Wert sein)
        self.control_panel.update_diversity_ratio(
            self._diversity_ctrl.ratio,
            self._diversity_ctrl.phase,
            operate_seconds_remaining=self._diversity_ctrl.seconds_until_remeasure,
            scoring_mode=self._diversity_ctrl.scoring_mode,
            is_dynamic=True,
        )
        print("[Dynamic] Toggle AN — Buffer leer, Statik pausiert")
    elif not enabled and self._dynamic_ctrl.is_active():
        self._dynamic_ctrl.deactivate()
        # ... bisheriges Panel-Update
```

### 2.2 `core/dynamic_diversity.py` `activate()` — AK5 Cache-Respekt

```python
def activate(self) -> None:
    """Toggle AUS→AN: Buffer leer, ggf. Statik-Mess abbrechen.
    
    P35-AK5: Ratio wird NUR auf 50:50 zurueckgesetzt wenn aktuell auch
    50:50 ODER None. Ein Cache-Reuse-Ratio (70:30/30:70) bleibt erhalten —
    Dynamic startet damit, fuellt Buffer leer, und ueberschreibt erst
    nach 5+5 Slots wenn evaluate eine andere Entscheidung trifft.
    """
    with self._lock:
        self._active = True
        self._buffer["A1"].clear()
        self._buffer["A2"].clear()
        self._diversity_ctrl.dynamic_active = True
        # AK4: Statik-Mess abbrechen wenn laufend
        if self._diversity_ctrl.phase == "measure":
            self._diversity_ctrl._phase = "operate"
            self._diversity_ctrl._last_measured_at = time.time()
            logger.info("[Dynamic] Statik-Mess-Phase abgebrochen")
            debug_log("DYNAMIC", "Statik-Mess-Phase abgebrochen")
        # AK5: Ratio NUR resetten wenn nicht von Cache (50:50 bedeutet
        # "kein Cache" ODER "Cache war 50:50" — beides OK)
        current_ratio = self._diversity_ctrl.ratio
        if current_ratio == "50:50" or current_ratio is None:
            self._diversity_ctrl.ratio = "50:50"
            self._diversity_ctrl.dominant = None
            debug_log("DYNAMIC", "activate -> Buffer leer, Ratio 50:50")
        else:
            # Cache-Ratio bleibt bis Dynamic-Buffer voll
            debug_log("DYNAMIC",
                      f"activate -> Buffer leer, Ratio behalten ({current_ratio})")
    logger.info("[Dynamic] Aktiviert (Buffer leer)")
```

### 2.3 `ui/mw_radio.py` `_enable_diversity` — Bug A Fix

```python
def _enable_diversity(self, scoring_mode: str = "normal", *,
                      cached_ratio: str | None = None,
                      cached_dominant: str | None = None,
                      cached_age_seconds: float = 0.0):
    """..."""
    self._diversity_in_operate = False
    self.rx_panel.table.setRowCount(0)
    ...  # Setup unangetastet bis Z.870
    
    # P35-Fix A: Wenn Radio nicht da, Init aufschieben.
    if not getattr(self.radio, 'ip', None):
        self._pending_diversity_init = scoring_mode
        # Phase=operate damit Mess nicht haengt
        self._diversity_ctrl._phase = "operate"
        self._diversity_ctrl.ratio = "50:50"
        self._diversity_ctrl.dominant = None
        self._set_cq_locked(False)
        self._set_gain_measure_lock(False)
        print(f"[Diversity] Radio nicht verbunden — Init aufgeschoben "
              f"(scoring={scoring_mode})")
        from core.debug_log import debug_log as _dlog
        _dlog("DIV-EN", f"Aufgeschoben scoring={scoring_mode}")
        return
    
    # Dynamic-Pfad (bestehender P34-Code)
    dynamic_active = (getattr(self, "_dynamic_ctrl", None) is not None
                      and self._dynamic_ctrl.is_active())
    if dynamic_active:
        ...
    elif cached_ratio is not None:
        ...
    else:
        ...
```

### 2.4 `ui/mw_radio.py` `_on_radio_connected` — Bug A Resume (R1-Q7)

```python
def _on_radio_connected(self):
    """..."""
    self._reconnect_attempts = 0
    self.control_panel.set_connection_status("connected")
    ...  # Bestehender Init-Code bis Z.174
    
    # P35-Fix A R1-Q7: Aufgeschobene Diversity-Init nachholen.
    # WICHTIG: NICHT _enable_diversity direkt aufrufen — sondern
    # _check_diversity_preset, damit Gain-Cache-Pfad korrekt durchlaufen
    # wird (Cache-Reuse, DXTuneDialog bei Gain stale/missing, etc.).
    pending_scoring = getattr(self, "_pending_diversity_init", None)
    if pending_scoring is not None:
        self._pending_diversity_init = None  # AK7: VOR Aufruf resetten
        print(f"[Diversity] Radio verbunden — aufgeschobene Init "
              f"(scoring={pending_scoring})")
        from core.debug_log import debug_log as _dlog
        _dlog("DIV-EN", f"Resume scoring={pending_scoring}")
        band = self.settings.band
        ft_mode = self.settings.mode
        self._check_diversity_preset(band, ft_mode, pending_scoring)
```

### 2.5 `ui/mw_radio.py` `_activate_diversity_with_scoring` — Bug B5

```python
def _activate_diversity_with_scoring(self, scoring: str):
    """..."""
    self._rx_mode = "diversity"
    self._diversity_stations = {}
    label = "DIVERSITY DX" if scoring == "dx" else "DIVERSITY"
    self.control_panel.btn_diversity.setText(label)
    
    band = self.settings.band
    ft_mode = self.settings.mode
    
    # P1.CACHE-SIMPLE: Cache-Dispatch
    self._check_diversity_preset(band, ft_mode, scoring)
    
    # P35-Fix B5 (Mike Q3): Settings-Toggle ueberlebt Mode-Wechsel.
    # Wenn der User Dynamic-Toggle AN hatte, jetzt Diversity aktiviert
    # ist, dann Dynamic auto-reactivieren. activate() respektiert
    # Cache-Ratio (AK5).
    if (getattr(self.settings, 'dynamic_diversity_enabled', False)
            and not self._dynamic_ctrl.is_active()):
        print("[Dynamic] Auto-Reactivate nach Mode-Wechsel "
              "(Settings-Toggle AN)")
        self._apply_dynamic_toggle(True)
```

### 2.6 `ui/mw_radio.py` `_disable_diversity` — Bug B5 (keine Aenderung an Settings)

```python
def _disable_diversity(self):
    """..."""
    # P35-Fix B5: Dynamic-Aktiv-Status pausieren, ABER Settings-Toggle
    # UNVERAENDERT. Bei naechstem _activate_diversity_with_scoring wird
    # Dynamic automatisch wieder aktiviert (siehe Bug B5 Fix).
    if getattr(self, "_dynamic_ctrl", None) and self._dynamic_ctrl.is_active():
        self._dynamic_ctrl.deactivate()
    # ... Rest unveraendert (Mode→Normal Pfad)
```

→ **Code-Aenderung effektiv: KEINE.** `_disable_diversity` ruft schon
`deactivate()` ohne Settings anzufassen. Doku-Kommentar klarstellen.

### 2.7 `ui/main_window.py` `__init__` — `_pending_diversity_init` Init

```python
def _init_diversity_state(self):
    ...
    self._diversity_ctrl = DiversityController()
    from core.dynamic_diversity import DynamicDiversityController
    self._dynamic_ctrl = DynamicDiversityController(self._diversity_ctrl)
    self._pending_diversity_init = None  # P35-AK7: Flag fuer Aufschub
    ...
```

---

## 3. Lifecycle-Tabelle (verbindlich)

| Ereignis | `settings.dynamic_diversity_enabled` | `_dynamic_ctrl._active` | `_diversity_ctrl.phase` | `_diversity_ctrl.ratio` | Pending-Flag |
|---|---|---|---|---|---|
| App-Start | False | False | "measure" | "50:50" | None |
| Radio-Connect, _rx_mode=normal | False | False | "measure" | "50:50" | None |
| User klickt Diversity vor Radio („ohne Radio weiter") | False | False | "operate" (Fix A!) | "50:50" | "normal" |
| Radio kommt → `_pending_diversity_init` Resume | False | False | "operate" (oder measure) | Cache oder 50:50 | None |
| Standard: Radio da → Diversity-Klick | False | False | "measure" → "operate" | Cache oder 50:50 (nach Mess) | None |
| Toggle Dynamic AN (Standard, Ratio=50:50) | True | True | "operate" | "50:50" → bleibt 50:50 | None |
| Toggle Dynamic AN (Cache-Reuse, Ratio=70:30) | True | True | "operate" | "70:30" → **bleibt 70:30** (AK5!) | None |
| Slot in Diversity+Dynamic AN | True | True | "operate" | wechselt nach Buffer-voll | None |
| Wechsel Diversity Standard → DX | True | False (deactivate transient) → True (auto-reactivate) | je nach Cache | je nach Cache | None |
| Wechsel Diversity → Normal | True | False (deactivate) | n/a | bleibt (egal Mode) | None |
| Wechsel Normal → Diversity | True | False → True (auto-reactivate) | je nach Cache | je nach Cache | None |
| Toggle Dynamic AUS (manuell) | False | False | unveraendert | bleibt | None |
| App-Quit | (RAM weg) | (egal) | (egal) | (egal) | (egal) |

---

## 4. Test-Liste (~12 Tests in 2 Files)

### 4.1 `tests/test_p35_startup_bugs.py` NEU

| # | Name | Was wird getestet |
|---|---|---|
| 1 | `test_enable_diversity_no_radio_defers_init` | Bug A: `_enable_diversity` bei radio.ip=None → Phase=operate, `_pending_diversity_init` gesetzt |
| 2 | `test_radio_connected_resumes_pending_init` | Bug A R1-Q7: `_on_radio_connected` mit pending → `_check_diversity_preset` aufgerufen |
| 3 | `test_pending_init_idempotent` | AK7: 2x `_on_radio_connected` mit pending → nur 1x Resume |
| 4 | `test_apply_dynamic_toggle_resets_queue` | Bug B: Queue + current_ant resettet |
| 5 | `test_apply_dynamic_toggle_preserves_cache_ratio` | AK5: Ratio=70:30 bleibt nach Toggle AN |
| 6 | `test_apply_dynamic_toggle_resets_5050_ratio` | AK5: Ratio=50:50 bleibt 50:50 (normal Toggle-Pfad) |
| 7 | `test_activate_diversity_with_settings_toggle_on` | Bug B5: Settings-Toggle AN → auto-reactivate |
| 8 | `test_activate_diversity_with_settings_toggle_off` | Bug B5: Settings-Toggle AUS → kein Auto-Reactivate |
| 9 | `test_disable_diversity_keeps_settings_toggle` | Bug B5: `_disable_diversity` laesst Settings-Toggle unangetastet |
| 10 | `test_diversity_mode_switch_preserves_dynamic` | Bug B5 End-to-End: Standard→DX→Standard mit Toggle AN → Dynamic durchgehend |

### 4.2 P34-Test-Anpassung (`tests/test_diversity_dynamic.py`)

Test `test_activate_resets_ratio` (Test 3 in V3 §3.1) muss angepasst werden:
- Wenn `static.ratio == "70:30"` UND activate() → Ratio BLEIBT 70:30 (war 50:50 in P34, ist 70:30 in P35)
- Neuer Test `test_activate_resets_5050_ratio` falls 50:50-Pfad separat geprueft

→ **Test-Bilanz: 15 → 16 P34-Tests, +10 P35-Tests = 1116 → ~1127 gruen**

---

## 5. Implementierungs-Plan (5 atomare Commits)

| # | Commit | Dateien | Tests | Risiko |
|---|---|---|---|---|
| **C1** | `core/dynamic_diversity.py` activate() AK5 + Tests | `core/dynamic_diversity.py`, `tests/test_diversity_dynamic.py` (1 Test angepasst, 1 neu) | 2 | Niedrig (Verhaltens-Aenderung, aber lokal) |
| **C2** | `ui/main_window.py` `_apply_dynamic_toggle` Queue-Reset + Tests | `ui/main_window.py`, `tests/test_p35_startup_bugs.py` (4 Tests) | 4 | Niedrig |
| **C3** | `ui/mw_radio.py` Bug A Fix (`_enable_diversity` defer + `_on_radio_connected` resume) | `ui/mw_radio.py`, `tests/test_p35_startup_bugs.py` (3 Tests) | 3 | Mittel (Init-Pfad-Eingriff) |
| **C4** | `ui/mw_radio.py` Bug B5 Fix (`_activate_diversity_with_scoring` auto-reactivate) | `ui/mw_radio.py`, `tests/test_p35_startup_bugs.py` (3 Tests) | 3 | Mittel (UX-Aenderung) |
| **C5** | APP_VERSION-Bump + HISTORY/HANDOFF/CLAUDE/TODO + Memory | `main.py`, `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md`, `TODO.md`, Memory | — | Doku-only |

**Total: ~80 LOC Code + ~200 LOC Tests, ~2-3h.**

---

## 6. Field-Test-Checkliste (Mike, F1-F8)

Nach Code-fertig + App-Neustart:

| # | Test | Erwartung |
|---|---|---|
| **F1** | App-Start, Toggle AUS, normaler Flow (Diversity-Klick nach Radio-Connect) | Wie heute. Statik misst, alles sauber. |
| **F2** | App-Start, „ohne Radio weiter" im P26-Modal klicken, dann Diversity-Klick | Diversity-Aktivierung wird aufgeschoben. Nach Radio-Connect: Init laeuft automatisch nach. KEIN Mess-Haengen mit ANT1-only. |
| **F3** | App-Start, Toggle Dynamic AN sofort, dann Diversity-Klick | Standard-Flow + Auto-Reactivate. Antennen-Panel blau „● DYNAMISCH (live)". Buffer fuellt sich Slot-fuer-Slot mit korrekten A1+A2. |
| **F4** | Toggle AN mitten in Cache-Reuse-Diversity (z.B. Mike's Standard mit Cache 70:30) | Antennen-Panel zeigt 70:30 in blau (Cache-Wert behalten!). Dynamic-Buffer fuellt sich. Nach ~3 Min ggf. Wechsel zu eigenem Ratio. |
| **F5** | Bug-Reproduktion-Test: alter Workaround Normal→Diversity → funktioniert noch? | Ja, soll wie heute laufen. |
| **F6** | Toggle AN, Wechsel Diversity → Normal → zurueck zu Diversity | Toggle bleibt AN (Settings), Dynamic aktiviert sich automatisch im neuen Diversity-Modus. |
| **F7** | Toggle AN, Wechsel Standard → DX → Standard | Toggle bleibt AN, Dynamic ueberlebt jeden Wechsel. |
| **F8** | Toggle AN, 5 Min beobachten, dann manuell Toggle AUS | Dynamic deaktiviert, Ratio bleibt beim letzten Dynamic-Wert. Settings-Toggle = False. |

**Bestanden wenn:** F1-F4 sauber, F5 keine Regression, F6-F8 wie spezifiziert.

---

## 7. 1-Seiten-Zusammenfassung fuer Mike (einfache Sprache)

### Was wir fixen

Drei Bugs aus dem 11.05.-Field-Test:

**Bug 1 (Start im Diversity-Modus):** Wenn die App startet und die App-
Bildschirm-Sperre fuer Radio-Connect mit „ohne Radio weiter" weggeklickt
wird, koennte Diversity-Mess haengen. Fix: Wenn Radio nicht da ist, wird
die Mess-Initialisierung verschoben bis Radio kommt — dann laeuft sie
automatisch nach.

**Bug 2 (Toggle aktivieren mit altem Mess-Status):** Wenn Mike den
Dynamic-Toggle anschaltet waehrend die Mess-Phase haengt, bleiben alte
Antennen-Eintraege in einer internen Warteschlange. Mein Code sieht
diese alten Eintraege und verarbeitet sie als A1. Fix: Warteschlange wird
beim Toggle-AN sauber geleert.

**Bug 3 (Toggle verliert bei Mode-Wechsel):** Mike's Toggle ging beim
Wechsel Diversity→Normal oder Diversity Standard→DX immer wieder aus.
Fix: Solange Mike den Toggle nicht selbst ausschaltet oder die App nicht
beendet, bleibt er AN — auch wenn Mike Modi wechselt. Bei jedem Mode-
Wechsel reactiviert sich Dynamic automatisch.

**Bonus (Cache-Reuse-Respekt):** Wenn die App ein gut funktionierendes
Antennen-Verhaeltnis aus dem Cache laed (z.B. 70:30), wird Dynamic dieses
Verhaeltnis NICHT mehr sofort auf 50:50 zuruecksetzen. Stattdessen
arbeitet Dynamic mit 70:30 weiter, sammelt 3 Min Daten, und korrigiert
nur wenn es einen besseren Wert findet.

### Was sich nicht aendert

- TX bleibt immer ANT1 (Hardware-Schutz).
- Toggle wird NICHT persistiert ueber App-Neustart (bei Neustart immer AUS).
- Antennen-Panel-Blau-Anzeige bleibt.
- Statik-Modus (Toggle AUS) verhaelt sich exakt wie heute.

### Was du testest (Feldtest F1-F8)

8 Punkte (siehe Sektion 6). Wichtigste:

1. F1: Normaler Flow (Toggle AUS) → keine Aenderung
2. F2: „ohne Radio weiter"-Pfad → Diversity startet sauber wenn Radio kommt
3. F4: Cache 70:30 + Toggle AN → bleibt 70:30 (kein 50:50-Reset!)
4. F6+F7: Toggle ueberlebt Mode-Wechsel
5. F8: Manuelles AUS funktioniert

---

## 8. Audit-Trail: R1-Findings → V3-Adressierung

| R1-Finding | V3-Adressierung |
|---|---|
| **Q1 — Race `_pending_diversity_init`** | AK7: Flag VOR Resume-Aufruf auf None setzen (idempotent) |
| **Q2 — Idempotenz `_apply_dynamic_toggle` in Auto-Reactivate** | `_apply_dynamic_toggle` prueft `is_active()` und macht no-op wenn schon aktiv |
| **Q3 — Settings als Wahrheit** | AK6 explizit. Lifecycle-Tabelle zeigt alle Zustaende. |
| **Q4 — Cache-Reuse + Dynamic-Konflikt (KRITISCH)** | **AK5 NEU** — `activate()` respektiert bestehendes Ratio != 50:50 |
| **Q5 — `_diversity_in_operate`** | AK12: nicht resetten in `_apply_dynamic_toggle` |
| **Q6 — Test-Coverage** | 10 P35-Tests + 1 P34-Anpassung in Section 4 |
| **Q7 — `_check_diversity_preset` bei Resume (KRITISCH)** | AK2 NEU — Resume ruft `_check_diversity_preset` statt `_enable_diversity` direkt |
| **Q8 — Backwards-Compat `_disable_diversity`** | 2.6 explizit: keine Aenderung, nur Doku |

---

## 9. Naechster Schritt

Mike-Freigabe → Plan-Mode → C1-C5 atomar → Tests → Final-R1 → Field-Test.

**Falls Mike zur V3 Korrektur hat:** zurueck zu V2-Anpassung + erneuter
R1-Lauf bevor Plan-Mode.
