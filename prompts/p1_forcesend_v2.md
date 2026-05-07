# P1.FORCESEND V2 — Self-Review

**Stand:** 2026-05-06.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Plan → Code.
**Aufgabe:** V1 als „frische KI" reviewen, Lücken/Fehler korrigieren.

---

## L1 — V1 Bug-A war HALLUZINATION

V1 §1 behauptete: „btn_advance dauerhaft disabled". **Falsch.** Code-
Verifikation `ui/mw_qso.py:208-234` zeigt:

```python
def _on_state_changed(self, state: QSOState):
    ...
    self.control_panel.btn_advance.setEnabled(
        state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73)
        and not self.qso_sm.cq_mode
    )
```

Der Button **wird** state-aware enabled — nur WAIT_73 fehlt + Label
ist statisch. V1 hatte den `_on_state_changed`-Handler übersehen
(grep nach `btn_advance.setEnabled` in mw_radio.py war zu eng).

**V2-Korrektur:** Es gibt nur 2 echte Bugs, nicht 3:
- ~~Bug A: dauerhaft disabled~~ — falsch, ignorieren
- **Bug B: Label statisch** „Weiter →" (state-unabhängig)
- **Bug C: WAIT_73 fehlt** in `advance()` UND in der Enabled-Liste
  (`_on_state_changed`)

---

## L2 — V1 §4 Update-Hook ist schon da

V1 fragte „wo state→Label-Update anhängen?". Antwort steht im Code:
`_on_state_changed` (ui/mw_qso.py:208) ist der Hook. Wir erweitern
ihn um Label-Update:

```python
self.control_panel.update_advance_button(state, self.qso_sm.cq_mode,
                                          diversity_locked=...)
```

oder einfacher: `set_advance_state(state)` setzt Label, `setEnabled`
bleibt wie gehabt (separat).

**V2-Empfehlung:** **2 Methoden in `ControlPanel`**:
- `set_advance_label(state)` — setzt nur Label
- Enabled-Logik bleibt im Caller (`_on_state_changed`)

KISS: Caller weiß über cq_mode + diversity_locked, Card weiß nur über
state.

---

## L3 — V1 §5 `TX_73_COURTESY`-Reuse — verifiziert OK

V1 fragte ob neuer State `TX_73_FORCED` her muss. Code-Verifikation:

- `qso_state.py:84` `courtesy_73_sent: bool = False` — Flag existiert
- `qso_state.py:282` TX_73_COURTESY ist in der 3-Min-Timeout-Ausschluss-
  Liste — manuelles Force-73 wird also nicht silent abgebrochen
- `qso_state.py:449` State-Behandlung in `on_message_sent` läuft
  durch zu LOGGING

**V2-Entscheidung:** TX_73_COURTESY wiederverwenden. Funktional
identisch zur P1.10-Logik. Im Kommentar erwähnen dass jetzt 2 Pfade
(Auto-Hoeflichkeit + manuell-Force) den State erreichen.

---

## L4 — V1 §5 `courtesy_73_sent`-Flag MUSS gesetzt werden

Ohne Flag-Setzung beim manuellen Force-73 könnte folgende Race
entstehen:
1. Mike klickt Force-73 in WAIT_73 → 73 manuell gesendet, state →
   TX_73_COURTESY
2. Auto-Pfad in `qso_state.py:604-615` (P1.10) prüft danach erneut
   und sendet 73 nochmal weil `courtesy_73_sent == False`

**V2-Korrektur:** Im neuen WAIT_73-Branch von `advance()` muss
`self.qso.courtesy_73_sent = True` gesetzt werden. **Pflicht-Test 9:**

```python
def test_advance_wait_73_sets_courtesy_flag():
    sm.state = WAIT_73
    sm.advance()
    assert sm.qso.courtesy_73_sent is True
```

---

## L5 — V1 §5 Diversity-Lock-Override-Race

`mw_radio.py:801,1227` ruft `btn_advance.setEnabled(not locked)`
direkt — überschreibt das `_on_state_changed`-Setzen.

**Frage:** Wenn Diversity-Lock aktiv → setEnabled(False) → state
wechselt → `_on_state_changed` setzt setEnabled(True) (weil state in
WAIT_RR73) → User kann klicken trotz Lock?

Hmm, prüfen: `_diversity_measuring`-Flag wird in mw_radio.py gesetzt
und in `_on_station_clicked` etc. abgefragt. Der Button-Klick selbst
geht aber direkt durch zu `qso_sm.advance()` (mw_qso.py:182).

**V2-Empfehlung:** `_on_state_changed` muss den Diversity-Lock
zusätzlich prüfen:

