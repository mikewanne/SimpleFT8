# P3.AUDIO-DUMP-DEBUG V2 — Self-Review (Rolle: frische KI prueft V1)

**Auftrag:** V1 kritisch lesen, Luecken/Mehrdeutigkeiten benennen,
V3-Plan schaerfen. **NICHT** das Problem loesen, sondern den Plan
verbessern.

---

## Lessons aus V1

### L1 — V1 Q2 „Diversity-Pattern" nicht beantwortet → Code-Verifikation

V1 fragt ob Diversity 1 oder 2 Decoder hat. Antwort durch
Code-Pruefung 08.05.:

- `ui/main_window.py:123` instanziiert **EINEN** Decoder.
- `core/diversity_merger.py` definiert `DiversityMerger`-Klasse, aber
  `grep DiversityMerger\(` findet **keine** Instanziierung in `ui/` —
  nur in Tests. Klasse ist im aktuellen Produktiv-Code-Pfad
  ungenutzt.
- `radio/flexradio.py:81` hat `on_audio_callback_b = None` aber
  `mw_radio.py:49` setzt nur `on_audio_callback = self.decoder.feed_audio`.
- Diversity-Implementierung in v0.95.x: **Pattern-Rotation pro Slot**
  (70:30 ANT1/ANT2). Pro Slot bekommt der EINE Decoder Audio von
  genau einer Hardware-RX-Antenne — die in
  `mw_cycle._resolve_hardware_antenna()` ermittelt wird.

**Konsequenz V2:** V1-Annahme „1 Decoder, 1 Stream pro Slot" ist
korrekt. Antennen-Info pro Slot ist eindeutig. V3 darf das hardcodieren
und einen einfachen Setter `decoder.set_current_antenna(ant)`
verwenden.

→ **Falsifikations-Kandidat fuer R1:** „Aendert sich das wenn Diversity
zwei parallele Decoder bekommt?" — antworten: aktuell unmoeglich,
Decoder ist Singleton, keine zweite Instanz im Code.

### L2 — V1 §5.3 Hook-Punkt zu spaet (NACH np.concatenate)

V1 hookt nach `audio_raw = np.concatenate(chunks)` (decoder.py:200).
Das ist **NACH** der Noise-Floor-basierten Normalisierung, **NACH**
Resample, **NACH** Preprocessing wenn man Z.215+ liest. NEIN — bei
genauem Lesen ist Z.200 GENAU die richtige Stelle: Noise-Norm passiert
Z.205-212 NACH Z.200, Resample Z.215 NACH Z.200.

**V2-Schaerfung:** Hook explizit ZWISCHEN Z.200 (`np.concatenate`)
und Z.205 (`audio_f = audio_raw.astype(...)`). `audio_raw` zu diesem
Zeitpunkt ist roh-konkateniert von 24kHz int16 chunks — perfekt
fuers Replay weil unverarbeitet. → V3 muss Z.200 vs Z.205 explizit
markieren.

### L3 — V1 ignoriert Slot-Skip-Pfad

`_decode_loop` Z.169-173 hat einen Skip wenn Audio leer ist:
```python
if not chunks:
    print(f"[Decoder] Zyklus ...: kein Audio")
    continue
```

In dem Fall kommt `_process_cycle` nie an und es gibt nichts zu
dumpen. Das ist OK aber V2-Note: keine WAV bei leerem Slot. V1
nicht erwaehnt → V3 dokumentieren.

### L4 — V1 Filename-Format `_v2`-Suffix unvollstaendig

V1 sagt: bei Kollision `_v2`. Aber wenn 3× im selben Sekunden-Slot
getriggert wird (extrem selten — eigentlich unmoeglich, 1 Slot = 1
Decode), dann waere `_v3` auch noetig.

**V2-Realitaetscheck:** `target_slot_start` ist UTC-Sekunden des
TX-Slot-Anfangs. Pro Slot wird `_process_cycle` **genau einmal**
aufgerufen (Z.157-179 `_decode_busy`-Lock verhindert
Mehrfach-Decode). Kollision kann nur passieren wenn:
- (a) Mike App-Zeit zurueckdreht (NTP-Sprung),
- (b) Decoder restart innerhalb 1 Sekunde,
- (c) gleichen Slot 2× im selben Tag (z.B. UTC 23:59:45 Slot
  beider Tage — aber TS hat YYYY-MM-DD drin → unmoeglich).

→ KISS: `_v2`-Suffix reicht. V3 testet (a) oder (b).

### L5 — V1 §5.4 `_atomic_write_wav` braucht keinen tempfile.mkstemp

