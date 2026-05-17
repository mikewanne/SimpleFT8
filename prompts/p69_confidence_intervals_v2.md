# P69 — V2 Self-Review (kritische Überprüfung der V1)

## V2-Findings

### F1 (KRITISCH) — Bootstrap-Aggregation muss zur _combo_summary_fair-Logik passen

**V1-Aussage:** „Block-Bootstrap nach (Datum, Stunde)". V1 hat aber NICHT
geklärt **was genau bootstrappt** wird. Die README-Headline-Werte kommen
aus `_combo_summary_fair` (Z. 1232), das ist **kein Stunden-Schnitt**
sondern ein simpler Pooled Mean über ALLE Zyklen jedes Modus, mit
Normal-Pooled-Mean als gemeinsame Referenz. Stunden-Filter gibt es
NICHT in dieser Berechnung.

**Wenn der Bootstrap auf (date, hour)-Blöcke bootstrappt, ABER der
Punktschätzer aus `_combo_summary_fair` kommt, sind beide rechnerisch
konsistent — solange wir den Pooled Mean innerhalb des Bootstraps auch
über ALLE gezogenen Cycles berechnen (nicht stundenweise gewichten).**

→ V3-Fix: Bootstrap-Funktion macht Pooled Mean = `sum(all_cycles) /
len(all_cycles)` über alle Cycles aller gezogenen Blöcke. Keine Stunden-
Mittelung dazwischen. Das matcht `_combo_summary_fair` exakt.

### F2 (KRITISCH) — Hierarchische Autokorrelation: Tag-Ebene bleibt unbehandelt

**V1-Aussage:** „Über-Tag-Drift bleibt unkorrigiert". Das stimmt, aber
ich habe nicht klar gemacht **warum** unser Block-Design das nicht
abdeckt. (date, hour)-Blöcke behandeln INNERHOUR-Korrelation gut, aber
Stunden DESSELBEN TAGES bleiben im Resample unabhängig — was sie nicht
sind (gleicher SFI, gleiches Wetter, ggf. gleiche Antennen-Bedingung).

**Sauberer wäre Hierarchischer Bootstrap (erst Tag-Block ziehen, dann
darin Stunden-Block). Das ist deutlich komplexer und macht aus 12 Tagen
× 20 Stunden = 240 Blöcken effektiv nur 12 Top-Level-Blöcke → CIs werden
wesentlich breiter.**

→ V3-Entscheidung: KISS bleibt bei (date, hour)-Block-Bootstrap. Aber
README-Caveat muss explizit sagen: „Innerhour kontrolliert; Tag-zu-Tag-
Drift NICHT vollständig modelliert — Confidence-Intervalle eher
optimistisch als zu konservativ."

Das ist ehrliche Wissenschaftskommunikation. Wenn jemand die Methodik
hart attackieren will, kann er hierarchischen Bootstrap als Verbesserung
einfordern — das ist dann ein V4-Thema.

### F3 — Daten-Threshold für „CI sinnvoll" konkretisieren

**V1-Aussage:** „mindestens 5 Blöcke pro Modus, sonst n/a". Das ist OK
als Heuristik, aber 5 ist willkürlich. Statistik-Faustregel: Bootstrap-
CI wird stabil bei n ≥ 20-30 Original-Beobachtungen. Bei n < 10 sind die
CIs unzuverlässig (zu eng, weil zu wenige unterschiedliche Resamples
möglich).

→ V3-Entscheidung: Threshold n ≥ 10 (date, hour)-Blöcke. Bei 5 ≤ n <
10: CI ausgeben mit Warnhinweis „limited data". Bei n < 5: „n/a".
Das ist transparenter.

### F4 — Test T2 ist okay aber missverständlich beschrieben

**V1-Test T2:** „normal=[10], compare=[20] → CI=[+100, +100]". Stimmt
nur wenn jeweils 1 Block mit 1 Cycle vorliegt. Beim Resampling mit
Zurücklegen wird immer derselbe Block gezogen — Mean ist deterministisch.

→ V3-Klärung: T2-Beschreibung präziser machen, plus T2b mit echter
Bandbreite (10 Blöcke à 1 Cycle alle = 10, 10 Blöcke à 1 Cycle alle =
20) → auch hier CI=[+100, +100] weil jeder Resample gibt 10 / 20 als
Mean. ✓ Verifiziert mein Verständnis.

### F5 — Performance-Schätzung in V1 zu optimistisch

**V1-Aussage:** „1000 iter × 12k Cycles → 12 M Operationen pro CI". Habe
unterschlagen dass pro Iteration der Pooled Mean berechnet werden muss
(eine Summe + eine Division). Bei 1000 iter × ~2× 50 Blöcke Zugriff +
2× Pooled-Mean-Berechnung ≈ 100k Operations pro CI, × 9 CIs (drei
Bänder × drei Modi) ≈ 1M Operations. Sehr schnell, <2s in plain Python.

Praktischer Test: zeit die Funktion in T8 mit `assert duration < 2.0`.

### F6 — _combo_summary_fair n_avg_common-Logik

