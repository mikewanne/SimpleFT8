# P14 — DT-Werte-Asymmetrie (V2 Self-Review, 13.05.2026)

**V2-Auftrag (Self-Review von V1):** Welche Lücken/Ambiguitäten/Annahmen hat V1? Was übersieht V1? Wo halluziniert V1 Code? Was würde eine frische KI als erstes bemängeln?

---

## V2-Findings (kritische Selbst-Prüfung)

### L1 — V1 verifiziert die Trim-Mathematik falsch in T2

**V1-Tabelle T2:** `[-1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]` n=10, trim=1.

Bei `floor(10 × 0.1) = 1` → entferne 1 oben + 1 unten → n=8.
Sortiert: `[-1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]`.
Trim 1+1: entferne `-1.0` und das letzte `0` → `[0, 0, 0, 0, 0, 0, 0, 0]` → Median 0. **OK.**

**V1-Tabelle T1 (Mike's 20 Werte):** sortiert
```
-1.2, -0.7, -0.7, -0.4, -0.3, -0.2, -0.1, -0.1, -0.1, -0.1,
-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, +0.3
```
`floor(20 × 0.1) = 2` → entferne 2 oben + 2 unten = 4 Werte weg.
Untere 2: `-1.2, -0.7`. Obere 2: `+0.3, 0.0`. Übrig: 16 Werte.
Mitte der 16: Position 8/9 (0-indexed 7/8). Diese sind: `-0.1, 0.0`.
**Median = (-0.1 + 0.0) / 2 = -0.05.**

V1 behauptet **„0.0"** — das ist **falsch**. Korrektur: erwartet ist **-0.05** (immer noch im Totband 0.05, kein Update, AK2 hält trotzdem).

→ V3: AK2 → Erwartung **-0.05 (im Totband, kein Update)**.

### L2 — DEADBAND 0.05 — Floating-Point-Vergleich

V1: `if abs(avg_median) > DEADBAND` — bei `avg_median = -0.05` ist `abs(-0.05) > 0.05` → **False** → kein Update.

**Aber:** Float-Precision-Trap. `-0.05 - 0.0` ergibt evtl. `0.04999999...` oder `0.05000000001`. Tests müssen `pytest.approx` nutzen.

→ V3: T6 mit `pytest.approx(0.27, abs=1e-9)` für `_correction`.

### L3 — V1 vergisst statistics.median bei gerader Anzahl

`statistics.median` bei n gerade: Durchschnitt der mittleren 2. Bei n ungerade: mittleres Element.

V1's Beispiele waren n=20 (gerade) und n=10 (gerade). T3 (n=5 ungerade): `[-0.5, -0.1, 0, 0.1, 0.5]` → Median 0 (mittleres Element). **OK**.

**Aber:** Trimmed-Median bei n=11 (ungerade)? `floor(11 × 0.1) = 1` → trim 1+1 = n=9 (ungerade) → Median = 5. Element. Kein Problem — `statistics.median(sorted[1:-1])` arbeitet auf beliebigen Längen.

→ Neuer Test T9: `_trimmed_median(11 Werte)` korrekt.

### L4 — V1 lässt `_FAST_CONVERGENCE_MIN_STATIONS = 10` unberührt — Wechselwirkung mit Trim-Schwelle?

P48-D: `_FAST_CONVERGENCE_MIN_STATIONS = 10` → Schnell-Konvergenz im 1. Slot wenn ≥10 Stationen mit Stddev<0.1.

**Wechselwirkung:** Bei genau n=10 → Fast-Path *könnte* feuern wenn alle Werte eng. Aber `_trimmed_median` arbeitet vor dem Fast-Path-Check (Median wird oben in der Funktion berechnet, bevor Fast-Path geprüft wird).

V1's Code-Reihenfolge:
1. `valid = [...]` Filter ±2.0
2. `median_dt = _trimmed_median(valid)` (NEU)
3. `_last_median_dt = median_dt` (für Status-Anzeige)
4. Fast-Path-Check `_FAST_CONVERGENCE_MIN_STATIONS` arbeitet mit `valid` (Anzahl)
5. `statistics.stdev(valid)` — KEIN Trim

**L4-Problem:** `statistics.stdev` über ALLE valid-Werte inkl. Outliers. Wenn 12 Werte, 2 davon `-1.2/+0.3`, stdev > 0.1 → Fast-Path blockiert.

Aber: Fast-Path ist eh nur 1×-Use-Case (App-Start). Damit Mike's Beobachtung nicht erklärt (Korrektur 0.27 ist schon dauerhaft gespeichert, App lange am Laufen → wir sind im Folge-Pfad nicht Fast-Path).

→ V3: keine Änderung am Fast-Path, aber **Begründung dokumentieren**.

### L5 — V1 vergisst Backward-Kompat-Test `_trimmed_median` muss exakt `statistics.median` ergeben bei n<10

V1 T3 testet n=5 → ok. Aber explizit: `_trimmed_median([1,2,3,4,5,6,7,8,9]) == statistics.median([1,2,3,4,5,6,7,8,9])` bei n=9 (gerade unter Schwelle).

→ V3: T10 `test_trimmed_median_below_threshold_matches_median` für n=9, 7, 5, 3.

### L6 — `_trimmed_median` Helper — wo platzieren?

V1 sagt „Modul-Funktion" aber nicht private vs. public. Vorschlag: **private** (`_trimmed_median`) am Anfang des Moduls vor `set_mode`. Tests importieren via `from core.ntp_time import _trimmed_median` — Python erlaubt das.

→ V3: explizit `_trimmed_median` (mit Unterstrich).

### L7 — DAMPING-Test in T7

V1 T7: `from core.ntp_time import DAMPING; assert DAMPING == 0.5` — **OK** aber fragil (Konstanten-Test ist Anti-Pattern).

Besser: **Verhaltens-Test** T8 (Damping-Effekt auf `_correction`) — das ist robuster.

→ V3: T7 streichen, T8 reicht.

### L8 — V1's Field-Test-Plan ist nicht zeitgebunden

„30 Min", „1 Std" — aber wenn Mike um 07:30 anfängt und um 12:00 Mittagessen hat → keine 1h Test. Soll Field-Test asynchron sein? **Ja** — Mike schickt Screenshots ab und zu, wir hacken erst ab nach mehreren Bestätigungen (Mike's explizite Anweisung).

→ V3: Field-Test asynchron, Mike schickt Screenshots, KEIN Push bis grünes Licht.

### L9 — V1 vergisst Mike's „Korrektur 0.27 nicht runter" Diagnose

Wenn die App stundenlang lief mit Korrektur 0.27 und Median konsistent -0.1 zeigt: warum hat das System nicht von alleine korrigiert?

**Möglich:**
- Median oszilliert um Totband (`abs(median) ≤ 0.05` mal True, mal False)
- Oder Median ist konsistent außerhalb → `_correction` sollte langsam wandern

V1 hat das nicht untersucht. **Annahme V2:** Mike's Screenshot ist eine Momentaufnahme. Wir können nicht sicher sagen ob System einfriert oder langsam wandert.

→ V3: **Diagnostik-Eintrag in HANDOFF** — Mike soll vor Field-Test einmal die `[DT-Korr] ...`-Print-Zeile im Log mitgeben (zeigt avg_median + Delta).

### L10 — V1's „dt_corrections.json bleibt unverändert beim ersten Start" (AK5) ist riskant formuliert

Beim App-Start triggert P48-Fast-Path im 1. Slot wenn Stationen ≥10 + stddev<0.1. Mit getrimmtem Median verschiebt sich avg_median potenziell → Korrektur kann sich ÄNDERN.

V1 AK5 sagt „0.2705 bleibt 0.2705 bis MEASURE-Phase neue Daten liefert" — **falsch**. Die MEASURE-Phase läuft sofort nach Start, 1. Slot kann Korrektur ändern.

→ V3: AK5 entfernen oder umformulieren: „Korrektur darf sich nur ändern wenn `|avg_trimmed_median| > DEADBAND`."

### L11 — V1 hat keine Tests für RACE/THREADING

`update_from_decoded` läuft im GUI-Thread (mw_cycle), `_correction` wird mit `_lock` geschützt. `_trimmed_median` ist pure function (kein Lock nötig). 

→ V3: dokumentieren, kein Test nötig.

### L12 — Backup-Pfad-Konvention

V1: `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/`. Aber heute ist 13.05. und wir hatten schon mehrere v0.97.X-Sprünge. Es gibt evtl. schon einen Ordner-Konflikt.

→ V3: prüfen ob schon vorhanden, ggf. `_2` Suffix.

### L13 — APP_VERSION 0.97.15 → 0.97.16 oder 0.98.0?

V1 sagt 0.97.16. Aber: Wir ändern Algorithmus-Verhalten (Damping + Trim) — das ist eine Verhaltens-Änderung. Bei der projekt-internen Konvention „Patch +0.01 für Features, unverändert für reine Bugfixes" wäre das hier... Bugfix (Wurzel-Fix) oder Feature (neuer Algorithmus)?

→ V3: 0.97.16 reicht, ist Wurzel-Fix mit neuem Helper.

---

## V2 → V3 Änderungen (Zusammenfassung)

1. **T1 Erwartung korrigieren:** Mike's 20 Werte → `_trimmed_median` = **-0.05** (nicht 0.0). Test-Assertion `pytest.approx(-0.05, abs=1e-9)`.
2. **AK2 anpassen:** „Trimmed Median liegt zwischen -0.06 und +0.06" (Totband-Range).
3. **T9 ergänzen:** `_trimmed_median` bei n=11 (ungerade).
4. **T10 ergänzen:** Backward-Kompat bei n<10 = `statistics.median`.
5. **T7 streichen:** Konstanten-Test redundant zu T8.
6. **AK5 umformulieren:** Korrektur ändert sich nur wenn Trimmed-Median außerhalb Totband.
7. **Helper-Name:** `_trimmed_median` (private).
8. **Fast-Path-stdev:** bewusst über alle valid-Werte (nicht getrimmt) — Begründung dokumentieren.
9. **Field-Test:** asynchron, mehrere Mike-Screenshots, kein Push bis grünes Licht.
10. **Backup-Pfad:** ggf. mit `_2`-Suffix bei Konflikt.

---

## Was DeepSeek vermutlich finden wird

- Trim-Anteil 10% bei n=10 = 1 Wert pro Seite → minimal effektiv. Wert bei n=10 ist sehr nahe an dem was einfacher Median bei n=8 wäre.
- Damping 0.5 vs 0.7 → DeepSeek wird vermutlich konservativ raten (0.7 lassen, nur Trim).
- KISS-Kritik: 2 Knöpfe drehen statt 1 ist Overengineering.
- Eventuell findet DeepSeek einen Edge-Case bei FT4/FT2 mit 3-5 Stationen.

V3 sollte Trim+Damping-Doppelmaßnahme begründen oder eines davon zurücknehmen.

---

**Nächster Schritt:** Prompt an DeepSeek (deepseek-reasoner) mit V2 + `core/ntp_time.py` als Anhang.
