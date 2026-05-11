# OMNI-TX Design-Spec — VERALTET

> **⛔ VERALTET seit 11.05.2026.** Dieses Dokument beschreibt das
> **alte 5-Slot-Pattern (v0.78–v0.96.0)** das durch
> **P7.OMNI-SIMPLIFY** (v0.96.4) ersetzt wurde. Es bleibt aus
> historischen Gruenden bestehen (Design-Geschichte), spiegelt aber
> NICHT den aktuellen Code wider.
>
> **Aktuelle OMNI-Spec:**
> - User-Doku: `docs/explained/omni-tx_de.md` + `omni-tx.md`
> - Code-Spec: `core/omni_cq.py` (~250 Zeilen, Single-Slot mit
>   modus-spezifischem Down-Counter)
> - Verbindliche Memory: `project_omni_cq_spec.md`

---

## ⛓️ Historisches Konzept (NICHT MEHR GUELTIG)

**Version:** v3.2 (geplant fuer SimpleFT8 v0.78)
**Status:** Ersetzt durch P7.OMNI-SIMPLIFY (v0.96.4)
**Erstellt:** 2026-04-30 von Mike (DA1MHH) + Claude (Anthropic)
**Workflow:** V1→V2→V3 nach `docs/WORKFLOW.md` v1.1

Dieses Dokument war die **permanente Design-Spec** fuer das OMNI-TX-Feature.
Es sammelt alle Konzept-, UI-, Logik- und Argumentations-Entscheidungen
des urspruenglichen 5-Slot-Designs.

---

## 1. Konzept — Even/Odd-Slot-Asymmetrie

### Grundproblem

Bei normalem CQ rufst du immer auf einer Slot-Paritaet (Even ODER Odd).
Operatoren die im **gleichen** Slot empfangen wie du sendest hoeren dich
gar nicht — sie senden ja gerade selbst. Du erreichst pro Zyklus nur
**~50%** der aktiven Operatoren.

### Loesung: 5-Slot-Pattern

```
Position:  0    1    2    3    4
Aktion:    TX   TX   RX   RX   RX
```

- 2/5 Slots = **40% TX** (normales CQ ist 50% → OMNI sendet **20% WENIGER**)
- 3/5 Slots = 60% RX (normaler Betrieb 50%)
- Trotzdem **~20-30% mehr CQ-Antworten** durch doppelte Hoererbasis

### Block-Wechsel

| Block | Pos 0 | Pos 1 | Pos 2 | Pos 3 | Pos 4 |
|---|---|---|---|---|---|
| **Block 1** (Even-First) | TX Even | TX Odd | RX Even | RX Odd | RX Even |
| **Block 2** (Odd-First) | TX Odd | TX Even | RX Odd | RX Even | RX Odd |

Wechsel automatisch nach **80 Zyklen** (Plan v3.2 — entspricht
`settings.diversity_operate_cycles` Default).

### Hoerslot-Bilanz

```
Block 1: 3× Even gehoert | 2× Odd gehoert
Block 2: 2× Even gehoert | 3× Odd gehoert
→ Ueber beide Bloecke perfekt ausgeglichen
→ Kein Slot verloren beim Uebergang (extra RX-Slot Pos 4)
```

---

## 2. UI-Logik (Mode-gekoppelt)

### Sichtbarkeit der CQ-Buttons je nach Empfangs-Modus

| Modus | btn_cq | btn_omni_cq | btn_auto_hunt |
|---|---|---|---|
| **Normal** | ✅ sichtbar + aktiv | ❌ unsichtbar | ❌ unsichtbar |
| **Diversity_Standard** | ❌ unsichtbar | ✅ sichtbar | ✅ sichtbar |
| **Diversity_Dx** | ❌ unsichtbar | ✅ sichtbar | ✅ sichtbar |
| **Easter-Egg-Test** (Versions-Klick) | wie immer + override fuer Test | sichtbar (override) | sichtbar (override) |

**Begruendung:** OMNI und Auto-Hunt sind **„Diversity auf Steroiden"** —
Power-User-Features die das Diversity-Setup voraussetzen. Im Normal-Modus
laeuft SimpleFT8 wie WSJT-X (klassischer Funkbetrieb ohne Power-User-
Features).

