[deepseek] ~19880 Tokens, 2 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=24022 out=6757 total=30779
## Kritik des V3-Plans (P14 – DT-Werte-Asymmetrie)

Ich habe den gesamten Vorschlag (V1 + V2 Self-Review) sowie den aktuellen Code (`core/ntp_time.py`) gründlich analysiert. Nachfolgend meine Findings in tabellarischer Form, kategorisiert nach Schweregrad.

---

| Schwere | Finding | Datei:Zeile | Empfehlung |
|---------|---------|-------------|------------|
| **KRITISCH** | Kombination aus `DEADBAND=0.05` und getrimmtem Median (10%) kann die Korrektur auf einem systematischen Bias von -0,05s einfrieren. Bei Mikes 20 Werten liefert der getrimmte Median -0,05 (exakt Deadband-Grenze) → kein Update, obwohl ein echter Bias vorliegt. Das *verschlechtert* die Situation gegenüber dem ungetrimmten Median, der -0,1 ergab und damit ein Update auslösen würde. | `ntp_time.py:29` (DEADBAND) + `update_from_decoded` Zeile ~237 (Vergleich) | **DEADBAND auf 0,02 reduzieren** oder adaptiv machen (z.B. DEADBAND = 0,02 + 0,01·(10/n)). Nur so kann ein Restbias <50ms ausgeregelt werden. Andernfalls wird die V3-Maßnahme das Problem *nicht* beheben. |
| **KRITISCH** | Der Plan geht nicht der Ursache nach, warum der bestehende Algorithmus mit einfachem Median die Korrektur nicht von 0,27 auf ~0,20 gesenkt hat. Mikes Rohmedian (-0,1) liegt außerhalb des Deadbands, also *müsste* ein Update erfolgen. Der Screenshot zeigt aber eine konstante Korrektur. Mögliche Gründe: Phasenwechsel-Mechanik (measure/operate) hängt oder Buffer wird nicht korrekt geleert. Ein getrimmter Median ist nur ein Symptom-Fix und könnte das eigentliche Problem (Bug) überdecken. | `ntp_time.py:195-245` (update_from_decoded) | **Vor jeder Änderung: Unit-Test mit Mikes Originaldaten und einfachem Median schreiben** – erwartet: `_correction` ändert sich von 0,27 auf 0,20. Falls der Test fehlschlägt, muss der Fehler im Algorithmus (z.B. Phasenlogik, Dämpfung bei `_is_initial=False`) gefunden und behoben werden, bevor irgendein Trim eingebaut wird. |
| **SOLLTE-FIX** | Getrimmter Median mit `trim_frac=0.1` entfernt bei n=20 nur 2 Werte pro Seite. Die verbleibenden Werte -0,7 und -0,4 (innerhalb der 2. Hälfte) verzerren den Median weiterhin. Ein robusterer Schätzer wie **Hampel-Filter** (MAD-basiert, z.B. Cutoff=3) würde alle Ausreißer adaptiv entfernen, unabhängig von ihrer Anzahl. | `_trimmed_median` (neu) | Ersetze `_trimmed_median` durch eine **MAD-basierte Funktion**: berechne Median, MAD (median absolute deviation), entferne alle Werte mit `|x - median| > k * MAD` (z.B. k=2,5), dann Median der Restdaten. Fallback zu einfachem Median wenn n<7. Alternativ: `trim_frac` auf **0,2** erhöhen (bei n=20→4 Werte pro Seite entfernen). |
| **SOLLTE-FIX** | Damping-Änderung 0,7→0,5 ist unnötig und erhöht die Korrekturzeit ohne Mehrwert. Wenn das Deadband reduziert wird, konvergiert das System auch mit Damping=0,7 schnell genug. KISS-Prinzip: Nur einen Parameter ändern. | `ntp_time.py:30` | **DAMPING auf 0,7 belassen.** Falls nötig, nach Feldtest separat optimieren. |
| **SOLLTE-FIX** | Tests decken die **Grenzfälle** nicht ausreichend ab. Fehlt: n=10 mit zwei Ausreißern auf derselben Seite (Trim entfernt nur einen), n=10 mit Ausreißer genau an der Trim-Grenze, FT4/FT2-Pfade (n=1,3,8) bei denen `_trimmed_median` auf `statistics.median` fallen muss. Auch kein Test für *mehrere* aufeinanderfolgende Messzyklen (Konvergenz-Test). | `tests/test_p14_dt_symmetry.py` | **Ergänze Tests:**<br>– `test_trimmed_median_n10_two_lows` → erwartet Median ≠ einfacher Median (Trim entfernt nur einen der beiden -1.0).<br>– `test_trimmed_median_n9_below_threshold` → exakt gleich wie `statistics.median`.<br>– `test_median_buffer_not_updated_within_deadband` (T6): verwende `pytest.approx` für Fließkomma.<br>– `test_convergence` (mocked 20 Werte 3 Zyklen) → prüfe Endkorrektur. |
| **KOENNTE** | Feldtest-Plan verlässt sich auf Screenshots, die nur die finale Verteilung zeigen. Aussagekräftiger wäre ein **Log-File** pro Slot mit: rohe DT-Liste, getrimmter Median, avg_median, Entscheidung (Update oder nicht). So könnten wir die Konvergenz detailliert analysieren. | Field-Test-Plan | Füge eine temporäre Debug-Option hinzu (z.B. `--log-dt`), die für jeden Slot eine Zeile in `dt_debug.log` schreibt. Mike kann das Log nach 30 Min an uns senden. |
| **HINWEIS** | DT-Konvention ist korrekt: Ziel-Median = 0 (kein Versatz). WSJT-X / JTDX verwenden ebenfalls eine auf 0 zentrierte Korrektur. Ein asymmetrisches Totband wäre ein Konventionsbruch. | – | Keine Änderung nötig. |
| **HINWEIS** | Es gibt eine ungenutzte Wechselwirkung mit dem Fast-Path (P48D): Dieser verwendet `statistics.stdev(valid)` auf *allen* Werten (nicht getrimmt). Wenn der getrimmte Median das System anders einstellt, könnte der Fast-Path anders zünden. Dies sollte dokumentiert bleiben, ist aber kein akutes Problem. | `ntp_time.py:225-233` | Dokumentiere im Code (oder `HANDOFF.md`), dass `stdev` nicht getrimmt wird – bewusst, um frühzeitige Konvergenz nicht zu blockieren. |

