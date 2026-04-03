#!/usr/bin/env python3
"""Schritt 2: Als GUI-Client registrieren + Keepalive.

Macht:
1. Discovery + TCP connect (wie Schritt 1)
2. 'client gui' senden — wir uebernehmen die Kontrolle
3. 'keepalive enable' senden
4. Alle 5s 'ping' senden
5. 60 Sekunden lauschen — bleibt die Verbindung stabil?

Ergebnis: Wir wissen ob client gui + keepalive reicht.
"""

import socket
import time
import sys
import threading


def discover(timeout=3.0):
    """FlexRadio finden."""
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
    def __init__(self, ip, port=4992):
        self.ip = ip
        self.port = port
        self.sock = None
        self.seq = 0
        self.running = False
        self.buffer = ""
        self.line_count = 0
        self.start_time = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.ip, self.port))
        self.sock.settimeout(0.5)
        print(f"[TCP] Verbunden mit {self.ip}")

        # Greeting lesen
        greeting = self._read_until_handle()
        print(f"[TCP] Handle: {greeting.get('handle', '?')}")
        return greeting

    def send(self, cmd):
        """Befehl senden mit Sequence-Nummer."""
        self.seq += 1
        line = f"C{self.seq}|{cmd}\n"
        self.sock.sendall(line.encode())
        print(f"  >>> C{self.seq}|{cmd}")
        time.sleep(0.15)

    def flush(self):
        """Alle wartenden Daten lesen und ausgeben."""
        data = ""
        try:
            while True:
                chunk = self.sock.recv(32768).decode("utf-8", errors="replace")
                data += chunk
        except (socket.timeout, OSError):
            pass
        if data:
            for line in data.split("\n"):
                line = line.strip()
                if line:
                    # Responses (R...) ausfuehrlich, Status (S...) gekuerzt
                    if line.startswith("R"):
                        print(f"  <<< {line}")
                    elif line.startswith("S"):
                        print(f"  <<< {line[:100]}...")
                    elif line.startswith("M"):
                        print(f"  <<< {line}")
        return data

    def listen_with_keepalive(self, duration=60):
        """Lauschen + alle 5s ping senden."""
        self.running = True
        self.start_time = time.time()
        self.line_count = 0

        # Ping-Thread
        def ping_loop():
            while self.running:
                time.sleep(5)
                if not self.running:
                    break
                try:
                    self.send("ping")
                except OSError:
                    break

        ping_thread = threading.Thread(target=ping_loop, daemon=True)
        ping_thread.start()

        print(f"\n[Listen] Lausche {duration}s mit Keepalive-Pings...")
        print("-" * 60)

        while time.time() - self.start_time < duration:
            try:
                data = self.sock.recv(4096)
                if not data:
                    elapsed = time.time() - self.start_time
                    print(f"\n[!] Verbindung geschlossen nach {elapsed:.1f}s")
                    self.running = False
                    return False
                text = data.decode("utf-8", errors="replace")
                self.buffer += text
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        elapsed = time.time() - self.start_time
                        self.line_count += 1
                        # Nur wichtige Zeilen voll anzeigen
                        if any(k in line for k in ["R", "client", "slice", "dax",
                                                     "stream", "M", "ping"]):
                            print(f"  {elapsed:6.1f}s | {line[:120]}")
                        elif self.line_count <= 20 or self.line_count % 50 == 0:
                            print(f"  {elapsed:6.1f}s | {line[:100]}...")
            except socket.timeout:
                continue
            except (socket.error, OSError) as e:
                elapsed = time.time() - self.start_time
                print(f"\n[!] Fehler nach {elapsed:.1f}s: {e}")
                self.running = False
                return False

        self.running = False
        print("-" * 60)
        print(f"[OK] {self.line_count} Zeilen in {duration}s — Verbindung STABIL")
        return True

    def close(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def _read_until_handle(self):
        result = {}
        buffer = ""
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                data = self.sock.recv(4096)
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
                if "handle" in result:
                    break
            except socket.timeout:
                continue
        return result


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    radio = discover()
    if not radio:
        sys.exit(1)

    t = RadioTester(radio["ip"])
    greeting = t.connect()
    if not greeting.get("handle"):
        print("Kein Handle — Abbruch")
        sys.exit(1)

    # Schritt 2: Als GUI-Client registrieren
    print("\n--- REGISTRIERUNG ---")
    t.send("client gui")
    time.sleep(3)  # Persistence laden lassen
    resp = t.flush()

    # Keepalive aktivieren
    t.send("keepalive enable")
    time.sleep(0.5)
    t.flush()

    # Lauschen mit Keepalive
    stable = t.listen_with_keepalive(duration)

    t.close()
    print(f"\nERGEBNIS: {'STABIL' if stable else 'VERBINDUNG VERLOREN'}")


if __name__ == "__main__":
    main()
