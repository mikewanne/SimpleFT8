# V1 — OMNI-TX Aktivierung + Auto-Hunt Mode-Coupling (SimpleFT8 v0.78)

**Workflow-Schritt:** 1a (V1, vor Self-Review)
**Vorausgegangen:** Schritt 0 — Code-Verifikation abgeschlossen, siehe `docs/OMNI_TX_DESIGN.md` Sektion 14.
**Naechster Schritt:** 1b (Self-Review als frische KI) → 1c (V2)

---

## Rollenanweisung (wandert in V2 als Pflicht-Kopf an DeepSeek)

> Du bist Senior Python-Entwickler mit Hobby-Projekt-Erfahrung,
> spezialisiert auf Amateurfunk-Software (FT8/FT4, WSJT-X-Konzepte) und
> PySide6 (Signal/Slot, NICHT pyqtSignal/pyqtSlot). Du weisst dass Code
> fuer einen einzelnen Operator NICHT die gleichen Schutzmechanismen wie
> Multi-Tenant-SaaS braucht.
>
> Deine einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT das
> Problem zu loesen. Erstelle eine strukturierte Liste mit: Luecken,
> fehlenden Informationen, Unklarheiten, Widerspruechen,
> Verbesserungsvorschlaegen und offenen Fragen.
>
> KRITISCHE REGELN:
> 1. SCOPE-RESPEKT — Out-of-scope-Markierungen NICHT erneut als Finding melden.
> 2. UX-DENKEN — Schwellwert-Faustregeln auf UX-Folgen pruefen.
> 3. KISS VOR DEFENSIV — Komplexitaet nur wenn Wahrscheinlichkeit > 50%.
> 4. PROJEKT-BEZUG — Jedes Finding muss am Hobby-Single-Operator-Use-Case messen.
> 5. FORMAT — Tabelle: Schwere | Finding | Datei:Zeile | Empfehlung.
>    Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).
>
> Bedenke: Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Projektphilosophie (Kontext)

- SimpleFT8 ist Hobby-Funker-Tool fuer einen einzelnen Operator (Mike, DA1MHH).
- KEIN Contest-Tool, KEIN Multi-Op, KEINE Pileup-Jagd.
- KISS strikt: drei einfache Zeilen schlagen eine schlaue Abstraktion.
- **Hardware-Pflicht:** ANT1 = TX immer. ANT2 = nur RX. Bei TX auf ANT2 (Regenrinne) Hardware-Schaden moeglich. Vor jedem TX-Trigger muss `radio.set_tx_antenna("ANT1")` verifiziert sein. Encoder-Schicht greift bereits zentral (v0.75).
- Visuell: dunkles Theme, Neon-Akzente. Keine 90er-Jahre-Funktionalitaets-UI.

---

## 1. Ziel

OMNI-TX-Feature **scharfschalten** — heute zu ~70% verkabelt
(`core/omni_tx.py` komplett, Hooks in `mw_qso.py`/`mw_cycle.py`/
`main_window.py` integriert, aber Aktivierungs-Pfad und Stop-Bedingungen
fehlen). Plus parallel Auto-Hunt von Easter-Egg-only auf
**Diversity-only** umstellen (gleiche UI-Logik wie OMNI).

Mike's Plan v3.2 (siehe `docs/OMNI_TX_DESIGN.md`): 5-Slot-Pattern
[TX TX RX RX RX] mit Even/Odd-Rotation, Block-Wechsel nach 80 Zyklen,
Mode-gekoppelte UI (Buttons sichtbar nur in Diversity), Direkt-Toggle
ohne Aktivierungsdialog.

**Design-Spec:** `docs/OMNI_TX_DESIGN.md` — vollstaendige permanente Spec.
Diese V1 referenziert die Spec, dupliziert sie nicht.

---

## 2. Akzeptanzkriterien

### A — UI-Verhalten

| # | Kriterium | Verifikation |
|---|---|---|
| A1 | Im Modus **Normal** ist nur `btn_cq` sichtbar. `btn_omni_cq` und `btn_auto_hunt` sind unsichtbar. | Klick „Normal"-Radio → visuell pruefen + Test |
| A2 | Im Modus **Diversity_Standard** und **Diversity_Dx** sind `btn_omni_cq` + `btn_auto_hunt` sichtbar, `btn_cq` unsichtbar. | Klick Diversity-Radios → visuell pruefen + Test |
| A3 | Easter-Egg (Klick auf Versionsnummer) zeigt im Normal-Modus zusaetzlich alle 3 Buttons (Test-Override fuer Mike). | Klick Versionsnummer im Normal-Modus → 3 Buttons sichtbar |
| A4 | `btn_omni_cq` und `btn_auto_hunt` sind **mutually exclusive**: Klick auf einen waehrend der andere aktiv ist → laufendes Feature stoppt automatisch. | Test: Auto-Hunt aktiv → OMNI-Klick → Auto-Hunt-Stop ausgeloest |
| A5 | OMNI-Status sichtbar in Statusbar als **Ω-Symbol + Block + Counter** (bestehender Code `main_window.py:760-762`). | Klick OMNI-Toggle → Ω erscheint, verschwindet bei Stop |

