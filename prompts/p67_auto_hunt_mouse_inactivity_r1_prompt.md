# R1 — DeepSeek-V4-pro Review fuer P67 (Auto-Hunt Mouse-Inactivity-Schicht)

Du bist Senior-Code-Reviewer. Sprache: Deutsch. Ueberpruefe diesen Plan
**streng** auf Bugs, Race-Conditions, Halluzinationen, Edge-Cases, KISS-
Verletzung und Hardware-Sicherheit.

## Kontext SimpleFT8

- FT8/FT4/FT2-Funk-App mit PySide6/Qt.
- **Auto-Hunt:** automatischer TX-Modus, ruft CQ-Stationen an. Sichtbar
  nur in Diversity-Modus. Aktuell zwei Stop-Bedingungen:
  1. 10-Min-Hard-Cap (`_auto_hunt_timer` QTimer, FEST, Maus-unabhaengig).
  2. 15-Min-Operator-Presence (`_presence_timer`, Maus reset) →
     `totmann_expired`.
- **Mike's Spec:** Variante C — neue zusaetzliche 5-Min-Maus-Inaktivitaets-
  Schicht. Beide Mechanismen (10-Min-Hard-Cap + 5-Min-Maus) laufen
  parallel, wer zuerst greift gewinnt.
- **Hardware-Pflicht:** ANT1=TX, ANT2=NUR RX. NIEMALS TX auf ANT2 (siehe
  CLAUDE.md). Stop-Pfade duerfen `set_tx_antenna` nicht ungewollt aendern.

## Aufgabe

Pruefe V1 (mit V2-Korrekturen) auf:
- **F-Bugs** (rot): falsche Methodenaufrufe, fehlende Initialisierung,
  Race-Conditions, Encoder/QSO-Korruption, Hardware-Sicherheits-Verletzung.
- **F-Risiken** (orange): Wartbarkeit, Testbarkeit, KISS-Verletzungen,
  doppelte State-Quellen, Drift-Risiken.
- **F-Verbesserungen** (gelb): klarer benennen, Code-Konsistenz,
  Edge-Cases die ergaenzt werden sollten.

Halluzinationen melden — wenn du Code-Verweise siehst die im echten Code
nicht stimmen, sag es. Du bekommst die echten Dateien zur Verifikation.

## Akzeptanzkriterien V1+V2

(siehe `p67_auto_hunt_mouse_inactivity_v1.md` mit V2-Korrekturen aus
`p67_auto_hunt_mouse_inactivity_v2.md`).

Zusammenfassung:
- Konstante `_AUTO_HUNT_MOUSE_TIMEOUT_S = 300` hartkodiert in `main_window.py`.
- Neuer State `self._auto_hunt_last_mouse_t: float = 0.0` in `_init_presence_watchdog`.
- `_poll_mouse_activity` setzt bei Mausbewegung zusaetzlich
  `self._auto_hunt_last_mouse_t = time.monotonic()`.
- `_on_btn_auto_hunt_toggled(checked=True)` setzt Anker VOR `start_auto_hunt(600)`.
- `_on_auto_hunt_polling_tick` (1s-Tick): NACH `if not self._auto_hunt.active`-
  Guard, VOR Text-Update: `if monotonic() - _auto_hunt_last_mouse_t > 300:
  add_info(...) + print(...) + stop_auto_hunt("mouse_inactive_5min") + return`.
- `core/auto_hunt.py:stop_auto_hunt` Docstring erweitert um Reason
  `mouse_inactive_5min`. Cleanup-Logik: DEFAULT-Branch (clear cooldowns
  + last_tx_even None) — analog manual_halt, anders als totmann_expired.
- Kein `_abort_active_tx` bei mouse_inactive_5min (analog totmann_expired:
  laufendes QSO darf zu Ende).
- 10 Tests in `tests/test_p67_mouse_inactivity.py`.

## Pflicht-Fragen

1. Ist die Reason-Cleanup-Logik korrekt? `mouse_inactive_5min` faellt in
   den DEFAULT-Branch (`_cooldown.clear()` + `_last_tx_even = None`).
   Macht das semantisch Sinn, oder sollte es analog `totmann_expired`
   die Cooldowns behalten (weil User schnell zurueckkommen koennte)?
2. Sollte `presence_can_tx()` parallel zum 5-Min-Maus-Check sein? Bei
   5-Min-Maus-Stop: Presence-Timer ist erst bei 15 Min abgelaufen, also
   `presence_can_tx() = True`. Ist das ein Konsistenz-Problem? (Auto-Hunt
   ist gestoppt, aber CQ/QSO laufen weiter.)
3. Race: was wenn `stop_auto_hunt("mouse_inactive_5min")` gerade gefeuert
   wird waehrend `_run_auto_hunt`-Pick im selben Slot laeuft (Decoder-
   Thread `_on_cycle_decoded` → mw_cycle._run_auto_hunt → AutoHunt.select_next)?
   Reicht der bestehende Race-Doppel-Check in `select_next` (`if not self.active`)?
4. `_auto_hunt_last_mouse_t = 0.0` Default → erster Polling-Tick nach
   App-Start ohne jede Maus-Bewegung wuerde theoretisch sofort stoppen.
   Aber: User muss eh erst Auto-Hunt klicken → Klick = Mausbewegung →
   `_poll_mouse_activity` setzt Anker → `_on_btn_auto_hunt_toggled`-Pfad
   setzt Anker erneut. Double-set, kein Bug, aber: ist das robust auch
   bei Keyboard-Aktivierung (Tab-Navigation, Space)?
5. UI-Feedback: `add_info("⏸ Auto-Hunt gestoppt — 5 Min ohne Mausbewegung.
   Maus bewegen + AUTO HUNT klicken zum Fortsetzen.")` — gut formuliert
   oder verbesserungsfaehig?
6. Sollte die 5-Min-Konstante in `core/auto_hunt.py` neben den anderen
   Konstanten leben (`_COOLDOWN_SECS`, `_RECENT_QSO_COOLDOWN_S`) statt in
   `main_window.py`? KISS sagt: kommt drauf an wo Maus-Polling lebt — wenn
   Maus-Polling nur in UI-Layer ist, muss Konstante auch dort sein.
   Pro/Contra einer Verlagerung nach `core/auto_hunt.py`?
7. Test-Coverage: T1-T10 ausreichend? Welche Edge-Cases fehlen noch?

## Antwortformat

```
## R1-Findings

### F1 (ROT): <Titel>
- Pfad: <Datei:Zeile>
- Symptom: ...
- Wurzel: ...
- Fix-Vorschlag: ...

### F2 (ORANGE): ...
### F3 (GELB): ...

## Pflicht-Fragen-Antworten
1. ...
2. ...
...

## Empfehlung
- Push-Status: FREIGEGEBEN / FREIGEGEBEN MIT F-X-FIX / BLOCKIERT
- KP (kritische Punkte): ...
```

Max 1500 Woerter.
