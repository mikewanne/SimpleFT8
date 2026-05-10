# P26.CONNECT-MODAL — R1-Review-Auftrag

Du bist DeepSeek-R1. **Aufgabe: Plan-Kritik, NICHT Problem lösen.**

Lies den V2-Plan (`p26_connect_modal_v2.md`) und die mitgesendeten
Code-Dateien. Bewerte den Plan auf:

## Kritik-Aufträge (priorisiert)

### KRITISCH (Plan unbrauchbar wenn nicht gefixt)

1. **Race-Conditions** in der Modal-Lifecycle / Worker-Thread-Interaktion.
   Specially: Worker emittet Signal an Dialog der schon destroyed ist.
2. **Threading**: Cross-thread Qt-Signal/Slot mit AutoConnection — sind
   meine Annahmen korrekt? `attempt_changed.emit` aus Daemon-Thread an
   Dialog im GUI-Thread — feuert das wirklich wie erwartet?
3. **`exec()`-vs-`show()`-Falle**: ist `exec()` blockierend wirklich OK
   in `_start_radio()` das Teil des MainWindow `__init__`-Flusses ist?
   Stehen wir uns selbst auf den Füßen wenn das App-Init-Path wartet?
4. **Failed-State bei mehr als 10 Versuchen** (User klickt nicht):
   bleibt Modal ewig stehen mit "fehlgeschlagen" → Worker tot → kein
   Auto-Reconnect → App nutzlos? Mike kann ja noch "Beenden" oder
   "ohne Radio weiter" klicken — aber ist das die richtige UX?
5. **Connect-vor-exec()-Race**: meine Annahme ist `accept()` vor
   `exec()` setzt Result und exec() returned sofort. Bestätige oder
   widerlege mit Qt-Doku-Verweis.

### SOLLTE-FIX (Plan funktional aber unsauber)

6. **`auto_connect`-Signatur-Erweiterung**: Optional-Param mit Default
   None ist abwärtskompatibel — siehst du Probleme die ich übersehe?
7. **Disconnect-Handling nach `exec()`**: try/except für `disconnect()`
   ist Standard-Pattern bei Qt — bessere Variante?
8. **Test-Strategie**: 9 Tests reichen? Welche Edge-Cases fehlen?
9. **Logging in `simpleft8.log`**: V2 schlägt Modal-Open/Close-Logging
   vor (analog MessStatusDialog). Sinnvoll oder Overkill?

### KOENNTE (Verbesserung, kein Blocker)

10. **Hyperlink-Style** (QPushButton flat + underline) — bessere
    Variante (QLabel mit `setOpenExternalLinks(False)` und
    `linkActivated`)?
11. **Spinner-Animation** (3 Punkte via QTimer) — moderner / hübscher
    via QMovie + GIF, oder bleibt KISS-Variante?
12. **"Erneut versuchen"-Button im Failed-State** — Mike-Spec sagt nur
    Beenden/Weiter. Du darfst es ablehnen, ich akzeptiere keine
    UX-Erweiterungen die Mike nicht angefragt hat.

## Was NICHT in deinem Scope

- **Mess-Guard** (P27, separates TODO) — ignoriere V2-Hinweise dazu
- **Demo-Modus tiefergehend** (Mock-Radio, Fake-Daten) — Mike-Spec ist
  pragmatisch: Modal zu, App läuft. Keine über-engineered Demo-Layer.
- **i18n** — App ist komplett deutsch, nicht ändern.
- **Reconnect-Logik** (`reconnect_forever`) — bleibt unangetastet, Modal
  betrifft nur den ersten Connect.

## Anforderungen an dein Verdict

Liefere strukturiert:

- **KRITISCH-Findings:** mit Datei:Zeile-Verweis und konkreter Fix-
  Empfehlung. Wenn keiner: explizit "keine KRITISCH-Findings" sagen.
- **SOLLTE-FIX-Findings:** dito.
- **KOENNTE-Findings:** dito.
- **Verdict:** "Plan freigegeben für V3" oder "Plan überarbeiten weil ..."

Halluziniere keine Files die nicht mitgesendet wurden — wenn du was
brauchst, sag explizit "müsste prüfen".

## Mitgesendete Files

- `prompts/p26_connect_modal_v2.md` (V2-Plan)
- `radio/flexradio.py` (auto_connect, connected/disconnected Signals)
- `ui/mw_radio.py` (heutiger _start_radio + _connect_worker)
- `ui/mess_status_dialog.py` (Pattern-Vorlage)
