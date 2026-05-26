# SimpleFT8 — Funktionsweisen-Referenz

**Zweck dieser Datei:** Erklären **wie** und **warum** Features intern
funktionieren. Antwort auf „wie war das nochmal mit X?" ohne den Code
neu lesen zu müssen.

**Abgrenzung zu anderen Dateien:**
- `HISTORY.md` = WANN was geändert wurde (Changelog, nur anhängen)
- `CLAUDE.md` = Regeln + Architektur-Überblick + Workflow-Pflichten
- `HANDOFF.md` = aktueller Session-Stand + nächste 1-2 Schritte
- `TODO.md` = Backlog (offene Bugs, Feature-Wünsche)
- **`FEATURES.md` (DIESE DATEI)** = funktionale Detail-Doku

**Pflege:** Bei jedem Feature wo eine Erklärung später nochmal nützlich
sein wird → Sektion hier anlegen. Trivial-Klausel: 1-2-Zeilen-Features
nicht hier, dafür reicht der Code-Kommentar.

**Stand:** 2026-05-26

---

## 1. Diversity Dx-Filter (warum filtern wir starke Stationen weg?)

**Kurzantwort:** Wir filtern starke Stationen **nicht** weg — wir
**ignorieren sie nur beim Bewerten der Antennen-Performance** im
Dx-Modus. Die Stationen sind weiter im Empfangsfenster, in der Karte,
im QSO-Log, im Wasserfall sichtbar und voll anrufbar.

### Wo der Filter im Code sitzt

`ui/mw_cycle.py:357-359`:
```python
# DX: schwache Signale (-20 < SNR < -10) pro Antenne
a1_weak = [m for m in a1_msgs if m.snr is not None and m.snr < -10]
a2_weak = [m for m in a2_msgs if m.snr is not None and m.snr < -10]
```

`a1_msgs`/`a2_msgs` enthalten **alle** decodierten Stationen pro Antenne
— da wird nichts entfernt. Nur die `a1_weak`/`a2_weak`-Untermenge
(SNR < -10 dB) fließt in die Antennen-Bewertung im Dx-Modus.

### Was der Dx-Filter beeinflusst

1. **`update_diversity_counts(...a1_weak_count=..., a2_weak_count=...)`**
   — die Status-Zeile zeigt im Dx-Modus die Anzahl schwacher Stationen
   pro Antenne (nicht alle).
2. **ANT2-Win-%** (P85, Median über 4 Zyklen) wird im Dx-Modus aus
   `a2_wins`/`compared` berechnet wo nur Vergleiche mit schwachen
   Stationen zählen.
3. **Diversity-Ratio-Entscheidung** (50:50 ↔ 70:30 ↔ 30:70) folgt der
   ANT2-Win-% → schwache Signale dominieren die Pattern-Wahl.

### Was der Dx-Filter NICHT beeinflusst

- RX-Tabelle (`rx_panel.table`) zeigt weiterhin **alle** Stationen
- Karte (`direction_map_widget`) zeigt **alle**
- QSO-Log (`qso_panel`) zeigt **alle**
- Wasserfall zeigt **alle**
- Anklicken/QSO-Starten geht für **alle**
- Statistik-Dateien (`statistics/`) loggen **alle** (jede Antenne
  separat, das DivDx-File hat aber den Dx-Score)

### Warum das fachlich richtig ist

Hobbyfunker im Dx-Modus jagen die schwachen DX-Stationen (die
Karibik-Insel an der Hörgrenze). Eine ANT2-Bewertung „besser für Dx"
muss aus den **schwachen** Signalen abgeleitet werden — wenn man
S9-Locals mitzählt, dominiert die Stadtantenne immer und das Pattern
springt nie auf 30:70.

Mike's Vergleich (25.05.2026): „starke Stationen sind ein Geschenk,
warum sollten wir die wegfiltern?". Antwort: weil sie für die Frage
„welche Antenne zieht DX besser?" nichts beitragen — die hört man eh
auf beiden Antennen.

