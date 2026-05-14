Final-Code-Review Bundle J (v0.97.27): Connect-Modal Version+MIT Footer,
SimpleHelpDialog (einheitlicher Help-Dialog mit Scrollbar), _antenna_pref_label
mit RX-Prefix bei ANT2, Intent-Klausel im Hardware-Disclaimer.

Bitte reviewe die folgenden geaenderten Files auf:
- Korrektheit (greift der Footer beim App-Start? Modal-Verhalten?
  Markdown-Render? Test-Mock-Pfade?)
- Bugs (Threading, Race-Conditions, NULL-Pointer-Risk, Lifecycle)
- KISS (Overengineering, unnoetige Abstraktion?)
- Hardware-Pflicht ANT1=TX: Bundle J aendert NICHTS an TX-Logik.
  set_tx_antenna("ANT1") wird unveraendert vor jedem ptt_on()/tune_on()
  gerufen (core/encoder.py:389 + ui/mw_tx.py:83).

Mike-Designentscheidung: alle ?-Hints im 700×600 SimpleHelpDialog mit
Weissraum — Konsistenz vor Optimum-pro-Dialog. NICHT als Overengineering
melden — explizit von Mike gewuenscht (TODO J-Punkt 2).

Format: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).
Antwort beginnt mit "Push freigegeben." oder konkretem Bug-Fix-Bedarf.
