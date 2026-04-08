#!/usr/bin/env python3
"""TX Brute-Force Test — probiert systematisch alle Kombinationen.

Sendet CQ DA1MHH JO31 mit verschiedenen:
- VITA-49 Header-Formaten
- Byte-Orders (big/little endian)
- Audio-Levels
- Sample-Formate (float32 vs int16)
- Audio-Frequenzen

EINE Verbindung, sequentiell, 15s pro Versuch.
Mike: Am IC-7300/SDR-Control beobachten wann FT8 dekodiert wird!
"""

import socket
import struct
import time
import re
import sys
import threading
import numpy as np

sys.path.insert(0, "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8")
from PyFT8.transmitter import pack_message, AudioOut

IP = "192.168.1.68"
FLEX_OUI = 0x001C2D
FLEX_ICC = 0x534C
PCC_FLOAT32 = 0x03E3
PCC_INT16 = 0x0123


def connect_and_setup():
    """Einmal verbinden, SmartSDR-M disconnecten, Slice erstellen."""
    # Phase 1: SmartSDR-M disconnect
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.settimeout(5); s1.connect((IP, 4992)); s1.settimeout(0.5)
    time.sleep(1)
    try:
        while True: s1.recv(4096)
    except: pass
    s1.sendall(b"C1|client gui\n"); time.sleep(3)
    s1.sendall(b"C2|sub client all\n"); time.sleep(1)
    data = ""
    try:
        while True: data += s1.recv(32768).decode("utf-8", errors="replace")
    except: pass
    for line in data.split("\n"):
        m = re.search(r"client (0x[0-9A-Fa-f]+).*local_ptt=1", line)
        if m:
            s1.sendall(f"C3|client disconnect {m.group(1)}\n".encode())
            print(f"SmartSDR-M disconnected: {m.group(1)}")
            time.sleep(1)
    s1.close(); time.sleep(2)

    # Phase 2: Frisch verbinden
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5); s.connect((IP, 4992)); s.settimeout(0.5)
    handle = None; buf = ""
    dl = time.time() + 3
    while time.time() < dl:
        try:
            buf += s.recv(4096).decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if line.startswith("H"): handle = line[1:].strip()
        except socket.timeout:
            if handle: break

    seq = [0]
    def send(cmd):
        seq[0] += 1
        s.sendall(f"C{seq[0]}|{cmd}\n".encode())
        time.sleep(0.2)
    def flush():
        data = ""
        try:
            while True: data += s.recv(32768).decode("utf-8", errors="replace")
        except: pass
        return data

    send("client gui"); time.sleep(5); flush()
    send("client set send_reduced_bw_dax=1")
    send("keepalive enable")
    for sub in ["slice", "tx", "audio", "dax", "radio"]:
        send(f"sub {sub} all")
    time.sleep(1); flush()

    send("display panafall create x=500 y=300"); time.sleep(2); flush()

    # UDP
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    udp.bind(("", 4991)); udp.settimeout(0.1)
    udp.sendto(b"\x00", (IP, 4992))
    send("client udpport 4991"); time.sleep(0.5); flush()

    # Slice
    send("slice tune 0 14.074"); time.sleep(1); flush()
    send("slice set 0 mode=DIGU"); time.sleep(1); flush()
    send("slice set 0 tx=1")
    send("interlock tx1_enabled=1")
    send("transmit set rfpower=20")
    send("slice set 0 dax=1")
    send("dax audio set 1 slice=0")
    send("transmit set dax=1")
    send("mic input pc")
    time.sleep(0.5); flush()

    # TX Streams erstellen (alle Typen)
    tx_streams = {}
    for stype in ["dax_tx1", "dax_tx", "remote_audio_tx"]:
        send(f"stream create type={stype}")
        time.sleep(1)
        resp = flush()
        for line in resp.split("\n"):
            if "|0|" in line and line.startswith("R"):
                parts = line.split("|")
                if len(parts) >= 3 and parts[2].strip():
                    try:
                        sid = int(parts[2].strip(), 16)
                        tx_streams[stype] = sid
                        print(f"  TX Stream {stype}: 0x{sid:08X}")
                    except: pass

    # Keepalive
    running = [True]
    def ka():
        while running[0]:
            time.sleep(5)
            try: seq[0] += 1; s.sendall(f"C{seq[0]}|ping\n".encode())
            except: break
    threading.Thread(target=ka, daemon=True).start()

    return s, udp, seq, send, flush, tx_streams, running