WAV-Datei muss **nicht** atomar sein wie ADIF-Archiv (kein
existing-Append-Risiko, jede WAV ist self-contained). KISS:
direkt schreiben + bei Crash unfinished WAV als naechstes vom
FIFO-Cleanup geloescht.

ABER: Mike-Erfahrung mit P2.ADIF-ARCHIVE zeigt: Atomic-Write
schadet nicht und bringt 1 Schicht extra Sicherheit. Pattern ist
schon bekannt, kostet < 10 Zeilen extra.

**V2-Entscheidung:** Atomic-Write **beibehalten** — Konsistenz mit
P2 + Schutz gegen halbe WAV bei Strg+C/Crash. „Halbe WAV" ist
schmerzlos (audacity faellt nicht um, aber schoener wenn alle
WAVs gueltig sind).

### L6 — V1 §5.5 Antennen-Info-Pfad zu vage

V1 sagt: „Im _on_cycle_decoded oder _slot_setup, BEVOR Decoder
Audio bekommt". Das ist mehrdeutig — Audio kommt kontinuierlich
ueber `feed_audio()`, das Audio fuer Slot N wird waehrend Slot N
gesammelt. „Bevor" muss heissen: vor `_process_cycle` startet.

**V2-Schaerfung:** Antenne wird im PRE-SLEEP von `_decode_loop`
ermittelt (Z.140-150ish, dort wo `target_slot_start` berechnet
wird). Aber Decoder ist Subsystem — der weiss nichts von der
Antennen-Architektur. Sauberer: `mw_cycle.py` setzt
`decoder.set_current_antenna(ant)` direkt **NACH**
`_resolve_hardware_antenna()` aufruf, nicht im Decoder selbst.

`_resolve_hardware_antenna(default_ant)` wird in `mw_cycle.py:80`
als „neuer Helper" beschrieben (CLAUDE.md). Wir setzen die
Antenne genau dort.

→ V3 muss exakte Datei:Zeile fuer Setter-Aufruf liefern.

### L7 — V1 fehlt: Settings-UI Layout-Detail

V1 §5.2 sagt nur „QCheckBox + QSpinBox". UX-konkret:
- Checkbox „Audio-Slots fuer Debugging sichern" (Default unchecked)
- Daneben: „Max. Files:" + Spinbox (50-1000, Default 200)
- Spinbox enabled/disabled abhaengig vom Checkbox-Zustand
- HLine drueber/drunter fuer visuelle Trennung von Debug-Konsole

**V2-Schaerfung:** V3 muss Layout-Pattern explizit (HBoxLayout,
QLabel + Spinbox + Stretch) + enabled-Bindung.

### L8 — V1 fehlt: Disk-Space-Pre-Check

Wenn Mike Cap auf 1000 setzt + Diversity laeuft, koennte trotzdem
ueber 290 MB landen. Was wenn Disk voll wird? Dann faellt der
WAV-Write um, V1 hat try/except → kein Crash, aber Mike merkt
nichts.

**V2-Vorschlag:** Bei FIFO-Cleanup pruefen ob Disk-Space < 1 GB
frei → Warnung im Log + (optional) Cleanup von 50% statt nur
overflow.

ALTERNATIVE (KISS): Disk-Voll-Check **NICHT** einbauen. FIFO-Cap
ist die Kontrolle. Mike kann das Verzeichnis manuell loeschen.
Hobby-Tool, nicht Server.

**V2-Entscheidung:** KISS — kein Disk-Voll-Check. FIFO-Cap reicht.

### L9 — V1 fehlt: was passiert bei Toggle-Wechsel mid-Slot?

Mike toggelt OFF→ON waehrend Slot N gerade decoded wird. V1
erwaehnt das nicht.

**V2-Klaerung:** `_audio_dump_enabled` wird im selben Thread
gelesen wie `_process_cycle`. Race-Condition trivial (bool-Read
ist atomar in Python). Wenn Toggle ON kommt waehrend `_process_cycle`
laeuft → naechster Slot wird gedumpt, aktueller nicht. Akzeptabel.

→ V3 dokumentiert, kein Test-Aufwand.

### L10 — V1 §5.4 `_enforce_fifo_cap` global glob `**/*.wav`

Gut gewaehlt — pruft ALLE band-Subdirs zusammen. ABER: was wenn
in `audio_dump/` zufaellig non-WAV-Dateien rumliegen (Mike kopiert
mal was rein)? `glob("**/*.wav")` ignoriert die — gut. Problem:
versehentliche Tmp-Dateien `.foo.wav.xyz.tmp` werden auch von glob
gefunden → wuerde aus FIFO-Cleanup keine, weil glob-Pattern endet
auf `.wav`. Tmpfile-Pattern ist `.{name}.{rand}.tmp` — endet
nicht auf `.wav`. ✅ Safe.

