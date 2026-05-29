# Final-R1 — P158 Implementierung (Code-Review vor Push-Freigabe)

Du bist Senior-Reviewer. Der Plan wurde in Design-R1 freigegeben (0 Blocker).
Hier ist die **tatsächlich implementierte Änderung** als Diff + die zwei
Kern-Dateien im Volltext. Prüfe ob die Umsetzung dem Plan entspricht und
**keine Regression / Race / KISS-Verstoß** enthält. Gib ein klares Verdikt:
**PUSH FREIGEBEN** oder **NACHBESSERN** + Findings nach Schweregrad.

## Kontext (Plan, R1-freigegeben)
P158: Fremde Station B ruft uns während Auto-Hunt ein QSO mit A fährt → die
„← Empf."-Zeile im QSO-Log wird klickbar (QTextBrowser-Anchor). Klick merkt B
vor (`auto_hunt._insert_pending_call`), A läuft ZU ENDE, dann wird B über den
bestehenden `_on_station_clicked`-Pfad gerufen (= Auto-Hunt-Pause + Auto-Resume
gratis). KEIN Abbruch von A. Hardware: kein TX-Antennen-Pfad berührt (ANT1-Regel).

Eingebaute Design-R1-Findings: 🟠1 Dict-Cleanup bei Stop, 🟠2 their_call-Null-
Check, F1 QTextBrowser statt QTextEdit-Subklasse, F2 Hook am Ende von
_on_qso_confirmed/_on_qso_timeout.

## Prüf-Schwerpunkte
1. **Klickbarkeits-Logik** `_p158_is_insertable_caller`: korrekt + vollständig?
   (genau der „B-wird-von-State-Machine-ignoriert"-Fall: Auto-Hunt aktiv, nicht
   manual_override, aktives QSO mit anderem their_call, kein 73/rr73)
2. **Klick-Guard** `_on_hunt_insert_clicked`: deckt veraltete Zeile + Klick-
   während-B-QSO ab? Lookup im Dict robust?
3. **Einschub-Trigger** `_p158_maybe_start_inserted_call`: feuert nur wenn
   Auto-Hunt noch aktiv (deferred Stop/HALT/Band → Puffer verworfen)? Reuse von
   `_on_station_clicked(msg)` korrekt (TX-frei zum Hook-Zeitpunkt)?
4. **Puffer-Lifecycle** auto_hunt: set/take/stop-Clear konsistent? Letzter-Klick-
   gewinnt ok?
5. **QTextBrowser-Umstellung**: bricht nichts Bestehendes (Kontext-Menü,
   _rerender_all alle 30s, Plain+HTML-Mischung, Auto-Scroll)? `_append_anchor_line`
   HTML-escaped korrekt?
6. **Dict-Cleanup** `_p158_insertable`: in _on_auto_hunt_stopped + nach Konsum —
   reicht das? Leak/Stale-Risiko?
7. **P144-Methode** `_p144_abort_and_skip` wurde während der Implementierung
   versehentlich gespalten und wieder repariert — prüfe ob sie jetzt
   vollständig + korrekt ist (encoder.abort, _pending_tx_log=None, cancel,
   clear_current_target, „⏭"-add_info, debug_log).

Falls etwas fehlt oder gefährlich ist: konkret benennen. Sonst: PUSH FREIGEBEN.
