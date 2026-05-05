## Plan-V2 Review – Ergebnisse

### 📋 Übersicht  
**Review-Gegenstand:** P1.10 Plan-V2 (8 Diffs, 11 Tests)  
**Basis-Code:** `core/qso_state.py`, `core/encoder.py`, `ui/mw_qso.py` (v0.95.3)  
**Bewertungsphase:** Kritische Prüfung vor Plan-R1  

---

### ⛔ KRITISCH (0)  
Keine kritischen Fehler gefunden. Die Diffs sind syntaktisch korrekt und logisch konsistent.

---

### 🟡 WICHTIG (3)

#### Finding 1 – Gemeinsamer `rr73_retries`-Zähler in WAIT_73  
**Code-Referenz:** `core/qso_state.py:582-597` (D4, unveränderter `elif msg.is_r_report`-Pfad)  
**Problem:**  
Der Höflichkeits-R-Report-Pfad in `WAIT_73` verwendet denselben Zähler `qso.rr73_retries` wie der `WAIT_RR73`-Pfad. Wenn ein QSO vor Eintritt in `WAIT_73` bereits mehrere Retries in `WAIT_RR73` durchlaufen hat (z. B. 2 von 3), sind in `WAIT_73` nur noch 0 statt 2 Höflichkeits-Retries erlaubt. Dies kann dazu führen, dass ein R-Report ignoriert wird, obwohl noch Kapazität vorhanden wäre.  
**Empfehlung:**  
Separaten Zähler für `WAIT_73` einführen (z. B. `wait_73_retries`) oder den Zähler bei Eintritt in `WAIT_73` zurücksetzen. Alternativ als Known Issue dokumentieren (wenn keine Verhaltensänderung gewünscht).  

---

#### Finding 2 – Irreführende QSO-Panel-Info bei Courtesy-73  
**Code-Referenz:** `ui/mw_qso.py:425-429` (`_on_tx_slot_for_partner`) + D4  
**Problem:**  
In D4 wird `tx_slot_for_partner.emit(msg)` aufgerufen. Das Signal löst in `mw_qso.py` den Slot `_on_tx_slot_for_partner` aus, der standardmäßig die Panel-Info `"Antworte DA1TST (ANT1)"` anzeigt. Für ein Courtesy-73 (keine Antwort auf CQ) ist dieses Label irreführend und könnte den Nutzer verwirren.  
**Empfehlung:**  
Entweder ein Flag im Signal-Objekt mitgeben (z. B. `is_courtesy=True`), das im Handler die Textauswahl steuert, oder die Panel-Info für Nicht-CQ-Fälle unterdrücken. Minimaler Aufwand, verbessert UX.  

---

#### Finding 3 – Fehlender defensiver Test für RR73 während TX_73_COURTESY  
**Code-Referenz:** `tests/test_p1_10_courtesy_73.py` – Test 10  
**Problem:**  
Test 10 prüft nur den Empfang eines zweiten `73` während `TX_73_COURTESY`. Der Fall eines eingehenden `RR73` während dieses States wird nicht getestet. Der Produktivcode ignoriert beide (da State nicht `WAIT_73`), aber ein Test für `RR73` fehlt.  
**Empfehlung:**  
Test 10 um eine ähnliche Assertion für `_make_rr73_msg()` erweitern (z. B. in einem separaten Test).  

---

### 🟢 OPTIONAL (3)

#### Finding 4 – Debug-Ausgabe `"CQ-Reply"` bei Courtesy-73  
**Code-Referenz:** `ui/mw_qso.py:425-429`  
**Problem:**  
Der Debug-Print in `_on_tx_slot_for_partner` lautet `"[TX] CQ-Reply {msg.caller}: ..."`. Bei einem Courtesy-73 ist keine CQ-Reply im Spiel → irrelevante Ausgabe im Log.  
**Empfehlung:**  
Z. B. über den aktuellen State unterscheiden: `"CQ-Reply"` vs `"Courtesy-73 Slot"`.  

---