**Easter-Egg ist Mike's Test-Bypass** (Klick auf Versionsnummer in der
GUI) — bleibt wegen Test-Anforderungen erhalten, ist aber **nicht
oeffentlich dokumentiert** auf GitHub.

### Mutually-exclusive Verhalten

Innerhalb des Diversity-2-Button-Layouts (`omni_cq`, `auto_hunt`) ist nur
**ein Modus zur Zeit aktivierbar**. Wird der andere geklickt waehrend einer
laeuft, stoppt der laufende automatisch.

---

## 3. Aktivierung — Direkt-Toggle

**Kein Aktivierungsdialog** (Plan v3.2 hatte einen vorgeschlagen, wurde
aber verworfen wegen Memory `feedback_disclaimer_no_threat.md` — keine
Marketing-Drohung-Texte in der UI; Hardware-Pflicht ist eh schon beim
App-Start abgefragt v0.77).

**Verhalten:**
1. Klick auf `btn_omni_cq` (sichtbar nur in Diversity)
2. → OMNI-TX wird aktiv, **Ω-Symbol** erscheint in der Statusbar
3. Erneuter Klick → OMNI-TX wird inaktiv, Ω verschwindet
4. Modus-Wechsel waehrend OMNI aktiv → automatischer Stop (siehe Stop-Bedingungen)

**Konsistenz:** Auto-Hunt verhaelt sich seit v0.75 ebenfalls als Toggle.
OMNI bekommt das gleiche Pattern.

---

## 4. Stop-Bedingungen

OMNI stoppt aus diesen Gruenden:

| Reason | Trigger | Cooldown-Verhalten |
|---|---|---|
| `manual_halt` | User klickt btn_omni_cq erneut | Sofort Stop, Ω weg |
| `band_change` | User wechselt Band | Sofort Stop, Block-State verworfen |
| `mode_change` | User wechselt von Diversity nach Normal | Sofort Stop, Buttons neu rendern |
| `totmann_expired` | 15 min keine Maus/Tastatur (ausser laufendes QSO) | Sofort Stop, kein Auto-Resume |

**Wichtig:** Im Gegensatz zu Auto-Hunt v0.75 hat OMNI **keinen Hard-Cap-Timer
(10 min)** — es laeuft bis manueller Stop oder eine der anderen Bedingungen
greift. Begruendung: OMNI ist „passiver" als Auto-Hunt (kein Decode-und-
sofort-rufen-Verhalten), keine Bot-Tarn-Anforderung.

---

## 5. QSO-Verhalten

Wenn waehrend laufendem OMNI-TX eine Antwort eingeht:

1. **`qso_state.start_qso()`** wird wie ueblich aufgerufen
2. **`omni_tx.on_qso_started()`** setzt den Block-Cycle-Counter zurueck
3. **Block bleibt unveraendert** — der gerade laufende Slot war ja erfolgreich
4. QSO laeuft im normalen Even/Odd-Rhythmus der Antwort (state-machine-driven)
5. Nach QSO-Ende laeuft das 5-Slot-Pattern weiter, Counter zaehlt wieder hoch

**Begruendung:** Wenn ein Slot gerade einen QSO ausloest, ist das ein
positives Signal — nicht den Block wechseln, dieser Slot liefert.

---

## 6. Hardware-Pflicht ANT1

Wie bei allen TX-Operationen in SimpleFT8 (siehe CLAUDE.md
Hardware-Warnung):

- **Vor jedem TX-Trigger** muss `radio.set_tx_antenna("ANT1")` verifiziert sein
- Bereits zentral abgesichert in `Encoder.transmit()` (v0.75)
- Plus alle `tune_on()`-Pfade
- App-Start-Dialog (v0.77) macht Pflicht-Acknowledgment

OMNI-TX bekommt **keinen separaten ANT1-Check** — die Encoder-Schicht
greift automatisch. Der TX-Pfad ist mode-/feature-unabhaengig abgesichert.

---

## 7. Frequenzlogik

**Feste Audiofrequenz** waehrend der gesamten OMNI-Session (Plan v3.2):

- **Startfrequenz:** Mitte des freien Bereichs aus dem CQ-Histogramm
  (bestehende `core/diversity.py` `_pick_cq_freq()`-Logik)
- **Kein Versatz** zwischen Even- und Odd-Slot
- **Kein Springen** waehrend des Blocks
- → Beobachter sehen eine Frequenz die zwischen Even und Odd wechselt
  (sieht aus wie manuelles Slot-Wechseln, ist gewollt unauffaellig)

