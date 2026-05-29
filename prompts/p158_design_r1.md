# Design-Review (R1) — P158: Wartende Station ins Auto-Hunt-QSO einschieben

Du bist Senior-Code-Reviewer für ein FT8-Hobby-Funker-Tool (PySide6/Qt,
Python). **KISS ist oberstes Gebot — kein Contest-Tool, keine Power-User-
Features.** Hardware-Regel: TX läuft IMMER über ANT1 (im Code verriegelt),
P158 fasst keinen TX-Antennen-Pfad an.

Bewerte den folgenden **konkreten Implementierungs-Plan V1** (code-verifiziert
gegen den echten Stand). KEINEN Code generieren. Liefere: Findings nach
Schweregrad (🔴 Blocker / 🟠 sollte / 🟡 nice), Race-Conditions, Edge-Cases,
KISS-Verstöße, und beantworte die 3 expliziten Fragen am Ende. Sei kritisch,
aber bestätige auch was tragfähig ist. Code ist Referenz, nicht Annahmen.

---

## Szenario (Mike, Field-beobachtet)

Auto-Hunt fährt ein QSO mit Station A. Eine FREMDE Station B ruft Mich (DA1MHH)
dazwischen → im QSO-Log-Fenster erscheint die Zeile `← Empf. DA1MHH F5MYK IN97`.
Heute geht B verloren. Mike will B per Klick auf genau diese Zeile vormerken;
A wird ZU ENDE gefunkt (kein Abbruch), dann wird B gerufen, danach läuft
Auto-Hunt automatisch weiter.

**Mike-Philosophie:** RX-Liste = aktiv jagen; QSO-Fenster = passiv höflich
antworten. Deshalb Klick im QSO-Log, NICHT in der RX-Liste.

## WICHTIG — nicht vermischen

- `_pending_station_click` (P1.24): RX-Listen-Klick, **bricht laufendes QSO ab**.
  P158 ist KEIN Abbruch.
- Caller-Queue (`qso_sm._caller_queue`): Warteliste bei normalem CQ-QSO. Anders.
- P158 ist ein **eigener** Auto-Hunt-Puffer, der erst am QSO-ENDE feuert.

---

## Verifizierter Code-Stand (echte Pfade + Zeilen)

### ui/qso_panel.py (Fenster 2, QSO-Log)
- `log_view` = `QTextEdit`, `setReadOnly(True)` (Z. 167-168). **Kein
  QTextBrowser** → hat KEIN `anchorClicked`-Signal.
- RX-Zeile entsteht via `add_rx(message, tx_even, slot_start_ts, ant_label)`
  (Z. 255) → Eintrag-dict `kind="rx"` in `self._entries` → `_render_entry(e)`
  (Z. 316). Für rx: `line = f"{utc} {tag} ← Empf. {message}"`, gerendert via
  `_append_colored(line, "#44BBFF")` (Z. 348-356) = **Plain-Text** `append`.
- `_entries` ist Single-Source-of-Truth. `_rerender_all()` (Z. 379) zeichnet
  bei jedem Toggle UND alle 30s (`_cleanup_timer` → `_auto_trim_by_age`,
  Z. 591) ALLES aus `_entries` neu. Einträge > 300s werden getrimmt.
- `clear_log_completely()` (Z. 531) leert `_entries`+`log_view`+Parity-Tracker
  (bei Band-/Mode-/RX-Toggle).

### ui/mw_cycle.py
- `on_message_decoded(msg)` (Z. 819): bei `msg.target == settings.callsign`
  (Z. 832) → nach P128-Block-Check → `qso_panel.add_rx(msg.raw, ...)` (Z. 847).
  Danach P144-Busy-Filter (Z. 861), P94-Quick73 (Z. 871), OMNI-Listener,
  schließlich `qso_sm.on_message_received(msg)` (Z. 897).
- P144-Helper `_p144_target_busy_with_other` (Z. 949) prüft sehr ähnliche
  Bedingungen (Auto-Hunt aktiv, nicht manual_override, qso aktiv, msg.caller
  vs qso.their_call). Gutes Vorbild.

### ui/mw_qso.py
- `_on_station_clicked(msg)` (Z. 168): macht ALLES für einen QSO-Start —
  SWR-Block-Check (Z. 177), `is_transmitting`→Buffer (Z. 189), OMNI-Pause
  (Z. 235), `_auto_hunt.on_manual_qso_start()` (Z. 244, = manual_override=True),
  `add_info("Rufe X...")` (Z. 266), `qso_sm.start_qso(...)` (Z. 276), Normal-
  Mode-Freq-Follow. **Dieser Pfad ist die komplette B-Start-Logik.**
