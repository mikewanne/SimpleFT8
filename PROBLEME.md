# SimpleFT8 — Bekannte Probleme und Loesungen

## PROBLEM: Python Crash (SIGSEGV Thread 0) bei ft8lib-Decode (GELOEST 08.04.2026)

**Symptom:** App stuerzt sofort beim ersten echten Decode-Zyklus ab. macOS Crash-Report:
`Thread 0 Crashed: ... SIGSEGV ... ftx_message_decode+0x38` (ARM-64, Python 3.12)

**Ursache:** `ftx_message_decode()` in ft8_lib schreibt IMMER in `offsets->types[]` und
`offsets->offsets[]` — das 4. Argument darf NICHT NULL sein. Unser erster `libft8simple.c`
hatte `ftx_message_decode(&msg, &s_hash_if, text, NULL)` → SEGFAULT.

**Loesung:** Stack-Variable deklarieren und Adresse uebergeben:
```c
ftx_message_offsets_t offsets;
ftx_message_rc_t rc = ftx_message_decode(&msg, &s_hash_if, text, &offsets);
```

**Datei:** `ft8_lib/libft8simple.c` Zeile ~179

---

## PROBLEM: ft8lib Decode liefert 0 Ergebnisse (2 Bugs, GELOEST 08.04.2026)

**Symptom:** `lib.decode(audio)` gibt leere Liste zurueck, obwohl echte FT8-Signale im Audio sind.

**Bug 1 — monitor_process() falsche Block-Groesse:**
`monitor_process()` erwartet `block_size=1920` Samples (1 FT8-Symbol @ 12kHz).
Intern verarbeitet es `time_osr=2` Sub-Bloecke selbst. Wenn man `subblock_size=960`
uebergibt, zerschneidet man die Symbole → Costas-Sync findet nichts.

**Bug 2 — Naiver Sinus-Encoder (kein GFSK):**
Einfaches `sinf(2π*f*t)` erzeugt Phasen-Sprunge zwischen Symbolen.
ft8_lib-Decoder braucht phasenkontinuierliche GFSK-Synthese fuer Costas-Korrelation.

**Loesung:**
```c
// Bug 1: block_size verwenden, NICHT subblock_size
int block_size = mon.block_size;   // 1920 @ 12kHz
while (n_fed + block_size <= n_samples) {
    monitor_process(&mon, fbuf);
    n_fed += block_size;
}

// Bug 2: synth_gfsk() aus ft8_lib/demo/gen_ft8.c (MIT) uebernehmen
synth_gfsk(tones, FT8_NN, freq_hz, FT8_SYMBOL_BT, FT8_SYMBOL_PERIOD, rate, signal);
```

**Datei:** `ft8_lib/libft8simple.c`

---

## PROBLEM: DAX Audio-Devices liefern kein Signal (GELOEST)

**Symptom:** Audio-Devices "Radio to External" (9) und "External To Radio" (8) zeigen Peak=0. Kein Audio vom FlexRadio empfangbar ueber virtuelle Audio-Devices.

**Ursache:** Die virtuellen Audio-Devices brauchen einen aktiven DAX-Client (SmartSDR for Mac oder FlexDAX). Ohne laufende SmartSDR-App werden die Devices nicht mit Audio befuellt.

**Loesung:** VITA-49 UDP Audio-Streaming nutzen statt DAX!
- `stream create type=remote_audio_rx compression=none` fuer RX
- Empfaengt float32 stereo big-endian @ 24kHz (PCC 0x03E3)
- Kein DAX-Treiber, kein virtuelles Audio-Device noetig
- UDP Port 4991 lokal binden, 1-byte Datagramm an Radio:4992 senden

**Dateien:** `radio/flexradio.py` Zeile ~80-120

---

## PROBLEM: `client program` statt `client gui` → kein Slice-Zugriff (GELOEST)

**Symptom:** `slice tune 0 14.074` → "Invalid slice receiver (0)". Befehle an Slices werden abgelehnt.

**Ursache:** Mit `client program SimpleFT8` wird der Client als Programm registriert, bekommt aber keinen Zugriff auf existierende Slices. Mit `client gui SimpleFT8` wird er als GUI-Client registriert und uebernimmt die Slice-Kontrolle.

**Loesung:** `client gui SimpleFT8` verwenden.

