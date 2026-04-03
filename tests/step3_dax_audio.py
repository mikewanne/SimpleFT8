#!/usr/bin/env python3
"""Schritt 3: Slice konfigurieren + DAX RX Audio-Stream.

Macht:
1. Discovery + TCP connect + client gui + keepalive
2. Slice auf 14.074 DIGU (FT8 20m) konfigurieren
3. DAX Channel 1 an Slice binden
4. DAX RX Stream erstellen
5. UDP lauschen — kommen VITA-49 Audio-Pakete?
6. Audio-Statistik ausgeben (Pakete, Peak, Format)

Das ist der Moment der Wahrheit: kommt Audio oder nicht?
"""

import socket
import struct
import time
import sys
import threading
import numpy as np


VITA49_HEADER_SIZE = 28
PCC_FLOAT32 = 0x03E3
PCC_INT16 = 0x0123


def discover(timeout=3.0):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", 4992))
        data, addr = sock.recvfrom(1024)
        sock.close()
        info = {"ip": addr[0]}
        for field in data.decode("utf-8", errors="replace").split():
            if "=" in field:
                k, v = field.split("=", 1)
                info[k] = v
        print(f"[Discovery] {info.get('model', '?')} @ {info['ip']}")
        return info
    except (socket.timeout, OSError) as e:
        print(f"[Discovery] Fehler: {e}")
        return None