- `_on_qso_confirmed(qso_data)` (Z. 685): läuft NACH Courtesy-73-Send (A
  vollständig fertig). Ruft `on_manual_qso_end()` (Z. 707-708, = Auto-Resume)
  + `_maybe_resume_omni()` (Z. 716). **Hook-Punkt Erfolg.**
- `_on_qso_timeout(their_call)` (Z. 982): bricht TX ab (Z. 989), ruft
  `on_qso_timeout` + `on_manual_qso_end()` (Z. 1014-1018). **Hook-Punkt Timeout.**
- `_on_qso_confirmed_visual` (Z. 654): nur optisches ✓ (Courtesy-Send von A
  läuft DANACH noch) → NICHT als B-Start-Hook geeignet.

### core/auto_hunt.py
- `_manual_override` (pausiert), `on_manual_qso_start()` (Z. 517, override=True),
  `on_manual_qso_end()` (Z. 523, override=False = Resume).
- `stop_auto_hunt(reason)` (Z. 216): setzt `active=False` + cleart State.
  P122-Defer für 3 zeitbasierte Reasons bei aktivem QSO; `flush_pending_stop()`
  (Z. 290) in den QSO-Ende-Handlern (läuft VOR meinem geplanten B-Hook).
- KEIN `_insert_pending_call` vorhanden — muss neu.

---

## PLAN V1 (4 kleine Bausteine)

### Baustein 1 — Klickbare RX-Zeile (ui/qso_panel.py)
1a. Mini-Subklasse `_ClickableLog(QTextEdit)` mit `anchor_clicked = Signal(str)`.
    Override `mouseReleaseEvent`: `href = self.anchorAt(ev.position().toPoint())`;
    wenn `href` mit `"huntinsert:"` beginnt → `anchor_clicked.emit(href[11:])`
    (= der Call). Sonst `super()`. Optional `mouseMoveEvent`: bei Anchor
    `PointingHandCursor`, sonst Default (Hover-Hinweis).
    → `log_view` wird Instanz dieser Subklasse statt nacktem QTextEdit.
1b. `add_rx(...)` bekommt neuen Optional-Param `insert_call: str = ""`.
    Im Eintrag-dict gespeichert (`e["insert_call"]`) → re-render-fest.
1c. `_render_entry` kind=="rx": wenn `e.get("insert_call")` →
    statt `_append_colored` ein neuer Helper `_append_anchor_rx(line, call)`
    der via HTML-Anchor rendert:
    `<a href="huntinsert:{call}" style="color:#7FE0FF;text-decoration:underline;">…line…</a>`
    (dezenter heller Cyan + Unterstrich als statischer Klick-Hinweis, KEIN
    Blinken). Normale rx-Zeilen bleiben Plain wie bisher.
1d. `_ClickableLog.anchor_clicked` wird in main_window an einen mw-Slot
    verdrahtet (Signal-Durchreichung wie bei `tx_slot_lock_changed`).

### Baustein 2 — Klickbarkeit bestimmen (ui/mw_cycle.py, in on_message_decoded)
In dem `if msg.target == self.settings.callsign:`-Zweig (Z. 832), parallel zur
add_rx-Berechnung: Helper `_p158_is_insertable_caller(msg) -> bool`:
- Auto-Hunt aktiv (`_auto_hunt.active`) UND nicht `_manual_override`
- qso_sm in aktivem QSO (`qso.their_call` gesetzt)
- `msg.caller != qso.their_call` (B ist NICHT der aktuelle Partner = fremd)
- `msg.caller != settings.callsign`
- `not msg.is_73 and not msg.is_rr73` (B will Kontakt, nicht bestätigen)
Wenn True: `add_rx(..., insert_call=msg.caller)` UND
`self._p158_insertable[msg.caller] = msg` (dict, hält letzten Decode von B —
für Freq/Slot beim späteren Start). Sonst `add_rx(...)` wie bisher.

### Baustein 3 — Klick-Handler (ui/mw_cycle.py oder mw_qso.py)
`_on_hunt_insert_clicked(call)`:
- Guard: nur wenn `_auto_hunt.active` UND qso_sm aktuell in aktivem QSO mit
  ANDERER Station (sonst ignorieren — deckt „Klick auf B während B-QSO" +
  Klick auf veraltete Zeile nach QSO-Ende ab).
