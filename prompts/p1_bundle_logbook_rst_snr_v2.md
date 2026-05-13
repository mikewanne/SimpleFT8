# P1.BUNDLE-LOGBOOK-RST-SNR V2 — Self-Review von V1

**Stand:** 2026-05-08.
**Workflow:** V1 ✅ → **V2 (diese Datei)** → R1 (DeepSeek) → V3 → Compact → Code.
**Aufgabe Self-Review:** mit frischen Augen lesen — was fehlt, was ist
mehrdeutig, was hat V1 uebersehen?

---

## Lessons (L1-L15)

### L1 — KRITISCH: Bug-A-Hauptursache ist NICHT der Refresh sondern `delete_qso` selbst

V1 sagt: „In-Memory-Update statt Full-Reload, KISS reicht". Falsch.

**Code-Verifikation `log/adif.py:70-94`:**
```python
new_body = ""
i = 0
while i < len(blocks):
    block = blocks[i]
    eor = blocks[i + 1] if i + 1 < len(blocks) else ""
    ...
    if (...):
        deleted = True  # ueberspringen
    else:
        new_body += block + eor   # ⛔ String-Konkat in Loop!
```

Python-Strings sind **immutable** — jeder `+=` allokiert einen neuen
String mit Kopie aller Bytes. Bei einer 12 MB-Datei mit ~10.000
Records hat das **O(n²)**-Verhalten: ~50 Mio Operationen,
geschaetzt **5-10 Sekunden** UI-Hang.

**KORREKTUR FUER V3:** `delete_qso` muss `parts.append(block + eor)`
+ `"".join(parts)` benutzen. **DAS ist der Haupt-Hang-Fix**, nicht
das In-Memory-Update.

In-Memory-Update bringt zusaetzlich ~2 Sekunden (Refresh-Re-Parse von
beiden Verzeichnissen), ist also auch sinnvoll, aber sekundaer.

→ **Fix-A ist 2-teilig:** (1) `delete_qso` O(n²)→O(n), (2) Refresh
in-memory.

### L2 — Bug-B unvollstaendig: R-Strip muss auch im QRZ-Send-Pfad

V1 sagt: „Mig-Helper P3, neue Records ab v0.95.18 sind korrekt".
**Nicht ausreichend.**

**Code-Verifikation `log/qrz.py:54-62`:**
```python
def upload_qso_from_dict(self, record: Dict[str, str]) -> Dict[str, str]:
    adif_parts = []
    for key, value in record.items():
        if key.startswith("_"):
            continue
        adif_parts.append(f"<{key.lower()}:{len(value)}>{value}")
    adif_parts.append("<eor>")
    return self.upload_qso(" ".join(adif_parts))
```

**Aufrufpfad:** `parse_adif_file` liest existierende Files (mit
R-Format!) → `record["RST_RCVD"] = "R-22"` → `upload_qso_from_dict`
sendet `<rst_rcvd:4>R-22` an QRZ → QRZ rejected.

**Mike's Bulk-Upload-Bug ist DAMIT erst geloest.** Strippen nur beim
Schreiben (Fix in `log_qso`) hilft nicht fuer existierende QSOs in
`adif/SimpleFT8_LOG_*.adi`.

**KORREKTUR FUER V3:** `_strip_r_prefix` muss in **2 Pfaden** aufgerufen
werden:
1. `log/adif.py.log_qso` (Schreib-Pfad — neue Records korrekt)
2. `log/qrz.py.upload_qso_from_dict` (Send-Pfad — alte Records werden
   beim Upload korrigiert, ohne die Files zu modifizieren)

**Helper-Lokation:** `log/adif.py` (von beiden Pfaden importierbar).

→ Defensive Sache: korrekt schreiben UND korrekt senden. Beide Layer.

### L3 — `_filtered_records` muss bei Filter aktualisiert werden

V1 sagt: „`_populate_table(self._filtered_records)` reicht nach
Delete".

