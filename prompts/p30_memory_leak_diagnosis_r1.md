[deepseek] ~7814 Tokens, 1 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=8930 out=6297 total=15227
## Kritische Prüfung der Diagnose-Hypothese

### 1. Hypothese `_audio_buffer_24k` Skip-Bug – plausibel?

**KRITISCH**: Ja, die Hypothese ist **plausibel und der wahrscheinlichste Hauptverdacht**. Der Code zeigt klar, dass der Skip-Pfad (`continue` bei `_decode_busy==True`) den Buffer nicht leert, während `feed_audio` weiter Chunks anhängt. Das führt zu monotonem Wachstum, solange `_decode_busy=True` bleibt. Dies ist ein **klassischer Logikfehler**, der genau das beobachtete Verhalten erklärt.

**KOENNTE**: Es gibt zwei Szenarien für `_decode_busy=True>1 Slot`:
- `_process_cycle` hängt in der C-Bibliothek ft8lib (kein Python-Exception → finally läuft nie).
- Der Thread braucht länger als 15s (z.B. CPU-Überlastung) → nächster Slot sieht `_decode_busy=True` und skipped.

Im ersten Fall bleibt der Zustand dauerhaft, im zweiten nur temporär. Beide führen zu akkumulierendem Buffer, weil der Skip-Pfad keine Bereinigung vornimmt.

---

### 2. Math-Check – passt 540 MB/h?

**KRITISCH**: Die beobachtete Rate von **540 MB/h** passt **nur bedingt** zur einfachen Skip-Theorie mit Standardannahmen.

- Mono: 24 kHz × 2 Byte × 15 s = **720 KB pro Slot** (15 s). Bei einem Skip alle 15 s ergäbe das **172,8 MB/h** (720 KB × 4 Slots/min × 60 min). Das ist Faktor ~3 niedriger als beobachtet.
- Mit Diversity (2 Antennen) und Annahme, dass beide Audio-Streams **gleichzeitig** im Buffer landen (z.B. als ein Stereo-Array oder zwei separate Aufrufe von `feed_audio`), würde sich der Pro-Slot-Beitrag verdoppeln auf **345,6 MB/h**. Immer noch deutlich unter 540 MB/h.
- Um auf 540 MB/h zu kommen, müssten etwa **1,5 MB pro Slot** anfallen – das entspricht entweder mehr als 2 Kanälen, oder die Chunks sind größer als 15s (z.B. weil `feed_audio` häufiger als einmal pro Sekunde aufgerufen wird und die Chunk-Größe nicht konstant ist). Die Rechnung im Prompt ("12,5 Slots/min ≈ 4 FT8-Slots/min × ~3 Skips pro Slot") ist irreführend: **Pro Slot kann nur ein Skip stattfinden** (der Decoder wacht nur einmal pro Slot auf). Wenn der Decoder hängt, wird jeder folgende Slot geskippt, aber das sind dennoch nur 4 Slots/min. Die Aussage "3 Skips pro Slot" ist mathematisch nicht haltbar.

**FAZIT**: Die beobachtete Rate ist **höher** als die einfache Abschätzung. Daher muss es Zusatzfaktoren geben:
1. **Diversity verdoppelt effektiv die Datenrate** (wenn beide Antennen getrennt oder als Stereosignal geliefert werden) → dann ~345 MB/h.
2. **Zusätzliche Speicherfresser** können zum RSS beitragen (z.B. hängende Threads mit großen Arrays, Qt-Event-Queues).
3. **Der Buffer wächst nicht nur linear mit der Zeit, sondern durch Fragmentierung und Overhead** (Python-Listen-Overhead pro Chunk, numpy-Array-Overhead). Die tatsächliche Speicherbelegung kann leicht das 1,5- bis 2-Fache der reinen Audiodaten betragen.

**SOLLTE**: Vor dem Fix sollte **genau gemessen werden, wie viele Bytes pro Sekunde in `_audio_buffer_24k` landen** (z.B. durch Logging der Summe der `len(chunk)` alle 60s). Nur so lässt sich die Rate mit der Theorie deckungsgleich bringen.