**Dateien:** `radio/flexradio.py`

---

## PROBLEM: PyFT8 Import fehlschlaegt — fehlende Dependencies (GELOEST)

**Symptom:** `ModuleNotFoundError: No module named 'serial'` bzw. `No module named 'paho'`

**Ursache:** PyFT8 deklariert nicht alle Dependencies in setup.py. `pyserial` und `paho-mqtt` fehlen.

**Loesung:** `pip install pyserial paho-mqtt` zusaetzlich installieren.

---

## PROBLEM: python3 Alias ignoriert venv (GELOEST)

**Symptom:** `python3` nutzt System-Python statt venv, Module werden nicht gefunden.

**Ursache:** `python3` ist in zsh als Alias auf `/usr/local/opt/python@3.12/bin/python3.12` definiert. `source venv/bin/activate` aendert den Alias nicht.

**Loesung:** Immer den vollen Pfad zum venv-Python verwenden:
```bash
./venv/bin/python3 main.py
```

---

## PROBLEM: TX — VITA-49 Audio kommt nicht am PA an (GELOEST)

**Symptom:** PTT funktioniert (`xmit 1` → Radio zeigt TX rot), VITA-49 Audio-Pakete werden gesendet (2370 Pakete), aber Wattmeter zeigt 0W.

**Root Cause:** Die virtuellen Audio-Devices "External To Radio" / "Radio to External" sind eine DAX-Bruecke die **nur funktioniert wenn SmartSDR laeuft**. VITA-49 DAX TX Pakete allein reichen nicht — das Radio braucht einen registrierten DAX-Client, und das ist SmartSDR.

**Was NICHT funktioniert (getestet):**
- VITA-49 TX-Pakete an Port 4991, 4992, 4993 → kein Power
- Audio ueber Device 8 OHNE SmartSDR → Audio geht an Mac-Lautsprecher
- `stream create type=dax_tx` allein → dax_clients=0, Modulator bekommt kein Audio

**Was FUNKTIONIERT:**
- SmartSDR muss im Hintergrund laufen (DAX-Bruecke aktiv)
- TX-Profil "macOS_FT8" in SmartSDR laden
- DAX in SmartSDR aktivieren
- Audio ueber Device 8 ("External To Radio") senden @ 48kHz int16 mono
- PTT ueber TCP API (`xmit 1`)
- → RF Power kommt raus, SWR OK

**ENDGUELTIGE LOESUNG (ohne SmartSDR!):**
3 Bugs in unserem VITA-49 TX-Code:

1. **Falscher Stream-Befehl:** `stream create type=dax_tx dax_channel=1` → FALSCH
   Richtig: `stream create type=dax_tx1` (ohne Leerzeichen, Channel im Typ!)

2. **DAX-Channel nicht an Slice gebunden:** Fehlender Befehl: `dax audio set 1 slice=0`
   Ohne das bleibt `dax_clients=0` und der Modulator bekommt kein Audio.

3. **Format-Mismatch:** Wir setzten `send_reduced_bw_dax=1` (int16 mono 24kHz)
   aber sendeten PCC 0x03E3 (float32 stereo 48kHz). Radio ignorierte die Pakete.
   Loesung: Kein reduced_bw setzen, float32 stereo @ 48kHz senden, 128 Stereo-Paare pro Paket.

**Korrekte TX-Sequenz:**
```
client gui SimpleFT8
client udpport 4991
slice set 0 tx=1
interlock tx1_enabled=1
transmit set rfpower=50
slice set 0 dax=1
transmit set dax=1
dax audio set 1 slice=0           ← KRITISCH!
stream create type=dax_tx1        ← KRITISCH! (nicht "dax_tx dax_channel=1")
xmit 1                            ← PTT
→ VITA-49 Pakete senden (float32 stereo BE, PCC 0x03E3, an Radio:4991)
xmit 0                            ← PTT aus
```

**Dateien:** `radio/flexradio.py` (send_audio, create_tx_stream), `core/encoder.py`

---

## PROBLEM: screencapture zeigt schwarzes Bild fuer PySide6/Qt (GELOEST)

**Symptom:** `screencapture` auf macOS zeigt schwarzes Fenster fuer Qt/PySide6 Apps.

**Ursache:** Qt nutzt eigenes Rendering (OpenGL/Metal), screencapture kann das nicht capturen.

