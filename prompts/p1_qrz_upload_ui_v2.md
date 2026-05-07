# P1.QRZ-UPLOAD-UI V2 — Self-Review

**Stand:** 2026-05-07.
**Workflow:** V1 → **V2 (diese Datei)** → R1 → V3 → Code.
**Aufgabe:** V1 als „frische KI" reviewen.

---

## L1 — V1 verpasst: Phase-1-Bestätigungsdialog war nicht im Akzeptanzkriterium

V1 §3.1 sagt nur „Sofort-Feedback bei Klick". Mike's Anweisung 07.05.
ist aber explizit: **Zwei-Phasen-Workflow**:
- Phase 1: Confirm-Dialog „X QSOs hochladen?" → User klickt OK
- Phase 2: Progress-Dialog mit Fortschritt

V1-Akzeptanzkriterium 1 wird zu zwei Kriterien:
- **AC-1a:** Klick auf btn_upload → Confirm-Dialog (modal-light, eigenes Theme,
  KEIN QMessageBox per Memory `feedback_qmessagebox_avoid.md`).
  Buttons: `[Abbrechen]` und `[Hochladen]`. Inhalt: Anzahl QSOs +
  Hinweis „Duplikate werden serverseitig erkannt".
- **AC-1b:** Bei `[Hochladen]` → Progress-Dialog erscheint (non-modal,
  StaysOnTopHint).

Default-Button im Confirm-Dialog: **`[Hochladen]`** (Enter-Key) — Mike
hat ja gerade aktiv geklickt, will hochladen. Default-Cancel waere
übervorsichtig.

---

## L2 — V1 §3.3 Progress-Granularität „alle 50 QSOs" ist zu grob

Bei 18.443 QSOs × ~200ms HTTP-Round-Trip = ~1 Stunde. Alle 50 QSOs =
369 Updates über 1h = **1 Update alle ~10s**. Im Progress-Bar wirkt das
zappelig, im Counter zu langsam.

**V2-Empfehlung:** alle **10 QSOs** (= alle ~2s = ~1843 Updates).
Performance-Cost vernachlässigbar (Signal-Emit ist <1ms).

R1 darf das überstimmen wenn 10 zu fein ist.

---

## L3 — V1 §5 Cancel-Verhalten: Race bei hängendem HTTP-Call

V1 sagt „kooperativ — laufender QSO wird abgewartet, dann Stop".
Aber: `qrz.py:48` hat `urlopen(req, timeout=10)`. Wenn QRZ.com 10s
nicht antwortet, hängt der Call 10s. Cancel reagiert dann erst nach 10s.

**V2-Klarstellung:**
- **Akzeptabel:** Cancel-Latenz max 10s (= HTTP-Timeout).
- **Alternative:** urlopen-Timeout auf 5s reduzieren — aber riskant
  (langsame Mobile-Verbindung beim Ferienhaus könnte fehlschlagen).
- **Nicht akzeptabel:** Thread hart killen (Python-Threads kann man
  nicht sauber killen).

V2-Vorschlag: Statusbar in Cancel-Phase: „Abbrechen — laufender
HTTP-Call wird abgewartet (max 10s) ...". Mike sieht dass es passiert.

---

## L4 — V1 §4.2 QThread vs ThreadPoolExecutor

V1 ließ es offen. **V2-Entscheidung: ThreadPoolExecutor** (KISS):
- ThreadPoolExecutor ist schon in `_on_qrz_upload` da (`self._qrz_pool`)
- Signal-Emit aus Worker-Thread funktioniert via Qt.QueuedConnection
- QThread wäre Overengineering für diesen Use-Case

Pattern wie folgt:

```python
# In Worker-Function (läuft im ThreadPool):
def _do_bulk(records, progress_signal, cancel_event):
    ok, fail, dup = 0, 0, 0
    for i, rec in enumerate(records):
        if cancel_event.is_set():
            break
        result = client.upload_qso_from_dict(rec)
        # Counter aktualisieren
        ...
        if i % 10 == 0:
            progress_signal.emit(i+1, len(records), ok, dup, fail)
    progress_signal.emit(...)  # final
    return (ok, dup, fail, cancel_event.is_set())
```

