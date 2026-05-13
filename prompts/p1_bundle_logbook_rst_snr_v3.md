# P1.BUNDLE-LOGBOOK-RST-SNR V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-08.
**Workflow:** V1 → V2 → R1 ✅ („Plan kann freigegeben werden", 0 KRITISCH,
1 Vorbehalt = QRZ-Field-Test-Bestaetigung) → **V3** → Compact → Code.
**Vorgaenger:** v0.95.17 (P1.COLLAPSE-RADIO-MODEBAND). Tests 921 gruen.
**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings (alle adressiert)

| Finding | Status |
|---|---|
| O(n²)→O(n) per list.append + "".join | ✅ KISS, < 200 ms |
| In-Memory-Update + Filter-Re-Apply Race-frei (Qt Single-Thread) | ✅ V2 L3 |
| _strip_r_prefix in 2 Pfaden — Defense-in-Depth | ✅ Notwendig (Send + Schreib) |
| Migration alter Files — KISS, P3 optional | ✅ Send-Strip korrigiert beim Upload |
| _last_snr bleibt fuer Hunt + Retry, Risiko bekannt | ✅ Nur Z.214+229 anfassen |
| 17 Tests reichen | ✅ Ausreichend |
| APP_VERSION 0.95.18 Patch | ✅ |
| Bundle-Strategie 3 Code-Commits + 1 Doku | ✅ Ideale Granularitaet |
| Performance < 500 ms realistisch | ✅ Konservativ |
| QRZ-Field-Test Pflicht nach Push | ⚠️ Mike-Pflicht im Field-Test |

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `log/adif.py:70-94` `delete_qso` O(n²) → O(n)

**Aktuell (Z.69-94):**
```python
    # blocks: [block0, "<EOR>", block1, "<EOR>", ...]
    new_body = ""
    i = 0
    deleted = False
    while i < len(blocks):
        block = blocks[i]
        eor = blocks[i + 1] if i + 1 < len(blocks) else ""
        i += 2

        if not block.strip():
            continue

        # Record aus Block parsen
        rec = {}
        for m in _FIELD_RE.finditer(block):
            name = m.group(1).upper()
            length = int(m.group(2))
            rec[name] = block[m.end():m.end() + length].strip()

        if (not deleted
                and rec.get("CALL") == match_call
                and rec.get("QSO_DATE") == match_date
                and rec.get("TIME_ON") == match_time):
            deleted = True  # diesen Record ueberspringen
        else:
            new_body += block + eor
```

**Neu:**
```python
    # blocks: [block0, "<EOR>", block1, "<EOR>", ...]
    # P1.BUNDLE Bug-A (v0.95.18): list.append + "".join statt += in Loop
    # → O(n²) → O(n). Bei 12 MB ADIF mit 10K Records: 5-10 s → < 200 ms.
    new_parts = []
    i = 0
    deleted = False
    while i < len(blocks):
        block = blocks[i]
        eor = blocks[i + 1] if i + 1 < len(blocks) else ""
        i += 2

        if not block.strip():
            continue

        # Record aus Block parsen
        rec = {}
        for m in _FIELD_RE.finditer(block):
            name = m.group(1).upper()
            length = int(m.group(2))
            rec[name] = block[m.end():m.end() + length].strip()

        if (not deleted
                and rec.get("CALL") == match_call
                and rec.get("QSO_DATE") == match_date
                and rec.get("TIME_ON") == match_time):
            deleted = True  # diesen Record ueberspringen
        else:
            new_parts.append(block + eor)

    if deleted:
        path.write_text(header + "".join(new_parts))
    return deleted
```

**Aenderung minimal:** `new_body = ""` → `new_parts = []`,
`new_body += block + eor` → `new_parts.append(block + eor)`,
`path.write_text(header + new_body)` → `path.write_text(header + "".join(new_parts))`.

### Diff 2 — `ui/logbook_widget.py:382-386` In-Memory-Update