### Verwandte Konstanten / Pfade

- Threshold: hartcodiert `< -10` in `ui/mw_cycle.py:358`
- Scoring-Mode-Property: `core/diversity.py:DiversityController.scoring_mode`
  („normal" oder „dx")
- Median-Glättung: `mw_radio.py` `_win_rate_history` Ringpuffer Länge 4

---

## 2. Auto-Hunt Defer-Familie (P81/P122/P124/P127/P128/P129)

**Kurzantwort:** Wenn ein Hintergrund-Mechanismus etwas tun will
(Auto-Hunt stoppen, Log-Eintrag schreiben, Empfang blocken), aber das
gerade einen laufenden QSO stört, **wird die Aktion bis zum QSO-Ende
deferiert** statt sofort ausgeführt. Pattern-Familie mit aktuell 6
Iterationen.

### Gemeinsames Pattern

```
Trigger → if QSO aktiv: pending_X = data; return
        → if QSO inaktiv: führe Aktion sofort aus

QSO-Ende-Handler (3 Pfade: complete/timeout/HALT):
    flush_pending_X()  # spielt deferierte Aktionen ab
```

3 QSO-Ende-Pfade in `ui/mw_qso.py`:
- `_on_qso_confirmed_visual` — QSO ✓ erfolgreich
- `_on_qso_timeout` — QSO ✗ Timeout
- `_on_cancel` — HALT-Button (Sicherheits-Notbremse)

### Die 6 Iterationen

| # | Ticket | Was wird deferiert? | Wer triggert? |
|---|--------|---------------------|---------------|
| 1 | P81 (v0.97.53) | Auto-Hunt-Stop-**Meldung** im Log | `core/auto_hunt.py` |
| 2 | P122 (v0.98.05) | Auto-Hunt-Stop-**Aktion** selbst | 10-Min-Cap / 5-Min-Maus / 15-Min-Totmann |
| 3 | P124 (v0.98.06) | Hash-Call-**Resolution** (`<...>` → call) | Decoder im aktiven QSO-State |
| 4 | P127 (v0.98.08) | TX-Log-Eintrag bei SWR-Abbruch verwerfen | `_on_swr_alarm` |
| 5 | P128 (v0.98.07) | Empf.-Eintrag 60s nach QSO blocken | `on_message_decoded` Filter |
| 6 | P129 (v0.98.10) | P128-**Whitelist** für 73/RR73 | Korrektur an P128 |

**Helper-Funktion `_qso_active_for_msg_defer()`** in `ui/mw_qso.py`
ist die Single-Source-of-Truth — keine Logik-Drift möglich.

### Sofort-Stop bleibt Sofort-Stop

`manual_halt`, `swr_block`, `band_change` greifen **weiterhin sofort**
— Hardware-Safety und Kontext-Wechsel haben Vorrang vor QSO-Etiquette.

### Warum diese Pattern-Familie?

Field-Bugs zeigten wiederholt das gleiche Muster: Hintergrund-Aktion
unterbricht laufenden QSO-Flow → User-Verwirrung („warum hat er
mittendrin abgebrochen?", „warum ist die Meldung mitten im QSO?").
Defer-Pattern ist **KISS** (Flag + Helper + 3 Flush-Punkte) und
verhindert die ganze Klasse von Bugs.

Pattern-Familie ist explizit etabliert (siehe Memory
`project_p129_done.md`) — neue Defer-Tickets sollen das Pattern
reusen, nicht neu erfinden.

---

## 3. Hash-Call-Resolution P124 (`<...>` und `<CALL>`)

**Kurzantwort:** FT8-i3-Frames können Calls als 22-Bit-Hash senden:
`DA1MHH <...> R+10`. Unsere State-Machine erkennt `<...>` nicht als
„zu uns gerichtet" → bleibt in WAIT_REPORT → ruft endlos. Fix: im
aktiven QSO-State den Hash kontextuell durch `qso.their_call`
ersetzen — der einzige Kandidat im Kontext.

