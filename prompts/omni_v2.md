# V2 — OMNI-TX Aktivierung + Auto-Hunt Mode-Coupling (SimpleFT8 v0.78)

**Workflow-Schritt:** 1c (V2, nach Self-Review von V1)
**Empfaenger:** DeepSeek-R1 (`deepseek-reasoner`) via `tools/deepseek_review.py`
**Ziel-Aktion an R1:** Prompt kritisieren — keine Loesung schreiben.

---

## Rollenanweisung an DeepSeek-R1

> Du bist Senior Python-Entwickler mit Hobby-Projekt-Erfahrung,
> spezialisiert auf Amateurfunk-Software (FT8/FT4, WSJT-X-Konzepte) und
> PySide6 (`Signal`/`Slot`, NICHT `pyqtSignal`/`pyqtSlot`). Du weisst,
> dass Code fuer einen einzelnen Operator NICHT die gleichen
> Schutzmechanismen wie Multi-Tenant-SaaS braucht.
>
> Deine einzige Aufgabe: diesen Prompt **kritisieren**, NICHT das Problem
> loesen. Liefere eine strukturierte Liste mit Luecken, fehlenden
> Informationen, Unklarheiten, Widerspruechen, Verbesserungsvorschlaegen
> und offenen Fragen.
>
> KRITISCHE REGELN fuer deine Findings:
>
> 1. **SCOPE-RESPEKT** — Wenn der Prompt etwas explizit als „out-of-scope"
>    oder „nicht im Scope" markiert, NICHT erneut als Finding melden.
>    Bewusste Mike-Entscheidungen sind keine Versehen.
>
> 2. **UX-DENKEN BEI REGELN** — Schwellwert-Faustregeln auf UX-Folgen pruefen.
>    Eine Regel die im Edge-Case zu schlechter Bedienbarkeit fuehrt ist
>    eine schlechte Regel.
>
> 3. **KISS VOR DEFENSIV** — Bevor du Komplexitaet vorschlaegst (neue
>    Klasse, Fallback, Library, Wrapper), frage dich: Wahrscheinlichkeit
>    dass das Problem real auftritt > 50%? Wenn nein, weglassen. „Koennte
>    vielleicht passieren" ist KEIN Grund fuer Code-Komplexitaet im
>    Hobby-Single-Operator-Tool.
>
> 4. **PROJEKT-BEZUG** — Jedes Finding muss am konkreten Use-Case
>    (Hobby-Funker, Single-Operator, Mike DA1MHH) gemessen werden.
>    Generic Best-Practice-Rufe ohne Projekt-Bezug sind Noise.
>
> 5. **FORMAT** — Tabelle mit Spalten: Schwere | Finding | Datei:Zeile |
>    Empfehlung. Severity-Stufen: Bug (rot) / Risiko (orange) /
>    Verbesserung (gelb) / Hinweis (grau).
>
> Bedenke: **Overengineering ist selbst ein Fehler den du benennen sollst.**

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

Wichtig fuer V2/V3/Implementation:

| Begriff | Was | Handler | Werte |
|---|---|---|---|
| **FT-Modus** | Protokoll-Wechsel | `mw_radio.py:195` `_on_mode_changed(mode)` | `"FT8"` / `"FT4"` / `"FT2"` |
| **RX-Modus** | Empfangs-Strategie | `mw_radio.py:356` `_on_rx_mode_changed(mode)` | `"normal"` / `"diversity"` |
| **Diversity-Submodus** | Scoring innerhalb Diversity | `_diversity_ctrl.scoring_mode` | `"normal"` / `"dx"` |

**Konsequenz:** Wenn dieser Prompt von „Modus-Wechsel" spricht, ist der
**Kontext explizit benannt** (FT- oder RX-Modus). Im OMNI-Kontext ist das
relevante Ereignis der **RX-Modus-Wechsel** (Diversity→Normal stoppt OMNI).

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
- Direkt-Toggle ohne Aktivierungsdialog (Memory `feedback_disclaimer_no_threat.md`)
- Easter-Egg (Klick Versionsnummer) bleibt als **manueller Override** fuer Mike's Tests

Plus parallel: Auto-Hunt von Easter-Egg-only auf Diversity-only umstellen
(gleiche UI-Logik wie OMNI), damit beide Power-User-Features konsistent.

---

## 2. Akzeptanzkriterien

### A — UI-Verhalten (Mode-Coupling + Easter-Egg-Override)

