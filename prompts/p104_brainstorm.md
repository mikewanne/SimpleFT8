# P104 — Brainstorm: Settings-UX-Vereinfachung

**Mike-Diskussion 21.05.2026 — KEINE Code-Änderung jetzt, nur Konzept.**

## Punkt 1 — RF-Presets-Tabelle ersetzen durch Band-Farb-Status

**Heute:** 4-spaltige Tabelle (Band, Watt, RF, Letzte Speicherung) + Band-
Auswahl-Combo + „Band löschen"/„Alle löschen".

**Mike-Argument:**
- RF-Detailwerte interessieren User nicht — bei leeren Slots wird
  interpoliert/hochgerechnet
- Was wirklich zählt: *welche Bänder haben Daten, welche nicht*
- Use-Case „neue Kabel, neue Antenne" → Band zurücksetzen

**Mike-Spec-Vorschlag:**
- Statt Tabelle: alle Bänder als Buttons/Labels nebeneinander
  (10m, 12m, 15m, 17m, 20m, 30m, 40m, 80m, 160m)
- **Grün** = hat RF-Werte
- **Rot** = keine RF-Werte
- Klick auf Band → Dialog „RF-Werte für 20m zurücksetzen? [Ja / Nein]"
- Plus weiterhin „Alle löschen"-Button

**Vorteile:**
- KISS, sofort visuell verständlich
- Weniger UI-Elemente, kompakter
- „Neue Antenne"-Use-Case in 2 Klicks erledigt

**Mögliche Bedenken:**
- Detail-Info geht verloren (wann zuletzt gespeichert, welche Watt-Stufen
  in welchem Band) — aber Mike sagt: brauchen wir nicht
- Power-User die exakte RF-Werte sehen wollen verlieren das

**Frage R1:**
1. Ist Mike's Vorschlag besser für Hobby-Funker-UX als die Tabelle?
2. Soll die alte Tabelle ganz weg, oder optional als „Details anzeigen"-
   Klappbar erhalten bleiben?
3. Wie sollen die Band-Buttons farblich aussehen — voll-grün/voll-rot
   oder dezenter (z.B. Border-Color)?
4. Click-Hit-Area: ganzes Band oder kleines Reset-X daneben?

## Punkt 2 — „Sendeleistung 100 W" und „TX Audio-Pegel 100%" überflüssig?

**Mike-Argument:**
- FlexRadio 8000er-Serie kann hardware-bedingt eh nur 100 W max
- Power-Preset im Hauptpanel deckt 10–100 W in 10er-Schritten ab
- RF-Pegel wird closed-loop nachgeregelt
- Beide Settings stehen einfach „auf Anschlag" und werden nie geändert

**Heute Settings-Tab "TX & Schutz":**
```
Sendeleistung:    100 W
TX Audio-Pegel:   100 %
Anrufversuche:    99
SWR-Limit:        3.0
[TUNE-Einstellungen]
[RF-Presets pro Band+Watt]
```

**Mike's implizite Frage:** Können die zwei Felder raus?

**Code-Audit nötig (R1 bitte bewerten):**

- `power_watts` (Settings-Key): wo wird der Wert tatsächlich gelesen
  und wirkt er sich auf TX aus?
- `tx_level` (Settings-Key): TX Audio-Pegel — wirkt das tatsächlich
  auf die Modulation, oder ist es ein Legacy-Feld?
- Power-Preset im Hauptpanel: nutzt es `power_watts` als Default oder
  hat es eigene Logik?

**Mögliche Outcomes:**
- A) Beide Felder sind tatsächlich überflüssig → können raus
- B) Sie haben Wirkung aber User-Verständlichkeit fehlt → besser
  positionieren / umbenennen / Tooltip
- C) Sie sind Default-Werte für neue Bänder → behalten aber als
  „Standard-Werte"-Sektion klar markieren

**Mike-Spec-Wunsch:** simple Hobby-Funker-UX, nicht WSJT-X-mäßig
mit 30 Reglern.

## Antwort bitte knapp — Mike will Konsens vor Code.