**Aktuell:**
```python
        if msg.clickedButton() == btn_yes:
            if delete_qso(rec):
                self.refresh()
            else:
                QMessageBox.warning(self, "Fehler", "Eintrag konnte nicht gelöscht werden.")
```

**Neu:**
```python
        if msg.clickedButton() == btn_yes:
            if delete_qso(rec):
                # P1.BUNDLE Bug-A (v0.95.18): In-Memory-Update statt
                # full refresh() — vermeidet Re-Parse beider Verzeichnisse
                # (~19 MB Disk-IO im UI-Thread). Filter-Re-Apply laeuft
                # frisch aus aktualisiertem _all_records (Qt-Events
                # serialisiert → keine Race).
                try:
                    self._all_records.remove(rec)
                except ValueError:
                    # Edge-Case: Record nicht in Liste → Fallback auf
                    # full refresh damit Tabelle konsistent bleibt
                    self.refresh()
                    return
                self._on_filter_changed(self.search_input.text())
                self._update_counters()
            else:
                QMessageBox.warning(self, "Fehler", "Eintrag konnte nicht gelöscht werden.")
```

**Begruendung:** `_on_filter_changed` ruft intern `_populate_table(filtered)`
mit aktualisierter `_all_records`-Liste auf. Counter zaehlt aus
`_all_records` (Z.304). Beide Listen sind synchron.

### Diff 3 — `log/adif.py` `_strip_r_prefix` Helper + Aufruf in `log_qso`

**NEU vor `_field` (Z.17):**
```python
def _strip_r_prefix(rst: str | None) -> str:
    """Strippt fuehrendes R-Praefix aus FT8-Reports (ADIF-Compliance).

    P1.BUNDLE Bug-B (v0.95.18): FT8-Sequence-Layer schreibt bei der
    Antwort `R{snr:+03d}` (z.B. „R-22" = „Roger, dein Report ist -22").
    Im ADIF-Logbuch ist das jedoch nicht spec-konform — RST_RCVD bei
    digitalen Modi soll nur das SNR enthalten (z.B. „-22", „+05").
    QRZ.com-Validator wirft R-Prefix-Records raus → Bulk-Upload-Burst.

    Idempotent: ohne R-Prefix oder nicht-FT8-Format unveraendert.
    """
    if not rst:
        return ""
    rst = str(rst).strip()
    if len(rst) >= 2 and rst[0].upper() == "R" and rst[1] in "+-":
        return rst[1:]
    return rst
```

**Aufruf in `log_qso` (Z.182-207, RST-Felder):**

Aktuell:
```python
            _field("RST_SENT", str(rst_sent)),
            _field("RST_RCVD", str(rst_rcvd)),
```

Neu:
```python
            _field("RST_SENT", _strip_r_prefix(rst_sent)),
            _field("RST_RCVD", _strip_r_prefix(rst_rcvd)),
```

### Diff 4 — `log/qrz.py:54-62` Send-Pfad-Strip

**Aktuell:**
```python
    def upload_qso_from_dict(self, record: Dict[str, str]) -> Dict[str, str]:
        """QSO-Dict (aus ADIF-Parser) an QRZ.com senden."""
        adif_parts = []
        for key, value in record.items():
            if key.startswith("_"):
                continue  # Skip interne Felder
            adif_parts.append(f"<{key.lower()}:{len(value)}>{value}")
        adif_parts.append("<eor>")
        return self.upload_qso(" ".join(adif_parts))
```