| # | Kriterium |
|---|---|
| A1 | RX-Modus **„normal"**: nur `btn_cq` sichtbar. `btn_omni_cq` + `btn_auto_hunt` versteckt (`setHidden(True)`). |
| A2 | RX-Modus **„diversity"** (egal ob Submodus Standard oder DX): `btn_omni_cq` + `btn_auto_hunt` sichtbar, `btn_cq` versteckt. |
| A3 | **Easter-Egg-Override** (Klick auf Versionsnummer): solange aktiv, sind in **„normal"** zusaetzlich `btn_omni_cq` + `btn_auto_hunt` sichtbar (3-Button-Layout). In „diversity" hat Easter-Egg keine zusaetzliche Wirkung. RX-Modus-Wechsel setzt Easter-Egg-Override automatisch zurueck. |
| A4 | `btn_omni_cq` und `btn_auto_hunt` sind **mutually exclusive**: Klick auf inaktiven stoppt den aktuell laufenden via `stop_*("manual_halt")` (oder neuem Reason — siehe offene Frage Q1) und startet sich selbst. Reine UI-Sequenz, keine Race-Condition. |
| A5 | OMNI-Status sichtbar in Statusbar als **„Ω Even=N Odd=M"** (Code bestehend, `main_window.py:760-762` lesen `_omni_tx.cq_even_count`/`cq_odd_count`). Verschwindet wenn OMNI inaktiv. |

### B — Aktivierung + Stop-Bedingungen

| # | Kriterium |
|---|---|
| B1 | Klick `btn_omni_cq` → OMNI aktiv (kein Aktivierungsdialog, Direkt-Toggle). |
| B2 | Erneuter Klick → `stop_omni_tx("manual_halt")`. |
| B3 | Bandwechsel waehrend OMNI aktiv → `stop_omni_tx("band_change")` in `mw_radio.py:259` `_on_band_changed` (analog Auto-Hunt `:297-299`). |
| B4 | RX-Modus-Wechsel von „diversity" nach „normal" waehrend OMNI aktiv → `stop_omni_tx("mode_change")` in `mw_radio.py:_on_rx_mode_changed` (NEUER Hook, aktuell nicht verkabelt). |
| B5 | FT-Modus-Wechsel (FT8↔FT4↔FT2) waehrend OMNI aktiv → `stop_omni_tx("mode_change")` in `mw_radio.py:195` `_on_mode_changed` (analog existierendes `stop_auto_hunt("mode_change")` Z.198). |
| B6 | Diversity-Submodus-Wechsel (Standard ↔ DX) waehrend OMNI → **OMNI laeuft weiter** (beide sind Diversity, OMNI-Logik unabhaengig vom Scoring). |
| B7 | Totmannschalter (15 min keine Maus/Tastatur, kein laufendes QSO) → `stop_omni_tx("totmann_expired")` in `main_window.py:836-849` `_on_presence_tick` (Anschluss an existing Auto-Hunt-Hook `:915`). |
| B8 | Bei laufendem QSO greift Totmann **nicht** (analog Auto-Hunt v0.75 — kein Stop). |
| B9 | QSO-Ende → Totmann-Timer-Reset (analog Auto-Hunt `_reset_presence`-Praxis), damit nach 30-min-QSO nicht sofort Totmann-Stop greift. |
| B10 | Kein Hard-Cap-Timer (im Gegensatz zu Auto-Hunt 10-min-Stop). OMNI laeuft bis manueller oder System-Stop. Begruendung: passiver Modus, keine Bot-Tarn-Anforderung. |

### C — OMNI-Logik (5-Slot-Pattern)

| # | Kriterium |
|---|---|
| C1 | Default `block_cycles = 80` in `core/omni_tx.py:54` (aktuell 40 → wird umgestellt). Plan v3.2 ist Wahrheits-Quelle. |
| C2 | Block 1: TX-Pattern Pos 0=Even, Pos 1=Odd, Pos 2-4=RX. |
| C3 | Block 2: TX-Pattern Pos 0=Odd, Pos 1=Even, Pos 2-4=RX. |
| C4 | Nach `block_cycles` Zyklen: Block-Wechsel **nur an Pos 0** (Pattern-Grenze, `_pending_switch`-Logik). |
| C5 | `on_qso_started()` setzt `_cycle_count = 0`, Block + `_pending_switch` bleiben unveraendert. |
| C6 | **`stop_omni_tx(reason)` setzt `_pending_switch = False`** (sonst Bug: nach Re-`enable()` springt Block sofort). |
| C7 | `OMNI_TX_ENABLED` Konstante in `core/omni_tx.py:35` wird **entfernt** (bisheriges Gate, jetzt obsolet — Singleton-Init in `main_window.py:230-232` reicht). |