→ V3 dokumentiert dass FIFO nur `.wav`-Endung beruecksichtigt.

### L11 — V1 fehlt: Test fuer mw_cycle Antennen-Setter-Aufruf

V1 §6 listet 12 Tests. Aber kein Test fuer den Setter-Aufruf von
`mw_cycle` (Integration). Das ist Qt-Smoke-Test-Gebiet.

**V2-Schaerfung:** Test 13 (oder Erweiterung von Test 9):
`test_mw_cycle_sets_decoder_antenna_per_slot` mit `QT_QPA_PLATFORM=
offscreen` + Mock-Decoder. Pro Slot Antenne wird vor Decode
gesetzt.

→ Tests-Soll 12 → 13.

### L12 — V1 §3 Cap-Spinbox Range vs Disk-Realitaet

V1: Cap 50-1000, Default 200. Bei 1000 Slots × 576 KB = 576 MB
Single-Antenne, ~1.15 GB Diversity (rotiert). Mike's MacBook hat
zwar Platz, aber 1 GB ist viel.

**V2-Vorschlag:** Cap-Range 50-500 (Default 200). 500 Slots = ~290 MB,
sicherer Default-Cap.

**V2-Realitaetscheck:** Mike ist erwachsen, kann selber
entscheiden. Range 50-1000 lassen, Default 200. Spinbox-Tooltip
zeigt geschaetzte Disk-Belegung.

→ V3 entscheidet final, mein Vorschlag: **Range 50-1000, Default
200, Tooltip mit Disk-Schaetzung.**

### L13 — V1 vergisst: was ist bei Modus-Wechsel mid-Slot?

Mike schaltet FT8 → FT4 waehrend ein FT8-Slot decoded wird. V1
filtert nur `self._mode == "FT8"`. Wenn `_mode` mid-`_process_cycle`
auf FT4 wechselt → kein Dump. Das ist OK weil Slot war FT8 — aber
Test-relevant.

**V2-Schaerfung:** Modus-Wert wird **vor** `_dump_audio_slot` gelesen,
nicht im Helper selbst. → V3 hookt:

```python
if self._audio_dump_enabled and self._mode == "FT8":
    try:
        self._dump_audio_slot(audio_raw, target_slot_start)
    ...
```

Das ist V1's Pattern — passt.

### L14 — V1 fehlt: WAV-Format-Doku

V1: 24kHz, 16-bit, mono. ABER `audio_raw` ist `np.concatenate(chunks)`
und `chunks` aus `feed_audio(samples_int16)` → schon int16 24kHz.

**V2-Pruefung:** core/decoder.py:84 `_audio_buffer_24k` ist eine Liste
von int16-Arrays. `np.concatenate` haengt aneinander → bleibt int16
24kHz. ✅ V1 korrekt.

### L15 — V1 nennt nicht: Pfad-Resolution-Question

V1 §3.1 Punkt 5: `audio_dump/{band}_FT8/...`. Aber **wo** liegt
`audio_dump/`? Mike's CWD oder fixer Projekt-Root oder
`~/.simpleft8/`?

Mike-Wunsch laut TODO: „Unterverzeichnis im SimpleFT8-Ordner, klar
wiederauffindbar". → Projekt-Root, also relativ zur App.

**V2-Schaerfung:** `Path("audio_dump")` als relativer Pfad
funktioniert nur wenn App im Projekt-Root gestartet wird (Mike's
Standard-Start). Sicherer:
`Path(__file__).resolve().parent.parent / "audio_dump"` — relativ
zur Decoder-Datei → Projekt-Root.

Aber: das ist auch fragil bei zip-Bundles oder PyInstaller. Final-
Pragma: `Path.cwd() / "audio_dump"` mit Fallback auf
`Path(__file__).parent.parent / "audio_dump"`.

→ V3 entscheidet. **Mein Vorschlag:** absoluter Pfad ueber
`Path(__file__).resolve().parent.parent` = SimpleFT8-Root, robust
gegen CWD-Wechsel.

---

## V2-Antworten auf V1's offene Fragen (§7)

1. **Antennen-Info Normal-Modus:** `_resolve_hardware_antenna(
   default_ant)` aus mw_cycle.py:674 wiederverwenden — der Helper
   ist exakt fuer den Use-Case da (Phase 2 vs Diversity vs Normal).
   Default-Ant ist `settings.get("rx_antenna", "ANT1")`.
