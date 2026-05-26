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