---

### 3. Diversity-Verdoppelung – prüfenswert?

**KRITISCH**: Ja, das ist ein **zentraler Punkt**. Der Code hat eine einzige `feed_audio`-Schnittstelle. Falls VITA-49 zwei Kanäle liefert, gibt es zwei Möglichkeiten:
- **Stereosignal**: Ein np.ndarray mit shape (N, 2) wird übergeben → `len(samples_int16)` ist dann N, aber die tatsächliche Byte-Zahl ist doppelt so hoch. Der Buffer speichert dann 2× so viele Daten pro Zeiteinheit.
- **Zwei getrennte Aufrufe**: `feed_audio` wird doppelt so oft aufgerufen (jeweils mit Mono-Chunks aus jeder Antenne). Das würde die Anzahl und Größe der Chunks verdoppeln.

**SOLLTE**: Im Code prüfen, ob `feed_audio` tatsächlich mit Stereo-Daten oder doppelter Frequenz aufgerufen wird. Ein `print(len(samples_int16), samples_int16.dtype, samples_int16.shape)` an geeigneter Stelle wäre aufschlussreich.

---

### 4. Lock-Pattern – Race-Condition möglich?

**KRITISCH**: Die Trennung von `_buffer_lock` und `_decode_busy_lock` ist **prinzipiell korrekt**, birgt aber eine **kleine Lücke**:
- Zwischen der Abfrage `if self._decode_busy:` (unter `_decode_busy_lock`) und dem anschließenden Holen des Buffers (unter `_buffer_lock`) besteht ein **Zeitfenster**, in dem `feed_audio` einen neuen Chunk hinzufügen kann, der dann nicht in `chunks` landet, sondern im neu zugewiesenen leeren Buffer liegen bleibt. Dieser Chunk geht **verloren** (wird nie dekodiert) – aber das ist **kein Leak**, da er beim nächsten Zyklus geholt wird. Allerdings kann dies zu leichten Audioverlusten führen, aber nicht zu kontinuierlichem Wachstum.

**KOENNTE**: Ein ernsteres Race wäre möglich, wenn `feed_audio` aus einem anderen Thread kommt und `_buffer_lock` nicht korrekt geschützt würde (tut es). Daher ist das Lock-Design **sicher** für das Leak-Problem.

---

### 5. Fix-Strategie – A allein, A+C, oder anders?

**KRITISCH**:
- **Fix A allein** (Buffer im Skip-Pfad leeren) behebt den **unmittelbaren Leak** – der Buffer wächst nicht mehr unbegrenzt, selbst wenn `_decode_busy` dauerhaft True bleibt. Allerdings wird dann kontinuierlich Audio verworfen (alle 15s). Das ist akzeptabel, solange der Decoder irgendwann wieder normal läuft.
- **Fix B** (Cap) ist eine **Absicherung** für den Fall, dass der Skip-Fix A vergessen wird oder ein anderer Codepfad den Buffer nicht leert. Ein Cap auf ~2 Slots (z.B. 2 MB) verhindert katastrophales Wachstum, führt aber zu Datenverlust der ältesten Slots. **Empfehlenswert als zweiten Schutz**.
- **Fix C** (Watchdog) adressiert den **hängenden Thread** – das eigentliche Grundproblem. Ohne Watchdog könnte der Decoder dauerhaft im Skip-Zustand bleiben (alle 15s Skip → kein Decode mehr). Ein Watchdog (z.B. Timer, der nach 30s `_decode_busy` zurücksetzt und den Thread abbricht oder ignoriert) wäre **sauberer**. Da der C-Code (ft8lib) nicht abbrechbar ist, müsste man den Thread als `daemon=True` laufen lassen und ihn einfach „vergessen“, während ein neuer `_process_cycle` gestartet wird.

