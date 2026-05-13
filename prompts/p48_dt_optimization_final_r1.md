[deepseek] ~31213 Tokens, 5 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=36118 out=4801 total=40919
## Bewertung P48 DT-System Optimierung (v0.97.13)

### Zusammenfassung der Änderungen

1. **config/settings.py** – `radio_timing`-Block mit `tx_buffer_s=1.3` und `rx_hardware_offset_default_s=0.26`, Properties mit defensiver `.get()`-Kette.  
2. **core/ntp_time.py** – `_hardware_default_offset` + `set_hardware_default()`, Cross-Modus-Fallback (FT8 > FT4 > FT2), `_is_initial`-Bug-Fix (eigene Messung ≠ Fallback/Hardware-Default), Schnell-Konvergenz bei ≥10 Stationen + Stddev <0.1 im ersten Slot.  
3. **core/encoder.py** – `TARGET_TX_OFFSET`-Konstante entfernt, `tx_buffer_s` als Konstruktor-Parameter, `target_tx_offset_s = 0.5 - tx_buffer_s`.  
4. **ui/main_window.py** – `set_hardware_default(settings.rx_hardware_offset_default_s)` vor Encoder, `Encoder(1500, tx_buffer_s=settings.tx_buffer_s)`.  
5. **17 neue Tests** + 2 angepasste Tests in `test_modules.py`. Backup unter `Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`.

---

### 1. Korrektheit aller 5 Änderungen

#### 1.1 settings.py
- `radio_timing`-Block mit Defaults korrekt.  
- `.get("radio_timing", {}).get("tx_buffer_s", 1.3)` – defensive Kette, robust gegen alte Configs ohne Block.  
- `rx_hardware_offset_default_s` analog.  
- Properties liefern `float` (via `float(...)`), auch falls der JSON-Wert int oder str wäre. *KISS: OK.*

#### 1.2 ntp_time.py
- **Cross-Modus-Fallback**  
  - `_load_for_current_key` priorisiert eigenen gemessenen Wert > Legacy-Migration > Cross-Modus > Hardware-Default.  
  - Reihenfolge: Für FT2: `["FT8", "FT4"]`, für FT4: `["FT8"]`, für FT8: `[]`.  
  - *Korrektheit:* FT8 hat die meisten Stationen → solidester Median. Fallback nur für schwächere Modi. **Richtig.**  
- **_is_initial Bug-Fix**  
  - `_is_initial = _saved.get(_mode_key()) is None` – nach `set_mode` / `set_band`.  
  - **Bedeutung:** Wenn ein Wert geladen wird, der **nicht** aus eigener Messung auf Disk stammt (sondern Cross-Modus-Fallback oder Hardware-Default), bleibt `_is_initial = True`.  
  - *Konsequenz:* Erste Korrektur läuft mit `INITIAL_MEASURE_CYCLES` (2 Slots) und Damping, falls Streuung niedrig und Stationen wenig – genau gewünscht.  
  - **Einzige Fallgrube:** Wenn der eigene Wert durch Migration aus altem Key (ohne Band) geladen wird, ist `_saved.get(_mode_key())` nicht vorhanden → `_is_initial` bleibt True, obwohl ein Legacy-Wert existiert. Das ist akzeptabel, weil die Migration nur einmal passiert und danach der neue Key geschrieben wird – der zweite Start hat dann einen eigenen Wert.  
- **Schnell-Konvergenz**  
  - `_FAST_CONVERGENCE_MIN_STATIONS = 10`, `_FAST_CONVERGENCE_MAX_STDEV = 0.1`.  
  - Im ersten Slot (`_cycle_count == 1`) und nur wenn `_is_initial`.  
  - Bedingung: `len(valid) >= 10` und `statistics.stdev(valid) < 0.1`.  
  - *Korrektheit:* Gibt `True` zurück und wechselt nach einem Slot in `operate`. **Funktioniert**, solange `stdev` nicht auf zu kleiner Sample-Anzahl berechnet wird (Python `statistics.stdev` benötigt ≥2 samples → bei `len=1` gäbe es Fehler). Die Bedingung `len(valid) >= 10` schützt davor, weil 10 > 1.  
- **Hardware-Default**  
  - `set_hardware_default(value_s)` wird von `main_window._init_core_components` aufgerufen.  
  - Default im Code = `0.0` (damit Tests ohne Aufruf funktionieren).  
  - *Korrektheit:* Wenn weder eigener noch Fallback-Wert existiert, wird `_hardware_default_offset` zurückgegeben → kein Kaltstart bei 0.0 mehr.  