---

## 8. Auto-Hunt + OMNI Coexistenz

| Aspekt | Auto-Hunt v0.75 | OMNI-TX v3.2 |
|---|---|---|
| Aktivierung | Toggle (btn_auto_hunt) | Toggle (btn_omni_cq) |
| Mode-Coupling | nur in Diversity (NEU mit v0.78) | nur in Diversity |
| Hard-Cap-Timer | 10 min | kein |
| Slot-Affinitaet | `_last_tx_even` Filter | gegenteilig: erzwingt Slot-Wechsel |
| Easter-Egg-Test | ja (Versions-Klick) | ja (Versions-Klick) |

**Mutually-exclusive im 2-Button-Layout:** wenn User Auto-Hunt aktiviert
waehrend OMNI laeuft → OMNI stoppt automatisch (`omni_stopped("auto_hunt_started")`?).
Same fuer umgekehrt.

→ **Klaerungspunkt fuer V1**: separater Stop-Reason oder ueber `manual_halt`?

---

## 9. Sozial-Argumentation (aus Plan v3.2)

Die fuer GitHub-Doku/README wichtigen Argumente warum OMNI-TX legitim ist:

### FT4-Analogie

FT4 wurde 2019 eingefuehrt, halbierte Zykluszeit (7.5s statt 15s) =
**doppelter Sendeanteil pro Zeiteinheit**. Niemand nennt FT4 „gierig".

OMNI-TX erreicht dasselbe Ziel (mehr QSOs), aber:
- ohne Zykluszeit zu verkuerzen
- ohne Bandbreite zu erhoehen
- ohne Sendeleistung zu erhoehen

→ **OMNI ist weniger invasiv als FT4.**

### Sendezeit-Bilanz

```
Normal Even-Betrieb (10 Slots):    5 TX + 5 RX = 50% TX
OMNI Block 1+2 (10 Slots):         4 TX + 6 RX = 40% TX
```

→ **OMNI sendet 20% weniger** als ein normaler Operator. Belastet das Band
weniger. Hoert mehr. Erreicht trotzdem mehr Stationen — pure
Effizienzsteigerung.

### „Eine Frequenz, kein Versatz"

OMNI sendet **nie zwei Slots gleichzeitig**. Slot-Wechsel ist sequenziell
(Even-Pause-Odd). Das ist dasselbe was erfahrene Operatoren manuell tun.
Zu keinem Zeitpunkt sind beide Slots gleichzeitig belegt.

---

## 10. GitHub-/Release-Status

| Aspekt | Regel |
|---|---|
| Code-Status `OMNI_TX_ENABLED` | bleibt `False` bis Feldtest abgeschlossen |
| GitHub-Doku (README) | Feature darf **erwaehnt** werden |
| GitHub-Doku Aktivierungsweg | **NICHT publik** — wie aktiviert man OMNI? Easter-Egg bleibt im PRIVAT-Block der CLAUDE.md |
| Push nach Remote | nur auf explizite Mike-Freigabe (CLAUDE.md Commits-Sektion) |

---

## 11. Test-Strategie

### Unit-Tests (`tests/test_omni_tx.py`)

| Test | Verifiziert |
|---|---|
| `test_initial_state_inactive` | OmniTX startet inactive |
| `test_enable_resets_state` | enable() setzt slot_index=0, block=1, counter=0 |
| `test_5_slot_pattern_block1` | TX-Pattern Block 1: TT RRR mit Even-First |
| `test_5_slot_pattern_block2` | TX-Pattern Block 2: TT RRR mit Odd-First |
| `test_block_switch_after_80_cycles` | nach 80 Zyklen Block 1→2 |
| `test_block_switch_at_position_0` | Switch nur an Pattern-Grenze (Pos 0) |
| `test_qso_resets_counter_keeps_block` | on_qso_started() Counter=0, Block bleibt |
| `test_disable_resets_state` | disable() → slot_index=0, active=False |

### Integration-Tests (`tests/test_omni_extended.py`)