**Loesung:** Screenshot von innerhalb der App mit `window.grab()`:
```python
pixmap = window.grab()
pixmap.save('/tmp/screenshot.png')
```

---

## PROBLEM: Font-Warning bei PySide6 ("-apple-system" not found) (GELOEST)

**Symptom:** `qt.qpa.fonts: Populating font family aliases took 216 ms. Replace uses of missing font family "-apple-system"`

**Loesung:** Font-Family nicht in globalem Stylesheet setzen, oder nur system-vorhandene Fonts verwenden (Helvetica Neue, Menlo).

---

## PROBLEM: Audio kommt aber Decoder findet 0 Stationen (GELOEST 30.03.2026)

**Symptom:** VITA-49 Audio-Stream liefert Pakete mit Signal (Peak -18 dBFS), aber Decoder dekodiert 0 FT8-Stationen. Gestern (29.03.) ging es, heute nicht.

**Drei Ursachen gefunden:**

### 1. Falsches Audio-Format: float32 stereo 48kHz statt int16 mono 24kHz
**Ursache:** Ohne `client set send_reduced_bw_dax=1` liefert `dax_rx` float32 stereo @ 48kHz (PCC 0x03E3). Das sind doppelt so viele Pakete wie noetig und die FFT/Waterfall-Pakete fluten den UDP-Buffer → 30-50% Paketverlust → nur 10s statt 15s Audio → Decoder kann nicht dekodieren.

**Loesung:** `client set send_reduced_bw_dax=1` senden! Dann kommt int16 mono @ 24kHz (PCC 0x0123). Halb so viele Pakete, kein Verlust.

### 2. Audio-Pegel 10x zu hoch
**Ursache:** Der DAX-RX Audio-Pegel ist bei Peak ~32000 (fast Full-Scale). PyFT8 Decoder erwartet moderaten Pegel (~3000-5000). Bei zu hohem Pegel versagt die LDPC-Dekodierung (llr_sd zu niedrig, ncheck konvergiert nicht zu 0).

**Loesung:** Audio normalisieren auf Peak ~3000 vor dem Dekodieren:
```python
peak = np.max(np.abs(audio.astype(np.float32)))
audio_norm = (audio.astype(np.float32) * 3000 / max(peak, 1)).astype(np.int16)
```

### 3. UDP Buffer zu klein
**Ursache:** Standard-UDP-Buffer (ca. 256KB) wird von FFT+Waterfall-Paketen geflutet. Audio-Pakete gehen verloren.

**Loesung:** 8MB UDP Buffer setzen:
```python
udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
```

### Korrekte RX-Sequenz (standalone, ohne SmartSDR):
```
client gui                              ← OHNE Argument!
client set send_reduced_bw_dax=1        ← KRITISCH! int16 mono 24kHz
keepalive enable
sub slice/tx/audio/dax/radio all
client udpport 4991                     ← NACH subscriptions
slice tune <s> 14.074
slice set <s> mode=DIGU
slice set <s> dax=1
dax audio set 1 slice=<s>
stream create type=dax_rx dax_channel=1 ← NICHT dax_rx1!
→ PCC 0x0123 int16 mono big-endian @ 24kHz
→ Normalisieren auf Peak ~3000
→ [::2] Dezimierung → 12kHz fuer PyFT8
```

**Hinweis:** `stream create type=dax_rx1` → "Malformed command" auf Firmware 4.1.3!
Richtig: `stream create type=dax_rx dax_channel=1`

**Dateien:** `radio/flexradio.py` (connect), `core/decoder.py` (Normalisierung)

---

## PROBLEM: Radio kickt Verbindung / DAX Audio nur Stille (GELOEST 30.03.2026)

**Symptom:** DAX RX Stream liefert Pakete (PCC 0x0123), aber Peak=0 — alle Samples sind Null. Ohne Keepalive-Pings trennt das Radio nach ~10s.

**Zwei Ursachen gefunden:**

### 1. SmartSDR-M besitzt den Slice → DAX geht an SmartSDR-M, nicht an uns
**Ursache:** Der FLEX-8400M hat einen eingebauten Display-Client `SmartSDR-M` der beim Booten automatisch startet und den Slice besitzt (`client_handle=0x5ED81EE8`). Unser DAX-Stream wird zwar erstellt, aber die Audio-Daten gehen an den Slice-Owner.

