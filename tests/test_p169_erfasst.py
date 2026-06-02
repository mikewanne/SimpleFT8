"""P169 — adif/erfasst/ als einzige rekursive Worked-Quelle + Import + Migration.

Deckt ab: rekursives Laden (qso_log + parse_all_adif_files), clear()+reload ohne
Doppelzählung, export_all_records aus erfasst/ (App-Logs only), Import-Kern
(_import_adif_file: Validierung + Kopie nach importiert/), und der
Migrations-Integrationstest (copy→verify→delete, idempotent, Nicht-ADIF bleibt).
"""
import importlib.util
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _write_adif(path: Path, *cbm):
    """Minimal-ADIF schreiben. cbm = (call, band, mode)-Tupel."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["<adif_ver:5>3.1.7<eoh>"]
    for call, band, mode in cbm:
        lines.append(
            f"<call:{len(call)}>{call} <band:{len(band)}>{band} "
            f"<mode:{len(mode)}>{mode} <qso_date:8>20260101 <eor>")
    path.write_text("\n".join(lines) + "\n")


# ── Rekursives Laden ─────────────────────────────────────────────────────────

def test_qso_log_load_directory_recursive(tmp_path):
    from log.qso_log import QSOLog
    _write_adif(tmp_path / "erfasst" / "neu" / "a.adi", ("AA1AA", "20m", "FT8"))
    _write_adif(tmp_path / "erfasst" / "importiert" / "b.adi", ("BB2BB", "40m", "FT4"))
    q = QSOLog()
    q.load_directory(tmp_path / "erfasst", recursive=True)
    assert q.is_worked_on_band("AA1AA", "20m")
    assert q.is_worked_on_band("BB2BB", "40m")
    assert q.qso_count() == 2


def test_qso_log_load_directory_nonrecursive_misses_subdirs(tmp_path):
    from log.qso_log import QSOLog
    _write_adif(tmp_path / "erfasst" / "neu" / "a.adi", ("AA1AA", "20m", "FT8"))
    q = QSOLog()
    q.load_directory(tmp_path / "erfasst", recursive=False)  # ohne rglob → leer
    assert q.qso_count() == 0


def test_parse_all_adif_files_recursive(tmp_path):
    from log.adif import parse_all_adif_files
    _write_adif(tmp_path / "x" / "a.adi", ("AA1AA", "20m", "FT8"))
    _write_adif(tmp_path / "y" / "b.adi", ("BB2BB", "40m", "FT8"))
    flat = parse_all_adif_files(tmp_path)
    rec = parse_all_adif_files(tmp_path, recursive=True)
    assert len(flat) == 0 and len(rec) == 2


# ── clear() + Reload ohne Doppelzählung ──────────────────────────────────────

def test_clear_reload_no_double_count(tmp_path):
    from log.qso_log import QSOLog
    _write_adif(tmp_path / "neu" / "a.adi", ("AA1AA", "20m", "FT8"),
                ("BB2BB", "40m", "FT8"))
    q = QSOLog()
    q.load_directory(tmp_path, recursive=True)
    assert q.qso_count() == 2
    q.clear()
    q.load_directory(tmp_path, recursive=True)
    assert q.qso_count() == 2  # nicht 4
    assert q.worked_count() == 2


# ── export_all_records aus erfasst/ (nur App-Logs) ───────────────────────────

def test_export_all_records_only_app_logs_from_erfasst(tmp_path):
    from log.adif import export_all_records
    # App-Log (SimpleFT8_LOG_*) in neu/ → wird exportiert
    _write_adif(tmp_path / "adif" / "erfasst" / "neu" / "SimpleFT8_LOG_20260101.adi",
                ("AA1AA", "20m", "FT8"))
    # importierte Fremd-Historie (anderer Name) → NICHT mit-exportiert
    _write_adif(tmp_path / "adif" / "erfasst" / "importiert" / "da1mhh.export.adi",
                ("ZZ9ZZ", "10m", "FT8"))
    out_path, count = export_all_records(tmp_path)
    assert count == 1  # nur das App-Log
    assert out_path.parent == tmp_path / "adif" / "exports"
    text = out_path.read_text()
    assert "AA1AA" in text and "ZZ9ZZ" not in text


# ── Import-Kern (_import_adif_file) ──────────────────────────────────────────

def test_import_adif_file_copies_to_importiert(qapp, tmp_path, monkeypatch):
    from ui.logbook_widget import LogbookWidget
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "fremd.adi"
    _write_adif(src, ("CC3CC", "15m", "FT8"), ("DD4DD", "20m", "FT4"))
    w = LogbookWidget(adif_directory=tmp_path / "adif")
    n, msg = w._import_adif_file(src)
    assert n == 2
    imported = list((tmp_path / "adif" / "erfasst" / "importiert").glob("*.adi"))
    assert len(imported) == 1
    assert "CC3CC" in imported[0].read_text()


def test_import_adif_file_rejects_no_call(qapp, tmp_path, monkeypatch):
    from ui.logbook_widget import LogbookWidget
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "leer.adi"
    src.write_text("<adif_ver:5>3.1.7<eoh>\n")  # kein QSO
    w = LogbookWidget(adif_directory=tmp_path / "adif")
    n, msg = w._import_adif_file(src)
    assert n == 0
    assert not (tmp_path / "adif" / "erfasst" / "importiert").exists() or \
        not list((tmp_path / "adif" / "erfasst" / "importiert").glob("*.adi"))


# ── Migrations-Tool Integration (copy → verify → delete) ─────────────────────

def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "mig_p169", PROJECT / "tools" / "migrate_adif_erfasst.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_apply_preserves_all_and_cleans(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mig = _load_migration_module()
    # Fixture: verstreute Quell-Ordner + eine Nicht-ADIF-Datei
    _write_adif(tmp_path / "adif" / "SimpleFT8_LOG_20260601.adi", ("RR1RR", "20m", "FT8"))
    _write_adif(tmp_path / "adif" / "hochgeladen" / "up.adi", ("UU1UU", "40m", "FT8"))
    _write_adif(tmp_path / "adif" / "_backup_qrz_export" / "exp.adi", ("EX1EX", "10m", "FT8"))
    _write_adif(tmp_path / "adif" / "repaired" / "rep.adi", ("RP1RP", "15m", "FT4"))
    (tmp_path / "adif" / "_backup_qrz_export" / "adif_stdout.log").write_text("log")

    assert mig.apply() == 0

    erfasst = tmp_path / "adif" / "erfasst"
    # Klassifikation
    assert (erfasst / "neu" / "SimpleFT8_LOG_20260601.adi").exists()
    assert (erfasst / "hochgeladen" / "up.adi").exists()
    assert any("exp.adi" in p.name for p in (erfasst / "importiert").glob("*.adi"))
    assert any("rep.adi" in p.name for p in (erfasst / "importiert").glob("*.adi"))
    # alte .adi-Quellen gelöscht
    assert not (tmp_path / "adif" / "hochgeladen").exists()
    assert not (tmp_path / "adif" / "repaired").exists()
    assert not list((tmp_path / "adif").glob("*.adi"))
    # Nicht-ADIF bleibt
    assert (tmp_path / "adif" / "_backup_qrz_export" / "adif_stdout.log").exists()
    # (Call,Band) vollständig erhalten
    from log.qso_log import QSOLog
    q = QSOLog()
    q.load_directory(erfasst, recursive=True)
    for c, b in [("RR1RR", "20m"), ("UU1UU", "40m"), ("EX1EX", "10m"), ("RP1RP", "15m")]:
        assert q.is_worked_on_band(c, b), (c, b)
    # Backup-ZIP angelegt
    assert list((tmp_path / "Appsicherungen").glob("adif_backup_pre_p169_*.zip"))


def test_migration_idempotent_rerun(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mig = _load_migration_module()
    _write_adif(tmp_path / "adif" / "SimpleFT8_LOG_20260601.adi", ("RR1RR", "20m", "FT8"))
    assert mig.apply() == 0
    n_after_first = len(list((tmp_path / "adif" / "erfasst").rglob("*.adi")))
    # Re-Run: keine neuen Quell-Dateien → keine Duplikate in erfasst/
    assert mig.apply() == 0
    n_after_second = len(list((tmp_path / "adif" / "erfasst").rglob("*.adi")))
    assert n_after_first == n_after_second
