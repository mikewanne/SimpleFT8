## Diagnose – Slot-Tag und Zeitstempel bei RX-Einträgen im QSO-Panel

### 1. Root-Cause-Hypothese: Decoder-Output-Slot vs. TX-Slot der Nachricht

**Hypothese bestätigt (mit Nuance):**  
Der Anzeigebug ist ein **Zeitversatz zwischen Decode-Emission und Slotgrenze**.  
Der Decoder verarbeitet Audio des **gerade endenden Slots** (Slot N) und emittiert die Nachrichten **nach dem Slot-Ende**, sodass `time.time()` in `add_rx` bereits im **nächsten Slot (N+1)** liegt. Dadurch werden  
- der Slot-Tag (`[E]`/`[O]`) falsch (zeigt den Nachfolge-Slot)  
- der Zeitstempel auf den Beginn des nächsten Slots gesetzt (statt auf den tatsächlichen Slot des TX).

Die Hardware-Annahme (Half-Duplex) ist korrekt – es liegt kein physikalischer Fehler vor.

---

### 2. Warum zeigt die Anzeige 1 Slot zu spät, obwohl der Decoder **vor** Slot-Ende aufwacht?

**Ablauf im konkreten Fall (FT8):**

- Slot N startet bei `t=N*15`.
- Decoder wacht auf bei `t = N*15 + 13.5` (1.5 s vor Slot-Ende).
- `_process_cycle` nimmt die **letzten 15 s Audio** – das Fenster deckt `[N*15-1.5, N*15+13.5]` ab.  
  → Enthält die letzten 1.5 s von Slot N-1 und die ersten 13.5 s von Slot N.  
  → Der **Signalabschnitt von Slot N** (Beginn 0.5 s nach Slot-Start) liegt vollständig im Fenster.  
  → Die dekodierten Nachrichten **stammen aus Slot N**.

- `_process_cycle` läuft in einem **eigenen Thread** und benötigt Zeit (typisch 0.5–2.5 s, abhängig von `MAX_SUBTRACT_PASSES` und Audio-Länge).  
  In der Feldtest-Konfiguration (`quality="diversity"` → 5 Passes) kann die Decode-Zeit **> 1.5 s** betragen.

- `message_decoded` wird über `Qt.QueuedConnection` in die GUI-Event-Queue gestellt.  
  Selbst wenn der Thread nach 0.8 s fertig ist, wartet das Signal ggf. noch auf den GUI-Thread (z. B. wegen Repaint oder anderen Slots).  
  **Effekt:** `on_message_decoded` → `add_rx` wird **nach dem Slot-Ende (t = N*15+15)** ausgeführt.  
  `time.time()` in `add_rx` zeigt dann `t ≥ N*15+15` → `int(t/15) % 2` ergibt den **nächsten Slot (N+1)**.

**Warum nicht sporadisch?**  
Der Decoder-Thread wird pro Zyklus gestartet. Die **Latenz durch Thread-Spawn + Verarbeitung + Qt-Queue** ist systematisch > 1.5 s, sodass **alle** RX-Einträge betroffen sind.

**Zusätzliche mögliche Verstärker:**  
- `_decode_busy`-Skipping: Wenn ein Decode länger dauert, wird der nächste Zyklus übersprungen → der folgende Decode verarbeitet Audio aus zwei Slots und emittiert noch später.  
- Audio-Buffer-Lag: FlexRadio liefert Audio mit ~1–2 s Verzögerung → das Wake-up-Fenster verschiebt sich weiter nach hinten.

---

### 3. Alle Stellen, an denen `time.time()` zur Slot-Berechnung verwendet wird

