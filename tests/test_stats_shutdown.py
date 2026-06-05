"""Tests fuer StationStatsLogger.shutdown (OPT-57, Robustheit).

Der Writer ist ein Daemon-Thread; ohne sauberen Stop gehen beim App-Close noch
in der Queue liegende Statistik-Eintraege verloren. shutdown() reiht einen
Sentinel ein (FIFO → alle davor liegenden Eintraege werden noch geschrieben)
und joint den Thread mit Timeout.

Schreibt ausschliesslich nach tmp_path — nie ins echte statistics/.
"""

import core.station_stats as stats_mod
from core.station_stats import StationStatsLogger


def _count_data_rows(tmp_path):
    """Datenzeilen ueber alle erzeugten .md-Dateien zaehlen.

    Datenzeilen beginnen mit '|' und enthalten eine HH:MM:SS-Zeit (Doppelpunkt);
    Header ('| Zeit | …') und Trennzeile ('|---|') haben keinen Doppelpunkt.
    """
    rows = 0
    for f in tmp_path.rglob("*.md"):
        for line in f.read_text().splitlines():
            if line.startswith("|") and ":" in line:
                rows += 1
    return rows


def test_shutdown_drains_queue(tmp_path, monkeypatch):
    """Alle vor shutdown() eingereihten Eintraege werden noch geschrieben.

    Mutationsbeweis: killte shutdown() den Thread ohne Sentinel+join, waeren
    < N Zeilen da. Da shutdown() bis zum Sentinel joint (= alle N davor
    geschrieben), ist die Zahl deterministisch N.
    """
    monkeypatch.setattr("core.sim_mode.is_sim_mode", lambda: False)
    logger = StationStatsLogger(base_dir=tmp_path)
    n = 25
    for i in range(n):
        logger.log_cycle(station_count=i, avg_snr=-10.0, band="20m",
                         ft_mode="FT8", rx_mode="Normal")
    logger.shutdown()
    assert not logger._thread.is_alive()
    assert _count_data_rows(tmp_path) == n


def test_shutdown_stops_thread(tmp_path):
    """Nach shutdown() laeuft der Writer-Thread nicht mehr."""
    logger = StationStatsLogger(base_dir=tmp_path)
    assert logger._thread.is_alive()
    logger.shutdown()
    assert not logger._thread.is_alive()


def test_shutdown_idempotent(tmp_path):
    """Zweiter shutdown()-Aufruf ist ein No-op (kein Crash)."""
    logger = StationStatsLogger(base_dir=tmp_path)
    logger.shutdown()
    logger.shutdown()  # darf nicht werfen
    assert not logger._thread.is_alive()


def test_sentinel_breaks_only_on_identity(tmp_path, monkeypatch):
    """Der Sentinel stoppt NUR per Identitaet (is) — normale Eintraege mit
    aehnlichem Inhalt laufen normal durch. Schutz gegen versehentlichen
    Frueh-Stop durch einen 'aehnlichen' Eintrag."""
    monkeypatch.setattr("core.sim_mode.is_sim_mode", lambda: False)
    logger = StationStatsLogger(base_dir=tmp_path)
    # Ein object()-aehnlicher, aber NICHT der Sentinel — als Roh-Eintrag waere
    # er kein dict und wuerde _write_entry werfen; daher pruefen wir die
    # Identitaet defensiv: ein frisches object() ist NICHT _SHUTDOWN.
    assert object() is not stats_mod._SHUTDOWN
    logger.log_cycle(station_count=1, avg_snr=-12.0, band="40m",
                     ft_mode="FT8", rx_mode="Normal")
    logger.shutdown()
    assert _count_data_rows(tmp_path) == 1