### D — Auto-Hunt Mode-Coupling (Zusatz-Aufgabe v0.78)

| # | Kriterium |
|---|---|
| D1 | `btn_auto_hunt` sichtbar nur in RX-Modus „diversity" (analog OMNI A2). |
| D2 | Easter-Egg-Override macht `btn_auto_hunt` zusaetzlich sichtbar in „normal" (analog OMNI A3). |
| D3 | RX-Modus-Wechsel diversity→normal stoppt Auto-Hunt mit `stop_auto_hunt("mode_change")` in `mw_radio.py:_on_rx_mode_changed` (**NEUER Hook**, parallel zu B4 OMNI). Bestehende `mode_change`-Logik in `mw_radio.py:198` (FT-Modus) bleibt unveraendert — beide Handler triggern denselben Reason, KISS. |

### E — Hardware-Pflicht ANT1

| # | Kriterium |
|---|---|
| E1 | OMNI-TX bekommt **keinen separaten** ANT1-Check. Encoder-Schicht (v0.75 zentral) greift. |
| E2 | Bestehender Test `tests/test_encoder.py::test_encoder_transmit_sets_ant1_before_ptt_on` deckt die Pflicht ab. Keine neuen ANT1-Tests in v0.78. |

### F — Tests + Build

| # | Kriterium |
|---|---|
| F1 | Test-Suite waechst von 472 auf ~488-492 gruen (+16-20 neue Tests). |
| F2 | App startet ohne Fehler, OMNI-Toggle funktioniert manuell in beiden Diversity-Submodi. |
| F3 | `APP_VERSION = "0.78"` in `main.py`. Tag-Setzung **erst nach Mike-Freigabe** (separater Schritt). |

---

## 3. Betroffene Module/Dateien

### Code-Aenderungen

| # | Datei | Zeilen | Was |
|---|---|---|---|
| 1 | `core/omni_tx.py` | ~50 | OmniTX → `QObject` (analog `core/auto_hunt.py:67ff`). Neues Signal `omni_stopped = Signal(str)`. Neue Methode `stop_omni_tx(reason: str)` zentralisiert: `active=False`, `_slot_index=0`, `_cycle_count=0`, `_pending_switch=False` (Bug-Fix C6), Signal-Emit. `enable()`/`disable()` als Thin-Wrapper bleiben (Test-Kompatibilitaet). `block_cycles` Default 40 → **80**. `OMNI_TX_ENABLED`-Konstante entfernt (C7). |
| 2 | `ui/main_window.py` | ~80 | Connect `_omni_tx.omni_stopped → _on_omni_stopped(reason)` Slot (analog `:253` Auto-Hunt). Neuer Handler `_on_btn_omni_cq_toggled` (analog Auto-Hunt `:565`). Mode-Coupling-Helper `_update_button_visibility(rx_mode)` der `btn_cq`/`btn_omni_cq`/`btn_auto_hunt` mode-abhaengig zeigt/versteckt + Easter-Egg-Override. Easter-Egg-Toggle (`:530-557`) ruft den Helper. Totmann-Hook (`:836-849`/`:915`) ergaenzt um `stop_omni_tx("totmann_expired")`. |
| 3 | `ui/mw_radio.py` | ~20 | `_on_band_changed` (`:259`): Block ergaenzen `if self._omni_tx.active: self._omni_tx.stop_omni_tx("band_change")`. `_on_mode_changed` (`:195`): analog ergaenzen mit `"mode_change"`. `_on_rx_mode_changed` (`:356`): NEUER Block — `if RX-Wechsel zu "normal":` → `stop_omni_tx("mode_change")` UND `stop_auto_hunt("mode_change")`. Plus `_update_button_visibility` aufrufen am Ende. |
| 4 | `ui/control_panel.py` | ~10 | Falls `update_omni_tx(bool)`-Methode existiert, bleibt unveraendert (wird vom Slot aus aufgerufen). Keine Layout-Aenderung — die 3 Buttons sind seit v0.75 da. Nur Sichtbarkeit wird via `setHidden()` gesteuert. |

### Tests neu

