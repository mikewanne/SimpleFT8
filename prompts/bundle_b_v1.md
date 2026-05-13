# Bundle B' — V1: RX-Panel-Spalten-Persist + QSO-Komplett-Reihenfolge

**Stand 13.05.2026 Abend, Basis v0.97.13 (P48 + 7 atomare Commits gepusht).**

Zwei voneinander unabhaengige UI-Bugs als gemeinsames Bundle — beide
hardware-frei, beide reine UI-Sachen, beide ohne Architektur-Wirkung.

## P32 — RX-Panel-Spalten-Persist

**Symptom (Mike-Wunsch 11.05. ~05:55):** Im RX-Panel kann der User per
Rechtsklick auf die Spaltenueberschrift (`UTC`, `dB`, `DT`, `Freq`,
`Land`, `km`, `Ant`, `Slot`) auswaehlen welche Spalten angezeigt werden.
Aber bei App-Restart geht die Auswahl verloren — Default ist „alle 9
Spalten sichtbar".

**Soll:** Auswahl persistieren ueber App-Restart hinweg.

**Aktueller Code-Stand:**
- `ui/rx_panel.py:17-26`: `COL_UTC=0..COL_SLOT=8`, `COL_COUNT=9`
- `ui/rx_panel.py:66`: `self._hidden_cols: set = set()` (RAM-only)
- `ui/rx_panel.py:483-512`: `_on_header_context_menu` + `_toggle_column`
  (8 toggelbare Spalten — `COL_MSG=6` ist NICHT toggelbar)
- `config/settings.py:144-147`: generische `get(key, default)` + `set(key, value)`

**Lösung (V1-Vorschlag):**
1. Neue Settings-Key `rx_panel_hidden_cols: list[int]` (Default `[]`).
2. `RxPanel.__init__` liest beim Start aus Settings + setzt
   `self._hidden_cols` + ruft `setColumnHidden(col, True)` fuer jede.
3. `_toggle_column` ruft `settings.set("rx_panel_hidden_cols",
   list(self._hidden_cols))` und `settings.save()` SOFORT (Pattern wie
   andere Persistenz: bei jeder User-Aktion sichern, kein Verlust bei
   App-Crash).
4. Defensive: bei ungueltigen Werten (Spalte > COL_COUNT, kein int,
   `COL_MSG` reingerutscht) im Load-Pfad ignorieren.

**Files:**
- `ui/rx_panel.py` (Init lesen + setzen, `_toggle_column` save)
- `config/settings.py` (Settings-Instanz an RxPanel reichen — eventuell
  ueber Konstruktor-Param, schauen wie heute injected)
- `tests/test_p32_rx_panel_persist.py` NEU

**Akzeptanzkriterien P32:**
- AK1: Spalten via Rechtsklick ausblenden → App quit/start → bleiben
  ausgeblendet.
- AK2: Erster Start ohne Settings (`rx_panel_hidden_cols` fehlt) →
  alle 9 Spalten sichtbar (Default).
- AK3: Settings hat ungueltige Werte (`[99]`, `["abc"]`) → keine Crash,
  Defaults greifen.
- AK4: `COL_MSG=6` darf nicht versteckt werden (nicht toggelbar).

---

## P33 — QSO-Komplett-Reihenfolge

**Symptom (Mike-Screenshot 11.05. ~05:55):** Im QSO-Panel erscheint
`✓ QSO mit X komplett`-Zeile NACH der naechsten `→ Sende CQ ↻N`-Zeile
statt davor:

```
03:53:30 [E] ← Empf. EC3A 73          ← Empfang 73 (QSO done)
03:54:00 [E] → Sende CQ DA1MHH ↻9     ← schon naechste OMNI-CQ
         ✓ QSO mit EC3A komplett      ← KOMMT ERST HIER (zu spaet)
03:55:00 [E] → Sende CQ DA1MHH ↻8
```

**Mike-Erwartung:**
```
03:53:30 [E] ← Empf. EC3A 73
         ✓ QSO mit EC3A komplett      ← gehoert DIREKT nach 73-Empfang
03:54:00 [E] → Sende CQ DA1MHH ↻9
03:55:00 [E] → Sende CQ DA1MHH ↻8
```

**Bug-Wurzel (verifiziert in Code):**
- `core/qso_state.py:493+` `on_message_received` empfaengt 73 in State
  WAIT_73 → setzt State auf `TX_73_COURTESY` und sendet Hoeflichkeits-73
- Erst NACH erfolgreichem Hoeflichkeits-73-Send (`on_message_sent` Z.488)
  wird `qso_confirmed.emit(self.qso)` gefeuert
- Aber: Zwischen 73-Empfang und Courtesy-73-Send liegt MINDESTENS ein
  Slot (Encoder wartet auf naechsten passenden TX-Slot). OMNI-CQ feuert
  ggf. ZUERST in einem dazwischen liegenden Slot