### Die zwei Marker-Formen (R1-F4-Catch)

`ft8_lib/message.c:709` produziert **zwei** Hash-Marker:
- `<...>` — unresolved Hash (Hashtable kennt den Call nicht)
- `<CALL>` — resolved aus Hashtable (Brackets bleiben als Markierung)

Beide werden über `is_hash_marker(call)` erkannt — kein Hardcode auf
`"<...>"` allein.

### Code-Struktur

`core/qso_state.py` Modul-Ende:
```python
HASH_MARKER = "<...>"
HASH_RESOLVE_STATES = frozenset({QSOState.TX_CALL, ...})  # 7 active states

def is_hash_marker(call: str) -> bool:
    return len(call) >= 3 and call.startswith("<") and call.endswith(">")

def resolve_hash_in_msg(msg, expected_call: str) -> bool:
    if not is_hash_marker(msg.field2): return False
    if not expected_call: return False
    original_marker = msg.field2
    msg.field2 = expected_call
    msg.raw = msg.raw.replace(original_marker, expected_call)
    return True
```

`ui/mw_cycle.py:on_message_decoded` (Z. 763) ruft
`_p124_resolve_hash_if_active_qso(msg)` **vor** P128-Block, P129-
Whitelist, State-Machine.

### 3 Guards (KISS)

1. **target == settings.callsign** (Hash an UNS, nicht an andere)
2. **state in HASH_RESOLVE_STATES** (7 aktive QSO-States)
3. **qso.their_call ist set** (kein Resolution ohne Kontext)

### Bekannter Race (R1-🟠, akzeptiert)

Wenn Fremd-Station Hash `<...>` an uns sendet während wir mit RA9LL im
QSO sind, wird Resolution falsch auf RA9LL setzen. Mike-Heuristik
nimmt das billigend in Kauf (Frequency-Match-Sicherung nur bei
Field-Evidenz nachrüsten — siehe TODO.md P124-Followup).

### Auswirkung

- Endlosschleife `-17` ↔ `<...> R+10` aufgelöst
- State-Machine wechselt korrekt auf RR73
- P125 (Höflichkeits-73 nach N Retries) wahrscheinlich überflüssig
- QSO-Erfolgsrate steigt für Special-Event-Calls + Contest-Stationen
  die i3-Frames mit Hash senden

### Display-Verhalten

Plain Call im UI (Mike-Entscheidung 25.05.: kein „RA9LL?"-Suffix,
kein Farbcode — User weiß im QSO-Kontext eh mit wem).

---

## 4. Debug-Konsole (Ctrl+D)

**Aktivierung:** `Ctrl+D` (Toggle) ODER Einstellungen →
„Debug-Konsole anzeigen". Einstellung wird persistiert.

**Funktionen:**

| Button | Funktion |
|--------|----------|
| Filter | Live grep-artige Filterung der Ausgabe (case-insensitive) |
| Copy | Sichtbaren Text in Zwischenablage |
| Clear | Konsole leeren |

**Typische Filter:**
- `diversity` — Diversity-Score-Entscheidungen
- `cq-freq` — CQ-Frequenz-Berechnungen
- `antenna` — Smart Antenna Selection
- `omni` — OMNI-TX Status
- `qso` — QSO State Machine
- `stats` — Statistik-Logger

**Technisch:** Menlo 11pt, max 500 Zeilen Ringpuffer, stdout+stderr
werden umgeleitet (Original-Konsole bleibt parallel aktiv).

---

## 5. Statistik-Format (`statistics/` Verzeichnis)

**Zweck:** SimpleFT8 loggt pro FT8/FT4-Zyklus die Anzahl empfangener
Stationen + Durchschnitts-SNR. Daten als Markdown-Dateien pro Stunde
für Langzeitanalysen + Bandpilot-Empfehlungen.

