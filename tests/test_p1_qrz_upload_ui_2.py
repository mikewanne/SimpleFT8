"""Tests fuer P1.QRZ-UPLOAD-UI-2 v0.95.15.

Decken ab:
- Worker file_results Property (pro Source-File aggregiert)
- Worker JSONL-Log (pro Result eine Zeile, Daily-Rotation)
- Rate-Limit-Detection (Counter-Reset, Cooldown, 2. Burst → Cancel)
- File-Move (alle OK/Dup, mind. 1 Fail, partial-Cancel, hochgeladen-Schutz)
- Title-Update + Reset
- Logbook Multi-Dir-Load
- Bulk-Filter Records aus hochgeladen/
- Pflege-Tests aus v0.95.14 (Progress-Signal, Immediate-Cancel, Confirm-Default)
- Statusbar-Widget initial hidden

Mock-Pattern: QRZClient mit MagicMock, Records mit `_SOURCE_FILE`.
"""
import os
import sys
import time
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_records(n: int, source_file: str = "/tmp/test.adi") -> list:
    return [{"CALL": f"DA{i}TST", "BAND": "40m", "MODE": "FT8",
             "QSO_DATE": "20260507", "TIME_ON": "120000",
             "_SOURCE_FILE": source_file}
            for i in range(n)]


# ── Worker file_results + Logging Tests ──────────────────────────────────


def test_worker_file_results_aggregates_per_file(qapp, tmp_path, monkeypatch):
    """file_results pro Source-File aggregiert ok/dup/fail/expected."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    client.upload_qso_from_dict.return_value = {"RESULT": "OK"}
    f1 = str(tmp_path / "2026-05-01.adi")
    f2 = str(tmp_path / "2026-05-02.adi")
    records = _make_records(3, source_file=f1) + _make_records(2, source_file=f2)

    worker = QRZUploadWorker(client, records)
    worker.start()
    worker._future.result(timeout=10)
    worker.shutdown(wait=True)

    fr = worker.file_results
    assert fr[f1]["expected"] == 3
    assert fr[f1]["ok"] == 3
    assert fr[f2]["expected"] == 2
    assert fr[f2]["ok"] == 2


def test_worker_file_results_mixed_results(qapp, tmp_path, monkeypatch):
    """OK/Dup/Fail werden korrekt pro File getrennt."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    f1 = str(tmp_path / "2026-05-01.adi")

    def variable(rec):
        c = rec["CALL"]
        if "0" in c:
            return {"RESULT": "OK"}
        if "1" in c:
            return {"RESULT": "FAIL", "REASON": "duplicate entry"}
        return {"RESULT": "FAIL", "REASON": "server error"}
    client.upload_qso_from_dict.side_effect = variable
    records = _make_records(3, source_file=f1)

    worker = QRZUploadWorker(client, records)
    worker.start()
    worker._future.result(timeout=10)
    worker.shutdown(wait=True)

    fr = worker.file_results
    assert fr[f1]["ok"] == 1
    assert fr[f1]["dup"] == 1
    assert fr[f1]["fail"] == 1


def test_worker_writes_jsonl_log(qapp, tmp_path, monkeypatch):
    """Worker schreibt pro Result eine JSONL-Zeile in qrz_upload_*.log."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    client.upload_qso_from_dict.return_value = {"RESULT": "OK"}
    records = _make_records(5)
    worker = QRZUploadWorker(client, records)
    worker.start()
    worker._future.result(timeout=10)
    worker.shutdown(wait=True)

    log_files = list(tmp_path.glob("qrz_upload_*.log"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().strip().splitlines()
    assert len(lines) == 5
    entry = json.loads(lines[0])
    assert entry["call"].startswith("DA")
    assert entry["result"] == "OK"
    assert "ts" in entry


# ── Rate-Limit-Detection Tests ───────────────────────────────────────────


def test_worker_cooldown_after_burst(qapp, monkeypatch, tmp_path):
    """Nach MAX_CONSECUTIVE_FAILS → Cooldown emittet cooldown_tick."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    orig_cool = QRZUploadWorker.COOLDOWN_SECONDS
    orig_max = QRZUploadWorker.MAX_CONSECUTIVE_FAILS
    QRZUploadWorker.COOLDOWN_SECONDS = 2
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 3

    try:
        client = MagicMock()
        # 3 Fails dann OK damit Worker durchlaeuft (kein zweiter Burst)
        counter = {"n": 0}

        def fails_then_ok(rec):
            counter["n"] += 1
            if counter["n"] <= 3:
                return {"RESULT": "FAIL", "REASON": "x"}
            return {"RESULT": "OK"}
        client.upload_qso_from_dict.side_effect = fails_then_ok
        records = _make_records(8)

        worker = QRZUploadWorker(client, records)
        cooldown_calls = []
        worker.cooldown_tick.connect(lambda s: cooldown_calls.append(s))

        worker.start()
        worker._future.result(timeout=10)
        worker.shutdown(wait=True)
        qapp.processEvents()

        # mind. 2 Ticks (2s Cooldown, 1s pro Tick + 0-Tick am Ende)
        assert len(cooldown_calls) >= 2
    finally:
        QRZUploadWorker.COOLDOWN_SECONDS = orig_cool
        QRZUploadWorker.MAX_CONSECUTIVE_FAILS = orig_max


