# P1.BUNDLE-LOGBOOK-RST-SNR V1 — Diagnose

**Stand:** 2026-05-08.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Ausloeser:** Mike-Field-Test 08.05. — drei unabhaengige Bugs im selben
ADIF/Logbuch/Reporting-Pfad, sinnvoll als Bundle weil thematisch
verwandt und alle ohne Hardware testbar.

---

## 1. Mike-Befund

### Bug A — Logbuch-Hang beim Eintrag-Loeschen
**Mike-Zitat 08.05.:** „eintrag neben qrz.com es kommt frage eintrag x
wirklich loeschen . da dreht sich der kreis fuer bearbeiten anscheinend
endlos jetzt hat es aufgehoert"

→ Symptom: macOS-Beachball / Spinner waehrend Loesch-Operation,
keine Reaktion mehrere Sekunden, danach ist die App wieder da
(kein Crash, sondern UI-Thread-Block).

### Bug B — RST_RCVD im ADIF mit `R`-Praefix
**Diagnose 08.05. via Format-Vergleich:** SimpleFT8-ADIF schreibt
`<RST_RCVD:4>R-22` (4 Zeichen mit `R`-Praefix), QRZ-Original
(`do4mhh.398467.20260427134135.adi`) schreibt `<rst_rcvd:3>-10`
(3 Zeichen, nur Zahl mit Vorzeichen).

