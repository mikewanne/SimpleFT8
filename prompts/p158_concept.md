# Konzept-Review (R1) — P158: Wartende Station während Auto-Hunt-QSO einschieben

Du bist Konzept-Reviewer für ein FT8-Hobby-Funker-Tool (KEIN Contest-Tool —
KISS, einfache Bedienung). KEIN Code generieren. Bewerte das Konzept, nenne
technische Stolperfallen + Edge-Cases, beantworte die offene Design-Frage,
gib am Ende eine klare Empfehlung. Kritisch sein, Overengineering vermeiden.

## Szenario (Mike, Field-beobachtet)
Auto-Hunt fährt gerade ein QSO mit Station A (z.B. EB3JT). Mitten drin ruft
eine FREMDE Station B (F5MYK) UNS an — im QSO-Log-Fenster springt eine Zeile
dazwischen: „← Empf. DA1MHH F5MYK IN97" (B ruft mein Call DA1MHH mit Grid).
Heute geht B verloren: Auto-Hunt ignoriert sie, das laufende A-QSO läuft weiter.

## Mike-Wunsch (P158)
- Die fremde „← Empf."-Zeile **im QSO-Log-Fenster selbst** (nicht in der
  separaten Empfangsliste!) anklickbar machen.
- Klick → B kommt in einen **Auto-Hunt-eigenen Puffer** (NICHT der bestehende
  RX-Listen-Klick-Puffer `_pending_station_click`, NICHT die CQ-Caller-Queue).
- Das laufende A-QSO wird **ZU ENDE geführt** (nicht abgebrochen).
- Danach: Auto-Hunt **pausiert**, wir rufen B manuell-gestartet.
- Vorteil: sehr hohe QSO-Chance, weil B nachweislich aktiv lauscht (rief uns).
- **Offene Design-Frage (Mike):** Nach Abschluss des B-QSO — soll Auto-Hunt
  (a) automatisch weiterlaufen, oder (b) manuell neu gestartet werden?

## Abgrenzung (WICHTIG — nicht vermischen)
- Bestehend `_pending_station_click` (P1.24): RX-Listen-Klick bricht laufendes
  QSO ab. P158 ist KEIN Abbruch — A wird fertig gefunkt.
- Bestehend Caller-Queue (`qso_sm.queue_changed`): Warteliste bei normalem
  CQ-QSO. P158 ist Auto-Hunt-spezifisch.

## Relevanter Code-Stand
- Auto-Hunt: `core/auto_hunt.py` (10-Min-Cap + 5-Min-Maus-Inaktivität +
  Totmannschalter; nach Stop ist PFLICHT-Neustart per User-Klick, KEIN
  Auto-Resume — ethischer Bot-Tarn-Schutz).
- Auto-Hunt-Stop-Defer existiert (P122): `stop_auto_hunt(reason)` deferiert
  3 zeitbasierte Reasons bis QSO-Ende.
- QSO-Log-Fenster `ui/qso_panel.py`: `log_view` ist QTextEdit `setReadOnly(True)`
  — Zeilen sind NICHT klickbar. `add_rx()` schreibt die „← Empf."-Zeilen als
  reinen Text.

## Konkrete Fragen
1. Konzept tragfähig + KISS? Oder zu komplex für den Nutzen?
2. **Technik QSO-Log klickbar:** QTextEdit read-only → klickbare Zeilen. Wie am
   saubersten (HTML-Anchor/`anchorClicked` vs cursorPositionAt-Klick-Parsing)?
   Welche Zeilen dürfen klickbar sein (nur fremde Calls die UNS rufen, während
   Auto-Hunt anderes QSO fährt)? Risiko Fehlklick.
3. **Auto-Resume vs manueller Neustart** nach dem eingeschobenen B-QSO —
   was passt besser, auch mit Blick auf den Totmann-/Bot-Tarn-Schutz?
   (Auto-Hunt war nie gestoppt, nur pausiert; Präsenz frisch durch Klick+QSO.)
4. Edge-Cases: A läuft in Timeout statt sauberem 73; B gibt auf während A noch
   läuft; mehrere fremde Anrufer; User klickt B während des B-QSO nochmal;
   Band-Sperre/SWR während Puffer.
5. Empfehlung: bauen / abspecken / verwerfen?