#### Finding 5 – Kein Test für R-Report-Höflichkeit in WAIT_73 nach P1.10  
**Code-Referenz:** `tests/test_p1_10_courtesy_73.py`  
**Problem:**  
Der Höflichkeits-`R-Report`-Pfad in `WAIT_73` (Senden eines erneuten RR73 bei `msg.is_r_report`) wird nicht explizit getestet. Obwohl der Code unverändert bleibt, könnte eine Regression durch die neue `courtesy_73_sent`-Logik auftreten (z. B. wenn ein R-Report vor dem 73 kommt und `courtesy_73_sent` noch False ist – das ist okay, aber ein Test deckt diese Sequenz nicht ab).  
**Empfehlung:**  
Einen Test `test_wait_73_with_r_report_before_73` hinzufügen, der prüft, dass der R-Report-Pfad weiterhin funktioniert und kein Courtesy-73 unterdrückt wird.  

---

#### Finding 6 – Slot-Parität nur auf Signal-Ebene getestet  
**Code-Referenz:** `tests/test_p1_10_courtesy_73.py` – Test 9  
**Problem:**  
Test 9 prüft, ob `tx_slot_for_partner.emit(msg)` mit der erwarteten `msg._tx_even` feuert. Der finale Effekt auf `encoder.tx_even` (Integration) wird nicht abgedeckt. Plan-V2 verweist auf den Field-Test – das ist akzeptabel, aber für automatisierte Sicherheit wäre ein Integration-Test (z. B. mit gemocktem Encoder) wünschenswert.  
**Empfehlung:**  
Kann auf später verschoben werden. Optional: Kurzen Integration-Test in `tests/test_integration_courtesy_73.py` ergänzen, der den gesamten Pfad von `WAIT_73` bis zur Änderung von `encoder.tx_even` prüft.  

---

### 📐 Reihenfolge der Implementation  
**Bewertung: ✅ Sauber**  
1. App stoppen  
2. D1+D2+D8+D3 (Enum, Dataclass, Timeout-Liste, on_message_sent)  
3. D4 (WAIT_73-Hauptlogik)  
4. D5 (is_tx in mw_qso)  
5. D6 (Version-Bump)  
6. D7 (Tests)  

Keine Abhängigkeitskonflikte. D8 benötigt den neuen Enum-Wert aus D1, daher korrekt vor D4 platziert.  

---

### ⚠️ Risiken  
- **Finding 1 (rr73_retries)** ist ein bestehendes, nicht durch P1.10 eingeführtes Risiko. Es sollte jedoch im Plan als Known Issue dokumentiert werden, nicht erst im Memory.  
- **D8 (3-Min-Timeout-Ausschluss)** wird als sinnvoll bewertet (billig, schließt hypothetischen Edge-Case, keine negativen Effekte). Kein Overengineering.  
- **Slot-Parität via Signal** ist korrekt implementiert. Die fehlende End-to-End-Absicherung wird durch Field-Test kompensiert (akzeptabel).  

---

### 🧪 Test-Coverage  
**Deckt alle Akzeptanzkriterien ab?**  
Ja – die 11 Tests prüfen:  
- Courtesy-73 bei 73/RR73 (1,2)  
- Einmaligkeit (3)  
- QSO-Confirmed nach TX_73_COURTESY (4,5)  
- Kein Doppel-ADIF (6,7)  
- Timeout ohne Änderung (8)  
- Slot-Parität (9)  
- Second-73 während TX_73_COURTESY (10)  
- Vorwärtssprung ohne Doppel-ADIF (11)  

**Fehlende Edge-Cases:**  
- R-Report vor 73 in WAIT_73 (siehe Finding 5)  
- RR73 während TX_73_COURTESY (siehe Finding 3)  

---

### 📝 Zusammenfassung  
Plan-V2 ist solide, die Diffs sind korrekt und die Reihenfolge sauber. Keine kritischen oder schwerwiegenden Mängel. Die wichtigen Findings betreffen den gemeinsamen `rr73_retries`-Zähler sowie UX/Debug-Unschärfen bei der Console- und Panel-Ausgabe. Die optionalen Findings verbessern die Testtiefe und Lesbarkeit.  

**Empfehlung:**  
1. Finding 1 (rr73_retries) vor Plan-V3 adressieren oder dokumentieren.  
2. Finding 2 und 4 als Low-Hanging-Fruit in D5 einbauen (Änderung in `ui/mw_qso.py`).  
3. Finding 3 und 5 als Test-Erweiterung in D7 aufnehmen.  
4. Rest wie geplant umsetzen.  

**Nächster Schritt:** Plan-R1 (DeepSeek-Reasoner) – diese Findings einfließen lassen.
