[deepseek] ~47740 Tokens, 5 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=55120 out=5660 total=60780
**R1-Audit: P80 — Unified Gain Store (V2 Review)**

## ✅ Zusammenfassung

**V2 ist technisch solide, hat alle V1-Halluzinationen gefunden und korrigiert.**
Der Refactor vereinfacht die Architektur signifikant (–90LOC Code, +220LOC Tests) und setzt Mikes Anforderung konsequent um. Die Migration ist idempotent, ant2_calibrated löst das Sentinel-Problem sauber, und die Teststrategie deckt kritische Pfade ab.

**Push-Empfehlung: FREIGEGEBEN mit zwei Pflicht-Fragen vor V3 (siehe 🔴).**

---

## Findings nach Schweregrad

### 🔴 ROT (Bug, Datenverlust, falsche Logic)

**F1 – `_check_diversity_preset` prüft nicht `ant2_calibrated`**
- V2 sagt, dass `ant2_calibrated` eine Aufrufer-Sache sei. In `_check_diversity_preset` wird aktuell nur die Gültigkeit des Gain-Eintrags anhand des Alters geprüft. Wenn nach der Migration ein Eintrag existiert, der nur `ant1_gain` enthält (`ant2_calibrated=False`), würde `_enable_diversity` mit Standard-Gain gestartet, obwohl keine echte ANT2-Kalibrierung vorliegt. Das verletzt die Garantie, dass Diversity nur mit einer echten ANT1+ANT2-Messung startet.
- **Konsequenz:** Nach einem Update würde ein Nutzer von Normal auf Diversity schalten und unbemerkt mit unkalibrierten ANT2-Werten arbeiten (z. B. 0 dB Gain statt optimaler 20 dB).
- **Korrektur:** In `_check_diversity_preset` muss nach dem Alters-Check auch `entry.get("ant2_calibrated") is True` geprüft werden, falls der Eintrag zum Diversity-Modus gehört. Für den Normal-Modus ist das irrelevant.

**F2 – Normal-Mode initial liest `ant1_gain` mit falsy-Fallback**
- V2-Vorschlag für `_apply_normal_mode` benutzt `if entry.get("ant1_gain"):`. Da der Migrations-Wert aus `normal_presets` 0 sein kann (falls der Eintrag nur `gain` hatte und `ant2_gain=0`), würde `ant1_gain=0` als falsy gewertet und auf `PREAMP_PRESETS` zurückgefallen. 0 ist zwar kein gültiger Gain-Wert (Verstärkerbereich 10/20), aber der Eintrag ist ja vorhanden und sollte als „kalibriert“ angezeigt werden. Robuster: `ant1_gain = entry.get("ant1_gain") if entry.get("ant1_gain") is not None else PREAMP_PRESETS.get(band, 10)`. Kein Crash, aber Inkonsistenz.

### 🟠 ORANGE (Risiko, Edge-Case, KISS-Verletzung)

**F3 – DXTuneDialog liefert u.U. unterschiedliche Gains pro Scoring**
- `get_results()` berechnet `ant1_gain`/`ant2_gain` separat für „standard“ und „dx“ (`_build_scoring_result`). In der Praxis sind sie bisher identisch (Mike-Verifikation), aber der Algorithmus erlaubt Abweichungen. V2 nimmt den „standard“-Eintrag für die persistierten Werte. Sollte der Nutzer später in den DX-Modus wechseln, könnte ein suboptimaler Gain für ANT1/ANT2 verwendet werden, falls die Optima auseinanderfallen.
- **Minderung:** Die empirische Basis sagt, dass das nicht passiert; der Fall würde sofort im Field-Test auffallen. Trotzdem: defensiv könnte man die Gains aus beiden Sub-Results mergen (z. B. den Mittelwert, oder den maximal sinnvollen). V2-Vorschlag ist akzeptabel, aber V3 sollte eine Log-Message spendieren, wenn `std`- und `dx`-Gain-Werte abweichen — dann sieht man es im Field-Test.

**F4 – `ant2_calibrated`-Prüfung im Cancel-Pfad nicht vollständig**
- In `_on_dx_tune_rejected` (Z.1733) soll nach V2 nur geprüft werden, ob ein Eintrag existiert und `ant2_calibrated=True`, dann Stale-Acceptance. Wenn der Eintrag aber älter als 6 h ist, ist er trotzdem stale und sollte ggf. nicht blind übernommen werden. Bisher war der Cancel-Pfad nur für den Fall gedacht, dass der Nutzer die Messung abbricht und trotzdem mit veralteten Werten weiterarbeiten will. Mit dem neuen `ant2_calibrated` sollte die Logik konsistent sein: **stale** (Alter >6 h) sollte trotzdem akzeptiert werden, aber nur wenn `ant2_calibrated=True`. Das ist in V2 implizit gemeint, sollte explizit dokumentiert werden.

### 🟡 GELB (Verbesserung, Doku, Testlücke)

