# P1.QRZ-UPLOAD-UI V1 — QRZ-Upload mit Status-Feedback + Klick-Sperre

**Stand:** 2026-05-07.
**Workflow:** **V1 (diese Datei)** → V2 (Self-Review) → R1 (DeepSeek) → V3 → Compact → Code.
**Mike-Anweisung 07.05.:** „brauche ne Meldung Status der irgendwas und
auch nur einmal gestartet werden darf das".

---

## 1. Aktueller Zustand (Field-Test 07.05.2026 10:35 UTC)

### Symptom

Mike klickt im Logbook auf QRZ-Button — keine sichtbare Reaktion. Klickt
mehrmals (insgesamt 8×) weil er nicht weiß ob's funktioniert. Tatsaechlich
hat JEDER Klick einen Bulk-Upload-Job in die ThreadPool-Queue gepusht.

### Beweis aus Output-Log

```
[QRZ] Upload gestartet (18443 QSOs)
[QRZ] Upload gestartet (18443 QSOs)
... 8× hintereinander
```

Bei `max_workers=1` werden die 8 Jobs sequenziell abgearbeitet:
8 × 18.443 QSOs × ~200ms Round-Trip = **~8 Stunden Duplikat-Spam an QRZ.com**.

### Code-Pfad (`ui/mw_qso.py:418-455` `_on_qrz_upload`)

```python
def _on_qrz_upload(self):
    api_key = self.settings.get("qrz_api_key", "")
    if not api_key:
        QMessageBox.warning(self, "QRZ.com", "...")
        return
    records = self.qso_panel.logbook._all_records  # 18443 QSOs
    if not records:
        self.statusBar().showMessage("Keine QSOs zum Hochladen.", 5000)
        return

    # Hier kommt der Bug:
    self._qrz_pool = ThreadPoolExecutor(max_workers=1)  # bei 1. Aufruf
    client = self._get_qrz_client()
    self.statusBar().showMessage(
        f"QRZ Upload: {len(records)} QSOs...", 30000)  # ⚠ wird ueberschrieben

    def _do_bulk():
        ok, fail, dup = 0, 0, 0
        for rec in records:
            result = client.upload_qso_from_dict(rec)
            ...
        return f"QRZ Upload: {ok} neu, {dup} Duplikate, {fail} Fehler"

    future = self._qrz_pool.submit(_do_bulk)
    future.add_done_callback(...)
    print(f"[QRZ] Upload gestartet ({len(records)} QSOs)")
```

### Probleme

| # | Problem | Auswirkung |
|---|---|---|
| **A** | Statusbar-Message wird sofort überschrieben (Bandwechsel/Diversity-Updates schreiben permanent in Statusbar) | Mike sieht keine Reaktion |
| **B** | btn_upload bleibt klickbar während Upload | Mehrfach-Klicks queuen N Jobs → riesiger Duplikat-Spam |
| **C** | Kein Progress-Feedback (X von Y QSOs) | Bei 18.443 QSOs ~1 Stunde Black-Box |
| **D** | Kein Cancel-Mechanismus | Falsch geklickt = Job läuft komplett durch |
| **E** | Keine klare Fertig-Meldung | Done-Callback setzt nur 10s-Statusbar — wird auch überschrieben |

---

## 2. Mike's Vision (aus Anweisung 07.05.)

> „brauche ne Meldung Status der irgendwas und auch nur einmal gestartet
> werden darf das"

Klare Anforderungen:
1. **Sichtbares Status-Feedback** (Meldung, die NICHT von anderen UI-Updates
   überschrieben wird)
2. **Klick-Sperre** (Single-Click-Garantie — wenn Upload läuft, kein
   weiterer Job kann starten)

Mike-Pattern aus bestehender App:
- DXTuneDialog: non-modal QDialog mit `WindowStaysOnTopHint` + GUI-Lock
- Calibration-Done: non-modal Auto-Close-Dialog (3s, mit `raise_+activateWindow`)

---

## 3. Akzeptanzkriterien

1. **Sofort-Feedback bei Klick:** binnen <100ms erscheint sichtbares
   Element das den Upload bestätigt. Kann Dialog ODER Statusbar-Pin sein
   (V2-Entscheidung).

2. **Klick-Sperre:** btn_upload ist während laufenden Upload `setEnabled(False)`.
   Nach Abschluss/Cancel/Fehler: wieder enabled.

3. **Progress-Anzeige:** Update mindestens alle 50 QSOs mit
   `"X von Y QSOs (P%) — Z neu, W dup, V fail"`.

4. **Cancel-Button:** kooperativ — laufender QSO wird abgewartet, dann
   Stop. Cancel-Statusbar: `"QRZ-Upload abgebrochen bei X von Y"`.

