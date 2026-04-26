#!/usr/bin/env python3
"""Tests fuer core/psk_reporter.py.

Keine echten HTTP-Aufrufe — nur Pure-Python-Logik (parse_spots, normalize_call,
Backoff-Sequenz, Cache-Roundtrip).

Ausfuehren:
    cd SimpleFT8
    ./venv/bin/python3 -m pytest tests/test_psk_reporter.py -v
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.psk_reporter import (
    Spot,
    normalize_call,
    parse_spots,
    PSKReporterClient,
    _Backoff,
    BACKOFF_MAX_S,
)


# ── normalize_call ────────────────────────────────────────

def test_normalize_call_plain():
    assert normalize_call("DA1MHH") == "DA1MHH"


def test_normalize_call_lowercase():
    assert normalize_call("da1mhh") == "DA1MHH"


def test_normalize_call_strips_portable_suffix():
    assert normalize_call("DA1MHH/P") == "DA1MHH"


def test_normalize_call_strips_maritime_suffix():
    assert normalize_call("DA1MHH/MM") == "DA1MHH"


def test_normalize_call_strips_qrp_suffix():
    assert normalize_call("DA1MHH/QRP") == "DA1MHH"


def test_normalize_call_only_first_slash_kept_as_split():
    # "K1ABC/W2" → Slash-Calls mit Region-Indikator. .rsplit('/', 1) liefert "K1ABC".
    assert normalize_call("K1ABC/W2") == "K1ABC"


def test_normalize_call_empty():
    assert normalize_call("") == ""
    assert normalize_call(None) == ""  # type: ignore[arg-type]


def test_normalize_call_whitespace():
    assert normalize_call("  DA1MHH  ") == "DA1MHH"


# ── parse_spots ───────────────────────────────────────────

SAMPLE_XML_NO_NS = """<?xml version="1.0" encoding="UTF-8"?>
<receptionReports currentSeconds="1745670900">
  <receptionReport receiverCallsign="DK4ABC" receiverLocator="JO31qf"
    frequency="14074123" flowStartSeconds="1745670900" mode="FT8"
    senderCallsign="DA1MHH" sNR="-12" />
  <receptionReport receiverCallsign="W1XYZ" receiverLocator="FN42"
    frequency="14074321" flowStartSeconds="1745670920" mode="FT8"
    senderCallsign="DA1MHH" sNR="-8" />
</receptionReports>
"""

SAMPLE_XML_WITH_NS = """<?xml version="1.0" encoding="UTF-8"?>
<receptionReports xmlns="https://www.pskreporter.info/" currentSeconds="1745670900">
  <receptionReport receiverCallsign="JA1ABC" receiverLocator="PM95"
    frequency="14074500" flowStartSeconds="1745670930" mode="FT8"
    senderCallsign="DA1MHH" sNR="-15" />