---

## Gesamtbewertung

**5/10** – Der V3-Plan hat eine realistische Stoßrichtung (Ausreißerproblematik erkennen), aber die konkreten Parameter (trim_frac=0,1, Damping-Änderung, Deadband=0,05) sind statistisch ungeschickt gewählt und könnten das Problem verschlimmern. Der größte Fehler: Es wird nicht die Ursache der fehlenden Konvergenz untersucht.

## Entscheidung

**Code-Schreiben wird nicht freigegeben.**  
V3 muss zuerst folgende Nachbesserungen erhalten:

1. **Unit-Test mit Mikes Rohdaten und einfachem Median** – stellt sicher, dass der existierende Algorithmus überhaupt funktioniert (Erwartung: _correction → 0,20). Falls nicht, Bugfix in `update_from_decoded` (Phasenlogik / Buffer / Damping für `_is_initial=False`).
2. **Deadband auf 0,02 reduzieren** – sonst friert die Korrektur auf -0,05 ein.
3. **Trim durch MAD-basierten Filter ersetzen** – adaptiv, robuster bei wenigen oder mehreren Ausreißern. Alternativ `trim_frac` auf 0,2 erhöhen.
4. **Damping auf 0,7 belassen** – kein zweiter Hebel.
5. **Tests erweitern** (siehe Tabelle) und **Debug-Logging** einbauen.

Erst nach diesen Korrekturen kann die Implementierung beginnen. Die Freigabe erfolgt dann per erneuter R1-Review (V4) durch mich.
