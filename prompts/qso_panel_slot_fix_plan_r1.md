## Prüfung des V2-Implementierungsplans

### 1. Architektur-Entscheidung (Decoder = Slot-Quelle) – robust und KISS?

**Bewertung: Robuster KISS-Ansatz, kein Overengineering.**

Begründung:
- Der Decoder ist die *einzige* Stelle, die den intendierten Slot (target_slot_start) vor Offset und Sleep-Latenz kennt. Jede time.time()-basierte Berechnung an anderer Stelle ist anfällig für Slot-Verschiebung durch Decoder-Skips („Zu wenig Audio").
- Der Plan setzt die Information als Attribut auf jede einzelne Message – das ist verlustfrei und erfordert nur minimale Änderungen in den Konsumenten (qso_panel, auto_hunt, mw_cycle).
- FT2 (3.8s) wird über denselben Mechanismus abgedeckt, ohne separaten `_slot_from_utc`-Umweg.
- Kein zusätzlicher globaler State, keine Abhängigkeit von Timer-Korrekturen in den Konsumenten.

Einzige mögliche Kritik: Der target_slot_start wird im Decoder-Thread vor dem Start des _process_cycle-Threads berechnet. Das ist aber synchron und korrekt, weil wait = target_slot_start + wake_offset - now genau diesen Slot referenziert.

**Entscheidung:** Bestätige die Architektur als robust und KISS.

---

### 2. Wake-Drift-Behandlung – target_slot_start pre-sleep berechnet?

**Bewertung: Schlüssig, Edge-Cases abgedeckt.**

Berechnung:
```python
cycle_pos = now % slot
if cycle_pos < wake_pos:
    target_slot_start = now - cycle_pos          # selber Slot
else:
    target_slot_start = now - cycle_pos + slot   # nächster Slot
```
Das liefert den exakten Slot-Start (z.B. :00 oder :15), der zum aktuellen `now` + wait führen wird. Auch wenn der anschließende `time.sleep(wait)` durch Scheduler-Jitter etwas länger dauert, bleibt `target_slot_start` korrekt – es referenziert den Slot, in den hinein aufgeweckt werden soll.

**Edge-Cases:**
- **Slot-Überlauf durch extremen Jitter (> slot - wake_pos)?** Kaum realistisch (wake_pos = 13.5s bei FT8, Jitter < 0.1s), aber selbst dann wäre der target_slot_start vom vorherigen Schleifendurchlauf und der Decoder müsste den nächsten Slot nehmen – hier würde der Decoder die Audio vom *falschen* Slot dekodieren. Das ist aber ein bestehendes Problem, nicht durch diesen Fix verursacht. Der Plan ignoriert diesen unwahrscheinlichen Fall zu Recht.
- **`_decode_busy`-Skip:** Wenn der vorherige Thread noch läuft, wird der ganze Zyklus übersprungen → kein target_slot_start berechnet → keine falschen Messages.
- **Mode-Wechsel mitten im Betrieb:** Die Slot-Länge kann sich ändern; die Variable `_SLOT` wird beim Start des Decoders aus `self._mode` gelesen. Wenn der Mode während des Schleifendurchlaufs wechselt (unwahrscheinlich, aber möglich), wäre die Berechnung inkonsistent. Hier müsste man sicherstellen, dass `_SLOT` nur einmal zu Beginn der Schleife gelesen wird oder die Mode-Änderung mit einem Lock geschützt ist. Der aktuelle Code liest `_SLOT = {...}.get(self._mode, 15.0)` innerhalb der Schleife – das ist okay, aber der Mode-Wechsel könnte zwischen `time.sleep` und `target_slot_start`-Berechnung passieren. Praktisch irrelevant, da Mode-Wechsel ohnehin den Decoder stoppt/neustartet.

**Fazit:** Wake-Drift-Behandlung ist robust und ausreichend.

---

### 3. Auto-Hunt-Regressions-Risiko – nutzt `_tx_even` aktuell den falschen Wert?

**Analyse des aktuellen Verhaltens:**

Der aktuelle Code setzt `_tx_even` in `mw_cycle._assign_slot_parity` direkt aus dem Timer zum Zeitpunkt der `cycle_decoded`-Emission:
```python
msg_was_even = self.timer.is_even_cycle()  # Zeitstempel des Aufrufs
for m in messages:
    m._tx_even = msg_was_even
```

Bei einem übersprungenen Slot (z.B. Decoder wake für Slot N+1, dekodiert Audio von Slot N) ist `msg_was_even` für Slot N+1, aber die Messages gehören zu Slot N → **falscher Wert**.

Auto-Hunt liest diesen Wert:
```python
tx_even = getattr(msg, '_tx_even', None)   # in auto_hunt.py select_next
# ...
self._last_tx_even = best.tx_even
# später in mw_cycle._run_auto_hunt:
if _candidate.tx_even is not None:
    self.encoder.tx_even = not _candidate.tx_even   # senden im Gegentakt
```

Wenn `_tx_even` falsch war (z.B. true statt false), sendet Auto-Hunt im Slot, den die Gegenstation angeblich nicht sendet – d.h., es sendet im *falschen* Slot. Das kann dazu führen, dass der CQ-Aufruf nicht empfangen wird oder das QSO scheitert. Mit dem Fix wird `_tx_even` korrekt auf den Slot der Nachricht gesetzt → Auto-Hunt sendet im richtigen Gegentakt.

**Risikobewertung:**
- **Keine bestehende Kompensation durch Inversion:** Die Logik `not _candidate.tx_even` ist *immer* die Korrektur für den richtigen Slot. Wenn `_tx_even` vorher falsch war, wurde `not falsch` = richtiger Slot gesendet? Nein: Wenn `_tx_even` für eine Nachricht in Slot N fälschlich auf Slot N+1 zeigt (z.B. true statt false), dann gilt `not true = false` → Encoder sendet im false-Slot, obwohl er im true-Slot senden müsste (Gegner sendet in false). Das ist *nicht* eine kompensierende Inversion, sondern ein reiner Fehler. Mit dem Fix wird `_tx_even` korrekt false, `not false = true`, Encoder sendet im richtigen Slot. **Auto-Hunt wird durch den Fix korrigiert, nicht gebrochen.** Das Risiko ist minimal.

- **Tests erforderlich:** Der geplante Test `test_auto_hunt_with_corrected_tx_even` sollte genau dieses Szenario abdecken: Eine Nachricht mit gesetztem `_tx_even` (korrekt) und prüfen, ob Auto-Hunt den Encoder im passenden Slot konfiguriert.

**Entscheidung:** Das Regressions-Risiko ist gering. Bestehende Feldtests mit korrekten Slot-Verschiebungen sollten grün bleiben.

---

### 4. Sind die 6 atomaren Commits sinnvoll geschnitten?

Der Plan listet 7 Commits (6 + 1 Test-Commit). Die Aufteilung ist sehr gut:

1. **feat(decoder): target_slot_start pre-sleep + Thread-Arg** – Grundlage, ohne Verhalten zu ändern.
2. **feat(decoder): _slot_start_ts/_tx_even auf Messages setzen** – Attribute werden gesetzt, aber noch von `_assign_slot_parity` überschrieben.
3. **refactor(mw_cycle): _assign_slot_parity respektiert Decoder** – Fallback, überschreibt nicht vorhandene Attribute. Jetzt wirken die Decoder-Werte.
4. **feat(qso_panel): add_rx/add_tx mit slot_start_ts/tx_even** – API-Erweiterung, backward-kompatibel.
5. **feat(encoder): tx_started mit slot_start_ts/tx_even** – Signal-Erweiterung, erfordert Anpassung aller Listener.
6. **refactor(mw_cycle): Caller add_rx mit Message-Feldern** – Nutzung des neuen Pfads.
7. **test(slot): 9 neue Tests** – sauber abgetrennt.

**Kritikpunkte:**
- Commit 2 und 3 könnten zusammengelegt werden, da sie logisch zusammengehören: erst Attribute setzen, dann Respektierung implementieren. Aber die Trennung ermöglicht einen sauberen Zwischenzustand (Commit 2 fügt Attribute hinzu, Commit 3 ändert `_assign_slot_parity`). Das ist in Ordnung.
- Commit 5 (encoder) erfordert Anpassung aller Listener des `tx_started`-Signals. Der Plan erwähnt `mw_qso.py:59` als einen Listener. Es sollte eine vollständige Liste der Listener geben (z.B. auch in `test_encoder.py`). Der Commit sollte alle Vorkommen migrieren. Das ist ein potenzielles Risiko, wenn ein Listener übersehen wird. Der Plan sollte klarstellen: „Suche alle Verbindungen zu `tx_started` im gesamten Projekt und migriere sie."

**Fazit:** Die Commit-Struktur ist sinnvoll, mit dem Hinweis auf vollständige Listener-Migration bei Commit 5.

---

### 5. Welche Tests fehlen? Welche AC-Punkte sind nicht testbar?

**Bereits geplante Tests (9 Stück):**
- test_add_rx_uses_provided_slot
- test_add_rx_fallback_when_no_slot_info
- test_add_tx_uses_provided_slot
- test_assign_slot_parity_respects_decoder
- test_assign_slot_parity_fallback
- test_target_slot_start_pre_sleep_no_drift
- test_target_slot_start_modes
- test_messages_get_slot_attributes
- test_auto_hunt_with_corrected_tx_even

**Fehlende Tests:**

1. **Encoder-Signal-Migration:** Es sollte einen Test geben, der prüft, dass `Encoder.tx_started`-Signal die neuen Parameter (tx_even, slot_start_ts) korrekt emittiert, und dass der Listener (z.B. in `mw_qso.py`) diese Werte an `qso_panel.add_tx` weitergibt. Dieser Test könnte in `test_encoder_slot.py` oder als Teil von `test_slot_display.py` realisiert werden.

2. **FT2-Konsistenz:** Es gibt keinen expliziten Test, der sicherstellt, dass der Decoder für FT2 (slot=3.8) `_tx_even` korrekt setzt und dass der Fallback `_slot_from_utc` nicht mehr benötigt wird. `test_target_slot_start_modes` deckt die Berechnung ab, aber nicht die FT2-spezifische Alternative (bisher `_slot_from_utc`). Ein Test wie `test_ft2_slot_from_decoder` wäre gut.

3. **rx_panel-Konsument:** Der Plan erwähnt, dass `rx_panel.py:412` `_tx_even` liest. Es sollte einen Test geben, der prüft, dass nach dem Fix die Anzeige (z.B. Slot-Spalte oder Highlighting) weiterhin funktioniert. Das könnte in `test_rx_panel.py` ergänzt werden. Wenn rx_panel keine Slot-Anzeige hat, ist es nicht kritisch, aber als Regressionstest sinnvoll.

4. **Negativtest für übersprungenen Slot:** Ein Test, der den Fall simuliert, dass der Decoder einen Slot überspringt (zu wenig Audio), und dann im nächsten Slot dekodiert. Dabei muss sichergestellt sein, dass die Messages aus dem korrekten target_slot_start stammen. Das ist durch `test_target_slot_start_pre_sleep_no_drift` und `test_messages_get_slot_attributes` indirekt abgedeckt, aber ein expliziter Test mit gemocktem `time.time()`-Verhalten wäre wünschenswert.

**Nicht testbare AC-Punkte:**

- **AC-1 Field-Test:** Manuelle Überprüfung, nicht automatisierbar. Der Plan sieht ihn vor.
- **AC-6 FT4 + FT2 Smoke-Test:** Nur manuell oder durch Integrationstests, nicht in Unit-Tests. Der Plan erwähnt „Test nicht Field, da Mike FT8 funkt" – das ist okay, die Unit-Tests für die Modi reichen.
- **AC-7 rx_panel-Visualisierung:** Visuelle Überprüfung, kann durch Screenshot-Tests ergänzt werden, ist aber nicht im Plan.

**Gesamtbewertung:** Die geplanten 9 Tests sind ausreichend, um die Kernlogik abzudecken. Die fehlenden Tests (Encoder-Signal, FT2-Stabilität, rx_panel) sind optional, aber empfehlenswert für vollständige Abdeckung.

---

## Zusammenfassung der Prüfung

| Punkt | Status | Anmerkung |
|-------|--------|-----------|
| 1. Architektur | ✅ Robust + KISS | Kein Overengineering |
| 2. Wake-Drift | ✅ Schlüssig | Edge-Cases behandelt |
| 3. Auto-Hunt-Risiko | ✅ Gering | Keine bestehende Inversion; Fix korrigiert |
| 4. Atomare Commits | ✅ Sinnvoll | Achtung bei Commit 5: alle Listener migrieren |
| 5. Tests | ⚠️ Ausreichend | Empfehle 2 Zusatztests (Encoder-Signal, FT2-Konsistenz) |

**Empfehlung:** Der Plan kann so umgesetzt werden. Vor Commit 5 sollte eine grep-Suche nach `tx_started\.connect` oder `tx_started` durchgeführt werden, um alle betroffenen Stellen zu finden. Die Tests sollten um die beiden genannten Punkte ergänzt werden.