**Loesung:** 2-Schritt-Verbindung in SEPARATEN TCP-Sessions:
```
# Phase 1: Separate TCP-Session — SmartSDR-M rauswerfen
tcp1 = connect()
client gui
sub client all → SmartSDR-M Handle finden (0x5ED81EE8)
client disconnect 0x5ED81EE8
tcp1.close()
time.sleep(2)

# Phase 2: Frische TCP-Session — jetzt gehoert der Slice uns!
tcp2 = connect()
client gui
→ Slice bekommt unseren client_handle → DAX Audio kommt!
```

### 2. Keepalive-Ping fehlt → Disconnect nach ~10s
**Ursache:** Ohne periodische Pings trennt das Radio die TCP-Verbindung.

**Loesung:** `keepalive enable` senden + alle 5s `ping` senden:
```python
# Nach Setup:
threading.Thread(target=keepalive_loop, daemon=True).start()

def keepalive_loop():
    while running:
        time.sleep(5)
        tcp.send("ping")
```

**Bewiesen:** step4_disconnect_smartsdr.py — 30s stabil, Peak=30539, 100% Non-Zero.
step5_ft8_decode.py — 19 Stationen in 3 Zyklen dekodiert.

**Eingebaut:** `radio/flexradio.py` — `_disconnect_smartsdr()` + `_start_keepalive()`

---

## PROBLEM: Slice-Erstellung scheitert nach SmartSDR-M Disconnect (GELOEST 30.03.2026)

**Symptom:** Nach `client disconnect` von SmartSDR-M sind 0 Slices vorhanden. `slice create` gibt Error 50000003, `display panafall create x=0 y=0` gibt Error 50000009.

**Ursache:** SmartSDR-M belegt beide Receiver-Slots des FLEX-8400M (2 Slices). Erst nach Disconnect werden die Receiver frei. Danach braucht `display panafall create` die RICHTIGEN Parameter.

**Loesung:**
1. SmartSDR-M disconnecten (gibt beide Receiver frei)
2. `display panafall create x=500 y=300` → erstellt Panadapter + Slice 0
3. NICHT `x=0 y=0` oder `x=50 y=50` — die geben Error 50000009!
4. Slice 0 wird automatisch mit dem Panadapter erstellt

**Korrekte Verbindungssequenz (FLEX-8400M, Stand 30.03.2026 abends):**
```
# Phase 1: SmartSDR-M disconnecten (separate TCP-Session)
tcp1 = connect()
client gui
sub client all → SmartSDR-M Handle finden
client disconnect <handle>
tcp1.close()
time.sleep(2)

# Phase 2: Frisch verbinden + eigenen Panadapter/Slice erstellen
tcp2 = connect()
client gui
time.sleep(5)  # Persistence
client set send_reduced_bw_dax=1
keepalive enable
sub slice/tx/audio/dax/radio all
client udpport 4991

# Panadapter + Slice erstellen (NACHDEM SmartSDR-M weg ist!)
display panafall create x=500 y=300   ← KRITISCH: x/y muessen >0 sein!
# → Erstellt automatisch Slice 0

# Slice konfigurieren
slice tune 0 14.074
slice set 0 mode=DIGU
slice set 0 tx=1
interlock tx1_enabled=1
transmit set rfpower=50
slice set 0 dax=1
transmit set dax=1
dax audio set 1 slice=0
stream create type=dax_rx dax_channel=1
stream create type=dax_tx1
```

**WICHTIG:** Nicht mehr als eine App-Instanz gleichzeitig starten! Alte Instanzen werden automatisch beim Start gekillt (main.py kill_old_instances).

**Dateien:** `radio/flexradio.py` (`_disconnect_smartsdr`, `_find_or_create_slice`, `connect`)

---

## PROBLEM: PSKReporter empfaengt kein FT8-Signal von uns (OFFEN 30.03.2026)

**Symptom:** CQ DA1MHH JO31 wird gesendet, Radio zeigt TRANSMITTING, Wattmeter zeigt Leistung, aber PSKReporter zeigt keine Empfangsmeldungen.

**Was funktioniert:**
- PTT (xmit 1/0) → Radio schaltet auf TX
- VITA-49 TX Pakete werden gesendet (4740 Pakete in 12.64s)
- Wattmeter zeigt RF-Leistung
- FT8 Encoding: 79 Symbole, korrekte Frequenz (~1023 Hz)