</receptionReports>
"""


def test_parse_spots_basic():
    spots = parse_spots(SAMPLE_XML_NO_NS)
    assert len(spots) == 2
    s0 = spots[0]
    assert s0.rx_call == "DK4ABC"
    assert s0.rx_locator == "JO31qf"
    assert s0.snr_db == -12.0
    assert s0.frequency_hz == 14074123
    assert s0.timestamp == 1745670900.0
    assert s0.mode == "FT8"
    assert s0.sender_call == "DA1MHH"


def test_parse_spots_with_namespace():
    spots = parse_spots(SAMPLE_XML_WITH_NS)
    assert len(spots) == 1
    assert spots[0].rx_call == "JA1ABC"
    assert spots[0].rx_locator == "PM95"
    assert spots[0].snr_db == -15.0


def test_parse_spots_empty_xml():
    assert parse_spots("") == []
    assert parse_spots("   ") == []


def test_parse_spots_malformed_xml():
    assert parse_spots("<not really xml") == []


def test_parse_spots_skip_missing_callsign():
    xml = """<receptionReports>
      <receptionReport receiverLocator="JO31" sNR="-10" />
    </receptionReports>"""
    assert parse_spots(xml) == []


def test_parse_spots_skip_missing_locator():
    xml = """<receptionReports>
      <receptionReport receiverCallsign="DK4ABC" sNR="-10" />
    </receptionReports>"""
    assert parse_spots(xml) == []


def test_parse_spots_invalid_snr_returns_none():
    xml = """<receptionReports>
      <receptionReport receiverCallsign="DK4ABC" receiverLocator="JO31"
        sNR="not-a-number" />
    </receptionReports>"""
    spots = parse_spots(xml)
    assert len(spots) == 1
    assert spots[0].snr_db is None


def test_parse_spots_uppercases_callsign():
    xml = """<receptionReports>
      <receptionReport receiverCallsign="dk4abc" receiverLocator="JO31"
        sNR="-10" />
    </receptionReports>"""
    spots = parse_spots(xml)
    assert spots[0].rx_call == "DK4ABC"


# ── _Backoff ──────────────────────────────────────────────

def test_backoff_starts_at_base():
    b = _Backoff(base_s=120)
    assert b.current_s == 120


def test_backoff_grows_factor_1_5():
    b = _Backoff(base_s=120, factor=1.5, max_s=10000)
    assert b.fail() == 180.0
    assert b.fail() == 270.0
    assert b.fail() == 405.0


def test_backoff_capped_at_max():
    b = _Backoff(base_s=100, factor=2.0, max_s=500)
    b.fail()  # 200
    b.fail()  # 400
    b.fail()  # capped at 500
    assert b.current_s == 500
    b.fail()
    assert b.current_s == 500  # bleibt am Cap


def test_backoff_reset_to_base():
    b = _Backoff(base_s=120)
    b.fail()
    b.fail()
    b.reset()
    assert b.current_s == 120


def test_backoff_default_max_is_60min():
    b = _Backoff(base_s=120)
    assert b.max_s == BACKOFF_MAX_S
    assert BACKOFF_MAX_S == 3600


# ── PSKReporterClient: nicht-Netz-Tests ────────────────────

def test_client_normalizes_callsign_at_init():
    c = PSKReporterClient("DA1MHH/P")
    assert c.callsign == "DA1MHH"


def test_client_uppercases_mode():
    c = PSKReporterClient("DA1MHH", mode="ft8")
    assert c._mode == "FT8"


def test_client_fetch_spots_empty_call_returns_empty():
    c = PSKReporterClient("")
    assert c.fetch_spots() == []


def test_client_cache_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "cache.json"
        c = PSKReporterClient("DA1MHH", cache_path=cache)
        spots = [
            Spot(rx_call="DK4ABC", rx_locator="JO31", snr_db=-10.0,
                 frequency_hz=14074000, timestamp=1234.5,
                 mode="FT8", sender_call="DA1MHH"),
            Spot(rx_call="W1XYZ", rx_locator="FN42", snr_db=-8.0,
                 frequency_hz=14074000, timestamp=1235.0,
                 mode="FT8", sender_call="DA1MHH"),
        ]
        c.save_cache(spots)
        assert cache.exists()
        loaded = c.cached_spots()
        assert len(loaded) == 2
        assert loaded[0].rx_call == "DK4ABC"
        assert loaded[0].snr_db == -10.0
        assert loaded[1].rx_call == "W1XYZ"


def test_client_cache_load_when_missing_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "missing.json"
        c = PSKReporterClient("DA1MHH", cache_path=cache)
        assert c.cached_spots() == []


def test_client_cache_load_on_corrupt_file_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "corrupt.json"
        cache.write_text("not json {{{")
        c = PSKReporterClient("DA1MHH", cache_path=cache)
        assert c.cached_spots() == []


def test_client_cache_atomic_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir) / "cache.json"
        c = PSKReporterClient("DA1MHH", cache_path=cache)
        c.save_cache([])
        # tmp-File darf nicht uebrig sein
        assert not cache.with_suffix(".tmp").exists()
        assert cache.exists()


def test_client_is_running_default_false():
    c = PSKReporterClient("DA1MHH")
    assert c.is_running is False


def test_client_stop_when_not_running_is_noop():
    c = PSKReporterClient("DA1MHH")
    c.stop()  # darf nicht crashen
    assert c.is_running is False


def test_client_start_polling_idempotent():
    """Start-Aufruf bei laufendem Thread tut nichts (kein 2. Thread)."""
    import threading
    c = PSKReporterClient("DA1MHH", poll_interval_s=10000)

    fetched = threading.Event()

    def fake_fetch(*args, **kwargs):
        fetched.set()
        return []

    c.fetch_spots = fake_fetch  # type: ignore[assignment]
    c.start_polling(on_spots=lambda s: None)
    fetched.wait(timeout=2.0)  # warten bis Worker einmal lief
    t1 = c._thread
    c.start_polling(on_spots=lambda s: None)  # erneuter Start
    t2 = c._thread
    assert t1 is t2  # selbe Thread-Instanz, kein Doppel-Start
    c.stop(timeout_s=2.0)


def test_client_stop_terminates_thread():
    c = PSKReporterClient("DA1MHH", poll_interval_s=10000)
    c.fetch_spots = lambda *a, **k: []  # type: ignore[assignment]
    c.start_polling(on_spots=lambda s: None)
    assert c.is_running
    c.stop(timeout_s=3.0)
    assert not c.is_running


def test_client_fetch_error_triggers_backoff():
    """Bei 3 Fetch-Fehlern hintereinander muss Backoff wachsen."""
    import threading
    c = PSKReporterClient("DA1MHH", poll_interval_s=1)

    error_count = [0]
    err_lock = threading.Lock()

    def failing_fetch(*args, **kwargs):
        with err_lock:
            error_count[0] += 1
        raise ConnectionError("simulated network error")

    c.fetch_spots = failing_fetch  # type: ignore[assignment]
    errors_seen = []
    c.start_polling(on_spots=lambda s: None,
                    on_error=lambda e: errors_seen.append(e))

    # 0.5s laufen lassen → mind. 1 Fehler bei 1s Intervall
    import time
    time.sleep(0.5)
    c.stop(timeout_s=2.0)
    assert error_count[0] >= 1
    # Backoff muss > base (1) sein nach >= 1 Fail
    assert c.current_interval_s > 1.0


def test_spot_to_dict_from_dict_roundtrip():
    s = Spot(rx_call="DK4ABC", rx_locator="JO31", snr_db=-10.0,
             frequency_hz=14074000, timestamp=1234.5,
             mode="FT8", sender_call="DA1MHH")
    d = s.to_dict()
    s2 = Spot.from_dict(d)
    assert s == s2


def test_client_on_spots_callback_exception_does_not_kill_worker():
    """UI-Bug im on_spots-Callback darf den Worker-Thread NICHT terminieren.

    Symmetrisch zu on_error: beide Callbacks duerfen schreien ohne den Polling-
    Loop zu zerstoeren. Sonst wuerde ein gerade falscher UI-Update-Pfad das
    Update-System dauerhaft offline nehmen.
    """
    import threading
    import time
    c = PSKReporterClient("DA1MHH", poll_interval_s=0.05)

    fetched = [0]
    fetch_lock = threading.Lock()

    def fake_fetch(*args, **kwargs):
        with fetch_lock:
            fetched[0] += 1
        return []

    c.fetch_spots = fake_fetch  # type: ignore[assignment]

    def crashing_callback(spots):
        raise RuntimeError("simulated UI bug")

    c.start_polling(on_spots=crashing_callback)
    time.sleep(0.3)  # mehrere fetch+callback-Zyklen
    c.stop(timeout_s=2.0)

    # Worker hat trotz Callback-Crashes mehrfach gefetcht
    assert fetched[0] >= 2, f"nur {fetched[0]} Fetches — Worker tot?"
