# Architektur-Review: QSO-State-Machine Report-/73-Pfade vereinfachen?

Du bist Senior-Reviewer für eine PySide6 FT8-Funk-App (Hobby-Tool, KISS-Prinzip,
KEIN Contest-Tool). Antworte auf DEUTSCH, kritisch, ehrlich. Code ist Referenz.

## Kontext

Die Datei `core/qso_state.py` (angehängt) ist eine QSO-Zustandsmaschine für den
FT8-Sequenz-Ablauf. Sie hat zwei Einstiegs-Modi:
- **HUNT**: Operator klickt eine Station an → `start_qso()` → TX_CALL
- **CQ**: Operator ruft CQ → Stationen antworten → automatische Abwicklung

Der FT8-QSO-Standardablauf (beide Seiten):
```
A: CQ A                       (A ruft CQ)
B: A B <grid>                 (B antwortet mit Grid)
A: B A <report>              (A sendet Rapport, z.B. -12)
B: A B R<report>             (B bestätigt mit R-Rapport, z.B. R-08)
A: B A RR73                   (A bestätigt Empfang)
B: A B 73                     (B verabschiedet sich, optional)
```

## Mikes Frage (Projekt-Owner)

Mike sagt sinngemäß: „Wir haben gefühlt **7 verstreute Pfade** für das Senden
von Rapport und 73/RR73. Könnten wir die mit EINER simplen Vorfahrtsregel auf
**1 Pfad** reduzieren und es wesentlich vereinfachen?"

Mikes KISS-Idee dazu (Originalton): „Wir prüfen einfach: enthält die empfangene
Nachricht an uns eine **Zahl zwischen -25 und +25** (= ein Rapport), evtl. mit
`R` davor und meinem Rufzeichen vorn — dann wissen wir, die Gegenstation hat uns
gehört, und wir reagieren entsprechend. Eine Abfrage statt sieben."

## Die tatsächlichen Pfade im Code (bitte selbst verifizieren)

Report-/RR73-/73-sendende Verzweigungen, die ich zähle:
1. `_process_cq_reply`: is_grid → TX_REPORT (Z.265-276)
2. `_process_cq_reply`: is_report non-R → TX_REPORT (Z.285-293)
3. `_process_cq_reply`: is_r_report → TX_RR73 (Z.279-284)
4. `on_message_sent` TX_CALL pending rr73/73 → sende "73" (Z.494-499)
5. `on_message_sent` TX_CALL pending is_r_report → TX_RR73 (Z.500-505)
6. `on_message_sent` TX_CALL pending plain → advance() (Z.506-509)
7. `on_message_sent` TX_REPORT pending RR73/R-Report → TX_RR73 (Z.512-523)
8. `on_message_received` WAIT_REPORT/TX_CALL + rr73/73 → TX_73 (Z.607-620)
9. `on_message_received` WAIT_REPORT + is_r_report → TX_RR73 (Z.629-634)
10. `on_message_received` WAIT_REPORT + plain report → advance() (Z.635-636)
11. `on_message_received` WAIT_REPORT + is_grid → resend report (Z.639-644)
12. `on_message_received` TX_REPORT + diverse → pending merken (Z.646-660)
13. `on_message_received` WAIT_RR73 + rr73/73 → advance() (Z.662-666)
14. `on_message_received` WAIT_RR73 + is_r_report → advance()/Cap (Z.677-707)
15. `on_message_received` WAIT_RR73 + plain report → resend (Z.708-728)
16. `on_message_received` WAIT_RR73 + is_grid → resend (Z.729-749)
17. `on_message_received` WAIT_73 + 73/rr73 → Höflichkeits-73 (Z.751-785)
18. `on_message_received` WAIT_73 + is_r_report → RR73 max 2× (Z.786-799)
19. `advance()` WAIT_REPORT/WAIT_RR73/WAIT_73 (Z.803-838)

## Wichtige Randbedingungen (NICHT verhandelbar)

- **„Pending"-Mechanik**: Wenn eine Antwort der Gegenstation eintrifft WÄHREND
  wir noch senden (`TX_CALL`/`TX_REPORT`), darf nicht sofort gesendet werden →
  sie wird in `_pending_*` gemerkt und in `on_message_sent()` nach TX-Ende
  verarbeitet. Das ist Qt-Timing-bedingt, kein Zufall.
- **R-Report vs plain-Report**: `R-08` heißt „ich habe deinen Rapport bestätigt"
  → wir senden RR73. `-08` ohne R heißt „ich höre dich, aber bestätige deinen
  Rapport noch nicht" → wir senden R-Report zurück. Diese Unterscheidung ist
  protokoll-zwingend.
- **Höflichkeits-73 genau 1×** (`courtesy_73_sent`), R-Report-Wiederholung nach
  unserem 73 max 2× dann ignoriert (`wait_73_retries<2`), QSO-Ende-Cooldown 60s.
  Mike: „wenn QSO Ende steht, hat das auch Ende zu sein." Diese Schutzlogik
  funktioniert zu ~95% im Feld und darf NICHT degradiert werden.
- **Grid-Wiederholung** in WAIT_REPORT/WAIT_RR73 bedeutet „unser Call/Report kam
  nicht an" → erneut senden (kein Vorwärts-Sprung).
- **Caps**: MAX_RR73_RETRIES=5, MAX_STATION_CALLS=7 — Endlosschleifen-Schutz.

## Deine Aufgabe — ehrlich und kritisch

1. **Ist Mikes „1 Vorfahrtsregel statt 7"-Idee technisch tragfähig**, ohne die
   funktionierende 95%-Logik zu degradieren? Ja/Nein + Begründung am echten Code.
2. Falls NEIN: Warum nicht — welche der obigen Verzweigungen lassen sich NICHT
   in eine einzige Regel kollabieren (und warum genau)?
3. Falls TEILWEISE ja: Welche ECHTE, risikoarme Vereinfachung ist möglich?
   Konkret: Lässt sich Duplikation reduzieren durch (a) Helper-Extraktion
   (z.B. `_make_report_msg`, `_advance_after_report`), (b) eine kleine
   Dispatch-Tabelle `(state, msg_type) → action`, (c) Zusammenführung der
   CQ- und Hunt-Report-Erzeugung? Bewerte jede Option mit Risiko (niedrig/
   mittel/hoch) und Nutzen.
4. **Empfehlung**: Was würdest du Mike raten — (A) alles lassen wie es ist,
   (B) reine interne Refactor-Vereinfachung ohne Verhaltensänderung mit
   Test-Schutz, (C) echter Rebuild auf eine zentrale Regel? Eine klare
   Empfehlung mit Begründung.
5. Beachte die Projekt-Philosophie: KISS, Overengineering vermeiden, „drei
   ähnliche Zeilen schlagen eine verfrühte Abstraktion". Eine Dispatch-Tabelle
   KANN Overengineering sein — sag es ehrlich wenn ja.

Sei knapp aber präzise. Keine Höflichkeitsfloskeln.