| Datei | Tests |
|---|---|
| `tests/test_omni_tx.py` (NEU) | 9 Unit-Tests: `test_initial_state_inactive`, `test_default_block_cycles_is_80`, `test_enable_resets_state`, `test_5_slot_pattern_block1`, `test_5_slot_pattern_block2`, `test_block_switch_after_block_cycles`, `test_block_switch_at_position_0_only`, `test_qso_resets_counter_keeps_block`, `test_stop_omni_tx_resets_pending_switch` (Bug C6) |
| `tests/test_omni_extended.py` (NEU) | 8 Integration-Tests: `test_band_change_stops_omni`, `test_ft_mode_change_stops_omni`, `test_rx_mode_change_stops_omni`, `test_diversity_submode_change_keeps_omni_running`, `test_totmann_stops_omni_when_no_qso`, `test_totmann_does_not_stop_during_qso`, `test_button_visibility_per_mode`, `test_mutually_exclusive_omni_autohunt` |
| `tests/test_auto_hunt_extended.py` (ERGAENZEN) | +2: `test_auto_hunt_visible_only_in_diversity`, `test_rx_mode_change_stops_auto_hunt` |

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
Analog fuer AutoHunt-Singleton falls noetig.

**Headless-Visibility-Test:** `setHidden()` ist persistent, `isHidden()`
spiegelt den Property-Wert wider (auch im offscreen-Modus). Tests pruefen
also `btn_omni_cq.isHidden()` (nicht `isVisible()`).

### Doku

| Datei | Aenderung |
|---|---|
| `main.py` | `APP_VERSION = "0.78"`. |
| `CLAUDE.md` | Header v0.77 → v0.78. „Bekannte Fallen" um OMNI-spezifische Notes ergaenzen (`_pending_switch` Reset-Bug, RX-Modus-Hook-Pflicht). |
| `HISTORY.md` | v0.78-Eintrag chronologisch (Format wie v0.75/v0.76/v0.77). |
| `README.md` | Sozial-Argumentation aus `docs/OMNI_TX_DESIGN.md` Sektion 9 darf erwaehnt werden. **NICHT publik:** Easter-Egg-Aktivierung. |
| `docs/OMNI_TX_DESIGN.md` | Bleibt unveraendert (Eingangs-Spec). |

---

## 4. Randbedingungen

### Threading (verifiziert)

- `_omni_tx.advance()` wird in `mw_cycle.py:494` aus dem **Cycle-End-Slot** aufgerufen (Decoder-Thread → `Qt.QueuedConnection` → GUI-Thread).
- `_omni_tx.should_tx()` wird in `mw_qso.py:225` aus dem **CQ-Send-Pfad** aufgerufen (GUI-Thread).
- → **Kein Lock noetig**, beide Calls sind im GUI-Thread. KISS bleibt.

### Persistence

- OMNI-Status wird **nicht** persistiert (App-Restart → OMNI startet inaktiv, Mike muss neu klicken). Begruendung: Hobby-Tool.
- `block_cycles=80` ist Code-Konstante, nicht in Settings konfigurierbar.

### UI-Regeln