**Code-Verifikation `ui/logbook_widget.py:263, 314-327`:**
- `_populate_table(records)` setzt `self._filtered_records = records`
- `_on_filter_changed(text)` filtert frisch aus `_all_records`

**Edge-Case:** wenn User eine Such-Filter-Eingabe hat, dann ist
`_filtered_records` eine Untermenge mit dem geloeschten Record. Wenn
wir nur `_all_records.remove(rec)` machen + `_populate_table(_filtered_records)`,
ist der Record IMMER NOCH in der Tabelle (bis User Filter aendert).

**KORREKTUR FUER V3:** Nach `_all_records.remove(rec)`:
```python
# Filter neu anwenden statt _filtered_records direkt zu nutzen
self._on_filter_changed(self._search_input.text())
self._update_counters()
```

Das triggert `_populate_table(filtered)` mit aktualisierter Liste.
Counter aktualisiert sich aus `_all_records` (Z.304).

### L4 — Search-Input-Widget-Name verifizieren

V1 nutzt `self._search_input.text()` — aber Code-Name evtl. anders.
**V3-Pflicht-grep:** `search_box`, `search_input`, `_search_*` in
`ui/logbook_widget.py` — exakter Attribut-Name.

### L5 — Fix-B Helper-Test mit allen Edge-Cases

V1 nennt 3-4 Tests. Realistisch:
- `test_strip_r_minus` — `R-22 → -22`
- `test_strip_r_plus` — `R+05 → +05`
- `test_strip_no_r` — `-22 → -22` (idempotent)
- `test_strip_only_r` — `R → R` (kein Vorzeichen, nicht strippen)
- `test_strip_empty` — `"" → ""`
- `test_strip_none_safe` — `None → ""` (defensive)
- `test_strip_lowercase_r` — `r-22 → -22` (case-insensitive)
- `test_strip_R73` — kein Match (kein +/- nach R)
- **8 Tests** statt 3-4.

### L6 — `msg.snr` Type ist `int` (verifiziert)

`core/message.py:14` `snr: int = -30`. → `f"{msg.snr:+03d}"`
funktioniert direkt.

### L7 — Test fuer P1.8: Mock-Pattern aus existierenden Tests uebernehmen

Existierende Tests in `tests/test_p1_*.py` testen
`_process_cq_reply` mit `FT8Message`-Instanzen. V3 nutzt das selbe
Pattern.

**Test-Skizze:**
```python
def test_process_cq_reply_uses_msg_snr_not_last_snr():
    sm = QSOStateMachine(my_call="DA1MHH")
    sm.set_last_snr(-22)  # Vorbedingung: zuletzt -22 von anderer Station
    msg = FT8Message(raw="DA1MHH SP6AXW JO80", field1="DA1MHH",
                     field2="SP6AXW", field3="JO80", snr=-08)
    msg._tx_even = False
    sm._process_cq_reply(msg)  # is_grid → Pfad Z.213
    assert sm.qso.our_snr == "-08"  # Z.214 jetzt msg.snr
```

### L8 — Fix-A: zusaetzliches AC fuer Disk-IO-Performance

V1 hat AC-A1 ~500 ms. V2-Verfeinerung:
- AC-A1a: `delete_qso` allein < 200 ms bei 12 MB-Datei (Performance-
  Test mit Tmp-Datei mit 10.000 Records).
- AC-A1b: `_on_delete_clicked` end-to-end < 500 ms (delete + UI-
  Update).

Test-Schaetzung Bug-A: 4 Tests:
- `test_delete_qso_performance` (10K records, < 500 ms wallclock)
- `test_on_delete_in_memory_update_no_refresh` (mock refresh, assert
  not called)
- `test_on_delete_with_filter_active` (Filter gesetzt, Record geloescht
  → nicht mehr in Tabelle)
- `test_on_delete_record_not_found_fallback` (Edge-Case)

### L9 — `set_last_snr` bleibt notwendig (nicht entfernen!)