**Moegliche Ursachen (noch zu pruefen):**
1. TX-Audio erreicht den Modulator nicht korrekt (VITA-49 Port/Stream-ID Problem?)
2. Audio-Upsampling-Qualitaet (np.interp statt Sinc-Filter — inzwischen gefixt von np.repeat)
3. TX-Timing nicht exakt genug (aktuell +0.2s nach Zyklusstart)
4. Radio sendet nur Traeger ohne FT8-Modulation
5. PSKReporter-Monitoring auf 80m am Tag duenn

**Erkenntnisse 31.03.2026:**
- VITA-49 TX Header MUSS `0x18D0xxxx` sein (wie nDAX), nicht `0x18000000`
- TX Port: 4991 (Radio lauscht dort fuer VITA-49 TX Audio)
- Byte-Order: Big-Endian `>f4` (wie nDAX, NICHT little-endian!)
- Audio-Level: NICHT im Code skalieren — Radio steuert Gain per API
- SmartSDR sendet perfekt (66 PSKReporter Spots) → Radio/Antenne OK
- Unser Signal: Big-Endian + 0x18D0 = bisher Dauerton oder kein Empfang
- Little-Endian = Leistung aber Muell-Signal (Tuner dreht durch)
- PROBLEM: Nie isoliert getestet — Radio-Zustand immer durch vorherige Tests korrumpiert

**GELOEST 31.03.2026!** TX funktioniert — 30+ PSKReporter Spots mit 10W, bis Azoren (3025km).

**Root Cause:** Falsches Audio-Format fuer VITA-49 TX!
- FALSCH: float32 stereo big-endian 48kHz (PCC 0x03E3) → Radio ignoriert Audio
- RICHTIG: **int16 mono big-endian 24kHz (PCC 0x0123)** → Radio moduliert korrekt

**Loesung aus AetherSDR Quellcode** (github.com/ten9876/AetherSDR):
Datei `src/core/AudioEngine.cpp`, Funktion `feedDaxTxAudio()`, Zeile 948-998:
- "Radio-native DAX route" nutzt int16 mono big-endian, PCC 0x0123
- Header: Type=1, C=1, TSI=3, TSF=1 (Word0 = 0x1CD1xxxx)
- 128 Mono-Samples pro Paket (256 Bytes Payload)
- Stream-Typ: `dax_tx` (NICHT dax_tx1, NICHT remote_audio_tx!)
- Audio bei 24kHz (reduced bandwidth DAX)
- `transmit set dax=1` + `mic_selection` NICHT aendern (bleibt MI)

**Korrekte TX-Sequenz:**
```python
# Stream erstellen
stream create type=dax_tx

# Audio: 12kHz erzeugen → 24kHz resamplen → int16 mono big-endian
audio_24k = audio_12k[::1]  # oder von 48k: audio[::2]
mono_int16 = (audio_float * 32767).astype('>i2')

# VITA-49 Paket:
w0 = (1<<28)|(1<<27)|(3<<22)|(1<<20) | (count<<16) | words  # 0x1CD1xxxx
PCC = 0x0123  # NICHT 0x03E3!
payload = mono_int16.tobytes()  # 128 Samples = 256 Bytes
→ senden an Radio-IP Port 4991
```

**Was NICHT funktioniert hat (2 Tage Debugging):**
- float32 stereo (PCC 0x03E3) → Dauerton, keine Modulation
- Little-endian → Modem-Geraeusche, Tuner dreht durch
- remote_audio_tx → keine Leistung
- dax_tx1 → Leistung aber keine FT8-Modulation
- Opus-komprimiert → keine Leistung
- Verschiedene Header-Formate → kein Unterschied

**Dateien:** `radio/flexradio.py` (send_audio), `core/encoder.py` (SAMPLE_RATE_FT8=12000)

---

## ERKENNTNIS: FLEX-8400M hat nur 1 SCU — kein echtes Simultandiversity (02.04.2026)

**Beobachtung:** `display panafall create` fuer 2. Panadapter gibt Error 0x50000009 (SL_NO_FOUNDATION_RX_AVAILABLE). `slice create` gibt Error 0x50000003 (ALL_SLICES_IN_USE). Beide Antennen gleichzeitig empfangen geht nicht.