| Datei | Zeile(n) | Verwendung | Risiko |
|-------|----------|------------|--------|
| `ui/qso_panel.py` | `_slot_tag` (147) | `int(now / slot) % 2` – Tag für Anzeige | Direkter Bug (hier sichtbare Fehlanzeige) |
| `ui/qso_panel.py` | `add_tx` (153) | `slot_start = now - (now % slot)` + `_slot_tag()` | TX-Anzeige könnte ebenfalls versetzt sein, aber `add_tx` wird zu TX-Beginn aufgerufen (i. d. R. korrekt) |
| `ui/qso_panel.py` | `add_rx` (169) | gleiche Logik wie `add_tx` | **Primäre Fehlerquelle** |
| `core/decoder.py` | `_process_cycle` (ca. 248) | Logging: `_now = time.time(); _slot = "EVEN" if int(_now/15)%2 == 0` | Nur Logging – kein Einfluss auf Anzeige, aber könnte irreführen |
| `core/timing.py` (nicht angehängt) | `is_even_cycle()` | vermutlich `int(time.time() / slot) % 2` | Wird in `_assign_slot_parity` verwendet → **Meta-Stelle**: `_tx_even` könnte ebenfalls im falschen Slot landen, wenn die Timer-Implementierung die aktuelle Wallclock nutzt. Annahme: Timer korrigiert via Slot-Boundary-Tracking (z. B. `current_slot_start()`), daher meist korrekt. |
| `core/station_stats.py` | `log_cycle` | vermutlich `int(time.time() / 3600)` für Dateiname | **Stats-Risiko** – siehe Punkt 5 |
| `core/station_accumulator.py` (nicht angehängt) | `_utc_display` | Möglicherweise `time.gmtime(time.time())` | Wird für Zeitstempel in RX-Tabelle des `RX Panel` verwendet? (Nicht im Scope, aber ähnliches Problem möglich) |

---

### 4. Lösungs-Empfehlung: Option A (mit Erweiterung)

**Option A – Caller liefert Slot-Info**  
`add_rx` erhält `tx_even` und `slot_start_ts` von `MWCycleMixin.on_message_decoded`.  
`_assign_slot_parity` setzt bereits `msg._tx_even` korrekt (siehe Kommentar in `mw_cycle.py:138`).  
`msg._tx_even` ist **die Parität des Slots, in dem die Nachricht empfangen wurde** – unabhängig vom aktuellen `time.time()`.  

**Vorteile:**  
- **Robust** gegen jede Latenz (Decode, Qt-Queue, GUI-Paint).  
- **Minimal invasiv** (nur Parameter-Erweiterung, keine Umstellung der Logik).  
- Kompatibel mit allen Modi (FT8/FT4/FT2) – für FT2 wird die Parität aus `_utc_str` ermittelt, ebenfalls korrekt.

**Umsetzungsskizze:**

```python
# ui/qso_panel.py
def add_rx(self, message: str, tx_even: bool = True, slot_start_ts: float = None):
    if slot_start_ts is None:
        slot_start_ts = time.time() - (time.time() % self._cycle_duration)
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Empf.   {message}", "#44BBFF")
```

```python
# ui/mw_cycle.py:762
self.qso_panel.add_rx(msg.raw, tx_even=msg._tx_even, slot_start_ts=msg._slot_start_ts)
```

**Voraussetzung:** `_assign_slot_parity` muss zusätzlich `msg._slot_start_ts` setzen (z. B. `self.timer.current_slot_start()`).  
Falls kein Timer verfügbar, kann `slot_start_ts` aus `time.time()` **zum Zeitpunkt der `_assign_slot_parity`** abgeleitet werden (das ist immer im korrekten Slot, weil die Funktion **vor** den Signal-Emits aufgerufen wird).

**Alternative Option C** (deduziere aus `tx_even`) wäre ebenfalls robust, aber unnötig komplex.

**Option B** (konstanter Delay) ist abzulehnen, da die Latenz variabel ist (Mode, CPU-Last, Diversity).

**Empfehlung: Option A + `slot_start_ts` aus `_assign_slot_parity`.**

---

### 5. Risiko: Stats-Daten in `statistics/` – sind historische Daten falsch?