V1 sagt: „bleibt fuer Hunt-Start". Gruen.

**Verifikation Z.143-145** (`set_last_snr`) wird genutzt von:
- `_process_cq_reply` Z.214,229 → wird gefixt zu `msg.snr`
- `start_qso` Z.268 → bleibt `_last_snr` (kein msg verfuegbar)
- Retry-Pfade Z.345,360,585,594,642 → BLEIBEN `_last_snr` (Fallback
  wenn `qso.our_snr` schon gesetzt war).

→ V3-Klausel: **NUR** Z.214 + Z.229 anfassen. Alles andere bleibt.

### L10 — V1 fehlt: existierende `tests/test_modules.py:1839+` ADIF-Tests

V1 sagt „Asserts erweitern oder separater test". V2-Empfehlung:
**neuer Test-File** `tests/test_p1_bundle_logbook_rst_snr.py` —
sauber gebuendelt, alle 3 Bugs in einem File. Bestehende Tests in
test_modules.py NICHT modifizieren (Stabilitaet + klarer Audit-Trail).

### L11 — Fix-B Test fuer QRZ-Send-Pfad

`tests/test_p1_qrz_upload_ui_2.py` mockt `upload_qso_from_dict`.
Neuer Test:
```python
def test_qrz_upload_strips_r_prefix_from_old_records():
    """Records aus parse_adif_file mit R-Format werden korrigiert
    bevor sie an QRZ gesendet werden."""
    client = QRZClient("user", "pass")
    record = {"CALL": "SP6AXW", "RST_RCVD": "R-22", "RST_SENT": "-08", ...}
    # Mock urlopen, capture payload
    ...
    assert "<rst_rcvd:3>-22" in captured_payload
    assert "<rst_rcvd:4>R-22" not in captured_payload
```

### L12 — V1 fragte: „RST_SENT auch defensiv?"

**JA** — beide Felder defensiv strippen. Auch wenn aktuell kein Bug:
Konsistenz + Robustheit. Aufwand 0 (gleicher Helper). Entscheidung
final.

### L13 — V1 fragte: APP_VERSION 0.95.18

**JA** — 3 unabhaengige Bugfixes als Bundle, Patch +0.01.
v0.95.17 (UI-Feature) → v0.95.18 (Bug-Bundle).

### L14 — Bundle-Trennung sauber halten

V1 hat die 3 Bugs klar abgegrenzt. V3 muss in den Diffs explizit
sagen: Diff X gehoert zu Bug A/B/C. Im Code-Commit dann ein
ATOMARER Commit pro Bug = 3 Commits + 1 Doku-Commit.

