#!/usr/bin/env python3
"""Tests fuer Thread-Safety von core/antenna_pref.AntennaPreferenceStore.

Cycle-Loop schreibt aus dem Decoder-Thread, UI/Karten-Code liest aus dem GUI-Thread.
Diese Tests stellen sicher, dass parallele Lese/Schreib-Operationen den Store
nicht korrumpieren und dass snapshot() unabhaengige Kopien liefert.

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_antenna_pref_threadsafe.py -v
"""

import sys
import os
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.antenna_pref import AntennaPreferenceStore


def _make_msg(call: str, snr_a1: float | None = None, snr_a2: float | None = None,
              antenna: str = "") -> SimpleNamespace:
    msg = SimpleNamespace(antenna=antenna)
    if snr_a1 is not None:
        msg._snr_a1 = snr_a1
    if snr_a2 is not None:
        msg._snr_a2 = snr_a2
    return msg


def test_snapshot_is_independent_copy():
    store = AntennaPreferenceStore()
    store.update_from_stations({"DL1ABC": _make_msg("DL1ABC", -15.0, -10.0)})
    snap = store.snapshot()
    # Snapshot mutieren — Store muss unveraendert bleiben
    snap["DL1ABC"]["best_ant"] = "MUTATED"
    snap["NEW_CALL"] = {"best_ant": "A1", "delta_db": 0.0}
    assert store.get("DL1ABC") == "A2"  # nicht "MUTATED"
    assert store.get("NEW_CALL") is None


def test_snapshot_inner_dict_is_copy():
    store = AntennaPreferenceStore()
    store.update_from_stations({"DL1ABC": _make_msg("DL1ABC", -15.0, -10.0)})
    snap1 = store.snapshot()
    snap2 = store.snapshot()
    # Beide Snapshots sind eigene Objekte
    assert snap1 is not snap2
    assert snap1["DL1ABC"] is not snap2["DL1ABC"]
    # Inhalt aber gleich
    assert snap1["DL1ABC"] == snap2["DL1ABC"]


def test_snapshot_after_clear_is_empty_but_old_snap_intact():
    store = AntennaPreferenceStore()
    store.update_from_stations({"DL1ABC": _make_msg("DL1ABC", -15.0, -10.0)})
    snap_before = store.snapshot()
    store.clear()
    snap_after = store.snapshot()
    assert len(snap_before) == 1
    assert len(snap_after) == 0
    # Alter Snapshot lebt unabhaengig weiter
    assert "DL1ABC" in snap_before


def test_concurrent_read_write_no_crash():
    """Viele Threads lesen/schreiben parallel — kein Crash, Konsistenz gewahrt."""
    store = AntennaPreferenceStore()
    stop = threading.Event()
    errors = []

    def writer(tid: int):
        try:
            i = 0
            while not stop.is_set():
                call = f"DL{tid}TEST{i % 10}"
                msg = _make_msg(call, -15.0 + (i % 5), -10.0 + (i % 5))
                store.update_from_stations({call: msg})
                i += 1
        except Exception as e:
            errors.append(e)

    def reader(tid: int):
        try:
            while not stop.is_set():
                _ = store.snapshot()
                _ = store.count
                _ = store.get(f"DL{tid}TEST0")
                _ = store.get_pref(f"DL{tid}TEST0")
                _ = store.get_delta_db(f"DL{tid}TEST0")
        except Exception as e:
            errors.append(e)

    writers = [threading.Thread(target=writer, args=(i,), daemon=True) for i in range(5)]
    readers = [threading.Thread(target=reader, args=(i,), daemon=True) for i in range(5)]
    for t in writers + readers:
        t.start()

    time.sleep(0.5)  # 500ms Last
    stop.set()
    for t in writers + readers:
        t.join(timeout=2.0)

    assert not errors, f"Threading-Fehler: {errors}"
    # Store sollte sinnvoll befuellt sein, aber keine Korruption
    snap = store.snapshot()
    for call, entry in snap.items():
        assert "best_ant" in entry
        assert entry["best_ant"] in ("A1", "A2")
        assert "delta_db" in entry


def test_clear_during_concurrent_writes():
    """clear() darf parallel zu writes laufen ohne Race."""
    store = AntennaPreferenceStore()
    stop = threading.Event()
    errors = []

    def writer():
        try:
            i = 0
            while not stop.is_set():
                msg = _make_msg(f"CALL{i % 20}", -15.0, -10.0)
                store.update_from_stations({f"CALL{i % 20}": msg})
                i += 1
        except Exception as e:
            errors.append(e)

    def clearer():
        try:
            while not stop.is_set():
                store.clear()
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, daemon=True) for _ in range(3)]
    threads.append(threading.Thread(target=clearer, daemon=True))
    for t in threads:
        t.start()

    time.sleep(0.3)
    stop.set()
    for t in threads:
        t.join(timeout=2.0)

    assert not errors, f"Threading-Fehler: {errors}"


def test_existing_api_unchanged_after_lock_added():
    """Bestaetigt: bestehende API-Calls verhalten sich identisch nach RLock-Einbau."""
    store = AntennaPreferenceStore()
    msg = _make_msg("DL1ABC", -15.0, -10.0)
    store.update_from_stations({"DL1ABC": msg})

    assert store.get("DL1ABC") == "A2"
    assert store.get("UNKNOWN") is None
    pref = store.get_pref("DL1ABC")
    assert pref == {"best_ant": "A2", "delta_db": 5.0}
    assert store.get_delta_db("DL1ABC") == 5.0
    assert store.count == 1
    store.clear()
    assert store.count == 0


def test_get_pref_returns_independent_copy():
    """get_pref() liefert schon vor RLock eine Kopie — verifizieren dass das so bleibt."""
    store = AntennaPreferenceStore()
    store.update_from_stations({"DL1ABC": _make_msg("DL1ABC", -15.0, -10.0)})
    p1 = store.get_pref("DL1ABC")
    p1["best_ant"] = "MUTATED"
    p2 = store.get_pref("DL1ABC")
    assert p2["best_ant"] == "A2"  # nicht "MUTATED"


def test_clear_mid_update_leaves_consistent_state():
    """clear() darf NICHT mitten in einem update_from_stations einen halben Eintrag hinterlassen.

    Da beide Methoden denselben Lock halten, sind Zwischenzustaende unsichtbar:
    Snapshot zeigt entweder kompletten Update oder leer-nach-clear, nie halb-befuellt.
    """
    store = AntennaPreferenceStore()
    stations = {f"DL{i}TST": _make_msg(f"DL{i}TST", -15.0, -10.0) for i in range(100)}

    for _ in range(20):
        t = threading.Thread(target=store.update_from_stations, args=(stations,), daemon=True)
        t.start()
        store.clear()
        t.join(timeout=2.0)

        snap = store.snapshot()
        # Jeder gefundene Eintrag muss vollstaendig sein
        for call, entry in snap.items():
            assert "best_ant" in entry, f"Halber Eintrag {call}: {entry}"
            assert entry["best_ant"] in ("A1", "A2"), f"Korrupter best_ant {call}: {entry}"
            assert "delta_db" in entry, f"Halber Eintrag {call}: {entry}"
