# DeepSeek-Review R1 — Re-Mess-Countdown-Anzeige hängt

## Kontext

**SimpleFT8** ist ein FT8/FT4 Hobby-Tool für FlexRadio. Bug-Fix für eine
hängende UI-Anzeige.

**Bug (Mike 22.05.2026):** Das `dx_info`-Label zeigt „noch X Stunden bis
Re-Mess (Gain-Messung)". Es **updated sich nur bei User-Aktionen**
(Band-/Modus-Wechsel, Diversity-Toggle, KALIBRIEREN-Klick). Wenn Mike
in einem Modus sitzt, bleibt die Zahl stehen, auch wenn Stunden
vergehen — bis er irgendwas klickt, dann springt die Anzeige plötzlich
auf den echten Wert.

**Mike-Symptom:** Diversity „3h" → Moduswechsel → „1h" — Wechsel erzwingt
Neuberechnung, die echte Restzeit war schon länger 1h.

**Root Cause:** `_update_gain_status_display()` (`ui/mw_radio.py:1454`)
hat 10 Aufrufer — alle aktions-getriggert (`set_band`, `set_mode`,
`_enable_diversity`, `_disable_diversity`, `_on_dx_tune_accepted`,
`_on_radio_connected`, etc.). **Kein Timer, kein Cycle-Hook.**

**Fix-Richtung (Mike vorab):** Einen Aufruf pro Slot im Cycle-Handler
hinzufügen. Kein neuer Timer, kein Zähler — der Slot-Tick existiert
eh (alle 3.8 / 7.5 / 15 s je nach Modus).

## V1 (Vorschlag)

**AC1:** In `_on_cycle_finished()` (`ui/mw_cycle.py:137`) — direkt nach
`self.qso_sm.on_decoder_finished()` (Z.152) — `self._update_gain_status_display()`
ergänzen. Vermutlich nach dem `_rx_active`-Guard (Z.150-151), damit
der bestehende Skip-Pfad konsistent bleibt.

**AC2:** `_format_gain_status` muss die Zeit-Berechnung pro Aufruf neu
machen (kein Cache). V3 verifizieren.

**AC3:** Bestehende 10 Action-Trigger **UNVERÄNDERT** lassen — sie
liefern sofortiges Feedback nach Klick, nicht „bis zum nächsten Slot
warten".

**AC4:** Neuer Test: Cycle-Hook löst Display-Update aus (Mock/Spy auf
`_update_gain_status_display`).

**AC5:** Doku — APP_VERSION 0.97.92→0.97.93, HISTORY/HANDOFF/CLAUDE.

**AC6:** TODO-Eintrag „Re-Mess-Countdown-Anzeige hängt" auf ERLEDIGT
umlabeln.

## V2 Findings (Self-Review)

- **F1:** `_format_gain_status` nicht gelesen — V3-Pflicht prüfen ob
  intern gecacht ist.
- **F2:** Reihenfolge in `_on_cycle_finished` — vor oder nach
  `on_decoder_finished()`? Vermutlich egal.
- **F3:** Bestehende 10 Trigger NICHT entfernen — Action-Trigger
  geben sofortiges Feedback, Pro-Slot-Aufruf ergänzt sie.
- **F4:** Test-Design — Mock/Spy auf die Methode, Cycle-Hook
  programmatisch triggern, Aufruf zählen.
- **F5:** Im `_on_cycle_finished` ist ein `if not self.rx_panel._rx_active: return`-
  Guard (Z.150-151). Frage: soll Display-Update VOR oder NACH dem
  Guard laufen? Anzeige ist global (Band-bezogen, nicht RX-State-
  bezogen) — argument für vor dem Guard.
- **F6:** Etabliertes Muster: `_refresh_diversity_freq_view` läuft auch
  pro Slot in `mw_cycle.py:154`.

## Was ich von dir will

Kritischer Sanity-Check für einen kleinen Bug-Fix:

1. **Annahmen korrekt?** `_update_gain_status_display` ist wirklich
   leichtgewichtig (`_format_gain_status` → HTML-String + setText),
   sicher per-Slot aufrufbar? Lies die angehängte `mw_radio.py` und
   verifiziere.
2. **`_format_gain_status`** in `mw_radio.py` — wird die „X Stunden"-
   Berechnung dort pro Aufruf neu gemacht? Oder ist da ein Cache, der
   invalidiert werden müsste?
3. **Hook-Wahl** — `_on_cycle_finished` (Slot-Ende) oder
   `_on_cycle_decoded` (nach Decode-Aggregation)? Welcher ist robuster
   gegen Edge-Cases (kein Decoder-Output, leerer Slot)?
4. **Guard-Reihenfolge** — vor oder nach `if not self.rx_panel._rx_active:
   return` (Z.150)? Anzeige sollte auch ohne aktives RX-Panel laufen
   können (Band-Info ist global), aber vielleicht gibt's Side-Effects.
5. **Was übersehe ich** — Race-Conditions, Threading, Performance,
   andere subtile Gründe gegen Pro-Slot-Update?

Antworte auf Deutsch, knapp, konkret, mit Datei:Zeile. Sei kritisch —
diese 1-Zeilen-Lösung soll wirklich der saubere Fix sein.