**Neu:**
```python
    def upload_qso_from_dict(self, record: Dict[str, str]) -> Dict[str, str]:
        """QSO-Dict (aus ADIF-Parser) an QRZ.com senden.

        P1.BUNDLE Bug-B (v0.95.18): RST_RCVD/RST_SENT defensiv vom
        FT8-Roger-Praefix (`R-22` → `-22`) befreien, damit alte
        SimpleFT8-ADIF-Files (vor v0.95.18 mit R-Format geschrieben)
        beim Re-Upload nicht von QRZ-Validator zurueckgewiesen werden.
        """
        from log.adif import _strip_r_prefix  # lazy: vermeidet Zirkel-Import-Risiko
        adif_parts = []
        for key, value in record.items():
            if key.startswith("_"):
                continue  # Skip interne Felder
            # Bug-B: RST-Felder defensiv strippen
            if key.upper() in ("RST_RCVD", "RST_SENT"):
                value = _strip_r_prefix(value)
            adif_parts.append(f"<{key.lower()}:{len(value)}>{value}")
        adif_parts.append("<eor>")
        return self.upload_qso(" ".join(adif_parts))
```

### Diff 5 — `core/qso_state.py:213-234` `_process_cq_reply` `msg.snr`

**Aktuell (Z.213-234):**
```python
        if msg.is_grid:
            report = f"{self._last_snr:+03d}" if self._last_snr > -30 else "-10"
            self.qso.our_snr = report
            tx_msg = f"{msg.caller} {self.my_call} {report}"
            self._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={self._last_snr})")
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(tx_msg)
        elif msg.is_report:
            self.qso.their_snr = msg.grid_or_report
            if msg.is_r_report:
                # R-prefix = sie haben uns schon bestätigt → RR73 senden (kein Report mehr!)
                tx_msg = f"{msg.caller} {self.my_call} RR73"
                print(f"[QSO] Antworte {msg.caller} mit RR73 (R-Report erhalten)")
                self._set_state(QSOState.TX_RR73)
                self.send_message.emit(tx_msg)
            else:
                report = f"R{self._last_snr:+03d}" if self._last_snr > -30 else "R-10"
                self.qso.our_snr = report
                tx_msg = f"{msg.caller} {self.my_call} {report}"
                print(f"[QSO] Antworte {msg.caller} mit R-Report '{tx_msg}'")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)
```

**Neu:**
```python
        if msg.is_grid:
            # P1.BUNDLE Bug-C / P1.8 (v0.95.18): msg.snr ist der SNR
            # der spezifischen anrufenden Station. _last_snr wuerde
            # vom letzten on_message_decoded-Aufruf im Slot ueberschrieben
            # (kann andere Station sein) → falscher Report.
            snr = msg.snr
            report = f"{snr:+03d}" if snr > -30 else "-10"
            self.qso.our_snr = report
            tx_msg = f"{msg.caller} {self.my_call} {report}"
            self._dbg.log("TX", f"Sende Report: '{tx_msg}' (SNR={snr})")
            self._set_state(QSOState.TX_REPORT)
            self.send_message.emit(tx_msg)
        elif msg.is_report:
            self.qso.their_snr = msg.grid_or_report
            if msg.is_r_report:
                # R-prefix = sie haben uns schon bestätigt → RR73 senden (kein Report mehr!)
                tx_msg = f"{msg.caller} {self.my_call} RR73"
                print(f"[QSO] Antworte {msg.caller} mit RR73 (R-Report erhalten)")
                self._set_state(QSOState.TX_RR73)
                self.send_message.emit(tx_msg)
            else:
                # P1.BUNDLE Bug-C / P1.8 (v0.95.18): siehe oben — msg.snr.
                snr = msg.snr
                report = f"R{snr:+03d}" if snr > -30 else "R-10"
                self.qso.our_snr = report
                tx_msg = f"{msg.caller} {self.my_call} {report}"
                print(f"[QSO] Antworte {msg.caller} mit R-Report '{tx_msg}'")
                self._set_state(QSOState.TX_REPORT)
                self.send_message.emit(tx_msg)
```

**WICHTIG:** Z.268 in `start_qso` (Hunt-Pfad) bleibt unveraendert
mit `_last_snr` (kein msg verfuegbar). Z.345,360,585,594,642
(Retry-Pfade) bleiben unveraendert (Fallback-Pfad).