| Test | Verifiziert |
|---|---|
| `test_band_change_stops_omni` | Bandwechsel → omni_stopped("band_change") |
| `test_mode_change_stops_omni` | Diversity→Normal stoppt OMNI |
| `test_totmann_stops_omni_when_no_qso` | 15 min Inaktivitaet → Stop |
| `test_totmann_does_not_stop_during_qso` | bei laufendem QSO kein Stop |
| `test_button_visibility_per_mode` | btn_omni_cq sichtbar nur in Diversity |
| `test_mutually_exclusive_omni_autohunt` | OMNI-Klick stoppt Auto-Hunt + umgekehrt |

### Manuelle Verifikation (Mike, vor Commit)

1. Diversity_Std → Klick btn_omni_cq → Ω-Symbol erscheint
2. 5-Slot-Pattern via Logging verifizieren (16+ Zyklen Logs)
3. Block-Wechsel nach 80 Zyklen → im Log sichtbar
4. QSO testen → Block bleibt, Counter reset
5. Bandwechsel waehrend OMNI → Stop in Status
6. Mode-Wechsel zu Normal → Buttons rendern neu, OMNI weg
7. Totmann-Test (15 min ohne Maus, kein QSO) → Stop

---

## 12. Workflow-Trail

Diese Design-Spec wird via WORKFLOW v1.1 in Code uebertragen:

| Schritt | Output |
|---|---|
| Schritt 0 — Code-Verifikation | direkt naechster Schritt |
| Schritt 1a — V1 schreiben | `prompts/omni_v1.md` |
| Schritt 1b/c — Self-Review → V2 | `prompts/omni_v2.md` |
| Schritt 2 — DeepSeek-R1-Review | R1-Findings strukturiert |
| Schritt 2.5 — R1-Findings verifizieren | Halluzinationen rausfiltern |
| Schritt 3 — V3 schreiben | `prompts/omni_v3.md` |
| Schritt 4 — Mike-Freigabe | explizites OK |
| Schritt 5 — Implementation | atomare Commits |
| Schritt 5b — Final-R1-Codereview | letzter Sicherheits-Check |
| Schritt 6 — Lessons-Learned | Memory-Updates falls noetig |

Bei Abschluss: HISTORY-Eintrag, APP_VERSION-Bump (v0.77 → v0.78), CLAUDE.md
Header-Update.

---

## 13. Bekannte Edge-Cases (zu klaeren in V1/V2/V3)

| # | Edge-Case | Loesungs-Strategie |
|---|---|---|
| E1 | Bandwechsel mitten in TX-Slot Pos 1 | TX-Slot wird zu Ende gefahren, dann Stop (Encoder-Schutz) |
| E2 | Mode-Wechsel mitten in Block 1 Pos 1 | Sofortiger Stop, kein Voll-Slot |
| E3 | QSO-Antwort waehrend pending Block-Switch | QSO hat Vorrang, Block-Switch wird verworfen, Counter reset |
| E4 | App-Restart waehrend OMNI aktiv | OMNI startet immer inactive (kein State-Persist), Mike muss neu klicken |
| E5 | Easter-Egg-Toggle waehrend OMNI laeuft | Buttons bleiben sichtbar, kein Stop |
| E6 | Mode-Wechsel Diversity_Std ↔ Diversity_Dx | OMNI laeuft weiter (beide sind Diversity-Modi) |
| E7 | btn_auto_hunt + btn_omni_cq beide gleichzeitig sichtbar — User klickt schnell beide | mutually-exclusive Logik: spaeterer Klick gewinnt, frueheres Feature stoppt |

---

## Anhang A — Plan v3.2 (Original-Konzept von Mike, 2026-04-29)