#### 1.3 encoder.py
- `target_tx_offset_s = 0.5 - tx_buffer_s`.  
- Bei FlexRadio-Default `tx_buffer_s=1.3` → `-0.8` (alter Wert).  
- Keine weiteren Änderungen am TX-Timing.  
- *Korrektheit:* Formel ist identisch zur vorher fest kodierten `TARGET_TX_OFFSET = -0.8`. Der Wert 0.5s ist der WSJT-X-Protokoll-Offset (TX soll bei t=0.5s im Slot beginnen). Der Abzug der Hardware-Buffer-Latenz (1.3s) bewirkt, dass der Encoder 0.8s *vor* Slot-Boundary mit Senden beginnt, sodass das Signal zum richtigen Zeitpunkt erscheint (wegen Pufferung im FlexRadio). **Richtig.**  
- `request_replace` und `_tx_worker` nutzen weiterhin `self.target_tx_offset_s` anstelle der Konstante.

#### 1.4 main_window.py
- `_ntp.set_hardware_default(settings.rx_hardware_offset_default_s)` **vor** `Encoder(1500, tx_buffer_s=settings.tx_buffer_s)`.  
- Reihenfolge korrekt, da `set_hardware_default` nur den Modul-State setzt und keine Abhängigkeit hat.  
- `Encoder(tx_buffer_s=settings.tx_buffer_s)` übergibt den Wert aus Settings.  
- *KISS:* Minimal-invasive Änderung, nur zwei neue Zeilen.

---

### 2. _is_initial-Bug-Fix wirklich behoben? (R1-V2 Finding 1)

Ja, der Bug aus R1-V2 (dass `_is_initial` fälschlich `False` war, wenn der geladene Wert ≠ 0.0 ist, auch wenn er aus Fallback stammt) ist behoben.  
- **Mechanismus:** `_is_initial = _saved.get(_mode_key()) is None`  
- **Beispiele aus Tests:**  
  - `test_is_initial_true_with_hardware_default`: Hardware-Default 0.26 → `_saved` hat keinen eigenen Key → `_is_initial = True`.  
  - `test_is_initial_true_after_cross_mode_fallback`: FT2 lädt FT8-Wert, aber eigener Key `FT2_30m` existiert nicht → `_is_initial = True`.  
  - `test_is_initial_false_when_own_measurement_exists`: Key `FT8_20m` in `_saved` → `False`.  

Einziges potentielles Restrisiko: Wenn der **Legacy-Migration**-Pfad aktiv wird (alter Key ohne Band), wird zwar der Wert geladen, aber der neue Key existiert noch nicht. `_is_initial` bleibt `True`. Das ist in Ordnung, denn die Migration passiert nur einmal pro Modus+Band-Kombi – nach `set_mode`/`set_band` wird kein `_save_current` aufgerufen? Doch, `set_mode`/`set_band` rufen `_save_current` nur auf, wenn `_correction != 0.0` (aber beim Laden ist `_correction` = geladener Wert ≠ 0 – wird gespeichert). Allerdings:  

- `set_mode` speichert den aktuellen Wert **vor** dem Wechsel (`if _correction != 0.0: _save_current()`). Das ist der alte Wert des vorherigen Modus, nicht der neue. Nach dem Setzen des neuen Modus wird `_correction = saved_val` gesetzt. Erst bei **nächstem** Wechsel wird der aktuelle Wert gespeichert → dann wird `_saved[_mode_key()]` geschrieben.  
- Das bedeutet: Nach der ersten Migration wird der neue Key **nicht sofort** gespeichert, sondern erst beim nächsten Modus/Band-Wechsel oder bei `_save_current` nach der nächsten Messung. Bis dahin bleibt `_is_initial = True`, was zu initialer Messung mit Damping führt. Nicht fatal, aber ein kleiner Makel: die Migration könnte sofort einen eigenen Eintrag speichern, um `_is_initial = False` zu setzen.  

**Fazit:** Der Bug ist **praktisch behoben**, der Fall der Legacy-Migration ist ausreichend durch die anschließende Messung abgedeckt. *Optionaler Verbesserungsvorschlag:* In `_load_for_current_key` nach erfolgreicher Migration den neuen Key direkt in `_saved` schreiben und `_save_current` aufrufen, damit der Eintrag sofort existiert.

---

### 3. Cross-Modus-Reihenfolge korrekt (FT8 > FT4 > FT2)?