**Verzeichnisstruktur:**
```
statistics/
├── Normal/<band>/<FTmode>/YYYY-MM-DD_HH.md
├── Diversity_Normal/<band>/<FTmode>/YYYY-MM-DD_HH.md
└── Diversity_Dx/<band>/<FTmode>/YYYY-MM-DD_HH.md
```

**Datei-Format (pro Stunde):**
```markdown
# Statistik YYYY-MM-DD HH:00-HH:59 UTC | FT8 | 20m | Normal

| Zeit | Stationen | Ø SNR |
|------|-----------|-------|
| HH:00:15 | 12 | -8 |
```

Im Diversity-Modus zusätzliche Spalte `Ant2 Wins`.

**Pause-Bedingungen (Warmup + Tuning):**

| Zustand | Grund | Dauer |
|---------|-------|-------|
| Radio-Suche | HW nicht verbunden | bis Verbindung |
| Gain/Tuning aktiv | Messdaten verfälscht | bis Ende + 60s |
| Bandwechsel | Accumulator leer | 60s Settling |
| Moduswechsel | Normal ↔ Diversity | 60s Settling |
| App-Start | Erste Zyklen unzuverlässig | 60s Settling |

Stats-Cleanup: FIFO-Sliding-Window N=30 pro `(Modus, Band, Proto,
Stunde)`-Bucket (P116 v0.98.01) — saisonale Variation berücksichtigt.

Antenna-QSO bleibt bei 90-Tage-Datum-Cleanup (separate Logik).
Bandpilot-Cache wird bei Bucket-Pruning invalidiert.

Nur FT8 + FT4. FT2 nicht unterstützt (zu wenige Stationen).

---

## 6. DT-Timing (RX + TX Konvergenz)

**Stand 23.04.2026 — validiert.**

### RX-Korrektur

Decoder wacht 1.5s vor Slot-Ende auf. Audio-Buffer enthält Audio ab
1.5s VOR aktuellem Slot-Start. **WSJT-X Protokoll-Konvention:**
TX startet bei `t=0.5s` im Slot (nicht bei `t=0`).

**`DT_BUFFER_OFFSET` (`core/decoder.py`):**

| Modus | Wert | Formel |
|-------|------|--------|
| FT8 | 2.0 | 1.5 (Buffer) + 0.5 (WSJT-X Protokoll) |
| FT4 | 1.0 | 0.5 + 0.5 |
| FT2 | 0.8 | 0.3 + 0.5 |

**Konvergenz (nur FlexRadio):** ~0.24s VITA-49 RX-Hardware-Latenz.
Stationen zeigen DT ≈ 0.0-0.2 nach wenigen Zyklen.

### TX-Offset

**`TARGET_TX_OFFSET = -0.8s` (`core/encoder.py`):**
```
0.5 (WSJT-X Protokoll) - 1.3 (FlexRadio TX-VITA-49-Buffer) = -0.8
```

FlexRadio puffert TX-Samples konstant 1.3s vor RF-Ausgabe. Audio
1.3s früher senden kompensiert das.

**Validiert:** 8 FT8-Zyklen 0.0s DT am Icom-Empfänger gemessen
(20m + 40m getestet).

### Persistierung

`~/.simpleft8/dt_corrections.json` mit Key-Format `"FT8_20m"`
(Modus_Band). Migration von altem Format `"FT8"` → `"FT8_20m"`
in `_load_for_current_key()` automatisch.

`set_band()` / `set_mode(mode, band)` lädt gespeicherten Wert
sofort beim Wechsel.

### Multi-Radio (P121 v0.98.04)

`TARGET_TX_OFFSET` ist FlexRadio-spezifisch. IC-7300/IC-7100-Forks
brauchen eigene `tx_buffer_s`-Klasse-Variable. Duck-Typing über
Radio-Klassen, **keine Vererbung** (FlexRadio erbt QObject nicht
RadioInterface).

