# V3 — OMNI-TX Aktivierung + Auto-Hunt Mode-Coupling (SimpleFT8 v0.78)

**Workflow-Schritt:** 3 (V3 — Mike-freigabe-fertig)
**Vorausgegangen:** V1 → Self-Review (17 Findings) → V2 → DeepSeek-R1-Review
(10 Findings) → Schritt 2.5 Code-Verifikation (9/10 angenommen, 0
Halluzinationen, 2 echte Bugs in V2 entdeckt).
**Status:** vollstaendiger Prompt — bereit fuer Mike-Freigabe + Implementation.

---

## Projektphilosophie (Kontext)

- SimpleFT8 ist Hobby-Funker-Tool fuer **einen einzelnen Operator** (Mike DA1MHH).
- KEIN Contest-Tool, KEIN Multi-Op, KEINE Pileup-Jagd.
- KISS strikt: drei einfache Zeilen schlagen eine schlaue Abstraktion.
- **Hardware-Pflicht:** ANT1 = TX immer. ANT2 = nur RX. Bei TX auf ANT2
  (Regenrinne) Hardware-Schaden moeglich. `radio.set_tx_antenna("ANT1")`
  ist **bereits zentral** in `Encoder.transmit()` und allen `tune_on()`-
  Pfaden v0.75 abgesichert. **OMNI-Pfad bekommt KEINEN separaten Check.**
- Visuell: dunkles Theme, Neon-Akzente. Keine 90er-Funktionalitaets-UI.

---

## Begriffsklarstellung — Drei verschiedene „Modi" im Code

| Begriff | Was | Handler | Werte |
|---|---|---|---|
| **FT-Modus** | Protokoll-Wechsel | `mw_radio.py:195` `_on_mode_changed(mode)` | `"FT8"` / `"FT4"` / `"FT2"` |
| **RX-Modus** | Empfangs-Strategie | `mw_radio.py:356` `_on_rx_mode_changed(mode)` | `"normal"` / `"diversity"` |
| **Diversity-Submodus** | Scoring innerhalb Diversity | `_diversity_ctrl.scoring_mode` | `"normal"` / `"dx"` |

→ Im OMNI-Kontext sind beide Mode-Wechsel relevant (FT- UND RX-Modus
stoppen OMNI). Diversity-Submodus-Wechsel laesst OMNI laufen.

---

## 1. Ziel

OMNI-TX-Feature **scharfschalten**. Heute zu ~70% verkabelt
(`core/omni_tx.py` komplett, Hooks in `mw_qso.py:223-242` `should_tx`,
`mw_cycle.py:494` `advance`, `main_window.py:230-232` Singleton-Init,
`main_window.py:546-548` Easter-Egg-Disable, `main_window.py:760-762`
Statusbar-Ω-Anzeige) — fehlend sind 8 Punkte plus Auto-Hunt-Mode-Coupling.

Mike's Plan v3.2 (vollstaendige Spec in `docs/OMNI_TX_DESIGN.md`):
- 5-Slot-Pattern `[TX TX RX RX RX]` mit Even/Odd-Rotation pro Block
- Block-Wechsel nach **80** Zyklen (aktueller Code-Default 40, wird angepasst)
- Mode-gekoppelte UI: `btn_omni_cq` + `btn_auto_hunt` sichtbar nur in RX-Modus „diversity"
- Direkt-Toggle ohne Aktivierungsdialog
- Easter-Egg (Klick Versionsnummer) bleibt als manueller Override fuer Tests

Plus parallel: Auto-Hunt von Easter-Egg-only auf Diversity-only umstellen
(gleiche UI-Logik wie OMNI), damit beide Power-User-Features konsistent.

### Direkt-Toggle-Begruendung (Memory-Inhalt zitiert)

> **Disclaimer-Ton sachlich statt drohend** — kein „Hardware-Schaden
> moeglich"-Drohton in Aktivierungs-Dialogen. Funker wissen das schon.
> Direkt-Toggle ist genauso sicher wie ein Dialog (User klickt bewusst),
> aber freundlicher.
> *(Quelle: Memory `feedback_disclaimer_no_threat.md`, 2026-04-29)*

