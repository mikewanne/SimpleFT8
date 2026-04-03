#!/usr/bin/env python3
"""Schritt 3b: Slice-Status pruefen + Panadapter erstellen.

Peak=0 heisst: Stream kommt, aber Stille.
Vermutung: Ohne Panadapter kein Audio.

Macht:
1. Verbinden + client gui
2. Slice-Status abfragen (slice list / info)
3. Panadapter erstellen (display panafall create)
4. DAX Stream starten
5. Schauen ob jetzt Audio kommt
"""

import socket
import struct
import time
import sys
import threading
import numpy as np


VITA49_HEADER_SIZE = 28
PCC_INT16 = 0x0123


def discover():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(3.0)
        sock.bind(("", 4992))
        data, addr = sock.recvfrom(1024)
        sock.close()
        print(f"[Discovery] Radio @ {addr[0]}")
        return addr[0]
    except (socket.timeout, OSError) as e:
        print(f"[Discovery] Fehler: {e}")
        return None


class Radio:
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
        buf = ""
        handle = None
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

    def send_quiet(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        time.sleep(0.15)

    def flush_all(self):
        """Alles lesen und KOMPLETT ausgeben (fuer Diagnostik)."""
        data = ""
        try:
            while True:
                data += self.sock.recv(32768).decode("utf-8", errors="replace")
        except (socket.timeout, OSError):
            pass
        if data:
            for line in data.strip().split("\n"):
                line = line.strip()
                if line:
                    print(f"  <<< {line[:150]}")
        return data

    def flush_responses(self):
        """Nur Responses zurueckgeben."""
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
                responses.append(line)
                print(f"  <<< {line}")
        return responses

    def setup_udp(self):
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
        self.udp.bind(("", 4991))
        self.udp.settimeout(0.1)
        self.udp.sendto(b"\x00", (self.ip, 4992))
        print("[UDP] Bereit")

    def start_keepalive(self):
        def loop():
            while self.running:
                time.sleep(5)
                if not self.running:
                    break
                try:
                    self.send_quiet("ping")
                except OSError:
                    break
        threading.Thread(target=loop, daemon=True).start()

    def listen_audio(self, duration=15):
        """Audio lauschen, Peak pruefen."""
        start = time.time()
        packets = 0
        peak = 0.0
        nonzero_packets = 0

        while time.time() - start < duration:
            try:
                data, _ = self.udp.recvfrom(4096)
                if len(data) < VITA49_HEADER_SIZE:
                    continue
                header = struct.unpack(">7I", data[:VITA49_HEADER_SIZE])
                pcc = header[3] & 0xFFFF
                has_trailer = (header[0] >> 26) & 1
                payload = data[VITA49_HEADER_SIZE:(-4 if has_trailer else len(data))]
                if not payload:
                    continue

                if pcc == PCC_INT16:
                    samples = np.frombuffer(payload, dtype=">i2").astype(np.float32)
                elif pcc == 0x03E3:
                    floats = np.frombuffer(payload, dtype=">f4")
                    samples = floats[0::2] * 32767
                else:
                    continue

                packets += 1
                p = np.max(np.abs(samples))
                if p > peak:
                    peak = p
                if p > 0:
                    nonzero_packets += 1

            except socket.timeout:
                continue

        elapsed = time.time() - start
        print(f"  {packets} Pakete in {elapsed:.0f}s, "
              f"Peak={peak:.0f}, Non-Zero={nonzero_packets}")
        return peak > 0

    def close(self):
        self.running = False
        for s in [self.sock, self.udp]:
            if s:
                try:
                    s.close()
                except OSError:
                    pass


def main():
    ip = discover()
    if not ip:
        sys.exit(1)

    r = Radio(ip)
    r.connect()

    # 1. Client GUI
    print("\n=== REGISTRIERUNG ===")
    r.send("client gui")
    time.sleep(3)
    r.flush_responses()
    r.send("keepalive enable")
    r.flush_responses()
    r.send("client set send_reduced_bw_dax=1")
    r.flush_responses()

    # 2. Subscriptions
    print("\n=== SUBSCRIPTIONS ===")
    for sub in ["slice", "tx", "audio", "dax", "radio", "client"]:
        r.send(f"sub {sub} all")
    time.sleep(1)

    # 3. Slice-Status abfragen
    print("\n=== SLICE STATUS ===")
    r.send("slice list")
    time.sleep(0.5)
    r.flush_all()

    # 4. UDP
    print("\n=== UDP ===")
    r.setup_udp()
    r.send("client udpport 4991")
    time.sleep(0.5)
    r.flush_responses()

    # 5. Panadapter erstellen!
    print("\n=== PANADAPTER ERSTELLEN ===")
    r.send("display panafall create x=0 y=0")
    time.sleep(2)
    r.flush_all()

    # 6. Slice nochmal checken
    print("\n=== SLICE STATUS NACH PANAFALL ===")
    r.send("slice list")
    time.sleep(0.5)
    r.flush_all()

    # 7. Slice konfigurieren
    print("\n=== SLICE KONFIGURATION ===")
    r.send("slice tune 0 14.074")
    time.sleep(0.5)
    r.flush_responses()
    r.send("slice set 0 mode=DIGU")
    time.sleep(0.5)
    r.flush_responses()

    # 8. DAX
    print("\n=== DAX SETUP ===")
    r.send("slice set 0 dax=1")
    r.flush_responses()
    r.send("dax audio set 1 slice=0")
    time.sleep(0.5)
    r.flush_responses()

    # 9. RX Stream
    print("\n=== RX STREAM ===")
    r.send("stream create type=dax_rx dax_channel=1")
    time.sleep(1)
    r.flush_responses()

    # 10. Audio testen
    print("\n=== AUDIO TEST (15s) ===")
    r.running = True
    r.start_keepalive()
    has_audio = r.listen_audio(15)

    r.close()
    print(f"\nERGEBNIS: {'AUDIO MIT SIGNAL' if has_audio else 'STILLE (Peak=0)'}")


if __name__ == "__main__":
    main()