```python
diversity_locked = getattr(self, "_diversity_measuring", False)
self.control_panel.btn_advance.setEnabled(
    state in (QSOState.WAIT_REPORT, QSOState.WAIT_RR73, QSOState.WAIT_73)
    and not self.qso_sm.cq_mode
    and not diversity_locked
)
```

Dann ist die Enabled-Logik an EINER Stelle, mw_radio.py-Lock ist
redundant aber harmlos.

**V2-Frage für R1:** Ist `_diversity_measuring` über self in mw_qso.py
erreichbar? Wenn nicht: Settings/State-Hook neu denken oder mw_radio.py-
Setzen behalten + `_on_state_changed` setzt nicht enabled wenn locked.

---

## L6 — V1 §3 Akzeptanzkriterien — Label-Wahl

V1 schlägt vor:
- WAIT_REPORT → "R+Report senden"
- WAIT_RR73 → "RR73 senden"
- WAIT_73 → "73 senden"

**V2-Empfehlung:** Konsistenter Stil — alle mit Verb am Ende:
- "Sende R+Report" / "Sende RR73" / "Sende 73"

ODER alle ohne Verb (kompakter, KISS):
- "R+Report" / "RR73" / "73"

Ich tendiere zu **kompakt ohne Verb** — Mike sieht direkt was gesendet
wird, der Button-Klick-Kontext ergibt das "senden" implizit. Spart
Platz neben HALT-Button.

**V2-Vorschlag final:**
- WAIT_REPORT → `"R+Report"`
- WAIT_RR73 → `"RR73"`
- WAIT_73 → `"73"`
- sonst → `"Weiter →"` (Default)

R1 darf das überstimmen wenn UX-Argument kommt.

---

## L7 — V1 fehlt: Initial-Refresh nach App-Start

`btn_advance` wird via `_on_state_changed`-Signal upgedated. Aber
beim App-Start wird kein State-Change emittiert (qso_sm startet in
IDLE direkt). Heißt: Initial-Label = was im Code-Default steht
(„Weiter →"). Das ist OK.

**V2-Klärung:** Kein Initial-Refresh nötig. Default-Label ist sowieso
"Weiter →" und Button disabled (state IDLE).

---

## L8 — V1 fehlt: Plan-V3 Compact-fest

Wie bei P1.AP-FIX und P1.ANTENNE-COLLAPSE: Plan-V3 mit konkreten
Diffs + Datei:Zeile-Range.

---

## L9 — V1 §6 Tests-Liste — Anpassung

V1 hatte 8 Tests. V2 erweitert um:

9. `test_advance_wait_73_sets_courtesy_flag` (siehe L4)
10. `test_advance_label_during_diversity_lock` — Label bleibt bei
    state, Enabled wird False

**V2-Tests-Liste final: 10.**

---

## L10 — Zusammenfassung der V2-Korrekturen für V3

1. **Bug A war Halluzination** — nur Bug B (Label statisch) + Bug C
   (WAIT_73 fehlt) bleiben.
2. **Update-Hook:** `_on_state_changed` ergänzen + neue Methode
   `ControlPanel.set_advance_label(state)`.
3. **TX_73_COURTESY-Reuse:** OK (Code-verifiziert).
4. **`courtesy_73_sent` Pflicht-Setzen** im neuen WAIT_73-Branch.
5. **Diversity-Lock + state-aware Enabled** an einer Stelle
   konsolidieren (`_on_state_changed`).
6. **Label-Stil:** kompakt ohne Verb („R+Report", „RR73", „73").
7. **Plan-V3 Compact-fest** mit allen Diffs.
8. **10 Tests** statt 8.
9. **HISTORY/HANDOFF/CLAUDE/TODO/Memory** als Pflicht-Schritt.

---

## Pruefauftraege fuer R1

1. **Bug-A-Halluzination:** V1 hatte falsch behauptet btn_advance sei
   dauerhaft disabled. Ist meine V2-Korrektur richtig (state-aware
   Enabled existiert bereits)?
2. **TX_73_COURTESY-Reuse:** Code-verifiziert OK. Du verifizierst.
3. **`courtesy_73_sent`-Flag setzen:** Doppel-Send verhindern. Ist
   das die einzige Schutzschicht oder gibt es weitere Pfade die 73
   schicken könnten?
4. **Diversity-Lock-Override:** Soll `_on_state_changed` den Lock
   zusätzlich prüfen, oder bleibt mw_radio.py Setzen erhalten?
5. **Label-Stil:** kompakt ohne Verb vs verbose mit „Sende"?
6. **TX_73_COURTESY vs neuer State `TX_73_FORCED`:** Reuse OK oder
   semantisch verwirrend?
7. **Tests-Coverage:** 10 Tests reichen?

---

**Workflow-Status:** V2 fertig. Weiter mit R1.
