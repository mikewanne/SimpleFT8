# Auto-Hunt

[English](auto-hunt.md) | **Deutsch**

## Was macht das Feature?

Auto-Hunt waehlt automatisch die naechste CQ-Station aus der RX-
Liste und startet das QSO ohne manuellen Klick. Wenn du auf
„Senden lassen" gehst statt selbst alle 30 Sekunden zu klicken —
Auto-Hunt ist deine Verbindung zwischen passivem Empfang und
serialisiertem QSO-Ablauf.

**Wichtig:** Auto-Hunt ist Diversity-only. Im Normal-Modus ist der
Button nicht sichtbar. Damit ist Auto-Hunt fest mit der Diversity-
Empfangsstrategie gekoppelt.

## Wie funktioniert es?

### Auswahl-Algorithmus (Scoring)

Aus der aktuellen RX-Liste der CQ-Rufer wird die naechste Station
nach folgender Prioritaet gewaehlt:

1. **Neue DXCC-Entitaet** — hoechste Prioritaet, immer zuerst
2. **Seltenes Rufzeichen** (haeufigkeit_in_logbuch < 3)
3. **Guter SNR** (> -15 dB) — schnelle, sichere QSOs
4. **Erstmaliger Empfang** an diesem Tag (vermeidet Wiederholungen)

Innerhalb gleicher Score-Gruppe wird zufaellig gewaehlt — keine
deterministische Hunt-Reihenfolge (wirkt natuerlicher fuer
Beobachter).

### Totmannschalter (Bot-Schutz)

`_auto_hunt_timer` ist UNABHAENGIG vom Maus-/Tastatur-Reset. Mike's
bewusste Entscheidung: Auto-Hunt soll nicht „infinit weiter" laufen
nur weil der Operator daneben sitzt und tippt. **Hard-Cap 10
Minuten** seit Aktivierung — danach Stop, Pflicht-Restart per
User-Klick.

Race-Doppel-Check in `select_next` ist Belt-and-Suspenders gegen
die 10-Min-Hard-Cap (ethische Garantie).

### QSO-Versuche

Pro Station max. 3 Versuche (Modul-Konstante `_MAX_ATTEMPTS=3`,
liegt fachlich aber in `qso_state.py`). Bei Timeout naechste
Station. Bei Erfolg: ADIF-Eintrag, weiter mit naechster.

### Bandwechsel

Beim Bandwechsel: Auto-Hunt wird automatisch gestoppt, Cooldowns
geleert. Mode-Wechsel zu Normal stoppt ebenfalls automatisch
(`auto_hunt_stopped("mode_change")`).

## Wann nuetzlich?

- **Aktiver Tag, viele Antworter:** Du willst nicht stundenlang
  klicken — Auto-Hunt arbeitet still im Hintergrund.
- **DX-Sweep:** Neue DXCC-Entitaeten werden bevorzugt — du
  bekommst die seltenen QSOs zuerst.
- **Lernender Modus:** Funkt eine Weile, schaut nach welche
  Stationen die App gewaehlt hat — operative Statistik.

## Wo zu finden?

**Sichtbarkeit:** `btn_auto_hunt` ist nur in Diversity-Mode
sichtbar (Mode-gekoppelt seit v0.78).

- **Hauptfenster:** Button neben dem CQ-Button, Diversity aktiv
- **Klick:** Aktiviert Auto-Hunt, Timer-Countdown im Statusbar
- **Erneuter Klick** oder Stop-Bedingung: deaktiviert

**Hardware-Pflicht:** Alle TX-Operationen ueber ANT1.
Auto-Hunt waehlt KEINE Antenne — die Antennen-Wahl trifft die
Diversity-Logik (siehe [diversity-modes_de.md](diversity-modes_de.md))
plus Antenna-Pref pro Station (siehe
[antenna-preference_de.md](antenna-preference_de.md)).

**Status-Anzeigen:**

- 1-Sekunden-Polling-Timer fuer Live-Countdown waehrend Session
- 5-Sek-UI-Reflexions-Cooldown nach Stop (verhindert Reflex-
  Klick — User soll bewusst entscheiden ob Restart)

## Status

Implementiert in v0.75. Diversity-Mode-Coupling in v0.78
hinzugefuegt. Voll getestet ueber Real-QSOs.