**Alternative:** ein gemeinsamer Commit mit klarer Header-Trennung
(„Bug A:", „Bug B:", „Bug C:"). Ueblicherweise atomar = 1 Bug = 1
Commit. **V3-Empfehlung: 3 Code-Commits + 1 Doku-Commit.**

### L15 — Test-Ergaenzung: Field-Test-Pfad fuer QRZ-Bulk

V1 hat **keinen** Field-Test im AC. V2-Ergaenzung:
- AC-Field: Mike re-uploaded eine alte ADIF-Datei mit R-Format.
  Erwartung: keine Fail-Burst-Cooldowns mehr (oder zumindest weniger).
  Wenn QRZ trotzdem rejecten: anderer Bug.

→ Bundle ist nur dann komplett wenn der Field-Test bestaetigt.
Ohne Field-Test bleibt Bug-B-Wurzel-Hypothese „RST-Format ist Grund
fuer 10K-Burst" unbestaetigt. Mike-Field-Test-Pflicht in V3.

---

## Konsolidierte Empfehlung fuer V3

### Architektur-Entscheidung

- **Bug-A 2-teilig:** (1) `delete_qso` O(n²) → O(n) per `list.append` +
  `"".join`, (2) `_on_delete_clicked` In-Memory-Update statt
  `refresh()`.
- **Bug-B 2-teilig:** (1) `_strip_r_prefix` Helper in `log/adif.py`,
  (2) Aufruf in `log_qso` (Schreib-Pfad) + `qrz.upload_qso_from_dict`
  (Send-Pfad).
- **Bug-C punktuell:** `_process_cq_reply` Z.214,229 → `msg.snr`.

### Konkreter Diff-Plan fuer V3

**6 Diffs:**

1. **`log/adif.py:47-98` `delete_qso`** — String-Konkat → list.append
   + "".join. O(n²) → O(n). KRITISCH fuer Bug-A-Performance.
2. **`ui/logbook_widget.py:382-386` `_on_delete_clicked`** —
   In-Memory-Update + Filter-Re-Apply statt full `refresh()`.
3. **`log/adif.py:_strip_r_prefix` NEU + Aufruf in `log_qso`** —
   Bug-B Schreib-Pfad.
4. **`log/qrz.py.upload_qso_from_dict`** — `_strip_r_prefix` Aufruf
   bei `RST_RCVD`/`RST_SENT` vor Payload-Bau. Bug-B Send-Pfad.
5. **`core/qso_state.py:213-234` `_process_cq_reply`** — `msg.snr`
   statt `_last_snr`. Bug-C.
6. **`tests/test_p1_bundle_logbook_rst_snr.py` NEU** — alle Tests
   gebuendelt:
   - 4 Bug-A-Tests
   - 8 Bug-B-Tests (Helper-Edge-Cases)
   - 1 Bug-B-Test fuer QRZ-Send-Pfad
   - 3 Bug-C-Tests
   - **= 16 Tests** (V1 schaetzte 9, V2-Verfeinerung 16).

**+ 1 Diff main.py:**

7. **`main.py:16` APP_VERSION 0.95.17 → 0.95.18**

### Test-Schaetzung

```
Bug-A (Logbuch-Hang):
  test_delete_qso_performance_10k_records           (Tmp-File 10K, < 500ms)
  test_delete_qso_correct_record_removed            (Funktional)
  test_on_delete_in_memory_no_refresh               (Mock refresh, not called)
  test_on_delete_with_filter_record_disappears      (Filter aktiv)

Bug-B (RST R-Strip):
  test_strip_r_minus                                (R-22 → -22)
  test_strip_r_plus                                 (R+05 → +05)
  test_strip_no_r_idempotent                        (-22 → -22)
  test_strip_lowercase_r                            (r-22 → -22)
  test_strip_only_r_no_sign                         (R → R)
  test_strip_empty_string                           ("" → "")
  test_strip_none_safe                              (None → "")
  test_strip_R73_no_match                           (RR73 → RR73)
  test_log_qso_writes_rst_rcvd_without_r            (E2E in tmpfile)
  test_qrz_upload_strips_r_from_old_records         (Mock urlopen)

Bug-C (P1.8):
  test_process_cq_reply_grid_uses_msg_snr           (msg.is_grid)
  test_process_cq_reply_report_uses_msg_snr         (msg.is_report)
  test_last_snr_unchanged_after_process_cq_reply    (Init-Schutz)
```

→ **17 Tests gesamt.** Tests 921 → 938 gruen.

### Decoder-Verifikation

Nicht relevant — alle Aenderungen sind in:
- ADIF-Schreib/Lese-Layer (`log/adif.py`)
- ADIF-Logbuch-UI (`ui/logbook_widget.py`)
- QRZ-Upload-Layer (`log/qrz.py`)
- State-Machine `_process_cq_reply` (Bug C, klein abgegrenzt)

Decoder/Encoder/ft8lib unbeeinflusst.

### Gesamt-Aufwand

- 5 Code-Diffs in 4 Files (~50-80 Zeilen netto)
- 1 NEU-Test-File mit 17 Tests (~250 Zeilen)
- 1 main.py-Bump
→ **Klein bis mittel.** Risiko gering, aber Mike's QRZ-Field-Test ist
Pflicht-Bestaetigung fuer Bug-B.

### Bundle-Commit-Strategie

V3-Empfehlung **3 Code-Commits + 1 Doku-Commit:**
1. `Bug A: delete_qso O(n²) + Logbuch In-Memory-Update` — Diffs 1+2
2. `Bug B: ADIF/QRZ RST_RCVD R-Praefix-Strip` — Diffs 3+4
3. `Bug C (P1.8): _process_cq_reply nutzt msg.snr` — Diff 5
4. `docs (v0.95.18): P1.BUNDLE-LOGBOOK-RST-SNR HISTORY+HANDOFF+CLAUDE`

Plus Tests in den Code-Commits jeweils mit drin (atomar).

---

## Naechste Schritte

V2 fertig. Weiter mit R1-DeepSeek-Review von V1+V2 zusammen.

R1-Prompt-Skizze:
```
Du reviewst zwei Plans (V1 + V2) fuer das P1.BUNDLE-LOGBOOK-RST-SNR
in SimpleFT8 (3 Bugs in einem Workflow):

A) Logbuch-UI-Hang beim Eintrag-Loeschen — V2 entlarvt String-Konkat
   in Loop (O(n²)) als Hauptursache, V1 hatte nur Refresh als Wurzel.
B) RST_RCVD im ADIF mit R-Praefix — V2 erweitert auf Send-Pfad-Strip
   (sonst alte Files unbrauchbar fuer QRZ-Re-Upload).
C) _last_snr-Race in _process_cq_reply — V1 + V2 einig.

PRUEFAUFTRAG:
1. Ist O(n²) → O(n) per list.append + "".join der korrekte Fix?
   Oder gibt's eine bessere Variante (z.B. memoryview, pathlib-stream)?
2. In-Memory-Update mit Filter-Re-Apply: Race-Frei? Wenn User
   waehrend des Klicks neuen Filter eintippt?
3. _strip_r_prefix in 2 Pfaden (Schreib + Send): redundant oder
   notwendige Defense-in-Depth?
4. Bug-B-Migration: alte Files mit R-Format bleiben so. Send-Pfad-
   Strip korrigiert sie beim Upload, aber Files bleiben „falsch" auf
   Disk. Akzeptabel (KISS) oder Migration-Helper-Pflicht?
5. Bug-C: _last_snr bleibt fuer Hunt-Start (start_qso) und Retry-
   Pfade. Konsistenz-Risiko?
6. Test-Coverage 17 Tests: ausreichend? Edge-Cases uebersehen?
7. APP_VERSION 0.95.18: 3-Bugfix-Bundle als Patch oder eigene Minor?
8. Bundle-Commit-Strategie 3+1 Commits: KISS oder zu granular?
9. Performance-AC „< 500 ms": realistisch fuer 12 MB ADIF nach Fix?
10. QRZ-Format-Bug-Hypothese (10K-Burst durch R-Format): bestaetigbar
    ohne Field-Test? Oder muss Mike re-uploaden?

Antworte strukturiert mit Datei:Zeile-Referenzen.
Halte dich an SimpleFT8-Philosophie: Hobby-Tool, KISS, kein
Overengineering.
```

R1-Files mitsenden:
- `prompts/p1_bundle_logbook_rst_snr_v1.md`
- `prompts/p1_bundle_logbook_rst_snr_v2.md` (diese Datei)
- `log/adif.py` (delete_qso + log_qso)
- `log/qrz.py` (upload_qso_from_dict)
- `ui/logbook_widget.py` (_on_delete_clicked + _on_filter_changed +
  _populate_table + _update_counters)
- `core/qso_state.py` (`_process_cq_reply` Z.190-235 + `set_last_snr`
  Z.143)
- `core/message.py` (FT8Message-Dataclass)
- `ui/mw_cycle.py:780-810` (`on_message_decoded` mit set_last_snr)
- `ui/mw_qso.py:315-340` (`adif.log_qso` Aufruf)
