"""SimpleFT8 FlexRadio Client — SmartSDR TCP API + VITA-49 Audio-Streaming.

Direkte Audio-Verbindung über UDP/VITA-49 — kein DAX-Treiber nötig.
"""

import socket
import struct
import threading
import time
import re
import numpy as np
from PySide6.QtCore import QObject, Signal


# VITA-49 Konstanten
FLEX_OUI = 0x001C2D
FLEX_ICC = 0x534C  # "SL" = SmartLink
PCC_AUDIO_FLOAT32 = 0x03E3   # float32 stereo, big-endian
PCC_AUDIO_INT16 = 0x0123     # int16 mono, big-endian (reduced BW)
VITA49_HEADER_SIZE = 28       # 7 × 32-bit Words


class FlexRadio(QObject):
    """SmartSDR Client mit VITA-49 Audio-Streaming.

    Signals:
        connected: () — Verbindung hergestellt
        disconnected: () — Verbindung getrennt
        frequency_changed: (float) — Frequenz in MHz
        audio_received: (np.ndarray) — Audio-Samples empfangen (int16, mono, 24kHz)
        error: (str) — Fehler
    """

    connected = Signal()
    disconnected = Signal()
    frequency_changed = Signal(float)
    audio_received = Signal(object)
    meter_update = Signal(str, float)  # (name, value) — FWDPWR, SWR, ALC
    swr_alarm = Signal(float)
    dx_tune_progress = Signal(str)  # Fortschritt fuer GUI
    error = Signal(str)

    def __init__(self, ip: str = "", port: int = 4992):
        super().__init__()
        self.ip = ip
        self.port = port
        self._tcp_socket = None
        self._udp_socket = None
        self._running = False
        self._keepalive_running = False
        self._sequence = 0
        self._lock = threading.Lock()
        self._client_handle = ""
        self._rx_stream_id = None
        self._tx_stream_id = None
        self._slice_idx = 0  # Wird dynamisch gesetzt
        self._udp_port = 4991       # Unser lokaler UDP Port
        self._radio_udp_port = None  # Port auf dem das Radio UDP sendet (auto-detect)
        self._responses = {}  # seq → (timestamp, response)
        self._response_events = {}  # seq → threading.Event
        self.on_audio_callback = None
        self._swr_limit = 3.0
        self._last_swr = 1.0
        self._last_fwdpwr_dbm = -130.0  # Letzter Empfangspegel (fuer Noise Floor Messung)
        self._tx_audio_level = 1.0
        self._last_tx_peak = 0.0  # Peak-Level des letzten TX-Audio (0.0-x.x)
        self._is_transmitting = False
        self._meter_ids = {}
        self._dx_mode = False
        self._saved_normal_settings = {}  # Fuer Ruecksetzen nach DX
        # Diversity
        self._diversity_mode = False
        self._slice_idx_b = None
        self._rx_stream_id_b = None
        self._panafall_b = None  # Panadapter-Handle fuer Slice B
        self.on_audio_callback_b = None
        self._rx_callbacks = {}  # {stream_id: callback} Dispatch-Tabelle

    # ── Verbindung ──────────────────────────────────────────────

    # Exponential Backoff Stufen in Sekunden (DeepSeek: in FlexRadio kapseln)
    _RECONNECT_DELAYS = [5, 10, 20, 40, 60]

    def auto_connect(self, max_retries: int = 5, retry_delay: float = 3.0):
        """Auto-Discovery + Connect mit Retry bis Radio gefunden.

        Fuer den ersten Start: max_retries/retry_delay wie gehabt.
        """
        for attempt in range(max_retries):
            if not self.ip:
                devices = self.discover(timeout=2.0)
                if devices:
                    self.ip = devices[0]["ip"]
                    model = devices[0].get("model", "FlexRadio")
                    print(f"[FlexRadio] {model} gefunden @ {self.ip}")

            if self.ip:
                self.disconnect()
                time.sleep(0.5)
                ok = self.connect()
                if ok:
                    return True
                print(f"[FlexRadio] Retry {attempt + 1}/{max_retries}...")

            time.sleep(retry_delay)

        self.error.emit("FlexRadio nicht erreichbar nach allen Versuchen")
        return False

    def reconnect_forever(self, on_waiting=None):
        """Unbegrenzte Reconnect-Schleife mit Exponential Backoff.

        Wird von main_window in einem Hintergrund-Thread aufgerufen.
        on_waiting(delay_secs): Callback fuer UI-Countdown (jede Sekunde).
        Gibt True zurueck wenn verbunden, laeuft bis Verbindung steht
        oder self._abort_reconnect gesetzt wird.
        """
        self._abort_reconnect = False
        attempt = 0

        while not self._abort_reconnect:
            # Ab Versuch 10: Discovery-Modus (IP koennte sich geaendert haben)
            if attempt >= 10:
                print(f"[FlexRadio] Reconnect #{attempt}: Discovery-Modus (IP-Check)")
                devices = self.discover(timeout=3.0)
                if devices:
                    new_ip = devices[0]["ip"]
                    if new_ip != self.ip:
                        print(f"[FlexRadio] Neue IP gefunden: {new_ip} (war {self.ip})")
                        self.ip = new_ip

            if self.ip:
                self.disconnect()
                time.sleep(0.5)
                if not self._abort_reconnect:
                    ok = self.connect()
                    if ok:
                        return True

            # Exponential Backoff: 5→10→20→40→60→60→...
            delay = self._RECONNECT_DELAYS[
                min(attempt, len(self._RECONNECT_DELAYS) - 1)
            ]
            print(f"[FlexRadio] Reconnect #{attempt + 1} in {delay}s...")

            # Sekunden-weise warten damit UI-Countdown updaten kann
            for remaining in range(delay, 0, -1):
                if self._abort_reconnect:
                    return False
                if on_waiting:
                    on_waiting(remaining)
                time.sleep(1)

            attempt += 1

        return False

    def abort_reconnect(self):
        """Reconnect-Schleife abbrechen."""
        self._abort_reconnect = True

    def connect(self) -> bool:
        """Verbindung zum FlexRadio herstellen + Audio-Stream aufsetzen.

        2-Schritt-Verbindung (bewiesen in step4/step5 Tests):
        Phase 1: SmartSDR-M disconnecten (separate TCP-Session)
        Phase 2: Frisch verbinden + Setup + Keepalive
        """
        if not self.ip:
            self.error.emit("Keine FlexRadio IP konfiguriert")
            return False

        try:
            # Phase 1: SmartSDR-M disconnecten damit Receiver frei werden.
            # Ohne das belegt SmartSDR-M beide Receiver und wir koennen
            # keinen eigenen Slice erstellen.
            self._disconnect_smartsdr()

            # Phase 2: Frisch verbinden — jetzt gehoert der Slice uns
            self._tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_socket.settimeout(5.0)
            self._tcp_socket.connect((self.ip, self.port))
            self._tcp_socket.settimeout(0.5)
            self._running = True

            greeting = self._read_initial()
            print(f"[FlexRadio] Version: {greeting.get('version', '?')}")
            self._client_handle = greeting.get("handle", "")

            # Setup OHNE Reader-Thread (raw sends!)
            self._raw_send("client gui")
            time.sleep(5)  # Persistence laden lassen
            self._raw_flush()

            self._raw_send("client set send_reduced_bw_dax=1")
            self._raw_send("keepalive enable")
            for sub in ["slice", "tx", "audio", "dax", "radio", "meter"]:
                self._raw_send(f"sub {sub} all")
            time.sleep(1)
            flush_data = self._raw_flush()

            # Meter-Definitionen lernen (TX-Meter sofort, LEVEL erst nach Slice)
            self._raw_send("meter list")
            time.sleep(0.5)
            meter_data = flush_data + self._raw_flush()
            self._learn_meters_from_text(meter_data, slice_idx=None)

            # UDP-Socket (8MB Buffer!)
            if self._udp_socket:
                try:
                    self._udp_socket.close()
                except OSError:
                    pass
            self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self._udp_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024
            )
            self._udp_socket.bind(("", self._udp_port))
            self._udp_socket.settimeout(0.01)
            self._udp_socket.sendto(b"\x00", (self.ip, self.port))
            self._raw_send(f"client udpport {self._udp_port}")
            time.sleep(0.5)
            self._raw_flush()

            # Slice finden oder erstellen (Extra-Slices lassen — Radio hat 2 RX)
            self._slice_idx = self._find_or_create_slice()
            s = self._slice_idx
            print(f"[FlexRadio] Verwende Slice {s}")

            # JETZT LEVEL-Meter fuer unseren Slice lernen
            self._raw_send("meter list")
            time.sleep(0.5)
            self._learn_meters_from_text(self._raw_flush(), slice_idx=s)

            # Slice auf DIGU konfigurieren (Frequenz wird spaeter von _on_radio_connected gesetzt)
            self._raw_send(f"slice tune {s} 14.074")  # Default, wird ueberschrieben
            time.sleep(1)
            self._raw_send(f"slice set {s} mode=DIGU")
            time.sleep(1)
            self._raw_send(f"slice set {s} tx=1")
            self._raw_send("interlock tx1_enabled=1")
            self._raw_send("transmit set max_power_level=100")  # Volle 100W freischalten
            self._raw_send("transmit set rfpower=50")
            self._raw_send(f"slice set {s} dax=1")
            self._raw_send(f"dax audio set 1 slice={s}")
            time.sleep(0.5)
            # DAX fuer TX aktivieren — mic_selection NICHT aendern!
            # SmartSDR nutzt mic_selection=MI mit dax=1
            self._raw_send("transmit set dax=1")
            time.sleep(0.5)
            self._raw_flush()
            print("[FlexRadio] TX: dax=1 (wie SmartSDR)")

            # DAX RX Stream
            self._raw_send("stream create type=dax_rx dax_channel=1")
            time.sleep(1)
            resp = self._raw_flush()
            for line in resp.split("\n"):
                if line.startswith("R") and "|0|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3 and parts[2].strip():
                        try:
                            self._rx_stream_id = int(parts[2].strip(), 16)
                        except ValueError:
                            pass
            if self._rx_stream_id:
                print(f"[FlexRadio] RX Stream A: 0x{self._rx_stream_id:08X}")
                # In Dispatch-Tabelle registrieren (Callback wird spaeter gesetzt)
                self._rx_callbacks[self._rx_stream_id] = None

            # JETZT erst Threads starten (Setup ist fertig!)
            threading.Thread(target=self._tcp_read_loop, daemon=True).start()
            threading.Thread(target=self._udp_read_loop, daemon=True).start()
            self._start_keepalive()

            self.connected.emit()
            print("[FlexRadio] Verbunden — SimpleFT8 hat Kontrolle")
            return True

        except (socket.error, OSError) as e:
            self.error.emit(f"FlexRadio Verbindung fehlgeschlagen: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Verbindung trennen und Streams aufräumen."""
        was_running = self._running
        self._running = False
        self._keepalive_running = False
        if self._rx_stream_id is not None and self._tcp_socket:
            try:
                self._send_cmd(f"stream remove 0x{self._rx_stream_id:08X}")
            except (OSError, AttributeError):
                pass
        if self._tcp_socket:
            try:
                self._tcp_socket.close()
            except OSError:
                pass
        if self._udp_socket:
            try:
                self._udp_socket.close()
            except OSError:
                pass
        self._tcp_socket = None
        self._udp_socket = None
        self._rx_stream_id = None
        self._tx_stream_id = None
        if was_running:
            self.disconnected.emit()

    def _read_initial(self) -> dict:
        """Begrüßung vom Radio lesen (V=Version, H=Handle)."""
        result = {}
        buffer = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                data = self._tcp_socket.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line.startswith("V"):
                        result["version"] = line[1:]
                    elif line.startswith("H"):
                        result["handle"] = line[1:]
                if "version" in result and "handle" in result:
                    break
            except socket.timeout:
                continue
        return result

    def _raw_send(self, command: str):
        """Befehl senden ohne Lock/Thread (fuer Setup-Phase)."""
        self._sequence += 1
        line = f"C{self._sequence}|{command}\n"
        self._tcp_socket.sendall(line.encode("utf-8"))
        time.sleep(0.15)

    def _raw_flush(self) -> str:
        """Alle wartenden TCP-Daten lesen (fuer Setup-Phase)."""
        data = ""
        try:
            while True:
                data += self._tcp_socket.recv(32768).decode("utf-8", errors="replace")
        except (socket.timeout, OSError):
            pass
        return data

    def _disconnect_smartsdr(self):
        """SmartSDR-M (lokaler Display-Client) in separater TCP-Session disconnecten.

        Der FLEX-8400M hat einen eingebauten Display-Client der den Slice besitzt.
        Ohne Disconnect bekommt unser DAX-Stream nur Stille (Peak=0).
        Bewiesen in step4_disconnect_smartsdr.py.
        """
        print("[FlexRadio] Phase 1: SmartSDR-M suchen...")
        tmp_sock = None
        try:
            tmp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tmp_sock.settimeout(5.0)
            tmp_sock.connect((self.ip, self.port))
            tmp_sock.settimeout(0.5)

            # Greeting lesen
            tmp_handle = None
            buf = ""
            deadline = time.time() + 3.0
            while time.time() < deadline:
                try:
                    buf += tmp_sock.recv(4096).decode("utf-8", errors="replace")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.startswith("H"):
                            tmp_handle = line[1:].strip()
                except socket.timeout:
                    if tmp_handle:
                        break

            # Als GUI registrieren + Client-Liste holen
            tmp_seq = 0
            tmp_seq += 1
            tmp_sock.sendall(f"C{tmp_seq}|client gui\n".encode())
            time.sleep(3)
            tmp_seq += 1
            tmp_sock.sendall(f"C{tmp_seq}|sub client all\n".encode())
            time.sleep(1)

            # Alles lesen
            data = ""
            try:
                while True:
                    data += tmp_sock.recv(32768).decode("utf-8", errors="replace")
            except (socket.timeout, OSError):
                pass

            # SmartSDR-M Handle finden und disconnecten
            for line in data.split("\n"):
                if "SmartSDR" in line and "0x" in line:
                    for part in line.split():
                        if part.startswith("0x"):
                            candidate = part.rstrip(",")
                            if tmp_handle and candidate.lower() == f"0x{tmp_handle}".lower():
                                continue
                            print(f"[FlexRadio] SmartSDR-M gefunden: {candidate}")
                            tmp_seq += 1
                            tmp_sock.sendall(
                                f"C{tmp_seq}|client disconnect {candidate}\n".encode()
                            )
                            time.sleep(1)
                            print(f"[FlexRadio] SmartSDR-M disconnected!")
                            break

        except (socket.error, OSError) as e:
            print(f"[FlexRadio] SmartSDR-M Disconnect fehlgeschlagen: {e}")
        finally:
            if tmp_sock:
                try:
                    tmp_sock.close()
                except OSError:
                    pass
            time.sleep(2)  # Radio braucht kurz nach Disconnect

    def _start_keepalive(self):
        """Keepalive-Thread starten — sendet alle 5s ping.

        Ohne periodische Pings trennt das Radio die Verbindung nach ~10s.
        Bewiesen in step2_client_gui.py.
        """
        self._keepalive_running = True

        def loop():
            while self._keepalive_running and self._running:
                time.sleep(5)
                if not self._keepalive_running or not self._running:
                    break
                try:
                    with self._lock:
                        self._sequence += 1
                        self._tcp_socket.sendall(
                            f"C{self._sequence}|ping\n".encode()
                        )
                except (OSError, AttributeError):
                    break

        threading.Thread(target=loop, daemon=True, name="keepalive").start()
        print("[FlexRadio] Keepalive gestartet (ping alle 5s)")

    def _find_or_create_slice(self) -> int:
        """Ersten aktiven Slice finden oder neu erstellen.

        Nach SmartSDR-M Disconnect kann slices=0 sein!
        Dann muessen wir Panadapter + Slice selbst anlegen.
        Nutzt _raw_send weil Reader-Thread noch nicht laeuft.
        """
        # Persistence-Daten lesen die nach client gui kamen
        time.sleep(0.5)
        resp = self._raw_flush()

        # Ersten aktiven Slice suchen
        for line in resp.split("\n"):
            if "slice" in line and "in_use=1" in line:
                match = re.search(r"slice (\d+) in_use=1", line)
                freq_match = re.search(r"RF_frequency=(\S+)", line)
                if match:
                    idx = int(match.group(1))
                    freq = freq_match.group(1) if freq_match else "?"
                    print(f"[FlexRadio] Verwende Slice {idx} ({freq} MHz)")
                    return idx

        # Kein Slice vorhanden — Panadapter + Slice erstellen
        # Nach SmartSDR-M Disconnect sind die Receiver frei
        print("[FlexRadio] Kein Slice — erstelle Panadapter + Slice...")

        self._raw_send("display panafall create x=500 y=300")
        time.sleep(2)
        resp = self._raw_flush()

        # Panafall create gibt Panadapter+Waterfall IDs zurueck
        # und erstellt automatisch Slice 0
        panafall_ok = False
        for line in resp.split("\n"):
            if line.startswith("R") and "|0|" in line:
                panafall_ok = True
                print(f"[FlexRadio] Panadapter erstellt: {line.strip()[:80]}")

        if panafall_ok:
            # Slice sollte jetzt existieren
            self._raw_send("sub slice all")
            time.sleep(1)
            resp = self._raw_flush()
            for line in resp.split("\n"):
                if "slice" in line and "in_use=1" in line:
                    match = re.search(r"slice (\d+) in_use=1", line)
                    if match:
                        idx = int(match.group(1))
                        print(f"[FlexRadio] Slice {idx} aktiv")
                        return idx
            # Slice 0 als Default
            print("[FlexRadio] Panadapter OK, verwende Slice 0")
            return 0

        print("[FlexRadio] WARNUNG: Panadapter-Erstellung fehlgeschlagen!")
        return 0

    def _cleanup_extra_slices(self, keep_slice: int):
        """Alle Slices ausser keep_slice entfernen.

        Das FLEX-8400M hat 2 Empfaenger aber nur 1 Sender.
        Mehrere Slices blockieren potentiell TX.
        """
        self._raw_send("slice list")
        time.sleep(0.5)
        resp = self._raw_flush()
        for line in resp.split("\n"):
            if line.startswith("R") and "|0|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    indices = parts[2].strip().split()
                    for idx_str in indices:
                        try:
                            idx = int(idx_str)
                            if idx != keep_slice:
                                print(f"[FlexRadio] Entferne Extra-Slice {idx}")
                                self._raw_send(f"slice remove {idx}")
                                time.sleep(0.5)
                        except ValueError:
                            pass

    def _create_stream(self, command: str) -> int | None:
        """Stream erstellen und ID zurueckgeben."""
        resp = self._send_cmd_wait(command)
        if resp:
            for line in resp.split("\n"):
                if line.startswith("R") and "|0|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3 and parts[2].strip():
                        try:
                            return int(parts[2].strip(), 16)
                        except ValueError:
                            pass
        return None

    # ── Rig Control ─────────────────────────────────────────────

    # Preamp pro Band — Basiswerte (werden per DX-Preset angepasst)
    PREAMP_PRESETS = {
        "160m": 0, "80m": 0, "60m": 0,
        "40m": 10, "30m": 10,
        "20m": 10, "17m": 10,
        "15m": 20, "12m": 20, "10m": 20,
    }

    # DX-Presets: Radio-Einstellungen fuer verschiedene Einsatzzwecke
    # Jedes Preset definiert: agc_mode, agc_off_level, preamp_boost, Beschreibung
    DX_PRESETS = {
        "nah": {
            "agc_mode": "slow",
            "agc_threshold": 65,
            "preamp_boost": 0,     # Kein Extra-Preamp
            "desc": "NAH/EU: AGC slow, normaler Preamp",
        },
        "mittel": {
            "agc_mode": "slow",
            "agc_threshold": 50,
            "preamp_boost": 10,    # +10 dB extra
            "desc": "MITTEL-DX: AGC slow, +10dB Preamp",
        },
        "dx": {
            "agc_mode": "slow",
            "agc_threshold": 20,   # Niedrig = empfindlicher
            "preamp_boost": 20,    # +20 dB extra
            "desc": "EXTREM-DX: AGC slow(20), max Preamp",
        },
    }

    def dx_tune(self, callback=None):
        """DX-Einmessung: Antenne + RF-Gain automatisch optimieren.

        1. Noise Floor auf ANT1 messen
        2. Noise Floor auf ANT2 messen
        3. Beste Antenne waehlen (niedrigster Noise Floor)
        4. RF-Gain so einstellen dass Noise Rise 6-8 dB
        5. 32-bit float DAX aktivieren
        6. Ergebnis zurueckgeben

        callback(step, text) wird fuer Fortschrittsanzeige aufgerufen.
        """
        s = self._slice_idx
        results = {"ant1_dbm": -130, "ant2_dbm": -130, "best_ant": "ANT1",
                   "rf_gain": 0, "mode": "DX"}

        def log(step, text):
            print(f"[DX-Tune] {text}")
            self.dx_tune_progress.emit(text)

        # Aktuelle Einstellungen sichern
        self._saved_normal_settings = {
            "reduced_bw": True,
        }

        log(10, "Messe Noise Floor auf ANT1...")
        self._send_cmd(f"slice set {s} rxant=ANT1")
        self._send_cmd(f"slice set {s} rfgain=0")
        time.sleep(2.0)  # Laenger warten bis Meter sich stabilisiert
        ant1_floor = self._last_fwdpwr_dbm
        log(20, f"  ANT1 Noise Floor: {ant1_floor:.1f} dBm")

        log(30, "Messe Noise Floor auf ANT2...")
        self._send_cmd(f"slice set {s} rxant=ANT2")
        time.sleep(2.0)
        ant2_floor = self._last_fwdpwr_dbm
        log(35, f"  ANT2 Noise Floor: {ant2_floor:.1f} dBm")

        results["ant1_dbm"] = ant1_floor
        results["ant2_dbm"] = ant2_floor

        # Beste Antenne: niedrigerer Noise Floor = besser fuer schwache Signale
        if ant2_floor < ant1_floor:
            results["best_ant"] = "ANT2"
            log(40, f"ANT2 besser ({ant2_floor:.0f} vs {ant1_floor:.0f} dBm)")
        else:
            results["best_ant"] = "ANT1"
            self._send_cmd(f"slice set {s} rxant=ANT1")
            log(40, f"ANT1 besser ({ant1_floor:.0f} vs {ant2_floor:.0f} dBm)")

        # TX bleibt IMMER auf ANT1!
        self._send_cmd(f"slice set {s} txant=ANT1")

        # RF-Gain optimieren: Preamp schrittweise erhoehen
        # Ziel: 6-8 dB Noise Rise ueber internem Floor
        log(50, "Optimiere RF-Gain...")

        # Basis: interner Floor bei Gain 0 (mehrfach messen + mitteln)
        self._send_cmd(f"slice set {s} rfgain=0")
        time.sleep(2.0)
        samples = []
        for _ in range(5):
            time.sleep(0.3)
            samples.append(self._last_fwdpwr_dbm)
        base_floor = sum(samples) / len(samples)
        log(55, f"  Basis Noise Floor: {base_floor:.1f} dBm")

        best_gain = 0
        for gain in [10, 20, 30]:
            self._send_cmd(f"slice set {s} rfgain={gain}")
            time.sleep(2.0)
            # Mehrfach messen
            samples = []
            for _ in range(5):
                time.sleep(0.3)
                samples.append(self._last_fwdpwr_dbm)
            current = sum(samples) / len(samples)
            rise = current - base_floor
            log(50 + gain, f"  RF-Gain {gain} dB → {current:.1f} dBm, Rise {rise:.1f} dB")

            if 6.0 <= rise <= 10.0:
                best_gain = gain
                break
            elif rise > 10.0:
                best_gain = max(0, gain - 10)
                self._send_cmd(f"slice set {s} rfgain={best_gain}")
                break
            best_gain = gain

        results["rf_gain"] = best_gain
        log(80, f"Optimaler RF-Gain: {best_gain} dB")

        # 32-bit float DAX aktivieren
        self._send_cmd("client set send_reduced_bw_dax=0")
        log(90, "32-bit float 48kHz aktiviert")

        self._dx_mode = True
        log(100, f"DX-Tune fertig: {results['best_ant']}, "
            f"RF-Gain {best_gain} dB, 32-bit float")

        return results

    def dx_reset(self):
        """DX-Modus zuruecksetzen auf Normal-Einstellungen."""
        s = self._slice_idx
        self._send_cmd(f"slice set {s} rxant=ANT1")
        self._send_cmd(f"slice set {s} txant=ANT1")
        preamp = self.PREAMP_PRESETS.get("20m", 10)
        self._send_cmd(f"slice set {s} rfgain={preamp}")
        self._send_cmd("client set send_reduced_bw_dax=1")
        self._dx_mode = False
        print("[FlexRadio] Normal-Modus wiederhergestellt")

    # ── Diversity ─────────────────────────────────────────────

    def enable_diversity(self, freq_mhz: float, band: str = "20m",
                         ant: str = "ANT2", gain: int = 20):
        """Diversity-Modus: 2. Slice auf gleicher Frequenz mit anderer Antenne.

        Erstellt Slice B mit eigenem DAX-Channel und RX-Stream.
        TX bleibt auf Slice A / ANT1.
        """
        if self._diversity_mode:
            return
        s_a = self._slice_idx

        # 2. Panadapter + Slice erstellen (FLEX braucht eigenen Panadapter pro SCU)
        # _send_cmd (fire-and-forget) statt _send_cmd_wait — das FLEX
        # bestaetigt panafall create manchmal asynchron
        cmd = "display panafall create x=500 y=300"
        print(f"[Diversity] CMD: {cmd}")
        self._send_cmd(cmd)

        # Warten bis der neue Slice erscheint (FLEX erstellt ihn asynchron)
        time.sleep(3)

        # Neuen Panadapter finden
        resp_post = self._send_cmd_wait("display panafall list", timeout=2.0)
        print(f"[Diversity] Panafall nach create: '{resp_post}'")

        # Neuen Slice finden
        idx_b = None
        resp3 = self._send_cmd_wait("slice list", timeout=3.0)
        print(f"[Diversity] slice list: '{resp3}'")
        if resp3:
            for line in resp3.split("\n"):
                if "|0|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        for idx_str in parts[2].strip().split():
                            try:
                                idx = int(idx_str)
                                if idx != s_a:
                                    idx_b = idx
                            except ValueError:
                                continue

        if idx_b is None:
            print(f"[Diversity] FEHLER: Kein 2. Slice gefunden!")
            return
        # Panadapter-Handle = 0x4000000 + idx_b (Konvention)
        self._panafall_b = f"0x4000000{idx_b}"

        self._slice_idx_b = idx_b
        print(f"[Diversity] Slice B gefunden: idx={idx_b}")

        # Slice B konfigurieren: Frequenz + Antenne + Filter
        self._send_cmd(f"slice tune {idx_b} {freq_mhz}")
        self._send_cmd(f"slice set {idx_b} rxant={ant}")
        self._send_cmd(f"slice set {idx_b} rfgain={gain}")
        self._send_cmd(f"slice set {idx_b} mode=DIGU")
        self._send_cmd(f"slice set {idx_b} nr=0")
        self._send_cmd(f"slice set {idx_b} nb=0")
        self._send_cmd(f"slice set {idx_b} anf=0")
        self._send_cmd(f"slice set {idx_b} filter_lo=100")
        self._send_cmd(f"slice set {idx_b} filter_hi=3100")
        self._send_cmd(f"slice set {idx_b} agc_mode=slow")

        # DAX Channel 2 zuweisen
        self._send_cmd(f"slice set {idx_b} dax=2")
        self._send_cmd(f"dax audio set 2 slice={idx_b}")
        time.sleep(0.5)

        # 2. RX Stream erstellen (mit _send_cmd_wait fuer Response)
        cmd2 = "stream create type=dax_rx dax_channel=2"
        print(f"[Diversity] CMD: {cmd2}")
        resp2 = self._send_cmd_wait(cmd2, timeout=3.0)
        print(f"[Diversity] Response stream create: '{resp2}'")
        if resp2:
            for line in resp2.split("\n"):
                if "|0|" in line:
                    parts = line.split("|")
                    print(f"[Diversity] Stream parts: {parts}")
                    if len(parts) >= 3 and parts[2].strip():
                        try:
                            sid = int(parts[2].strip(), 16)
                            self._rx_stream_id_b = sid
                        except ValueError:
                            pass

        if self._rx_stream_id_b:
            self._rx_callbacks[self._rx_stream_id_b] = self.on_audio_callback_b
            print(f"[Diversity] RX Stream B: 0x{self._rx_stream_id_b:08X}")
            print(f"[Diversity] Callback B: {self.on_audio_callback_b}")
        else:
            print("[Diversity] FEHLER: Stream B ID nicht erkannt!")
            return

        # Audio-Subscriptions erneuern + UDP-Ping (manche Firmware braucht das)
        self._send_cmd("sub audio all")
        self._send_cmd("sub dax all")
        time.sleep(0.3)
        # UDP-Ping an Radio damit der neue Stream startet
        if self._udp_socket and self.ip:
            try:
                self._udp_socket.sendto(b"\x00", (self.ip, self.port))
                print("[Diversity] UDP-Ping gesendet")
            except OSError:
                pass

        self._diversity_mode = True
        print(f"[Diversity] AKTIV: Slice A={s_a}(ANT1) + "
              f"Slice B={idx_b}({ant}, Gain {gain})")

    def disable_diversity(self):
        """Diversity-Modus beenden: Stream + Slice + Panadapter entfernen."""
        if not self._diversity_mode:
            return

        # Stream B entfernen
        if self._rx_stream_id_b:
            self._send_cmd(f"stream remove 0x{self._rx_stream_id_b:08X}")
            self._rx_callbacks.pop(self._rx_stream_id_b, None)
            self._rx_stream_id_b = None

        # Slice B entfernen
        if self._slice_idx_b is not None:
            self._send_cmd(f"slice remove {self._slice_idx_b}")
            time.sleep(0.5)
            self._slice_idx_b = None

        # Beim FLEX wird der Panadapter automatisch entfernt
        # wenn der letzte Slice darauf entfernt wird.
        # Falls nicht: nochmal alle Extra-Slices aufraeumen
        time.sleep(0.5)
        resp = self._send_cmd_wait("slice list", timeout=2.0)
        if resp and "|0|" in resp:
            parts = resp.split("|")
            if len(parts) >= 3:
                for idx_str in parts[2].strip().split():
                    try:
                        idx = int(idx_str)
                        if idx != self._slice_idx:
                            self._send_cmd(f"slice remove {idx}")
                            print(f"[Diversity] Extra-Slice {idx} entfernt")
                    except ValueError:
                        pass

        self._diversity_mode = False
        self.on_audio_callback_b = None
        print("[Diversity] Deaktiviert")

    def set_frequency(self, freq_mhz: float, slice_idx: int = 0):
        """Frequenz setzen in MHz. Bei Diversity beide Slices synchron."""
        self._send_cmd(f"slice tune {slice_idx} {freq_mhz}")
        if self._diversity_mode and self._slice_idx_b is not None:
            self._send_cmd(f"slice tune {self._slice_idx_b} {freq_mhz}")

    def set_mode(self, mode: str, slice_idx: int = 0):
        """Betriebsart setzen (DIGU für FT8)."""
        self._send_cmd(f"slice set {slice_idx} mode={mode}")

    def set_power(self, power_percent: int):
        """Sendeleistung in Prozent (0-100). max_power_level=100 wird immer zuerst gesetzt,
        da Bandwechsel das Radio-Profil laden und den Wert ueberschreiben koennen."""
        self._send_cmd("transmit set max_power_level=100")
        self._send_cmd(f"transmit set rfpower={power_percent}")

    def check_swr_safe(self) -> bool:
        """Return True if SWR is below the safety limit."""
        return self._last_swr < self._swr_limit

    def set_tx_level(self, level: float):
        """Set TX audio level (0.0 to 1.5). Steuert FlexRadio mic_level (0-100) UND Software-Gain.
        Ueber 100% (1.0) wird das Audio-Signal im Software-Pfad verstaerkt (mic_level bleibt 100)."""
        self._tx_audio_level = max(0.0, min(1.5, level))
        mic_level = min(100, int(level * 100))
        self._send_cmd(f"transmit set mic_level={mic_level}")

    def ptt_on(self):
        if not self.check_swr_safe():
            print(f"[TX] SWR ALARM: {self._last_swr:.1f} >= {self._swr_limit:.1f} — TX blockiert!")
            self.swr_alarm.emit(self._last_swr)
            return
        print("[TX] PTT ON (xmit 1)")
        self._is_transmitting = True
        resp = self._send_cmd_wait("xmit 1", timeout=2.0)
        if resp:
            print(f"[TX] xmit Response: {resp.strip()[:100]}")

    def ptt_off(self):
        print("[TX] PTT OFF (xmit 0)")
        self._is_transmitting = False
        self._send_cmd("xmit 0")

    def tune_on(self):
        """Tune-Modus starten (interner Testton vom Radio)."""
        self._send_cmd("transmit tune 1")

    def tune_off(self):
        """Tune-Modus stoppen."""
        self._send_cmd("transmit tune 0")

    def apply_ft8_preset(self, slice_idx: int = 0, band: str = "20m",
                         dx_mode: str = "mittel"):
        """FT8-Einstellungen am FLEX-8400M nach DX-Preset.

        dx_mode:
          'nah'    — EU/Nahbereich: AGC slow(65), normaler Preamp
          'mittel' — Mittel-DX: AGC slow(50), erhoehter Preamp
          'dx'     — Extrem-DX: AGC slow(20), max Preamp, max Empfindlichkeit
        """
        preset = self.DX_PRESETS.get(dx_mode, self.DX_PRESETS["mittel"])
        base_preamp = self.PREAMP_PRESETS.get(band, 10)
        preamp = min(base_preamp + preset["preamp_boost"], 30)  # Max 30 dB

        cmds = [
            f"slice set {slice_idx} mode=DIGU",
            # Alles aus was FT8-Signale verfaelscht
            f"slice set {slice_idx} nr=0",
            f"slice set {slice_idx} nb=0",
            f"slice set {slice_idx} anf=0",
            f"slice set {slice_idx} wnb=0",
            f"slice set {slice_idx} nbfm=0",   # Kein FM-Noise-Blanker
            f"slice set {slice_idx} apf=0",     # Kein Audio-Peak-Filter
            # FT8 Bandbreite (100-3100Hz: FT8-Signale starten bei ~200Hz)
            f"slice set {slice_idx} filter_lo=100",
            f"slice set {slice_idx} filter_hi=3100",
            # Preamp
            f"slice set {slice_idx} rfgain={preamp}",
        ]

        # AGC nach DX-Preset
        agc_mode = preset["agc_mode"]
        cmds.append(f"slice set {slice_idx} agc_mode={agc_mode}")
        if agc_mode == "off":
            off_level = preset.get("agc_off_level", 20)
            cmds.append(f"slice set {slice_idx} agc_off_level={off_level}")
        else:
            threshold = preset.get("agc_threshold", 65)
            cmds.append(f"slice set {slice_idx} agc_threshold={threshold}")

        for cmd in cmds:
            self._send_cmd(cmd)

        print(f"[FlexRadio] Preset '{dx_mode}': {band}, DIGU, "
              f"AGC={agc_mode}, Preamp={preamp}dB — {preset['desc']}")

    # ── TX Audio ────────────────────────────────────────────────

    def send_audio(self, audio_float_mono: np.ndarray, sample_rate: int = 48000):
        """Audio via VITA-49 dax_tx senden — AetherSDR Radio-native DAX Route.

        Format: int16 MONO big-endian, PCC 0x0123, 128 Samples/Paket.
        Header: TSI=3, TSF=1 (wie nDAX/FlexLib).
        """
        if self._tx_stream_id is None or self._udp_socket is None:
            print("[TX] FEHLER: kein TX Stream oder kein UDP Socket")
            return

        audio = audio_float_mono.astype(np.float32)
        if np.max(np.abs(audio)) > 1.5:
            audio = audio / 32768.0

        # Auf 24kHz resamplen (reduced BW DAX = 24kHz)
        if sample_rate == 48000:
            audio = audio[::2]  # 48k → 24k
        elif sample_rate != 24000:
            ratio = 24000 / sample_rate
            n_out = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, n_out),
                np.arange(len(audio)), audio
            ).astype(np.float32)

        # TX audio level anwenden
        audio = audio * self._tx_audio_level

        # Peak-Level messen VOR Clipping (fuer Signal-Qualitaets-Monitoring)
        self._last_tx_peak = float(np.max(np.abs(audio)))
        if self._last_tx_peak > 1.0:
            print(f"[TX] CLIPPING! Peak={self._last_tx_peak:.2f} bei TxLvl={self._tx_audio_level:.2f}")

        # Float → int16 big-endian mono (wie AetherSDR Zeile 956-958)
        mono_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)

        # 128 Mono-Samples pro Paket (256 Bytes Payload)
        SAMPLES_PER_PKT = 128
        pkt_count = 0
        t_start = time.time()

        print(f"[TX] Sende {len(mono_int16)} Samples int16 mono 24kHz, "
              f"Stream 0x{self._tx_stream_id:08X}")

        for offset in range(0, len(mono_int16), SAMPLES_PER_PKT):
            chunk = mono_int16[offset:offset + SAMPLES_PER_PKT]
            if len(chunk) < SAMPLES_PER_PKT:
                chunk = np.pad(chunk, (0, SAMPLES_PER_PKT - len(chunk)))

            payload_bytes = SAMPLES_PER_PKT * 2  # 256 bytes
            total_words = 7 + payload_bytes // 4  # 7 + 64 = 71

            # Header: Type=1, C=1, TSI=3, TSF=1 (wie AetherSDR/nDAX)
            w0 = ((1 << 28) | (1 << 27) | (3 << 22) | (1 << 20)
                  | ((pkt_count & 0xF) << 16) | (total_words & 0xFFFF))

            header = struct.pack(
                ">7I", w0, self._tx_stream_id, FLEX_OUI,
                (FLEX_ICC << 16) | PCC_AUDIO_INT16,  # PCC 0x0123!
                0, 0, 0,
            )
            payload = chunk.astype(">i2").tobytes()  # Big-endian int16

            try:
                self._udp_socket.sendto(header + payload, (self.ip, 4991))
            except OSError:
                break

            pkt_count += 1
            expected = t_start + pkt_count * (SAMPLES_PER_PKT / 24000.0)
            delta = expected - time.time()
            if delta > 0:
                time.sleep(delta)

        elapsed = time.time() - t_start
        print(f"[TX] {pkt_count} Pakete in {elapsed:.2f}s (int16 mono 24kHz)")

    def create_tx_stream(self):
        """TX Audio-Stream erstellen — versucht remote_audio_tx, dann dax_tx."""
        # remote_audio_tx = fuer Netzwerk-Clients (wir!)
        # dax_tx = fuer lokale DAX-Clients (SmartSDR)
        # Nur dax_tx — remote_audio_tx blockiert die Leistung
        for stream_type in ["dax_tx"]:
            resp = self._send_cmd_wait(f"stream create type={stream_type}")
            if resp:
                for line in resp.split("\n"):
                    if line.startswith("R") and "|0|" in line:
                        parts = line.split("|")
                        if len(parts) >= 3 and parts[2].strip():
                            try:
                                sid = int(parts[2].strip(), 16)
                                print(f"[FlexRadio] TX Stream ({stream_type}): "
                                      f"0x{sid:08X}")
                                # remote_audio_tx ist der Stream fuer Opus-Audio
                                if "remote" in stream_type:
                                    self._tx_stream_id = sid
                                elif self._tx_stream_id is None:
                                    self._tx_stream_id = sid
                            except ValueError:
                                pass
                    elif line.startswith("R") and "|0|" not in line:
                        print(f"[FlexRadio] {stream_type} fehlgeschlagen: "
                              f"{line.strip()[:80]}")
        if self._tx_stream_id:
            print(f"[FlexRadio] TX Audio Stream: 0x{self._tx_stream_id:08X}")
        else:
            print("[FlexRadio] WARNUNG: Kein TX Stream erstellt!")

    # ── TCP Command Channel ─────────────────────────────────────

    def _send_cmd(self, command: str):
        """Befehl senden (fire-and-forget)."""
        if not self._tcp_socket or not self._running:
            return
        with self._lock:
            self._sequence += 1
            line = f"C{self._sequence}|{command}\n"
            try:
                self._tcp_socket.sendall(line.encode("utf-8"))
            except (socket.error, OSError) as e:
                self.error.emit(f"Senden fehlgeschlagen: {e}")

    def _send_cmd_wait(self, command: str, timeout: float = 3.0) -> str | None:
        """Befehl senden und auf Antwort warten."""
        if not self._tcp_socket or not self._running:
            return None
        with self._lock:
            self._sequence += 1
            seq = self._sequence
            event = threading.Event()
            self._response_events[seq] = event
            line = f"C{seq}|{command}\n"
            try:
                self._tcp_socket.sendall(line.encode("utf-8"))
            except (socket.error, OSError):
                return None

        event.wait(timeout)
        return self._responses.pop(seq, None)

    def _tcp_read_loop(self):
        """TCP-Empfangsschleife für Befehls-Antworten und Status."""
        buffer = ""
        while self._running and self._tcp_socket:
            try:
                data = self._tcp_socket.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self._handle_tcp_line(line.strip())
            except socket.timeout:
                continue
            except (socket.error, OSError):
                break

        if self._running:
            self._running = False
            self.disconnected.emit()

    def _handle_tcp_line(self, line: str):
        """TCP-Zeile verarbeiten."""
        if not line:
            return

        # Response: R<seq>|<code>|<body>
        if line.startswith("R"):
            match = re.match(r"R(\d+)\|(.+)", line)
            if match:
                seq = int(match.group(1))
                body = match.group(2)
                self._responses[seq] = line
                event = self._response_events.pop(seq, None)
                if event:
                    event.set()
                # Memory Leak Fix: alte Responses entfernen (max 200 behalten)
                if len(self._responses) > 200:
                    oldest_keys = sorted(self._responses.keys())[:100]
                    for k in oldest_keys:
                        self._responses.pop(k, None)

        # Status: Slice-Frequenz-Updates
        if "slice" in line and "RF_frequency" in line:
            match = re.search(r"RF_frequency=(\d+\.?\d*)", line)
            if match:
                self.frequency_changed.emit(float(match.group(1)))

        # Meter-Definitionen lernen (TCP) — wiederverwendbare Methode
        if "meter" in line and ".nam=" in line:
            self._learn_meters_from_text(line, slice_idx=self._slice_idx)

    # ── UDP VITA-49 Audio ───────────────────────────────────────

    def _udp_read_loop(self):
        """UDP-Empfangsschleife für VITA-49 Audio-Pakete."""
        packets_received = 0
        while self._running and self._udp_socket:
            try:
                data, addr = self._udp_socket.recvfrom(2048)
                if len(data) < VITA49_HEADER_SIZE:
                    continue

                # Radio-Port auto-detect (fuer TX-Pakete)
                if self._radio_udp_port is None and addr[0] == self.ip:
                    self._radio_udp_port = addr[1]
                    print(f"[FlexRadio] Radio UDP Port: {addr[1]}")

                # VITA-49 Header parsen
                header = struct.unpack(">7I", data[:VITA49_HEADER_SIZE])
                word0 = header[0]
                stream_id = header[1]
                pcc = header[3] & 0xFFFF

                # Debug: alle PCC-Typen loggen (einmalig)
                if not hasattr(self, '_pcc_seen'):
                    self._pcc_seen = set()
                if pcc not in self._pcc_seen:
                    self._pcc_seen.add(pcc)
                    print(f"[UDP] Neuer PCC: 0x{pcc:04X}, Stream 0x{stream_id:08X}, {len(data)} bytes")

                # Meter-Pakete (PCC 0x8002): uint16 ID + int16 Wert Paare
                if pcc == 0x8002:
                    payload = data[VITA49_HEADER_SIZE:]
                    if len(payload) >= 4:
                        self._process_meter_packet(payload)
                    continue

                # Audio-Stream per Dispatch-Tabelle oder direktem ID-Check
                callback = self._rx_callbacks.get(stream_id)
                if callback is None:
                    # Fallback: Stream A per on_audio_callback
                    if self._rx_stream_id and stream_id == self._rx_stream_id:
                        callback = self.on_audio_callback
                    elif self._rx_stream_id_b and stream_id == self._rx_stream_id_b:
                        callback = self.on_audio_callback_b
                    else:
                        continue

                # Trailer prüfen (Bit 26 von Word 0)
                has_trailer = (word0 >> 26) & 1
                payload_end = -4 if has_trailer else len(data)
                payload = data[VITA49_HEADER_SIZE:payload_end]

                if not payload:
                    continue

                # Audio dekodieren je nach Format
                samples = None
                if pcc == PCC_AUDIO_INT16:
                    # int16 mono, big-endian → numpy
                    samples = np.frombuffer(payload, dtype=">i2").astype(np.int16)
                    packets_received += 1

                elif pcc == PCC_AUDIO_FLOAT32:
                    # float32 stereo 48kHz big-endian → mono 24kHz int16
                    floats = np.frombuffer(payload, dtype=">f4")
                    mono = floats[0::2]  # Stereo → Mono (nur L)
                    mono_24k = mono[::2]  # 48kHz → 24kHz
                    samples = (np.clip(mono_24k, -1.0, 1.0) * 32767).astype(np.int16)
                    packets_received += 1

                if samples is not None:
                    if callback:
                        callback(samples)
                    # Erstes Audio-Paket loggen
                    if packets_received == 1:
                        print(f"[FlexRadio] Audio-Paket: "
                              f"PCC=0x{pcc:04X}, Stream=0x{stream_id:08X}")

            except socket.timeout:
                continue
            except (socket.error, OSError):
                break

    def _learn_meters_from_text(self, text: str, slice_idx=None):
        """Meter-Definitionen aus TCP-Text lernen.

        Format: "...meter N.src=TX#N.nam=FWDPWR#N.unit=dBm#N.num=0..."
        TX-Meter (FWDPWR, SWR, HWALC) werden immer gelernt.
        LEVEL wird NUR gelernt wenn src=SLC und num=slice_idx.
        """
        for line in text.split("\n"):
            line = line.strip()
            if not line or ".nam=" not in line:
                continue
            tokens = line.replace("|", "#").split("#")
            for tok in tokens:
                tok = tok.strip()
                if ".nam=" not in tok:
                    continue
                try:
                    dot = tok.index(".")
                    mid = int(tok[:dot].split()[-1])
                except (ValueError, IndexError):
                    continue
                # Alle Felder fuer diese Meter-ID extrahieren
                prefix = f"{mid}."
                name = src = num_str = ""
                for kv in tokens:
                    kv = kv.strip()
                    if kv.startswith(prefix + "nam="):
                        name = kv.split("=", 1)[1]
                    elif kv.startswith(prefix + "src="):
                        src = kv.split("=", 1)[1]
                    elif kv.startswith(prefix + "num="):
                        num_str = kv.split("=", 1)[1]

                # TX-Meter: immer lernen
                if name in ("FWDPWR", "SWR", "HWALC") and src.startswith("TX"):
                    self._meter_ids[name] = mid
                    print(f"[FlexRadio] Meter {name}={mid} (src={src})")

                # LEVEL: NUR wenn src=SLC und num=unser Slice
                if name == "LEVEL" and src == "SLC":
                    try:
                        meter_slice = int(num_str)
                    except (ValueError, TypeError):
                        meter_slice = -1
                    if slice_idx is None or meter_slice == slice_idx:
                        self._meter_ids["LEVEL"] = mid
                        print(f"[FlexRadio] Meter LEVEL={mid} "
                              f"(src=SLC, slice={meter_slice})")

    def _process_meter_packet(self, payload: bytes):
        """VITA-49 Meter-Paket parsen (PCC 0x8002).

        Format: N Paare von (uint16 meter_id, int16 raw_value).
        Wert = raw / 128.0 fuer dBm/dB/SWR.
        Meter-IDs werden dynamisch gelernt wenn noch unbekannt.
        """
        n_pairs = len(payload) // 4
        for i in range(n_pairs):
            off = i * 4
            mid = struct.unpack(">H", payload[off:off + 2])[0]
            raw = struct.unpack(">h", payload[off + 2:off + 4])[0]
            val = raw / 128.0

            # Auto-Detect: waehrend TX, Meter mit dBm > -10 = FWDPWR
            if not self._meter_ids.get("FWDPWR") and self._is_transmitting:
                if -30 < val < 60:  # Plausibel fuer dBm
                    self._meter_ids["FWDPWR"] = mid
                    print(f"[FlexRadio] Meter FWDPWR auto-detect: ID {mid}")

            if mid == self._meter_ids.get("FWDPWR"):
                watts = 10 ** ((val - 30) / 10) if val > -50 else 0
                self.meter_update.emit("FWDPWR", watts)
            elif mid == self._meter_ids.get("SWR"):
                # SWR-Wert: raw/128 bei normalen Werten, sonst raw direkt
                # Gueltige SWR: 1.0 - 50.0
                swr = val
                if swr < 1.0 or swr > 50.0:
                    # Vielleicht raw nicht durch 128 teilen fuer SWR
                    swr = raw / 256.0  # Alternativer Divisor
                if swr < 1.0:
                    swr = 1.0
                if 1.0 <= swr <= 50.0:
                    self._last_swr = swr
                    self.meter_update.emit("SWR", swr)
                    if self._is_transmitting and swr >= self._swr_limit:
                        print(f"[TX] SWR ALARM: {swr:.1f}!")
                        self.swr_alarm.emit(swr)
            elif mid == self._meter_ids.get("HWALC"):
                if self._is_transmitting and abs(val) > 0.01:
                    print(f"[Meter] HWALC raw={raw} val={val:.2f} dB")
                self.meter_update.emit("ALC", val)
            elif mid == self._meter_ids.get("LEVEL"):
                self._last_fwdpwr_dbm = val
                # Debug: alle paar Sekunden loggen
                if not hasattr(self, '_lvl_dbg_t'):
                    self._lvl_dbg_t = 0
                import time as _t
                if _t.time() - self._lvl_dbg_t > 3:
                    self._lvl_dbg_t = _t.time()
                    print(f"[Meter] LEVEL raw={raw} val={val:.1f} dBm")
                # Debug: ALC beim ersten TX loggen
                if self._is_transmitting and not hasattr(self, '_alc_dbg'):
                    self._alc_dbg = True
                    print(f"[Meter] ALC raw={raw} val={val:.1f}dB")

    def _build_vita49_packet(self, stream_id: int, pcc: int,
                              payload: bytes) -> bytes:
        """VITA-49 Paket bauen."""
        if not isinstance(stream_id, int) or not isinstance(pcc, int):
            raise ValueError(f"stream_id={stream_id!r} pcc={pcc!r} — kein TX-Stream aktiv?")
        # Word 0: type=1(IFData), C=1, no trailer, packet size in words
        total_words = 7 + len(payload) // 4
        word0 = (0x1 << 28) | (1 << 27) | (total_words & 0xFFFF)
        word1 = stream_id
        word2 = FLEX_OUI
        word3 = (FLEX_ICC << 16) | pcc
        word4 = 0  # timestamp
        word5 = 0
        word6 = 0

        header = struct.pack(">7I", word0, word1, word2, word3,
                              word4, word5, word6)
        return header + payload

    # ── Discovery ───────────────────────────────────────────────

    @staticmethod
    def discover(timeout: float = 2.0) -> list[dict]:
        """FlexRadio-Geräte im Netzwerk per UDP-Discovery finden."""
        devices = []
        seen = set()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            sock.bind(("", 4992))

            end = time.time() + timeout
            while time.time() < end:
                try:
                    data, addr = sock.recvfrom(1024)
                    if addr[0] in seen:
                        continue
                    seen.add(addr[0])
                    text = data.decode("utf-8", errors="replace")
                    device = {"ip": addr[0], "raw": text}
                    for field in text.split():
                        if "=" in field:
                            key, val = field.split("=", 1)
                            device[key] = val
                    devices.append(device)
                except socket.timeout:
                    break
            sock.close()
        except OSError:
            pass
        return devices
