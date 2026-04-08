#!/usr/bin/env python3
"""Schritt 4: SmartSDR-M disconnecten, dann frisch verbinden + Audio.

Das Problem: SmartSDR-M (der lokale Display-Client) besitzt Slice 0.
Unser DAX-Stream bekommt deshalb nur Stille (Peak=0).

Loesung: 2-Schritt-Verbindung:
  Session 1: SmartSDR-M Handle finden + disconnecten
  Session 2: Frisch verbinden → jetzt gehoert der Slice uns → Audio!
"""

import socket
import struct
import time
import sys
import threading
import numpy as np


VITA49_HEADER_SIZE = 28
PCC_INT16 = 0x0123


def discover(timeout=3.0):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", 4992))
        data, addr = sock.recvfrom(1024)
        sock.close()
        print(f"[Discovery] Radio @ {addr[0]}")
        return addr[0]
    except (socket.timeout, OSError) as e:
        print(f"[Discovery] Fehler: {e}")
        return None


class FlexConnection:
    def __init__(self, ip):
        self.ip = ip
        self.sock = None
        self.seq = 0
        self.handle = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.ip, 4992))
        self.sock.settimeout(0.5)
        buf = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                buf += self.sock.recv(4096).decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.startswith("H"):
                        self.handle = line[1:].strip()
            except socket.timeout:
                if self.handle:
                    break
        print(f"[TCP] Verbunden, Handle: {self.handle}")
        return self.handle

    def send(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        print(f"  >>> {cmd}")
        time.sleep(0.15)

    def send_quiet(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        time.sleep(0.15)

    def read_all(self, timeout=1.0):
        """Alles lesen was ansteht."""
        data = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data += self.sock.recv(32768).decode("utf-8", errors="replace")
            except (socket.timeout, OSError):
                break
        return data

    def read_and_print(self, timeout=1.0):
        data = self.read_all(timeout)
        lines = []
        for line in data.split("\n"):
            line = line.strip()
            if line:
                print(f"  <<< {line[:200]}")
                lines.append(line)
        return lines

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


def phase1_disconnect_smartsdr(ip):
    """Session 1: SmartSDR-M finden und disconnecten."""
    print("\n" + "=" * 60)
    print("PHASE 1: SmartSDR-M disconnecten")
    print("=" * 60)

    c = FlexConnection(ip)
    c.connect()

    # Als GUI registrieren
    c.send("client gui")
    time.sleep(3)
    c.read_and_print()

    # Client-Liste abonnieren
    c.send("sub client all")
    time.sleep(1)
    lines = c.read_and_print()

    # SmartSDR-M Handle finden
    smartsdr_handle = None
    our_handle = c.handle

    # Nochmal alles lesen was ansteht
    all_data = c.read_all(1.0)
    for line in all_data.split("\n"):
        line = line.strip()
        if line:
            lines.append(line)

    # In allen empfangenen Zeilen nach SmartSDR-M suchen
    for line in lines:
        if "SmartSDR" in line and "program=" in line:
            # Handle aus "client 0xXXXXXXXX" extrahieren
            parts = line.split()
            for p in parts:
                if p.startswith("0x") and p != f"0x{our_handle}":
                    # Pruefen ob es nicht unser eigener Handle ist
                    candidate = p.rstrip(",")
                    if candidate.lower() != f"0x{our_handle}".lower():
                        smartsdr_handle = candidate
                        print(f"\n  SmartSDR-M gefunden: {smartsdr_handle}")
                        break

    if not smartsdr_handle:
        # Fallback: direkt nach client-Statuszeilen suchen
        print("  SmartSDR-M nicht in Status gefunden, suche in allen Zeilen...")
        for line in lines:
            if "client" in line.lower() and "0x" in line:
                print(f"  Zeile: {line[:150]}")

    if smartsdr_handle:
        print(f"\n  Disconnecte SmartSDR-M ({smartsdr_handle})...")
        c.send(f"client disconnect {smartsdr_handle}")
        time.sleep(1)
        c.read_and_print()
        print("  SmartSDR-M disconnected!")
    else:
        print("\n  WARNUNG: SmartSDR-M Handle nicht gefunden!")
        print("  Versuche trotzdem Phase 2...")

    c.close()
    print("\n  Session 1 geschlossen.")
    time.sleep(2)  # Radio braucht kurz


def phase2_connect_and_audio(ip, duration=30):
    """Session 2: Frisch verbinden, jetzt gehoert alles uns."""
    print("\n" + "=" * 60)
    print("PHASE 2: Frische Verbindung + Audio")
    print("=" * 60)

    c = FlexConnection(ip)
    c.connect()

    # 1. Registrierung
    print("\n--- Registrierung ---")
    c.send("client gui")
    time.sleep(5)  # Persistence abwarten!
    c.read_and_print()
    c.send("keepalive enable")
    c.read_and_print()
    c.send("client set send_reduced_bw_dax=1")
    c.read_and_print()

    # 2. Subscriptions
    print("\n--- Subscriptions ---")
    for sub in ["slice", "tx", "audio", "dax", "radio"]:
        c.send(f"sub {sub} all")
    time.sleep(1)
    c.read_and_print()

    # 3. Slice-Status pruefen
    print("\n--- Slice Status ---")
    c.send("slice list")
    time.sleep(0.5)
    lines = c.read_and_print()

    # Pruefen ob Slice uns gehoert
    for line in lines:
        if "slice 0" in line and "client_handle" in line:
            if c.handle and c.handle.lower() in line.lower():
                print(f"  >>> SLICE GEHOERT UNS! (Handle {c.handle})")
            else:
                print(f"  >>> WARNUNG: Slice gehoert jemand anderem!")

    # 4. UDP
    print("\n--- UDP ---")
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    udp.bind(("", 4991))
    udp.settimeout(0.1)
    udp.sendto(b"\x00", (ip, 4992))
    c.send("client udpport 4991")
    time.sleep(0.5)
    c.read_and_print()

    # 5. Slice konfigurieren
    print("\n--- Slice konfigurieren ---")
    c.send("slice tune 0 14.074")
    time.sleep(1)
    c.read_and_print()
    c.send("slice set 0 mode=DIGU")
    time.sleep(1)
    c.read_and_print()

    # 6. DAX
    print("\n--- DAX ---")
    c.send("slice set 0 dax=1")
    c.read_and_print()
    c.send("dax audio set 1 slice=0")
    time.sleep(0.5)
    c.read_and_print()

    # 7. RX Stream
    print("\n--- RX Stream ---")
    c.send("stream create type=dax_rx dax_channel=1")
    time.sleep(1)
    lines = c.read_and_print()

    # Stream-ID
    stream_id = None
    for line in lines:
        if "|0|" in line and line.startswith("R"):
            parts = line.split("|")
            if len(parts) >= 3 and parts[2].strip():
                try:
                    stream_id = int(parts[2].strip(), 16)
                    print(f"  RX Stream ID: 0x{stream_id:08X}")
                except ValueError:
                    pass

    # 8. Keepalive starten
    running = True

    def keepalive():
        while running:
            time.sleep(5)
            if not running:
                break
            try:
                c.send_quiet("ping")
            except OSError:
                break

    threading.Thread(target=keepalive, daemon=True).start()

    # 9. Audio lauschen
    print(f"\n--- Audio Test ({duration}s) ---")
    start = time.time()
    packets = 0
    peak = 0.0
    nonzero = 0
    first_signal = None

    while time.time() - start < duration:
        try:
            data, _ = udp.recvfrom(4096)
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
            p = float(np.max(np.abs(samples)))
            if p > peak:
                peak = p
            if p > 0:
                nonzero += 1
                if first_signal is None:
                    first_signal = time.time() - start
                    print(f"  ERSTES SIGNAL nach {first_signal:.1f}s! Peak={p:.0f}")

            # Alle 5s Status
            elapsed = time.time() - start
            if packets > 0 and packets % 1000 == 0:
                print(f"  {elapsed:.0f}s: {packets} Pakete, Peak={peak:.0f}, "
                      f"Non-Zero={nonzero}")

        except socket.timeout:
            continue

    running = False
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"ERGEBNIS nach {elapsed:.0f}s:")
    print(f"  Pakete:       {packets}")
    print(f"  Peak:         {peak:.0f}")
    print(f"  Non-Zero:     {nonzero} ({100*nonzero/max(packets,1):.0f}%)")
    if peak > 0:
        print(f"\n  AUDIO LAEUFT MIT SIGNAL! Peak={peak:.0f}")
        if peak > 10000:
            print(f"  (Normalisierung auf ~3000 noetig fuer Decoder)")
    else:
        print(f"\n  STILLE (Peak=0) — kein Signal auf dem Slice")
    print("=" * 60)

    # Aufraeumen
    try:
        udp.close()
    except OSError:
        pass
    c.close()

    return peak > 0


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    ip = discover()
    if not ip:
        sys.exit(1)

    phase1_disconnect_smartsdr(ip)
    has_audio = phase2_connect_and_audio(ip, duration)

    if has_audio:
        print("\nSCHRITT 4 BESTANDEN: Audio kommt durch!")
        print("Naechster Schritt: FT8 dekodieren")
    else:
        print("\nSCHRITT 4 GESCHEITERT: Immer noch Stille")
        print("Moegliche Ursachen:")
        print("  - Antenne nicht angeschlossen?")
        print("  - Band tot (14.074 MHz, 20m)?")
        print("  - SmartSDR-M kam sofort zurueck?")


if __name__ == "__main__":
    main()