### Diff 6 — `tests/test_p1_bundle_logbook_rst_snr.py` (NEU)

```python
"""Tests fuer P1.BUNDLE-LOGBOOK-RST-SNR (v0.95.18).

Bundle aus 3 unabhaengigen Bugs im selben ADIF/Logbuch/Reporting-Pfad:
- Bug A: Logbuch-UI-Hang beim Eintrag-Loeschen (delete_qso O(n²))
- Bug B: RST_RCVD/RST_SENT mit FT8-R-Praefix in ADIF (QRZ-Reject)
- Bug C/P1.8: _process_cq_reply nutzt _last_snr statt msg.snr
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from log.adif import (
    _strip_r_prefix,
    delete_qso,
    parse_adif_file,
    AdifWriter,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ── Bug A: Logbuch-Hang Tests ─────────────────────────────────────────────


def _write_test_adif(path: Path, n_records: int) -> None:
    """Schreibt Tmp-ADIF mit n Records (CALL=Cxxxxx, QSO_DATE=20260101)."""
    parts = ["SimpleFT8 ADIF Export\n",
             "<ADIF_VER:5>3.1.7\n<PROGRAMID:9>SimpleFT8\n<EOH>\n"]
    for i in range(n_records):
        parts.append(
            f"<CALL:7>C{i:06d} <QSO_DATE:8>20260101 <TIME_ON:6>"
            f"{i % 240000:06d} <BAND:3>20M <MODE:3>FT8 <RST_SENT:3>-10 "
            f"<RST_RCVD:3>-08 <EOR>\n"
        )
    path.write_text("".join(parts))


def test_delete_qso_performance_10k_records(tmp_path):
    """Bug-A: delete_qso < 500 ms bei 10K Records (was vorher 5-10 s)."""
    f = tmp_path / "perf_test.adi"
    _write_test_adif(f, 10000)
    records = parse_adif_file(f)
    target = next(r for r in records if r["CALL"] == "C005000")
    start = time.perf_counter()
    assert delete_qso(target) is True
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"delete_qso brauchte {elapsed:.2f}s, soll < 0.5s"


def test_delete_qso_correct_record_removed(tmp_path):
    """Bug-A: nach delete_qso ist genau der Ziel-Record weg."""
    f = tmp_path / "test.adi"
    _write_test_adif(f, 100)
    records = parse_adif_file(f)
    target = next(r for r in records if r["CALL"] == "C000050")
    assert delete_qso(target) is True
    new_records = parse_adif_file(f)
    assert len(new_records) == 99
    assert all(r["CALL"] != "C000050" for r in new_records)


def test_on_delete_in_memory_update_no_full_refresh(app, tmp_path):
    """Bug-A: _on_delete_clicked entfernt Record aus _all_records ohne
    full reload."""
    from ui.logbook_widget import LogbookWidget
    f = tmp_path / "test.adi"
    _write_test_adif(f, 50)
    widget = LogbookWidget()
    widget.load_adif(tmp_path)
    initial_count = len(widget._all_records)
    rec = widget._all_records[0]
    # delete + update emulieren (ohne MessageBox)
    assert delete_qso(rec) is True
    widget._all_records.remove(rec)
    widget._on_filter_changed(widget.search_input.text())
    widget._update_counters()
    assert len(widget._all_records) == initial_count - 1


def test_on_delete_with_filter_record_disappears(app, tmp_path):
    """Bug-A: bei aktivem Filter verschwindet geloeschter Record sofort."""
    from ui.logbook_widget import LogbookWidget
    f = tmp_path / "test.adi"
    _write_test_adif(f, 50)
    widget = LogbookWidget()
    widget.load_adif(tmp_path)
    widget.search_input.setText("C00001")  # filtert auf Records mit C00001*
    rec = next(r for r in widget._all_records if r["CALL"] == "C000010")
    assert delete_qso(rec) is True
    widget._all_records.remove(rec)
    widget._on_filter_changed(widget.search_input.text())
    # Tabelle darf den Record nicht mehr enthalten
    assert all(r.get("CALL") != "C000010" for r in widget._filtered_records)


# ── Bug B: RST R-Strip Tests ──────────────────────────────────────────────


def test_strip_r_minus():
    assert _strip_r_prefix("R-22") == "-22"


def test_strip_r_plus():
    assert _strip_r_prefix("R+05") == "+05"


def test_strip_no_r_idempotent():
    assert _strip_r_prefix("-22") == "-22"
    assert _strip_r_prefix("+05") == "+05"


def test_strip_lowercase_r():
    assert _strip_r_prefix("r-22") == "-22"


def test_strip_only_r_no_sign():
    """R ohne Vorzeichen-Folge soll bleiben (z.B. RR73-Edge)."""
    assert _strip_r_prefix("R") == "R"
    assert _strip_r_prefix("RR73") == "RR73"


def test_strip_empty_string():
    assert _strip_r_prefix("") == ""


def test_strip_none_safe():
    assert _strip_r_prefix(None) == ""


def test_log_qso_writes_rst_rcvd_without_r(tmp_path):
    """Bug-B E2E: log_qso schreibt RST_RCVD ohne R-Praefix."""
    writer = AdifWriter(tmp_path)
    path = writer.log_qso(
        call="SP6AXW", band="20M", freq_mhz=14.074, mode="FT8",
        rst_sent="-08", rst_rcvd="R-22",  # Eingang mit R
        gridsquare="JO80", my_gridsquare="JO31",
        my_callsign="DA1MHH", tx_power=100,
        time_on=1715000000.0,
    )
    content = path.read_text()
    assert "<RST_RCVD:3>-22" in content
    assert "<RST_RCVD:4>R-22" not in content


def test_qrz_upload_strips_r_from_old_records():
    """Bug-B: QRZ-Send-Pfad strippt R-Praefix aus alten ADIF-Records."""
    from log.qrz import QRZClient
    client = QRZClient("user", "pass")
    record = {
        "CALL": "SP6AXW", "QSO_DATE": "20260101", "TIME_ON": "120000",
        "BAND": "20M", "MODE": "FT8", "RST_SENT": "-08", "RST_RCVD": "R-22",
    }
    captured = {}

    def fake_upload_qso(adif_str):
        captured["adif"] = adif_str
        return {"RESULT": "OK"}

    with patch.object(client, "upload_qso", side_effect=fake_upload_qso):
        client.upload_qso_from_dict(record)
    payload = captured["adif"]
    assert "<rst_rcvd:3>-22" in payload
    assert "<rst_rcvd:4>R-22" not in payload


# ── Bug C / P1.8: msg.snr im _process_cq_reply ──────────────────────────


def _make_msg(field1, field2, field3, snr, raw=None):
    """Helper: minimale FT8Message mit msg.snr."""
    from core.message import FT8Message
    return FT8Message(
        raw=raw or f"{field1} {field2} {field3}",
        field1=field1, field2=field2, field3=field3, snr=snr,
    )


def test_process_cq_reply_grid_uses_msg_snr_not_last_snr():
    """Bug-C: bei msg.is_grid wird msg.snr fuer Report genutzt, nicht
    _last_snr (der vom letzten Slot ueberschrieben sein kann)."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH")
    sm.set_last_snr(-22)  # Vorbedingung: andere Station, fuer Report ignoriert
    msg = _make_msg("DA1MHH", "SP6AXW", "JO80", snr=-8)
    sm._process_cq_reply(msg)
    # Report aus msg.snr, nicht aus _last_snr=-22
    assert sm.qso.our_snr == "-08"


def test_process_cq_reply_report_uses_msg_snr_not_last_snr():
    """Bug-C: bei msg.is_report (non-R) wird msg.snr fuer R-Report
    genutzt, nicht _last_snr."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH")
    sm.set_last_snr(-22)
    msg = _make_msg("DA1MHH", "SP6AXW", "-08", snr=-8)
    sm._process_cq_reply(msg)
    assert sm.qso.our_snr == "R-08"  # Bug-Fix: msg.snr=-8, nicht -22


def test_last_snr_unchanged_after_process_cq_reply():
    """Bug-C: _last_snr wird nicht modifiziert (Fallback bleibt
    bestehen fuer Hunt-Start + Retry-Pfade)."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH")
    sm.set_last_snr(-15)
    msg = _make_msg("DA1MHH", "SP6AXW", "JO80", snr=-8)
    sm._process_cq_reply(msg)
    assert sm._last_snr == -15  # unveraendert
```

