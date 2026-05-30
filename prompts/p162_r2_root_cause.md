# R2-Review P162: Root-Cause-Klärung BEVOR wir Code schreiben

Du hast in R1 für den EG5SUN-Bug die Minimal-Variante (a) empfohlen: neue Regel
NUR bei `state == WAIT_REPORT` + `msg.is_r_report` → RR73. Inzwischen habe ich
den Code weiter verifiziert und einen Widerspruch gefunden, den ich dir vorlege.
Bitte überdenke deine Empfehlung mit diesen NEUEN Fakten. Antworte knapp.

## NEUE FAKTEN (im Code verifiziert, Datei:Zeile)

**Fakt 1 — Reihenfolge ist HART garantiert (dein R1-Blocker #1 ist entschärft):**
`ui/mw_cycle.py:177-209` + `ui/mw_radio.py:61-66`: Der Decoder emittiert pro Slot
in fester Qt-FIFO-Reihenfolge: (1) `cycle_decoded`→`_on_cycle_decoded`, (2) pro
msg `message_decoded`→`on_message_decoded`→`qso_sm.on_message_received`, (3)
`cycle_finished`→`_on_cycle_finished`→`qso_sm.on_decoder_finished`. Also läuft
`on_message_received` für ALLE Messages eines Slots GARANTIERT VOR
`on_decoder_finished`. Das war ein bewusster Fix (v0.82 Fix E, gegen Doppel-
Report-Bug). Connection-Typ ist Standard-Qt (gleicher Sender=Decoder → FIFO).

**Fakt 2 — der R-Report-Pfad in WAIT_REPORT EXISTIERT BEREITS:**
`core/qso_state.py:622-637`: In `on_message_received`, State WAIT_REPORT,
`if msg.is_report: ... if msg.is_r_report: → set TX_RR73 + send RR73`. Also:
ein R-Report in WAIT_REPORT führt SCHON HEUTE zu RR73.

**Fakt 3 — der Filter-Layer verschluckt den R-12 NICHT:**
`ui/mw_cycle.py:819-913`: P124(Hash)/P128(nur add_rx-Log)/P144(nur wenn
target!=my_call)/P94/OMNI — keiner greift für `DA1MHH EG5SUN R-12` (target=my,
caller=their_call). Die msg erreicht `qso_sm.on_message_received` Z.913 sauber.

**Fakt 4 — was wir tatsächlich senden:** 5× `EG5SUN DA1MHH -25`. Das Format
`their my our_snr` (Report, KEIN RR73) wird NUR erzeugt von:
- `on_decoder_finished` WAIT_REPORT-Retry (qso_state.py:417), ODER
- `on_decoder_finished` WAIT_RR73-Retry (Z.433), ODER
- `on_message_received` WAIT_REPORT plain-report `advance()` (Z.636), ODER
- WAIT_RR73 plain-report/grid-Retry (Z.708/729).

## MEIN LOGISCHER SCHLUSS (bitte prüfen/widerlegen)

Aus Fakt 1+2+3 folgt zwingend: WENN der State zum Zeitpunkt des R-12-Empfangs
WAIT_REPORT gewesen wäre, hätte Z.629 RR73 gesendet (message_received läuft
garantiert vor dem decoder_finished-Retry). Da wir STATTDESSEN `-25` senden,
muss der State ETWAS ANDERES gewesen sein als WAIT_REPORT — ODER `is_r_report`
war für "R-12" überraschend False.

→ **Deine R1-Empfehlung (Variante a: nur WAIT_REPORT) wäre damit FUNKTIONAL
IDENTISCH zum schon existierenden Z.629-Pfad → würde den Bug NICHT fangen.**

## OFFENES PROBLEM: Wir haben KEIN State-Trace

Die State-Machine loggt nur nach `qso_debug.log`, das pro QSO ÜBERSCHRIEBEN
wird → die EG5SUN-Sequenz ist weg. Wir können den State zum R-12-Zeitpunkt NICHT
aus Logs rekonstruieren. Das persistente `debug_*.log` enthält nur HUNT-Events
(kein RX/State).

## MEINE FRAGEN AN DICH

F1: Stimmt mein logischer Schluss? Ist „nur WAIT_REPORT" damit wertlos für
diesen Bug? Oder übersehe ich einen Weg, wie WAIT_REPORT trotz Fakt 1+2 mit -25
statt RR73 antwortet (z.B. is_r_report-Parsing-Edge bei "R-12")?

F2: Plausibelste Wurzel, gegeben Fakt 1-4? Kandidaten:
(i) State war WAIT_RR73 (nicht WAIT_REPORT): dann läuft Z.677 (is_r_report →
   advance→RR73). Auch das sendet RR73, nicht -25. Außer rr73_retries>5 (Cap) →
   dann P100-Pfad (Z.681 → TIMEOUT/Log). Aber wir sehen 5× Wiederholung VOR
   Timeout, nicht sofort. Passt nicht sauber.
(ii) State war TX_CALL/TX_REPORT (wir sendeten gerade, R-12 kam als pending):
   Z.500/652 → on_message_sent → RR73. Auch nicht -25.
(iii) `our_snr` war gesetzt und ein Retry-Pfad feuerte BEVOR message_received
   den R-12 verarbeiten konnte — würde Fakt 1 widersprechen.
(iv) is_r_report war False für "R-12" → dann plain-report-Pfad advance()/retry
   → sendet -25! Das würde ALLES erklären. Ist "R-12" → is_r_report=True
   garantiert? `is_r_report = field3.startswith("R") and is_report`,
   `is_report`: f3 ohne führendes R muss int -50..50 sein. "R-12"→"-12"→-12 ✓.
   Scheint True. Aber: was wenn der Decoder "R−12" mit UNICODE-Minus (U+2212)
   liefert statt ASCII "-"? Dann int() failt → is_report=False → is_r_report
   =False → plain-Pfad? Bitte bewerte diese Unicode-Hypothese.

F3: Gegeben dass wir die Wurzel NICHT beweisen können — ist es
verantwortungsvoll, ZUERST ein State-Trace ins persistente Log einzubauen
(additiv, kein Verhalten geändert) und Mike beim nächsten EG5SUN-Fall die
lückenlose Sequenz einfangen zu lassen, BEVOR wir den Fix committen? Oder ist
eine breite defensive Regel (is_r_report von their_call → RR73 in ALLEN
Warte+TX-States, mit pending-Mechanik in TX-States) sicher genug, um sie jetzt
zu bauen — gegeben dass die alten 6 Pfade als Fallback drin bleiben?

F4: Falls breite Regel: Wo platzieren — in `on_message_received` ganz vorne
(nach den 2 Guards), für States {WAIT_REPORT, WAIT_RR73} direkt RR73 und
{TX_CALL, TX_REPORT} als pending? Bricht das die bestehende pending-Mechanik
oder die WAIT_RR73-Cap-Logik (die du in R1 schützen wolltest)? Beachte: wenn wir
NUR is_r_report abfangen (nicht plain-report), bleibt die WAIT_RR73-plain-report-
Cap-Logik (Z.708) unberührt — stimmt das?

F5: Konkrete Empfehlung für den JETZT-Schritt (Mike ist weg, ich arbeite
autonom, alte Pfade bleiben als Fallback, Field-Test folgt): (A) erst Trace dann
Fix, (B) breite Regel jetzt + Trace dazu, (C) etwas anderes. Begründe.

Code ist Referenz. Wo du etwas nicht aus dem Vorgelegten ableiten kannst, sag es
explizit statt zu raten. Sei knapp und konkret.
