# Review: Diagnose-Logging für ungeklärten Watt-/RF-Bug (TX-Pfad)

## Kontext (SimpleFT8, FlexRadio, FT8/FT4)

Sporadischer Field-Bug: Die App zeigt **RF 100 %** (`_rfpower_current`), das
Funkgerät macht aber nur ~60 W (Ziel 70 W) und die Regelung passt nichts mehr an
— sie „klebt". Heilt sich, sobald der Nutzer die Ziel-Wattzahl umschaltet (das ruft
`_on_power_changed` → `set_power(...)` = frischer Befehl ans Radio). Bei Ziel 80 W
macht das Gerät dagegen sauber 83 W bei RF **80 %** (nicht am Anschlag) — rfpower↔Watt
ist also normal ~linear. Die 100 %/60 W sind ein **echter Sync-/Freeze-Fehler**, kein
Hardware-Limit. SWR durchgehend 1,3 (kein Foldback).

**Leitende Hypothese:** `_auto_adjust_tx_level` schickt keine neuen `set_power`-Befehle
mehr, sobald `new_rfpower == _rfpower_current` (z. B. am 100-Anschlag) → es markiert
`_rfpower_converged=True` und „verstummt". Wenn das Radio seine Leistung zwischendurch
zurücksetzt (Bandwechsel ODER Diversity-Slice-/Antennen-Umschaltung laden ein Profil —
`set_power` selbst kommentiert genau diese Gefahr), bleibt die App auf „100 %", das
Radio tiefer → Output klebt.

**Ich will den Bug NICHT jetzt fixen** (zu wenig Evidenz, ich habe schon einmal falsch
geraten). Ich will **nur Diagnose-Logging** einbauen, das beim nächsten Auftreten die
echte Ursache zeigt.

## Diagnose-Framework

`core/debug_log.py: debug_log(category, message)`:
- No-op wenn Debug-Log deaktiviert (globaler `_enabled`-Flag, per Ctrl+D/Settings).
- Öffnet/schließt Datei pro Write, thread-safe, Retention (keep_days=1).
- Im Normalbetrieb (Debug aus) = komplett still.

## Mein Plan (V1) — reines Logging, KEINE Verhaltensänderung

**A) In `_auto_adjust_tx_level` (läuft 1× pro Sende-Slot, alle 7,5–15 s):**
Eine `debug_log("TXPWR", …)`-Zeile am Ende mit allen Diagnose-Feldern:
`band/mode, target={_power_target}, app_rf={_rfpower_current}%, fwdpwr={gemessen}W,
audio={current_audio}, peak={raw_peak}, swr={radio.last_swr}, conv={_rfpower_converged}/
{_was_converged}, action={set_rf->N | audio | hold | converge_save}`.
Dazu eine lokale `action`-Variable in den bestehenden if/elif-Zweigen (set_power
gesendet? Audio geändert? nichts?). Die bestehende `print("[AutoTX]…")`-Zeile bleibt.

**B) In `_on_power_changed`:** `debug_log("TXPWR", f"power_btn {old}->{new}W
preset_rf={_rfpower_current} → set_power gesendet")` (selten, user-getriggert).

**C) In `_apply_rf_preset`:** `debug_log("TXPWR", …)` ob Preset-Treffer oder Default
+ geladener rfpower-Wert (die Funktion `print`t das schon).

**Bewusst NICHT** in `_on_meter_update` (FWDPWR/SWR-Meter-Callback) loggen — der feuert
zig-mal/s → Log-Flut-Falle (in v0.99.3 gab's deshalb mal 4 GB Logflut, das vermeiden).

## Fragen an dich

1. **Sind das die richtigen Felder**, um die Freeze/Sync-Hypothese zu beweisen oder zu
   widerlegen? Fehlt etwas Entscheidendes (z. B. ein Flag/Zähler), um „App glaubt 100 %,
   Radio macht real weniger, set_power wird NICHT neu gesendet" zweifelsfrei zu sehen?
2. **Ist die Frequenz sicher** (1×/Slot in `_auto_adjust_tx_level`) — oder gibt es einen
   Pfad, auf dem diese Funktion viel häufiger läuft?
3. **Ist es wirklich verhaltensneutral** (nur Logging, kein Seiteneffekt auf die
   Regelung/TX)? Stolperfallen bei der `action`-Variable in den Zweigen?
4. Sollte ich zusätzlich an EINER weiteren, seltenen Stelle loggen, wo das Radio seine
   rfpower verlieren könnte (Bandwechsel-Handler / Diversity-Slice-Switch), damit man im
   Log die Korrelation „Switch → danach klebt's" sieht? Wenn ja, wo grob (Modul/Funktion),
   ohne dass es zur Flut wird?

Antworte knapp und konkret. Code-Pfade gegen die beigefügte Datei prüfen, nicht raten.
