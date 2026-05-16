## Findings

### F-R1-1 (Hinweis) – Wortlaut juristisch tragfähig, keine Lücken
**Was:** Der vorgeschlagene Disclaimer-Text (aus `prompts/intent_klausel_v1.md`) benennt die wesentlichen Risiken: Hardware-Defekte, Funklizenz-Verstöße, Betrieb ausschließlich auf eigene Gefahr. Die ausdrückliche Nennung der MIT-Lizenz schafft Klarheit über die rechtliche Basis; der standardmäßige Gewährleistungsausschluss der MIT-Lizenz wird hier noch einmal explizit bekräftigt, was für ein Hobbyprojekt ohne professionellen Support hilfreich ist. Der Hinweis auf die ANT2-Nutzung (Regenrinne) bleibt – wie in der Abwägung (V1) beschrieben – bewusst redundant zum Body, um auch bei flüchtigem Lesen auf die Gefahr hinzuweisen.  
**Empfehlung:** Keine Änderung am Wortlaut. Die Klausel ist für ein unentgeltliches Bastel-Tool angemessen. Auf spezielle Privacy-/Datenverarbeitungshinweise kann verzichtet werden, da die App keine personenbezogenen Daten verarbeitet (alles lokal).

### F-R1-2 (Risiko) – Dialoghöhe 380 px könnte auf abweichenden Systemen zu eng sein
**Was:**  
- Die Berechnung aus V2 (Findings F1, F2) geht von Menlo 11 pt und einer Textbreite von ca. 468 px aus und kommt auf ~7 Zeilen für den Disclaimer.  
- Der Dialog nutzt `setFixedSize(540, 340)` und ist nicht resizable; ein abgeschnittener Text wäre nicht mehr erreichbar.  
- Bei HiDPI-Displays oder anderen Font-Substitutionen kann die tatsächliche Texthöhe etwas abweichen. Ein Puffer ist daher ratsam.  
**Empfehlung:** `dlg.setFixedSize(540, 400)` – das gibt ausreichend Spielraum, ohne das Layout zu überdehnen. Die Änderung erhöht die Box um weitere 20 px gegenüber dem Vorschlag 380 und vermeidet zuverlässig abgeschnittenen Text.

**Konsequenz für Tests:** AC5 sollte auf `540×400` angepasst werden; Test T4 auf `>= 400`.

### F-R1-3 (KISS-Entscheidung) – Kein separates Dialog-Modul nötig
**Was:** Der V2-Self-Review hat zutreffend festgehalten, dass der Dialog einfach ist und nur an einer Stelle existiert. Eine Auslagerung in `startup_disclaimer_dialog.py` (in TODO.md als Möglichkeit erwähnt) brächte hier nur zusätzliche Komplexität ohne Mehrwert.  
**Empfehlung:** Änderung weiterhin direkt in `main.py:_show_hardware_warning` vornehmen. KISS-Ansatz beibehalten.

---

## Push-Empfehlung

**Bedingt freigegeben.**  
- Der Disclaimer-Text und die sonstigen ACs sind in Ordnung.  
- Die Höhe des Dialogfensters muss jedoch von 340 auf **400 px** erhöht werden, um ein Abschneiden unter verschiedenen Darstellungsbedingungen sicher zu verhindern.  
- Nach dieser Anpassung (inkl. Aktualisierung von AC5 und Test T4 auf 400 px) ist der Patch ohne weitere Einschränkungen push-fähig.
