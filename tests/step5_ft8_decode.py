#!/usr/bin/env python3
"""Schritt 5: Live FT8 dekodieren — Audio empfangen + PyFT8 Decode.

Benutzt PyFT8 Receiver API direkt (wie der App-Decoder).
"""

import socket
import struct
import time
import sys
import threading
import numpy as np

sys.path.insert(0, "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8")

from PyFT8.receiver import (
    AudioIn, Candidate,
    SAMP_RATE, HPS, SYM_RATE, BPT,
    HOPS_PER_CYCLE, HOPS_PER_GRID,
    H0_RANGE, BASE_FREQ_IDXS, COSTAS,
)
from PyFT8.time_utils import global_time_utils

print(f"[PyFT8] OK — SAMP_RATE={SAMP_RATE}, HPS={HPS}")

VITA49_HEADER_SIZE = 28
PCC_INT16 = 0x0123
MAX_FREQ = 3000


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
        print(f"[TCP] Handle: {self.handle}")

    def send(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        time.sleep(0.15)

    def send_quiet(self, cmd):
        self.seq += 1
        self.sock.sendall(f"C{self.seq}|{cmd}\n".encode())
        time.sleep(0.15)

    def drain(self, timeout=1.0):
        data = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data += self.sock.recv(32768).decode("utf-8", errors="replace")
            except (socket.timeout, OSError):
                break
        return data

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


def disconnect_smartsdr(ip):
    """SmartSDR-M rauswerfen."""
    print("\n--- SmartSDR-M disconnecten ---")
    c = FlexConnection(ip)
    c.connect()
    c.send("client gui")
    time.sleep(3)
    c.send("sub client all")
    time.sleep(1)
    data = c.drain(2.0)

    for line in data.split("\n"):
        if "SmartSDR" in line and "0x" in line:
            for part in line.split():
                if part.startswith("0x") and part.lower() != f"0x{c.handle}".lower():
                    handle = part.rstrip(",")
                    print(f"  SmartSDR-M: {handle} → disconnect")
                    c.send(f"client disconnect {handle}")
                    time.sleep(1)
                    c.drain(1.0)
                    break

    c.close()
    time.sleep(2)


def decode_audio(audio_12k_int16):
    """Einen Block 12kHz int16 Audio durch PyFT8 jagen."""
    audio_in = AudioIn(MAX_FREQ)
    samples_per_hop = int(SAMP_RATE / (SYM_RATE * HPS))
    audio_float = audio_12k_int16.astype(np.float32)
    n_hops = min(len(audio_float) // samples_per_hop, audio_in.hops_per_grid)

    # Audio in AudioIn fuettern
    for i in range(n_hops):
        chunk = audio_float[i * samples_per_hop:(i + 1) * samples_per_hop]
        audio_in._callback(chunk.astype(np.int16).tobytes(), None, None, None)

    # Kandidaten suchen (Costas-Sync)
    df = MAX_FREQ / (audio_in.nFreqs - 1)
    f0_range = range(
        int(200 / df),
        min(audio_in.nFreqs - 8 * BPT, int(MAX_FREQ / df))
    )

    cyclestart = global_time_utils.cyclestart(time.time())
    costas_nhops = 7 * HPS
    cands = []

    for f0_idx in f0_range:
        freq_idxs = f0_idx + BASE_FREQ_IDXS
        if max(freq_idxs) >= audio_in.nFreqs:
            continue

        best_score = -999
        best_h0 = 0
        for h0 in range(H0_RANGE[0], min(H0_RANGE[1], n_hops - costas_nhops)):
            score = 0
            for ci, cv in enumerate(COSTAS):
                hop = h0 + ci * HPS
                if hop < audio_in.dBgrid_main.shape[0]:
                    fidx = freq_idxs[cv]
                    if fidx < audio_in.nFreqs:
                        score += audio_in.dBgrid_main[hop, fidx]
            if score > best_score:
                best_score = score
                best_h0 = h0

        c = Candidate(cyclestart=cyclestart, f0_idx=f0_idx)
        c.h0_idx = best_h0
        c.sync_score = best_score
        c.fHz = int(f0_idx * df)
        c.dt = best_h0 / (HPS * SYM_RATE) - 0.7
        cands.append(c)

    cands.sort(key=lambda c: c.sync_score, reverse=True)

    # Dekodieren
    results = []
    seen = set()
    for c in cands[:100]:
        try:
            c.demap(audio_in.dBgrid_main)
            c.decode()
            if c.msg and c.msg not in seen:
                seen.add(c.msg)
                results.append({
                    "msg": c.msg,
                    "snr": c.snr,
                    "freq": c.fHz,
                    "dt": c.dt,
                })
        except Exception:
            continue

    return results


def main():
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    ip = discover()
    if not ip:
        sys.exit(1)

    disconnect_smartsdr(ip)

    # Frisch verbinden
    print("\n--- Verbinde + Setup ---")
    c = FlexConnection(ip)
    c.connect()
    c.send("client gui")
    time.sleep(5)
    c.drain(2.0)
    c.send("keepalive enable")
    c.send("client set send_reduced_bw_dax=1")
    for sub in ["slice", "tx", "audio", "dax", "radio"]:
        c.send(f"sub {sub} all")
    time.sleep(1)
    c.drain(1.0)

    # UDP
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    udp.bind(("", 4991))
    udp.settimeout(0.1)
    udp.sendto(b"\x00", (ip, 4992))
    c.send("client udpport 4991")
    time.sleep(0.5)
    c.drain(0.5)

    # Slice
    c.send("slice tune 0 14.074")
    time.sleep(1)
    c.send("slice set 0 mode=DIGU")
    time.sleep(1)
    c.send("slice set 0 dax=1")
    c.send("dax audio set 1 slice=0")
    time.sleep(0.5)
    c.drain(0.5)

    # RX Stream
    c.send("stream create type=dax_rx dax_channel=1")
    time.sleep(1)
    c.drain(0.5)

    # Keepalive
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

    # Auf FT8-Zyklusstart warten
    print(f"\n--- Warte auf FT8-Zyklusstart ---")
    utc_sec = time.time() % 15
    wait = 15 - utc_sec
    if wait < 2:
        wait += 15
    print(f"  Naechster Zyklus in {wait:.1f}s")
    time.sleep(wait)

    total_decoded = 0

    for cycle_num in range(cycles):
        print(f"\n{'='*60}")
        print(f"ZYKLUS {cycle_num+1}/{cycles} — Sammle 15s Audio...")

        # 15s Audio sammeln
        audio_chunks = []
        start = time.time()
        while time.time() - start < 15.0:
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
                    audio_chunks.append(samples)
                elif pcc == 0x03E3:
                    floats = np.frombuffer(payload, dtype=">f4")
                    samples = floats[0::2] * 32767
                    audio_chunks.append(samples)
            except socket.timeout:
                continue

        if not audio_chunks:
            print("  KEIN AUDIO!")
            continue

        audio = np.concatenate(audio_chunks)
        peak = float(np.max(np.abs(audio)))
        print(f"  {len(audio)} Samples, Peak={peak:.0f}")

        if peak < 10:
            print("  STILLE")
            continue

        # Normalisieren
        audio_norm = (audio * 3000.0 / peak).astype(np.int16)

        # 24kHz → 12kHz
        audio_12k = audio_norm[::2]
        expected = 15 * SAMP_RATE  # 180000
        if len(audio_12k) < expected:
            audio_12k = np.pad(audio_12k, (0, expected - len(audio_12k)))
        else:
            audio_12k = audio_12k[:expected]

        print(f"  {len(audio_12k)} Samples @ 12kHz → Dekodiere...")

        # Dekodieren
        t0 = time.time()
        results = decode_audio(audio_12k)
        dt = time.time() - t0

        if results:
            print(f"\n  {len(results)} STATIONEN in {dt:.1f}s:")
            print(f"  {'SNR':>5} {'DT':>6} {'Freq':>6}  Message")
            print(f"  {'-'*5} {'-'*6} {'-'*6}  {'-'*35}")
            for r in sorted(results, key=lambda x: -x['snr']):
                print(f"  {r['snr']:>5} {r['dt']:>6.1f} {r['freq']:>6}  {r['msg']}")
            total_decoded += len(results)
        else:
            print(f"  Keine Stationen ({dt:.1f}s)")

    running = False
    udp.close()
    c.close()

    print(f"\n{'='*60}")
    print(f"GESAMT: {total_decoded} Stationen in {cycles} Zyklen")
    if total_decoded > 0:
        print("SCHRITT 5 BESTANDEN!")
    else:
        print("Keine Stationen — Band evtl. tot um diese Uhrzeit?")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