- `msg = self._p158_insertable.get(call)`; wenn None → ignorieren.
- `self._auto_hunt.set_pending_insert(msg)` (NEU in auto_hunt.py:
  `_insert_pending_call`-Slot, letzter-Klick-gewinnt).
- `qso_panel.add_info(f"⏳ {call} vorgemerkt — wird nach diesem QSO gerufen")`.

### Baustein 4 — Einschub am QSO-Ende (ui/mw_qso.py)
Helper `_p158_maybe_start_inserted_call()`, aufgerufen am ENDE von
`_on_qso_confirmed` (Erfolg) UND `_on_qso_timeout` (Timeout) — also NACH
`flush_pending_stop()` + `on_manual_qso_end()`:
- `if not self._auto_hunt.active: return` (Session zwischenzeitlich gestoppt
  → Puffer wurde in stop_auto_hunt eh schon gecleart → Edge-Case erfüllt).
- `msg = self._auto_hunt.take_pending_insert()`; wenn None → return.
- `self._p158_insertable.clear()` (aufräumen).
- `self._on_station_clicked(msg)` → reused kompletten Start-Pfad inkl.
  manual_override=True (pausiert Auto-Hunt für B) + „Rufe B...". Nach B-QSO
  ruft `_on_qso_confirmed`/`_on_qso_timeout` erneut `on_manual_qso_end()` =
  **Auto-Resume**. Falls beim B-Start TX noch läuft, buffert `_on_station_clicked`
  in `_pending_station_click` (1 Slot später) — akzeptabel, kein Abbruch.

### auto_hunt.py — neue Mini-API
- `self._insert_pending_call = None` im `__init__`.
- `set_pending_insert(msg)` / `take_pending_insert() -> msg|None` (gibt zurück
  + setzt None).
- In `stop_auto_hunt()` (sofortiger Stop-Zweig): `self._insert_pending_call = None`
  → Session-Ende verwirft Puffer (Edge-Case „deferred Stop vor B-Start").

### Aufräum-Pfade für `_p158_insertable` (mw)
- nach Einschub-Konsum (Baustein 4: `.clear()`)
- bei Band-/Mode-Wechsel (dort wird eh viel resettet)

---

## KEINE Tests nötig im Plan-Doc — kommen nach R1.

## 3 explizite Fragen an dich (R1)

**F1 — QTextEdit Anchor-Klick:** Ist `_ClickableLog(QTextEdit)` + `anchorAt(pos)`
in `mouseReleaseEvent` der saubere, KISS-konforme Weg (statt QTextBrowser-
Umbau)? Fallstricke: feuert `anchorAt` zuverlässig wenn der Text via
`append('<a href=...>')` als HTML eingefügt wurde? Muss ich `setOpenLinks`/
`setTextInteractionFlags` beachten? Mischung Plain-`append` (normale Zeilen)
+ HTML-Anchor-Zeile in EINEM QTextEdit — Probleme mit `_rerender_all` (alle
30s) bzgl. Anchor-Erhalt + Auto-Scroll?

**F2 — Hook-Punkt-Timing:** Ist das Ende von `_on_qso_confirmed` (nach
Courtesy-73-Send) + `_on_qso_timeout` der richtige Moment für den B-Start?
State sollte dort IDLE / kurz davor sein, TX nicht aktiv. Gibt es ein
Race-Fenster wo `_on_station_clicked(msg)` falsch in `_pending_station_click`
buffert oder die State-Machine noch nicht IDLE ist? Wäre ein
`QTimer.singleShot(0, ...)`-Defer sicherer, oder Overengineering?

**F3 — Highlight-Frage (Mike):** Soll die klickbare Einschub-Zeile zusätzlich
optisch hervorgehoben werden, damit Mike sie im Eifer nicht übersieht?
Optionen: (a) nur statisch dezent (heller Cyan + Unterstrich + Hover-Pointer,
mein Vorschlag), (b) zusätzlich kleines ▸/Hand-Symbol als Präfix, (c) Blinken/
Animation. Empfehlung mit Begründung (Hobby-Tool, ruhige moderne Optik).

Plus: alle Race-/Edge-Cases die ich übersehen habe (mehrere Anrufer →
letzter-Klick-gewinnt ohne Liste; B im selben Slot wie A; Klick während
Courtesy-Send; Band-Sperre während Wartezeit).