`progress_signal` ist `Signal(int, int, int, int, int)` aus
**neuem QObject-Wrapper** (Signals brauchen QObject-Parent).

---

## L5 — V1 §4.3 Dialog: zusätzliche Spezifikation nötig

V1 hat Stub. V2 konkretisiert:

```python
class QRZUploadDialog(QDialog):
    cancel_clicked = Signal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QRZ.com Upload")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet("...")  # #1a1a2e Theme

        # Layout:
        # ┌─────────────────────────────────────┐
        # │  QRZ.com Upload                     │
        # │                                     │
        # │  4123 von 18443 QSOs (22%)          │  <- progress_label
        # │  ████████░░░░░░░░░░░░░░░░░░░░░      │  <- progress_bar (QProgressBar)
        # │                                     │
        # │  Neu: 4100   Dup: 23   Fehler: 0    │  <- counter_label
        # │                                     │
        # │             [ Abbrechen ]           │  <- btn_cancel
        # └─────────────────────────────────────┘

    @Slot(int, int, int, int, int)
    def update_progress(self, current, total, ok, dup, fail): ...

    @Slot(int, int, int, bool)
    def set_finished(self, ok, dup, fail, cancelled): ...
        # Buttons: btn_cancel weg, btn_close erscheint
        # Title: "Fertig" oder "Abgebrochen"
        # Auto-Close: 10s (siehe L12)
```

---

## L6 — V1 verpasst: Konflikt mit `_qrz_upload_single` (Auto-Upload pro QSO)

`mw_qso.py:397` hat `_qrz_upload_single` — wird nach JEDEM QSO
automatisch aufgerufen wenn Auto-Upload aktiv ist. Beide nutzen
`self._qrz_pool` (max_workers=1) → würden serielle Queue bilden. Bei
Bulk läuft 1h → Auto-Uploads stauen sich.

**V2-Klarstellung:** Bulk-Upload UND Auto-Upload (1 QSO) müssen
koexistieren:
- **Lösung A (KISS):** Während Bulk-Upload sind Auto-Uploads ausgesetzt.
  `_qrz_upload_single` checkt `self._qrz_bulk_active`-Flag und logt
  „Auto-Upload uebersprungen — Bulk laeuft" statt zu queuen.
  Nach Bulk-Ende: ab nächstem QSO wieder Auto-Upload.
- **Lösung B:** Separate Pools (Bulk- und Single-Pool). Mehr Threads,
  aber Auto-Upload reagiert sofort.

**V2-Empfehlung A** — Hobby-Tool, max 1× pro Tag Bulk, dann normal weiter.

---

## L7 — V1 §3.2 „Klick-Sperre" mehrstufig absichern

V1 sagt nur `btn_upload.setEnabled(False)`. Sicherer:

1. `_qrz_bulk_active = True` Flag (instance) — defensive Belt-and-Suspenders
2. `btn_upload.setEnabled(False)` — UI-Pfad
3. `_on_qrz_upload` Re-Entry-Check: `if self._qrz_bulk_active: return`

Falls Bug existiert wo Button enabled bleibt → Flag fängt's ab.

---

## L8 — V1 §3.5 Auto-Close 3s zu kurz für lange Uploads

Mike-Pattern Calibration-Done: 3s Auto-Close. Aber: bei 18.443 QSOs ×
1 Stunde Upload ist Mike eventuell nicht am Bildschirm. Endergebnis
sollte sichtbar bleiben.

**V2-Vorschlag:** **10 Sekunden Auto-Close** + `[Schliessen]`-Button
für sofortigen Close. Mike kann lesen ohne Hetze, aber kein Stuck-Dialog.

R1 entscheidet final 3s vs 10s vs OK-only.

---

## L9 — V1 §7.5 Worker-Lifecycle: ThreadPool wiederverwenden