---

## 7. Auto-Hunt Call-Validation (warum kommt „JA" nicht mehr als Call durch?)

**Kurzantwort:** Zwei Schichten — Parser-Fix erkennt CQ-mit-Richtung
auch ohne Grid, Auto-Hunt validiert Calls als Defense-in-Depth.

### Das Problem (P136 26.05.2026)

Mike's Field-Bug: Auto-Hunt rief „JA" aus `CQ JA HG60IPA` an → 5×
„Sende JA DA1MHH -17" → Timeout. Etikette-Verletzung.

Root Cause war ein **Parser-Bug** in `core/message.py:114`:

```python
# Alt: nur 4 Parts wurden als CQ-mit-Richtung erkannt
if f1 == "CQ" and len(parts) == 4 and not _looks_like_call(f2):
```

„CQ JA HG60IPA" hat **3 Parts** (kein Grid) → fiel durch → field2="JA"
→ `caller`="JA" → Auto-Hunt griff zu.

### Der Fix

**Schicht 1 — Parser** (`core/message.py:114`):
```python
if f1 == "CQ" and len(parts) >= 3 and not looks_like_callsign(f2):
    f1 = f"CQ {f2}"
    f2 = parts[2]
    f3 = parts[3] if len(parts) >= 4 else ""
```

Damit werden alle 3 typischen CQ-mit-Richtung-Formate korrekt
geparst:
- `CQ JA HG60IPA` → `caller`=HG60IPA, `field1`="CQ JA"
- `CQ DX DA1MHH` → `caller`=DA1MHH, `field1`="CQ DX"
- `CQ DX DA1MHH JN58` → `caller`=DA1MHH, `field3`="JN58"

**Schicht 2 — Auto-Hunt** (`core/auto_hunt.py` in `select_next`):

```python
base = max(call.split("/"), key=len) if "/" in call else call
if not looks_like_callsign(base):
    continue
```

Slash-tolerant via `max(split("/"), key=len)` — fängt `DA1MHH/P`,
`DA1MHH/QRP`, `DA1MHH/MM`.

### Die 3-Regel-Heuristik `looks_like_callsign`

`core/message.py:126` — Public-Funktion (P136 umbenannt aus
`_looks_like_call`).

| Regel | Beispiele die durchfallen | Beispiele die durchkommen |
|---|---|---|
| Länge 3-10 Zeichen | „JA", „EU", „NA", „DX" (zu kurz) | DA1MHH (6), HG60IPA (7) |
| ≥1 Ziffer | „CQ", „TEST", „QSO", „STATION" | 1A0KM, 4U1UN, R1A0KM |
| ≥1 Buchstabe | „123", „4567" | alle echten Calls |

**Sonderformate die korrekt durchkommen:**
- 1A0KM — Order of Malta
- 4U1UN — UN Geneva
- R1A0KM — Antarktis (hypothetisch)
- DA1MHH/P — Portabel (slash-tolerant)

**Was nicht abgefangen wird:**
- Synthetische Pseudo-Calls wie „RR73" (hat Ziffer + Buchstabe, formal
  valide). Praktisch irrelevant — `_recently_completed_qsos`-Cooldown
  oder `is_directed_to`-Filter fängt das ab.

---

## 8a. Debug-Log-Datei (für Bug-Diagnose nach dem Lauf)

**Kurzantwort:** Es gibt ein File-Logging-Framework (`core/debug_log.py`,
P21 10.05.2026) das **eine Datei pro Tag** schreibt mit zeitstempelten
Events. Ergänzend zur Live-Konsole (Sektion 4) — Konsole zeigt während
des Laufs, Datei kann man nach einem Bug retrospektiv durchgehen.

### Aktivieren

**Einstellungen → „Debug-Log schreiben"** (Häkchen). Wird persistiert.
- **Aus (Default):** No-op, **0 Performance-Kosten** (kein Disk-Write,
  kein File-Open).