**Test-Anzahl:** 4 Bug-A + 8 Bug-B + 1 Bug-B-QRZ + 3 Bug-C = **16 Tests**.
V2 schaetzte 17 — V3 final konkret 16.

### Diff 7 — `main.py:16` APP_VERSION

```python
APP_VERSION = "0.95.18"
```

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** (Verifikation):
   - `prompts/p1_bundle_logbook_rst_snr_v3.md` (diese Datei)
   - `log/adif.py` (Z.47-98 delete_qso, Z.114-219 AdifWriter)
   - `log/qrz.py` (Z.54-62 upload_qso_from_dict)
   - `ui/logbook_widget.py` (Z.353-386 _on_delete_clicked + _on_filter_changed)
   - `core/qso_state.py` (Z.190-235 _process_cq_reply)
   - `core/message.py` (FT8Message)
2. **Diff 1** — `delete_qso` O(n²) → O(n).
3. **Diff 2** — `_on_delete_clicked` In-Memory-Update.
4. **Diff 3** — `_strip_r_prefix` Helper + Aufruf in `log_qso`.
5. **Diff 4** — `qrz.upload_qso_from_dict` Send-Pfad-Strip.
6. **Diff 5** — `_process_cq_reply` Z.214,229 `msg.snr`.
7. **Diff 6** — `tests/test_p1_bundle_logbook_rst_snr.py` NEU mit 16 Tests.
8. **Diff 7** — `main.py` APP_VERSION 0.95.17 → 0.95.18.
9. **Tests laufen:** `921 → 937 erwartet gruen` (+16).
10. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.BUNDLE-LOGBOOK-RST-SNR v0.95.18 final-Code.
    3 Bugfixes: delete_qso O(n²)→O(n), RST_RCVD R-Strip Schreib+Send,
    _process_cq_reply msg.snr statt _last_snr. 16 neue Tests." | \
    ./venv/bin/python3 tools/deepseek_review.py \
    log/adif.py log/qrz.py ui/logbook_widget.py core/qso_state.py \
    tests/test_p1_bundle_logbook_rst_snr.py
    ```
11. **Atomare Commits — 3 Code + 1 Doku:**
    - Bug-A: `P1.BUNDLE Bug-A (v0.95.18): delete_qso O(n²) Fix +
      Logbuch In-Memory-Update`
    - Bug-B: `P1.BUNDLE Bug-B (v0.95.18): RST_RCVD/RST_SENT R-Strip
      Schreib- und Send-Pfad`
    - Bug-C: `P1.BUNDLE Bug-C (v0.95.18) / P1.8: _process_cq_reply
      nutzt msg.snr statt _last_snr`
    - Doku: `docs (v0.95.18): P1.BUNDLE-LOGBOOK-RST-SNR
      HISTORY+HANDOFF+CLAUDE`
12. **Doku-Updates** (HISTORY, HANDOFF beide Pfade, CLAUDE beide
    Pfade, Memory).
13. **Push** NUR nach Mike-Freigabe + Field-Test (besonders QRZ-Bulk).
14. **Lessons-Learned**.

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] Diff 1: delete_qso list.append + "".join (O(n²)→O(n))
- [ ] Diff 2: _on_delete_clicked In-Memory-Update + Filter-Re-Apply
- [ ] Diff 3: _strip_r_prefix Helper + log_qso Aufruf
- [ ] Diff 4: qrz.upload_qso_from_dict Send-Pfad-Strip (lazy import)
- [ ] Diff 5: _process_cq_reply Z.214,229 msg.snr
- [ ] Diff 6: 16 neue Tests in test_p1_bundle_logbook_rst_snr.py
- [ ] Diff 7: APP_VERSION 0.95.18
- [ ] 937 Tests gesamt gruen (921 + 16)
- [ ] Bug-A AC < 500 ms (Performance-Test)
- [ ] Bug-B AC: ADIF-Output ohne R + QRZ-Payload ohne R
- [ ] Bug-C AC: msg.snr im Report, _last_snr unveraendert
- [ ] Final-R1 ohne 🔴-Findings
- [ ] HISTORY/HANDOFF/CLAUDE updated (beide Pfade)
- [ ] 3 atomare Code-Commits + 1 Doku-Commit
- [ ] Mike-Freigabe fuer Push EXPLIZIT (nach Field-Test)
- [ ] Field-Test QRZ-Bulk-Upload: kein 10K-Burst mehr
- [ ] Lessons-Learned
```