→ ADIF-Spec sieht fuer FT8/FT4 nur den SNR-Wert vor (z.B. `-10`,
`+05`). Der `R`-Praefix ist FT8-Protokoll-Layer („Roger, dein
Report ist X") und gehoert NICHT ins Logbuch. WSJT-X / JTDX strippen
das routinemaessig.

→ **Folge:** Mike-Bulk-Upload zu QRZ.com brach ab ca. 10.000 QSOs ein
mit Fail-Burst. Hypothese: QRZ-Validator-Strict-Mode wirft die
nicht-spec-konformen Records ab, oder die Fail-Burst-Detection von
v0.95.15 (20 fails → 60s Cooldown) schaltete bei diesen Format-Errors
auf Cooldown. Erster Bulk lief eventuell durch, Re-Upload haengt fest.

### Bug C — Report-SNR-Bias `_last_snr` statt `msg.snr` (TODO P1.8)
**Mike-Beispiel HANDOFF:** „DA1TST: wir -23, er R+19 = 42 dB Diff".
Wir senden Reports mit deutlich schlechteren dB-Werten als wir
empfangen.

→ Wurzel: `_last_snr` wird in `mw_cycle.on_message_decoded:793` per
`self.qso_sm.set_last_snr(msg.snr)` fuer JEDE decodierte Message im
Slot gesetzt — egal welche Station. Bei einem Slot mit 50 Stationen
wird das Attribut 50× ueberschrieben, die zuletzt iterierte
„gewinnt". `_process_cq_reply` (qso_state.py:214,229) baut dann den
Report aus dem ueberschriebenen Wert statt aus der spezifisch
anrufenden Station.

---

## 2. Wurzel-Lokationen (Code-Refs verifiziert 08.05.)

### Bug A — Logbuch-Hang
- **`ui/logbook_widget.py:353-386`** `_on_delete_clicked()`
  - Zeile 383: `delete_qso(rec)` — synchroner Disk-IO (Datei lesen +
    Records re-parsen + Datei umschreiben). Bei `da1mhh.410638.adi`
    = **12.8 MB** dauert das mehrere Sekunden.
  - Zeile 384: `self.refresh()` → `load_adif()` → `parse_all_adif_files`
    fuer BEIDE Dirs (`adif/` + `adif/hochgeladen/` ~ **19.5 MB**) im
    Qt-Hauptthread.
- **`log/adif.py:47-98`** `delete_qso()` — re-parsed das gesamte
  Source-File als String, schreibt es komplett neu zurueck.
- **`ui/logbook_widget.py:239-255`** `load_adif()` — re-parsed alle
  Files in beiden Verzeichnissen + populated die ganze Tabelle neu.

### Bug B — RST_RCVD R-Praefix
- **`core/qso_state.py:229`** `report = f"R{self._last_snr:+03d}"` —
  R-Praefix bewusst fuer FT8-TX (ist korrekt fuer den Send-Layer).
- **`core/qso_state.py:204,221,417,423,434,533,578`** —
  `their_snr = msg.grid_or_report` uebernimmt den Roh-String aus der
  FT8-Message (kann `R-22` oder `+05` sein, je nach Sender-Layer).
- **`ui/mw_qso.py:329`** `rst_rcvd=qso_data.their_snr or "-10"` —
  reicht den Roh-String 1:1 an `log_qso()`.
- **`log/adif.py:194-195`** `_field("RST_RCVD", str(rst_rcvd))` —
  schreibt unveraendert.

### Bug C — `_last_snr`-Race
- **`ui/mw_cycle.py:793`** `self.qso_sm.set_last_snr(msg.snr)` — wird
  in `on_message_decoded` PRO MESSAGE aufgerufen, ueberschreibt das
  State-Machine-Attribut.
- **`core/qso_state.py:214`** `report = f"{self._last_snr:+03d}"` —
  in `_process_cq_reply` (Grid-Antwort-Pfad).
- **`core/qso_state.py:229`** `report = f"R{self._last_snr:+03d}"` —
  in `_process_cq_reply` (R-Report-Pfad).

---

## 3. Loesungen (V1-Vorschlag)

### Fix A — Logbuch in-memory-Update statt Full-Reload
**Pattern:** nach `delete_qso(rec) == True` den Record direkt aus
`self._all_records` entfernen + die Tabellen-Row finden + entfernen,
KEIN `load_adif()`-Call.

**Diff-Skizze (`ui/logbook_widget.py:382-386`):**
```python
if msg.clickedButton() == btn_yes:
    if delete_qso(rec):
        # In-Memory-Update statt Full-Reload (KISS, kein Worker-Thread)
        try:
            self._all_records.remove(rec)
        except ValueError:
            pass  # Record nicht in Liste → einfach Refresh trigern
            self.refresh()
            return
        # Tabelle aktualisieren — entweder Filter-Refresh oder direkt
        self._populate_table(self._filtered_records)
        self._update_counters()
    else:
        QMessageBox.warning(self, "Fehler", "...")
```

**Begruendung KISS:** Worker-Thread-Variante (Option A) ist
overengineered fuer EINEN Loesch-Klick. In-Memory-Liste bleibt
synchron (wir wissen welcher Record geloescht wurde). Disk-IO im
`delete_qso` selbst bleibt synchron — fuer eine 12 MB-Datei sind
das ~200 ms (vertretbar), aber das volle `load_adif()` dauert
~2-5 Sekunden bei 19 MB Total-Daten.

**Optional (Option A2 als Fallback):** falls `delete_qso` selbst
zu langsam ist, koennte das in QtConcurrent verlagert werden — aber
erst nach Field-Test der reinen In-Memory-Loesung.

### Fix B — RST_RCVD ohne R-Praefix
**Pattern:** in `log/adif.py.log_qso` defensiv das fuehrende `R`
strippen falls vorhanden. Robust, KISS, keine Annahmen ueber den
Aufrufpfad.

**Diff-Skizze (`log/adif.py:182-207`):**
```python
def _strip_r_prefix(rst: str) -> str:
    """Strippt fuehrendes R-Prefix aus FT8-Reports (ADIF-Compliance)."""
    rst = str(rst).strip()
    if rst[:1].upper() == "R" and len(rst) > 1 and rst[1] in "+-":
        return rst[1:]
    return rst

# In log_qso bei den RST-Feldern:
_field("RST_SENT", _strip_r_prefix(rst_sent)),
_field("RST_RCVD", _strip_r_prefix(rst_rcvd)),
```

**Vorteile:**
- Defensiv im einzigen Schreib-Pfad
- Keine Aenderung an State-Machine (FT8-Sequence sendet weiter `R-22`)
- ADIF-Output ist QRZ/LoTW-kompatibel
- Existierende Tests in `tests/test_modules.py:1839+` lassen sich um
  R-Strip-Asserts erweitern

**Migration existierender Files:** KISS — die in `adif/hochgeladen/`
liegenden Files mit `R-22`-Format wurden ja bereits hochgeladen
(bzw. bei Re-Upload-Versuch verworfen). v0.95.15 filtert sie ohnehin
aus zukuenftigen Bulks. **Kein** Migrations-Skript noetig.

**Optional Folge-Aufgabe:** `tools/adif_fix_rst.py` als 1-shot-Helper
falls Mike die Files manuell zu QRZ neu hochladen will. P3-Prioritaet.

### Fix C — `_last_snr` durch `msg.snr` ersetzen
**Pattern:** in `_process_cq_reply` direkt `msg.snr` benutzen.
`_last_snr` bleibt als Fallback fuer Hunt-Start-Pfad (`start_qso`,
qso_state.py:268) — dort gibt es kein `msg` zur Verfuegung, der User
hat geklickt.

**Diff-Skizze (`core/qso_state.py:213-234`):**
```python
if msg.is_grid:
    snr = msg.snr  # P1.8: spezifisch der anrufenden Station, nicht _last_snr
    report = f"{snr:+03d}" if snr > -30 else "-10"
    self.qso.our_snr = report
    tx_msg = f"{msg.caller} {self.my_call} {report}"
    self._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
    self._set_state(QSOState.TX_REPORT)
    self.send_message.emit(tx_msg)
elif msg.is_report:
    self.qso.their_snr = msg.grid_or_report
    if msg.is_r_report:
        # ... unveraendert
    else:
        snr = msg.snr  # P1.8 dito
        report = f"R{snr:+03d}" if snr > -30 else "R-10"
        self.qso.our_snr = report
        tx_msg = f"{msg.caller} {self.my_call} {report}"
        ...
```

**Begruendung:** `msg.snr` ist die SNR der spezifischen anrufenden
Message. `_last_snr` wird in `on_message_decoded` per Slot vielfach
ueberschrieben — Wert von zuletzt iterierter Message gewinnt, ist
fast nie die Station mit der wir QSO machen.

`set_last_snr` BLEIBT bestehen fuer den Hunt-Start-Pfad
(`start_qso`-Aufruf bei User-Klick aus RX-Panel — dort haben wir die
SNR aus der angeklickten Message bereits separat).

---

## 4. Akzeptanzkriterien

### AC-A1 (Logbuch-Hang)
- Loeschen eines Eintrags aus 12 MB ADIF-Datei dauert < 500 ms
  (UI-Reaktion gemessen).
- Tabelle aktualisiert sich sofort, geloeschter Eintrag verschwindet.
- Counter (`_update_counters`) zeigt korrekten neuen Wert.
- Refresh-Spinner kommt nicht mehr vor.

### AC-A2 (Logbuch-Konsistenz)
- Wenn Record nicht in `_all_records` (Edge-Case durch Filter) →
  Fallback: `self.refresh()` (alter Pfad).
- Disk-File ist nach Delete korrekt geschrieben (alter Test bleibt
  gruen: `tests/test_modules.py:1864+`).

### AC-B1 (RST_RCVD ADIF-Compliance)
- Neuer SimpleFT8-Log enthaelt `<RST_RCVD:3>-22` oder
  `<RST_RCVD:3>+05` — kein `R` mehr.
- Existierende Tests in `tests/test_modules.py:1839+` werden um
  Asserts erweitert (z.B. `assert "<RST_RCVD:3>-22" in content`).

### AC-B2 (RST_SENT defensiv)
- Selbe Behandlung fuer `RST_SENT` (auch wenn aktuell kein Bug
  beobachtet — Robustheit).

### AC-C1 (P1.8 Report-SNR korrekt)
- Bei msg mit `snr=-08` → unser TX-Report `-08` (oder `R-08`),
  nicht `-22` aus `_last_snr`.
- Unit-Test: `_process_cq_reply(msg_with_snr_minus_8)` → `our_snr ==
  "-08"`.
- Test mit 2 Messages im Slot: erster setzt `_last_snr=-22`, zweiter
  hat `msg.snr=-08` → Report = `-08`.

### AC-C2 (set_last_snr bleibt verfuegbar)
- `set_last_snr` wird nicht entfernt — Hunt-Start (`start_qso`) +
  Retry-Pfade in `qso_state.py` (Z.345,360,585) nutzen weiter den
  Fallback `_last_snr`.

### AC-Tests
- 921 → erwartet ~932 (3 neue Tests fuer Logbuch-Delete-Performance,
  3 fuer R-Strip, 3 fuer P1.8 = ~9 Tests, finale Schaetzung in V3).

---

## 5. Betroffene Module

### Bug A
- `ui/logbook_widget.py:382-386` — `_on_delete_clicked` In-Memory-
  Update.
- Test: neuer `tests/test_p1_logbook_delete.py` mit Tmp-ADIF-Datei.

### Bug B
- `log/adif.py:182-207` — `_strip_r_prefix` Helper + Aufruf bei
  RST_SENT/RST_RCVD.
- Test: `tests/test_modules.py:1839+` Asserts erweitern (oder
  separater `tests/test_p1_rst_strip.py`).

### Bug C
- `core/qso_state.py:213-234` — `_process_cq_reply` `msg.snr` statt
  `_last_snr`.
- Test: neuer `tests/test_p1_8_msg_snr.py`.

### Sonstige
- `main.py:16` APP_VERSION 0.95.17 → 0.95.18 (Patch +0.01 — 3 Bugfixes).
- HISTORY.md + HANDOFF.md (beide Pfade) + CLAUDE.md (beide Pfade) +
  Memory-Update.

---

## 6. Randbedingungen / Kritische Punkte (V1-Sicht)

- **Bug-A Ueberlap mit P1.7 (lokaler Duplikat-Filter)** — beide
  beruehren `log/adif.py`. P1.7 ist NICHT Teil des Bundles, separater
  Workflow nach v0.95.18.
- **Bug-A Edge-Case mit Filter:** Wenn User gefilterte Tabelle hat
  (`_filtered_records != _all_records`), muss der Record aus BEIDEN
  Listen entfernt werden. Im Code aber `_all_records.remove(rec)`
  reicht — `_populate_table(_filtered_records)` wird nochmal
  aufgerufen und filtert frisch.
- **Bug-B Migration:** existierende Files im `adif/`-Hauptverzeichnis
  haben weiter `R-22`-Format. Beim naechsten QRZ-Bulk werden diese
  re-uploaded mit altem Format → QRZ-Reject. **Mitigation:** v0.95.18
  schreibt nur NEUE Records korrekt. Alte Records sind in
  `adif/hochgeladen/` (vom v0.95.15-File-Move) und werden NICHT
  re-uploaded. Wenn welche im Hauptordner geblieben sind: Mike kann
  sie manuell verschieben oder Helper-Script nachreichen.
- **Bug-C Fallback `_last_snr`:** muss erhalten bleiben fuer Hunt-
  Start (qso_state.py:268) und Retry-Pfade (Z.345,360,585,594,642).
  KEIN globaler Replace — nur die zwei Stellen in
  `_process_cq_reply` (Z.214,229).
- **Slot-Race:** wenn 2 Stationen uns parallel rufen (CQ-Antwort), ist
  `_process_cq_reply` schon mit `msg`-spezifisch — Bug-C-Fix loest
  das automatisch.

## 7. Nicht im Scope (P2 oder spaeter)

- **P1.7 Duplikat-Filter** — separater Workflow nach v0.95.18.
- **P1.11 rr73_retries shared** — separater Workflow.
- **P1.13 TX-Frequenz-Spinbox-Sync** — braucht Hardware-Test.
- **Migration-Helper `tools/adif_fix_rst.py`** — P3, optional.
- **Worker-Thread fuer delete_qso Disk-IO** — erst wenn In-Memory-
  Loesung sich als unzureichend erweist (Field-Test).
- **`start_qso` SNR-Pfad fuer Hunt** — User-Klick liefert keine SNR
  durch, das ist ein anderer Bug (RX-Panel-Klick muesste msg.snr
  durchreichen). Separat.

## 8. Offene Fragen fuer V2/R1

1. **Bug-A: `_filtered_records` vs `_all_records`** — wenn User Filter
   gesetzt hat (Search-Box), muss der Loeschen-Pfad sicherstellen
   dass beide Listen synchron bleiben. V2 grep-verifiziert ob es
   noch andere Listen gibt.
2. **Bug-A: Performance `delete_qso` selbst** — bei 12 MB-Datei
   ~200 ms? V2 misst per Test. Wenn > 500 ms: Worker-Thread doch
   noetig.
3. **Bug-B: Soll auch RST_SENT defensiv gestrippt werden?** — aktuell
   schreiben wir RST_SENT ohne R (kein Bug), aber Defensive macht
   Sinn fuer Konsistenz.
4. **Bug-B: Was wenn Aufrufer R+22 mit + sendet** — Edge-Case
   `_strip_r_prefix("R+22")` → `+22`. Funktioniert.
5. **Bug-B: Was wenn Wert leer/None** — Edge-Case
   `_strip_r_prefix(None)` → defensive `str()`-Cast.
6. **Bug-C: `msg.snr`-Type** — int oder str? Verifikation in V2 via
   `core/message.py`.
7. **Bug-C: `start_qso` SNR aus Klick** — RX-Panel-Klick-Pfad reicht
   `their_call/their_grid/freq_hz` weiter. SNR wird nicht uebergeben
   → bleibt `_last_snr`-Fallback. V2 prueft ob sinnvoll, sonst
   separater Bug.
8. **APP_VERSION 0.95.18** — 3 unabhaengige Bugfixes als Bundle:
   Patch +0.01 (kein Feature) reicht?

## 9. Compact-Strategie

V1 ist Diagnose. V2 wird Self-Review mit Lessons. R1 reviewt V2+V1
mit Code-Files. V3 ist Compact-fest mit allen Diffs. Erwartung Tests
921 → ~930 gruen (+9). APP_VERSION 0.95.17 → 0.95.18.

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