Bestehender Code: `if not hasattr(self, '_qrz_pool'): self._qrz_pool = ThreadPoolExecutor(max_workers=1)`. Pool wird 1× erstellt, ewig gehalten.

**V2-Klarstellung:** Bei App-Close muss Pool sauber gestoppt werden
(`shutdown(wait=False)`) sonst hängt der Process beim Beenden. Test
für `closeEvent`-Cleanup nötig.

---

## L10 — V1 fehlt: Compact-Strategie

Mike geht eventuell essen während Workflow läuft. V3 muss
Compact-fest sein:
- Alle Diffs konkret mit Datei:Zeile-Ranges
- Memory-File `project_p1_qrz_upload_ui_in_progress.md` für post-Compact
- Implementations-Reihenfolge

---

## L11 — V1 §7 Tests-Liste erweitern

V1 hatte 4 Tests. V2 ergänzt:
- `test_confirm_dialog_cancel_aborts_upload` — Phase 1 Cancel
- `test_second_click_blocked_during_upload` — Klick-Sperre via Flag
- `test_qrz_pool_reused_across_calls` — Worker-Lifecycle
- `test_auto_upload_skipped_during_bulk` — L6 Konflikt
- `test_dialog_close_event_clean_pool_shutdown` — L9 App-Close

→ **9 Tests** total.

---

## L12 — V1 nicht erwähnt: Persistenz-Cancel-Restart-Verhalten

Mike fragte „die 50 die wir hochgeladen haben merken". V1 §6 listet
das als Out-of-Scope (Resume-After-Crash). Mike-Diskussion 07.05.
bestätigt: **KISS — keine Persistenz, QRZ filtert serverseitig**.

V3 muss das explizit dokumentieren als „bewusste Entscheidung gegen
Resume-Funktion (P1.QRZ-RESUME als optionales Future-Feature)".

---

## Pruefauftraege fuer R1

1. **Phase-1-Confirm-Dialog Default-Button:** `[Hochladen]` (Enter)
   oder `[Abbrechen]` (Sicherheit)?
2. **Progress-Granularität:** alle 10 QSOs (V2-Vorschlag) oder anders?
3. **Cancel-Pfad:** akzeptable Latenz max 10s (HTTP-Timeout) ODER
   urlopen-Timeout auf 5s reduzieren?
4. **Worker:** ThreadPoolExecutor + Signal-Emit (V2-Vorschlag) oder
   QThread für saubereren Lifecycle?
5. **Auto-Upload-Konflikt:** Lösung A (skip waehrend Bulk) oder B
   (separate Pools)?
6. **Auto-Close:** 3s, 10s oder OK-only? Bei langem Upload kann Mike
   das Endergebnis verpassen.
7. **Dialog-Position:** Center-on-Parent oder Mike-Pattern (raise_+
   activateWindow für macOS-Spaces)?
8. **Race bei App-Close während Bulk:** ThreadPool-Shutdown blockierend
   oder daemon-thread `shutdown(wait=False)`?
9. **Compact-Plan:** Diffs konkret in V3, Reihenfolge festlegen.

---

## Zusammenfassung der V2-Korrekturen für V3

1. **Phase-1-Confirm-Dialog ergänzen** (L1)
2. **Progress alle 10 QSOs** statt 50 (L2)
3. **Cancel-Latenz dokumentieren** (max 10s wegen HTTP-Timeout) (L3)
4. **ThreadPoolExecutor + Signal-Emit** als Worker (L4)
5. **Dialog-Spec konkretisiert** mit Layout + Methoden (L5)
6. **Auto-Upload-Konflikt: Skip-Pattern** (L6)
7. **Klick-Sperre 3-fach: Flag + Button + Re-Entry-Check** (L7)
8. **Auto-Close 10s** statt 3s (L8)
9. **Pool-Lifecycle in closeEvent** (L9)
10. **Compact-Strategie** (L10)
11. **Tests auf 9 erweitert** (L11)
12. **Resume explizit out-of-scope** (L12)

---

**Workflow-Status:** V2 fertig. Weiter mit R1 (DeepSeek-Review).