2. **Diversity-Pattern:** Geklaert (L1) — 1 Decoder, 1 Stream pro
   Slot, Antenne ueber Pattern-Rotation. Kein Special-Handling.
3. **APP_VERSION-Bump:** **JA** auf 0.95.20 — neues Modul +
   Decoder-API + Settings-Keys = nicht trivial. V3 setzt Bump.
4. **Cap-Default:** 200 (= ~58 MB Single-Antenne, ~115 MB Diversity).
   Range 50-1000.
5. **Cleanup-Frequenz:** Jedes Mal — `glob("**/*.wav")` < 1 ms bei
   200 Files.
6. **Settings-UI Spinbox:** Ja, Spinbox einbauen (Mike-Wunsch
   Refinement: rollierend mit Cap).
7. **Antennen-Info Toggle-OFF:** Setter-Aufruf laeuft trotzdem
   (1 String-Set, irrelevant).

---

## V2-Schaerfungen fuer V3

| Punkt | V1 | V2 |
|---|---|---|
| Hook-Punkt | „nach np.concatenate" | exakt zwischen Z.200 und Z.205 |
| Antennen-Setter-Aufruf | „in mw_cycle" | exakt nach `_resolve_hardware_antenna()` |
| WAV-Format | „24kHz int16 mono" | bestaetigt durch Code-Trace |
| Atomic-Write | Pflicht | Beibehalten (KISS aber ueberlegt) |
| Cap-Range | 50-1000 | bleibt, Tooltip mit Disk-Schaetzung |
| Modus-Filter | nur FT8 | bleibt, mit Race-Condition-Doku |
| Pfad-Resolution | unklar | absoluter Pfad via `__file__.resolve()` |
| Tests-Soll | 12 | 13 (mw_cycle Integration) |
| FIFO-Cleanup | jedes Mal | jedes Mal, nur `*.wav` |
| APP_VERSION | offen | 0.95.20 |

---

## V3-Pflicht-Punkte

V3 muss enthalten:
- Komplettes Code-Skelett (Compact-fest)
- 13 Tests konkret formuliert
- Datei:Zeile-Referenzen fuer alle Hook-Punkte
- Pfad-Resolution explizit
- Settings-UI Layout-Code
- Atomic-Write-Pattern (wiederverwenden aus P2)
- Antennen-Setter-Aufruf-Pfad in mw_cycle
- APP_VERSION 0.95.19 → 0.95.20
- Lessons-Learned-Vorschlaege

---

## R1-Vorbereitung — kritische Fragen fuer Plan-Review

1. **Race-Condition `_audio_dump_enabled`:** bool-Read atomar, aber
   `_audio_dump_max_files` int? Bei Toggle-Wechsel waehrend
   Cleanup-Run koennte das Cap-Wert wechseln. Akzeptabel?
2. **Antennen-Info-Race:** `set_current_antenna(ant)` wird VOR
   `_process_cycle`-Trigger gesetzt. Aber `_process_cycle` laeuft
   in eigenem Thread. Wenn Setter mehrfach pro Slot aufgerufen wird
   (mw_cycle hat mehrere Code-Pfade?), koennte ein falscher Wert
   gespeichert werden.
3. **WAV-Atomic-Write Disk-Voll-Edge:** `os.replace` schlaegt fehl bei
   voller Disk → tmp wird unlinkt aber existing Datei kommt nicht.
   Akzeptabel (kein Crash, Mike merkt's beim FIFO).
4. **Test-Coverage Diversity-Pfad:** Tests laufen ohne Hardware. Kann
   `_resolve_hardware_antenna()` mit Mock-Settings korrekt getestet
   werden?
5. **Settings-UI Disabled-Bindung:** Spinbox bei Checkbox-OFF disabled
   — Pflicht-Test mit Qt-offscreen?
6. **Cap-Range vs Filename-Format:** WAV-Filename ist im Sekunden-
   genauen Slot-Format. Bei FT2 (3.8s Slots) waeren mehrere WAVs
   im selben Sekunden-Slot moeglich → aber FT2 wird gefiltert,
   irrelevant.
7. **Path("audio_dump")-Relative vs Absolute:** Mike startet App
   immer aus Projekt-Root via `cd "..." && ./venv/bin/python3 main.py`.
   Aber Tests laufen aus pytest-CWD. Tests muessen `tmp_path`
   verwenden → kein Konflikt.

---

**V2-Ende. R1-Plan-Review folgt.**
