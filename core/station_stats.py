"""SimpleFT8 Stations-Statistik Logger — Pro-Zyklus Empfangsstatistiken.

Loggt pro FT8/FT4-Zyklus:
- Anzahl empfangener Stationen
- Durchschnitts-SNR
- Band, Protokoll (FT8/FT4), RX-Modus

Verzeichnis: Statistics/<RX-Modus>/<Band>/<Protokoll>/
Dateien: <Datum>_<Stunde>.md (stuendlich, mit Zusammenfassung)
Threading: async via Queue + Daemon-Thread (blockiert nie den Decoder)
"""

import os
import queue
import threading
import time
from pathlib import Path

FT8_DECODE_THRESHOLD = -24


def get_active_reception_mode(rx_mode: str, scoring_mode: str = "normal") -> str | None:
    """Aktiven Empfangsmodus als Verzeichnisname.

    Returns: "Normal", "Diversity_Normal", "Diversity_Dx", oder None (dx_tuning)
    """
    if rx_mode == "normal":
        return "Normal"
    if rx_mode == "diversity":
        return f"Diversity_{scoring_mode.capitalize()}"
    return None  # dx_tuning → kein Logging


def get_active_protocol(ft_mode: str) -> str | None:
    """Aktives Protokoll validieren. Gibt None zurueck bei FT2 (nicht unterstuetzt).

    Returns: "FT8", "FT4", oder None
    """
    if ft_mode in ("FT8", "FT4"):
        return ft_mode
    return None


def ensure_statistics_directory(base_dir: Path, rx_mode: str, band: str, protocol: str) -> Path:
    """Statistik-Verzeichnis erstellen falls noetig. Gibt den Pfad zurueck.

    Struktur: base_dir/<rx_mode>/<band>/<protocol>/
    """
    target = base_dir / rx_mode / band / protocol
    target.mkdir(parents=True, exist_ok=True)
    return target