---

## 5. Risiken & Notbremse

- **Bug-A: In-Memory-Update Edge-Case:** Wenn 2 Records absolut
  identisch sind (gleiche CALL+DATE+TIME), wird `_all_records.remove(rec)`
  den ersten passenden entfernen — kann aber falscher sein.
  **Mitigation:** parse_adif_file setzt `_SOURCE_FILE` plus die
  Records werden als Dict-Identitaet behandelt — Python `list.remove`
  matcht via `==`. Bei identischen Records ist beide Versionen
  funktional aequivalent (Disk hat einen weniger). Akzeptabel.
- **Bug-B Lazy-Import:** `from log.adif import _strip_r_prefix`
  innerhalb `upload_qso_from_dict` vermeidet Zirkel — `log.adif`
  importiert nichts aus `log.qrz`, also OK. Test: lazy import wird
  gemockt? Nein, der Helper ist defensiv und einfach.
- **Bug-C Hunt-Pfad-Inkonsistenz:** `start_qso` (Z.268) nutzt weiter
  `_last_snr`. Wenn User einen Record klickt, kann `_last_snr` von
  einer anderen Message stammen. **Bekannt, aus Scope** — separater
  Bug fuer Hunt-Pfad-SNR mit RX-Panel-Klick-Durchreichung (P1.16
  oder spaeter).
