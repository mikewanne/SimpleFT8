# Anrufer-Warteliste

[English](waitlist.md) | **Deutsch**

## Was macht das Feature?

Wenn du auf CQ rufst und mehrere Stationen gleichzeitig antworten,
verlierst du normalerweise alle bis auf eine — du musst manuell
auswaehlen, die anderen geben auf. SimpleFT8 setzt alle Antworter
in eine **Warteliste** und arbeitet sie nach dem aktuellen QSO
automatisch ab. Niemand wird vergessen.

## Wie funktioniert es?

Wenn die App im CQ-Modus laeuft (`btn_cq` aktiv) und mehrere
Stationen im selben Slot antworten, registriert die QSO-State-
Machine alle Antworter:

- **Grid-Antwort** (`DA1MHH DK5ON JO31`) — die Standard-Erstantwort
- **Report-Antwort** (`DA1MHH DK5ON -15`) — direkter Report ohne
  Grid (haeufig bei DX und Contestern)

Beide Typen werden in der Warteliste gespeichert. Nach Abschluss
des aktuellen QSOs (RR73 oder 73 erhalten/gesendet) prueft die
State-Machine die Warteliste:

1. Liste vorhanden, mind. ein Eintrag → naechste Station
   automatisch antworten (gleicher Ablauf wie manuell anklicken)
2. Pro QSO max. 3-5-7-99 Versuche (Settings, „Anrufversuche")
3. Bei Timeout (~3 Min) → Eintrag verworfen, naechster aus der
   Liste

Die Liste ueberlebt nicht den Bandwechsel — beim Bandwechsel wird
sie geloescht (neuer Kontext).

## Wann nuetzlich?

- **DX-Pile-Ups:** Mehrere Stationen rufen gleichzeitig — du
  bedienst alle, ohne dass jemand abbrechen muss.
- **Contest-Modus:** Antworter werden serialisiert, der Zaehler
  steigt schnell.
- **Aktiver Tag:** 5-10 Antworten pro CQ sind normal — Warteliste
  macht sie alle moeglich.

## Wo zu finden?

- **QSO-Panel:** Wenn die Warteliste Eintraege hat, erscheint ein
  Hinweis `Warteliste: 3 Stationen` im QSO-Status.
- **Hauptfenster:** Aktiv im CQ-Modus, kein eigener An/Aus-Knopf
  — die Warteliste ist immer aktiv, wenn `btn_cq` an ist.
- **Auto-Hunt-Synergie:** Mit aktivem Auto-Hunt werden auch
  CQ-Rufer in der RX-Liste automatisch abgearbeitet (siehe
  [auto-hunt_de.md](auto-hunt_de.md)).

**Hardware-Pflicht:** Alle Antworten werden ueber ANT1 (TX)
gesendet — automatisch, unabhaengig von der Diversity-RX-Antenne.

## Sichtbarkeit fuer den Operator

Der Operator sieht im QSO-Panel die aktuelle Station und die
Anzahl wartender Stationen. Auf Wunsch kann der Operator die Liste
manuell ueberspringen oder das aktive QSO abbrechen — die
naechste Station wird dann sofort kontaktiert.

Mike-Beweis (DL3AQJ): Real-QSO, 40m FT8 — F1IQH ruft waehrend des
laufenden QSOs mit DL3AQJ. F1IQH wird automatisch in die
Warteliste gestellt und nach Abschluss des DL3AQJ-QSOs sofort
beantwortet. Kein manueller Eingriff. Screenshot in `docs/screenshots/warteliste_qso.png`.