```
OMNI-TX Plan v3.2 — FINAL
Codename: OMNI-TX | Automatische Slot-Rotation

Ziel:
CQ auf Even UND Odd senden um 100% aller aktiven Operatoren
zu erreichen statt nur 50%. Eine feste Audiofrequenz.
Kein Frequenzversatz. Kein Chaos. Versteckt in der GUI.

5-Slot-Muster:
Block 1 (Even-First, 80 Zyklen):
  Even SENDEN
  Odd  SENDEN
  Even HOEREN
  Odd  HOEREN
  Even HOEREN  ← extra Slot

Block 2 (Odd-First, 80 Zyklen):
  Odd  SENDEN
  Even SENDEN
  Odd  HOEREN
  Even HOEREN
  Odd  HOEREN  ← extra Slot

Wechselzaehler:
- App-Start → Block 1, erster freier Slot
- Nach 80 Zyklen → Block wechseln
- QSO kommt zustande → Wechselzaehler RESET, aktueller Block bleibt
- QSO fertig → Zaehler laeuft weiter im aktuellen Block
- Max 80 Zyklen → Block wechseln

Easter-Egg-Aktivierung:
- Klick auf Versionsnummer unten links
- Aktivierungsdialog [Aktivieren] [Abbrechen]
  → ENTFERNT in finaler Spec — wird Direkt-Toggle (siehe Sektion 3)
- Bei Aktivierung: Ω-Symbol sichtbar
- Bei Deaktivierung: unsichtbar

Realistischer Gewinn:
Belegte Baender:    20-30% mehr CQ-Antworten
Leere Baender:      10-20% mehr

Soziale Einschaetzung:
Technisch:        Sauber. Gleiche Sendezeit. Eine Frequenz.
Sozial:           Akzeptabel. Erfahrene Ops machen das manuell.
Erkennbarkeit:    Sehr gering.
Regelkonformitaet: 100%.

Autorenschaft:
Konzept entwickelt von DA1MHH (Mike) und Claude (Anthropic).
Beide Namen werden bei Veroeffentlichung genannt.
MIT Lizenz — Open Source fuer alle.
```

---

## Anhang B — Aenderungen ggue. Plan v3.2

| Punkt | Plan v3.2 | Finale Spec | Begruendung |
|---|---|---|---|
| Aktivierung | Aktivierungsdialog | Direkt-Toggle | Memory `feedback_disclaimer_no_threat`, Konsistenz mit Auto-Hunt |
| Easter-Egg | primaere Aktivierung | Test-Bypass nur fuer Mike | UX-Logik mode-gekoppelt: btn_omni_cq direkt sichtbar in Diversity |
| Auto-Hunt-Coupling | nicht erwaehnt | wird auch Diversity-only | Konsistenz mit OMNI-Strategie, „Power-User in Diversity" |
| `block_cycles` Default | 80 (Plan-Text) | 80 (final) — aktueller Code hat 40, wird angepasst | Plan v3.2 ist Wahrheit |
| Stop-Bedingungen | nicht detailliert | 4 Reasons: manual_halt, band_change, mode_change, totmann_expired | klar definiert fuer V1 |

---

## Workflow-Verweis

Implementation folgt dem **WORKFLOW.md v1.1** Pflicht-Pfad. Code-Aenderungen
gehen ueber V1 → V2 → DeepSeek-R1 → V3 → Mike-Freigabe. Diese Design-Spec
ist das Eingangsdokument fuer V1 — V1 zitiert konkret die Sektionen 1-13
mit Datei:Zeile-Verweisen.

---

## 14. Schritt-0-Code-Verifikation (2026-04-30)

**Wichtigste Erkenntnis:** OMNI-TX ist bereits zu **~70% verkabelt** im
Codebase (vermutlich von einer frueheren Implementation v0.50-v0.60). Die
Logik-Schicht in `core/omni_tx.py` ist komplett vorhanden, und die
Integrations-Hooks sind groesstenteils implementiert.

### Bereits verkabelte Hooks (verifiziert)

| Hook | Datei:Zeile | Was es tut |
|---|---|---|
| OmniTX-Singleton-Init | `ui/main_window.py:230-232` | `from core import omni_tx; self._omni_tx = _omni.get_instance(block_cycles=_block_cycles)` |
| `should_tx()` + `tx_even` setzen | `ui/mw_qso.py:223-242` | Pro CQ-Send-Trigger: should_tx() → bei RX-Slot return ohne TX, bei TX-Slot Encoder-Paritaet setzen |
| `on_qso_started()` | `ui/mw_qso.py:178` | Counter-Reset bei QSO-Start |
| `advance(qso_active)` pro Cycle | `ui/mw_cycle.py:494` | Slot-Index inkrementieren, Block-Wechsel ggf. ausloesen |
| Easter-Egg-Disable | `ui/main_window.py:546-548` | `if self._omni_tx.active: self._omni_tx.disable(); self.control_panel.update_omni_tx(False)` |
| Statusbar-Anzeige Ω + Counter | `ui/main_window.py:760-762` | `f"  Ω Even={self._omni_tx.cq_even_count} Odd={self._omni_tx.cq_odd_count}"` |
| `control_panel.update_omni_tx(False)` | UI-Update-Methode | bestehend |
| 3-Button-Layout `btn_cq` / `btn_omni_cq` / `btn_auto_hunt` | `ui/control_panel.py:774-802` | QButtonGroup mutually exclusive |

