"""SimpleFT8 PSK-Reporter Client — wer hat MICH gehoert?

Wrappt die XML-API auf retrieve.pskreporter.info zu einem wiederverwendbaren
Polling-Client mit Cache und Backoff. Genutzt vom Karten-Widget im SENDEN-Modus
(Rueckspielung: welche Stationen weltweit haben Mike's TX dekodiert?).

API:
    client = PSKReporterClient("DA1MHH", mode="FT8")
    spots = client.fetch_spots(window_min=10)  # synchron
    client.start_polling(on_spots=callback, window_min=10)  # asynchron
    client.stop()

Format:
    Spot(rx_call, rx_locator, snr_db, frequency_hz, timestamp, mode, sender_call)

Bestehender main_window._psk_worker bleibt unangetastet — er liefert nur
Aggregat-Stats (n/w/o/s-Distanz) fuer den Statusbar-Indikator. Dieses Modul
liefert die Roh-Spots fuer das Karten-Rendering. Eine spaetere Migration
faellt unter "out-of-scope" fuer das Karten-Feature.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path


PSK_QUERY_URL = (
    "https://retrieve.pskreporter.info/query?"
    "senderCallsign={call}&flowStartSeconds=-{seconds}&mode={mode}"
)
USER_AGENT_TMPL = "SimpleFT8/{version}"
DEFAULT_TIMEOUT_S = 10
DEFAULT_POLL_INTERVAL_S = 120
BACKOFF_FACTOR = 1.5
BACKOFF_MAX_S = 3600  # 60 Minuten


@dataclass
class Spot:
    """Ein einzelner Reception-Report aus PSK-Reporter."""
    rx_call: str
    rx_locator: str
    snr_db: float | None
    frequency_hz: int | None
    timestamp: float
    mode: str
    sender_call: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Spot":
        return cls(**d)


def normalize_call(call: str) -> str:
    """Suffix entfernen: DA1MHH/P → DA1MHH. Fuer PSK-API senderCallsign-Match.

    Returnt UPPERCASE. Lege keinen leeren String an, wenn Input leer ist.
    """
    if not call:
        return ""
    return call.upper().strip().rsplit("/", 1)[0]


def _local_tag(elem) -> str:
    """Tag-Namen ohne XML-Namespace zurueckgeben."""
    tag = elem.tag
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_spots(xml_text: str) -> list[Spot]:
    """PSK-Reporter XML in Spot-Liste zerlegen.

    Robust gegen mit/ohne XML-Namespace (PSK-Reporter liefert beides).
    Ueberspringt Eintraege mit leerem Locator oder Callsign.

    Args:
        xml_text: Rohes XML der API-Antwort.
    Returns:
        Liste von Spot. Leer bei Parse-Fehler oder leerer API-Antwort.
    """
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    spots: list[Spot] = []
    for elem in root.iter():
        if _local_tag(elem) != "receptionReport":
            continue
        rx_call = (elem.get("receiverCallsign") or "").strip().upper()
        rx_loc = (elem.get("receiverLocator") or "").strip()
        if not rx_call or not rx_loc:
            continue

        snr_raw = elem.get("sNR") or elem.get("snr")
        snr: float | None = None
        if snr_raw is not None:
            try:
                snr = float(snr_raw)
            except ValueError:
                snr = None

        freq_raw = elem.get("frequency")
        freq: int | None = None
        if freq_raw is not None:
            try:
                freq = int(freq_raw)
            except ValueError:
                freq = None

        ts_raw = elem.get("flowStartSeconds")
        try:
            ts = float(ts_raw) if ts_raw is not None else 0.0
        except ValueError:
            ts = 0.0

        spots.append(Spot(
            rx_call=rx_call,
            rx_locator=rx_loc,
            snr_db=snr,
            frequency_hz=freq,
            timestamp=ts,
            mode=(elem.get("mode") or "").upper(),
            sender_call=(elem.get("senderCallsign") or "").upper(),
        ))
    return spots


@dataclass
class _Backoff:
    """Exponentielles Backoff fuer Polling-Fehler."""
    base_s: float
    factor: float = BACKOFF_FACTOR
    max_s: float = BACKOFF_MAX_S
    current_s: float = field(init=False)

    def __post_init__(self):
        self.current_s = self.base_s

    def reset(self):
        self.current_s = self.base_s

    def fail(self) -> float:
        """Naechstes Intervall setzen und zurueckgeben."""
        self.current_s = min(self.max_s, self.current_s * self.factor)
        return self.current_s


class PSKReporterClient:
    """Polling-Client fuer eigene Reception-Reports von PSK-Reporter.

    Thread-Safety: start_polling/stop sind aus dem GUI-Thread aufzurufen.
    Der interne Worker-Thread ruft `on_spots`-Callback aus dem Worker —
    Aufrufer ist verantwortlich, den Callback ggf. via Qt-Signal in den
    GUI-Thread zu marshallen.
    """

    def __init__(
        self,
        callsign: str,
        mode: str = "FT8",
        cache_path: str | os.PathLike | None = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        version: str = "1.0",
    ):
        self._call = normalize_call(callsign)
        self._mode = mode.upper()
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._user_agent = USER_AGENT_TMPL.format(version=version)
        self._cache_path = (
            Path(cache_path) if cache_path
            else Path.home() / ".simpleft8" / "psk_cache.json"
        )
        self._backoff = _Backoff(base_s=poll_interval_s)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ── Synchroner Single-Shot ────────────────────────────

    def fetch_spots(self, window_min: int = 10) -> list[Spot]:
        """Eine API-Abfrage, returnt geparste Spots. Wirft urllib-Exceptions weiter."""
        if not self._call:
            return []
        url = PSK_QUERY_URL.format(
            call=self._call,
            seconds=int(max(60, window_min * 60)),
            mode=self._mode,
        )
        req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
        return parse_spots(xml_text)

    # ── Cache ─────────────────────────────────────────────

    def load_cache(self) -> dict:
        """Cache lesen. Returnt {'timestamp': float, 'spots': list[dict]}."""
        if not self._cache_path.exists():
            return {"timestamp": 0.0, "spots": []}
        try:
            with open(self._cache_path) as f:
                d = json.load(f)
            if not isinstance(d, dict) or "spots" not in d:
                return {"timestamp": 0.0, "spots": []}
            return d
        except (OSError, json.JSONDecodeError):
            return {"timestamp": 0.0, "spots": []}

    def save_cache(self, spots: list[Spot]) -> None:
        """Cache schreiben. Erzeugt Verzeichnis falls noetig."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": time.time(),
            "call": self._call,
            "mode": self._mode,
            "spots": [s.to_dict() for s in spots],
        }
        # atomar: erst .tmp, dann rename
        tmp = self._cache_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, self._cache_path)

    def cached_spots(self) -> list[Spot]:
        """Spots aus Cache laden (deserialisiert)."""
        d = self.load_cache()
        out: list[Spot] = []
        for raw in d.get("spots", []):
            try:
                out.append(Spot.from_dict(raw))
            except (TypeError, KeyError):
                continue
        return out

    # ── Asynchrones Polling ───────────────────────────────

    def start_polling(
        self,
        on_spots,
        on_error=None,
        window_min: int = 10,
    ) -> None:
        """Daemon-Thread starten der periodisch fetched.

        on_spots(list[Spot]) wird bei Erfolg aus dem Worker-Thread aufgerufen.
        on_error(Exception) optional bei Fehlern (Backoff aktiv solange Fehler).
        Idempotent: erneuter Aufruf bei laufendem Thread tut nichts.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._backoff.reset()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(on_spots, on_error, window_min),
                daemon=True,
                name="PSKReporter",
            )
            self._thread.start()

    def _run_loop(self, on_spots, on_error, window_min) -> None:
        while not self._stop_event.is_set():
            try:
                spots = self.fetch_spots(window_min=window_min)
                self.save_cache(spots)
                self._backoff.reset()
                interval = self._poll_interval_s
            except Exception as e:
                if on_error:
                    try:
                        on_error(e)
                    except Exception:
                        pass  # Callback-Fehler nicht eskalieren
                interval = self._backoff.fail()
                spots = None  # type: ignore[assignment]
            # on_spots-Callback symmetrisch zu on_error gewrappt:
            # ein UI-Bug im Callback darf den Worker-Thread NICHT killen.
            if spots is not None and on_spots:
                try:
                    on_spots(spots)
                except Exception:
                    pass
            # Interruptible Sleep in 1s-Schritten, robust gegen interval < 1
            slept = 0.0
            while slept < interval and not self._stop_event.is_set():
                remaining = interval - slept
                time.sleep(min(1.0, max(0.0, remaining)))
                slept += 1.0

    def stop(self, timeout_s: float = 5.0) -> None:
        """Worker stoppen. Blockiert bis Thread terminiert oder Timeout."""
        with self._lock:
            self._stop_event.set()
            t = self._thread
        if t is not None:
            t.join(timeout=timeout_s)
        with self._lock:
            self._thread = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def current_interval_s(self) -> float:
        return self._backoff.current_s

    @property
    def callsign(self) -> str:
        return self._call
