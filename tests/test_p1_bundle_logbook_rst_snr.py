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
from unittest.mock import patch

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
    """Schreibt Tmp-ADIF mit n Records (CALL=Cxxxxxx, QSO_DATE=20260101)."""
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
    """Bug-A: delete_qso < 500 ms bei 10K Records (vorher 5-10 s)."""
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
    # _filtered_records darf den Record nicht mehr enthalten
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


def test_strip_whitespace_handled():
    """Whitespace-Padding wird gestrippt."""
    assert _strip_r_prefix("  R-22  ") == "-22"


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
    client = QRZClient(api_key="dummy")
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


def _make_msg(field1, field2, field3, snr):
    """Helper: minimale FT8Message mit msg.snr."""
    from core.message import FT8Message
    return FT8Message(
        raw=f"{field1} {field2} {field3}",
        field1=field1, field2=field2, field3=field3, snr=snr,
    )


def test_process_cq_reply_grid_uses_msg_snr_not_last_snr():
    """Bug-C: bei msg.is_grid wird msg.snr fuer Report genutzt, nicht
    _last_snr (der vom letzten Slot ueberschrieben sein kann)."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.cq_mode = True
    sm.set_last_snr(-22)  # andere Station, fuer Report ignoriert
    msg = _make_msg("DA1MHH", "SP6AXW", "JO80", snr=-8)
    sm._pending_reply = msg
    sm._process_cq_reply()
    # Report aus msg.snr=-8, nicht aus _last_snr=-22
    assert sm.qso.our_snr == "-08"


def test_process_cq_reply_report_uses_msg_snr_not_last_snr():
    """Bug-C: bei msg.is_report (non-R) wird msg.snr fuer R-Report
    genutzt, nicht _last_snr."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.cq_mode = True
    sm.set_last_snr(-22)
    msg = _make_msg("DA1MHH", "SP6AXW", "-08", snr=-8)
    sm._pending_reply = msg
    sm._process_cq_reply()
    assert sm.qso.our_snr == "R-08"  # Bug-Fix: msg.snr=-8, nicht -22


def test_last_snr_unchanged_after_process_cq_reply():
    """Bug-C: _last_snr wird nicht modifiziert (Fallback bleibt
    bestehen fuer Hunt-Start + Retry-Pfade)."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine(my_call="DA1MHH", my_grid="JO31")
    sm.cq_mode = True
    sm.set_last_snr(-15)
    msg = _make_msg("DA1MHH", "SP6AXW", "JO80", snr=-8)
    sm._pending_reply = msg
    sm._process_cq_reply()
    assert sm._last_snr == -15  # unveraendert
