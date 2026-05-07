"""Tests fuer P1.QRZ-UPLOAD-UI v0.95.14 (Confirm + Worker).

Decken ab:
- Worker progress-Signal alle 10 QSOs
- Worker cancel-Pfad (sauberer Stop nach aktuellem QSO)
- Worker immediate-cancel emittet trotzdem finished (R1-Final v0.95.14)
- Worker counter-Logik (OK/Dup/Fail)
- Confirm-Dialog Default-Button (Enter = Upload)
- Confirm-Dialog Reject-Pfad

P1.QRZ-UPLOAD-UI-2 v0.95.15: Progress-Dialog-Tests (4) entfernt — Status
laeuft jetzt in Titelleiste + Statusbar-Cancel-Widget. Neue Tests in
tests/test_p1_qrz_upload_ui_2.py.
"""
import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_records(n: int) -> list:
    return [{"CALL": f"DA{i}TST", "BAND": "40m", "MODE": "FT8"}
            for i in range(n)]


# ── Worker Tests ────────────────────────────────────────────────────────


def test_worker_progress_signal_every_10_qsos(qapp):
    """Progress-Signal feuert alle 10 QSOs."""
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()
    client.upload_qso_from_dict.return_value = {"RESULT": "OK"}
    records = _make_records(35)

    worker = QRZUploadWorker(client, records)
    progress_calls = []
    worker.progress.connect(lambda *a: progress_calls.append(a))
    finished_called = []
    worker.finished.connect(lambda *a: finished_called.append(a))

    worker.start()
    worker._future.result(timeout=10)
    qapp.processEvents()
    worker.shutdown(wait=True)
    qapp.processEvents()

    # 35 QSOs / 10 = 3 Progress-Updates (bei 10, 20, 30)
    assert len(progress_calls) == 3
    assert progress_calls[0] == (10, 35, 10, 0, 0)
    assert progress_calls[2] == (30, 35, 30, 0, 0)
    # Finished feuert immer
    assert len(finished_called) == 1
    ok, dup, fail, cancelled, processed = finished_called[0]
    assert ok == 35 and processed == 35 and not cancelled


def test_worker_cancel_stops_cleanly(qapp):
    """Cancel-Event stoppt Worker nach aktuellem QSO."""
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()

    def slow_upload(rec):
        time.sleep(0.05)
        return {"RESULT": "OK"}
    client.upload_qso_from_dict.side_effect = slow_upload
    records = _make_records(50)

    worker = QRZUploadWorker(client, records)
    finished = []
    worker.finished.connect(lambda *a: finished.append(a))

    worker.start()
    time.sleep(0.15)
    worker.cancel()
    worker._future.result(timeout=5)
    qapp.processEvents()
    worker.shutdown(wait=True)
    qapp.processEvents()

    ok, dup, fail, cancelled, processed = finished[0]
    assert cancelled is True
    assert processed < 50


def test_worker_immediate_cancel_still_emits_finished(qapp):
    """R1-Final: Wenn User sofort cancelt (processed=0), muss Worker
    trotzdem finished emittieren, sonst bleibt Dialog haengen."""
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()

    def slow_upload(rec):
        time.sleep(0.5)
        return {"RESULT": "OK"}
    client.upload_qso_from_dict.side_effect = slow_upload
    records = _make_records(5)

    worker = QRZUploadWorker(client, records)
    finished = []
    worker.finished.connect(lambda *a: finished.append(a))

    worker.start()
    worker.cancel()  # SOFORT canceln, vor erstem upload-Aufruf
    worker._future.result(timeout=5)
    qapp.processEvents()
    worker.shutdown(wait=True)
    qapp.processEvents()

    # Trotz processed=0 muss finished emittieren
    assert len(finished) == 1
    ok, dup, fail, cancelled, processed = finished[0]
    assert cancelled is True


def test_worker_counts_ok_dup_fail(qapp):
    """Counter unterscheidet OK / Duplicate / Fail."""
    from core.qrz_upload_worker import QRZUploadWorker
    client = MagicMock()

    def variable_response(rec):
        call = rec["CALL"]
        if "0" in call or "1" in call:
            return {"RESULT": "OK"}
        if "2" in call:
            return {"RESULT": "FAIL", "REASON": "duplicate entry"}
        return {"RESULT": "FAIL", "REASON": "server error"}
    client.upload_qso_from_dict.side_effect = variable_response

    records = _make_records(30)
    worker = QRZUploadWorker(client, records)
    finished = []
    worker.finished.connect(lambda *a: finished.append(a))
    worker.start()
    worker._future.result(timeout=10)
    qapp.processEvents()
    worker.shutdown(wait=True)

    ok, dup, fail, cancelled, processed = finished[0]
    assert ok > 0 and dup > 0 and fail > 0
    assert ok + dup + fail == 30


# ── Dialog Tests ────────────────────────────────────────────────────────


def test_confirm_dialog_default_button_is_upload(qapp):
    """Default-Button ist [Hochladen] (Enter = Upload, R1.1)."""
    from ui.qrz_upload_dialogs import QRZConfirmDialog
    dlg = QRZConfirmDialog(total=1000)
    assert dlg.btn_upload.isDefault() is True
    assert dlg.btn_cancel.isDefault() is False


def test_confirm_dialog_reject_returns_rejected(qapp):
    """Klick auf [Abbrechen] → reject() → DialogCode.Rejected."""
    from PySide6.QtWidgets import QDialog
    from ui.qrz_upload_dialogs import QRZConfirmDialog
    dlg = QRZConfirmDialog(total=100)
    dlg.btn_cancel.click()
    assert dlg.result() == QDialog.DialogCode.Rejected


