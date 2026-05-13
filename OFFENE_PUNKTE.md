# Offene Punkte — Stand 13.05.2026 (nach v0.97.13)

Übersicht der nächsten möglichen Aufgaben. Sortiert nach
Aufwand + Logik. Full backlog steht in `TODO.md`, hier nur die
realistischen Nächste-Schritte-Kandidaten.

---

## 🟢 P49 — OMNI-Pretrigger aus Settings (direkter P48-Followup)

**Aufwand:** ~30 Min — ein eigener Mini-Workflow.

**Was es ist:** In `core/omni_cq.py` steht die letzte hartcodierte
FlexRadio-Konstante:
```python
_OMNI_PRETRIGGER_OFFSET_S = 1.3
```
Die ist mathematisch identisch mit `tx_buffer_s` aus P48 — beide
kompensieren den FlexRadio-VITA-49-TX-Buffer.

**Warum jetzt sinnvoll:** Wir haben in P48 schon `tx_buffer_s` in
Settings ausgelagert und Encoder umgestellt. OMNI ist die letzte
Stelle wo der gleiche Wert nochmal separat steht. Wenn jemand mal
einen IC-7300-Fork bauen will, muss er nur **einen** Wert in Settings
ändern statt zwei Stellen im Code finden.

**Risiko:** sehr klein — gleiche Pattern wie P48, gleiche Konstante,
gleiche Defensiv-Logik (`.get()`-Kette).

**Akzeptanzkriterium:** OMNI-CQ feuert TX zur gleichen Slot-Position
wie vor dem Refactor. 2-3 neue Tests.

---

## 🟢 Bundle B — UI-Persistenz (3 kleine UX-Fixes als Bundle)

**Aufwand:** ~2.5h zusammen — analog Bundle A.

Drei voneinander unabhängige UI-Sachen die einzeln zu klein für einen
vollen Workflow sind. Als Bundle ein voller V1→V2→R1→V3 mit drei
Akzeptanzkriterien.

### P24 — Letzten RX-Mode merken
**Symptom:** App startet IMMER in Normal-Modus, egal in welchem Modus
sie beendet wurde (Diversity Standard oder DX).
**Fix:** Settings-Key `last_rx_mode`, `closeEvent` speichert, Init lädt.

### P32 — RX-Panel-Spalten speichern
**Symptom:** Rechtsklick auf Spaltenüberschrift im RX-Panel öffnet
Auswahl (km, DT, Zeit, Land...). Wahl geht beim Neustart verloren.
**Fix:** Settings-Key `rx_panel_visible_columns` (Liste), gleicher
Pattern wie andere Settings-Persistenz.

### P29 — OMNI-CQ Even/Odd optisch trennen
**Symptom:** OMNI sendet abwechselnd Even/Odd-Slot, im QSO-Panel
laufen die `→ Sende CQ ↻N`-Zeilen ohne sichtbare Trennung
hintereinander.
**Fix:** Leerzeile bei Paritäts-Wechsel + Even-TX-Zeilen minimal
dunkler (`#CC8800` statt `#FFAA00`).

**Risiko:** Bundle: keins — drei isolierte UX-Sachen ohne
Architektur-Wirkung.

---

## 🟡 Bundle C — Reihenfolge & Cache (2h, Field-Test-light)

### P33 — QSO-Komplett-Zeile in falscher Reihenfolge
**Symptom:** Im QSO-Panel erscheint `✓ QSO mit X komplett` NACH dem
nächsten `→ Sende CQ ↻N` statt davor.
**Wurzel (vermutet):** `qso_confirmed`-Signal feuert erst nach
Höflichkeits-73 statt sofort bei 73-Empfang.
**Fix:** Signal früher emittieren ODER `add_qso_complete` mit
Zeitstempel + Sortierung.

### P10 — PSK-Backoff-Reset bei Bandwechsel
**Symptom:** Nach Bandwechsel braucht PSK-Reporter zu lange bis er
wieder pollt — exponentielles Backoff vom alten Band läuft weiter.
**Fix:** Bandwechsel → `_backoff = INITIAL_INTERVAL` in
`core/psk_reporter.py`.

**Risiko:** klein — beide Bugfixes lokal.

---

## 🟡 P46 — Bandpilot Normal-Reintegration (2-3h, eigener Workflow)

**Was es ist:** Bandpilot vergleicht aktuell nur Diversity Standard
vs DX. Mike's Vision: „ganz oder gar nicht" — wenn schon Pilot, dann
alle 3 Modi (Normal + Std + DX).

**Bedingung:** Normal-Mode wird nur in den Vergleich aufgenommen wenn
er die Mindest-Datenbasis erfüllt (`MIN_DAYS_HOUR=3`,
`MIN_CYCLES_HOUR=20` — gleiche Schwellen wie die anderen Modi).
Sonst 2-Wege-Vergleich wie heute.

**Mehrwert:** Für dünne Datenbasis-Bänder (17m/12m), resonante
20m-Antenne in ruhigen Stunden, Single-Antenna-Setups — etwa 5% der
Bänder, aber dort fairere Pilot-Entscheidung.

**Files:** `core/mode_recommender.py` (`compare_modes()` Normal-Slot
reinholen), `ui/main_window.py` (3-Wege-Switch), Settings-Dialog
(Beschreibung anpassen), Tests.

**Risiko:** mittel — Bandpilot-Logik ist komplex, R1 hat schon mal
gewarnt vor 2-3-Datenpunkt-Volatilität.

---

## 🔴 P12 — QSO-Postprocessing-Async-Hang (besteht seit Wochen)

**Symptom:** Nach manchen QSOs hängt die App ~1-3 Sekunden bevor
nächster Slot startet. Mike: „besteht schon Wochen".

**Verdacht:** ADIF-Save oder QRZ-Worker blockt im GUI-Thread statt
asynchron zu laufen.

**Aufwand:** 2-3h Diagnose + Fix. Field-Test-pflicht.

---

## 🔴 P27 — Mess-Guard vor Antennen-Vergleich

**Symptom:** Mess-Pipeline startet manchmal obwohl Voraussetzungen
nicht erfüllt sind (kein Radio, falsches Band, Hunt läuft).

**Fix:** Vorab-Check in `_handle_diversity_measure` ob alle
Voraussetzungen passen, sonst defer + Toast.

**Aufwand:** 1-2h. Pattern aus P21-Skip-Workaround verallgemeinern.

---

## Empfehlung Reihenfolge

1. **P49** (30min, hängt direkt am frischen P48 ein)
2. **Bundle B** (2.5h, drei UX-Verbesserungen die Mike täglich sieht)
3. **Bundle C** (2h, zwei Bugs am QSO-Pfad — sichtbar nach jedem QSO)
4. **P46 Bandpilot** (2-3h, mittlerer Mehrwert für 5% der Bänder)
5. **P12 Async-Hang** + **P27 Mess-Guard** wenn Lust auf
   Diagnose-Arbeit besteht.

Triviale Sachen werden alle als voller Workflow gefahren —
Trivial-Klausel greift bei keinem dieser Punkte (mindestens 2
Akzeptanzkriterien oder mehrere Dateien betroffen).