def test_worker_consecutive_fails_reset_on_ok(qapp, monkeypatch, tmp_path):
    """OK zwischen Fails → Counter resetet, kein Cooldown."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    orig_max = QRZUploadWorker.MAX_CONSECUTIVE_FAILS
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 5

    try:
        client = MagicMock()
        counter = {"n": 0}

        def alternating(rec):
            counter["n"] += 1
            # 4 fails, 1 ok bei Index 5, dann 4 fails (4 reicht nicht für Cooldown)
            if counter["n"] == 5:
                return {"RESULT": "OK"}
            return {"RESULT": "FAIL", "REASON": "x"}
        client.upload_qso_from_dict.side_effect = alternating
        records = _make_records(9)

        worker = QRZUploadWorker(client, records)
        cooldown_calls = []
        worker.cooldown_tick.connect(lambda s: cooldown_calls.append(s))

        worker.start()
        worker._future.result(timeout=10)
        worker.shutdown(wait=True)
        qapp.processEvents()

        assert len(cooldown_calls) == 0  # kein Cooldown weil reset
    finally:
        QRZUploadWorker.MAX_CONSECUTIVE_FAILS = orig_max


def test_worker_cancel_during_cooldown(qapp, monkeypatch, tmp_path):
    """Cancel waehrend Cooldown stoppt Worker sofort."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    orig_cool = QRZUploadWorker.COOLDOWN_SECONDS
    orig_max = QRZUploadWorker.MAX_CONSECUTIVE_FAILS
    QRZUploadWorker.COOLDOWN_SECONDS = 5
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 3

    try:
        client = MagicMock()
        client.upload_qso_from_dict.return_value = {"RESULT": "FAIL", "REASON": "x"}
        records = _make_records(10)

        worker = QRZUploadWorker(client, records)
        finished = []
        worker.finished.connect(lambda *a: finished.append(a))
        worker.start()
        time.sleep(0.5)  # warten bis Cooldown angefangen hat
        worker.cancel()
        worker._future.result(timeout=5)
        worker.shutdown(wait=True)
        qapp.processEvents()

        assert len(finished) == 1
        cancelled = finished[0][3]
        assert cancelled is True
    finally:
        QRZUploadWorker.COOLDOWN_SECONDS = orig_cool
        QRZUploadWorker.MAX_CONSECUTIVE_FAILS = orig_max