**F5 – Migration in `PresetStore.__init__` ist ein versteckter Seiteneffekt**
- V2 bindet `migrate_legacy_files()` in den Konstruktor ein. Das erleichtert den Boot, erschwert aber Unit-Tests (jede Store-Instanziierung triggert Migration). Mit `tmp_path`/Monkeypatch lösbar, wie V2 schon plant. Allerdings könnte man die Migration in `main.py` vor dem ersten Store-Init ausführen, damit der Konstruktor „pure“ bleibt. Vorteil: sauberere Testbarkeit, Nachteil: mehr Boilerplate. Für die geringe Komplexität des Projekts ist V2’s Ansatz okay, aber eine explizite Boot-Funktion wäre zukunftssicherer. Ich gebe keinen harten Ratschlag, aber empfehle, im Code und Docstring zu dokumentieren, dass `__init__` eine Migration durchführen kann.

**F6 – Dokumentation der neuen Store-Struktur fehlt**
- Weder in V2 noch aktuell gibt es eine zentrale Doku zur `presets.json`. Die Migration ist zwar selbst-dokumentierend, aber eine kurze `README.md`-Zeile oder ein Docstring im `PresetStore`-Header hilft bei späteren Debugs. Trivial, aber nützlich.

**F7 – Test für `gain_timestamp=0.0` als „ungültig“**
- V2 schlägt vor, dass `is_valid_gain` bei `ts==0.0` False zurückgibt (Migration-Marker). Das ist sinnvoll, aber nicht explizit getestet. Im `test_p80_unified_gain.py` sollte ein Test sein: ´store.save_gain(...)` mit ts=0 → `is_valid_gain` liefert False.

### ⚪ WEISS (INFO)

- Backwards-Compat: keine Alias-Wrapper nötig, alle Aufrufer im Repo. Bestätigt.
- Race-Conditions: Migration idempotent, kein File-Lock nötig.
- Hardware: TX-Pfad unberührt, ANT2 bei Diversity-Wechsel nur aktiv wenn `ant2_calibrated=True`, also sicher.

---

## Spezielle Prüf-Punkte (aus Prompt)

1. **`gain_timestamp=0.0`-Marker:** Ja, R1 hält das für sinnvoll. `is_valid_gain` soll False liefern, Re-Kalibrierung wird automatisch angestoßen.  
2. **`ant2_calibrated`-Konzept:** Aufrufer-Schicht (mw_radio) ist die richtige Stelle. `PresetStore` bleibt einfach. Ein optionaler Parameter in `is_valid_gain` würde die Abstraktion verwässern.  
3. **Migration in `__init__`:** Akzeptabel, solange dokumentiert und Idempotenz gewährleistet. Separater Boot-Call wäre sauberer, aber für den Zweck vertretbar.  
4. **Backwards-Compat:** Keine externen Skripte → kein Problem.  
5. **DXTuneDialog `get_results` Sub-Key:** Standard nehmen ist okay, da empirisch identisch. Vorschlag: `assert std_gains == dx_gains` mit Log-Warnung, wenn jemals abweichend.  
6. **Race-Conditions:** Single-Process, idempotent → kein File-Lock nötig.  
7. **Test-Coverage Lücken:** `ant2_calibrated`-Prüfung in Diversity-Pfad muss explizit getestet werden. Die vorgeschlagenen 25 Tests decken das ab, wenn sie `_check_diversity_preset` mocken oder integrieren. Fehlt ggf. ein Test: „Diversity ohne ANT2-Kalibrierung → Messung wird gestartet“.  
8. **Hardware-Pflicht:** `_apply_normal_mode`-Fallback auf `PREAMP_PRESETS` greift, wenn `ant1_gain==0`, d.h. kein taubes Radio. Sicher.

---

## Antworten auf V2's offene Fragen an R1

1. **`ant2_calibrated`-Sentinel:** Boolean ist sauberer als `ant2_gain==0`, bleibt.
2. **Migration in `__init__`:** Für P80 okay, aber Docstring ergänzen.
3. **Legacy-Files:** Bleiben lassen, keine automatische Löschung – so kann ein Rollback manuell erfolgen. Später per Cleanup-Skript.
4. **`is_valid_gain` Diversity-Check:** Aufrufer-Sache (mw_radio). `PresetStore` weiß nichts über RX-Modi.
5. **`commit_gain` ohne FT-Mode:** Tests müssen alle angepasst werden, ja.
6. **Backwards-Compat-Aliase:** Keine, einheitlicher Refactor.
7. **DXTuneDialog Sub-Key:** Standard nehmen; wenn beide abweichen, Log-Warnung. Mergen ist unnötig.
8. **DT-Korrektur bleibt separat:** Wurde in V1/V2 nicht angetastet – korrekt.

---

## PUSH-Empfehlung

**PUSH FREIGEGEBEN nach V3, sobald F1 und F2 behoben sind.**  
(Die orange-Findings sind akzeptabel, gelb optional.)  
V3 muss enthalten:
- In `_check_diversity_preset` Prüfung auf `ant2_calibrated` für Diversity.
- `_apply_normal_mode` robuster Fallback (nicht falsy).
- Test für `gain_timestamp=0.0` und `ant2_calibrated` in Diversity-Pfad.

Overall ein hervorragend analysiertes V2 – solide Basis für den nächsten Schritt.
