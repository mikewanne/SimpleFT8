# P14 — DT-Werte-Asymmetrie (V1, 13.05.2026)

**Status:** V1 Entwurf — geht in V2 (Self-Review) → R1 (DeepSeek) → V3 → Mike-Freigabe.
**Trivial-Klausel:** nein — berührt Algorithmus (Median + Damping + Totband), 1 Modul Hauptaufwand, neue Tests.

---

## 1. Symptom (Mike-Screenshot 13.05.2026 ~07:30 UTC)

**Setup:** 20m FT8, Diversity-Mode (eigentlich Normal — der Screenshot zeigt das Empfangs-Panel; egal), 20 dekodierte RX-Stationen.

**Gespeicherte Korrektur:** `~/.simpleft8/dt_corrections.json` → `FT8_20m: 0.2705s`

**RX-DT-Verteilung im Panel (20 Werte, sortiert):**
```
-1.2, -0.7, -0.7, -0.4, -0.3, -0.2, -0.1, -0.1, -0.1, -0.1,
-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, +0.3
```

- **Median:** -0.1s
- **Mean:** -0.20s (Outlier-verzerrt)
- **Symmetrie:** 11 negativ, 1 positiv (≥+0.1), 8 nahe Null
- **Ideal:** symmetrisch verteilt um 0, Median ±0.05

## 2. Wurzel-Hypothesen

| H | These | Plausibel? |
|---|---|---|
| **H1** | Korrektur 0.27 ist tendenziell ~0.07s zu hoch. System sollte über mehrere MEASURE-Phasen auf 0.20 wandern (Damping 0.7 → 3-5 Phasen × ~3 Min = 9-15 Min Konvergenz) | Hoch — passt zu Mathematik |
| **H2** | Median wird von Mobile/QRP/QSB-Ausreißern (-0.7, -1.2) nach unten gezogen. Bei 20 Werten reicht 1-2 Stationen Wegfall um Median 1 Position zu verschieben | Hoch — direkt im Screenshot sichtbar |
| **H3** | Symmetrisches Totband 0.05 friert Korrektur ein wenn Median knapp drunter ist (oszillation -0.04/+0.04 → kein Update) | Mittel — nur wenn Median lange im Totband bleibt |
| **H4** | DAMPING 0.7 + 10-Slot-OPERATE-Pause macht Konvergenz unnötig langsam (1 Korrektur-Schritt pro ~3 Min FT8) | Mittel — kein Bug, aber suboptimal |

**Wahrscheinlichste Wurzel:** H1+H2 kombiniert. Outliers ziehen den Median, Damping bremst die Korrektur, Resultat: stabiler -0.1 Bias.

## 3. Lösungsvariante C (Mike-Vorschlag, gewählt)

### C-Maßnahme 1 (Primär) — Getrimmter Median in `update_from_decoded`

**Statt:** `median_dt = statistics.median(valid)`

**Neu:** Helper `_trimmed_median(values, trim_frac=0.1)`:
- Bei `len(values) >= 10` → sortiere, entferne `floor(n × 0.1)` Werte oben + unten, dann Median
- Bei `len(values) < 10` → einfacher Median (keine Trimmung — sonst zu aggressiv bei FT4/FT2)

**Effekt:** Im Screenshot (n=20, trim=2) fallen `-1.2` und `+0.3` weg → Median berechnet aus 18 Werten = **0.0** (statt -0.1).

### C-Maßnahme 2 (Sekundär) — DAMPING leicht reduzieren

**Statt:** `DAMPING = 0.7`
**Neu:** `DAMPING = 0.5`

**Effekt:** Schnellere Konvergenz. -0.1 × 0.5 = -0.05 statt -0.07 → 1 Schritt mehr nötig, aber Reaktion auf echte Drift schneller weil OPERATE-Pause weiterhin 10 Slots.

**Risiko:** Schwingung bei rauschigen Messungen. Gegenmaßnahme: Totband bleibt 0.05, Sprung-Reset bei |median|>1.0 bleibt.

### C-Maßnahme 3 — NICHT umgesetzt (bewusst weggelassen)