---

## 2. Akzeptanzkriterien

### A — UI-Verhalten (Mode-Coupling + Easter-Egg-Override)

| # | Kriterium |
|---|---|
| A1 | RX-Modus **„normal"**: nur `btn_cq` sichtbar. `btn_omni_cq` + `btn_auto_hunt` versteckt (`setHidden(True)`). |
| A2 | RX-Modus **„diversity"** (egal ob Submodus Standard oder DX): `btn_omni_cq` + `btn_auto_hunt` sichtbar, `btn_cq` versteckt. |
| A3 | **Easter-Egg-Override** (Klick auf Versionsnummer): solange aktiv, sind in „normal" zusaetzlich `btn_omni_cq` + `btn_auto_hunt` sichtbar (3-Button-Layout). In „diversity" hat Easter-Egg keine zusaetzliche Wirkung. RX-Modus-Wechsel setzt Easter-Egg-Override automatisch zurueck. |
| A4 | `btn_omni_cq` und `btn_auto_hunt` sind **mutually exclusive**: Klick auf inaktiven stoppt aktuell laufenden via neuem Reason `"superseded"` und startet sich selbst. Reason-Granularitaet hilft bei spaeterer Log-Analyse zu unterscheiden zwischen User-direkt-Stop (`manual_halt`) und Auto-Stop-durch-anderes-Feature. |
| A5 | OMNI-Status sichtbar in Statusbar als „Ω Even=N Odd=M" (Code bestehend, `main_window.py:760-762` lesen `_omni_tx.cq_even_count`/`cq_odd_count`). Verschwindet wenn OMNI inaktiv. |

### B — Aktivierung + Stop-Bedingungen

