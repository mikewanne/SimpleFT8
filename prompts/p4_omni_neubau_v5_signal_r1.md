[deepseek-high] ~32460 Tokens, 5 File(s) → deepseek-reasoner (max_tokens=32000)
[deepseek-high] R1 denkt — bis zu 5 Min ...
[deepseek-high] in=37701 out=12459 total=50160
## Kritik der Spezifikation „P4.OMNI-NEUBAU V5 — Signal-basierter Refactor (V2)“  

**Regelkonformität:**  
- Die Arbeit am vorliegenden Code (v0.96.0) wird nicht gefordert – die Kritik bezieht sich **ausschließlich auf die Ziel-Spezifikation** (V5).  
- „Out-of-scope“ (Frequenz-Recheck, Encoder-Änderungen etc.) wurde respektiert.  
- Jedes Finding wird am konkreten Use-Case eines Hobby-Funker-Tools gemessen (Single-Operator, kein Multi-Tenant).  

---

### Strukturierte Liste der Findings

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---------|---------|-------------|------------|
| **Hinweis** | `slot_action.emit` für TX-Slot fehlt in der textlichen Beschreibung (AC8). AC24 definiert zwar das Signal, aber AC8 listet nur `encoder.transmit` auf – das Emittieren von `slot_action` ist implizit. | §3 AC8 | In AC8 ergänzen: nach erfolgreichem `encoder.transmit` auch `slot_action.emit(label, is_tx=True, target_even=target_even)` aufrufen. Alternativ AC9 zu AC8+AC9 zusammenfassen. |
| **Hinweis** | Keine Angabe, ob `start()` idempotent sein soll. Im aktuellen Code (v0.96.0) gibt es eine `if self._running: return`-Guard – dieser Schutz fehlt in der Spezifikation. | §3 AC1 | AC1 ergänzen: „Rufe `start()` bei bereits aktivem OMNI ohne Wirkung auf (no-op).“ |
| **Risiko** | Pattern-Desynchronisation bei schwerer GUI-Thread-Blockade (Decoder/Event-Queue). Die Spezifikation erwähnt das Risiko in §5 und akzeptiert es per KISS (Klärungsfrage 3, Variante A). Jedoch fehlt eine explizite Warnung, dass bei `cycle_pos > x Sekunden` der `_slot_index` und die tatsächliche Slot-Synchronisation auseinanderlaufen *können* (kein Guard). | §5 Randbedingungen + §8 Klärung 3 | In §5 einen Hinweis ergänzen, dass bei regelmäßigen Blockaden > 0,5 s pro Slot das OMNI-Pattern temporär inkonsistent werden kann. Für Hobby-Use akzeptabel – klar dokumentieren. |
| **Hinweis** | `counter_changed` wird in AC26 definiert, aber der genaue Emit-Zeitpunkt (nach erfolgreichem TX) ist nicht mit AC11 verknüpft. AC11 beschreibt nur, wann *nicht* inkrementiert wird. | §3 AC11 / AC26 | AC11 um den Hinweis ergänzen: „Bei erfolgreichem `encoder.transmit` (True) immer `counter_changed` und `slot_action` emitten – in dieser Reihenfolge.“ |
| **Hinweis** | Reihenfolge von `omni_started` und dem ersten `on_cycle_start` ist nicht festgelegt. Listener von `omni_started` könnten darauf angewiesen sein, dass `cq_freq_changed` bereits verfügbar ist (wird erst später beim ersten TX emittet). | §3 AC22, AC12 | Klarstellen: `omni_started` wird **sofort** in `start()` emittet (vor erstem `cycle_start`). `cq_freq_changed` folgt beim ersten TX – falls gewünscht, ggf. `_cq_audio_hz` schon in `start()` setzen und emitten? (unwahrscheinlich). |
| **Verbesserung** | Test T6 trägt den Namen `test_block1_pos4_rollover_to_block2_pos0_tx_odd`. Block 1 Pos 4 ist ein **RX-Slot** (Horche), kein TX. Der Rollover ist korrekt, aber der Name suggeriert einen TX-Aufruf direkt nach dem RX. | §6 Test T6 | Test umbenennen in z. B. `test_block1_rx_rollover_to_block2_tx_odd` oder Beschreibung präzisieren. |
| **Hinweis** | `resume_after_qso` setzt `_active=True` „falls noch nicht“. Da `pause()` nur `_paused` setzt, ist `_active` nach `pause()` noch **True** – die Klausel greift nie. Der Satz ist unnötig und könnte Verwirrung stiften (z. B. wenn jemand `resume_after_qso` nach `stop()` aufruft). | §3 AC18 | `_active=True` ergänzend zu `_paused=False` setzen – der Satz kann entfallen oder als „idempotenter Schutz“ kommentiert werden. |
| **Risiko** (niedrig) | `encoder.transmit` kann True zurückgeben, aber der TX-Job später scheitern (Encoding-Fehler, Radio-Fehler). OMNI hat dann einen TX-Counter inkrementiert und das Pattern verschoben, ohne dass tatsächlich gesendet wurde. Dieses Risiko bestand auch in v0.96.0 und wird **nicht adressiert**. | §3 AC11, AC8 | Keine Änderung (KISS), aber in den Randbedingungen (§5) erwähnen, dass `encoder.transmit`**Erfolg** nicht garantiert, dass FT8-Audio auch wirklich gesendet wird. Hobby-typisch selten, daher akzeptabel. |

---

### Stellungnahme zu den drei Klärungsfragen (§8)

**1. Toggle-Start Block-Wahl – Variante A (IMMER Block 1)**  
✅ *Bewertung:* KISS-konform. Die 1-Slot-Wartezeit im Falle eines Startens auf einem odd Slot ist vernachlässigbar (15s). Die Vermeidung einer bedingten Block-Wahl macht den Code einfacher und robuster. Richtig entschieden.

**2. Frequenz-Sticky – Variante A (1× gesetzt, fest bis Stop)**  
✅ *Bewertung:* Folgt konsistent Mikes Aussage „Bleibt fest. Kein Versatz.“. Ein Recheck alle 4 Blöcke (ca. 5 Min) wäre Overengineering, da die Frequenzumgebung sich in dieser Zeit kaum ändert. KISS ist hier die richtige Wahl.

**3. Decoder-Blockade-Schutz – Variante A (kein Schutz)**  
✅ *Bewertung:* Das Risiko ist gering (Decoder-Blockade > 0,5 s ist selten) und tritt im gleichen Maße beim existierenden Normal-CQ auf. Eine zusätzliche `cycle_pos`-Prüfung wäre Code-Komplexität ohne messbaren Nutzen im Hobby-Betrieb. Variante A ist vertretbar.

---

### Overengineering – kein Befund

- Die 30 Akzeptanzkriterien sind für eine präzise Umsetzung sinnvoll und nicht überladen.  
- Die Klärungsfragen sind notwendig, weil sie konkrete Design-Konflikte auflösen.  
- Der Verzicht auf Worker-Thread, eigene Boundary-Berechnung und Sleep-Logik reduziert die Komplexität drastisch – genau richtig.  

**Fazit:** Die Spezifikation ist durchdacht und weitgehend widerspruchsfrei. Die genannten Punkte sind kleinere Unschärfen, die vor der Implementierung geklärt werden sollten. Die Architektur (signal-getriggert, GUI-Thread, Encoder-Atomar-Aufruf) ist robust und für den Hobby-Einsatz angemessen.