- **Direkt-Toggle ohne Dialog** (Memory `feedback_disclaimer_no_threat.md`).
- **Keine** „Hardware-Schaden moeglich"-Drohungstexte beim Klick.
- Statusbar-Ω-Symbol bestehend (`main_window.py:760-762`) bleibt unveraendert.
- Easter-Egg-Override bleibt erhalten als manueller Test-Bypass; in GitHub-Doku **nicht** publik (siehe `CLAUDE.md` „OMNI-TX (PRIVAT)" Sektion).

### Compatibility

- `enable()`/`disable()` in `core/omni_tx.py:137-151` bleiben als Thin-Wrapper damit bestehende Hooks (`main_window.py:546-548` Easter-Egg-Disable) ohne Anpassung weiterlaufen. Intern delegieren sie an `stop_omni_tx("easter_egg_off")` bzw. setzen `active=True`.
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

### Integration-Tests (`tests/test_omni_extended.py` NEU, 8 Cases)

```
test_band_change_stops_omni                       _on_band_changed → omni_stopped("band_change")
test_ft_mode_change_stops_omni                    FT8→FT4 in Diversity → omni_stopped("mode_change")
test_rx_mode_change_stops_omni                    Diversity→Normal → omni_stopped("mode_change")
test_diversity_submode_change_keeps_omni_running  Standard↔DX → OMNI aktiv bleibt
test_totmann_stops_omni_when_no_qso               Presence timeout, kein QSO → Stop
test_totmann_does_not_stop_during_qso             Presence timeout, QSO laeuft → kein Stop
test_button_visibility_per_mode                   btn_omni_cq.isHidden() je nach RX-Mode
test_mutually_exclusive_omni_autohunt             Auto-Hunt aktiv → OMNI-Klick stoppt Auto-Hunt + startet OMNI
```

### Auto-Hunt-Erweiterung (`tests/test_auto_hunt_extended.py` ERGAENZEN, +2 Cases)

```
test_auto_hunt_visible_only_in_diversity   btn_auto_hunt.isHidden() in RX-Mode "normal"
test_rx_mode_change_stops_auto_hunt         Diversity→Normal → auto_hunt_stopped("mode_change")
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
9. Totmann (15 min ohne Maus, kein QSO) → Stop
10. Easter-Egg im Normal-Modus → 3 Buttons sichtbar; danach RX-Mode-Wechsel → Override resetet

---

## Implementierungs-Reihenfolge (atomare Commits)

| # | Commit | Tests-gruen-Bedingung |
|---|---|---|
| 1 | `refactor(omni_tx): OmniTX → QObject + omni_stopped Signal` | bestehende Tests gruen, neuer Test `test_signal_emits` |
| 2 | `feat(omni_tx): stop_omni_tx(reason) zentralisiert + _pending_switch-Reset` | Unit-Tests fuer stop_omni_tx |
| 3 | `feat(omni_tx): block_cycles Default 80, OMNI_TX_ENABLED-Konstante entfernt` | `test_default_block_cycles_is_80` |
| 4 | `feat(ui): _on_btn_omni_cq_toggled + omni_stopped-Slot in main_window` | Manuell verifiziert |
| 5 | `feat(ui): Mode-Coupling Buttons (RX-Mode-abhaengig + Easter-Egg-Override)` | `test_button_visibility_per_mode`, +2 Auto-Hunt |
| 6 | `feat(safety): Stop-Hooks band/ft_mode/rx_mode/totmann fuer OMNI + Auto-Hunt rx_mode` | 6 Integration-Tests |
| 7 | `chore(release): v0.78 — OMNI-TX scharfgeschaltet + Auto-Hunt Diversity-only` | Doku + Version-Bump |

Falls Tests bei Commit 4-6 nicht atomic gruen werden: Commit 4-6 zu einem
zusammenfuehren („feat(ui): OMNI-Lifecycle vollstaendig"). KISS-Praeferenz.

---

## Aufwands-Schaetzung

| Block | Code-Z. | h |
|---|---|---|
| OMNI-Code (`omni_tx.py` + `main_window.py` + `mw_radio.py`) | ~150 | ~2 |
| Auto-Hunt-Coupling | ~25 | ~0.5 |
| Tests Unit + Integration + Fixture | ~200 | ~1.5 |
| Doku + Version-Bump | ~30 | ~0.5 |
| **Gesamt** | **~405** | **~4-5** |

Vergleich Schritt-0-Schaetzung (~425 Z. / 4-5h): liegt im Rahmen.

---

## Offene Fragen an R1 (explizit)

- **Q1 (A4):** Mutually-exclusive — sollte der Reason beim automatischen Stop des „verlierenden" Features `"manual_halt"` sein, oder ein eigener Reason wie `"superseded_by_other"`? KISS-Praeferenz: `"manual_halt"` (User hat zwar nicht direkt gestoppt, aber das ist Debug-Detail, kein User-relevanter Unterschied). Frage: stimmst du zu, oder gibt es einen Fall wo Granularitaet wichtig wird?
- **Q2 (B7/B9):** Totmannschalter im OMNI-Pfad — `_reset_presence` bei QSO-Ende ist heute fuer CQ-Resume-Logik verkabelt. Sollten wir explizit pruefen, dass OMNI nach QSO-Ende **nicht** auto-resumed (analog Auto-Hunt-Pattern: nach Stop ist Pflicht-Restart durch User-Klick)?
- **Q3 (Implementierungs-Reihenfolge Commit 5/6):** Mode-Coupling vs Stop-Hooks — kann beim Test ein Problem entstehen wenn Mode-Coupling die Buttons versteckt aber `_omni_tx.active==True`? Sollten wir bei Commit 5 schon einen Defensive-Stop einbauen (Button-Hide → Auto-Stop)?

---

## Workflow-Hinweis

Diese V2 wird via `tools/deepseek_review.py` an `deepseek-reasoner` mit
folgenden angehaengten Files geschickt:

- `core/omni_tx.py`
- `core/auto_hunt.py`
- `ui/main_window.py`
- `ui/mw_radio.py`
- `ui/mw_cycle.py`
- `ui/mw_qso.py`
- `ui/control_panel.py`
- `tests/test_auto_hunt_extended.py`
- `docs/OMNI_TX_DESIGN.md`

R1-Antwort → Schritt 2.5 (Code-Verifikation der Findings) → Schritt 3 (V3
+ Zusammenfassung der angenommenen/abgelehnten Findings) → Mike-Freigabe.

**Ende V2.**
