Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# Review-Auftrag: SimpleFT8 P2.OMNI-SEQUENCER

## Kontext

SimpleFT8 ist ein FT8-Amateurfunk-Client (Python/PySide6, 1014 Tests).
OMNI-CQ sendet CQ auf Even- UND Odd-Slots (5-Slot-Pattern) statt nur einem —
beide Hörergruppen werden erreicht. Feature ist Diversity-only, Easter-Egg aktiviert.

## Korrektes 5-Slot-Pattern (Design-Spec)

```
Block 1 (Even-First, 80 Zyklen):
  Pos 0: Even TX  — CQ auf Even-Slot
  Pos 1: Odd  TX  — CQ auf Odd-Slot
  Pos 2: Even RX  — hören
  Pos 3: Odd  RX  — hören
  Pos 4: Even RX  — hören  ← nahtloser Übergang zu Block 2

Block 2 (Odd-First, 80 Zyklen):
  Pos 0: Odd  TX  — CQ auf Odd-Slot
  Pos 1: Even TX  — CQ auf Even-Slot
  Pos 2: Odd  RX  — hören
  Pos 3: Even RX  — hören
  Pos 4: Odd  RX  — hören  ← nahtloser Übergang zu Block 1

Bilanz: Even/Odd über beide Blöcke ausgeglichen ✓
Kein Slot verloren beim Block-Übergang ✓
```

## Root Cause (Zeilen verifiziert)

`on_cycle_end()` (`qso_state.py:322`) ruft `_send_cq()` wenn State=CQ_WAIT
und cq_mode=True.

`_send_cq()` (Z.177) setzt State→CQ_CALLING VOR `send_message.emit()`.

`_on_send_message()` (`mw_qso.py:311`) prüft per `should_tx()` ob OMNI diesen
Slot überspringen will → RX-Slot → return ohne TX.

`on_message_sent()` wird nie aufgerufen → State bleibt CQ_CALLING →
nächster `on_cycle_end()` feuert nicht (State ≠ CQ_WAIT) → OMNI-Loop tot.

## Geplante Änderung (6 Dateipunkte)

### 1. core/qso_state.py — auto_cq_enabled Flag

Neues Attribut `auto_cq_enabled: bool = True` (Default True).

In `on_cycle_end()` Z.322 wird die Bedingung erweitert:
```python
if self.qso.timeout_cycles >= 1 and self.cq_mode and self.auto_cq_enabled:
    self._send_cq()
```

Neue öffentliche Methode:
```python
def omni_drive_cq(self, target_even: bool) -> bool:
    if self.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
        return False  # QSO läuft — kein CQ
    self.cq_mode = True
    self.auto_cq_enabled = False  # OMNI treibt — kein Auto-Trigger
    self._omni_target_even = target_even  # für _on_send_message
    self._send_cq()
    return True
```

`_omni_target_even: bool | None = None` — neues Attribut, in `__init__`.
In `_on_send_message()` (mw_qso.py) wird statt `should_tx()` dieses Attribut
gelesen um Encoder-Parität zu setzen.

### 2. ui/mw_cycle.py:592+ — OMNI-Slot-Treiber

Nach `advance()` (Z.592) neuer Block:
```python
if self._omni_tx.active and not _in_qso:
    send_ok, target_even = self._omni_tx.should_tx()
    if send_ok:
        self.qso_sm.omni_drive_cq(target_even)
    # RX-Slot: nichts tun, State bleibt CQ_WAIT
```

### 3. ui/mw_qso.py:308-328 — OMNI-Filter vereinfachen

Den `if self._omni_tx.active:` Block ersetzen durch:
```python
if message.startswith("CQ ") and self.qso_sm._omni_target_even is not None:
    self.encoder.tx_even = self.qso_sm._omni_target_even
    self.qso_sm._omni_target_even = None  # einmalig konsumieren
```

### 4. ui/main_window.py:703-707 — start_cq() entfernen

`self.qso_sm.start_cq()` nach `enable()` entfernen.
OMNI treibt selbst via `omni_drive_cq()`.

### 5. ui/main_window.py — _on_omni_stopped()

Zusätzlich `self.qso_sm.auto_cq_enabled = True` setzen (Normal-CQ wieder aktiv).

## Akzeptanzkriterien

1. OMNI aktivieren → nächster TX-Slot: CQ auf korrekter Parität
2. Pos 1 → CQ auf zweiter Parität, kein Aussetzer
3. Pos 2/3/4 → State = CQ_WAIT (nicht CQ_CALLING)
4. Antwort in RX-Slot → normaler QSO-Ablauf unverändert
5. Nach QSO → OMNI-Resume, kein Normal-CQ-Start
6. HALT → IDLE + auto_cq_enabled=True zurückgesetzt
7. Block-Wechsel nach 80 Zyklen korrekt

## Nicht im Scope (NICHT als Finding melden)

- Normal-CQ, Auto-Hunt, Manual-Hunt — unverändert
- Caller-Queue, QSO-Subroutine — unverändert
- Block-Wechsel-Logik in omni_tx.py — unverändert