5. **Fertig-Meldung:** non-modal Auto-Close-Dialog (3s) mit Endergebnis
   `"QRZ-Upload fertig: X neu, Y Duplikate, Z Fehler"`. Wie
   `_show_calibration_done` Pattern.

6. **Tests grün** + neue Tests für UI-Sperre + Cancel-Pfad.

---

## 4. Betroffene Module/Dateien (vermutet)

### 4.1 `ui/mw_qso.py`
- `_on_qrz_upload` Z.418-455 komplett refactoren
- Neue Methoden: `_on_qrz_progress(current, total, ok, dup, fail)`,
  `_on_qrz_finished(ok, dup, fail, cancelled)`, `_on_qrz_cancel()`

### 4.2 `core/qrz_upload_worker.py` (NEU)
QThread oder ThreadPool-Worker mit:
- `progress_signal = Signal(int, int, int, int, int)` (current, total, ok, dup, fail)
- `finished_signal = Signal(int, int, int, bool)` (ok, dup, fail, cancelled)
- `cancel_event` als Threading.Event
- Bulk-Loop liest cancel_event, stoppt sauber

### 4.3 `ui/qrz_upload_dialog.py` (NEU)
Non-modal QDialog mit:
- Progress-Label `"X von Y (P%)"`
- Counter-Labels `"Neu: X | Dup: Y | Fehler: Z"`
- Cancel-Button
- WindowStaysOnTopHint
- Signal: `cancel_clicked`
- Slot: `update_progress(current, total, ok, dup, fail)`
- Slot: `set_finished(ok, dup, fail, cancelled)` → schließt nach 3s

### 4.4 `ui/logbook_widget.py`
- btn_upload braucht keinen Aufrufer-Eingriff — die Sperre macht
  `_on_qrz_upload` direkt via `setEnabled(False)`.
- ALTERNATIV: Public-Methode `set_upload_enabled(bool)` exposieren.

### 4.5 Tests
- `tests/test_qrz_upload_ui.py` (NEU):
  - `test_button_disabled_while_uploading`
  - `test_progress_signal_emits_periodically`
  - `test_cancel_stops_upload_cleanly`
  - `test_finished_dialog_auto_closes`
- Bestehende QRZ-Tests (falls vorhanden) anpassen

---

## 5. Randbedingungen

- **Hardware-Schutz:** keine TX-Aktion betroffen, nur HTTP-Calls.
- **Thread-Safety:** QRZ-Client ist sync-only. Worker im Background-Thread.
  GUI-Updates per Signal/Slot mit Qt.QueuedConnection.
- **QRZ-API-Rate-Limits:** keine offiziellen, aber Mike rate-limit
  freundlich → kein Spam-Schutz nötig.
- **Cancel-Race:** Mike klickt Cancel während HTTP-Call läuft →
  cancel_event wird gesetzt, aktueller Call läuft fertig (~200ms),
  dann Loop-Exit. Acceptable.
- **Progress-Granularität:** alle 50 QSOs Signal emit. 18.443 / 50 = 369
  Updates → ~1 Update alle 10 Sekunden bei 200ms/QSO. Sinnvoll.

---

## 6. Nicht im Scope

- QRZ.com-Pre-Check (vor Upload schauen welche QSOs schon drin sind) →
  spart Bandbreite, aber Aufwand. KISS: alle hochladen, Server filtert.
- Selektiver Upload (nur QSOs nach Datum X) → Mike-only Tool, kein Bedarf.
- Resume-After-Crash (Cache wo Upload aufhörte) → KISS, App neu starten = von vorn.
- Async-Variante (`aiohttp` statt `urllib`) → Overengineering für Hobby-Use.

---

## 7. Offene Fragen für V2/R1

1. **Modal vs non-modal Dialog?** Mike-Pattern: non-modal mit
   StaysOnTopHint (wie DXTuneDialog).
2. **Auto-Close oder OK-Klick?** Mike-Pattern: Auto-Close (wie
   Calibration-Done).
3. **Cancel-Verhalten:** sofort hart abbrechen ODER laufenden QSO
   abwarten? V1-Vorschlag: kooperativ (Sauberkeit).
4. **Progress-Granularität:** alle 50 QSOs OK oder zu selten/oft?
5. **Worker-Implementierung:** QThread (Qt-nativ) oder ThreadPoolExecutor
   mit Signal-Emit (einfacher)?
6. **Statusbar zusätzlich oder nur Dialog?** V1-Vorschlag: nur Dialog
   (Statusbar wird eh überschrieben).

---

**Workflow-Status:** V1 fertig. Weiter mit V2 (Self-Review).
