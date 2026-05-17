# P67 V2 — Self-Review (vor R1)

## V1-Halluzinations-Check

**V2-F1 (BUG ROT):** V1 nennt Init-Method `_init_presence_timer` — Code hat
`_init_presence_watchdog` (Z.449). V3 muss korrigieren.

**V2-F2 (BUG ROT):** V1 nennt Toggle-Handler `_on_auto_hunt_toggled` — Code
hat `_on_btn_auto_hunt_toggled` (Z.878). V3 muss korrigieren.

## Code-Realitaets-Check

**V2-F3 (Reihenfolge-Praezisierung):** `_on_btn_auto_hunt_toggled` Z.883-900:
```
895   if self._omni_cq.is_active():
896       self._omni_cq.stop("superseded")
897   self._auto_hunt.start_auto_hunt(600)
898   self._auto_hunt_polling_timer.start()
899   self._on_auto_hunt_polling_tick()  # initialer Text-Set ← HIER
900   print(...)
```
Anker `_auto_hunt_last_mouse_t = time.monotonic()` MUSS **vor** Z.897
gesetzt sein, sonst koennte der initiale Polling-Tick (Z.899) bei
Default 0.0 sofort den 5-Min-Stop ausloesen.

**V2-F4 (Polling-Tick Struktur):** Bestehender Code Z.936-943:
```
def _on_auto_hunt_polling_tick(self):
    if not self._auto_hunt.active:
        self._auto_hunt_polling_timer.stop()
        return
    sec = self._auto_hunt.seconds_remaining()
    m, s = divmod(sec, 60)
    self.control_panel.btn_auto_hunt.setText(...)
```
5-Min-Check kommt NACH `if not self._auto_hunt.active`-Guard, VOR Text-
Update (sonst flickert die Restzeit-Anzeige zwischen Ablauf und Stop).

**V2-F5:** `import time` ist Z.12 bereits vorhanden. ✓

**V2-F6:** `_abort_active_tx`, `qso_panel.add_info` existieren. ✓

**V2-F7 (start_auto_hunt-Aufrufer):** Nur EIN aktiver Aufruf (Z.897, im
Toggle-Handler). Andere greps sind Backups. → V1 AC4 deckt alles ab.

## Edge-Cases

**V2-F8 (Race „Maus exakt im Trigger-Moment"):**
- `_poll_mouse_activity` laeuft alle 500 ms, setzt `_auto_hunt_last_mouse_t = monotonic()`
- `_on_auto_hunt_polling_tick` laeuft jede Sekunde, liest
  `monotonic() - _auto_hunt_last_mouse_t > 300`
- Beide laufen im Qt-Event-Loop (GUI-Thread) → kein echtes Race.
- 1-Sek-Granularitaet: Stop kann 0-1 s nach Ablauf der 5 Min kommen
  (also bei 5:00 bis 5:01). Akzeptabel, kein Bug.

**V2-F9 (Aktives QSO bei Maus-Inaktivitaet):**
- 5 Min ohne Maus + laufendes QSO → `stop_auto_hunt("mouse_inactive_5min")`
  beendet nur die Auto-Hunt-Session, nicht das QSO.
- Encoder.is_audio_streaming → laeuft, weil kein `_abort_active_tx`.
- `presence_can_tx()` bleibt True (Presence-Timer ist eigener 15-Min-Counter).
- → QSO laeuft zu Ende. ✓ analog `totmann_expired`.

**V2-F10 (Multi-Klick Toggle off→on→off):**
- Klick 1 (on): Anker gesetzt + start_auto_hunt.
- Klick 2 (off): `_abort_active_tx + stop_auto_hunt("manual_halt")` (Z.901-904).
- Klick 3 (on): Anker neu gesetzt + start_auto_hunt.
- Polling-Tick laeuft dazwischen mit `active=False` → frueher Return. ✓

**V2-F11 (`_auto_hunt_last_mouse_t` zwischen Sessions):**
- Bleibt am alten Wert (legitim — wird beim naechsten Start ueberschrieben).
- Kein Reset noetig im stop-Pfad.

**V2-F12 (Hardware-Pflicht CLAUDE.md):**
- Code-Pfad: Lese (monotonic, delta-Compare) + Aufruf `stop_auto_hunt` +
  `add_info` + `print`. **Keine TX-Trigger, kein set_tx_antenna.**
- Test T9 verifiziert dass `_abort_active_tx` NICHT aufgerufen wird
  (Pruefung via mock.call_count == 0).

## V2-Empfehlungen fuer V3

1. AC2 → `_init_presence_watchdog` statt `_init_presence_timer`.
2. AC4 → `_on_btn_auto_hunt_toggled` statt `_on_auto_hunt_toggled`.
3. AC4 → Reihenfolge praezisieren: Anker zwischen `if checked and not
   self._auto_hunt.active`-Block und `start_auto_hunt(600)` setzen.
4. AC5 → Check-Position: nach `if not self._auto_hunt.active`-Guard, VOR
   Text-Update.
5. AC11 → T-Namen aktualisieren mit Methodennamen.
6. AC9 → `add_info`-Aufruf direkt in `_on_auto_hunt_polling_tick` einbauen,
   VOR `stop_auto_hunt`. Reihenfolge: add_info → print → stop_auto_hunt.
7. Bonus: Add explizite Initial-Wert-Doku — `_auto_hunt_last_mouse_t = 0.0`
   ist Default-Wert vor erstem Session-Start. Beim Klick wird Anker gesetzt,
   also kein Bug.