- **An:** Eintrag in `~/.simpleft8/debug_YYYY-MM-DD.log` für jeden
  strategischen Code-Punkt.

### Format

```
HH:MM:SS.mmm [KATEGORIE] message
14:21:30.456 [HUNT] START band=20m mode=FT8 duration=600s
14:21:45.123 [HUNT] SELECT_NEXT msgs=8 qso_idle=True presence=True
14:21:45.124 [HUNT] SKIP call=K1ABC reason=recent_qso_cooldown age=42s
14:21:45.125 [HUNT] CANDIDATES pre_affinity n=3
14:21:45.126 [HUNT] PICKED call=DA1MHH score=75.0 snr=-12 tx_even=True
```

### Vorhandene Kategorien

| Kategorie | Was loggt sie | Eingeführt |
|---|---|---|
| `ANT` | Antennen-Switching (ANT1/ANT2-Kommandos) | P21 v0.96.8 |
| `BAND` | Bandwechsel-Pipeline-Schritte | P21 |
| `DIV` | Diversity-Phase-Übergänge, Pattern-Wechsel | P21 |
| `OMNI` | OMNI-CQ Lifecycle | P21 |
| `QSO-DONE` | Bisection-Debug bei „App hängt nach QSO" | P28 v0.96.x |
| **`HUNT`** | **Auto-Hunt: START, STOP, SELECT_NEXT, SKIP, PICKED, MARK_PICK, START_QSO, TX_STARTED** | **P139 v0.98.20** |

### Cleanup

Beim App-Start werden `debug_*.log`-Dateien älter als der Vortag
automatisch gelöscht (`cleanup_old_files(keep_days=1)`). Mike kann
also bedenkenlos an lassen — kein Disk-Spam.

### Typische Workflows

**Bug-Reproduktion gewünscht:**
1. Settings → „Debug-Log schreiben" AN
2. Bug provozieren (z.B. Auto-Hunt klicken, 60s warten)
3. App schließen
4. `~/.simpleft8/debug_2026-05-26.log` durchgehen (`grep HUNT` etc.)