**Asymmetrisches Totband / Ziel-Verschiebung ins Positive** (Mike's „Schwelle ins Positive legen"):
- Verlangt Konvention zu brechen (Median-Ziel = 0 ist Industriestandard)
- Symptomatisch — adressiert nicht die Wurzel (Outliers + Damping)
- Anti-WSJT-X-kompatibel — Audio-Buffer-Mitte ist 0
- **R1 wird das vermutlich auch als Overengineering einstufen.**

→ Falls C-Maßnahme 1+2 nicht reichen: in einem späteren Workflow nachjustieren.

## 4. Akzeptanzkriterien

| AK | Bedingung | Verifikation |
|---|---|---|
| **AK1** | `_trimmed_median([0.0]*8 + [-1.2, -0.7])` = 0.0 (Trimmen entfernt -1.2 und -0.7 erst bei n≥10? Nein bei n=10 → trim=1 entfernt -1.2; -0.7 bleibt) | Unit-Test |
| **AK2** | `_trimmed_median(Mike-Screenshot-20-Werte)` ergibt ein Wert zwischen -0.05 und +0.05 (im Totband, kein Update nötig) | Unit-Test mit Mike's Daten |
| **AK3** | Bei `len(values) < 10` → kein Trim (Verhalten = `statistics.median(values)`) | Unit-Test FT4/FT2-Pfad |
| **AK4** | DAMPING-Konstante 0.5, alte Tests `test_fast_convergence_*` bleiben grün (P48-Tests testen Phasen-Wechsel nicht Damping-Wert) | pytest |
| **AK5** | Korrektur in `dt_corrections.json` darf sich nicht beim ersten App-Start automatisch ändern (0.2705 bleibt 0.2705 bis MEASURE-Phase neue Daten liefert) | Mike-Field-Test |
| **AK6** | Field-Test nach 30 Min: RX-Panel zeigt ~symmetrische Verteilung (Median ±0.05) | Mike-Screenshot |

## 5. Files

| Datei | Was |
|---|---|
| `core/ntp_time.py` | `_trimmed_median()` Helper NEU (Modul-Funktion); `update_from_decoded` Z.244 ersetzt Median-Aufruf; `DAMPING = 0.5` Konstante |
| `tests/test_p14_dt_symmetry.py` NEU | 8 Tests (siehe §6) |

**KEIN Touch:**
- `core/decoder.py` — Roh-DT-Werte bleiben gleich
- `core/encoder.py` — TX-Pfad unberührt
- `ui/mw_cycle.py:218` — Aufrufer-API bleibt `update_from_decoded(dt_values)`
- `dt_corrections.json` — Format unverändert
- `docs/explained/dt-correction*.md` — Doku-Update separat NACH Field-Test-Bestätigung

## 6. Tests (test_p14_dt_symmetry.py)

| T# | Test | Erwartung |
|---|---|---|
| T1 | `test_trimmed_median_n20_with_outliers` (Mike's 20-Werte) | Ergebnis 0.0 (statt -0.1 ohne Trim) |
| T2 | `test_trimmed_median_n10_one_outlier` ([-1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]) | Median 0.0 (trim=1 entfernt -1.0) |
| T3 | `test_trimmed_median_n5_no_trim` ([-0.5, -0.1, 0, 0.1, 0.5]) | Median 0.0 (kein Trim, einfacher Median) |
| T4 | `test_trimmed_median_n1` ([0.3]) | Median 0.3 (Edge-Case n=1) |
| T5 | `test_trimmed_median_empty` ([]) | raises `statistics.StatisticsError` (Verhalten von `statistics.median` durchgereicht) |
| T6 | `test_update_from_decoded_uses_trimmed` (fresh_ntp + Mike's 20 Werte 2× hintereinander) | Nach 2 MEASURE-Slots: `abs(avg_median) ≤ DEADBAND` → `_correction` bleibt unverändert (0.27 → 0.27) |
| T7 | `test_damping_05_constant` | `from core.ntp_time import DAMPING; assert DAMPING == 0.5` |
| T8 | `test_damping_effect_on_correction` (fresh_ntp, _correction=0.27, _is_initial=False, 2 Slots mit Median -0.1) | `_correction == 0.27 + (-0.1 × 0.5) = 0.22` |

## 7. Risiken & Mitigation

| R | Risiko | Mitigation |
|---|---|---|
| R1 | Trimmed-Median bei FT4/FT2 (oft <10 Stationen) ändert Verhalten | Schwelle `n>=10` → unter 10 normaler Median, kein Verhaltens-Change |
| R2 | Damping 0.5 vs 0.7 verändert P48-Tests nicht (P48 testet Phasen-Wechsel), aber alte Doku referenziert 0.7 | docs/explained/dt-correction_de.md+en separat updaten NACH Field-Test |
| R3 | Bei extrem schiefer Verteilung (alle 20 Werte negativ, kein Ausreißer) bleibt das Bias bestehen | OK so — System reagiert auf echte Drift, soll es ja |
| R4 | Hardware-Default 0.26 + 1 Slot Fast-Path könnte bei dem getrimmten Median anders konvergieren | Test mit Mike's Daten zeigt: passt, Median bleibt ~0 |

## 8. Backup & Commits (nach V3-Freigabe)

**Backup:** `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/core/ntp_time.py`

**Atomare Commits:**
- **C1** `core/ntp_time.py` — `_trimmed_median` Helper + `DAMPING = 0.5`
- **C2** `core/ntp_time.py` — `update_from_decoded` nutzt `_trimmed_median(valid)`
- **C3** `tests/test_p14_dt_symmetry.py` — 8 neue Tests
- **C4** `main.py` — `APP_VERSION` 0.97.15 → 0.97.16
- **C5** Doku: `HISTORY.md` + `HANDOFF.md` + `CLAUDE.md` + Memory + `TODO.md` (P14 → ERLEDIGT)
- **C6** (optional, nach Field-Test) `docs/explained/dt-correction_de.md` + `_en` aktualisieren

## 9. Field-Test-Plan

**Mike-Workflow:**
1. App neu starten (alte Korrektur 0.27 bleibt geladen aus json)
2. 5 Min FT8 20m laufen lassen, Screenshot RX-Panel
3. 30 Min weiter laufen lassen, Screenshot
4. 1 Std weiter, Screenshot
5. Erwartung: RX-DT-Verteilung wird über die Zeit symmetrischer um 0

**Push:** erst nach Mike's Bestätigung — Field-Test kann mehrere Stunden dauern.

## 10. Mike-Entscheidungspunkte (V3-Freigabe)

- **Q1:** DAMPING 0.7 → 0.5 OK, oder lieber bei 0.7 lassen und nur Trim einbauen? (Konservativer: nur Trim)
- **Q2:** Trim-Schwelle `n >= 10` OK, oder lieber `n >= 15`? (mehr Stationen = mehr Sicherheitsmarge fürs Trimmen)
- **Q3:** Trim-Anteil 10% (= 1 Wert bei n=10, 2 bei n=20) OK, oder lieber 5% (konservativer)?

→ Default-Vorschlag: DAMPING=0.5, n≥10, trim=10%. Begründung: Mike sieht das Problem JETZT, schnellere Konvergenz hilft, n=10 ist Schwelle wo Trimmen statistisch beginnt zu greifen.

---

**Nächster Schritt:** V2 (Self-Review) — was übersieht V1?