### B — Aktivierung + Stop-Bedingungen

| # | Kriterium | Verifikation |
|---|---|---|
| B1 | Klick `btn_omni_cq` → OMNI aktiv (kein Aktivierungsdialog, Direkt-Toggle). | Test + manuell |
| B2 | Erneuter Klick auf aktiven `btn_omni_cq` → `stop_omni_tx("manual_halt")`. | Test |
| B3 | Bandwechsel waehrend OMNI aktiv → `stop_omni_tx("band_change")`. | Test |
| B4 | Modus-Wechsel von Diversity nach Normal waehrend OMNI aktiv → `stop_omni_tx("mode_change")`. | Test |
| B5 | Totmannschalter (15 min Inaktivitaet, kein laufendes QSO) → `stop_omni_tx("totmann_expired")`. | Test (Mock-Time) |
| B6 | Bei laufendem QSO greift Totmann **nicht** (analog Auto-Hunt v0.75). | Test |
| B7 | Es gibt **keinen** Hard-Cap-Timer (im Gegensatz zu Auto-Hunt's 10-min-Stop). OMNI laeuft bis manueller oder System-Stop. | Test (kein Timer existiert) |

### C — OMNI-Logik (5-Slot-Pattern)

| # | Kriterium | Verifikation |
|---|---|---|
| C1 | Default `block_cycles = 80` (Plan v3.2; aktueller Code-Default 40 wird umgestellt). | Code-Inspektion + Test |
| C2 | Block 1: TX-Pattern Pos 0=Even, Pos 1=Odd, Pos 2-4=RX. | Test (16+ Zyklen Logs) |
| C3 | Block 2: TX-Pattern Pos 0=Odd, Pos 1=Even, Pos 2-4=RX. | Test |
| C4 | Nach 80 Zyklen Block-Wechsel **nur an Pos 0** (Pattern-Grenze). | Test (`_pending_switch`-Logik bestaetigen) |
| C5 | `on_qso_started()` setzt `_cycle_count = 0`, Block bleibt unveraendert. | Test (existiert) |

### D — Auto-Hunt Mode-Coupling (Zusatz-Aufgabe v0.78)

| # | Kriterium | Verifikation |
|---|---|---|
| D1 | Auto-Hunt-Button `btn_auto_hunt` sichtbar **nur in Diversity_Standard / Diversity_Dx** (analog OMNI). | Test |
| D2 | Easter-Egg im Normal-Modus zeigt `btn_auto_hunt` zusaetzlich (Test-Override). | Test |
| D3 | Modus-Wechsel von Diversity nach Normal stoppt Auto-Hunt mit `auto_hunt_stopped("mode_change")`. | Test (Stop-Reason existiert seit v0.75) |

### E — Hardware-Pflicht ANT1

| # | Kriterium | Verifikation |
|---|---|---|
| E1 | OMNI-TX bekommt **keinen separaten** ANT1-Check — Encoder-Schicht (v0.75) greift automatisch. | Code-Inspektion (kein neuer ANT1-Code in OMNI-Pfad) |
| E2 | Vor jedem TX-Trigger ist `set_tx_antenna("ANT1")` durch `Encoder.transmit()` (Z.235) garantiert. | Bestehender Test deckt das ab |

### F — Tests + Build

| # | Kriterium | Verifikation |
|---|---|---|
| F1 | Test-Suite waechst von 472 auf ~485-490 gruen (~13-18 neue Tests). | `./venv/bin/python3 -m pytest tests/ -q` |
| F2 | App startet ohne Fehler, OMNI-Toggle funktioniert manuell in beiden Diversity-Modi. | Manuell |
| F3 | `OMNI_TX_ENABLED` Konstante in `core/omni_tx.py` bleibt **als Konstante** existent (Default `True` nach Aktivierung), aber wird im Code **nicht mehr als Gate** verwendet — Singleton-Init im `main_window.py` reicht. Begruendung: nach v0.78 ist das Feature scharfgeschaltet, kein zweiter Lock noetig. | Code-Inspektion |

---

## 3. Betroffene Module/Dateien

### Hauptaenderungen

| Datei | Was | Aufwand |
|---|---|---|
| `core/omni_tx.py` | OmniTX → QObject mit Signal `omni_stopped(reason: str)`. Neue Methode `stop_omni_tx(reason)` zentralisiert. `block_cycles` Default 40 → 80. | ~40 Z. |
| `ui/main_window.py` | Neuer Handler `_on_btn_omni_cq_toggled` (analog `:255` Auto-Hunt). Mode-Coupling: `_on_mode_changed` rendert Buttons abhaengig von Diversity/Normal. Easter-Egg-Toggle wird Test-Override. Slot fuer `omni_stopped`-Signal. Totmann-Hook ergaenzen (`:836-849`). | ~80 Z. |
| `ui/mw_radio.py` | `_on_band_changed` (`:259`): `stop_omni_tx("band_change")` analog Auto-Hunt `:297-299`. `_on_mode_changed` (`:195`): `stop_omni_tx("mode_change")` und `stop_auto_hunt("mode_change")` bei Wechsel zu Normal. | ~15 Z. |
| `ui/control_panel.py` | Sichtbarkeits-Helper `update_button_visibility(mode)` der die 3 Buttons mode-abhaengig zeigt/versteckt. Aktuell `:774-802` Layout vorhanden. | ~25 Z. |

### Tests neu

| Datei | Tests |
|---|---|
| `tests/test_omni_tx.py` (NEU) | 8 Unit-Tests: initial_state, enable_resets_state, 5-slot-pattern Block 1/2, block_switch, qso_resets_counter, disable_resets_state |
| `tests/test_omni_extended.py` (NEU) | 6 Integration-Tests: band_change, mode_change, totmann (mit/ohne QSO), button_visibility, mutually_exclusive_omni_autohunt |
| `tests/test_auto_hunt_extended.py` (ERGAENZEN) | +2 Tests: auto_hunt_visible_only_in_diversity, mode_change_stops_auto_hunt |

### Dokumentation

| Datei | Aenderung |
|---|---|
| `CLAUDE.md` | Header v0.77 → v0.78. „Bekannte Fallen" um OMNI-Eintraege ergaenzen. |
| `HISTORY.md` | v0.78-Eintrag chronologisch (siehe `docs/OMNI_TX_DESIGN.md` Sektion 12 als Referenz). |
| `main.py` | `APP_VERSION = "0.78"`. |
| `README.md` | OMNI-Feature darf erwaehnt werden (Plan v3.2 Sozialargumentation), Aktivierung **NICHT publik**. |
| `docs/OMNI_TX_DESIGN.md` | Bleibt unveraendert — ist die Eingangs-Spec. |

---

## 4. Randbedingungen

### Threading

- OmniTX wird QObject (Signal-faehig). `omni_stopped`-Signal wird per
  Standard-Auto-Connection (Default-Connection-Type) ausgeliefert —
  Singleton lebt im GUI-Thread, Slot ist im GUI-Thread → kein Cross-Thread-Issue.
- Decoder-Thread ruft `advance()` und `should_tx()` (lesend/inkrementell)
  — Race-Risiko minimal weil Mike Single-Operator ist; **kein Lock noetig**
  (KISS-Bewertung; bei Bedarf nachruesten).

### Persistence

- OMNI-Status wird **nicht** persistiert (App-Restart → OMNI startet immer
  inaktiv, Mike muss neu klicken). Begruendung: Hobby-Tool, kein Hot-Recovery.
- `block_cycles=80` ist Konstante, **nicht** in Settings konfigurierbar.

### UI-Regeln

- Direkt-Toggle ohne Aktivierungsdialog (Memory `feedback_disclaimer_no_threat.md`).
  Auf KEINEN Fall einen „Hardware-Schaden moeglich"-Dialog beim Klick einbauen.
- Statusbar-Ω-Symbol bestehend — wird nicht angefasst.
- Easter-Egg bleibt Test-Bypass fuer Mike, ist GitHub-publik **nicht**
  dokumentiert (siehe CLAUDE.md „OMNI-TX (PRIVAT)" Sektion).

### Hardware-Pflicht

- ANT1=TX-Pflicht ist Encoder-zentralisiert (v0.75). OMNI-Pfad bekommt
  keinen separaten ANT1-Check. **NICHT** doppelt einbauen — KISS.

### Compatibility

- Bestehende Hooks bleiben:
  `mw_qso.py:178` `on_qso_started()`, `mw_qso.py:223-242` `should_tx()`,
  `mw_cycle.py:494` `advance()`, `main_window.py:230-232` Singleton-Init,
  `main_window.py:546-548` Easter-Egg-Disable, `main_window.py:760-762`
  Statusbar-Ω-Anzeige.
- API-Brueche werden vermieden — bestehende Methoden `enable()`/`disable()`
  bleiben (intern von `stop_omni_tx`/`start`-Pfad aufgerufen) damit Tests
  stabil bleiben.

---

## 5. Nicht im Scope

- ❌ **Kein Hard-Cap-Timer** (kein 10-Min-Stop wie Auto-Hunt). OMNI ist
  passiver, keine Bot-Tarn-Anforderung.
- ❌ **Kein Aktivierungsdialog** (Direkt-Toggle, Memory `feedback_disclaimer_no_threat`).
- ❌ **Kein zusaetzlicher ANT1-Check** im OMNI-Pfad (Encoder-zentralisiert v0.75).
- ❌ **Kein Persistieren** des OMNI-Status zwischen App-Sessions.
- ❌ **Kein** Frequenz-Springen waehrend OMNI (eine feste Audiofrequenz pro Session, Plan v3.2).
- ❌ **Kein** Versatz zwischen Even- und Odd-Slot.
- ❌ **Kein** OMNI-im-Normal-Modus (nur Diversity_Standard + Diversity_Dx).
- ❌ **Kein** OMNI+Auto-Hunt-Hybrid (mutually exclusive, ein Feature gleichzeitig).
- ❌ **Kein** GitHub-Push ohne explizite Mike-Freigabe.
- ❌ **Kein** Lock fuer OMNI-State (KISS, single-operator, kein Multi-Threading-Stress).

---

## 6. Testbarkeit

### Unit-Tests (8 in `tests/test_omni_tx.py`)

```
test_initial_state_inactive          → OmniTX.active == False initial
test_enable_resets_state             → enable() setzt slot=0, block=1, count=0
test_5_slot_pattern_block1           → Block 1: [Even, Odd, RX, RX, RX]
test_5_slot_pattern_block2           → Block 2: [Odd, Even, RX, RX, RX]
test_block_switch_after_80_cycles    → Counter=80 → switch
test_block_switch_at_position_0      → _pending_switch wartet auf Pos 0
test_qso_resets_counter_keeps_block  → on_qso_started() count=0, block bleibt
test_disable_resets_state            → disable() → active=False, slot=0
```

### Integration-Tests (6 in `tests/test_omni_extended.py`)

```
test_band_change_stops_omni             → stop_omni_tx("band_change") emit
test_mode_change_stops_omni             → Diversity→Normal stoppt
test_totmann_stops_omni_when_no_qso     → 15 min, kein QSO → Stop
test_totmann_does_not_stop_during_qso   → QSO laeuft → kein Stop
test_button_visibility_per_mode         → btn_omni_cq nur in Diversity
test_mutually_exclusive_omni_autohunt   → OMNI-Klick stoppt Auto-Hunt
```

### Auto-Hunt-Erweiterung (+2 in `tests/test_auto_hunt_extended.py`)

```
test_auto_hunt_visible_only_in_diversity → btn_auto_hunt unsichtbar in Normal
test_mode_change_stops_auto_hunt          → stop_auto_hunt("mode_change") emit
```

### Mike's manuelle Verifikation (vor letztem Commit)

1. Diversity_Std waehlen → btn_omni_cq sichtbar → Klick → Ω erscheint
2. 16+ Zyklen laufen lassen → Pattern-Log enthaelt TT RRR Sequenz
3. Block-Wechsel nach 80 Zyklen im Log sichtbar
4. QSO triggern → Counter geht zurueck auf 0, Block bleibt
5. Bandwechsel waehrend OMNI → Stop in Statusbar
6. Wechsel zu Normal-Modus → Buttons rendern neu, OMNI weg
7. Totmann (15 min ohne Maus, kein QSO) → Stop
8. Easter-Egg-Test im Normal-Modus → 3 Buttons sichtbar (Override)

### Test-Run-Erwartung

- Vor v0.78: 472 gruen
- Nach v0.78: ~485-490 gruen (8 + 6 + 2 = 16 neue Tests)
- Alle bestehenden Tests bleiben stabil (keine Regressionen)

---

## Aufwands-Schaetzung (aus Schritt 0)

| Block | Code-Z. | h |
|---|---|---|
| OMNI: 8 Punkte (`omni_tx.py` + `main_window.py` + `mw_radio.py` + `control_panel.py`) | ~250 | ~2-3 |
| Auto-Hunt-Coupling | ~25 | ~0.5 |
| Tests (Unit + Integration) | ~150 | ~1-1.5 |
| Doku (HISTORY/CLAUDE/README/main.py) | ~30 | ~0.5 |
| **Gesamt** | **~455** | **~4-5** |

Geplante Aufteilung in atomare Commits: **6-8 Stueck**.

---

## Workflow-Hinweis

Diese V1 ist Eingang fuer Schritt 1b (Self-Review) → 1c (V2). V2 wird dann
mit der Rollenanweisung oben + allen referenzierten Code-Files an
DeepSeek-R1 geschickt (Schritt 2). Nach 2.5-Verifikation und V3 + Mike-OK
geht es in Implementation (Schritt 5).

**Ende V1.**