- Folge: `add_qso_complete` kommt einen Slot zu spaet
- Semantisch falsch: QSO ist bestaetigt sobald wir 73 empfangen — nicht
  erst wenn wir unsere Hoeflichkeits-73 raus haben

**Loesung (V1-Vorschlag):**

Variante A (bevorzugt — semantisch korrekt):
`qso_confirmed.emit` sofort beim 73-Empfang, NICHT erst nach Courtesy-Send.

```python
# core/qso_state.py — in on_message_received bei msg.is_73 + State WAIT_73:

# QSO ist semantisch BESTAETIGT durch 73-Empfang — UI sofort updaten.
self.qso_confirmed.emit(self.qso)
if not self.qso.courtesy_73_sent:
    self.qso.courtesy_73_sent = True
    tx_msg = f"{self.qso.their_call} {self.my_call} 73"
    self._set_state(QSOState.TX_73_COURTESY)
    self.tx_slot_for_partner.emit(msg)
    self.send_message.emit(tx_msg)
    # qso_confirmed bereits oben gefeuert
else:
    self._resume_cq_if_needed()

# Und in on_message_sent fuer TX_73_COURTESY (Z.483-489):
elif self.state == QSOState.TX_73_COURTESY:
    # qso_confirmed wurde bereits in on_message_received gefeuert.
    self._dbg.log("TX", "Courtesy-73 fertig -> resume_cq")
    self._resume_cq_if_needed()
```

Variante B: Slot-Zeitstempel an `add_qso_complete` + Insertion sortieren.
→ komplexer, aendert QTextEdit-Append-Logik. **Nicht empfohlen.**

**Risiken Variante A:**
- R1: Wird `qso_confirmed` von anderen Subscribern erwartet erst nach
  Courtesy-Send? (z.B. ADIF-Logger, QRZ-Worker)
- R2: WAIT_73-Timeout-Pfad (Z.317) emittet `qso_confirmed` schon einmal
  — keine Doppel-Emission garantiert?
- R3: P1.10 Courtesy-73-Logik wurde explizit so gebaut dass
  `qso_confirmed` NACH Courtesy laeuft. Geht da was kaputt?

**Akzeptanzkriterien P33:**
- AK1: Empfang von 73 in State WAIT_73 → `✓ QSO komplett` erscheint
  IM SELBEN Slot im QSO-Panel.
- AK2: Courtesy-73-Send laeuft weiter wie heute (kein Logik-Verlust).
- AK3: `qso_confirmed`-Signal feuert genau EINMAL pro QSO (kein
  Doppel-Emit, kein Doppel-ADIF, kein Doppel-Logbuch-Refresh).
- AK4: WAIT_73-Timeout-Pfad funktioniert weiter (3 Zyklen ohne 73 →
  ✓ trotzdem).
- AK5: Bestehende Tests fuer P1.10 Courtesy-73 (`test_p1_10_courtesy_73`
  + verwandte) bleiben gruen.

**Files:**
- `core/qso_state.py` (1 Block in `on_message_received` umsortiert,
  `on_message_sent` TX_73_COURTESY-Branch entschlackt)
- `tests/test_p33_qso_complete_order.py` NEU (3 Tests fuer AK1-3)
- evtl. bestehender `test_modules.py` Anpassung wenn ein Test die
  alte Reihenfolge erwartet

---

## Bundle-Strategie

**Warum gemeinsam:** beide UI-Sichtbarkeits-Fixes ohne Architektur-
Beruehrung. Werte fuer ein gemeinsames V1→V2→R1→V3 weil:
- Workflow-Overhead nur 1× (~30min Plans + 1× R1-Call)
- Field-Test sieht Mike eh beide sofort
- Atomare Commits trotzdem getrennt: 1× P32 + 1× P33 + 1× APP_VERSION
  + 1× Doku

**Was NICHT mit reingebundlt wird:**
- P49 OMNI-Pretrigger — bereits in P48 erledigt (Encoder-Pfad).
- P24 Last-RX-Mode — widerspricht Mike-Vision aus P35-Bug-F (App-Start
  IMMER 20m FT8 Normal).
- P10 PSK-Backoff-Reset — eigener Workflow (kein UI sondern Netz-Logik).
- P29 OMNI-Paritaets-Trennung — bereits in v0.97.0er-Serie erledigt
  (commit `5498f0d` 11.05.2026).

**Tests:** 1192 → ~1199 erwartet (+3 P32 + 4 P33 inkl. AK4 WAIT_73-Timeout).

**APP_VERSION:** 0.97.13 → 0.97.14 (Bugfix-Bundle, keine Features).

**Backup:** `Appsicherungen/2026-05-13_v0.97.13_vor_bundle_b/` (4 Files:
`ui/rx_panel.py`, `config/settings.py`, `core/qso_state.py`,
`ui/main_window.py` falls Settings-Injection geaendert wird).