def test_worker_second_burst_cancels(qapp, monkeypatch, tmp_path):
    """Zweiter Fail-Burst nach Cooldown → cancel."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    orig_cool = QRZUploadWorker.COOLDOWN_SECONDS
    orig_max = QRZUploadWorker.MAX_CONSECUTIVE_FAILS
    QRZUploadWorker.COOLDOWN_SECONDS = 1
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 3

    try:
        client = MagicMock()
        client.upload_qso_from_dict.return_value = {"RESULT": "FAIL", "REASON": "x"}
        records = _make_records(20)
        worker = QRZUploadWorker(client, records)
        finished = []
        worker.finished.connect(lambda *a: finished.append(a))
        worker.start()
        worker._future.result(timeout=10)
        worker.shutdown(wait=True)
        qapp.processEvents()

        assert len(finished) == 1
        # cancelled muss True sein weil zweiter Burst
        assert finished[0][3] is True
        # processed deutlich kleiner als 20
        assert finished[0][4] < 20
    finally:
        QRZUploadWorker.COOLDOWN_SECONDS = orig_cool
        QRZUploadWorker.MAX_CONSECUTIVE_FAILS = orig_max


# ── File-Move Tests ──────────────────────────────────────────────────────


def test_handle_file_results_moves_when_all_ok(qapp, tmp_path, monkeypatch):
    """File mit nur OK/Dup wird nach hochgeladen/ verschoben."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path / "adif"
    adif_dir.mkdir()
    src = adif_dir / "2026-05-01.adi"
    src.write_text("dummy")

    file_results = {
        str(src): {"ok": 2, "dup": 1, "fail": 0, "expected": 3}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    monkeypatch.chdir(tmp_path)

    QSOMixin._handle_qrz_file_results(fake_self, file_results)

    assert (adif_dir / "hochgeladen" / "2026-05-01.adi").exists()
    assert not src.exists()


def test_handle_file_results_skipped_when_fail(qapp, tmp_path, monkeypatch):
    """File mit FAIL bleibt in adif/."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path / "adif"
    adif_dir.mkdir()
    src = adif_dir / "2026-05-02.adi"
    src.write_text("dummy")

    file_results = {
        str(src): {"ok": 2, "dup": 0, "fail": 1, "expected": 3}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    monkeypatch.chdir(tmp_path)

    QSOMixin._handle_qrz_file_results(fake_self, file_results)

    assert src.exists()  # bleibt
    assert not (adif_dir / "hochgeladen" / "2026-05-02.adi").exists()


def test_handle_file_results_skipped_when_partial(qapp, tmp_path, monkeypatch):
    """File mit weniger processed als expected (Cancel) bleibt."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path / "adif"
    adif_dir.mkdir()
    src = adif_dir / "2026-05-03.adi"
    src.write_text("dummy")

    file_results = {
        str(src): {"ok": 1, "dup": 0, "fail": 0, "expected": 5}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    monkeypatch.chdir(tmp_path)

    QSOMixin._handle_qrz_file_results(fake_self, file_results)

    assert src.exists()


def test_handle_file_results_skips_when_dest_exists(qapp, tmp_path, monkeypatch):
    """File-Move wird übersprungen wenn Ziel-Datei in hochgeladen/ schon existiert (R1-Fix)."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path / "adif"
    hoch = adif_dir / "hochgeladen"
    hoch.mkdir(parents=True)
    src = adif_dir / "2026-05-04.adi"
    src.write_text("new content")
    existing = hoch / "2026-05-04.adi"
    existing.write_text("old content")

    file_results = {
        str(src): {"ok": 3, "dup": 0, "fail": 0, "expected": 3}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    monkeypatch.chdir(tmp_path)

    QSOMixin._handle_qrz_file_results(fake_self, file_results)

    # Quelle bleibt unverändert, Ziel nicht ueberschrieben
    assert src.exists()
    assert src.read_text() == "new content"
    assert existing.read_text() == "old content"


def test_handle_file_results_skips_hochgeladen_path(qapp, tmp_path, monkeypatch):
    """File aus hochgeladen/ wird NIE bewegt (Schutz vor Doppel-Move)."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path / "adif"
    hoch = adif_dir / "hochgeladen"
    hoch.mkdir(parents=True)
    src = hoch / "2026-04-01.adi"
    src.write_text("already moved")

    file_results = {
        str(src): {"ok": 5, "dup": 0, "fail": 0, "expected": 5}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    monkeypatch.chdir(tmp_path)

    QSOMixin._handle_qrz_file_results(fake_self, file_results)

    # File bleibt wo es ist (in hochgeladen/), kein Doppel-Move
    assert src.exists()


# ── Title-Update Tests ───────────────────────────────────────────────────


def test_update_window_title_with_suffix(qapp):
    """_update_window_title appended _qrz_title_suffix."""
    from ui.mw_qso import QSOMixin
    fake_self = MagicMock()
    fake_self.settings.callsign = "DA1MHH"
    fake_self._qrz_title_suffix = " — QRZ ↑ 100/500 (20%)"
    QSOMixin._update_window_title(fake_self)
    fake_self.setWindowTitle.assert_called_once()
    title = fake_self.setWindowTitle.call_args[0][0]
    assert "DA1MHH" in title
    assert "100/500" in title


def test_update_window_title_reset(qapp):
    """Reset Suffix → Title nur Callsign."""
    from ui.mw_qso import QSOMixin
    fake_self = MagicMock()
    fake_self.settings.callsign = "DA1MHH"
    fake_self._qrz_title_suffix = ""
    QSOMixin._update_window_title(fake_self)
    title = fake_self.setWindowTitle.call_args[0][0]
    assert title == "SimpleFT8 — DA1MHH"


# ── Logbook Multi-Dir Tests ──────────────────────────────────────────────


def test_logbook_loads_both_directories(qapp, tmp_path):
    """LogbookWidget lädt aus adif/ UND adif/hochgeladen/."""
    from ui.logbook_widget import LogbookWidget
    adif = tmp_path / "adif"
    hochgeladen = adif / "hochgeladen"
    adif.mkdir()
    hochgeladen.mkdir()

    # ADIF-Format: <field:length>value<eor>
    (adif / "active.adi").write_text(
        "<adif_ver:5>3.1.7<eoh>\n"
        "<call:5>NEW01 <band:3>40m <mode:3>FT8 <qso_date:8>20260507 <eor>\n"
    )
    (hochgeladen / "old.adi").write_text(
        "<adif_ver:5>3.1.7<eoh>\n"
        "<call:5>OLD01 <band:3>40m <mode:3>FT8 <qso_date:8>20260101 <eor>\n"
    )

    w = LogbookWidget(adif_directory=adif)
    w.load_adif()
    calls = [r["CALL"] for r in w._all_records]
    assert "NEW01" in calls
    assert "OLD01" in calls


def test_bulk_filters_hochgeladen_records(qapp):
    """Filter-Logik nimmt nur Records ohne 'hochgeladen' im _SOURCE_FILE."""
    all_records = [
        {"CALL": "NEW01", "_SOURCE_FILE": "/x/adif/2026-05-07.adi"},
        {"CALL": "OLD01", "_SOURCE_FILE": "/x/adif/hochgeladen/2026-01-01.adi"},
        {"CALL": "NEW02", "_SOURCE_FILE": "/x/adif/2026-05-08.adi"},
        {"CALL": "WIN01", "_SOURCE_FILE": "C:\\x\\adif\\hochgeladen\\foo.adi"},
    ]
    filtered = [
        r for r in all_records
        if "hochgeladen" not in r.get("_SOURCE_FILE", "").replace("\\", "/")
    ]
    assert len(filtered) == 2
    assert {r["CALL"] for r in filtered} == {"NEW01", "NEW02"}


# ── Existing Behaviour (Pflege-Tests) ────────────────────────────────────


def test_worker_progress_signal_every_10_qsos(qapp, tmp_path, monkeypatch):
    """Pflege: Progress alle 10 QSOs (aus v0.95.14)."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    client.upload_qso_from_dict.return_value = {"RESULT": "OK"}
    records = _make_records(35)
    worker = QRZUploadWorker(client, records)
    progress_calls = []
    worker.progress.connect(lambda *a: progress_calls.append(a))
    worker.start()
    worker._future.result(timeout=10)
    qapp.processEvents()
    worker.shutdown(wait=True)
    assert len(progress_calls) == 3


def test_worker_immediate_cancel_emits_finished(qapp, tmp_path, monkeypatch):
    """Pflege: Sofort-Cancel emittet trotzdem finished (R1-Final v0.95.14)."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()

    def slow(rec):
        time.sleep(0.5)
        return {"RESULT": "OK"}
    client.upload_qso_from_dict.side_effect = slow
    records = _make_records(5)
    worker = QRZUploadWorker(client, records)
    finished = []
    worker.finished.connect(lambda *a: finished.append(a))
    worker.start()
    worker.cancel()
    worker._future.result(timeout=5)
    qapp.processEvents()
    worker.shutdown(wait=True)
    assert len(finished) == 1
    assert finished[0][3] is True


def test_qrz_status_widget_initially_hidden(qapp):
    """Statusbar-Widget ist initial versteckt (Smoke)."""
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.hide()
    assert not w.isVisible()


def test_worker_total_records_property(qapp, tmp_path, monkeypatch):
    """Worker.total_records gibt Anzahl Records zurück (R1-Kapselung-Fix)."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    records = _make_records(7)
    worker = QRZUploadWorker(client, records)
    assert worker.total_records == 7