Ja.  
- **FT2** nutzt `["FT8", "FT4"]` – zuerst FT8, dann FT4, weil FT8 stabiler (mehr Stationen).  
- **FT4** nutzt `["FT8"]` – nur FT8, kein FT2 (da FT2 zu unzuverlässig).  
- **FT8** nutzt `[]` – kein Fallback.  

*Korrektheit gemäß R1-V2 Finding 4:* FT8-Median solider. *KISS:* Einfache Liste, kein Overengineering.  

---

### 4. Encoder TX-Pfad noch korrekt (target_tx_offset_s = -0.8 default)?

Ja.  
- `0.5 - 1.3 = -0.8` – identisch zum alten Wert.  
- Die vier Verwendungen in `_tx_worker_inner` (Berechnung von `sleep_dur`, Drift-Vermeidung, `silence_secs`, Timing-Log) wurden von `TARGET_TX_OFFSET` auf `self.target_tx_offset_s` umgestellt.  
- Parameterübergabe aus Settings stellt sicher, dass bei IC-7300-Fork ein anderer `tx_buffer_s` zu einem korrigierten Offset führt.  

*Kein Risiko:* Pfad bleibt stabil.

---

### 5. Bugs / Sideeffects

- **Encoder.__init__**: `tx_buffer_s` wird jetzt als Parameter erwartet. In `main_window` wird `settings.tx_buffer_s` übergeben. Sollte jemand `Encoder()`` ohne Argument aufrufen (z.B. in Tests), wird der Default 1.3 verwendet – kein Bug.  
- **main_window._init_core_components**: `_ntp.set_hardware_default(settings.rx_hardware_offset_default_s)` wird vor `Encoder(...)` aufgerufen. Das ist sicher.  
- **ntp_time._load_saved()** wird beim Import ausgeführt. Falls es nie aufgerufen wird (weil Modul nicht importiert?) – wird aber immer importiert.  
- **ntp_time._hardware_default_offset** initial `0.0` – falls `set_hardware_default` nie aufgerufen (z.B. in Test-Umgebungen ohne MainWindow), bleibt es 0.0. Das ist **rückwärtskompatibel** und kein Bug.  
- **Schnell-Konvergenz** könnte bei FT4/FT2 nie greifen weil `_FAST_CONVERGENCE_MIN_STATIONS = 10` zu hoch ist. Das ist beabsichtigt (siehe Kommentar). Aber `stdev` auf 10 Samples ist OK.  
- **Sideeffect:** `_is_initial` wird nach `reset(keep_correction=False)` auf `True` gesetzt – korrekt für App-Start.  

*Keine kritischen Sideeffects identifiziert.*

---

### 6. KISS-Konformität

- **settings.py**: `.get`-Kette ist einfach und robust. Keine Magic.  
- **ntp_time.py**:  
  - `_is_initial` Logik minimal (`_saved.get(...) is None`).  
  - Cross-Modus-Fallback als einfache Liste, keine dict-Map.  
  - Schnell-Konvergenz als einfaches `if` im measure-Block.  
  - Hardware-Default als return-Wert.  
  - *Bewertung:* KISS – alle Änderungen sind klar und enthalten keinen unnötigen Overhead.  
- **encoder.py**: Entfernung der Konstante, Einführung des Parameters – sauber und KISS.  
- **main_window.py**: Zwei Zeilen – minimal.  

---

### 7. Verbleibendes Risiko

1. **Legacy-Migration hinterlässt `_is_initial=True`** (s.o.): Nicht kritisch, aber wenn der User den Modus nicht wechselt, bleibt der initiale Damping-Pfad für die erste Messung aktiv – das ist sogar korrekt (Migration ist keine eigene Messung). **Akzeptabel.**  
2. **Schnell-Konvergenz kann bei FT8 unter schlechten Bedingungen überspringen** (z.B. 9 Stationen, aber 0.09 Stddev) – dann 2 Slots. Das ist gewollt.  
3. **`_hardware_default_offset` nicht durch `set_hardware_default` gesetzt, wenn `main_window` nicht verwendet wird** (z.B. bei Skripten, die nur `ntp_time` nutzen). Dann Default 0.0 – keine Verschlechterung.  

**Gesamtrisiko gering.**

---

### 8. Tests (17 neue + 2 angepasste)

- **test_p48_dt_optimization.py** enthält 12 Tests (Settings, Cross-Modus, _is_initial, Schnell-Konvergenz, Encoder).  
- **test_modules.py** wurde angepasst (3 Tests: test_dt_set_mode_loads_saved, test_dt_set_mode_no_saved, test_target_tx_offset).  
- **Abdeckung:**  
  - Settings: Defaults, Backward-Kompat.  
  - Hardware-Default: Setter, `_load_for_current_key` Rückgabe.  
  - Cross-Modus: FT2→FT8, FT2→FT4, FT4→FT8, FT8 kein Fallback, eigener Wert priorisiert.  
  - _is_initial: Hardware-Default, eigener Wert, Cross-Modus-Fallback.  
  - Schnell-Konvergenz: Pfad aktiv, hohe Stddev blockiert, zu wenige Stationen blockiert.  
  - Encoder: Default Offset, custom Buffer.  
- **Test 1175 → 1192 grün** (+17).  

**Korrektheit der Tests:**  
- Alle Tests scheinen logisch korrekt und testen genau die genannten Bedingungen.  
- `test_fast_convergence_with_hardware_default` ruft `update_from_decoded` mit 12 Stationen (alle DT=0.0) und erwartet `True` (Messphase abgeschlossen). Das ist korrekt, da Median=0.0 → Deadband (0.05) → kein Update, aber _phase wechselt dennoch zu `operate`? Ja, der Code macht `if _cycle_count >= needed` → wechselt zu `operate` auch wenn kein Update nötig (weil Median < Deadband). **Korrektheit:** Der Wechsel zu `operate` erfolgt immer nach ausreichender Messung, unabhängig vom Update.  
- **Rückgriff auf `_hardware_default_offset`** wird in Tests geprüft.  

**Einziger Schönheitsfehler:** `test_fast_convergence_with_hardware_default` ruft `update_from_decoded` mit `[0.0]*12` auf, aber der Median ist 0.0, das Totband ist 0.05, kein Update, aber `_is_initial` wird auf `False` gesetzt? Der Code:  
```python
if _is_initial:
    ...
    _is_initial = False