### Was fehlt fuer v0.78 (8 Punkte)

| # | Lücke | Datei | Aufwand |
|---|---|---|---|
| 1 | `btn_omni_cq.clicked` Handler `_on_btn_omni_cq_toggled` | `ui/main_window.py` (analog `:255` Auto-Hunt) | ~10 Z. |
| 2 | OmniTX → QObject mit `omni_stopped(reason)` Signal | `core/omni_tx.py` | ~15 Z. |
| 3 | Zentralisierte `stop_omni_tx(reason)` Methode | `core/omni_tx.py` | ~20 Z. |
| 4 | Mode-Coupling (Buttons mode-abhaengig statt Easter-Egg-only) | `ui/main_window.py` `_on_easter_egg_toggle` + `_on_mode_changed` umbauen | ~30 Z. |
| 5 | Stop bei `band_change` | `ui/mw_radio.py:259` `_on_band_changed` (analog Auto-Hunt `:297-299`) | ~5 Z. |
| 6 | Stop bei `mode_change` | `ui/mw_radio.py:195` `_on_mode_changed` (analog Auto-Hunt `:197-198`) | ~3 Z. |
| 7 | Stop bei `totmann_expired` (ausser laufendes QSO) | `ui/main_window.py:836-849` `_on_presence_tick` (analog Auto-Hunt) | ~5 Z. |
| 8 | `block_cycles` Default 40 → 80 (Plan v3.2) | `core/omni_tx.py:54` | 1 Z. |

### Zusatz-Aufgabe — Auto-Hunt mode-coupled (Plan v0.78)

Auto-Hunt war bisher Easter-Egg-only (sichtbar nach Versions-Klick, modus-
agnostisch). Wird in v0.78 ebenfalls Diversity-only Feature:

| Lücke | Datei | Aufwand |
|---|---|---|
| Auto-Hunt-Buttons mode-coupled (sichtbar nur in Diversity) | `ui/main_window.py` `_on_mode_changed` | ~20 Z. |
| Easter-Egg = Test-Override fuer Mike behalten | `ui/main_window.py` `_on_easter_egg_toggle` | ~5 Z. |

### Geschaetzter Gesamtaufwand

| Block | Code-Zeilen | Aufwand |
|---|---|---|
| OMNI-Implementation (8 Punkte) | ~250 | ~2-3 h |
| Auto-Hunt-Coupling | ~25 | ~30 min |
| Tests (Unit + Integration) | ~150 | ~1-1.5 h |
| **Gesamt** | **~425** | **~4-5 h** |

→ **Deutlich kleiner als v0.75 Auto-Hunt-Implementation** (10 Commits, ~600
Zeilen) weil OMNI-Logik-Schicht schon da ist.

### Erkannte Risiko-Pfade fuer V1/V2/V3

1. **Easter-Egg-Logik bestehend** (`main_window.py:530-557`) — wird
   umstrukturiert. Mike testet weiterhin via Versions-Klick.
2. **`_on_mode_changed` in `mw_radio.py:195`** und **`mw_radio.py:_on_mode_changed`
   in `main_window.py`** — vermutlich zwei separate Handler die koordiniert
   werden muessen.
3. **Race-Conditions:** Bandwechsel mid-Pos1, Mode-Wechsel mid-Block,
   QSO mid-Pending-Switch — alle in Sektion 13 als Edge-Cases dokumentiert.
4. **Test-Strategie:** OmniTX als QObject braucht QApplication-Fixture
   (analog `tests/test_auto_hunt_extended.py`).

### Stand am Ende von Schritt 0

✅ Alle relevanten Files gelesen + verifiziert
✅ Existing-Strukturen identifiziert (70% schon da)
✅ Luecken-Liste mit Datei:Zeile-Verweisen
✅ Aufwand-Schaetzung realistisch
✅ Risiko-Pfade benannt
✅ Memory-Lessons (R1-Files-Attachment, Disclaimer-Ton, QMessageBox-vs-QDialog) im Hinterkopf

→ **Bereit fuer Schritt 1a (V1 schreiben).**