class StationStatsLogger:
    """Asynchroner Statistik-Logger fuer Empfangszyklen."""

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            # Im Projektverzeichnis (sichtbar fuer den User)
            base_dir = Path(__file__).parent.parent / "statistics"
        self._base_dir = Path(base_dir)
        self._dir_cache: set = set()  # Gecachte existierende Verzeichnisse
        self._queue = queue.Queue(maxsize=1000)
        self._current_file = None
        self._current_hour = None
        self._current_path = None
        self._cycle_count = 0
        self._station_total = 0
        self._station_max = 0
        self._station_min = 999
        self._ant2_wins_total = 0
        self._snr_delta_total = 0.0
        self._snr_delta_count = 0
        # Station-Comparison Counter (eigene Stunden-Datei)
        self._sc_path = None
        self._sc_compare_count = 0
        self._sc_saved_count = 0
        self._sc_delta_a2_total = 0.0
        self._sc_delta_a2_count = 0
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def log_cycle(self, station_count: int, avg_snr: float,
                  band: str, ft_mode: str, rx_mode: str,
                  ant2_wins: int = 0, snr_delta: float = 0.0):
        """Einen Zyklus loggen (non-blocking, thread-safe).

        Args:
            station_count: Anzahl empfangener Stationen
            avg_snr: Durchschnitts-SNR in dB
            band: z.B. "20m", "40m"
            ft_mode: "FT8" oder "FT4"
            rx_mode: "Normal", "Diversity_Normal", "Diversity_Dx"
            ant2_wins: Wie oft Ant2 strikt besser als Ant1 (nur Diversity)
        """
        if ft_mode not in ("FT8", "FT4"):
            return
        entry = {
            "time": time.strftime("%H:%M:%S", time.gmtime()),
            "hour": time.strftime("%Y-%m-%d_%H", time.gmtime()),
            "date_display": time.strftime("%Y-%m-%d", time.gmtime()),
            "hour_display": time.strftime("%H:00-%H:59", time.gmtime()),
            "count": station_count,
            "snr": round(avg_snr),
            "band": band,
            "ft_mode": ft_mode,
            "rx_mode": rx_mode,
            "ant2_wins": ant2_wins,
            "snr_delta": snr_delta,
        }
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            pass  # Queue voll — Eintrag verwerfen (sollte nie passieren)

    def log_station_comparisons(self, band: str, mode: str, scoring_mode: str,
                                comparisons: list[dict]):
        """Per-Station SNR-Vergleiche loggen (non-blocking, thread-safe).

        Args:
            band: z.B. "20m", "40m"
            mode: "FT8" oder "FT4"
            scoring_mode: "normal" oder "dx"
            comparisons: Liste von Dicts aus accumulate_stations()
        """
        if not comparisons:
            return
        rx_mode = get_active_reception_mode("diversity", scoring_mode)
        protocol = get_active_protocol(mode)
        if not rx_mode or not protocol:
            return

        now_utc = time.gmtime()
        hour_str = time.strftime("%Y-%m-%d_%H", now_utc)
        time_str = time.strftime("%H:%M:%S", now_utc)
        date_display = time.strftime("%Y-%m-%d", now_utc)

        rows = []
        for comp in comparisons:
            a1 = comp["ant1_snr"]
            a2 = comp["ant2_snr"]
            saved = "★" if (a1 <= FT8_DECODE_THRESHOLD and a2 > FT8_DECODE_THRESHOLD) else ""
            rows.append({
                "time": time_str,
                "call": comp["call"],
                "ant1_snr": a1,
                "ant2_snr": a2,
                "delta": comp["delta"],
                "winner": comp["antenna_winner"],
                "saved": saved,
            })

        entry = {
            "type": "station_comparison",
            "path": f"{rx_mode}/{band}/{protocol}/stations/{hour_str}.md",
            "rx_mode": rx_mode,
            "band": band,
            "protocol": protocol,
            "date_display": date_display,
            "rows": rows,
        }
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            pass

    def _writer_loop(self):
        """Hintergrund-Thread: schreibt Queue-Eintraege in .md Dateien."""
        while True:
            try:
                entry = self._queue.get(timeout=5)
            except queue.Empty:
                continue

            try:
                self._write_entry(entry)
            except Exception as e:
                print(f"[Stats] Schreibfehler: {e}")

    def _write_entry(self, entry: dict):
        """Einen Eintrag in die passende Stunden-Datei schreiben."""
        if entry.get("type") == "station_comparison":
            self._write_station_comparisons(entry)
            return

        dir_key = f"{entry['rx_mode']}/{entry['band']}/{entry['ft_mode']}"
        if dir_key not in self._dir_cache:
            target_dir = ensure_statistics_directory(
                self._base_dir, entry["rx_mode"], entry["band"], entry["ft_mode"])
            self._dir_cache.add(dir_key)
        else:
            target_dir = self._base_dir / entry["rx_mode"] / entry["band"] / entry["ft_mode"]
        target_path = target_dir / f"{entry['hour']}.md"

        # Stundenwechsel? Alte Datei abschliessen
        if self._current_path and self._current_path != target_path:
            self._write_summary()
            self._reset_counters()

        # Neue Datei? Header schreiben
        if self._current_path != target_path:
            self._current_path = target_path
            self._current_hour = entry["hour"]
            is_diversity = "Diversity" in entry["rx_mode"]
            if not target_path.exists():
                with open(target_path, "w") as f:
                    f.write(f"# Statistik {entry['date_display']} "
                            f"{entry['hour_display']} UTC | "
                            f"{entry['ft_mode']} | {entry['band']} | "
                            f"{entry['rx_mode']}\n\n")
                    if is_diversity:
                        f.write("| Zeit | Stationen | Ø SNR | Ant2 Wins | Ø ΔSNR |\n")
                        f.write("|------|-----------|-------|-----------|--------|\n")
                    else:
                        f.write("| Zeit | Stationen | Ø SNR |\n")
                        f.write("|------|-----------|-------|\n")

        # Zeile anfuegen
        is_diversity = "Diversity" in entry["rx_mode"]
        with open(target_path, "a") as f:
            if is_diversity:
                delta_str = f"{entry['snr_delta']:+.1f}"
                f.write(f"| {entry['time']} | {entry['count']} | {entry['snr']} | {entry['ant2_wins']} | {delta_str} |\n")
            else:
                f.write(f"| {entry['time']} | {entry['count']} | {entry['snr']} |\n")

        # Zaehler aktualisieren
        self._cycle_count += 1
        self._station_total += entry["count"]
        self._station_max = max(self._station_max, entry["count"])
        self._ant2_wins_total += entry.get("ant2_wins", 0)
        delta = entry.get("snr_delta", 0.0)
        if delta != 0.0:
            self._snr_delta_total += delta
            self._snr_delta_count += 1
        if entry["count"] > 0:
            self._station_min = min(self._station_min, entry["count"])

    def _write_station_comparisons(self, entry: dict):
        """Station-Vergleiche in separate Stunden-Datei schreiben."""
        full_path = self._base_dir / entry["path"]
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Stundenwechsel? Zusammenfassung schreiben + Reset
        if self._sc_path and self._sc_path != full_path:
            self._write_sc_summary()
            self._reset_sc_counters()

        # Neue Datei? Header schreiben
        if not full_path.exists():
            with open(full_path, "w") as f:
                f.write(f"# Station-Vergleiche {entry['date_display']} | "
                        f"{entry['rx_mode']} | {entry['band']} | {entry['protocol']}\n\n")
                f.write("| Zeit | Call | ANT1 dB | ANT2 dB | Δ dB | Gewinner | Saved |\n")
                f.write("|------|------|---------|---------|------|----------|-------|\n")

        # Zeilen schreiben + Zaehler aktualisieren
        with open(full_path, "a") as f:
            for row in entry["rows"]:
                f.write(f"| {row['time']} | {row['call']} | {row['ant1_snr']} | "
                        f"{row['ant2_snr']} | {row['delta']:+.1f} | "
                        f"{row['winner']} | {row['saved']} |\n")
                self._sc_compare_count += 1
                if row["saved"] == "★":
                    self._sc_saved_count += 1
                if row["winner"] == "A2":
                    self._sc_delta_a2_total += row["delta"]
                    self._sc_delta_a2_count += 1

        self._sc_path = full_path

    def _write_sc_summary(self):
        """Zusammenfassung am Ende einer Stunden-Vergleichs-Datei anfuegen."""
        if not self._sc_path or self._sc_compare_count == 0:
            return
        try:
            with open(self._sc_path, "a") as f:
                f.write(f"\n## Zusammenfassung\n")
                f.write(f"- Vergleiche gesamt: {self._sc_compare_count}\n")
                f.write(f"- Saved-Events (★): {self._sc_saved_count}\n")
                if self._sc_delta_a2_count > 0:
                    avg = self._sc_delta_a2_total / self._sc_delta_a2_count
                    f.write(f"- Ø Δ wenn A2 gewann: {avg:+.1f} dB\n")
        except Exception:
            pass

    def _reset_sc_counters(self):
        self._sc_path = None
        self._sc_compare_count = 0
        self._sc_saved_count = 0
        self._sc_delta_a2_total = 0.0
        self._sc_delta_a2_count = 0

    def _write_summary(self):
        """Zusammenfassung am Ende einer Stunde anfuegen."""
        if not self._current_path or self._cycle_count == 0:
            return
        avg = self._station_total / self._cycle_count
        min_val = self._station_min if self._station_min < 999 else 0
        try:
            with open(self._current_path, "a") as f:
                f.write(f"\n## Zusammenfassung\n")
                f.write(f"- Zyklen: {self._cycle_count}\n")
                f.write(f"- Ø Stationen/Zyklus: {avg:.1f}\n")
                f.write(f"- Max: {self._station_max} | Min: {min_val}\n")
                if self._ant2_wins_total > 0:
                    ant2_avg = self._ant2_wins_total / self._cycle_count
                    f.write(f"- Ø Ant2 Wins/Zyklus: {ant2_avg:.1f}\n")
                if self._snr_delta_count > 0:
                    delta_avg = self._snr_delta_total / self._snr_delta_count
                    f.write(f"- Ø ΔSNR (A2-A1): {delta_avg:+.1f} dB\n")
        except Exception:
            pass

    def _reset_counters(self):
        self._cycle_count = 0
        self._station_total = 0
        self._station_max = 0
        self._station_min = 999
        self._ant2_wins_total = 0
        self._snr_delta_total = 0.0
        self._snr_delta_count = 0