**Code-Stelle hinzufügen:**
```python
from core.debug_log import debug_log
debug_log("KATEGORIE", f"event=... param={value}")
```
Try/except wrappen falls die Stelle kritisch ist (Crash-Schutz war
schon P21-Anforderung: „Debug darf NIE App crashen").

### Auto-Hunt-Diagnose-Beispiel (P139)

Bei „Auto-Hunt springt erst nach 60s an" → Log lesen:
- `SELECT_NEXT msgs=0` mehrfach → Decoder lieferte noch keine CQs
- `presence=False` → Totmannschalter blockt
- `SKIP reason=recent_qso_cooldown` → vorheriges QSO innerhalb 5min
- `CANDIDATES pre_affinity n=2 post_affinity n=0` → Slot-Affinität
  filtert alle weg (`last_tx_even` aus vorheriger Session noch gesetzt)

---

## 8. QSO-Ende-Blocker (warum verschwindet das 73 nach ✓?)

**Kurzantwort:** Nach „✓ QSO komplett" wird der Call 60 Sekunden lang
für ALLE Empf.-Einträge im QSO-Log blockiert — inklusive 73/RR73.
RX-Tabelle, Wasserfall und State-Machine bleiben unberührt.

### Mike-Spec-Historie (3 Iterationen an einem Tag)

| Datum | Bug/Spec | Code-Fix |
|---|---|---|
| 25.05.2026 P128 | Späte Reports/Grids tauchten nach ✓ noch im Log auf → Spam | 60s-Cooldown → alles blocken |
| 25.05.2026 P129 | 3 QSOs hintereinander ohne 73-Eintrag → P128 zu aggressiv | Whitelist: 73/RR73 trotz Cooldown durchlassen |
| 26.05.2026 P138 | 73 erschien NACH ✓ ins neue QSO hereinrutschend | Whitelist wieder raus — „beendet ist beendet" |

### Mechanik — wann wird geblockt?

Der Cooldown-Stempel wird **ausschließlich** in `_on_qso_complete`
(mw_qso.py:557) gesetzt — das ist exakt der ✓-Trigger-Zeitpunkt:

```python
self._recently_completed_qsos[qso_data.their_call] = time.monotonic()
```

Daraus ergibt sich automatisch das gewünschte 2-Zeitfenster-Verhalten:

| Zeitfenster | Cooldown-Eintrag? | 73/RR73 |
|---|---|---|
| **Vor ✓** (QSO läuft noch) | leer | kommt durch ✓ |
| **Nach ✓** (60s Fenster) | aktiv | wird geblockt ✗ |
| Nach 60s | gelöscht (lazy aging) | kommt wieder durch |

### Was wird geblockt, was nicht?

Filter sitzt **nur** in `on_message_decoded` direkt vor dem
`qso_panel.add_rx`-Aufruf (mw_cycle.py:810):

```python
if not self._p128_recently_completed_block(msg.caller):
    self.qso_panel.add_rx(...)  # nur geblockt, sonst alles wie immer
```

**Geblockt** (nach ✓):
- QSO-Log-Eintrag „← Empf. ..." (alle Message-Typen)

**Nicht geblockt:**
- `rx_panel.table` (RX-Liste links) — separater Pfad via
  `accumulate_stations` in `_handle_diversity_operate` /
  `_handle_normal_mode`
- Wasserfall / Frequency-Histogram
- State-Machine `on_message_received` — verarbeitet die Message ganz
  normal (z.B. CQ-Tracking, Locator-DB)
- PSK-Reporter / Karten-Snapshot — separater Datenpfad

### Konstanten

`core/timing.py` und `ui/mw_cycle.py`:
- `_RECENTLY_COMPLETED_BLOCK_S = 60.0` — Cooldown-Dauer
- Lazy-Aging: Eintrag > 60s wird beim nächsten Filter-Aufruf gelöscht
  (kein extra Timer)

### Field-Beispiel (Mike's Bilder 26.05.)

**Bild 2 (sauber):** Mike sendet RR73 → Gegenstation antwortet im
**selben Slot** mit 73 → `add_rx` rendert 73 (Cooldown noch leer) →
State-Machine triggert ✓ → Cooldown-Eintrag gesetzt → folgende
Empfänge geblockt.

**Bild 1 (Bug heute):** Mike sendet RR73 → State-Machine triggert ✓
sofort → Cooldown gesetzt → Gegenstation-RR73 kommt 1 Slot später →
**wird geblockt** (gewünschtes Verhalten).

### Reset-Pfade (Cooldown leeren)

- **Bandwechsel** (`_on_band_changed`): `_recently_completed_qsos.clear()`
- **Mode-Wechsel**: ebenso
- **Lazy-Aging** nach 60s pro Eintrag
- KEIN Reset bei HALT (Mike-Spec: HALT ist Notbremse, nicht QSO-Ende)

---

## Pflege dieser Datei

**Neue Sektionen** anhängen wenn:
- Funktion ist nicht-trivial (mehr als 1 Methode involviert)
- Erklärung wird vermutlich nochmal nachgefragt („wie war das nochmal
  mit X?")
- Code-Verständnis braucht Kontext den der Code allein nicht hergibt
  (Field-Bug-Historie, Mike-Spec-Entscheidungen, Trade-offs)

**Nicht hier dokumentieren:**
- Reine Code-Änderungen / Bugfixes → `HISTORY.md`
- Aktuelle TODO-Tickets → `TODO.md`
- Session-State → `HANDOFF.md`
- Architektur-Regeln → `CLAUDE.md`

**Format:** Sektion mit Nummer + Titel, Kurzantwort am Anfang,
Code-Pfade mit Datei:Zeile, Verlinkung zu HISTORY.md-Einträgen für
Detail-History.