class RadioTester:
    def __init__(self, ip):
        self.ip = ip
        self.sock = None
        self.udp = None
        self.seq = 0
        self.running = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.ip, 4992))
        self.sock.settimeout(0.5)

        # Greeting
        handle = None
        buf = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                buf += self.sock.recv(4096).decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.startswith("H"):
                        handle = line[1:].strip()
            except socket.timeout:
                if handle:
                    break
        print(f"[TCP] Handle: {handle}")
        return handle

    def send(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        print(f"  >>> {cmd}")
        time.sleep(0.15)

    def flush(self):
        """Alles lesen, Responses (R...) zurueckgeben."""
        data = ""
        try:
            while True:
                data += self.sock.recv(32768).decode("utf-8", errors="replace")
        except (socket.timeout, OSError):
            pass
        responses = []
        for line in data.split("\n"):
            line = line.strip()
            if line.startswith("R"):
                print(f"  <<< {line}")
                responses.append(line)
            elif line.startswith("M"):
                print(f"  <<< {line}")
        return responses

    def setup_udp(self):
        """UDP-Socket fuer VITA-49 Audio."""
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
        self.udp.bind(("", 4991))
        self.udp.settimeout(0.1)
        # Registration packet
        self.udp.sendto(b"\x00", (self.ip, 4992))
        print("[UDP] Socket bereit auf Port 4991 (8MB Buffer)")

    def start_keepalive(self):
        def loop():
            while self.running:
                time.sleep(5)
                if not self.running:
                    break
                try:
                    self.seq += 1
                    self.sock.sendall(f"C{self.seq}|ping\n".encode())
                except OSError:
                    break
        threading.Thread(target=loop, daemon=True).start()

    def listen_audio(self, duration=30):
        """VITA-49 Audio-Pakete empfangen und Statistik ausgeben."""
        print(f"\n[Audio] Lausche {duration}s auf VITA-49 Pakete...")
        print("-" * 60)

        start = time.time()
        stats = {
            "total_packets": 0,
            "audio_packets": 0,
            "other_packets": 0,
            "stream_ids": {},
            "pccs": {},
            "peak": 0,
            "total_samples": 0,
            "first_audio_at": None,
        }

        while time.time() - start < duration:
            try:
                data, addr = self.udp.recvfrom(4096)
                stats["total_packets"] += 1

                if len(data) < VITA49_HEADER_SIZE:
                    stats["other_packets"] += 1
                    continue

                header = struct.unpack(">7I", data[:VITA49_HEADER_SIZE])
                stream_id = header[1]
                pcc = header[3] & 0xFFFF

                # Stream-ID tracken
                sid_hex = f"0x{stream_id:08X}"
                stats["stream_ids"][sid_hex] = stats["stream_ids"].get(sid_hex, 0) + 1

                # PCC tracken
                pcc_hex = f"0x{pcc:04X}"
                stats["pccs"][pcc_hex] = stats["pccs"].get(pcc_hex, 0) + 1

                # Trailer?
                word0 = header[0]
                has_trailer = (word0 >> 26) & 1
                payload_end = -4 if has_trailer else len(data)
                payload = data[VITA49_HEADER_SIZE:payload_end]

                if not payload:
                    continue

                # Audio dekodieren
                if pcc == PCC_INT16:
                    samples = np.frombuffer(payload, dtype=">i2").astype(np.float32)
                    stats["audio_packets"] += 1
                elif pcc == PCC_FLOAT32:
                    floats = np.frombuffer(payload, dtype=">f4")
                    samples = floats[0::2] * 32767  # Mono, skaliert
                    stats["audio_packets"] += 1
                else:
                    stats["other_packets"] += 1
                    continue

                peak = np.max(np.abs(samples))
                if peak > stats["peak"]:
                    stats["peak"] = peak
                stats["total_samples"] += len(samples)

                if stats["first_audio_at"] is None:
                    stats["first_audio_at"] = time.time() - start
                    print(f"  ERSTES AUDIO nach {stats['first_audio_at']:.1f}s!")
                    print(f"  PCC={pcc_hex}, Stream={sid_hex}, "
                          f"{len(samples)} samples, peak={peak:.0f}")

                # Alle 5s Status
                if stats["audio_packets"] % 200 == 0:
                    elapsed = time.time() - start
                    rate = stats["audio_packets"] / elapsed
                    print(f"  {elapsed:.0f}s: {stats['audio_packets']} Pakete "
                          f"({rate:.0f}/s), Peak={stats['peak']:.0f}")

            except socket.timeout:
                continue
            except (socket.error, OSError) as e:
                print(f"  UDP Fehler: {e}")
                break

        print("-" * 60)
        elapsed = time.time() - start
        print(f"\n[Ergebnis nach {elapsed:.0f}s]")
        print(f"  Pakete total:  {stats['total_packets']}")
        print(f"  Audio-Pakete:  {stats['audio_packets']}")
        print(f"  Andere:        {stats['other_packets']}")
        print(f"  Peak:          {stats['peak']:.0f}")
        print(f"  Samples total: {stats['total_samples']}")
        if stats["total_samples"] > 0:
            secs = stats["total_samples"] / 24000.0  # bei 24kHz
            print(f"  Audio-Dauer:   ~{secs:.1f}s (bei 24kHz)")
        print(f"  Stream-IDs:    {stats['stream_ids']}")
        print(f"  PCC-Typen:     {stats['pccs']}")

        if stats["audio_packets"] == 0:
            print("\n  KEIN AUDIO EMPFANGEN!")
        else:
            print(f"\n  AUDIO LAEUFT! ({stats['audio_packets']} Pakete)")

        return stats["audio_packets"] > 0

    def close(self):
        self.running = False
        for s in [self.sock, self.udp]:
            if s:
                try:
                    s.close()
                except OSError:
                    pass


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    radio = discover()
    if not radio:
        sys.exit(1)

    t = RadioTester(radio["ip"])
    handle = t.connect()
    if not handle:
        sys.exit(1)

    # --- Phase 1: Registrierung ---
    print("\n--- REGISTRIERUNG ---")
    t.send("client gui")
    time.sleep(3)
    t.flush()
    t.send("keepalive enable")
    t.flush()

    # --- Phase 2: Reduced BW (int16 mono 24kHz) ---
    print("\n--- KONFIGURATION ---")
    t.send("client set send_reduced_bw_dax=1")
    t.flush()

    # --- Phase 3: Subscriptions ---
    print("\n--- SUBSCRIPTIONS ---")
    for sub in ["slice", "tx", "audio", "dax", "radio"]:
        t.send(f"sub {sub} all")
    time.sleep(0.5)
    t.flush()

    # --- Phase 4: UDP ---
    print("\n--- UDP SETUP ---")
    t.setup_udp()
    t.send("client udpport 4991")
    time.sleep(0.5)
    t.flush()

    # --- Phase 5: Slice konfigurieren ---
    print("\n--- SLICE KONFIGURATION ---")
    t.send("slice tune 0 14.074")
    time.sleep(1)
    t.flush()
    t.send("slice set 0 mode=DIGU")
    time.sleep(1)
    t.flush()

    # --- Phase 6: DAX ---
    print("\n--- DAX SETUP ---")
    t.send("slice set 0 dax=1")
    t.flush()
    t.send("dax audio set 1 slice=0")
    time.sleep(0.5)
    t.flush()

    # --- Phase 7: RX Stream ---
    print("\n--- RX STREAM ---")
    t.send("stream create type=dax_rx dax_channel=1")
    time.sleep(1)
    responses = t.flush()

    # Stream-ID aus Response extrahieren
    for r in responses:
        if "|0|" in r:
            parts = r.split("|")
            if len(parts) >= 3 and parts[2].strip():
                try:
                    sid = int(parts[2].strip(), 16)
                    print(f"  RX Stream ID: 0x{sid:08X}")
                except ValueError:
                    pass

    # --- Phase 8: Keepalive starten + Audio lauschen ---
    t.running = True
    t.start_keepalive()
    has_audio = t.listen_audio(duration)

    t.close()
    print(f"\nERGEBNIS: {'AUDIO OK' if has_audio else 'KEIN AUDIO'}")


if __name__ == "__main__":
    main()
