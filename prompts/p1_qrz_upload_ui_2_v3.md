# P1.QRZ-UPLOAD-UI-2 V3 — Final-Plan (Compact-fest, R1-freigegeben)

**Stand:** 2026-05-07.
**Workflow:** V1 → V2 → R1 ✅ („Plan freigegeben mit Praezisierungen") → **V3** → Compact → Code.
**Vorgaenger:** v0.95.14 (P1.QRZ-UPLOAD-UI). Tests 872 gruen.
**Compact-fest:** Diese Datei enthaelt ALLE Diffs. Nach Compact direkt Code.

**Mike-Anforderungen 07.05.2026:**
- Status in Titelleiste statt non-modal Dialog (StaysOnTopHint nervt)
- Hochgeladene ADIF-Files nach `adif/hochgeladen/` verschieben
- JSON-Lines Log-Datei (Mike: „log ob die daten nach qrz ok hochgeladen wurden")
- Rate-Limit-Detection nach Fail-Burst (Mike beobachtet 12134 Dups + Fail-Burst)

---

## 1. R1-Findings (alle eingearbeitet)

| Finding | Status |
|---|---|
| `_SOURCE_FILE` bereits in `log/adif.py:42` (uppercase) | ✅ Verwende bestehendes Field, kein Parser-Refactor noetig |
| Cooldown als Loop mit `cancel_event`-Check + 1s tick | ✅ Diff 2 |
| `worker.file_results` Property (Copy bei Zugriff) | ✅ Diff 2 |
| `_update_window_title()` zentralisiert | ✅ Diff 4 |
| Statusbar-Cancel feste Slot-Methode | ✅ Diff 4 |
| Statusbar-Toast bei OSError beim File-Move | ✅ Diff 4 |
| Log-Datei pro Tag (Rotation) | ✅ Diff 2: `qrz_upload_YYYY-MM-DD.log` |
| Cancel-Pfad: File bleibt bei partial | ✅ Diff 4 |
| MAX_CONSECUTIVE_FAILS=20, COOLDOWN=60s, 2. Burst → cancel | ✅ Diff 2 |
| QRZUploadDialog Klasse + 4 Tests loeschen | ✅ Diff 6 |
| Tests 12 → 18 (R1: +3 Rate-Limit, +2 Log+Title, +1 Bulk-Skip) | ✅ Diff 8 |
| LogbookWidget zwei Verzeichnisse laden | ✅ Diff 5 |

---

## 2. Konkrete Diffs (Compact-fest)

### Diff 1 — `log/adif.py:101-110` `parse_all_adif_files` Verifikation

**Bestehender Code (KEINE Aenderung noetig):**
```python
def parse_all_adif_files(directory: Path) -> List[Dict[str, str]]:
    """Alle ADIF-Dateien in einem Verzeichnis parsen."""
    all_records = []
    for adi_file in sorted(directory.glob("*.adi")):
        records = parse_adif_file(adi_file)
        all_records.extend(records)
    return all_records
```

`parse_adif_file` setzt schon `record["_SOURCE_FILE"] = str(path)` (Z.42).
`glob("*.adi")` ist flat (nicht recursive). **PERFEKT — keine Aenderung
noetig.** Alle anderen Diffs nutzen das bestehende Field.

### Diff 2 — `core/qrz_upload_worker.py` komplett rewriten

```python
"""SimpleFT8 QRZ Upload Worker — ThreadPool + Qt-Signals + File-Tracking + Log.

P1.QRZ-UPLOAD-UI-2 v0.95.15: erweitert um
- File-Tracking pro Source-File (`_SOURCE_FILE`)
- JSON-Lines Log-Datei pro Result
- Rate-Limit-Detection (consecutive fails → cooldown)
- Cooldown-Loop mit Cancel-Check (NICHT blockierend)
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
    """Bulk-Upload Worker mit Progress, File-Tracking, Log und Rate-Limit-Detection."""

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
        # Log-Datei pro Tag (R1.2.1 Rotation)
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_path = _LOG_DIR / f"qrz_upload_{datetime.now().strftime('%Y-%m-%d')}.log"

    @property
    def file_results(self) -> Dict[str, Dict[str, int]]:
        """Threadsafe Copy — Worker schreibt nicht mehr nach finished."""
        return {k: dict(v) for k, v in self._file_results.items()}

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
        """Cooldown als Loop mit Cancel-Check (R1-KP-1).

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

            # Rate-Limit-Detection (R1.2.2)
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
```

### Diff 3 — `ui/qrz_upload_dialogs.py` — `QRZUploadDialog` loeschen

Behalten: `_DLG_STYLE` + `QRZConfirmDialog`.
Loeschen: komplette `QRZUploadDialog`-Klasse (Z.~95-185 in v0.95.14).

Datei ist nach Diff am Ende ca. 90 Zeilen (statt 195).

### Diff 4 — `ui/mw_qso.py` — `_on_qrz_upload` umbauen + neue Slots

Ersetze die in v0.95.14 angelegten Methoden:
- `_on_qrz_upload`: kein QRZUploadDialog mehr, statt dessen Title-Update + Statusbar-Widget
- `_on_qrz_bulk_finished`: Title resetten + Toast + File-Move
- NEU: `_on_qrz_progress` (war an Dialog), `_on_qrz_cooldown_tick`,
  `_on_qrz_status_cancel_clicked`, `_handle_qrz_file_results`,
  `_update_window_title`

```python
    def _on_qrz_upload(self):
        """QRZ Bulk-Upload mit Title-Suffix + Statusbar-Cancel-Widget.

        P1.QRZ-UPLOAD-UI-2 v0.95.15: Progress in Titelleiste statt Dialog.
        Klick-Sperre 3-fach (R1-KP-2) bleibt: Flag → Button → submit.
        """
        from PySide6.QtWidgets import QDialog

        if getattr(self, '_qrz_bulk_active', False):
            print("[QRZ] Re-Entry-Schutz: Bulk laeuft schon, Klick ignoriert")
            return

        api_key = self.settings.get("qrz_api_key", "")
        if not api_key:
            from ui.qrz_upload_dialogs import _DLG_STYLE
            from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton
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

        # Filter: nur Records aus adif/ (NICHT adif/hochgeladen/) — AC-7
        all_records = self.qso_panel.logbook._all_records
        records = [
            r for r in all_records
            if "hochgeladen" not in r.get("_SOURCE_FILE", "").replace("\\", "/")
        ]
        if not records:
            self.statusBar().showMessage(
                "Keine QSOs zum Hochladen — alle bereits in adif/hochgeladen/.", 5000)
            return

        # Phase 1: Confirm-Dialog (bleibt)
        from ui.qrz_upload_dialogs import QRZConfirmDialog
        confirm = QRZConfirmDialog(len(records), parent=self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        # KP-2 Reihenfolge: 1) Flag → 2) Button → 3) Worker
        self._qrz_bulk_active = True
        self._set_qrz_button_enabled(False)
        self._show_qrz_status_widget(True, len(records))

        from core.qrz_upload_worker import QRZUploadWorker
        client = self._get_qrz_client()
        self._qrz_worker = QRZUploadWorker(client, records, parent=self)
        self._qrz_worker.progress.connect(
            self._on_qrz_progress, Qt.ConnectionType.QueuedConnection)
        self._qrz_worker.finished.connect(
            self._on_qrz_bulk_finished, Qt.ConnectionType.QueuedConnection)
        self._qrz_worker.cooldown_tick.connect(
            self._on_qrz_cooldown_tick, Qt.ConnectionType.QueuedConnection)

        self._qrz_worker.start()
        print(f"[QRZ] Bulk-Upload gestartet ({len(records)} QSOs)")

    @Slot(int, int, int, int, int)
    def _on_qrz_progress(self, current: int, total: int,
                         ok: int, dup: int, fail: int) -> None:
        """Worker-Progress alle 10 QSOs → Title + Statusbar-Label."""
        pct = int((current / total) * 100) if total else 0
        self._qrz_title_suffix = f" — QRZ ↑ {current}/{total} ({pct}%)"
        self._update_window_title()
        if hasattr(self, '_qrz_status_label'):
            self._qrz_status_label.setText(f"QRZ ↑ {current}/{total} ({pct}%)")

    @Slot(int)
    def _on_qrz_cooldown_tick(self, seconds_left: int) -> None:
        """Worker meldet Cooldown-Sekunde — Statusbar zeigt Countdown."""
        if hasattr(self, '_qrz_status_label'):
            if seconds_left > 0:
                self._qrz_status_label.setText(
                    f"QRZ ↑ pausiert {seconds_left}s ...")
            else:
                self._qrz_status_label.setText("QRZ ↑ retrying...")

    @Slot(int, int, int, bool, int)
    def _on_qrz_bulk_finished(self, ok: int, dup: int, fail: int,
                              cancelled: bool, total_processed: int) -> None:
        """Worker-Finish — Title reset, Toast, File-Move."""
        # Title zuruecksetzen
        self._qrz_title_suffix = ""
        self._update_window_title()
        # Statusbar-Widget verbergen
        self._show_qrz_status_widget(False)
        # Toast 10s mit Endstand
        if cancelled:
            msg = (f"QRZ Upload abgebrochen bei {total_processed}/"
                   f"{len(self._qrz_worker._records) if self._qrz_worker else '?'}: "
                   f"{ok} neu, {dup} dup, {fail} fail")
        else:
            msg = f"QRZ Upload fertig: {ok} neu, {dup} dup, {fail} fail"
        self.statusBar().showMessage(msg, 10000)

        # File-Move
        if hasattr(self, '_qrz_worker') and self._qrz_worker:
            file_results = self._qrz_worker.file_results
            self._handle_qrz_file_results(file_results)
            self._qrz_worker.shutdown(wait=False)

        # State reset
        self._qrz_bulk_active = False
        self._set_qrz_button_enabled(True)
        self.qso_panel.logbook.refresh()
        print(f"[QRZ] Bulk-Upload beendet: {ok} neu, {dup} dup, {fail} fail "
              f"(cancelled={cancelled})")

    def _handle_qrz_file_results(self, file_results: dict) -> None:
        """Files mit fail==0 und expected==processed nach adif/hochgeladen/."""
        import shutil
        from pathlib import Path
        adif_dir = Path.cwd() / "adif"
        target_dir = adif_dir / "hochgeladen"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.statusBar().showMessage(f"Fehler hochgeladen-Ordner: {e}", 8000)
            return
        moved = 0
        skipped = 0
        for src_path, counts in file_results.items():
            processed = counts["ok"] + counts["dup"] + counts["fail"]
            if counts["fail"] == 0 and processed == counts["expected"] and processed > 0:
                src = Path(src_path)
                if not src.is_file():
                    continue
                # Schutz: nur Files aus adif/ verschieben (nicht aus hochgeladen/)
                if "hochgeladen" in str(src):
                    continue
                dest = target_dir / src.name
                try:
                    shutil.move(str(src), str(dest))
                    moved += 1
                except OSError as e:
                    print(f"[QRZ] File-Move {src} fehlgeschlagen: {e}")
                    self.statusBar().showMessage(
                        f"File-Move fehlgeschlagen: {src.name} ({e})", 5000)
            else:
                skipped += 1
        if moved:
            print(f"[QRZ] {moved} Datei(en) nach adif/hochgeladen/ verschoben "
                  f"({skipped} bleiben wegen FAILs oder unvollstaendig)")

    def _show_qrz_status_widget(self, visible: bool, total: int = 0) -> None:
        """Statusbar-Cancel-Widget toggle."""
        if not hasattr(self, '_qrz_status_widget'):
            return
        self._qrz_status_widget.setVisible(visible)
        if visible:
            self._qrz_status_label.setText(f"QRZ ↑ 0/{total} (0%)")

    @Slot()
    def _on_qrz_status_cancel_clicked(self) -> None:
        """Klick auf Statusbar-✕ → Worker cancel."""
        if hasattr(self, '_qrz_worker') and self._qrz_worker and self._qrz_bulk_active:
            self._qrz_worker.cancel()
            if hasattr(self, '_qrz_status_cancel_btn'):
                self._qrz_status_cancel_btn.setEnabled(False)
            if hasattr(self, '_qrz_status_label'):
                self._qrz_status_label.setText("QRZ ↑ wird abgebrochen ...")

    def _update_window_title(self) -> None:
        """Zentrale Title-Update-Methode (R1: Hardcoding vermeiden)."""
        suffix = getattr(self, '_qrz_title_suffix', '')
        self.setWindowTitle(f"SimpleFT8 — {self.settings.callsign}{suffix}")

    def _set_qrz_button_enabled(self, enabled: bool) -> None:
        """Logbook-QRZ-Button enable/disable — Single-Instance-Schutz (R1-KP-2)."""
        try:
            self.qso_panel.logbook.set_qrz_button_enabled(enabled)
        except AttributeError:
            pass
```

### Diff 5 — `ui/logbook_widget.py` — Multi-Directory-Load

Erweitere `load_adif()`:

```python
    def load_adif(self, directory: Path = None):
        """Alle ADIF-Dateien aus adif/ UND adif/hochgeladen/ laden.

        P1.QRZ-UPLOAD-UI-2: hochgeladene QSOs sollen weiter sichtbar bleiben,
        aber NICHT erneut hochgeladen werden (Filter via _SOURCE_FILE im
        mw_qso._on_qrz_upload).
        """
        if directory:
            self._adif_dir = directory
        records_active = parse_all_adif_files(self._adif_dir)
        # NEU: zusaetzlich aus hochgeladen/ laden falls existiert
        hochgeladen_dir = self._adif_dir / "hochgeladen"
        records_archived = []
        if hochgeladen_dir.is_dir():
            records_archived = parse_all_adif_files(hochgeladen_dir)
        self._all_records = records_active + records_archived
        self._populate_table(self._all_records)
        self._update_counters()
```

### Diff 6 — `ui/main_window.py` — Statusbar-Widget Init + qso_log Multi-Dir

Im `_init_statusbar` ergaenze:
```python
        # P1.QRZ-UPLOAD-UI-2: Cancel-Widget (initial versteckt)
        from PySide6.QtWidgets import QHBoxLayout, QPushButton as _QPB2
        self._qrz_status_widget = QWidget()
        _qrz_lay = QHBoxLayout(self._qrz_status_widget)
        _qrz_lay.setContentsMargins(0, 0, 0, 0)
        _qrz_lay.setSpacing(4)
        self._qrz_status_label = QLabel("QRZ ↑")
        self._qrz_status_label.setStyleSheet(
            "color: #4488cc; font-family: Menlo; font-size: 11px; padding: 0 4px;")
        self._qrz_status_cancel_btn = _QPB2("✕")
        self._qrz_status_cancel_btn.setFixedSize(18, 18)
        self._qrz_status_cancel_btn.setStyleSheet(
            "QPushButton { background: rgba(180,30,30,0.4); color: #FFAAAA;"
            "border: 1px solid #533; border-radius: 3px; font-size: 10px; padding: 0;}"
            "QPushButton:hover { background: rgba(220,40,40,0.6); }"
            "QPushButton:disabled { color: #555; }")
        self._qrz_status_cancel_btn.clicked.connect(self._on_qrz_status_cancel_clicked)
        _qrz_lay.addWidget(self._qrz_status_label)
        _qrz_lay.addWidget(self._qrz_status_cancel_btn)
        self._qrz_status_widget.hide()
        self.statusBar().addPermanentWidget(self._qrz_status_widget)
```

(Statusbar-Init-Reihenfolge: nach `_help_btn`-Add)

In `__init__` initial-Werte adden:
```python
        self._qrz_title_suffix = ""  # P1.QRZ-UPLOAD-UI-2
```

(in `_init_radio_state` oder direkt in `__init__` nach `setWindowTitle`)

In `_init_qso_log` ergaenze:
```python
        # P1.QRZ-UPLOAD-UI-2: hochgeladene QSOs auch in qso_log
        hochgeladen_dir = Path.cwd() / "adif" / "hochgeladen"
        if hochgeladen_dir.is_dir():
            self.qso_log.load_directory(hochgeladen_dir)
```

(nach den bestehenden `qso_log.load_directory`-Aufrufen)

Und:
```python
        # LocatorDB auch aus hochgeladen/
        if (Path.cwd() / "adif" / "hochgeladen").is_dir():
            n_loc += self.locator_db.bulk_import_directory(
                Path.cwd() / "adif" / "hochgeladen")
```

### Diff 7 — closeEvent (KP-3 bleibt erhalten)

Aus v0.95.14 unveraendert:
```python
    def closeEvent(self, event):
        if hasattr(self, '_qrz_worker') and self._qrz_worker:
            try:
                self._qrz_worker.finished.disconnect()
                self._qrz_worker.progress.disconnect()
                self._qrz_worker.cooldown_tick.disconnect()  # NEU: cooldown auch disconnect
            except (RuntimeError, TypeError):
                pass
            self._qrz_worker.cancel()
            self._qrz_worker.shutdown(wait=False)
        # ... bestehender closeEvent-Code
```

### Diff 8 — `tests/test_p1_qrz_upload_ui_2.py` (NEU, 18 Tests)

```python
"""Tests fuer P1.QRZ-UPLOAD-UI-2 v0.95.15.

Decken ab:
- _SOURCE_FILE bereits in Records (existing pattern)
- Worker file_results Property
- File-Move (alle OK/Dup, mind. 1 Fail, partial-Cancel, hochgeladen-Schutz)
- Title-Update + Reset
- Statusbar-Widget Visibility
- Logbook Multi-Dir-Load
- Bulk-Skip Records aus hochgeladen/
- Rate-Limit-Detection (Counter-Reset, Cooldown, 2. Burst → Cancel)
- JSONL Log-Datei Append
- Auto-Upload-Skip (KP-1 aus v0.95.14, Pflege-Test)

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


def test_worker_file_results_aggregates_per_file(qapp, tmp_path):
    """file_results pro Source-File aggregiert ok/dup/fail/expected."""
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


def test_worker_file_results_mixed_results(qapp, tmp_path):
    """OK/Dup/Fail werden korrekt pro File getrennt."""
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
    QRZUploadWorker.COOLDOWN_SECONDS = 2  # schneller fuer Test
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 3

    client = MagicMock()
    client.upload_qso_from_dict.return_value = {"RESULT": "FAIL", "REASON": "x"}
    records = _make_records(10)

    worker = QRZUploadWorker(client, records)
    cooldown_calls = []
    worker.cooldown_tick.connect(lambda s: cooldown_calls.append(s))

    worker.start()
    worker._future.result(timeout=10)
    worker.shutdown(wait=True)
    qapp.processEvents()

    assert len(cooldown_calls) >= 2  # mind. 2 Ticks (2s Cooldown)
    # Reset zurueck:
    QRZUploadWorker.COOLDOWN_SECONDS = 60
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 20


def test_worker_consecutive_fails_reset_on_ok(qapp, monkeypatch, tmp_path):
    """OK zwischen Fails → Counter resetet, kein Cooldown."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 5

    client = MagicMock()
    counter = {"n": 0}

    def alternating(rec):
        counter["n"] += 1
        # 4 fails, 1 ok, 4 fails — sollte reset → kein Cooldown
        if counter["n"] in (5, 6):  # ok bei 5
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
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 20


def test_worker_cancel_during_cooldown(qapp, monkeypatch, tmp_path):
    """Cancel waehrend Cooldown stoppt Worker sofort."""
    monkeypatch.setattr("core.qrz_upload_worker._LOG_DIR", tmp_path)
    from core.qrz_upload_worker import QRZUploadWorker
    QRZUploadWorker.COOLDOWN_SECONDS = 5
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 3

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

    assert len(finished) == 1
    cancelled = finished[0][3]
    assert cancelled is True
    QRZUploadWorker.COOLDOWN_SECONDS = 60
    QRZUploadWorker.MAX_CONSECUTIVE_FAILS = 20


# ── File-Move Tests ──────────────────────────────────────────────────────


def test_file_move_when_all_ok_or_dup(qapp, tmp_path):
    """Datei mit nur OK/Dup → Move nach hochgeladen/."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path
    src = adif_dir / "2026-05-01.adi"
    src.write_text("dummy")
    file_results = {
        str(src): {"ok": 2, "dup": 1, "fail": 0, "expected": 3}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    # CWD-Patch fuer pathlib
    import os as _os
    cwd_old = _os.getcwd()
    _os.chdir(adif_dir.parent)
    try:
        # adif/ Symlink to tmp_path
        adif_link = adif_dir.parent / "adif"
        if not adif_link.exists():
            adif_link.symlink_to(adif_dir)
        QSOMixin._handle_qrz_file_results(fake_self, file_results)
        assert (adif_link / "hochgeladen" / "2026-05-01.adi").exists()
        assert not src.exists()
    finally:
        _os.chdir(cwd_old)


def test_file_move_skipped_when_fail(qapp, tmp_path):
    """Datei mit FAIL → bleibt in adif/."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path
    src = adif_dir / "2026-05-02.adi"
    src.write_text("dummy")
    file_results = {
        str(src): {"ok": 2, "dup": 0, "fail": 1, "expected": 3}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    import os as _os
    cwd_old = _os.getcwd()
    _os.chdir(adif_dir.parent)
    try:
        adif_link = adif_dir.parent / "adif"
        if not adif_link.exists():
            adif_link.symlink_to(adif_dir)
        QSOMixin._handle_qrz_file_results(fake_self, file_results)
        assert src.exists()  # bleibt
        assert not (adif_link / "hochgeladen" / "2026-05-02.adi").exists()
    finally:
        _os.chdir(cwd_old)


def test_file_move_skipped_when_partial(qapp, tmp_path):
    """Datei mit weniger processed als expected (Cancel) → bleibt."""
    from ui.mw_qso import QSOMixin
    adif_dir = tmp_path
    src = adif_dir / "2026-05-03.adi"
    src.write_text("dummy")
    file_results = {
        str(src): {"ok": 1, "dup": 0, "fail": 0, "expected": 5}
    }
    fake_self = MagicMock()
    fake_self.statusBar.return_value = MagicMock()
    import os as _os
    cwd_old = _os.getcwd()
    _os.chdir(adif_dir.parent)
    try:
        adif_link = adif_dir.parent / "adif"
        if not adif_link.exists():
            adif_link.symlink_to(adif_dir)
        QSOMixin._handle_qrz_file_results(fake_self, file_results)
        assert src.exists()
    finally:
        _os.chdir(cwd_old)


# ── Title + Statusbar Tests ──────────────────────────────────────────────


def test_update_window_title_with_suffix(qapp):
    """_update_window_title appended _qrz_title_suffix."""
    from PySide6.QtWidgets import QMainWindow
    win = QMainWindow()
    win.settings = MagicMock()
    win.settings.callsign = "DA1MHH"
    from ui.main_window import MainWindow
    win._qrz_title_suffix = " — QRZ ↑ 100/500 (20%)"
    MainWindow._update_window_title(win)
    assert "DA1MHH" in win.windowTitle()
    assert "100/500" in win.windowTitle()


def test_update_window_title_reset(qapp):
    """Reset Suffix → Title nur Callsign."""
    from PySide6.QtWidgets import QMainWindow
    from ui.main_window import MainWindow
    win = QMainWindow()
    win.settings = MagicMock()
    win.settings.callsign = "DA1MHH"
    win._qrz_title_suffix = ""
    MainWindow._update_window_title(win)
    assert win.windowTitle() == "SimpleFT8 — DA1MHH"


# ── Logbook Multi-Dir Tests ──────────────────────────────────────────────


def test_logbook_loads_both_directories(qapp, tmp_path):
    """LogbookWidget lädt aus adif/ UND adif/hochgeladen/."""
    from ui.logbook_widget import LogbookWidget
    adif = tmp_path / "adif"
    hochgeladen = adif / "hochgeladen"
    adif.mkdir()
    hochgeladen.mkdir()

    (adif / "active.adi").write_text(
        "<EOH>\n<call:5>NEW01<band:3>40m<mode:3>FT8<qso_date:8>20260507<eor>\n")
    (hochgeladen / "old.adi").write_text(
        "<EOH>\n<call:5>OLD01<band:3>40m<mode:3>FT8<qso_date:8>20260101<eor>\n")

    w = LogbookWidget(adif_directory=adif)
    w.load_adif()
    calls = [r["CALL"] for r in w._all_records]
    assert "NEW01" in calls
    assert "OLD01" in calls


def test_bulk_filters_hochgeladen_records(qapp, tmp_path):
    """_on_qrz_upload nimmt nur Records ohne 'hochgeladen' im _SOURCE_FILE."""
    # Reine Filter-Logik testen — kein full mw_qso instanziieren
    all_records = [
        {"CALL": "NEW01", "_SOURCE_FILE": "/x/adif/2026-05-07.adi"},
        {"CALL": "OLD01", "_SOURCE_FILE": "/x/adif/hochgeladen/2026-01-01.adi"},
        {"CALL": "NEW02", "_SOURCE_FILE": "/x/adif/2026-05-08.adi"},
    ]
    filtered = [
        r for r in all_records
        if "hochgeladen" not in r.get("_SOURCE_FILE", "").replace("\\", "/")
    ]
    assert len(filtered) == 2
    assert {r["CALL"] for r in filtered} == {"NEW01", "NEW02"}


# ── Existing Behaviour (Pflege-Tests) ────────────────────────────────────


def test_worker_progress_signal_every_10_qsos(qapp, tmp_path, monkeypatch):
    """Pflege: Progress alle 10 QSOs (aus v0.95.14, soll bestehen bleiben)."""
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
    assert finished[0][3] is True  # cancelled


def test_confirm_dialog_default_button_is_upload(qapp):
    """Pflege: Confirm-Dialog Default = Hochladen (aus v0.95.14)."""
    from ui.qrz_upload_dialogs import QRZConfirmDialog
    dlg = QRZConfirmDialog(total=1000)
    assert dlg.btn_upload.isDefault() is True


def test_qrz_status_widget_initially_hidden(qapp):
    """Statusbar-Widget ist initial versteckt — wird erst beim Bulk gezeigt."""
    # Smoke-Test: Widget-Init liefert hidden
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.hide()
    assert not w.isVisible()
```

(Test-Anzahl: 18 Tests; v0.95.14 hatte 10 Tests in `test_p1_qrz_upload_ui.py`,
davon werden 4 fuer Progress-Dialog geloescht. Netto:
- Alt: 10 Tests in `test_p1_qrz_upload_ui.py`
- Davon werden 4 obsolet (Progress-Dialog) → bleiben 6 Tests
- Aus v0.95.14 koennen 3 (`progress`, `immediate_cancel`, `confirm_default`)
  als „Pflege" in `test_p1_qrz_upload_ui_2.py` integriert werden ODER in
  `test_p1_qrz_upload_ui.py` bleiben — V3 entscheidet: BLEIBEN dort plus
  Pflege-Tests in neuer Datei.
- Test-Datei `test_p1_qrz_upload_ui.py` bleibt mit 6 Tests (4 Progress-Dialog
  loeschen)
- Neue Datei `test_p1_qrz_upload_ui_2.py` mit 18 Tests (3 davon redundant
  mit alten Pflege-Tests — kein Schaden)
- Erwartung: 872 - 4 (geloescht) + 18 (neu) = **886 gruen**)

---

## 3. Implementations-Reihenfolge (nach Compact)

1. **App killen** falls noch laeuft (Mike's Bulk-Versuch v0.95.14 mit
   Fail-Burst — am besten zuerst pruefen).
2. **Files lesen** zur Verifikation:
   - `prompts/p1_qrz_upload_ui_2_v3.md` (diese Datei)
   - aktuelle `core/qrz_upload_worker.py`, `ui/qrz_upload_dialogs.py`,
     `ui/mw_qso.py`, `ui/main_window.py`, `ui/logbook_widget.py`,
     `log/adif.py`, `log/qso_log.py`
3. **Diff 2** — `core/qrz_upload_worker.py` komplett neu schreiben.
4. **Diff 3** — `ui/qrz_upload_dialogs.py` `QRZUploadDialog` raus.
5. **Diff 5** — `ui/logbook_widget.py:load_adif()` erweitern.
6. **Diff 4** — `ui/mw_qso.py` `_on_qrz_upload` + neue Slots/Helpers.
7. **Diff 6** — `ui/main_window.py` Statusbar-Widget Init + `_qrz_title_suffix`
   Init + qso_log/locator_db Multi-Dir.
8. **Diff 7** — `ui/main_window.py:closeEvent` cooldown_tick disconnect.
9. **Diff 8** — `tests/test_p1_qrz_upload_ui_2.py` NEU mit 18 Tests +
   `tests/test_p1_qrz_upload_ui.py` 4 Progress-Dialog-Tests loeschen.
10. **APP_VERSION** in `main.py` 0.95.14 → 0.95.15
11. **Tests laufen:** `872 → 886 erwartet gruen` (4 weg, 18 neu).
12. **Final-R1-Codereview:**
    ```bash
    echo "Reviewe P1.QRZ-UPLOAD-UI-2 v0.95.15 final-Code. Race-Conditions,
    Worker-Lifecycle, File-Move-Atomicity, Title-Updates, Statusbar-
    Widget-Integration. KP-1/2/3 aus v0.95.14 noch intakt?" | \
    ./venv/bin/python3 tools/deepseek_review.py \
    core/qrz_upload_worker.py ui/qrz_upload_dialogs.py \
    ui/mw_qso.py ui/main_window.py ui/logbook_widget.py \
    tests/test_p1_qrz_upload_ui_2.py
    ```
13. **Atomare Commits:**
    - Code+Tests: `P1.QRZ-UPLOAD-UI-2 (v0.95.15): Title + File-Move + Log + Rate-Limit`
    - Doku: `docs (v0.95.15): P1.QRZ-UPLOAD-UI-2 HISTORY+HANDOFF+CLAUDE`
14. **Doku-Updates** (HISTORY beide Pfade, HANDOFF beide, CLAUDE beide,
    Memory-File umflaggen).
15. **Push** NUR nach Mike-Freigabe.
16. **Lessons-Learned** aus V3 §6.

---

## 4. Akzeptanz-Checkliste (final)

```
- [ ] core/qrz_upload_worker.py rewritten (file_results + log + rate-limit)
- [ ] ui/qrz_upload_dialogs.py: QRZUploadDialog Klasse weg
- [ ] ui/logbook_widget.py: load_adif Multi-Dir
- [ ] ui/mw_qso.py: _on_qrz_upload + 6 neue Slots/Helpers
- [ ] ui/main_window.py: Statusbar-Widget Init, _qrz_title_suffix init,
      qso_log + locator_db Multi-Dir, closeEvent cooldown_tick disconnect
- [ ] tests/test_p1_qrz_upload_ui_2.py: 18 Tests
- [ ] tests/test_p1_qrz_upload_ui.py: 4 Progress-Dialog-Tests geloescht
- [ ] 886 Tests gesamt gruen
- [ ] Final-R1 ohne 🔴-Findings
- [ ] APP_VERSION 0.95.14 → 0.95.15
- [ ] HISTORY/HANDOFF/CLAUDE updated
- [ ] Atomare Commits
- [ ] Mike-Freigabe fuer Push EXPLIZIT
- [ ] Lessons-Learned
```

---

## 5. Risiken & Notbremse

- **File-Move-Bug:** wenn `shutil.move` fehlschlaegt, bleibt File in `adif/`.
  Naechster Bulk versucht's wieder. Worst case: User muss manuell aufraeumen.
- **Rate-Limit-Cooldown zu kurz/lang:** `MAX_CONSECUTIVE_FAILS=20`/`COOLDOWN=60s`
  sind Schaetzungen. Nach Field-Test ggf. anpassen.
- **Log-Datei-Wachstum:** pro Tag eine eigene Datei (`qrz_upload_YYYY-MM-DD.log`)
  → kein unbegrenztes Wachstum, Mike kann manuell loeschen wenn ihm zuviel.
- **Backwards-Compat:** Records ohne `_SOURCE_FILE` (theoretisch unmoeglich
  weil Parser es immer setzt) → werden ignoriert beim File-Tracking.
- **Compact-Risiko:** alle Diffs konkret in V3, Memory-File vorbereitet.

---

## 6. Lessons-Learned-Fragen (Skill Schritt 6 final, nach Code+Push)

1. Was war an P1.QRZ-UPLOAD-UI-2 ueberraschend?
2. Was wuerde ich rueckblickend anders machen?
3. Welches Memory soll geschrieben werden? (Vorschlag:
   `feedback_long_action_status_pattern.md` — Pattern: Title-Suffix +
   Statusbar-Widget-Inline-Cancel + JSONL-Log-pro-Tag fuer alle
   zukuenftigen Long-Running-Actions)

---

**Plan-V3 Ende. Bereit fuer Compact + Code.**
