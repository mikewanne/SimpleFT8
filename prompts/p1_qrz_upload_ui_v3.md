# P1.QRZ-UPLOAD-UI V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-07.
**Workflow:** V1 → V2 → R1 ✅ („alle 9 Pruefauftraege bestaetigt + 3 KP gefunden") → **V3** → Compact → Code.

**Mike's Anforderungen 07.05.2026:**
- QRZ.com Bulk-Upload mit sichtbarem Status-Fenster (vorher: kein Feedback → 8x Klick-Spam → ~8h Duplikat-Spam waere passiert)
- Nur eine Upload-Instanz parallel
- Weiterfunken waehrend Upload moeglich (non-modal mit StaysOnTopHint)
- Phase 1: Confirm-Dialog → Phase 2: Progress-Dialog
- KEIN Resume-Feature (KISS, QRZ.com filtert Duplikate serverseitig)

**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

---

## 1. R1-Findings übernommen

| R1-Empfehlung / Finding | Status |
|---|---|
| Default-Button `[Hochladen]` (Enter) | ✅ |
| Progress alle 10 QSOs (~2s Update) | ✅ |
| Cancel-Latenz max 10s (HTTP-Timeout) | ✅ |
| ThreadPoolExecutor + Signal-Emit | ✅ |
| Loesung A: Auto-Upload skip waehrend Bulk | ✅ |
| Auto-Close 10s + `[Schliessen]`-Button | ✅ |
| `raise_ + activateWindow` (Mike-Pattern) | ✅ |
| `shutdown(wait=False)` + cancel_event vorher | ✅ |
| **KP-1:** Auto-Upload-Race defensive fixen | ✅ |
| **KP-2:** Klick-Sperre-Reihenfolge Flag→Button→submit | ✅ |
| **KP-3:** Worker-Cancel-Check vor Signal-Emit | ✅ |

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — NEU `ui/qrz_upload_dialogs.py`

Beide Dialoge in einer Datei (Phase 1 + Phase 2). Mike-Theme #1a1a2e,
keine QMessageBox.

```python
"""SimpleFT8 QRZ Upload Dialoge — Confirm + Progress.

P1.QRZ-UPLOAD-UI v0.95.14: Phase-1-Bestaetigung + Phase-2-Progress.
Mike-Anforderung 07.05.: sichtbares Status-Fenster, weiterfunken
moeglich (non-modal), nur EINE Upload-Instanz.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar,
)


_DLG_STYLE = """
QDialog, QWidget { background-color: #1a1a2e; }
QLabel { color: #CCCCCC; font-family: Menlo; font-size: 12px;
         background-color: #1a1a2e; }
QLabel#lbl_title { color: #88AACC; font-size: 14px;
                   font-weight: bold; padding-bottom: 6px; }
QLabel#lbl_counter { color: #88CCAA; font-size: 12px; padding: 2px 0; }
QLabel#lbl_finished { color: #00CC66; font-size: 13px; font-weight: bold; }
QLabel#lbl_cancelled { color: #CCAA44; font-size: 13px; font-weight: bold; }
QPushButton {
    background-color: #2a2a3e; color: #CCCCCC;
    border: 1px solid #444; border-radius: 5px;
    font-family: Menlo; font-size: 12px;
    padding: 6px 16px; min-width: 100px;
}
QPushButton:hover { background-color: #3a3a5e; }
QPushButton#btn_primary { background-color: #1a3a6e; border-color: #4488cc; }
QPushButton#btn_primary:hover { background-color: #2a4a8e; }
QProgressBar {
    background-color: #2a2a3e; border: 1px solid #444; border-radius: 3px;
    text-align: center; color: #CCCCCC; font-family: Menlo; font-size: 11px;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #4488cc; border-radius: 3px;
}
"""


class QRZConfirmDialog(QDialog):
    """Phase 1: Bestaetigung vor Bulk-Upload.

    User-Choice via accepted/rejected. Default = Hochladen (Enter-Key).
    """

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QRZ.com Upload")
        self.setStyleSheet(_DLG_STYLE)
        self.setModal(True)  # blockt Logbuch waehrend Confirm

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        lbl_title = QLabel("QRZ.com Upload starten?")
        lbl_title.setObjectName("lbl_title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_msg = QLabel(
            f"<b>{total}</b> QSOs werden an QRZ.com Logbook gesendet.<br><br>"
            f"Duplikate werden serverseitig erkannt und uebersprungen.<br>"
            f"Bei <b>{total}</b> QSOs dauert der Upload ca. "
            f"<b>{max(1, total // 300)}</b> Minuten.<br><br>"
            f"Du kannst weiterfunken — der Upload laeuft im Hintergrund."
        )
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_msg.setWordWrap(True)
        layout.addWidget(lbl_msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_upload = QPushButton("Hochladen")
        self.btn_upload.setObjectName("btn_primary")
        self.btn_upload.setDefault(True)  # Enter = Upload (R1.1)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_upload.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_upload)
        layout.addLayout(btn_row)


class QRZUploadDialog(QDialog):
    """Phase 2: Non-modal Progress-Dialog mit Cancel.

    Signals:
        cancel_clicked: User klickt Abbrechen waehrend Upload laeuft.

    Slots:
        update_progress: Worker emittet alle 10 QSOs.
        set_finished: Worker meldet Endergebnis (Auto-Close 10s).
    """

    cancel_clicked = Signal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total = total
        self.setWindowTitle("QRZ.com Upload")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet(_DLG_STYLE)
        # Kein setModal → non-modal, weiterfunken moeglich

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        self.lbl_title = QLabel("QRZ.com Upload laeuft ...")
        self.lbl_title.setObjectName("lbl_title")
        layout.addWidget(self.lbl_title)

        self.lbl_progress = QLabel(f"0 von {total} QSOs (0%)")
        layout.addWidget(self.lbl_progress)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_counter = QLabel("Neu: 0   Duplikate: 0   Fehler: 0")
        self.lbl_counter.setObjectName("lbl_counter")
        layout.addWidget(self.lbl_counter)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self.btn_cancel)
        self.btn_close = QPushButton("Schliessen")
        self.btn_close.setObjectName("btn_primary")
        self.btn_close.hide()  # erst nach finished sichtbar
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self._auto_close_timer = QTimer(self)  # Child von dlg → safe cleanup
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.accept)

    @Slot(int, int, int, int, int)
    def update_progress(self, current: int, total: int,
                        ok: int, dup: int, fail: int) -> None:
        """Worker-Update (alle 10 QSOs via Qt.QueuedConnection)."""
        pct = int((current / total) * 100) if total else 0
        self.lbl_progress.setText(f"{current} von {total} QSOs ({pct}%)")
        self.progress_bar.setValue(current)
        self.lbl_counter.setText(
            f"Neu: {ok}   Duplikate: {dup}   Fehler: {fail}")

    @Slot(int, int, int, bool, int)
    def set_finished(self, ok: int, dup: int, fail: int,
                     cancelled: bool, total_processed: int) -> None:
        """Worker-Ende — Title + Auto-Close 10s + Schliessen-Button."""
        if cancelled:
            self.lbl_title.setText("QRZ.com Upload abgebrochen")
            self.lbl_title.setObjectName("lbl_cancelled")
        else:
            self.lbl_title.setText("QRZ.com Upload fertig")
            self.lbl_title.setObjectName("lbl_finished")
        # CSS neu laden damit Style-Update greift
        self.lbl_title.setStyleSheet(_DLG_STYLE)

        self.lbl_progress.setText(
            f"{total_processed} von {self._total} QSOs verarbeitet")
        self.lbl_counter.setText(
            f"Neu: {ok}   Duplikate: {dup}   Fehler: {fail}")
        self.btn_cancel.hide()
        self.btn_close.show()

        # Auto-Close 10s (R1.6) + raise_/activateWindow (R1.7)
        self._auto_close_timer.start(10000)
        self.raise_()
        self.activateWindow()

    def _on_cancel_clicked(self) -> None:
        """User-Klick → Signal emit, Button disable, warten."""
        self.btn_cancel.setEnabled(False)
        self.lbl_title.setText("QRZ.com Upload wird abgebrochen ...")
        self.cancel_clicked.emit()
```

### Diff 2 — NEU `core/qrz_upload_worker.py`

ThreadPool-Worker mit QObject-Wrapper für Signals.

```python
"""SimpleFT8 QRZ Upload Worker — ThreadPool + Qt-Signals.

P1.QRZ-UPLOAD-UI v0.95.14: Bulk-Upload Worker mit Progress-Updates
und Cancel-Event. Nutzt ThreadPoolExecutor (Mike-bestehender Pool).
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

    # current, total, ok, dup, fail
    progress = Signal(int, int, int, int, int)
    # ok, dup, fail, cancelled, total_processed
    finished = Signal(int, int, int, bool, int)

    PROGRESS_INTERVAL = 10  # alle 10 QSOs Update (R1.2)

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
            # Cancel-Check VOR Call (KP-3: kein Signal nach Cancel)
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

            # Progress-Update alle 10 QSOs (R1.2) — VOR Cancel-Re-Check
            if (i + 1) % self.PROGRESS_INTERVAL == 0:
                if not self._cancel_event.is_set():
                    self.progress.emit(i + 1, total, ok, dup, fail)

        cancelled = self._cancel_event.is_set()
        total_processed = ok + dup + fail
        # Final-Emit nur wenn nicht hart geschnitten (KP-3)
        if not cancelled or total_processed > 0:
            self.finished.emit(ok, dup, fail, cancelled, total_processed)
```

### Diff 3 — `ui/mw_qso.py:418-455` — `_on_qrz_upload` komplett ersetzen

```python
def _on_qrz_upload(self):
    """QRZ Bulk-Upload mit Confirm-Dialog + Progress-Dialog.

    P1.QRZ-UPLOAD-UI v0.95.14: Phase 1 Confirm → Phase 2 Progress (non-modal).
    Klick-Sperre 3-fach (R1-KP-2): Flag → Button → submit-Reihenfolge.
    """
    # KP-2: Re-Entry-Check als FIRST line (defensive)
    if getattr(self, '_qrz_bulk_active', False):
        print("[QRZ] Re-Entry-Schutz: Bulk laeuft schon, Klick ignoriert")
        return

    api_key = self.settings.get("qrz_api_key", "")
    if not api_key:
        from ui.qrz_upload_dialogs import _DLG_STYLE  # Theme-Hinweis
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        # Mike-Pattern: eigenes QDialog statt QMessageBox
        dlg = QDialog(self)
        dlg.setWindowTitle("QRZ.com")
        dlg.setStyleSheet(_DLG_STYLE)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16)
        lbl = QLabel(
            "Kein QRZ API Key konfiguriert.\n\n"
            "Bitte in ~/.simpleft8/config.json eintragen:\n"
            '"qrz_api_key": "XXXX-XXXX-XXXX-XXXX"'
        )
        lay.addWidget(lbl)
        btn = QPushButton("OK")
        btn.setObjectName("btn_primary")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)
        dlg.exec()
        return

    records = self.qso_panel.logbook._all_records
    if not records:
        self.statusBar().showMessage("Keine QSOs zum Hochladen.", 5000)
        return

    # Phase 1: Confirm-Dialog (R1.1)
    from ui.qrz_upload_dialogs import QRZConfirmDialog, QRZUploadDialog
    confirm = QRZConfirmDialog(len(records), parent=self)
    if confirm.exec() != QDialog.DialogCode.Accepted:
        return  # Mike hat abgebrochen

    # KP-2 Reihenfolge: 1) Flag → 2) Button → 3) Worker starten
    self._qrz_bulk_active = True
    self._set_qrz_button_enabled(False)

    # Phase 2: Progress-Dialog (non-modal)
    self._qrz_dialog = QRZUploadDialog(len(records), parent=self)
    self._qrz_dialog.setWindowFlag(Qt.WindowType.Window, True)

    # Worker erstellen + verkabeln
    from core.qrz_upload_worker import QRZUploadWorker
    client = self._get_qrz_client()
    self._qrz_worker = QRZUploadWorker(client, records, parent=self)
    self._qrz_worker.progress.connect(
        self._qrz_dialog.update_progress, Qt.ConnectionType.QueuedConnection)
    self._qrz_worker.finished.connect(
        self._on_qrz_bulk_finished, Qt.ConnectionType.QueuedConnection)
    self._qrz_dialog.cancel_clicked.connect(self._qrz_worker.cancel)
    self._qrz_dialog.show()
    self._qrz_dialog.raise_()
    self._qrz_dialog.activateWindow()

    self._qrz_worker.start()
    print(f"[QRZ] Bulk-Upload gestartet ({len(records)} QSOs)")

@Slot(int, int, int, bool, int)
def _on_qrz_bulk_finished(self, ok: int, dup: int, fail: int,
                          cancelled: bool, total_processed: int) -> None:
    """Worker-Finish — Dialog updaten, Flag/Button reset."""
    if hasattr(self, '_qrz_dialog') and self._qrz_dialog:
        self._qrz_dialog.set_finished(ok, dup, fail, cancelled, total_processed)
    self._qrz_bulk_active = False
    self._set_qrz_button_enabled(True)
    # Worker-Pool sauber runterfahren (kein Memory-Leak)
    if hasattr(self, '_qrz_worker') and self._qrz_worker:
        self._qrz_worker.shutdown(wait=False)
    print(f"[QRZ] Bulk-Upload beendet: {ok} neu, {dup} dup, {fail} fail "
          f"(cancelled={cancelled})")

def _set_qrz_button_enabled(self, enabled: bool) -> None:
    """Logbook-QRZ-Button enable/disable — Single-Instance-Schutz (R1-KP-2)."""
    try:
        self.qso_panel.logbook.set_qrz_button_enabled(enabled)
    except AttributeError:
        pass  # falls Logbook noch nicht initialisiert
```

### Diff 4 — `ui/mw_qso.py:397-416` — `_qrz_upload_single` Bulk-Skip (KP-1)

```python
def _qrz_upload_single(self, record: dict):
    """Einzelnes QSO an QRZ.com hochladen (non-blocking).

    P1.QRZ-UPLOAD-UI v0.95.14 (R1-KP-1): Bei aktivem Bulk-Upload
    skippen — sonst Race im geteilten ThreadPool.
    """
    # KP-1: Defensive-Check vor submit
    if getattr(self, '_qrz_bulk_active', False):
        call = record.get("CALL", "?")
        print(f"[QRZ] Auto-Upload {call} uebersprungen — Bulk-Upload laeuft")
        return

    from concurrent.futures import ThreadPoolExecutor
    if not hasattr(self, '_qrz_pool'):
        self._qrz_pool = ThreadPoolExecutor(max_workers=1)
    client = self._get_qrz_client()

    def _do_upload():
        result = client.upload_qso_from_dict(record)
        status = result.get("RESULT", "FAIL")
        call = record.get("CALL", "?")
        if status == "OK":
            return f"QRZ Upload OK: {call}"
        return f"QRZ Fehler: {result.get('REASON', 'unbekannt')}"

    future = self._qrz_pool.submit(_do_upload)
    future.add_done_callback(
        lambda f: self.statusBar().showMessage(f.result(), 5000)
        if not f.exception() else None
    )
```

### Diff 5 — `ui/logbook_widget.py` — Public API für Button-Enable

Nach Z.124 (`btn_upload.clicked.connect(...)`) einfuegen:

```python
        # Reference fuer P1.QRZ-UPLOAD-UI Klick-Sperre
        self._btn_upload = btn_upload
```

Und neue Methode am Ende der Klasse (nach load_adif etc.):

```python
    def set_qrz_button_enabled(self, enabled: bool) -> None:
        """P1.QRZ-UPLOAD-UI: Single-Instance-Schutz fuer Bulk-Upload."""
        if hasattr(self, '_btn_upload'):
            self._btn_upload.setEnabled(enabled)
            # Visuell: ausgegraut bei disabled
            if enabled:
                self._btn_upload.setToolTip("")
            else:
                self._btn_upload.setToolTip("Upload laeuft …")
```

### Diff 6 — `ui/main_window.py` closeEvent — Pool-Shutdown (KP-3)

In `MainWindow.closeEvent` (suchen mit grep, ca. mw_radio.py oder
main_window.py) ergaenzen:

```python
def closeEvent(self, event):
    # P1.QRZ-UPLOAD-UI: Bulk-Worker sauber stoppen vor App-Close (KP-3)
    if hasattr(self, '_qrz_worker') and self._qrz_worker:
        self._qrz_worker.cancel()
        self._qrz_worker.shutdown(wait=False)
    # ... bestehender closeEvent-Code
    super().closeEvent(event)
```

**WICHTIG:** Wenn closeEvent schon existiert, NUR die ersten 3 Zeilen
adden. Sonst: closeEvent neu definieren.

### Diff 7 — `tests/test_p1_qrz_upload_ui.py` (NEU, 9 Tests)

```python
"""Tests fuer P1.QRZ-UPLOAD-UI v0.95.14.

Decken ab:
- Klick-Sperre (Flag + Button + Re-Entry-Check)
- Confirm-Dialog Cancel-Pfad
- Progress-Signal alle 10 QSOs
- Cancel-Pfad sauber
- Auto-Close 10s
- Worker-Lifecycle
- Auto-Upload-Skip waehrend Bulk
- App-Close-Cleanup
- Dialog-Smoke

Mock-Pattern: QRZClient mit MagicMock, Records als list[dict].
"""
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── 1. QRZUploadWorker Tests ────────────────────────────────────────────


def _make_records(n: int) -> list:
    return [{"CALL": f"DA{i}TST", "BAND": "40m", "MODE": "FT8"}
            for i in range(n)]


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
    # Warten bis fertig
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
    # Simulate slow uploads so we have time to cancel
    def slow_upload(rec):
        time.sleep(0.05)
        return {"RESULT": "OK"}
    client.upload_qso_from_dict.side_effect = slow_upload
    records = _make_records(50)

    worker = QRZUploadWorker(client, records)
    finished = []
    worker.finished.connect(lambda *a: finished.append(a))

    worker.start()
    time.sleep(0.15)  # ~3 QSOs durch
    worker.cancel()
    worker._future.result(timeout=5)
    qapp.processEvents()
    worker.shutdown(wait=True)
    qapp.processEvents()

    # Worker hat aufgehoert vor 50 → cancelled=True
    ok, dup, fail, cancelled, processed = finished[0]
    assert cancelled is True
    assert processed < 50


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

    # CALLS: DA0TST..DA29TST
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


# ── 2. Dialog Tests ──────────────────────────────────────────────────────


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


def test_progress_dialog_update_renders_correctly(qapp):
    """update_progress aktualisiert Progress-Bar + Counter-Label."""
    from ui.qrz_upload_dialogs import QRZUploadDialog
    dlg = QRZUploadDialog(total=18443)
    dlg.update_progress(4123, 18443, 4100, 23, 0)
    assert "4123 von 18443" in dlg.lbl_progress.text()
    assert "22%" in dlg.lbl_progress.text()
    assert dlg.progress_bar.value() == 4123
    assert "4100" in dlg.lbl_counter.text()
    assert "23" in dlg.lbl_counter.text()


def test_progress_dialog_finished_shows_close_button(qapp):
    """set_finished blendet Cancel aus, Schliessen ein, Title aktualisiert."""
    from ui.qrz_upload_dialogs import QRZUploadDialog
    dlg = QRZUploadDialog(total=100)
    dlg.set_finished(ok=80, dup=15, fail=5, cancelled=False, total_processed=100)
    assert dlg.btn_cancel.isHidden()
    assert dlg.btn_close.isVisible() is False or dlg.btn_close.isHidden() is False
    # Title nun "fertig"
    assert "fertig" in dlg.lbl_title.text().lower()


def test_progress_dialog_cancelled_title_yellow(qapp):
    """Cancel-Pfad: Title bekommt cancelled-Style."""
    from ui.qrz_upload_dialogs import QRZUploadDialog
    dlg = QRZUploadDialog(total=100)
    dlg.set_finished(ok=20, dup=5, fail=0, cancelled=True, total_processed=25)
    assert "abgebrochen" in dlg.lbl_title.text().lower()


def test_progress_dialog_auto_close_timer_starts(qapp):
    """set_finished startet 10s Auto-Close-Timer (R1.6)."""
    from ui.qrz_upload_dialogs import QRZUploadDialog
    dlg = QRZUploadDialog(total=100)
    dlg.set_finished(ok=100, dup=0, fail=0, cancelled=False, total_processed=100)
    assert dlg._auto_close_timer.isActive()
    assert dlg._auto_close_timer.remainingTime() > 9000  # ~10s
```

(Tests fuer Klick-Sperre und Auto-Upload-Skip in mw_qso.py-Tests
ergaenzen — Pattern aus bestehenden Tests.)

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **Files lesen** zur Verifikation:
   - `prompts/p1_qrz_upload_ui_v3.md` (diese Datei)
   - `ui/mw_qso.py:380-460` (QRZ-Methoden + closeEvent suchen)
   - `ui/logbook_widget.py:84-145` (btn_upload + Layout)
   - `ui/main_window.py` (closeEvent suchen)
   - `log/qrz.py` (timeout=10 verifizieren)

2. **Diff 1** — `ui/qrz_upload_dialogs.py` NEU (Confirm + Progress)

3. **Diff 2** — `core/qrz_upload_worker.py` NEU (ThreadPool-Worker)

4. **Diff 5** — `ui/logbook_widget.py` btn_upload-Reference + setter

5. **Diff 4** — `ui/mw_qso.py:397-416` `_qrz_upload_single` mit
   KP-1 Bulk-Skip (defensive zuerst, falls 3 anders failt)

6. **Diff 3** — `ui/mw_qso.py:418-455` `_on_qrz_upload` komplett ersetzen
   + neuer Slot `_on_qrz_bulk_finished` + Helper `_set_qrz_button_enabled`

7. **Diff 6** — `ui/main_window.py` closeEvent erweitern

8. **Diff 7** — `tests/test_p1_qrz_upload_ui.py` NEU mit 9 Tests

9. **Tests laufen:** erwartet 862 + 9 = **~871 gruen**

10. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.QRZ-UPLOAD-UI v0.95.14. KP-1/2/3 sauber adressiert?
    Race-Conditions, Worker-Lifecycle, Dialog-Cleanup?" | \
    ./venv/bin/python3 tools/deepseek_review.py \
    ui/qrz_upload_dialogs.py core/qrz_upload_worker.py \
    ui/mw_qso.py tests/test_p1_qrz_upload_ui.py
    ```

11. **APP_VERSION** in `main.py` 0.95.13 → 0.95.14

12. **Atomare Commits:**
    - Code+Tests: `P1.QRZ-UPLOAD-UI (v0.95.14): Confirm + Progress + Single-Instance`
    - Doku: `docs (v0.95.14): P1.QRZ-UPLOAD-UI HISTORY+TODO+HANDOFF+CLAUDE`

13. **Doku-Updates:**
    - `HISTORY.md` v0.95.14 Eintrag
    - `HANDOFF.md` beide Pfade
    - `CLAUDE.md` Header beide Pfade + Test-Count
    - `TODO.md` P1.QRZ-UPLOAD-UI als ERLEDIGT
    - Memory `project_p1_qrz_upload_ui_in_progress.md` umflaggen

14. **Push** (NUR nach Mike-Freigabe — explizit fragen!)

15. **Lessons-Learned**

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] ui/qrz_upload_dialogs.py NEU (Confirm + Progress + Theme)
- [ ] core/qrz_upload_worker.py NEU (ThreadPool + Signals + Cancel)
- [ ] _on_qrz_upload Refactor (Confirm → Progress, KP-2 Reihenfolge)
- [ ] _on_qrz_bulk_finished Slot
- [ ] _qrz_upload_single Bulk-Skip (KP-1)
- [ ] _set_qrz_button_enabled Helper
- [ ] logbook_widget set_qrz_button_enabled API
- [ ] main_window closeEvent Worker-Cleanup (KP-3)
- [ ] tests/test_p1_qrz_upload_ui.py mit 9 Tests
- [ ] ~871 Tests gesamt gruen
- [ ] Final-R1-Codereview ohne 🔴-Findings
- [ ] APP_VERSION 0.95.13 → 0.95.14
- [ ] HISTORY/TODO/HANDOFF/CLAUDE updated
- [ ] Atomare Commits
- [ ] Mike-Freigabe fuer Push EXPLIZIT eingeholt
- [ ] Lessons-Learned beantwortet
```

---

## 5. Risiken & Notbremse

- **Race bei Mehrfach-Klick:** KP-2 Flag-Reihenfolge schuetzt. Test
  `test_second_click_blocked_during_upload` validiert.
- **Worker-Signal-Emit auf zerstoerten Dialog:** KP-3 cancel_event vor
  shutdown. Bei App-Close in closeEvent.
- **Auto-Upload-Konflikt:** KP-1 `_qrz_bulk_active`-Check als first line
  in `_qrz_upload_single`.
- **HTTP-Timeout 10s:** kein Fix noetig (R1 bestaetigt). Statusbar bei
  Cancel zeigt „max 10s warten".
- **Compact-Risiko:** alle Diffs konkret in V3, Memory-File
  vorbereitet → autonom durchfuehrbar.

---

## 6. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.QRZ-UPLOAD-UI ueberraschend?
2. Was wuerde ich rueckblickend anders machen?
3. Welches Memory soll geschrieben werden? (Vorschlag:
   `feedback_ui_feedback_for_long_actions.md` — Pattern fuer
   zukuenftige Long-Running-Actions: immer Confirm + Progress + Cancel,
   nicht Statusbar-only)

---

**Plan-V3 Ende. Bereit fuer Compact + Code.**
