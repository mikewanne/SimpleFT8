Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und
PySide6/Qt-Signale. Das Projekt (SimpleFT8) ist ein Hobby-Funker-Tool für EINEN
Operator, FlexRadio, FT8/FT4/FT2.

WICHTIG: Der Auftraggeber hat zweimal erlebt, dass ich (die andere KI) voreilig
Annahmen statt Code-Fakten genommen habe. Deine Aufgabe ist deshalb zuerst
DIAGNOSE auf Basis des angehängten Codes — nicht meiner Hypothese zustimmen,
sondern im Code nachweisen WO die Doppelung entsteht. Erst danach Fix-Plan.

KRITISCHE REGELN:
1. Code als Referenz, nicht meine Worte. Belege jede Aussage mit Datei:Zeile.
2. KISS für ein Hobby-Tool. Keine Abstraktion ohne Mehrfach-Bedarf.
3. FORMAT: erst Diagnose-Abschnitt (Wo/Warum), dann Tabelle
   Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

================================================================================
SYMPTOM (Mike-Field, Screenshot)
================================================================================
Im QSO-Verlauf erscheinen ZWEI EXAKT IDENTISCHE Empfangs-Zeilen direkt
untereinander:

  12:35:30 ← Empf. DA1MHH LZ100LZ R-07
  12:35:30 ← Empf. DA1MHH LZ100LZ R-07

Gleicher Text, gleiche Uhrzeit AUF DIE SEKUNDE. Sehr selten, aber reproduzierbar
beobachtet. Das QSO wurde danach korrekt komplett (✓). Modus war Diversity DX.

Mike-Aussage (zu verifizieren): Die zwei Diversity-Antennen empfangen
slot-versetzt (eine even, eine odd), können also NIE dieselbe Sekunde
dekodieren — gleiche Uhrzeit = dieselbe Nachricht doppelt, NICHT zwei echte
Empfänge. Daraus folgert Mike: reiner Anzeige-Bug.

================================================================================
VON MIR VERIFIZIERTE CODE-FAKTEN
================================================================================
- `core/decoder.py:441 _decode_with_subtraction`: dedupliziert INTERN über alle
  Passes + Slide-Offsets via `seen: set[str]` (Z.445), key = normalisierte
  message; `if key not in seen: seen.add(key)` (Z.463/494). → innerhalb EINES
  Decode-Durchlaufs kann dieselbe message NICHT zweimal in die Liste.
- `core/decoder.py:330` `_process_cycle` ruft `_decode_with_subtraction` EINMAL,
  setzt `m._slot_start_ts = target_slot_start` (Z.341) auf JEDE msg, dann
  `cycle_decoded.emit(messages)` (Z.345) + Schleife `message_decoded.emit(msg)`
  (Z.355) pro msg + `cycle_finished.emit()` (Z.358).
- `ui/mw_radio.py:61`: `decoder.message_decoded.connect(self.on_message_decoded)`
  — nur EINE Verbindung gefunden.
- `ui/mw_cycle.py:819 on_message_decoded(msg)`: im Zweig `msg.target == my_call`
  → `qso_panel.add_rx(...)` (Z.850 mit insert_call ODER Z.864 ohne). GANZ am
  Ende der Methode (Z.914): `self.qso_sm.on_message_received(msg)` — die
  QSO-State-Machine läuft also PRO msg.
- `ui/qso_panel.py:268 add_rx`: hängt Eintrag an `_entries` + `_render_entry`.
  Kein Dedup vorhanden.

================================================================================
OFFENE FRAGEN (das ist der Kern — bitte im Code beantworten)
================================================================================
F1. Wo entsteht die Doppelung, wenn der Decoder doch intern dedupliziert und nur
    EINE message_decoded-Verbindung existiert? Mögliche Quellen, bitte im Code
    prüfen/ausschließen:
    - Wird `_process_cycle` / der Decode pro Slot evtl. ZWEIMAL ausgeführt
      (z.B. zwei Antennen-Captures im Diversity-Operate, ratio-Pattern)? Suche
      nach einem zweiten Decode-/Capture-Pfad.
    - Kann `on_message_decoded` für dieselbe msg ein zweites Mal aufgerufen
      werden (Signal-Requeue, doppelte Emission, Re-Entry)?
    - Anzeige-seitig: ruft irgendein Pfad `add_rx`/`_render_entry` für denselben
      Eintrag zweimal? (z.B. Live-Append + Re-Render-Überlappung)
F2. **WICHTIG:** Wenn dieselbe msg zweimal durch `on_message_decoded` läuft,
    läuft auch `qso_sm.on_message_received(msg)` (Z.914) ZWEIMAL. Ist das ein
    funktionales Problem (doppelter State-Übergang / Counter / Report)? Falls ja,
    wäre Mikes „reiner Anzeige-Bug" FALSCH und ein Dedup NUR in `add_rx` würde
    das eigentliche Problem verschleiern. Bitte einschätzen, ob der Fix in
    `on_message_decoded` (vor add_rx UND vor on_message_received) sitzen muss
    statt in `add_rx`.
F3. Falls es WIRKLICH nur die Anzeige betrifft: Ist mein Dedup-Kriterium
    korrekt? Mein Plan (qso_panel.add_rx): einen RX-Eintrag verwerfen, wenn im
    SELBEN Slot (gleiche `utc`/`slot_start_ts`) bereits ein RX-Eintrag mit
    gleicher `message` existiert. Echte Wiederholungen in einem ANDEREN Slot
    (andere utc) bleiben (Mike v0.78: alle Rufe einzeln sichtbar). Edge-Cases?
F4. KISS: Wenn die Doppelung aus einem doppelten Decode-Aufruf stammt, wäre es
    sauberer, die Quelle abzustellen statt nachgelagert zu dedupen? Oder ist der
    Anzeige-Dedup pragmatisch das Richtige (Hobby-Tool)?

Mein aktueller Test (test_bug2_duplicate_rx.py, 5 Tests, 3 rot ohne Fix) prüft
NUR die Anzeige-Ebene (add_rx-Dedup). Falls F2 ein State-Machine-Problem zeigt,
muss ich Tests + Fix-Ort anpassen.

Angehängt: core/decoder.py, ui/mw_cycle.py, ui/qso_panel.py.