**Ursache:** FLEX-8400M hat nur 1 SCU (Spectral Capture Unit). Fuer echtes Simultandiversity braucht man den FLEX-8600M (2 SCUs). Bestaetigt durch AetherSDR-Quellcode und FlexRadio Community.

**Loesung: Temporal Polarization Diversity!**
Antenne pro FT8-Zyklus (15s) wechseln. Stationen akkumulieren statt loeschen. Bei Duplikaten besseren SNR behalten. Stationen die >2 Min nicht mehr gehoert werden: entfernen.

Ergebnis: 14 Stationen NORMAL → 48 Stationen DIVERSITY bei POOR Conditions auf 20m. 3x mehr! Neuseeland (18.000 km) empfangen mit einer Regenrinne als zweite Antenne.

**Implementierung:**
```python
# Bei jedem Zyklus-Start:
if diversity_cycle % 2 == 0:
    radio._send_cmd(f"slice set {s} rxant=ANT1")
    radio._send_cmd(f"slice set {s} rfgain={gain_a}")
else:
    radio._send_cmd(f"slice set {s} rxant=ANT2")
    radio._send_cmd(f"slice set {s} rfgain={gain_b}")
# Stationen akkumulieren, nicht loeschen!
```

**WICHTIG:** Antennen-Switch non-blocking in separatem Thread! Sonst blockiert Keepalive → Radio-Disconnect.

**Dateien:** `ui/main_window.py` (_on_cycle_start, _on_cycle_decoded)

---

## ERKENNTNIS: LEVEL Meter zeigt falschen Wert — falsche Meter-ID (GELOEST 02.04.2026)

**Symptom:** LEVEL Meter (ID 15) zeigt immer -81.4 dBm unabhaengig von Antenne oder RF-Gain.

**Ursache:** Meter-IDs sind dynamisch. Code hat LEVEL Meter ohne Pruefung von `src=SLC` und `num=<slice_index>` gelernt. Konnte falscher Meter (anderer Slice, andere Quelle) sein.

**Loesung:** `_learn_meters_from_text()` Methode: parst `src`, `nam` UND `num`. LEVEL wird NUR akzeptiert bei `src=SLC` + `num=<unser_slice_index>`.

**Dateien:** `radio/flexradio.py` (_learn_meters_from_text)

---

## ERKENNTNIS: Modaler Dialog blockiert Signal-Zustellung (GELOEST 02.04.2026)

**Symptom:** DX Tuning Dialog (QDialog.exec()) empfaengt keine cycle_decoded Signale vom Decoder-Thread. Dialog bleibt bei 0%.

**Ursache:** `dialog.exec()` startet einen modalen Event-Loop der Cross-Thread-Signale nicht zuverlaessig zustellt. Der Decoder emittiert cycle_decoded aus einem Background-Thread.

**Loesung:** `dialog.show()` (non-modal) statt `dialog.exec()`. Ergebnis-Handling ueber accepted/rejected Signals.

**Dateien:** `ui/main_window.py` (_start_dx_tuning)

---

## ERKENNTNIS: FLEX-8400M Noise Floor vs IC-7300 (01.04.2026)

**Beobachtung:** IC-7300 + SDR-Control findet Stationen bis -24 dB. FLEX-8400M (egal welche Software) findet unter -15 dB kaum noch was. Bei gemeinsamen Stationen ist FLEX 4-18 dB staerker.

**Ursache:** FLEX-8400M hat hoeheren Noise Floor (-128 dBm) als IC-7300 (-140 dBm). Das ist BY DESIGN — Direct Sampling 16-bit ADC bei 122.88 MHz priorisiert Dynamikbereich (115 dB RMDR) auf Kosten der Empfindlichkeit.

**KEIN Defekt, KEINE Einstellungssache!** Trade-Off: Dynamik vs Empfindlichkeit.

**Was hilft:**
- Preamp pro Band optimieren (8-10 dB Noise Rise Regel)
- DX-Modus (32-bit float 48kHz statt 16-bit 24kHz)
- AP-Decoder fuer schwache bekannte Signale
- SimpleFT8 Decoder schlaegt SDR-Control auf gleichem FLEX (13 vs 12)!

**Quellen:** FlexRadio Community, S-Meter Vergleich 8400 vs 6400
