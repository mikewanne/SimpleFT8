# P26.CONNECT-MODAL — Final-R1-Review (Code-Review)

Du bist DeepSeek-R1. **Code-Review** des fertigen P26-Codes vor Push.

V3-Plan + R1-Pre-Code-Findings sind eingearbeitet. Alle 14 Tests grün
(1056 → 1070). Du bekommst die geänderten/neuen Files. Bitte review
auf Push-Reife:

## Review-Auftrag

### KRITISCH (Push blockieren)

1. **Threading-Race-Conditions** im finalen Code:
   - Worker emittet Signal nach Dialog-Destroy → wird try/except RuntimeError
     korrekt gehandhabt?
   - Lokale `dlg`-Referenz im Worker — atomar genug?
   - `_connect_dialog = None` nach `exec()` — Race mit noch laufendem
     Worker-Thread?

2. **Modal-Lifecycle / `exec()`-Interaktion:**
   - `_start_radio()` deferred via `QTimer.singleShot(0, ...)` — Race mit
     anderem Init-Code?
   - Reentrancy: kann `_start_radio()` versehentlich 2× gerufen werden?

3. **Disconnect-Cleanup:**
   - `self.radio.connected.disconnect(self._connect_dialog.accept)` — was
     wenn nie connectet wurde (Test-Fall)?

4. **`auto_connect`-Signatur-Erweiterung:**
   - Default-Param `on_attempt=None` — bestehender Aufrufer
     `radio.auto_connect(max_retries=10, retry_delay=3.0, on_attempt=...)`
     ist Keyword-Arg, kein Positional-Arg. Save?

### SOLLTE-FIX

5. **Test-Coverage**:
   - 14 Tests reichen? Welche Edge-Cases fehlen vor Push?
   - T10 (emit nach Dialog-Destroy) und T11 (connected-during-exec) —
     sind die Test-Patterns sauber?

6. **Code-Style / Defensive-Coding:**
   - `try/except` zu breit (Exception statt RuntimeError)?
   - Logging-Aufrufe? heute nur `print` — soll structured logging?

### KOENNTE

7. UX-Polish:
   - Spinner-Animation: 500ms zu schnell/langsam?
   - "ohne Radio weiter" — verständlich genug?
   - Failed-State-Text — klar genug?

## Liefer-Format

- KRITISCH: Datei:Zeile + Fix-Empfehlung. "Push blockieren" oder "Push freigegeben".
- SOLLTE: dito, "soll vor Push fixen" oder "kann nach Push".
- KOENNTE: optional.
- Verdict: "Push freigegeben" / "Push blockieren wegen X".

## Mitgesendete Files

- `radio/flexradio.py` (auto_connect mit on_attempt)
- `ui/connect_status_dialog.py` (NEU)
- `ui/mw_radio.py` (_start_radio + _connect_worker)
- `ui/main_window.py` (deferred singleShot + Attribut)
- `tests/test_p26_connect_modal.py` (14 Tests)

Keine Halluzinationen — wenn du eine Datei brauchst, sag explizit
"müsste prüfen". Code ist Referenz, nicht meine Beschreibung.
