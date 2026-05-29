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

`ui/mw_cycle.py`:
```python
# DX: schwache Signale (SNR < -10, KEINE Untergrenze) pro Antenne
a1_weak = [m for m in a1_msgs if m.snr is not None and m.snr < -10]
a2_weak = [m for m in a2_msgs if m.snr is not None and m.snr < -10]
```

`a1_msgs`/`a2_msgs` enthalten **alle** decodierten Stationen pro Antenne
— da wird nichts entfernt. Nur die `a1_weak`/`a2_weak`-Untermenge
(SNR < -10 dB) fließt in die Antennen-Bewertung im Dx-Modus.

**Wichtig (P150-Synergie, 28.05.2026):** Der Filter hat **KEINE
Untergrenze** — nur `< -10`. Vor P150 (kMin_score=10) war das egal, weil
der Decoder kaum unter -20 dB lieferte. Seit P150 (kMin_score=4) kommen
auch -21..-27 dB Decodes durch, und die fließen **voll** in die DX-
Antennen-Bewertung ein. Das ist gewollt: DX jagt genau die schwachen
Signale, und eine -27 dB Station die nur auf EINER Antenne durchkommt ist
ein glasklarer „diese Antenne zieht das DX"-Datenpunkt. (Früherer Kommentar
sagte fälschlich „-20 < SNR < -10" — es gibt keinen -20-Boden.)

Im Gegensatz dazu: Diversity **Standard** (`core/diversity.py:compute_slot_score`)
filtert `> -20` — dort zählen die ganz tiefen NICHT (zu verrauschte
Antennen-Differenz bei Stärke-basierter Bewertung).

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

## 2. Auto-Hunt Defer-Familie (P81/P122/P124/P127/P128/P129/P126/P131/P138/P140/P144)

**Kurzantwort:** Wenn ein Hintergrund-Mechanismus etwas tun will
(Auto-Hunt stoppen, Log-Eintrag schreiben, Empfang blocken), aber das
gerade einen laufenden QSO stört, **wird die Aktion bis zum QSO-Ende
deferiert** statt sofort ausgeführt. Pattern-Familie mit aktuell 11
Iterationen. Variante: KISS-Defensive bei Kontextwechsel
(P127/P131/P126/P144 — encoder.abort + _pending_tx_log=None + cancel).

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

### Die 11 Iterationen