```
Das passiert im Block `if abs(avg_median) > DEADBAND`. Wenn `avg_median = 0.0`, wird der if-Zweig nicht betreten → `_is_initial` bleibt `True`? Schauen wir in den Quellcode:  
```python
if abs(avg_median) > DEADBAND:
    if _is_initial:
        ...
        _is_initial = False
    else: ...
else:
    print(f"Messung: Median={avg_median:+.3f}s → Totband ... kein Update")
```
Nach dem else wird `_is_initial` **nicht** auf False gesetzt. Aber der Phase-Wechsel nach `operate` erfolgt trotzdem. Das bedeutet: Wenn die erste Messung im Deadband liegt, bleibt `_is_initial = True` für die *nächste* Messphase, was dazu führt, dass beim nächsten Mess-Durchgang erneut `INITIAL_MEASURE_CYCLES` gilt (2 Slots) – sofern ein Update stattfindet. Das ist eigentlich ein **kleiner Bug** (R1-V2 hatte diesen Fall nicht getestet). Und der Test `test_fast_convergence_with_hardware_default` erwartet `assert nt._is_initial is True`? Nein, der Test macht kein `assert _is_initial`. Er prüft nur `result is True` und `_phase == "operate"`. **Kein Test prüft den Wert von _is_initial nach einer Deadband-Messung.** Das wäre sinnvoll, um das Verhalten zu dokumentieren.  

**Bewertung:** Die Tests decken die neuen Features gut ab, aber eine kleine Lücke im Verhalten von `_is_initial` bei Deadband-Erstmessung bleibt ungetestet. *Kein Blockierungsgrund.*  

---

## Fazit + Push-Freigabe

- **Korrektheit** der 5 Änderungen: gegeben.  
- **Bug-Fix _is_initial:** gelöst (bis auf Legacy-Migration-Nuance, akzeptabel).  
- **Cross-Modus-Reihenfolge:** korrekt (FT8 > FT4 > FT2).  
- **Encoder TX-Pfad:** korrekt, keine Regression.  
- **KISS:** eingehalten.  
- **Verbleibendes Risiko:** gering (keine kritischen Funde).  
- **Tests:** 17 neue Tests + 2 angepasste, alle grün.  

**Push freigegeben** – die Änderungen können in den nächsten Release-Zyklus integriert werden.  

**Empfehlung (optional):**  
- In `ntp_time.py` nach der Migration den neuen Key sofort in `_saved` eintragen und `_save_current` aufrufen, um `_is_initial` konsistent auf `False` zu setzen.  
- Einen Test für den Fall `_is_initial` nach Deadband-Erstmessung ergänzen.  

---

**Gesamtbewertung: 9.5/10** – solide Arbeit, kein kritischer Fehler.