def send_ft8(udp, tx_stream_id, audio_48k, header_format, byte_order,
             level, pcc, port, desc):
    """Einen CQ-Ruf mit bestimmten Parametern senden."""
    # Audio vorbereiten
    audio = audio_48k.astype(np.float32)
    audio = audio / 32768.0
    audio = audio * level

    if pcc == PCC_FLOAT32:
        # Stereo float32
        stereo = np.empty(len(audio) * 2, dtype=np.float32)
        stereo[0::2] = audio
        stereo[1::2] = audio
        samples_per_pkt = 256
        dtype_str = f"{byte_order}f4"
    else:
        # Mono int16 (reduced BW)
        stereo = (audio * 32767).astype(np.int16)
        samples_per_pkt = 128
        dtype_str = f"{byte_order}i2"

    pkt_count = 0
    t_start = time.time()
    pkt_interval = 128 / 48000.0 if pcc == PCC_FLOAT32 else 128 / 24000.0

    for offset in range(0, len(stereo), samples_per_pkt):
        chunk = stereo[offset:offset + samples_per_pkt]
        if len(chunk) < samples_per_pkt:
            if pcc == PCC_FLOAT32:
                chunk = np.pad(chunk.astype(np.float32), (0, samples_per_pkt - len(chunk)))
            else:
                chunk = np.pad(chunk.astype(np.int16), (0, samples_per_pkt - len(chunk)))

        total_words = 7 + (len(chunk) * (4 if pcc == PCC_FLOAT32 else 2)) // 4
        w0 = header_format | ((pkt_count & 0xF) << 16) | (total_words & 0xFFFF)

        header = struct.pack(">7I", w0, tx_stream_id, FLEX_OUI,
                             (FLEX_ICC << 16) | pcc, 0, 0, 0)
        payload = chunk.astype(dtype_str).tobytes()

        try:
            udp.sendto(header + payload, (IP, port))
        except OSError:
            break

        pkt_count += 1
        expected = t_start + pkt_count * pkt_interval
        delta = expected - time.time()
        if delta > 0:
            time.sleep(delta)

    return pkt_count