| # | Ticket | Was wird deferiert? | Wer triggert? |
|---|--------|---------------------|---------------|
| 1 | P81 (v0.97.53) | Auto-Hunt-Stop-**Meldung** im Log | `core/auto_hunt.py` |
| 2 | P122 (v0.98.05) | Auto-Hunt-Stop-**Aktion** selbst | 10-Min-Cap / 5-Min-Maus / 15-Min-Totmann |
| 3 | P124 (v0.98.06) | Hash-Call-**Resolution** (`<...>` → call) | Decoder im aktiven QSO-State |
| 4 | P127 (v0.98.08) | TX-Log-Eintrag bei SWR-Abbruch verwerfen | `_on_swr_alarm` |
| 5 | P128 (v0.98.07) | Empf.-Eintrag 60s nach QSO blocken | `on_message_decoded` Filter |
| 6 | P129 (v0.98.10) | P128-**Whitelist** für 73/RR73 (später wieder entfernt durch P138) | Korrektur an P128 |
| 7 | P126 (v0.98.12) | Send-nach-Timeout TX-Pipeline-Race-Fix | `_on_qso_timeout` (encoder.abort + _pending_tx_log=None) |
| 8 | P131 (v0.98.15) | Sende-Log bei Bandwechsel verwerfen | `_on_band_changed` |
| 9 | P138 (v0.98.19) | P129-Whitelist entfernt (Spec-Umkehr „beendet ist beendet") | Korrektur an P129 |
| 10 | P140 (v0.98.21) | Cooldown-Trigger umhängen (qso_complete → qso_confirmed_visual) | Korrektur an P138 |
| 11 | **P144 (v0.98.26)** | **Auto-Hunt-Target sendet an Fremd → Abort+Skip ohne Cooldown** | **`on_message_decoded` Filter (NEU)** |

**P144 Besonderheit:** Erstmals ein Filter der **VOR der State-Machine**
greift und das laufende QSO **abbricht** statt nur Hintergrund-Aktion zu
deferieren. Wenn Auto-Hunt-Target an Fremd-Call sendet (z.B. RR73 an
anderen QSO-Partner), brechen wir unsere TX-Versuche ab und überspringen
ohne Cooldown. Target bleibt für späteren Pick verfügbar.

```python
# ui/mw_cycle.py:on_message_decoded — zwischen P124 und P94/OMNI/SM
if self._p144_target_busy_with_other(msg):
    self._p144_abort_and_skip(target=..., busy_with=msg.target)
    return

# Filter-Bedingungen (alle MÜSSEN gelten):
# - Auto-Hunt aktiv UND nicht manual_override
# - State-Machine in aktivem QSO (qso.their_call gesetzt)
# - msg.caller == qso.their_call (unser Target sendet)
# - msg.target != my_call (nicht Antwort an uns)
# - not msg.is_cq (neuer CQ wäre OK, Target ist wieder frei)
```

**Neue API `core/auto_hunt.py:clear_current_target()`** — setzt nur
`_current_target = None` ohne Cooldown (Pattern-Unterschied zu
`on_qso_complete`/`on_qso_timeout` die jeweils 5-Min-Cooldown setzen).

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

### Mike-Spec-Historie (4 Iterationen an einem Tag)

| Datum | Bug/Spec | Code-Fix |
|---|---|---|
| 25.05.2026 P128 | Späte Reports/Grids tauchten nach ✓ noch im Log auf → Spam | 60s-Cooldown → alles blocken |
| 25.05.2026 P129 | 3 QSOs hintereinander ohne 73-Eintrag → P128 zu aggressiv | Whitelist: 73/RR73 trotz Cooldown durchlassen |
| 26.05.2026 P138 | 73 erschien NACH ✓ ins neue QSO hereinrutschend | Whitelist wieder raus — „beendet ist beendet" |
| 26.05.2026 P140 | P138 setzte Cooldown an `qso_complete` (interner RR73-Send) statt `qso_confirmed_visual` (optisches ✓) — 73 vor ✓ wurde fälschlich geblockt | Cooldown umgehängt + symmetrisch in Timeout-Pfad |

### ⚠ Zwei getrennte QSO-Ende-Trigger (P140 26.05.2026)

Die State-Machine emittiert **zwei verschiedene** Signale beim QSO-Ende:

| Signal | Wann es feuert | Was es triggert |
|---|---|---|
| `qso_complete` | **sofort** beim eigenen RR73-Send | interner Cleanup: ADIF-Schreiben, Auto-Hunt-Pause, `_active_qso_targets.discard` |
| `qso_confirmed_visual` | nach Empfang des 73 (oder Courtesy-73-fertig) | **optisches** ✓: `qso_panel.add_qso_complete` rendert „✓ QSO komplett" |

Zwischen den beiden Signalen können **mehrere Slots** liegen (Mike-
Field-Bug 26.05.: ~30-45 s typisch). In dieser Zeit kommt das 73
der Gegenstation an.

### Mechanik — wann wird geblockt? (P140-Update)

Der Cooldown-Stempel wird in **zwei** Stellen gesetzt:

1. **`_on_qso_confirmed_visual`** (mw_qso.py:660+) — optisches ✓-Zeitpunkt
2. **`_on_qso_timeout`** (mw_qso.py:980+) — defensiv nach ✗ (Mike-Spec
   „beendet ist beendet" auch nach scheiterndem QSO)

```python
# _on_qso_confirmed_visual:
self.qso_panel.add_qso_complete(qso_data.their_call)  # ✓ zuerst
import time as _t
if qso_data.their_call:
    self._recently_completed_qsos[qso_data.their_call] = _t.monotonic()
```

**Was wichtig ist:** Cooldown wird **NACH** `add_qso_complete` gesetzt
— sonst Spec-Verstoss (gleicher Bug wie P138 wieder).

`_on_qso_complete` (interner Trigger) setzt **KEINEN** Cooldown mehr —
nur State-Cleanup. Falls jemand denkt „das war doch früher anders":
ja, P138 → P140 hat das umgehängt.

Daraus ergibt sich das gewünschte 2-Zeitfenster-Verhalten:

| Zeitfenster | Cooldown-Eintrag? | 73 der Gegenstation |
|---|---|---|
| RR73-Send (= `qso_complete`) | leer | wird gerendert ✓ |
| Optisches ✓ (= `qso_confirmed_visual`) | wird gesetzt | — |
| **Nach ✓** (60 s Fenster) | aktiv | wird geblockt ✗ |
| Nach 60 s | gelöscht (lazy aging) | kommt wieder durch |
| Nach ✗ Timeout (= `qso_timeout`) | wird gesetzt | gleiche Block-Regel |

### Auto-Hunt-Cooldown ist UNABHÄNGIG (R1-F1-Klärung P140)

`core/auto_hunt.py` hat einen **eigenen** Cooldown-Mechanismus
`_recent_qso` (P61, gesetzt via `mark_pick()`) der **unabhängig** von
`_recently_completed_qsos` ist. Auto-Hunt wird also dieselbe Station
NICHT erneut picken, auch wenn der Log-Filter-Cooldown nicht greift
(P140 nutzt diese Trennung aus). Test T6 in
`test_p140_cooldown_trigger.py` verifiziert die Unabhängigkeit.

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
- **Lazy-Aging** nach 60 s pro Eintrag
- KEIN Reset bei HALT (Mike-Spec: HALT ist Notbremse, nicht QSO-Ende)

### Field-Beispiel (Mike 26.05. P140-Fix verifiziert)

```
14:32:15 → Gesendet 5P1KZX DA1MHH -18       ← Mike-TX
14:32:30 ← Empf. DA1MHH 5P1KZX R-12         ← Gegenstation-R-Report
14:32:45 → Gesendet 5P1KZX DA1MHH RR73      ← qso_complete (intern)
                                              VOR P140: Cooldown HIER → 73 weg
                                              NACH P140: kein Cooldown
14:33:15 ← Empf. DA1MHH 5P1KZX 73            ← Gegenstation-73
                                              VOR P140: GEBLOCKT
                                              NACH P140: durchgelassen ✓
         ✓ QSO mit 5P1KZX komplett          ← qso_confirmed_visual
                                              NACH P140: Cooldown HIER
14:33:30 → Gesendet CQ DA1MHH JN58           ← nächster CQ
14:33:45 ← Empf. DA1MHH 5P1KZX 73           ← später-73 von 5P1KZX
                                              wird geblockt ✗ (60 s)
```

---

## 9. Bandsperre + TUNE-Pipeline (P53/P63/P54/P76-A)

> **⚠ P119-Update (29.05.2026):** Die unten beschriebene **Phase B
> (10W-Einpendeln)** ist ENTFERNT. Die Pipeline ist jetzt: Phase A
> (Tuner-Match) → SWR-Freeze (`_compute_match_swr`) → tune_off → 2s-Post-Check
> → Band-Freigabe/-Sperre. **Die SWR-Sicherheit ist unverändert** (der Freeze
> lief schon immer VOR Phase B). Phase-B-Erwähnungen unten = historischer
> Kontext. Details: §16.

**Kurzantwort:** Bei zu hohem SWR während TX wird das aktuelle Band
**markiert** (in-Memory `set`). Solange der Marker gesetzt ist, ist
TX auf diesem Band gesperrt — Auto-Hunt, OMNI-CQ, CQ, Hunt-Reply,
sogar Bandwechsel zum gesperrten Band führen TX nicht aus. Nur ein
manueller TUNE-Vorgang mit SWR ≤ Limit kann den Marker entfernen.

### Wer/wann setzt den Marker?

`ui/mw_tx.py:_on_swr_alarm` (Z. 689 ff) — der Live-SWR-Watchdog.

| Trigger | Bedingung | Code-Pfad |
|---|---|---|
| Live-Alarm während TX | **2 Alarms innerhalb 500 ms** + `encoder.is_transmitting=True` + `tuner_present=True` | `mw_tx.py:771-772` |
| Pre-TX-Alarm aus `ptt_on()` | wird ignoriert (Spike-Schutz) | `mw_tx.py:716-718` |
| Während manuellem TUNE | komplett bypassed (kein Marker) | `mw_tx.py:712-713` |
| Auto-TUNE nach Bandwechsel scheitert | Marker proaktiv gesetzt | `mw_tx.py:447-449` |

**SWR-Limit:** `settings.get("swr_limit", 3.0)` — User-konfigurierbar in
Einstellungen → „TX & Schutz" → „SWR-Limit". Mike's typischer Wert: 3.0.

**Wenn `tuner_present=False`:** kein Marker gesetzt → klassisches
„Antenne prüfen"-Modal ohne Sperre. Use-Case: Mobil-Betrieb ohne
Tuner.

### Die Daten-Struktur

```python
self._swr_blocked_bands: set[str]  # in MainWindow.__init__
```

In-Memory **set von Band-Strings in Upper-Case** (`"15M"`, `"20M"`...).
**Nicht persistiert** — App-Neustart räumt den Marker automatisch ab
(Mike-Logik: nach Neustart kommt eh der erste TX-Versuch mit Watchdog,
falls Antenne immer noch defekt rastet die Sperre sofort wieder ein).

### Wer respektiert den Marker (TX-Blocker)?

Alle TX-auslösenden Pfade prüfen `band in self._swr_blocked_bands`
**bevor** Hardware angesprochen wird:

| Datei:Zeile | Pfad | Aktion bei Sperre |
|---|---|---|
| `mw_radio.py:643` | Bandwechsel-Hint (Antennen-Auswahl) | Hint übersprungen |
| `mw_radio.py:662` | Bandwechsel-Diversity-Apply | übersprungen |
| `mw_radio.py:1575` | Bandwechsel-Pipeline (Auto-TUNE-Trigger) | Auto-TUNE ausgelöst |
| `mw_radio.py:1742` | RX-Mode-Switch | TX-Aktionen geblockt |
| `mw_radio.py:1798` | Reverse-Sync von Settings | Marker re-add |
| `mw_qso.py:177` | `_on_tx_started` Pre-Check | TX abgebrochen |
| `mw_qso.py:338` | Hunt-Reply | Reply unterdrückt |
| `mw_qso.py:507` | `start_qso`-Aufruf | QSO verhindert |

**Was wird NICHT geblockt:**
- RX-Decoder, Wasserfall, Karte, Stats — kein TX, kein Risiko
- Manueller TUNE-Klick — ist der einzige Weg zur Freigabe
- HALT (Notbremse) — Stop ist sowieso kein TX-Trigger

### Wer/wann entfernt den Marker (Freigabe)?

**Ausschließlich** `_tune_post_swr_check` (`mw_tx.py:310`) bei SWR ≤
Limit nach manuellem TUNE-Vorgang:

```python
if swr_now <= swr_limit:
    was_blocked = band in self._swr_blocked_bands
    self._swr_blocked_bands.discard(band)
    ...
    if was_blocked:
        self.qso_panel.add_info(f"✓ Band {band} freigegeben — SWR {swr_now:.1f}")
```

**Es gibt KEINEN anderen Discard-Pfad.** Bandwechsel weg/hin entfernt
den Marker NICHT (Mike-Spec: Antenne ist immer noch defekt).

### Die TUNE-Pipeline (3 Phasen + Post-Check)

Wenn der User TUNE drückt (oder Auto-TUNE bei Bandwechsel startet):

```
PHASE A (Tuner-Match)
  ├─ radio.set_tx_antenna("ANT1")                ← Hardware-Safety
  ├─ radio.set_rfpower_direct(10)                ← 10 W Träger
  ├─ radio.tune_on()                             ← FlexRadio-Tuner-Match
  ├─ SWR-Ticks sammeln (P153) → _tune_swr_samples[(elapsed, swr)]
  └─ tune_duration_s warten (default 15 s)
                ↓
SWR-FREEZE (P142 27.05. + P153 28.05.2026)         ← NACH Phase A, VOR Phase B
  └─ swr_after_match = _compute_match_swr()       ← MEDIAN über [Dauer-3s, Dauer-1s]
     _tune_last_valid_swr = swr_after_match       ← robust gegen Snapshot-Ausreißer
     (< 3 Samples ODER kein Wert → None → Band bleibt gesperrt)
                ↓
PHASE B (Closed-Loop Power-Konvergenz)            ← OPTIONAL
  ├─ Vor-Check: swr_after_match ≤ swr_limit ?
  │     NEIN → Phase B SKIP, _tune_converged_rf = None
  │     JA  → weiter
  ├─ 5 Iterationen á 1 s:
  │     – FWDPWR-Samples sammeln
  │     – Proportional rfpower-Slider anpassen
  │     – Ziel: FWDPWR ≈ 10 W (±1 W Toleranz)
  └─ Konvergenz-Ergebnis: rf-Wert (Stützpunkt für späteren rf_preset)
                ↓
TUNE-OFF
  ├─ radio.tune_off()
  ├─ VFO zurück auf Work-Frequency
  ├─ power_preset wiederherstellen
  └─ TUNE-Button visuell zurücksetzen
                ↓
POST-CHECK (2 s später)
  ├─ token-validation (Re-Tune-Race-Schutz)
  ├─ swr_now = _tune_last_valid_swr (eingefroren VOR Phase B)
  ├─ if swr_now ≤ swr_limit:
  │     ✓ Marker discard + Diversity-Resume (wenn aktiv)
  │     ✓ rf_preset_store.save bei plausiblem rf-Wert
  │     ✓ qso_panel.add_info("✓ Band X freigegeben — SWR Y.Z")
  └─ if swr_now > swr_limit:
        ✗ Marker setzen (Phase-B-Schicht reicht)
        ✗ Modal „Tuner konnte nicht matchen"
```

### Warum die 2-Sekunden-Verzögerung im Post-Check?

`mw_tx.py:294`: `QTimer.singleShot(2000, lambda: self._tune_post_swr_check(...))`

Nach `tune_off()` braucht FlexRadio kurz, bis die letzten VITA-49
Meter-Updates durch sind. 2 s ist empirisch genug für saubere Werte.
Token-Pattern (`_tune_post_check_token`) schützt vor Race bei
schnellem Re-Tune (User klickt TUNE 2×).

### Bekannte Stolperfalle 1: Clamp-Bug ohne Träger / während Phase-B

Nach `tune_off()` liefert FlexRadio weiterhin Meter-Updates **ohne TX-
Träger** — Werte < 1.0 die in `_handle_meter` auf 1.0 geclamped werden
und `radio._last_swr` überschreiben. **Zusätzlich** clampt der Sensor
**während Phase B**, wenn die rfpower-Regelung den Träger
runterdrückt → SWR scheint auf 1.0 zu fallen obwohl die echte
Match-Last unverändert ist.

Deshalb wird der Match-SWR **direkt nach Phase A** (vor Phase B und
vor `tune_off()`) eingefroren — das ist der
einzige Zeitpunkt mit verlässlich vollem 10-W-Träger an der Antenne.
Vorher (vor P142, 27.05.2026) wurde der Freeze nach Phase B genommen
→ false-OK 1.0 bei defekter Antenne.

### Bekannte Stolperfalle 4: Snapshot-Ausreißer (P153, 28.05.2026)

P142 zog den Freeze auf „direkt nach Phase A" — aber genau dort
**schwankt der SWR-Stream am stärksten** (ATU gerade fertig, Sensor
rauscht, periodische Nachregelung). Ein **einzelner** Snapshot
(`radio.last_swr`) erwischt dann leicht einen Ausreißer-Tick.

**Mike-Field-Bug 28.05.:** Tuner stabil bei 2,5, aber der Snapshot
fror einen 4,0-Spike ein → Band fälschlich gesperrt. 2. TUNE traf
zufällig einen guten Moment (2,3). P148 machte es sichtbar (Anzeige
hält letzten echten Wert statt auf 1,0 zu springen).

**Fix (P153):** Statt Snapshot → **Median über Fenster [Dauer-3s,
Dauer-1s]** (`_compute_match_swr()`). Das Fenster schließt die Match-
Suchphase (SWR fällt von hoch) UND die Übergangs-Sekunde vor tune_off
aus. Median filtert einen einzelnen Spike in beide Richtungen.

**Hardware-Sicherheit (R1-V4-pro):** < 3 Samples im Fenster → `None`
(nicht aussagekräftig). KEIN Fallback auf `radio.last_swr` (= Snapshot-
Bug zurück). `None` → Post-Check FAIL → Band bleibt gesperrt. Lieber
nochmal TUNEN als falsche Freigabe.

`_tune_stop` nutzt `if swr_after_match is not None and swr_after_match
<= swr_limit` — expliziter None-Check (NICHT `None <= limit`, das ist
Python-`TypeError`).

### Bekannte Stolperfalle 2: Disconnect-Pfad

`mw_tx.py` — wenn das Radio während Post-Check disconnected ist, wird
`_tune_last_valid_swr = None` reset (Stale-Schutz) und Auto-TUNE-
Dialog erhält `auto_tune_done.emit(False, 0.0, 0.0)`.

### Bekannte Stolperfalle 3: User-Cancel während Phase B

Wenn der User TUNE erneut drückt **während** die Phase-B-Konvergenz
läuft, greift die Re-Entry-Sperre `_tune_stop_active=True`. Sie setzt
nur `_tune_convergence_cancelled = True` und return — würde aber den
bereits gesetzten Phase-A-Freeze durchreichen → Post-Check sieht
einen "gültigen" Wert → fälschliche Band-Freigabe trotz Abbruch.

**Fix (P142 R1-Catch):** Re-Entry-Sperre invalidiert den Freeze
explizit: `_tune_last_valid_swr = None`. Damit fällt der Post-Check
hart aus → Band bleibt gesperrt → Hardware sicher.

### Konstanten + Settings

| Wert | Wo | Default |
|---|---|---|
| `swr_limit` | `settings.swr_limit` | 3.0 |
| `tune_duration_s` | `settings.tune_duration_s` | 15 s |
| `tune_power_w` | `radio.tune_power_w` Class-Var | 10 W (hartcodiert, kein Settings-Override aus Hardware-Safety) |
| `tuner_present` | `settings.tuner_present` | True |
| Phase-B Iterationen | `_tune_converge_to_target` Param | 5 × 1 s |
| Phase-B Toleranz | `TOLERANCE_W` | ±1 W |
| Phase-B Min-Samples | `MIN_SAMPLES` | 2 |
| Post-Check Verzögerung | `QTimer.singleShot` Param | 2000 ms |
| SWR-Spike-Fenster | `_swr_first_alarm_t` ± | 500 ms |
| `rf_preset_store` plausibel-Bereich | `mw_tx.py:393` | rf ∈ [3, 50] |

### Field-Beispiel (Mike 26.05. 17:24)

```
QSO-Log:
  ⚠ Band 15M gesperrt — SWR 28.5      ← P63 Sperre (Antenne defekt)
  ✓ Band 15M freigegeben — SWR 1.0    ← Meldung mit falschem SWR
  ✓ TUNE OK — SWR 2.5                  ← 2. TUNE im freigegebenen Band

Radio-Widget:
  Erster TUNE:  11 W / SWR 2.5         ← echter Live-Wert
  Zweiter TUNE: 0 W / SWR 1.0          ← idle, kein TX
```

→ Die App nimmt einen echten, aber falschen Wert (1.0 aus Phase-B-
Power-Down). Behebung in P142.

### Verwandte Dateien

- `ui/mw_tx.py` — Hauptlogik (TUNE-Pipeline + SWR-Alarm + Post-Check)
- `ui/mw_radio.py` — Bandwechsel-Hooks, Auto-TUNE-Trigger
- `ui/mw_qso.py` — TX-Pre-Checks
- `core/preset_store.py` — RFPreset-Stützpunkt-Speicher (Phase-B-Output)
- `radio/flexradio.py:1388` — SWR-Watchdog-Signal-Emitter

### Verwandte HISTORY-Einträge

- P53 (v0.97.x) — Live-SWR-Watchdog während TX
- P54 (v0.97.44) — Closed-Loop Power-Konvergenz Phase B
- P63 (v0.97.36) — Marker + Modal + Diversity-Resume
- P76-A/B/C (v0.97.49+50) — Freeze-vor-Tune-Off + Auto-TUNE-Dauer-UX
- P127 (v0.98.08) — `_pending_tx_log` Reset bei SWR-Stop

---

## 10. QSO-Log Zwei-Speicher-Architektur + Clear-Pfade (P95/P143)

**Kurzantwort:** Das QSO-Log hat **zwei** Speicher die synchron
gehalten werden müssen. Wer nur einen leert holt sich Resurrection-
Bugs ein. Helper `qso_panel.clear_log_completely()` macht's richtig.

### Die zwei Speicher

| Speicher | Wofür | Eingeführt |
|---|---|---|
| `log_view` (QPlainTextEdit) | sichtbares Widget | seit immer |
| `_entries: list[dict]` | Master-SOT für Re-Render | P95 v0.97.67 |

`_entries` wurde mit P95 eingeführt um **Visibility-Toggles** zu
unterstützen (Even/Odd-Tag ein/ausblenden, Antennen-Label
ein/ausblenden) ohne Re-Decode aus Audio. `_rerender_all()` zeichnet
log_view komplett neu aus `_entries`.

### Der Trigger der Bugs verursacht

`_cleanup_timer` (Z. 54 in qso_panel.py) läuft alle **30 Sekunden**
und ruft `_auto_trim_by_age(max_age_s=300.0)`:
- entfernt Einträge älter als 5 Min aus `_entries`
- ruft `_rerender_all()` wenn was getrimmt wurde (≥ 5 alte Einträge)
- → zeichnet log_view aus aktuellem `_entries` neu

**Wenn jemand nur `log_view.clear()` aufruft**, aber `_entries`
bleibt voll: nach maximal 30 s zeichnet der Auto-Trim-Timer alle
„geleerten" Einträge wieder ins log_view. Mike-Field-Bug 26.05.
17:34 (30m → 20m Bandwechsel).

### Der Helper

`qso_panel.clear_log_completely()` (vor `_append_colored`):

```python
self._entries.clear()
self.log_view.clear()
self._last_omni_tx_even = None
```

**Reihenfolge: Daten → View → State** (R1-F1 26.05.).
**Thread-safe ohne Lock** (alle Aufrufer + Cleanup-Timer im
GUI-Thread, Qt single-threaded queue, R1-F2).

### Wo der Helper AUFGERUFEN wird (Mike-Spec 26.05.)

| Pfad | Wann | Warum leer |
|---|---|---|
| `mw_radio._on_band_changed` | Bandwechsel | neuer Band-Kontext |
| `mw_radio._on_mode_changed` | FT8↔FT4-Wechsel | Stationen senden in anderem Modus, kein Bezug mehr |
| `mw_radio._on_rx_panel_toggled` | RX-On/Off-Toggle | Neustart-Charakter |

### Wo der Helper NICHT aufgerufen wird (P115-Spec)

| Pfad | Wann | Warum NICHT leer |
|---|---|---|
| `set_rx_mode` / `_on_rx_mode_clicked` | Normal↔Diversity-Switch | P115-Spec: optische Kontinuität, Chronik bleibt sichtbar |

### Die OMNI-Parity-Falle

`_last_omni_tx_even` (qso_panel.py:61) trackt die Even/Odd-Parity
des letzten OMNI-TX-Eintrags um Leerzeilen-Trennung bei Parity-
Wechsel zu setzen. **Wer log_view ohne diesen Reset leert** bekommt
nach Bandwechsel eine falsche Trennung (Parity-Wert vom alten Band).
Helper resettet das mit (R1-F3).

### Field-Beispiel (Mike 26.05. 17:34, vor P143-Fix)

```
30m: Auto-Hunt sendet
  → Gesendet BG4UCZ DA1MHH -15      (_entries[0])
  → Gesendet R9AL DA1MHH -15        (_entries[1])
  → Gesendet MW0DNF DA1MHH -17      (_entries[2])

User klickt 20m:
  _on_band_changed → log_view.clear()   # _entries BLEIBT [0,1,2]
  → Mike sieht: leer

~30 s später Auto-Trim-Timer:
  _auto_trim_by_age → _rerender_all()
  → for entry in _entries: render(entry)
  → log_view zeigt BG4UCZ/R9AL/MW0DNF wieder
  → Mike sieht: 30m-Einträge auf 20m wieder da
```

Nach P143-Fix ruft `_on_band_changed` `clear_log_completely()`
das `_entries.clear()` mit aufruft → kein Resurrection.

### Verwandte Konstanten

- `_cleanup_timer` Intervall: **30 Sekunden** (qso_panel.py:55)
- `_auto_trim_by_age` Max-Age: **300 Sekunden** = 5 Min
  (qso_panel.py:562)
- Min-Trim-Schwelle: ≥ 5 alte Einträge nötig damit Re-Render läuft
  (R1-F5 Early-Exit-Schutz)

### Tests die das absichern

`tests/test_p143_clear_log_completely.py`:
- T1: Helper leert alle 3 States (echter Lifecycle-Test)
- T2a/b/c: 3 Aufrufer rufen Helper (Source-Inspektion)
- T3: rx_mode-Switch-Pfade rufen Helper NICHT (P115-Schutz)
- T4: Mike-Field-Bug-Reproduktion (Resurrection-Schutz)
- T5: Reihenfolge Daten→View→State
- T6: Docstring P115-Hinweis vorhanden
- T7: Idempotenz

`tests/test_p131_band_change_pending_tx_log.py::test_t2` verwendet
`clear_log_completely()` als Anker (P143-Migration-fest).

---

## 11. Mode-aware Symmetrie-Pattern (P102/P114/P135/P141)

**Kurzantwort:** Wenn die App zwei oder mehr parallele Pfade hat
(Normal vs Diversity, FT8 vs FT4, ...), MÜSSEN alle Control-Panel-
Updates symmetrisch in jedem Pfad gerufen werden. Vergessen in einem
Pfad → stale-Anzeige-Bug. Bisher 4 Iterationen gefunden — wahrscheinlich
gibt's noch mehr.

### Bekannte Iterationen

| # | Ticket | Was wurde vergessen | Pfad wo es fehlte |
|---|---|---|---|
| 1 | P102 (v0.97.97) | `_refresh_antenna_status_label()` | User-Klick-Pfad `_on_rx_mode_clicked` (vs programmatischer `set_rx_mode`) |
| 2 | P114 (v0.97.99) | `_refresh_modeband_status_label()` | nur in einer der set-Methoden |
| 3 | P135 (v0.98.16) | mode-aware Decode-Count | `_on_cycle_decoded` Slot-Parity |
| 4 | **P141** (v0.98.23) | `compute_local_conditions` + `update_local_conditions` | `_handle_diversity_operate` (vs `_handle_normal_mode`) |

### Anatomie des Bugs

```python
def _handle_normal_mode(self, messages):
    ...
    # Sterne-Anzeige
    score, n_st, median = compute_local_conditions(self._normal_stations)
    self.control_panel.update_local_conditions(score, n_st, median)
    self._emit_map_snapshot_if_open()

def _handle_diversity_operate(self, messages, ant):
    ...
    # ← HIER FEHLTE der Sterne-Update bis P141 (27.05.2026)
    self._emit_map_snapshot_if_open()
```

User schaltet auf Diversity-Mode → Sterne-Anzeige hängt auf
1★ (Init-Default) oder dem letzten Normal-Mode-Wert. Kein Crash,
kein Log-Fehler, einfach „komische Anzeige".

### Wie der Bug entdeckt wird

Mike sieht im Feld einen Wert der nicht zu den Daten im
Empfangsfenster passt (z.B. „14 Stationen mit -18 dB Median →
zeigt nur 1★?"). Mike fragt nach. Wir finden den fehlenden Aufruf.

### Wo sonst noch Risiko besteht (zu prüfende Stellen)

| rx_mode-aware Funktion | Bereits in beiden Pfaden? |
|---|---|
| `update_decode_count` | ✅ P135 |
| `update_snr` | ⚠ nur in Normal-Mode (Diversity berechnet `_avg_snr` lokal aber ruft `update_snr` nicht — TODO prüfen) |
| `update_diversity_counts` | ✅ nur Diversity (Per-Definition) |
| `update_local_conditions` | ✅ P141 |
| `_refresh_antenna_status_label` | ✅ P102 |
| `_refresh_modeband_status_label` | ✅ P114 |
| `_emit_map_snapshot_if_open` | ✅ beide Pfade |

### Empfehlung für die Zukunft

DeepSeek-R1 hat 27.05.2026 vorgeschlagen ein **Pattern-Check-Skript**
zu bauen (siehe TODO P145 falls eingetragen) das:
1. Alle Stellen findet die `_rx_mode` abfragen
2. Pro Branch alle Control-Panel-Update-Aufrufe extrahiert
3. Asymmetrien meldet (Methode X in Branch A, fehlt in Branch B)
4. Als Pre-Commit-Hook läuft

Aufwand klein, Nutzen hoch — würde diese Bug-Klasse abhaken.

### Trigger für neue Iteration

Sobald jemand einen neuen `_handle_*_mode`-Pfad einbaut (z.B. für
einen neuen rx_mode oder Sondermodus), MUSS er die Symmetrie-Tabelle
oben aktualisieren und alle bekannten Updates spiegeln. Sonst kommt
Mike mit „komische Anzeige" zurück und es wird P14X.

### Verwandte Tests

- `tests/test_p141_diversity_local_conditions.py::test_t2` —
  Symmetrie-Test (beide Handler MÜSSEN `compute_local_conditions`
  rufen)
- `tests/test_p135_*` — Decode-Count-Symmetrie

---

## 12. Pattern-Klasse Hardware-Sicherheit (P53/P76-A/P142/P153/P154/P159)

**Pattern-Frage:** Wie schützt SimpleFT8 die FlexRadio-Hardware (PA,
Antennen-Pfad) vor TX an defekter Last?

**Antwort:** Sechs aufeinander aufbauende Schichten — jede neue
Iteration verstärkt die vorigen ohne sie zu brechen. SWR-Werte werden
an zeitlich gestaffelten Punkten geprüft, jeder Punkt setzt
einen anderen Marker bzw. greift einen anderen Race ab.

### Die 5 Schichten (chronologisch)

| Schicht | Wo | Wann eingebaut | Was sie tut |
|---|---|---|---|
| **P53 SWR-Live-Watchdog** | `mw_tx._on_meter_update` | v0.97.29 (14.05.2026) | Liest `radio._last_swr` aus VITA-49-Meter-Stream. Setzt `_swr_blocked_bands`-Marker live wenn SWR > limit während TX. **Schutz bei plötzlicher Antennen-Defekt mitten in QSO** (Steckverbinder lose, Wetter-Einfluss). |
| **P76-A SWR-Freeze vor tune_off** | `mw_tx._tune_stop` | v0.97.49 (19.05.2026) | Friert `_tune_last_valid_swr` VOR `tune_off()` ein. **Schutz vor Clamp-1.0 nach Träger-Aus** (Stolperfalle 1, ohne-Träger-Branch). |
| **P142 SWR-Freeze vor Phase B** | `mw_tx._tune_stop` | v0.98.29 (27.05.2026) | Friert `_tune_last_valid_swr` schon VOR Phase B. **Schutz vor Clamp-1.0 während Power-Down** (Stolperfalle 1, Phase-B-Branch). |
| **P153 Median statt Snapshot** | `mw_tx._compute_match_swr` | v0.98.34 (28.05.2026) | Der Freeze nimmt nicht mehr EINEN Snapshot, sondern den **Median über [Dauer-3s, Dauer-1s]**. **Schutz vor Snapshot-Ausreißer** (Stolperfalle 4) — P142 zog den Freeze-Zeitpunkt in die instabile Post-Match-Phase, ein Einzel-Tick erwischte dort leicht einen Spike (Mike-Bug: 2,5 stabil, 4,0 eingefroren). <3 Samples → None → Band gesperrt. |
| **P154 Median-Init in ALLEN TUNE-Pfaden** | `mw_tx._init_tune_swr_sampling` (von `_tune_start` + beiden Auto-TUNE-Pfaden gerufen) | v0.98.36 (28.05.2026) | P153 baute die Sample-Sammlung NUR in `_tune_start` (manueller TUNE) ein. Die zwei Auto-TUNE-Pfade (`_start_auto_tune_for_band_change`, `_start_dialog_tune_sequence`) haben eigenes Setup ohne `_tune_start` → `_tune_start_time` STALE → Median-Fenster griff ins Leere (Mike-Bug: „8.7 gesperrt", real 1.4, nur manueller TUNE OK). **Schutz: zentraler Helper, von ALLEN TUNE-Pfaden gerufen** — Zwillings-Bug-Klasse wie P133/P134. |
| **P159 Clamp-1.0-Werte aus Median filtern** | `mw_tx._compute_match_swr` | v0.98.41 (28.05.2026) | Der FlexRadio-Sensor clampt bei fehlendem Träger (FWDPWR≈0) HART auf **exakt 1.0** (`flexradio.py: if swr<1.0: swr=1.0`). Diese künstlichen 1.0-Werte landeten im Median-Fenster und zogen den Median runter → Band fälschlich freigegeben (Mike-Bug field-belegt 14:52: 14 echte 2.5-2.6 + 19 Clamp 1.0 → median=1.00). **Schutz: `swr > 1.0`-Filter im Fenster** — verschiebt Median nach oben (sichere Richtung); nur-Clamp-Fenster → <3 echte → None → gesperrt. Echte KW-SWR sind nie exakt 1.0 (nur Dummy-Load; bester realer Wert ~1.2). Erkennungsmerkmal: echte Werte streuen, Clamp ist immer glatt 1.0. |

### ⚠ Stolperfalle (P154): Auto-TUNE-Pfade dürfen NICHT `_tune_start` umgehen ohne den Median-Helper

Es gibt **drei** Pfade die TUNE-Hardware starten und später `_tune_stop`
→ `_compute_match_swr` (Median-Fenster) nutzen:
1. `_tune_start` (mw_tx) — manueller TUNE-Knopf
2. `_start_auto_tune_for_band_change` (mw_tx) — Bandwechsel-Auto-TUNE
3. `_start_dialog_tune_sequence` (mw_radio) — DXTuneDialog-TUNE

**JEDER** dieser Pfade MUSS `self._init_tune_swr_sampling(duration_s)` rufen
(VOR `_tune_active = True`, sonst Mini-Race im `_on_meter_update`-Guard).
Sonst sammelt `_on_meter_update` mit veralteter `_tune_start_time` →
`_compute_match_swr` liefert Müll. **Wenn ein 4. TUNE-Start-Pfad gebaut
wird: Helper-Aufruf nicht vergessen.** (Der Gain-Mess-TUNE
`_start_dx_tuning._after_tune` ist KEIN solcher Pfad — er nutzt noch
`radio.last_swr`-Snapshot direkt, siehe TODO P155.)

### Warum kumulativ statt ersetzend?

Jede Schicht deckt ein anderes Zeit-Fenster ab:

```
TUNE-Start ───── Phase A (15s, voller Träger) ───── Phase B (5s, Power-Drop) ───── tune_off ───── Post-Check (2s) ───── QSO-TX
                                                                                                                          │
                       ↑ P142 Freeze hier (echter Match-SWR)                                                              │
                                                                                                                          │
                                                                  ↑ P76-A Freeze hier (last Match vor tune_off)            │
                                                                                                                          │
                                                                                                                          ↑ P53 Watchdog läuft DAUERHAFT
```

- **P53** läuft die ganze Zeit (jeder Meter-Push) — auch im QSO-TX
  nach erfolgreichem TUNE-Cycle.
- **P76-A** und **P142** schützen den TUNE-Cycle selbst. P76-A war
  notwendig weil ohne Träger 1.0 geclamped wird. P142 war notwendig
  weil Phase B den Träger runterregelt → gleicher Clamp-Effekt
  während gewollter Power-Reduktion.

**Wenn man P142 ohne P76-A bauen würde:** Funktion theoretisch identisch
(Freeze ist eh früher), aber 2 Code-Pfade je nach `_tune_converged_rf`
+ Auto-TUNE-Dialog-Branch → P76-A-Code bleibt als bewährter
Backup-Pfad.

### Mike-Funker-Intuition als Diagnose-Tool

Bei P142 hat Mike die richtige Hypothese live im Feld geliefert
(„übernimmt er wohl den 1.0 wert aus der gui"), nur die technische
Ursache (Phase-B-Power-Drop-Clamp) war anders als seine erste
Theorie („2 Programmpfade"). **Lesson:** Mike's Symptom-Beschreibung
ist meist 100% präzise; die Funker-Hypothese zur Ursache muss
manchmal verschoben werden. Symptom + 2-TUNE-Vergleichs-Beobachtung
(„beim 2. TUNE stimmt es") ist Gold wert — das ist der direkte Hinweis
auf den Power-Drop-Mechanismus.

### Marker `_swr_blocked_bands` — die zentrale Hardware-Bremse

Alle drei Schichten benutzen denselben Marker. Wer den Marker
respektieren MUSS:

- jeder TX-Trigger in `mw_qso.py`, `mw_tx.py`, `mw_cycle.py` —
  vor jedem `encoder.start_tx` / `radio.ptt_on` Check
- Auto-Hunt-Pick in `mw_cycle.py:on_message_decoded`
- OMNI-CQ-Trigger
- TUNE-Button selbst (sonst Endlosschleife: blocked → tune → blocked → tune)

Wer den Marker löschen darf:
- Erfolgreicher Post-Check (Marker discard + `qso_panel.add_info` Meldung)
- Bandwechsel (`_swr_blocked_bands` ist pro-Band, anderes Band ist
  per Definition nicht gesperrt)

### Hardware-Konsequenz für neue TX-Features

**Erste Frage bei jedem neuen TX-Trigger (CLAUDE.md HW-Warnung):**

1. Läuft TX garantiert über ANT1? (`radio.set_tx_antenna("ANT1")`)
2. Wird `_swr_blocked_bands` für aktuelles Band geprüft VOR `start_tx`?
3. Gibt es einen Pfad an dem `_tune_last_valid_swr` als alter Wert
   stehen bleibt? (z.B. Cancel-Pfade, Disconnect-Pfade)

Bei P142 war Punkt 3 der Killer — Cancel-während-Phase-B hätte den
Freeze durchgereicht. R1-V4-pro fing das im Pre-Code-Review (siehe
Stolperfalle 3 oben).

### Verwandte Tests

- `tests/test_p53_swr_live_watchdog.py` — P53 Schicht 1
- `tests/test_p76_swr_freeze.py` — P76-A Schicht 2
- `tests/test_p142_swr_freeze_before_phase_b.py` — P142 Schicht 3
  (inkl. T4 ORANGE-Catch Cancel-während-Phase-B)
- `tests/test_p153_swr_median_window.py` — P153 Median-Fenster
- `tests/test_p159_swr_clamp_filter.py` — P159 Clamp-1.0-Filter

### Verwandte HISTORY-Einträge

- v0.97.29 P53 SWR-Live-Watchdog
- v0.97.49 P76-A SWR-Freeze vor tune_off
- v0.98.29 P142 SWR-Freeze vor Phase B
- v0.98.34 P153 Median statt Snapshot
- v0.98.36 P154 Median-Init in ALLEN TUNE-Pfaden (Zwilling)
- v0.98.41 P159 Clamp-1.0-Werte aus Median filtern

### ⚠ Der Clamp-1.0-Wert (P159 — wichtige Sensor-Eigenheit)

Der FlexRadio meldet **SWR = exakt 1.0**, wenn keine/zu wenig
Vorwärtsleistung anliegt (kein Träger). Das ist KEINE Messung, sondern
ein hartcodierter Ersatzwert (`flexradio.py: if swr < 1.0: swr = 1.0`).
**Erkennungsmerkmal:** echte SWR-Messungen streuen (1.3 / 2.5 / 2.6),
der Clamp ist immer glatt 1.0. Auf einer echten KW-Antenne ist 1.0
praktisch unmöglich (nur Dummy-Load gibt 1.0; resonanter Dipol ~73 Ω →
~1.5:1). **Wer SWR-Werte aggregiert (Median/Mittelwert/Min) MUSS die
exakt-1.0-Werte ausschließen** — sonst verfälschen die „kein-Träger"-
Stempel das Ergebnis nach unten. Gilt auch für den noch offenen
Gain-Mess-Pfad (`_start_dx_tuning._after_tune`, TODO P155) falls der je
auf Aggregation umgestellt wird.

### Trigger für 7. Iteration

Wenn jemals eine neue Power-Modulation in der TUNE-Pipeline auftaucht
(z.B. AGC-Tests, Schutz-Trip-Tests, Tuner-Re-Match-Loops): erste
Frage — wo bleibt `_tune_last_valid_swr` im neuen Pfad? Wenn der
Freeze gegenüber dem neuen Power-Event timing-falsch sitzt → P14X
ist vorprogrammiert. Und: kommen dort Clamp-1.0-Werte in eine
Aggregation? (P159-Filter mitdenken.)

**P154-Lehre:** Wenn ein NEUER TUNE-Start-Pfad gebaut wird, MUSS er
`_init_tune_swr_sampling(duration_s)` rufen (sonst Median-Fenster mit
stale Startzeit). Drei Pfade nutzen den Helper heute — ein vierter ist
sofort verdächtig wenn er ihn vergisst.

---

## 13. Sim-Modus (P64 — FakeRadio + SimInjector, ohne Hardware)

**Pattern-Frage:** Wie testet man SimpleFT8 (UI, QSO-Flow, Auto-Hunt) OHNE
echtes FlexRadio — und ohne echte Daten/Netze zu kontaminieren?

**Aktivierung:** Env-Var `SIMPLEFT8_FAKE_RADIO=1` (kein UI, kein Setting):
```
SIMPLEFT8_FAKE_RADIO=1 ./venv/bin/python3 main.py
```

**Architektur (3 Bausteine):**
1. `core/sim_mode.py` → `is_sim_mode()` (liest die Env-Var). Zentrale Wahrheit.
2. `radio/fake_radio.py` → `FakeRadio(QObject)`: duck-typing-kompatibel zur
   FlexRadio-Oberfläche (8 Signals + ~34 vom App-Code genutzte Member).
   `ip="SIM"` (non-empty) → die ~45 App-Gates `if self.radio.ip:` behandeln
   den Sim als verbunden. Liefert KEIN Audio → der echte Decoder-Thread wird
   im Sim gar nicht gestartet (`mw_radio` gated `decoder.start()`).
   `radio_factory.create_radio()` gibt bei gesetzter Env-Var FakeRadio zurück.
3. `core/sim_injector.py` → `SimInjector`: QTimer (Slot-aligned, GUI-Thread)
   baut pro Slot Fake-FT8Messages (CQ + Fremd-Wechsel, SNR variiert inkl.
   ≤ -24 dB) und feuert sie über die **Decoder-Signals** in EXAKTER
   Reihenfolge `cycle_decoded → message_decoded(je msg) → cycle_finished`.
   Verdrahtet in `main_window._init_sim()`, Start an `radio.connected` gekoppelt.

**Warum Decoder-Signals direkt emittieren?** KISS — kein Wiring-Umbau. Die
App connected ohnehin an `decoder.cycle_decoded` etc.; der Injector ist nur
eine zweite Quelle. Da der Decoder ohne Audio nichts emittiert, kein Doppel-
Emit. (DeepSeek-R1-bestätigt für ein Test-Tool.)

**⚠ Safety-Guards (Sim darf echte Daten/Netze NICHT kontaminieren):**
- `core/weak_decode_log.py` → schreibt im Sim NICHT (Mikes P150-Evidenz).
- `core/station_stats.py` (alle 3 log_*-Methoden) → schreiben im Sim NICHT.
- PSK-Reporter → KEIN Guard nötig (read-only: lädt Spots, lädt nichts hoch).
- ADIF/QRZ → nur bei QSO-complete (in V1 nicht erreichbar, kein Responder).
- **Wenn ein neuer always-on Schreib-/Netz-Pfad gebaut wird: `is_sim_mode()`-
  Guard prüfen!** (Es gibt aktuell KEIN allgemeines „ALL.txt"-Decode-Log.)

**Grenzen V1 (→ TODO P64-B):** kein interaktiver QSO-Responder (angerufene
Station antwortet nicht → kein vollständiges QSO); Diversity-MESSUNG nicht
simuliert (braucht dual-stream); Slot-Intervall bei `start()` fixiert.
Wenn Diversity im Sim auto-startet (frische Kalibrierung gelesen), öffnet
sich der Kalibrier-Dialog — wegklicken oder vorher Normal-Modus.

**Nebennutzen:** FakeRadio ist ein **Konformitäts-Check für die
RadioInterface-Abstraktion** vor dem Icom-Fork — fehlt ein vom App-Code
genutzter Member, crasht der Sim-Start und legt das FlexRadio-Leck offen.

---

## 14. Netto-Leistungs-Anzeige (P156 — die graue Zahl in Klammern)

**„Was ist die kleine graue `(56)` zwischen W und SWR?"**

Die große Watt-Zahl ist **FWDPWR** (vorlaufende Leistung Richtung Antenne).
Bei SWR > 1 läuft ein Teil zurück → die graue `(56)` ist die **Netto-
Leistung in die Leitung** = `FWD · (1 − Γ²)`, mit Γ = (SWR−1)/(SWR+1).

- `ui/control_panel.py:compute_net_power(fwd, swr)` — pure Funktion (testbar).
- `netto_label` (#666, 10px, statisch, kein Farbwechsel) zwischen
  watt_label/swr_label. `_refresh_netto()` läuft auf `update_watt` +
  `update_swr`, zeigt NUR wenn W > 0 (im RX/0 W leer). Reset bei Bandwechsel.

**⚠ Ehrlichkeits-Subtilität (Tooltip!):** „netto in die Leitung" ist NICHT
„abgestrahlte Leistung". Mit Tuner wird die reflektierte Leistung
größtenteils re-reflektiert und strahlt doch ab; Leitungs-/Antennen-Verluste
sind nicht messbar. Daher das neutrale Label, KEIN „effektiv abgestrahlt".
Beispiel SWR 2.6: Γ=0.44 → Γ²≈0.20 → ~80% durch → 70 W → ~56 W.

**Warum statisch grau (kein Farbwechsel)?** Mike-Spec: W + SWR sind schon
farbig; eine dritte farbwechselnde Zahl wäre zu unruhig. Die Warn-Farbe
gehört zum SWR. Das interessante Fenster ist SWR 1,5–3,0 (über gutem Match,
unter der Bandsperre) — genau wo Netto-Verlust sichtbar wird.

---

## 15. RX-Liste / Stations-Akkumulator + Aging (P157)

**Kurzantwort:** Die sichtbare Empfangsliste (`rx_panel.table`) ist eine reine
**Projektion** des Stations-Dicts (`_diversity_stations` bzw. `_normal_stations`
in `mw_cycle`). Sie wird nicht inkrementell gepflegt, sondern bei Änderung
komplett neu gezeichnet (`_rebuild_rx_table` → `setRowCount(0)` + `add_message`
je `dict.values()` + `reapply_sort`). Das Dict ist die einzige Wahrheit; die
Tabelle bildet es ab.

### Akkumulation + Aging (`core/station_accumulator.py`)

`accumulate_stations(stations, messages, active_qso_targets, antenna, slot_duration_s)`:
- **Neue Station:** Eintrag anlegen, `_last_heard`/`_slot_start_ts`/`_utc_display`
  setzen.
- **Bekannte Station (Wiederhören):** seit P157 werden `_last_heard`,
  `_utc_display` und (defensiv) `_slot_start_ts` **IMMER** aktualisiert —
  VOR der change-Prüfung. Danach steuert die change-Prüfung
  (snr/ant/content) nur noch SNR/raw-Update + ob ein Rebuild nötig ist
  (`changed`).
- **Aging:** `remove_stale()` am Ende entfernt Stationen deren
  `now - _last_heard` die Schwelle übersteigt.

**Aging-Schwellen** (in SLOTS, mode-aware via `slot_duration_s`):
`AGING_SLOTS_NORMAL=7`, `AGING_SLOTS_ACTIVE=14` (aktiv angerufen),
`AGING_SLOTS_CQ_CALLER=20` (CQ-Rufer bleiben länger). Bei FT8 (15s/Slot):
105s / 210s / 300s. CQ-Rufer werden also bewusst bis 5 Min gehalten.

### Zwei Aging-Trigger (P157 — die Lücke)

`remove_stale` hat zwei Aufruf-Pfade:
1. **In `accumulate_stations`** — läuft bei jedem Slot **mit** Decodes
   (egal welche Station neu ist; remove_stale läuft immer am Ende).
2. **Zentraler Block in `_on_cycle_decoded`** (P157) — läuft bei **leeren**
   Slots (`if not messages and self._rx_mode in ("diversity", "normal")`),
   altert das aktive Dict und zeichnet bei Entfernung Tabelle + Decode-Count
   neu.

**Warum zwei Pfade?** Vor P157 lief `remove_stale` NUR über
`accumulate_stations`, und das nur bei vorhandenen Decodes. Wird das Band
still (leere Slots), wurde nie gealtert → tote Stationen klebten unbegrenzt
fest. Der zentrale Block schließt genau diese Lücke (Variante b, KISS — kein
API-Bruch, kein neuer Zustand).

### UTC-Spalte + Zeit-Sortierung

`rx_panel._populate_row` + `_time_key` bevorzugen `_slot_start_ts`
(Slot-Boundary vom Decoder, gesetzt in `decoder.py` + Fallback
`mw_cycle._assign_slot_parity`), Fallback `_utc_display`. Seit P157 wird
`_slot_start_ts` beim Wiederhören mit-aktualisiert → die Spalte zeigt
„zuletzt gehört", nicht mehr die Erst-Sichtung. `_slot_start_ts` ist die
Slot-Grenze (nicht „now"), bei Diversity also der letzte Slot wo gehört —
kein künstliches „immer jetzt".

### P157 Bug-Historie (Mike-Field 28.05.2026)

„Uralte" Stationen (bis ~17 Min) klebten in der Liste, man rief tote
Stationen an. Drei Ursachen:
- **Bug 1 (Hauptursache):** Aging lief nur bei Decodes → stilles Band =
  keine Alterung. → zentraler Block für leere Slots.
- **Bug 2:** `_slot_start_ts` beim Wiederhören nicht aktualisiert → UTC zeigte
  Erst-Sichtung. → immer aktualisieren.
- **Bug 3 (DeepSeek):** `_last_heard` nur bei Inhalts-Änderung gesetzt →
  aktive Station mit stabilem SNR + identischem Text altert raus. → immer
  aktualisieren.

### Stolperfallen

- **`_rebuild_rx_table` ist der einzige dict-basierte Render-Pfad** — beide
  Handler (`_handle_diversity_operate`, `_handle_normal_mode`) + der leere-Slot-
  Block nutzen ihn. Der DX-Tune-Pfad rendert separat (`messages` direkt, kein
  Akkumulator-Dict) — NICHT auf den Helper umstellen.
- **Aging-Block muss NACH der Modus-Verzweigung stehen** (sonst altern
  frisch akkumulierte Stationen sofort raus). Er greift nur bei `not messages`,
  daher kein Doppel-Render mit den Handlern.
- **`remove_stale` testet man direkt** — alle Aging-Tests setzen `_last_heard`
  manuell + rufen `remove_stale` separat (nicht über `accumulate_stations`).
  → Variante-c-Refactor (remove_stale ganz rausziehen) wäre test-sicher
  gewesen, wurde aber als Overengineering verworfen.

---

## 16. TUNE-Dauer & die vier TUNE-Pfade (wer nimmt welche Dauer?)

> **⚠ P119-Update (29.05.2026): Phase B (10W-Einpendeln) ist ENTFERNT.** Ein
> TUNE besteht jetzt nur noch aus **Phase A (Tuner-Match, voller Träger über
> `tune_duration_s`)** + **2s-SWR-Post-Check**. Das frühere „Leistung wird auf
> 10 W eingeregelt" nach Phase A gibt es nicht mehr (Anzeige zeigt stattdessen
> kurz „prüfe SWR"). Auch die 10W→Ziel-Watt-Hochrechnung (`_kruecken_skalierung`)
> + der 10W-Stützpunkt-Save sind weg — der echte rfpower pro (Band,Watt) kommt
> aus dem Normalbetrieb (`_auto_adjust_tx_level`→`rf_preset_store.save`). Die
> SWR-Freeze-/Band-Sperren-Logik (§12, P142/P153/P159) ist **unberührt** (Freeze
> lief schon immer VOR der jetzt entfernten Phase B). **Folge für Auto-TUNE bei
> Bandwechsel:** Skip-Bedingung ist jetzt `has_any_preset(band)` (irgendein
> gespeicherter Watt-Wert) statt `has_anchor(watt=10)`. **Der TUNE in der
> Gain-Messung heißt jetzt „Kontroll-TUNE"** (war „Auto-TUNE" — Verwechslung mit
> dem Bandwechsel-Feature). Die Phase-A/B-Detailbeschreibung in §9 + §12 unten
> beschreibt teils den Vor-P119-Stand (Phase-B-Erwähnungen = historisch).

**Kurzantwort:** Es gibt **vier** Wege, einen TUNE-Vorgang zu starten. Drei
nehmen die Dauer aus dem Setting `tune_duration_s`, einer (Rechtsklick) nutzt
bewusst eine eigene Ad-hoc-Dauer. ALLE laufen über denselben Mess-/Stop-Pfad
(`_init_tune_swr_sampling` → `_tune_stop` → `_compute_match_swr`, siehe §12).

### Die vier TUNE-Start-Pfade

| Pfad | Methode | Dauer-Quelle | Whitelist | Zweck |
|---|---|---|---|---|
| **Linksklick TUNE-Button** | `mw_tx._on_tune_clicked` | `tune_duration_s`-Setting | 5/10/15 (sonst→15) | Normaler manueller TUNE |
| **Rechtsklick-Menü** | `mw_tx._on_tune_override` (P95/P101/P160) | **Ad-hoc-Auswahl**, Setting UNBERÜHRT | **5/10/15/20** | Schnell-TUNE ohne Settings-Änderung (nasse Antenne, Dummyload-Test, „wie verhält sich der Wert gerade") |
| **Auto-TUNE bei Bandwechsel** | `mw_tx._start_auto_tune_for_band_change` | `tune_duration_s`-Setting | 5/10/15 (sonst→15) | Automatisch nach Bandwechsel (nur wenn Setting an + kein Anker) |
| **Dialog-TUNE / Kalibrierung** | `mw_radio._start_dialog_tune_sequence` | `tune_duration_s`-Setting | — | DXTuneDialog (TUNE + Gain-Mess in einem Fenster, P74-A) |

**Mike-Spec (28.05.2026):** Der Rechtsklick-Override ist bewusst NICHT an das
Setting gekoppelt — er soll genau die gewählte Zeit tunen, unabhängig von den
eingestellten 15 s. Anwendungsfall: zwischendurch kurz tunen um zu sehen wie
sich der SWR gerade verhält, ohne komplett neu einzumessen und ohne ins
Settings-Menü zu gehen (z.B. empfindlicher 20-W-Dummyload schnell zerschossen).
Die anderen drei Pfade nehmen konsistent das Setting. **Rechtsklick-Menü bietet
5/10/15/20 s** (P160, 28.05.2026: 5 s ergänzt für empfindliche Lasten wie
20-W-Dummyload — kurzer Träger ohne neu einzumessen). Hinweis: auch ein
5-s-Override durchläuft den normalen Post-Check (Median-Fenster [2 s, 4 s]) →
wenn der Tuner in 5 s nicht eingeregelt ist, kann das Band gesperrt werden
(identisch zum bestehenden Linksklick-5-s-Verhalten, kein Sonderfall).

### `auto_tune_on_band_change`-Setting (Default True)

`config/settings.py:90`. Steuert, ob beim Bandwechsel automatisch getunt wird
(`mw_radio._on_band_changed` Z. 678). **Bedingungen für Auto-TUNE bei Bandwechsel:**
Setting an + `radio.ip` + Band nicht schon gesperrt + `tuner_present` + nicht
initialer Band-Set + **kein RFPreset-Anker** (`_has_anchor`).

- **RFPreset-Anker** = Mike's „Marker"-Idee: wurde ein Band schon erfolgreich
  getunt (10W-Stützpunkt gespeichert), wird beim erneuten Eintreten NICHT nochmal
  getunt. Einmal pro Band tunen, danach nur Watchdog-Überwachung.
- **Wenn Setting AUS:** kein Auto-TUNE → Band bleibt roh-fehlangepasst → erster
  TX (Auto-Hunt/CQ) läuft auf hohe Last → SWR-Watchdog sperrt (siehe unten).

### ⚠ Zwei verschiedene „Band gesperrt — SWR"-Meldungen (Diagnose-Schlüssel)

An der **Meldungs-Länge** erkennt man, WELCHER Pfad gesperrt hat:

| Meldung | Pfad | Bedeutung |
|---|---|---|
| „⚠ Band X gesperrt — SWR Y **> Limit Z. Antenne prüfen ODER...**" (lang) | `_tune_post_swr_check` (mw_tx.py:560) | Ein TUNE lief, aber Match-SWR (Median) > Limit |
| „⚠ Band X gesperrt — SWR Y" (**kurz**) | `_on_swr_alarm` Live-Watchdog (mw_tx.py:882) | TX lief auf fehlangepasste Antenne (oft: Band nie getunt) → Watchdog (2 Alarms < 500ms) |

**Mike-Field-Bug 28.05. (28.5 auf 15M):** Die KURZE Meldung → Watchdog während
TX → Ursache war `auto_tune_on_band_change` DEAKTIVIERT → 15M nie getunt →
Auto-Hunt ging roh auf TX. KEIN Code-Bug, Lösung: Setting aktivieren. (Abzugrenzen
vom P159-Clamp-Bug, der den TUNE-MEDIAN betraf — andere Baustelle.)

### Verwandte

- §12 Hardware-Sicherheit (SWR-Mess-Schichten P53/.../P159, `_compute_match_swr`)
- §9 Bandsperre + TUNE-Pipeline (Phase A/B, `_swr_blocked_bands`)

---

## 17. Aktiv vs. Passiv: RX-Liste jagen, QSO-Fenster antworten (P158 — GEPLANT)

> **Status: KONZEPT (29.05.2026), noch NICHT gebaut.** DeepSeek-v4-pro
> Konzept-Review: GO/BAUEN. Spec in TODO.md (P158), Memory
> `project_p158_concept`. Hier dokumentiert weil es eine **Design-Philosophie**
> festschreibt, die auch über P158 hinaus gilt.

### Die zwei Fenster, zwei Haltungen

| Fenster | Haltung | Was Mike dort tut |
|---|---|---|
| **Empfangsliste (`rx_panel`)** | **AKTIV** | Stationen gezielt raussuchen, filtern, anklicken = DX-Jagen. Klick startet/überschreibt aktiv ein QSO (`_pending_station_click`, P1.24 — bricht laufendes QSO ab). |
| **QSO-Log-Fenster (`qso_panel.log_view`)** | **PASSIV / höflich** | Wer *Mike* ruft, dem antwortet er aus Freundlichkeit. Er muss nichts suchen — die Station steht ja schon im Log. |

**Mike-Wortlaut (29.05.):** „im empfangsfenster suche ich aktiv die station,
im qso fenster antworte ich jeder station, bin also passiv."

### Was P158 daraus baut (Konzept)

Wenn Auto-Hunt ein QSO mit A fährt und B *Mike* dazwischen ruft, erscheint im
QSO-Log eine Zeile `← Empf. DA1MHH B <grid>`. Diese **eine Zeile** wird
anklickbar (HTML-Anchor, da `log_view` read-only QTextEdit ist). Klick →
Auto-Hunt-eigener Puffer `_insert_pending_call` → **A wird zu Ende gefunkt**
(nicht abgebrochen!) → Auto-Hunt pausiert → B gerufen → danach **Auto-Hunt
läuft automatisch weiter** (wie nach manuellem QSO, `on_manual_qso_end`).

**Klickbar-Regel (gegen Fehlklicks):** NUR Zeilen wo ein fremder Call UNS ruft
UND Auto-Hunt anderes QSO fährt. CQs / fremde QSOs bleiben toter Text — die
gehören in die aktive RX-Liste, nicht ins passive QSO-Fenster.

### Abgrenzung zu bestehenden Mechanismen (NICHT vermischen)

| Mechanismus | Was | Verhalten |
|---|---|---|
| `_pending_station_click` (P1.24) | RX-Listen-Klick während TX | bricht laufendes QSO **ab** |
| CQ-Caller-Queue (`qso_sm.queue_changed`) | Warteliste bei normalem CQ-QSO | eigener Modus |
| **P158 `_insert_pending_call` (geplant)** | **QSO-Fenster-Klick auf Anrufer** | **laufendes QSO zu Ende, dann B** |

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
