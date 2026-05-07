"""SimpleFT8 QRZ Upload Worker — ThreadPool + Qt-Signals + File-Tracking + Log.

P1.QRZ-UPLOAD-UI-2 v0.95.15: erweitert um
- File-Tracking pro Source-File (`_SOURCE_FILE`)
- JSON-Lines Log-Datei pro Result (Mike: „log ob die daten nach qrz ok hochgeladen wurden")
- Rate-Limit-Detection (consecutive fails → cooldown)
- Cooldown-Loop mit Cancel-Check (NICHT blockierend, R1-KP)
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

from PySide6.QtCore import QObject, Signal


_LOG_DIR = Path.home() / ".simpleft8"


class QRZUploadWorker(QObject):
    """Bulk-Upload Worker mit Progress, File-Tracking, Log und Rate-Limit-Detection.

    Pattern:
        worker = QRZUploadWorker(client, records, parent=self)
        worker.progress.connect(slot_progress)
        worker.cooldown_tick.connect(slot_cooldown)
        worker.finished.connect(slot_finished)
        worker.start()
        ...
        worker.cancel()  # User-Cancel ODER App-Close
    """

    progress = Signal(int, int, int, int, int)
    finished = Signal(int, int, int, bool, int)
    cooldown_tick = Signal(int)  # NEU: seconds_left

    PROGRESS_INTERVAL = 10
    MAX_CONSECUTIVE_FAILS = 20
    COOLDOWN_SECONDS = 60

    def __init__(self, client, records: List[Dict], parent=None):
        super().__init__(parent)
        self._client = client
        self._records = records
        self._cancel_event = threading.Event()
        self._pool: ThreadPoolExecutor | None = None
        self._future: Future | None = None
        # File-Tracking: pro source_file ein Dict {ok, dup, fail, expected}
        self._file_results: Dict[str, Dict[str, int]] = {}
        for rec in records:
            src = rec.get("_SOURCE_FILE", "")
            if src and src not in self._file_results:
                self._file_results[src] = {"ok": 0, "dup": 0, "fail": 0, "expected": 0}
            if src:
                self._file_results[src]["expected"] += 1
        # Log-Datei pro Tag (Rotation)
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_path = _LOG_DIR / f"qrz_upload_{datetime.now().strftime('%Y-%m-%d')}.log"

    @property
    def file_results(self) -> Dict[str, Dict[str, int]]:
        """Threadsafe Copy — Worker schreibt nicht mehr nach finished."""
        return {k: dict(v) for k, v in self._file_results.items()}

    @property
    def total_records(self) -> int:
        """Anzahl Records die der Worker bearbeitet (read-only Property)."""
        return len(self._records)

    def start(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qrz_bulk")
        self._future = self._pool.submit(self._run)

    def cancel(self) -> None:
        self._cancel_event.set()

    def shutdown(self, wait: bool = False) -> None:
        if self._pool:
            self._pool.shutdown(wait=wait)

    def _log_result(self, rec: Dict, result: str, reason: str = "") -> None:
        """Append-only JSON-Lines Log."""
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "call": rec.get("CALL", ""),
            "band": rec.get("BAND", ""),
            "mode": rec.get("MODE", ""),
            "date": rec.get("QSO_DATE", ""),
            "time": rec.get("TIME_ON", ""),
            "result": result,
        }
        if reason:
            entry["reason"] = reason
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Log-Fehler nie Worker abbrechen lassen

    def _do_cooldown(self) -> bool:
        """Cooldown als Loop mit Cancel-Check (R1-KP).

        Returns False wenn cancel waehrend Cooldown, True wenn fertig.
        """
        for sec in range(self.COOLDOWN_SECONDS, 0, -1):
            if self._cancel_event.is_set():
                return False
            self.cooldown_tick.emit(sec)
            time.sleep(1)
        self.cooldown_tick.emit(0)
        return True

    def _run(self) -> None:
        ok = dup = fail = 0
        total = len(self._records)
        consecutive_fails = 0
        cooldown_used = False  # 1× Cooldown pro Bulk, dann cancel bei zweitem Burst

        for i, rec in enumerate(self._records):
            if self._cancel_event.is_set():
                break
            src = rec.get("_SOURCE_FILE", "")
            try:
                result = self._client.upload_qso_from_dict(rec)
                status = result.get("RESULT", "FAIL")
                reason = result.get("REASON", "").lower()
                if status == "OK":
                    ok += 1
                    consecutive_fails = 0
                    if src:
                        self._file_results[src]["ok"] += 1
                    self._log_result(rec, "OK")
                elif "duplicate" in reason:
                    dup += 1
                    consecutive_fails = 0
                    if src:
                        self._file_results[src]["dup"] += 1
                    self._log_result(rec, "duplicate")
                else:
                    fail += 1
                    consecutive_fails += 1
                    if src:
                        self._file_results[src]["fail"] += 1
                    self._log_result(rec, "fail", reason or "unknown")
            except Exception as e:
                fail += 1
                consecutive_fails += 1
                if src:
                    self._file_results[src]["fail"] += 1
                self._log_result(rec, "fail", str(e))

            # Progress alle 10 QSOs
            if (i + 1) % self.PROGRESS_INTERVAL == 0:
                if not self._cancel_event.is_set():
                    self.progress.emit(i + 1, total, ok, dup, fail)

            # Rate-Limit-Detection
            if consecutive_fails >= self.MAX_CONSECUTIVE_FAILS:
                if cooldown_used:
                    # Zweiter Burst → Cancel
                    print(f"[QRZ-Worker] Zweiter Fail-Burst nach Cooldown → Cancel")
                    self._cancel_event.set()
                    break
                cooldown_used = True
                print(f"[QRZ-Worker] {consecutive_fails} consecutive fails → Cooldown {self.COOLDOWN_SECONDS}s")
                if not self._do_cooldown():
                    break  # cancel waehrend Cooldown
                consecutive_fails = 0  # Reset nach Cooldown

        cancelled = self._cancel_event.is_set()
        total_processed = ok + dup + fail
        # IMMER emit (P1.QRZ-UPLOAD-UI Final-R1-Lesson, behalten)
        self.finished.emit(ok, dup, fail, cancelled, total_processed)
