# P158 verallgemeinern: Klick auf „uns rufende Station" im QSO-Fenster IMMER erlauben

Du bist Senior-Reviewer einer PySide6 FT8-Funk-App (Hobby-Tool, KISS, KEIN
Contest-Tool). Antwort auf DEUTSCH, kritisch, knapp. Code ist Referenz.

## Was es heute gibt (P158, v0.98.44)

Wenn eine fremde Station B *uns* (DA1MHH) anruft, erscheint im **QSO-Log-Fenster**
(`qso_panel.log_view`, ein QTextBrowser) eine Zeile `← Empf. DA1MHH B <grid>`.
Diese Zeile ist NUR unter ALLEN folgenden Bedingungen klickbar
(`_p158_is_insertable_caller`, mw_cycle.py:1027):

1. **Auto-Hunt-Session aktiv** (`_auto_hunt.active`)
2. **NICHT** im manual_override (`not ah._manual_override`)
3. **aktives QSO läuft mit einem ANDEREN Call** (`qso.their_call` gesetzt und
   `msg.caller != qso.their_call`)
4. msg ist kein 73/rr73

Klick → `_on_hunt_insert_clicked` → `auto_hunt.set_pending_insert(msg)`.
Am QSO-Ende (`_on_qso_confirmed` ODER `_on_qso_timeout`) ruft
`_p158_maybe_start_inserted_call()`: wenn Auto-Hunt noch aktiv →
`take_pending_insert()` → `_on_station_clicked(msg)` (= manueller Start-Pfad,
inkl. Auto-Hunt-Pause + Auto-Resume danach).

## Mikes Wunsch (Projekt-Owner, Originalton)

„Es ist Quatsch dass Auto-Hunt aktiv sein muss. Sie ruft uns — DAS ist der Punkt,
und damit ist sie im QSO-Fenster sichtbar. Es muss auch kein aktives QSO mit einer
anderen Station sein. Die EINZIGE Bedingung ist: **sie ruft uns und ist damit im
QSO-Fenster sichtbar** → dann muss sie anklickbar sein."

Mike will außerdem wissen: **„Sollen wir die alte Logik durch eine neue ersetzen,
bevor wir wieder einen zweiten Pfad bauen?"** — d.h. er will KEINE Doppel-Logik,
sondern die EINE generalisierte Regel.

## Die Code-Realität, die du bewerten musst

`_on_station_clicked` (mw_qso.py:168) ist der EINE zentrale Start-Pfad. Er hat
bereits Guards:
- Diversity-Messung läuft → Abbruch
- Band SWR-gesperrt → Abbruch
- `encoder.is_transmitting` → Klick wird in `_pending_station_click` gemerkt,
  nach TX-Ende ausgeführt (P1.24)
- sonst → `_start_clicked_qso`: stoppt CQ, pausiert Auto-Hunt (falls aktiv,
  `on_manual_qso_start`), startet `qso_sm.start_qso(msg.caller, ...)`.

Wichtig: `start_qso` (qso_state.py:297) **bricht ein laufendes QSO ab** und
startet ein neues (`if self.state != IDLE: ... cancel pendings; set IDLE`).

P158s einziger Mehrwert gegenüber „direkt `_on_station_clicked`" ist der
**aufgeschobene Einschub**: laufendes Auto-Hunt-QSO wird NICHT abgebrochen,
sondern zu Ende gefunkt, B kommt DANACH, dann Auto-Resume.

## Mikes neue Spec impliziert vier Fälle, wenn B uns ruft und man klickt

1. **IDLE** (kein QSO, kein Auto-Hunt, kein CQ): B ist im QSO-Fenster (uns-Anruf
   wird angezeigt). Klick → einfach B sofort rufen (`_on_station_clicked` →
   `start_qso`). Trivial.
2. **CQ läuft, kein aktives QSO**: Klick → CQ stoppen, B rufen. `_start_clicked_qso`
   macht das schon.
3. **Aktives QSO mit anderer Station A läuft** (egal ob durch Auto-Hunt, CQ-Reply
   oder manuell gestartet): Klick auf B. → Hier ist die Frage: sofort A abbrechen
   und B rufen? ODER A zu Ende und B einschieben (heutiges P158-Verhalten)?
4. **Auto-Hunt aktiv** (Spezialfall von 1 oder 3): nach B soll Auto-Hunt weiterlaufen.

## Deine Aufgabe — bewerte EHRLICH

1. Ist Mikes generalisierte Regel („B ruft uns → im QSO-Fenster klickbar, IMMER,
   einzige Bedingung = uns-Anruf, kein 73/rr73") sauber umsetzbar, OHNE Risiko für
   die bestehende 95%-Logik?

2. **Kernfrage Einschub vs. Sofort-Abbruch:** Heutiges P158 macht „A zu Ende, dann
   B" (aufgeschoben). Wenn wir generalisieren und KEIN aktives QSO mit anderer
   Station verlangen — was passiert im Fall „aktives QSO mit A läuft, Mike klickt
   B"? Soll dann weiter eingeschoben werden (A zu Ende), oder ist das im
   QSO-Fenster-Kontext anders zu behandeln? Beachte: das RX-Listen-Verhalten
   (P1.24, `_on_station_clicked` → `start_qso`) BRICHT A sofort ab. Mike sagte
   früher (FEATURES §17): „RX-Liste = aktiv jagen (abbrechen OK), QSO-Fenster =
   passiv höflich". Heißt das, im QSO-Fenster sollte IMMER eingeschoben (A zu
   Ende) statt abgebrochen werden — auch ohne Auto-Hunt?

3. **Doppel-Pfad-Vermeidung (Mikes Hauptsorge):** Kann man die Klickbar-Bedingung
   einfach von 4 Conditions auf 1 reduzieren (`msg.target == my_call and not
   is_73/rr73`), und den Klick-Handler so umbauen dass er den Einschub-Mechanismus
   auch ohne Auto-Hunt nutzt (am QSO-Ende B rufen, danach ggf. Auto-Resume nur
   wenn Auto-Hunt lief)? Oder entstehen dadurch zwingend zwei Pfade?

4. **Konkrete Risiken** beim Lockern jeder einzelnen der 4 heutigen Bedingungen:
   - Bedingung 1 weg (Auto-Hunt-Zwang): Was bricht? (`take_pending_insert` /
     `_p158_maybe_start_inserted_call` prüfen heute `ah.active` — wenn kein
     Auto-Hunt, wird der Einschub NIE abgearbeitet! Das ist der Knackpunkt.)
   - Bedingung 3 weg (anderes-aktives-QSO-Zwang): Klickbar auch im IDLE — dann ist
     „Einschub am QSO-Ende" sinnlos (es gibt kein laufendes QSO), man müsste sofort
     rufen. Zwei verschiedene Klick-Wirkungen je nach State?

5. **Empfehlung:** (A) lassen wie es ist, (B) Klickbar-Bedingung lockern +
   Klick-Wirkung state-abhängig (IDLE→sofort, aktives QSO→einschieben), den
   Einschub-Abarbeitungs-Pfad von `ah.active` entkoppeln, (C) anders. Klare
   Empfehlung mit Begründung. Beachte KISS — keine verfrühte Abstraktion, aber
   auch kein zweiter paralleler Klick-Pfad (Mikes Sorge).

6. Gibt es Hardware-/Safety-Risiken? (TX läuft IMMER über ANT1; SWR-Sperre/
   Diversity-Guards sitzen in `_on_station_clicked` — bleiben die wirksam wenn
   der Einschub diesen Pfad reused?)

Sei knapp, konkret, mit Bezug auf die genannten Methoden/Zeilen.