**FAZIT**: **A + C** ist die robusteste Kombination:
- **A** verhindert den Buffer-Leak sofort.
- **C** stellt sicher, dass der Decoder sich bei einem Hang selbst „heilt“ (z.B. nach 30s `_decode_busy` auf False setzen und den alten Thread aufgeben). Ohne C wird der Decoder nach einem Hang dauerhaft skippen – das ist funktional schlecht, aber speichertechnisch durch A begrenzt.
- **B** als zusätzliche Sicherung ist optional, aber harmlos.

**KOENNTE**: Zusätzlich sollte geprüft werden, ob `ft8lib.decode` wirklich nie zurückkehrt. Ein `timeout`-Wrapper um den C-Aufruf wäre ideal, aber schwer umsetzbar. Ein Workaround ist, den `_process_cycle`-Thread in einem separaten Prozess zu starten (multiprocessing), dann könnte man ihn per `terminate()` killen. Das wäre aber eine große Umstellung.

---

### 6. Was vor dem Fix prüfen (Memory-Watcher)

**SOLLTE**: Vor dem Einspielen eines Fixes sollten folgende Messungen durchgeführt werden:

1. **Buffer-Größe loggen**: In `_decode_loop`, direkt vor dem `with self._buffer_lock:` (Zeile 168), die Gesamtlänge des Buffers (Summe aller Chunk-Längen) ausgeben. Vergleiche mit RSS-Wachstum.
2. **Diversity-Datenrate messen**: In `feed_audio` die Größe der eingehenden Chunks und deren Frequenz protokollieren (z.B. alle 1s: `total_samples += len(samples_int16)`).
3. **Häufigkeit von Skips tracken**: Zähler, wie oft der Skip-Pfad pro Stunde erreicht wird.
4. **RSS-Monitoring**: Aktivitätsmonitor oder `psutil`-basierte Aufzeichnung der Python-RSS über mehrere Stunden.

Wenn sich zeigt, dass der Buffer-Wachstum mit dem RSS-Wachstum korreliert und der Skip häufig auftritt, ist die Hypothese bestätigt.

**KOENNTE**: Auch die Qt-Signal-Queues überwachen (z.B. durch Zählen der emittierten Signale vs. verarbeiteten Events in der GUI). Falls die GUI langsam ist, könnten sich dort FT8Message-Objekte stauen, was auch zum Speicherwachstum beiträgt (wenn auch in geringerem Maße). Ein schneller Test: `len(self.findChildren(QObject))` oder die Event-Queue-Länge in der Hauptschleife.

---

## Zusammenfassung der Lücken und Kritikpunkte

1. **Math passt nur mit Zusatzfaktoren** (Diversity + Fragmentierung). Die Rate 540 MB/h ist plausibel, aber nicht ausreichend begründet.
2. **Diversity-Datenpfad muss geklärt werden** – ob 1× oder 2× Daten in den Buffer fließen.
3. **Andere mögliche Quellen** wurden zu schnell eliminiert:
   - Qt-Signal-Stau bei Überlastung (FT8Message-Objekte könnten sich in der Event-Queue türmen).
   - Hängende Threads halten große temporäre Arrays (`audio_12k`, `audio_work`) – das summiert sich, wenn viele Threads hängen.
   - C-Bibliothek könnte intern Speicher allozieren, der nicht freigegeben wird (schwer prüfbar).
4. **Lock-Pattern** ist OK, aber der Skips-Pfad übersieht die Buffer-Bereinigung – das ist der Kern.
5. **Fix-Strategie**: Ohne Watchdog C bleibt der Decoder nach einem Hang funktional tot (nur Skips). Fix A allein löst das Speicherproblem, aber nicht das Verfügbarkeitsproblem.

**Empfehlung**:  
- **Kurzfristig**: Fix A einbauen (Buffer leeren im Skip-Pfad) – das stoppt den Leak sofort.  
- **Parallel**: Diversity-Datenpfad klären und Watchdog C implementieren.  
- **Test**: Mit einem künstlichen „Hang“ (z.B. `time.sleep(30)` in `_process_cycle`) den Effekt von A+C validieren.

Die Diagnose ist **gut fundiert**, aber die Rate sollte noch mit Messdaten untermauert werden, bevor man von „bestätigt“ spricht.