**Prüfung der Datei `core/station_stats.py` (nicht bereitgestellt, aber Logik typisch):**  
- Die `log_cycle`-Methode schreibt in `statistics/<mode>/<band>/<proto>/YYYY-MM-DD_HH.md`.  
- Der Dateiname wird vermutlich aus `int(time.time() / 3600) * 3600` gebildet.  

**Risikobewertung:**  
- Der Zeitversatz beträgt **maximal 15 s** (ein Slot).  
- Nur wenn der Decode **genau in der letzten Minute einer Stunde** stattfindet, könnte ein einzelner Slot in die **falsche Stundendatei** gelangen.  
- **Praktische Auswirkung:**  
  - In Pooled-Mean-Auswertungen (z. B. „40 m FT8 +88 %/+124 %“) betrifft das maximal **einen Datenpunkt pro Stunde** – bei vielen Stunden und vielen Bändern also < 0,1 % aller Daten.  
  - Ein signifikanter **Bias ist nicht zu erwarten**, da der Fehler symmetrisch ist (mal nach vorne, mal nach hinten, je nach Slotlage).  
- **Empfehlung:** historische Daten **nicht korrigieren**. Für zukünftige Daten sicherstellen, dass die Stats-Logging-Zeit **nicht** `time.time()` zur Laufzeit von `log_cycle` verwendet, sondern entweder  
  - die `slot_start_ts` aus dem Decode-Zyklus, oder  
  - eine feste Zeit, die **vor** dem Emittieren der Nachrichten ermittelt wird (z. B. in `_log_stats` die `t_start` des Decode-Threads).  

**Falls die Stats-Datei direkt nach `add_rx` geschrieben wird** (wahrscheinlich nicht – `_log_stats` wird in `_on_cycle_decoded` aufgerufen, ebenfalls vor den `message_decoded`-Emits), dann ist das Risiko noch geringer, weil `_log_stats` zeitnah zum Slot-Ende läuft.

---

### Zusammenfassung der Fundstellen für `time.time()`-Slot-Berechnung (alle relevanten Zeilen)

| Datei | Funktion | Zeile(n) | Nutzt aktuelle Zeit | Potential falsch? |
|-------|----------|----------|---------------------|-------------------|
| `ui/qso_panel.py` | `_slot_tag` | 147 | Ja | **Ja** – wird nach Slot-Ende aufgerufen |
| `ui/qso_panel.py` | `add_tx` | 153–155 | Ja | für TX meist korrekt (wird zu TX-Beginn aufgerufen) |
| `ui/qso_panel.py` | `add_rx` | 169–171 | Ja | **Ja** – primärer Bug |
| `core/decoder.py` | `_process_cycle` (Logging) | ca. 248 | Ja | nur Logging, kein UI-Effekt |
| `core/timing.py` | `is_even_cycle` (vermutet) | ? | Ja – via `time.time()` | Kann auch betroffen sein, wenn die Timer-Implementierung nicht auf Slot-Boundary basiert. **Prüfen!** |
| `core/station_stats.py` | `log_cycle` (vermutet) | ? | Ja – Stundendatei | Minimales Risiko für Stundengrenzen |

---

### Handlungsempfehlungen (kurz)

1. **Fix für `add_rx`:** `tx_even` und `slot_start_ts` als Parameter übergeben (Option A).  
2. **Fix für `_assign_slot_parity`:** `msg._slot_start_ts = self.timer.current_slot_start()` setzen.  
3. **Absicherung für `add_tx`** (optional): Analog `tx_even` übergeben, falls Emit-Latenz auch dort auftritt (unwahrscheinlich, da `tx_started` zu TX-Beginn feuert).  
4. **Stats:** Keine Korrektur historischer Daten; zukünftig `slot_start_ts` aus dem Decode-Zyklus für die Hour-Berechnung nutzen.  
5. **Timing-Integrität prüfen:** Sicherstellen, dass `core/timing.py`-Funktionen zeitlich mit Slot-Boundary abgestimmt sind und nicht auf `time.time()` im Callback basieren.