`_combo_summary_fair` setzt `n_avg_common = Normal_pooled_mean` als
gemeinsame Baseline. In der PDF-Tabelle (Z. 1480) wird `+X% =
(avg/n_ref - 1) * 100` berechnet. Mein Bootstrap muss dasselbe machen:
für jeden Resample compute `avg_compare_pooled - avg_normal_pooled`,
dann durch `avg_normal_pooled` teilen.

Wichtig: pro Iteration brauche ich BEIDE Pooled Means — die werden aus
zwei separaten Resamples (compare und normal) berechnet. Sie sind also
unabhängig zufällig. Das passt zur Methodik.

→ V3-Klärung: explizit dokumentieren dass es kein paired-bootstrap ist.
Beide Modi werden unabhängig resampelt.

### F7 — README-Tabellen-Update-Helper

V1 sagt „Helper-Skript das Markdown ausgibt". Konkretisieren:
`scripts/print_ci_for_readme.py` — liest statistics/, ruft den neuen
Helper auf, druckt für jede Band-Mode-Kombo eine fertige Markdown-Zeile.
Mike kann das manuell in den README übernehmen. Kein Auto-Update des
README — der wird zu viel angefasst, manuell sicherer.

### F8 — APP_VERSION-Bump-Wert

V1 sagt 0.97.45 → 0.97.46. Patch-Bump ist falsch — neue Funktion = Minor-
Bump auf 0.98.0? Oder bleibt es Patch weil keine User-Visible-Code-
Änderung am App-Verhalten?

→ V3-Entscheidung: bleibt Patch 0.97.46. P69 ist eine Auswertungs-
Erweiterung im Skript, nicht in der App. Mike's Konvention im CLAUDE.md
sagt „Patch +0.01 bei Features, unchanged bei Bugfix-only" — diese
Stats-Erweiterung qualifiziert als Feature → 0.97.46 ist konsistent.

### F9 — Frequenz-Test mit echten Daten muss Reproduzierbarkeit haben

Test T9 sagt „mit echter statistics/40m-Daten → CI enthält Punkt
schätzer 126%". Das ist aber datenabhängig — wenn jemand die Tests
laufen lässt und neue Daten dazugekommen sind, könnte der Punktschätzer
sich verschieben.

→ V3-Fix: T9 fixiert Test-Daten in `tests/data/p69_fixture/` mit einem
Mini-statistics-Tree, OR T9 prüft nur dass CI **existiert und Punkt
schätzer einschließt** (nicht den absoluten Wert). KISS: zweite Variante.

### F10 — V1-Aus-Scope-Liste vergessen: paired-test alternative

Wenn jemand sagt „wieso kein paired t-test pro Stunde": das wäre ein
ganz anderer Test (gleiche Stunden vergleichen, Innerhour-Differenz
testen). Wir machen das nicht weil:
- Modi werden in unterschiedlichen Stunden gemessen (Mike wechselt durch)
- Paired setzt voraus dass beide Modi gleichzeitig laufen — geht nicht

→ V3-Caveat-Update: „Paired tests nicht anwendbar, weil Modi sequenziell
gemessen werden, nicht parallel. Block-Bootstrap auf Pooled Mean ist die
sauberste Lösung für diese Datenstruktur."

## Halluzinations-Check (V2-Pflicht)

V1 erwähnt diese konkreten Code-Stellen — alle verifiziert gegen Code:

- ✅ `load_hourly_stats` returnt `dict[hour → {"cycles": [], "daily": {}, "minutes": set}]` (Z. 787-821)
- ✅ `_combo_summary_fair` (Z. 1232) ist die Baseline-Berechnung
- ✅ PDF-Tabelle Z. 1500 hat 7 Spalten (`p3_col_labels`)
- ✅ README hat 3 Tabellen (Z. 191/254/301 EN + Z. 618/682/730 DE) mit
  Pooled-Mean-Werten

Keine Halluzinationen entdeckt.

## Was V3 ändern muss

1. **F1**: Bootstrap rechnet Pooled Mean = `sum(all_cycles)/len(all_cycles)`
   über alle gezogenen Cycles — kein Stunden-Mittel zwischendrin.
2. **F2**: README-Caveat klar formulieren: Tag-zu-Tag-Drift NICHT
   modelliert, CIs eher optimistisch.
3. **F3**: Threshold n ≥ 10 für CI, 5 ≤ n < 10 mit Warning, n < 5 „n/a".
4. **F4**: T2-Beschreibung präzisieren, T2b ergänzen.
5. **F6**: explizit dokumentieren: kein paired-bootstrap, beide Modi
   unabhängig resampelt.
6. **F7**: Helper-Skript `scripts/print_ci_for_readme.py` als separates
   Tool-File, nicht in `generate_plots.py`.
7. **F9**: T9 prüft nur CI-Enthält-Punktschätzer, nicht absolute Werte.
8. **F10**: Caveat ergänzt um „paired tests nicht anwendbar".

Aus Scope bleibt: Hierarchischer Bootstrap, p-Werte, Solar-Stratifikation.

Bereit für R1 mit DeepSeek-V4-pro.
