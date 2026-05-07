"""SimpleFT8 QRZ Upload Worker — ThreadPool + Qt-Signals.

P1.QRZ-UPLOAD-UI v0.95.14: Bulk-Upload Worker mit Progress-Updates
und Cancel-Event. Nutzt ThreadPoolExecutor (Mike-bestehender Pattern).
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Dict

from PySide6.QtCore import QObject, Signal


class QRZUploadWorker(QObject):
    """Bulk-Upload Worker mit Progress-Signal und Cancel-Event.

    Pattern:
        worker = QRZUploadWorker(client, records, parent=self)
        worker.progress.connect(dialog.update_progress)
        worker.finished.connect(self._on_qrz_bulk_finished)
        worker.start()
        ...
        worker.cancel()  # bei User-Cancel oder App-Close
    """

    progress = Signal(int, int, int, int, int)
    finished = Signal(int, int, int, bool, int)

    PROGRESS_INTERVAL = 10

    def __init__(self, client, records: List[Dict], parent=None):
        super().__init__(parent)
        self._client = client
        self._records = records
        self._cancel_event = threading.Event()
        self._pool: ThreadPoolExecutor | None = None
        self._future: Future | None = None

    def start(self) -> None:
        """Worker im ThreadPool starten."""
        self._pool = ThreadPoolExecutor(max_workers=1,
                                        thread_name_prefix="qrz_bulk")
        self._future = self._pool.submit(self._run)

    def cancel(self) -> None:
        """Sauberer Abbruch — Worker beendet nach aktuellem QSO."""
        self._cancel_event.set()

    def shutdown(self, wait: bool = False) -> None:
        """Pool runterfahren — wait=False fuer App-Close (R1.8)."""
        if self._pool:
            self._pool.shutdown(wait=wait)

    def _run(self) -> None:
        """Worker-Loop — laeuft im ThreadPool-Thread."""
        ok = dup = fail = 0
        total = len(self._records)

        for i, rec in enumerate(self._records):
            if self._cancel_event.is_set():
                break
            try:
                result = self._client.upload_qso_from_dict(rec)
                status = result.get("RESULT", "FAIL")
                reason = result.get("REASON", "").lower()
                if status == "OK":
                    ok += 1
                elif "duplicate" in reason:
                    dup += 1
                else:
                    fail += 1
            except Exception:
                fail += 1

            if (i + 1) % self.PROGRESS_INTERVAL == 0:
                if not self._cancel_event.is_set():
                    self.progress.emit(i + 1, total, ok, dup, fail)

        cancelled = self._cancel_event.is_set()
        total_processed = ok + dup + fail
        # IMMER emit: Wenn User sofort cancelt (processed=0) muss Dialog
        # trotzdem set_finished erhalten, sonst bleibt er in "wird abgebrochen ...".
        # App-Close-Schutz (Signal-Emit auf zerstoerten Dialog) erfolgt im
        # main_window.closeEvent via finished.disconnect() vor cancel().
        self.finished.emit(ok, dup, fail, cancelled, total_processed)