def main():
    print("=" * 70)
    print("TX BRUTE-FORCE TEST — CQ DA1MHH JO31")
    print("Beobachte am IC-7300/SDR-Control wann FT8 dekodiert wird!")
    print("Jeder Versuch dauert ~15 Sekunden")
    print("=" * 70)

    # FT8 Audio erzeugen bei verschiedenen Frequenzen
    symbols = pack_message("CQ", "DA1MHH", "JO31")
    ao = AudioOut()
    audio_48k_1000 = ao.create_ft8_wave(symbols, fs=48000, f_base=1000.0)
    audio_48k_1500 = ao.create_ft8_wave(symbols, fs=48000, f_base=1500.0)

    # Verbinden
    print("\nVerbinde...")
    s, udp, seq, send, flush, tx_streams, running = connect_and_setup()
    print(f"Verbunden! TX Streams: {tx_streams}")

    # Kombinationen definieren
    tests = []
    test_num = [0]

    def add(stream, header, order, level, pcc, port, audio, desc):
        test_num[0] += 1
        if stream in tx_streams:
            tests.append({
                "num": test_num[0],
                "stream": stream,
                "sid": tx_streams[stream],
                "header": header,
                "order": order,
                "level": level,
                "pcc": pcc,
                "port": port,
                "audio": audio,
                "desc": desc,
            })

    # === TESTS DEFINIEREN ===

    # Gruppe 1: dax_tx1 mit verschiedenen Headern + Byte-Orders (bekanntester Stream-Typ)
    for hdr_name, hdr in [("AetherSDR", 0x18900000), ("nDAX", 0x18D00000), ("Plain", 0x18000000)]:
        for order, oname in [(">", "BE"), ("<", "LE")]:
            for lvl in [0.2, 0.4, 0.8]:
                add("dax_tx1", hdr, order, lvl, PCC_FLOAT32, 4991, audio_48k_1000,
                    f"dax_tx1 {hdr_name} {oname} lvl={lvl} f32 1000Hz")

    # Gruppe 2: dax_tx1 mit int16 Format (PCC 0x0123)
    for hdr_name, hdr in [("AetherSDR", 0x18900000), ("nDAX", 0x18D00000)]:
        for order, oname in [(">", "BE"), ("<", "LE")]:
            add("dax_tx1", hdr, order, 0.4, PCC_INT16, 4991, audio_48k_1000,
                f"dax_tx1 {hdr_name} {oname} INT16 1000Hz")

    # Gruppe 3: dax_tx (ohne "1")
    if "dax_tx" in tx_streams:
        for hdr_name, hdr in [("AetherSDR", 0x18900000), ("nDAX", 0x18D00000)]:
            for order, oname in [(">", "BE"), ("<", "LE")]:
                add("dax_tx", hdr, order, 0.4, PCC_FLOAT32, 4991, audio_48k_1000,
                    f"dax_tx {hdr_name} {oname} f32 1000Hz")

    # Gruppe 4: remote_audio_tx
    if "remote_audio_tx" in tx_streams:
        for hdr_name, hdr in [("AetherSDR", 0x18900000), ("nDAX", 0x18D00000)]:
            for order, oname in [(">", "BE"), ("<", "LE")]:
                add("remote_audio_tx", hdr, order, 0.4, PCC_FLOAT32, 4991, audio_48k_1000,
                    f"remote_audio_tx {hdr_name} {oname} f32 1000Hz")

    # Gruppe 5: Andere Frequenz (1500 Hz statt 1000 Hz)
    for hdr_name, hdr in [("AetherSDR", 0x18900000), ("nDAX", 0x18D00000)]:
        add("dax_tx1", hdr, ">", 0.4, PCC_FLOAT32, 4991, audio_48k_1500,
            f"dax_tx1 {hdr_name} BE f32 1500Hz")

    # Gruppe 6: Verschiedene Ports
    for port in [4992, 4993]:
        add("dax_tx1", 0x18900000, ">", 0.4, PCC_FLOAT32, port, audio_48k_1000,
            f"dax_tx1 AetherSDR BE f32 PORT={port}")

    print(f"\n{len(tests)} Kombinationen zu testen")
    print(f"Geschaetzte Dauer: {len(tests) * 16 // 60} Minuten")
    print()

    # Tests durchfuehren
    for t in tests:
        # Auf Zyklusstart warten
        wait = 15.0 - (time.time() % 15.0)
        if wait < 2:
            wait += 15
        time.sleep(wait)

        # PTT an
        seq[0] += 1; s.sendall(f"C{seq[0]}|xmit 1\n".encode())
        time.sleep(0.05)

        # Audio senden
        pkts = send_ft8(udp, t["sid"], t["audio"], t["header"], t["order"],
                        t["level"], t["pcc"], t["port"], t["desc"])

        time.sleep(0.2)

        # PTT aus
        seq[0] += 1; s.sendall(f"C{seq[0]}|xmit 0\n".encode())

        print(f"  #{t['num']:>2d}/{len(tests)} | {t['desc']:<45s} | {pkts} pkts")

    print()
    print("=" * 70)
    print("ALLE TESTS FERTIG!")
    print("Check PSKReporter fuer DA1MHH und sag mir welche Nummer(n) dekodiert wurden!")
    print("=" * 70)

    running[0] = False
    udp.close()
    s.close()


if __name__ == "__main__":
    main()