| # | Kriterium |
|---|---|
| B1 | Klick `btn_omni_cq` → OMNI aktiv (kein Aktivierungsdialog, Direkt-Toggle). |
| B2 | Erneuter Klick → `stop_omni_tx("manual_halt")`. |
| B3 | Bandwechsel waehrend OMNI aktiv → `stop_omni_tx("band_change")` in `mw_radio.py:259` `_on_band_changed` (analog Auto-Hunt `:297-299`). |
| B4 | RX-Modus-Wechsel diversity→normal waehrend OMNI aktiv → `stop_omni_tx("rx_mode_change")` in `mw_radio.py:_on_rx_mode_changed` (NEUER Hook, aktuell nicht verkabelt). |
| B5 | FT-Modus-Wechsel (FT8↔FT4↔FT2) waehrend OMNI aktiv → `stop_omni_tx("ft_mode_change")` in `mw_radio.py:195` `_on_mode_changed` (analog existierendes `stop_auto_hunt("mode_change")` Z.198 — wird parallel umbenannt zu `"ft_mode_change"`). |
| B6 | Diversity-Submodus-Wechsel (Standard ↔ DX) waehrend OMNI → **OMNI laeuft weiter** (beide sind Diversity, OMNI-Logik unabhaengig vom Scoring). |
| B7 | Totmannschalter (Presence-Timeout, default 15 min) → `stop_omni_tx("totmann_expired")` in `main_window.py:836-849` `_on_presence_tick` (Anschluss an existing Auto-Hunt-Hook `:914-915`). |
| B8 | **Totmann stoppt OMNI immer** — auch bei laufendem QSO. Das laufende QSO wird **separat** durch `presence_can_tx()` (`main_window.py:933-945`) bis zum Abschluss erlaubt. → Erkenntnis aus R1-Review: V2 hatte Verhalten falsch beschrieben („Totmann greift bei QSO nicht") — Code zeigt Auto-Hunt wird unconditional gestoppt. OMNI bekommt das gleiche Verhalten, was konsistent + simpel ist. |
| B9 | **Kein Hard-Cap-Timer** (im Gegensatz zu Auto-Hunt 10-min-Stop). OMNI laeuft bis manueller oder System-Stop. Begruendung: passiver Modus, keine Bot-Tarn-Anforderung. |

### C — OMNI-Logik (5-Slot-Pattern)

| # | Kriterium |
|---|---|
| C1 | Default `block_cycles = 80` in `core/omni_tx.py:54` (aktuell 40 → wird umgestellt). Plan v3.2 ist Wahrheits-Quelle. |
| C2 | Block 1: TX-Pattern Pos 0=Even, Pos 1=Odd, Pos 2-4=RX. |
| C3 | Block 2: TX-Pattern Pos 0=Odd, Pos 1=Even, Pos 2-4=RX. |
| C4 | Nach `block_cycles` Zyklen: Block-Wechsel **nur an Pos 0** (Pattern-Grenze, `_pending_switch`-Logik bestehend). |
| C5 | `on_qso_started()` setzt `_cycle_count = 0`, Block + `_pending_switch` bleiben unveraendert. **Methode existiert bereits** in `core/omni_tx.py:121-131` — wird nicht neu gebaut, nur Test ergaenzt. |
| C6 | **`stop_omni_tx(reason)` setzt `_pending_switch = False`** (sonst Bug: nach Re-`enable()` springt Block sofort). |
| C7 | `OMNI_TX_ENABLED` Konstante in `core/omni_tx.py:35` wird **entfernt** (bisheriges Gate, jetzt obsolet — Singleton-Init in `main_window.py:230-232` reicht). |

### D — Auto-Hunt Mode-Coupling (Zusatz-Aufgabe v0.78)

| # | Kriterium |
|---|---|
| D1 | `btn_auto_hunt` sichtbar nur in RX-Modus „diversity" (analog OMNI A2). |
| D2 | Easter-Egg-Override macht `btn_auto_hunt` zusaetzlich sichtbar in „normal" (analog OMNI A3). |
| D3 | RX-Modus-Wechsel diversity→normal stoppt Auto-Hunt mit `stop_auto_hunt("rx_mode_change")` in `mw_radio.py:_on_rx_mode_changed` (**NEUER Hook**, parallel zu B4 OMNI). |
| D4 | Bestehende `mw_radio.py:198` `stop_auto_hunt("mode_change")`-Aufruf wird zu `stop_auto_hunt("ft_mode_change")` umbenannt (Konsistenz mit B5). Ein bestehender Test-Case in `test_auto_hunt_extended.py` muss entsprechend angepasst werden. |

### E — Hardware-Pflicht ANT1

| # | Kriterium |
|---|---|
| E1 | OMNI-TX bekommt **keinen separaten** ANT1-Check. Encoder-Schicht (v0.75 zentral) greift. |
| E2 | Bestehender Test `tests/test_encoder.py::test_encoder_transmit_sets_ant1_before_ptt_on` deckt die Pflicht ab. Keine neuen ANT1-Tests in v0.78. |

### F — Tests + Build

| # | Kriterium |
|---|---|
| F1 | Test-Suite waechst von 472 auf ~490-494 gruen (+18-22 neue Tests, plus 1 angepasster Auto-Hunt-Test fuer Reason-Rename). |
| F2 | App startet ohne Fehler, OMNI-Toggle funktioniert manuell in beiden Diversity-Submodi. |
| F3 | `APP_VERSION = "0.78"` in `main.py`. Tag-Setzung **erst nach Mike-Freigabe** (separater Schritt). |

### G — Mutually-exclusive Reason-Tabelle (zur Klarheit)

| Trigger | Reason | Verwendung |
|---|---|---|
| User klickt aktiven Button erneut | `manual_halt` | klar User-direkt |
| User klickt anderen mode-button (Mutually exclusive) | `superseded` | Auto-Stop durch anderes Feature |
| User wechselt Band | `band_change` | Hardware-Kontext geaendert |
| User wechselt FT-Modus (FT8↔FT4↔FT2) | `ft_mode_change` | Cycle-Zeiten geaendert |
| User wechselt RX-Modus (Diversity↔Normal) | `rx_mode_change` | Feature out-of-scope im neuen Modus |
| Presence-Timeout (Totmannschalter) | `totmann_expired` | gesetzliche Pflicht DE |
| Easter-Egg-Toggle (Hide-Buttons) | `easter_egg_off` | bestehend, wird beibehalten |

---

## 3. Betroffene Module/Dateien

### Code-Aenderungen

| # | Datei | Zeilen | Was |
|---|---|---|---|
| 1 | `core/omni_tx.py` | ~50 | OmniTX → `QObject` (analog `core/auto_hunt.py:67ff`). Neues Signal `omni_stopped = Signal(str)`. Neue Methode `stop_omni_tx(reason: str)` zentralisiert: `active=False`, `_slot_index=0`, `_cycle_count=0`, `_pending_switch=False` (Bug-Fix C6), Signal-Emit. `enable()`/`disable()` als Thin-Wrapper bleiben (Test-Kompatibilitaet). `block_cycles` Default 40 → **80**. `OMNI_TX_ENABLED`-Konstante entfernt (C7). |
| 2 | `ui/main_window.py` | ~80 | Connect `_omni_tx.omni_stopped → _on_omni_stopped(reason)` Slot (analog `:253` Auto-Hunt). Neuer Handler `_on_btn_omni_cq_toggled` (analog Auto-Hunt `:565`). Mode-Coupling-Helper `_update_button_visibility(rx_mode)` der `btn_cq`/`btn_omni_cq`/`btn_auto_hunt` mode-abhaengig zeigt/versteckt + Easter-Egg-Override. Easter-Egg-Toggle (`:530-557`) ruft den Helper. Totmann-Hook (`:914-915`) ergaenzt um `stop_omni_tx("totmann_expired")` (parallel zu Auto-Hunt-Stop, ohne QSO-Filter). Mutually-exclusive: `_on_btn_omni_cq_toggled` und `_on_btn_auto_hunt_toggled` checken jeweils ob das andere Feature aktiv ist und stoppen es mit `"superseded"`. |
| 3 | `ui/mw_radio.py` | ~25 | `_on_band_changed` (`:259`): Block ergaenzen `if self._omni_tx.active: self._omni_tx.stop_omni_tx("band_change")`. `_on_mode_changed` (`:195`): `stop_auto_hunt("mode_change")` Reason umbenannt zu `"ft_mode_change"`, Block ergaenzen fuer `stop_omni_tx("ft_mode_change")`. `_on_rx_mode_changed` (`:356`): NEUER Block — bei RX-Wechsel zu „normal" ruft `stop_omni_tx("rx_mode_change")` UND `stop_auto_hunt("rx_mode_change")`. Plus `_update_button_visibility(rx_mode)` aufrufen am Ende. |
| 4 | `ui/control_panel.py` | ~5 | Methode `update_omni_tx(active: bool)` falls noch nicht da (sonst keine Aenderung). Layout der 3 Buttons besteht seit v0.75 — nur Sichtbarkeit wird via `setHidden()` gesteuert. |

### Tests neu

| Datei | Tests |
|---|---|
| `tests/test_omni_tx.py` (NEU) | 9 Unit-Tests: `test_initial_state_inactive`, `test_default_block_cycles_is_80`, `test_enable_resets_state`, `test_5_slot_pattern_block1`, `test_5_slot_pattern_block2`, `test_block_switch_after_block_cycles`, `test_block_switch_at_position_0_only`, `test_qso_resets_counter_keeps_block`, `test_stop_omni_tx_resets_pending_switch` (Bug-Fix C6) |
| `tests/test_omni_extended.py` (NEU) | 9 Integration-Tests: `test_band_change_stops_omni`, `test_ft_mode_change_stops_omni`, `test_rx_mode_change_stops_omni`, `test_diversity_submode_change_keeps_omni_running`, `test_totmann_stops_omni_unconditional` (auch bei QSO!), `test_button_visibility_per_mode`, `test_mutually_exclusive_omni_starts_stops_autohunt_with_superseded`, `test_easter_egg_override_in_normal_mode`, `test_easter_egg_resets_on_rx_mode_change` |
| `tests/test_auto_hunt_extended.py` (ERGAENZEN) | +2 NEU + 1 ANGEPASST: `test_auto_hunt_visible_only_in_diversity` (NEU), `test_rx_mode_change_stops_auto_hunt` (NEU), bestehender `mode_change`-Test anpassen auf neuen Reason `ft_mode_change` |

**Pytest-Fixture (NEU in `tests/conftest.py`):**
```python
@pytest.fixture
def omni_tx_fresh():
    """Reset OmniTX-Singleton zwischen Tests."""
    from core import omni_tx
    omni_tx._instance = None
    yield
    omni_tx._instance = None
```
Hinweis: `AutoHunt` ist **kein Singleton** (wird in `main_window.py:_auto_hunt = AutoHunt(...)` direkt instanziiert), braucht keine Reset-Fixture.

**Headless-Visibility-Test:** `setHidden()` ist persistent, `isHidden()`
spiegelt den Property-Wert wider (auch im offscreen-Modus). Tests pruefen
`btn_omni_cq.isHidden()` (nicht `isVisible()`).

### Doku

| Datei | Aenderung |
|---|---|
| `main.py` | `APP_VERSION = "0.78"`. |
| `CLAUDE.md` | Header v0.77 → v0.78. „Bekannte Fallen" um OMNI-spezifische Notes ergaenzen (`_pending_switch` Reset-Bug, RX-Modus-Hook-Pflicht, Reason-Tabelle G). |
| `HISTORY.md` | v0.78-Eintrag chronologisch (Format wie v0.75/v0.76/v0.77). |
| `README.md` | Sozial-Argumentation aus `docs/OMNI_TX_DESIGN.md` Sektion 9 darf erwaehnt werden. **NICHT publik:** Easter-Egg-Aktivierung. |
| `docs/OMNI_TX_DESIGN.md` | Bleibt unveraendert (Eingangs-Spec). |

---

## 4. Randbedingungen

### Threading (verifiziert in Schritt 0/2.5)

- `_omni_tx.advance()` in `mw_cycle.py:494` aus dem **Cycle-End-Slot** (Decoder→`Qt.QueuedConnection`→GUI-Thread).
- `_omni_tx.should_tx()` in `mw_qso.py:225` aus **CQ-Send-Pfad** (GUI-Thread).
- → Beide GUI-Thread, **kein Lock noetig**. KISS bleibt.

### Persistence

- OMNI-Status wird **nicht** persistiert (App-Restart → OMNI startet inaktiv).
- `block_cycles=80` ist Code-Konstante, nicht in Settings konfigurierbar.

### UI-Regeln

- **Direkt-Toggle ohne Dialog** (Memory-Begruendung oben zitiert).
- **Keine** „Hardware-Schaden moeglich"-Drohungstexte beim Klick.
- Statusbar-Ω-Symbol bestehend (`main_window.py:760-762`) bleibt unveraendert.
- Easter-Egg-Override bleibt erhalten als manueller Test-Bypass; in GitHub-Doku **nicht** publik (siehe `CLAUDE.md` „OMNI-TX (PRIVAT)" Sektion).

### Compatibility

- `enable()`/`disable()` in `core/omni_tx.py:137-151` bleiben als Thin-Wrapper damit bestehende Hooks (`main_window.py:546-548` Easter-Egg-Disable) ohne Anpassung weiterlaufen. Intern delegieren `disable()` an `stop_omni_tx("easter_egg_off")`, `enable()` setzt `active=True`.
- API-Brueche werden vermieden.

---

## 5. Nicht im Scope

- ❌ Kein Hard-Cap-Timer (kein 10-Min-Stop wie Auto-Hunt).
- ❌ Kein Aktivierungsdialog (Direkt-Toggle).
- ❌ Kein zusaetzlicher ANT1-Check im OMNI-Pfad (Encoder-zentralisiert v0.75).
- ❌ Kein Persistieren des OMNI-Status zwischen App-Sessions.
- ❌ Kein Frequenz-Springen waehrend OMNI (eine feste Audiofrequenz pro Session).
- ❌ Kein Versatz zwischen Even- und Odd-Slot.
- ❌ Kein OMNI im RX-Modus „normal" (Buttons unsichtbar ausser Easter-Egg-Override).
- ❌ Kein OMNI+Auto-Hunt-Hybrid (mutually exclusive).
- ❌ Kein automatischer GitHub-Push.
- ❌ Kein Lock fuer OMNI-State (single-operator, GUI-Thread).
- ❌ Keine Settings-Konfigurierbarkeit von `block_cycles`.
- ❌ Keine automatische OMNI-Aktivierung beim Wechsel Normal→Diversity (User klickt selbst).
- ❌ **Kein `_reset_presence`-Aufruf bei QSO-Ende.** Aktuell existiert dieser Hook nicht (V2 hatte das faelschlich angenommen, R1 entdeckt). Wer 30-min-QSO ohne Mausbewegung fuehrt → Totmann triggert nach QSO-Ende. **TODO fuer separates Release** (kleines `_reset_presence()`-Aufruf in `_on_qso_confirmed` waere ein 1-Zeilen-Fix, betrifft aber auch CQ-Flow → eigener Workflow).
- ❌ **Kein Defensive-Stop wenn Buttons via Mode-Coupling versteckt werden** (V2-Q3). Begruendung: B4 stoppt OMNI sowieso bei RX-Modus-Wechsel — wenn die Buttons unsichtbar werden, ist OMNI bereits gestoppt.

---

## 6. Testbarkeit

### Unit-Tests (`tests/test_omni_tx.py` NEU, 9 Cases)

```
test_initial_state_inactive             OmniTX.active == False initial
test_default_block_cycles_is_80          get_instance().block_cycles == 80
test_enable_resets_state                 enable() setzt slot=0, block=1, count=0, pending=False
test_5_slot_pattern_block1               Block 1: should_tx → (T,Even),(T,Odd),(F,_),(F,_),(F,_)
test_5_slot_pattern_block2               Block 2: should_tx → (T,Odd),(T,Even),(F,_),(F,_),(F,_)
test_block_switch_after_block_cycles     Counter erreicht block_cycles → switch markiert
test_block_switch_at_position_0_only     _pending_switch wartet bis slot_index==0
test_qso_resets_counter_keeps_block      on_qso_started → count=0, block + pending unveraendert
test_stop_omni_tx_resets_pending_switch  Bug-Fix C6: pending=False nach stop_omni_tx
```

### Integration-Tests (`tests/test_omni_extended.py` NEU, 9 Cases)

```
test_band_change_stops_omni                          _on_band_changed → omni_stopped("band_change")
test_ft_mode_change_stops_omni                        FT8→FT4 → omni_stopped("ft_mode_change")
test_rx_mode_change_stops_omni                        Diversity→Normal → omni_stopped("rx_mode_change")
test_diversity_submode_change_keeps_omni_running      Standard↔DX → OMNI aktiv bleibt
test_totmann_stops_omni_unconditional                 Presence timeout → Stop, auch waehrend QSO
test_button_visibility_per_mode                       btn_omni_cq.isHidden() je nach RX-Mode
test_mutually_exclusive_omni_starts_stops_autohunt_with_superseded  Auto-Hunt aktiv → OMNI-Klick → autohunt_stopped("superseded") + omni aktiv
test_easter_egg_override_in_normal_mode              Easter-Egg in „normal" → 3 Buttons sichtbar
test_easter_egg_resets_on_rx_mode_change             RX-Mode-Wechsel resetet Override
```

### Auto-Hunt-Erweiterung (`tests/test_auto_hunt_extended.py` ERGAENZEN, +2 NEU + 1 ANGEPASST)

```
test_auto_hunt_visible_only_in_diversity              btn_auto_hunt.isHidden() in „normal"
test_rx_mode_change_stops_auto_hunt                    Diversity→Normal → auto_hunt_stopped("rx_mode_change")
test_mode_change_stops_auto_hunt (BESTEHEND, ANGEPASST)  Reason von "mode_change" → "ft_mode_change"
```

### Mike's manuelle Verifikation (vor letztem Commit)

1. RX-Mode Diversity_Std → `btn_omni_cq` sichtbar → Klick → Ω erscheint
2. 16+ Zyklen → Logs zeigen TT-RRR-Pattern (Block 1)
3. Nach 80 Zyklen → Block-Wechsel im Log
4. QSO triggern → Counter geht auf 0, Block + `_pending_switch` bleiben
5. Bandwechsel waehrend OMNI → Stop in Statusbar
6. RX-Mode-Wechsel zu Normal → Buttons rendern neu, OMNI weg
7. FT-Modus-Wechsel FT8→FT4 in Diversity → OMNI stoppt
8. Diversity_Std → Diversity_Dx → OMNI laeuft weiter
9. Totmann-Test (Mausbewegung 16 min unterlassen, kein QSO) → Stop
10. Easter-Egg im Normal-Modus → 3 Buttons sichtbar; danach RX-Mode-Wechsel → Override resetet
11. Mutually-exclusive: Auto-Hunt aktiv → OMNI-Klick → Auto-Hunt stoppt, OMNI startet

---

## Implementierungs-Reihenfolge (atomare Commits)

| # | Commit | Tests-gruen-Bedingung |
|---|---|---|
| 1 | `refactor(omni_tx): OmniTX → QObject + omni_stopped Signal` | bestehende Tests gruen, Smoke-Test fuer Signal-Emit |
| 2 | `feat(omni_tx): stop_omni_tx(reason) zentralisiert + _pending_switch-Reset (C6)` | Unit-Tests fuer stop_omni_tx |
| 3 | `feat(omni_tx): block_cycles Default 80, OMNI_TX_ENABLED-Konstante entfernt` | `test_default_block_cycles_is_80` |
| 4 | `feat(ui): _on_btn_omni_cq_toggled + omni_stopped-Slot in main_window` | Manuell verifiziert, Smoke-Test |
| 5 | `feat(ui): Mode-Coupling Buttons (RX-Mode-abhaengig + Easter-Egg-Override)` | `test_button_visibility_per_mode`, `test_easter_egg_*` |
| 6 | `feat(safety): Stop-Hooks band/ft_mode/rx_mode/totmann fuer OMNI + Auto-Hunt rx_mode + Reason-Rename ft_mode` | 9 Integration-Tests, +2 Auto-Hunt-Tests |
| 7 | `feat(ui): Mutually-exclusive OMNI ↔ Auto-Hunt mit superseded-Reason` | `test_mutually_exclusive_*` |
| 8 | `chore(release): v0.78 — OMNI-TX scharfgeschaltet + Auto-Hunt Diversity-only` | Doku + Version-Bump |

Falls Tests bei Commit 4-7 nicht atomic gruen werden: zusammenfuehren („feat(ui): OMNI-Lifecycle vollstaendig"). KISS-Praeferenz.

---

## Aufwands-Schaetzung (aktualisiert nach R1-Review)

| Block | Code-Z. | h |
|---|---|---|
| OMNI-Code (`omni_tx.py` + `main_window.py` + `mw_radio.py`) | ~150 | ~2 |
| Auto-Hunt-Coupling + Reason-Rename | ~50 | ~0.75 |
| Mutually-exclusive Logik | ~30 | ~0.5 |
| Tests Unit + Integration + Fixture | ~220 | ~1.5 |
| Doku + Version-Bump | ~30 | ~0.5 |
| **Gesamt** | **~480** | **~5-5.5** |

(V2 hatte ~405 Z. / 4-5h. R1-Korrektur: Auto-Hunt-Coupling + Mutually-exclusive Reason-Logik realistisch +75 Zeilen.)

---

## Workflow-Hinweis

V3 ist Mike-freigabe-fertig. Nach OK von Mike (Schritt 4):
- Schritt 5 — Implementation in 8 atomaren Commits
- Schritt 5b — Final-R1-Codereview vor letztem Commit
- Schritt 6 — Lessons-Learned + Memory-Update

**Ende V3.**