- **Performance-AC < 500 ms:** Kann in CI auf langsamem System
  knapp werden. **Mitigation:** Test wird auf Mike-Mac gemessen
  (M-Mac, < 100 ms erwartet). Wenn CI-Box langsamer ist, AC anheben
  auf 1000 ms.
- **QRZ-Field-Test-Pflicht:** Bug-B ist nur bestaetigt wenn Mike's
  10K-Burst nach Update verschwindet. Sonst andere Wurzel — separater
  Workflow. **Notbremse:** v0.95.18-Push erst nach Mike-Field-Test-OK.

---

## 6. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.BUNDLE-LOGBOOK-RST-SNR ueberraschend?
2. Was wuerde ich rueckblickend anders machen?
3. Welches Memory soll geschrieben werden? Vorschlag:
   - `feedback_python_string_concat_loop_oN2.md` — bei jedem
     File-Re-Write-Fix grep auf `+=` in Loop. Generelles Python-
     Anti-Pattern.
   - `feedback_format_compliance_check_pflicht.md` — bei jedem
     Standard-Format (ADIF, JSON-Schema, etc.) Vergleich gegen
     Referenz-Datei (Mike's QRZ-Export war Goldstandard hier).

---

**Plan-V3 Ende. Bereit fuer Compact + Code.**
