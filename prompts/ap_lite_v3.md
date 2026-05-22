# V3 — AP-Lite (P2-Lite): Strategie + Umsetzungsplan

**Status: wartet auf Mike-Freigabe. Kein Code vor explizitem OK.**

## Empfehlung: Option B — AP-Lite ehrlich deaktivieren

Einstimmig: meine Diagnose, DeepSeek-Review und die Projekt-Philosophie
(KISS, kein Overengineering) kommen zum selben Ergebnis.

## Worum es geht — in einfachen Worten

AP-Lite soll schwache QSOs retten, indem es zwei misslungene Empfangs-
Versuche zusammenrechnet. Die App hat dieses Feature an, es läuft bei jedem
QSO mit — aber es hat **noch nie ein QSO gerettet**. Zwei Gründe:

1. Die Bauteil-Ebene ist fehlerhaft (die Ausrichtung der zwei Aufnahmen
   funktioniert nicht — schon zwei identische Aufnahmen werden falsch
   zusammengelegt).
2. Schlimmer: die Grundidee selbst trägt nicht. Zwei Funksendungen 15
   Sekunden auseinander „passen" nicht sauber aufeinander — je nach
   zufälliger Phasenlage addieren sie sich mal verstärkend, mal löschen
   sie sich komplett aus. Im Durchschnitt: **0 dB Gewinn**. Die
   versprochenen +4-5 dB gibt es real nicht.

Ein echter Fix wäre ein tiefer Umbau (mehrere Tage), den man ohne Radio
nicht testen kann — und der für ein Hobby-Tool unverhältnismäßig ist.
Darum: das Feature ehrlich abschalten, statt so zu tun als ob es wirkt.

## Verifizierte Diagnose (Code gelesen + gemessen + DeepSeek bestätigt)

| # | Fehler | Ebene | belegt durch |
|---|--------|-------|--------------|
| A1 | `_build_costas_reference` ist Sinus-Stückwerk statt echtes FT8-GFSK → Ausrichtung findet Nebenmaxima | flach | Messung: identische Buffer → `dt=-6, df=-1.5 Hz` |
| A2 | Frequenzkorrektur `real × cos()` erzeugt Spiegelfrequenzen statt sauberer Verschiebung | flach | DeepSeek bestätigt: DSP-Fehler |
| B1 | Kohärente Addition über 15-s-Slots ohne Trägerphasen-Korrektur → Mittel 0 dB | tief | Messung: Mittel über φ = 2.0× = 0 dB netto |
| B2 | E2E-Tests nutzen phasengleiche Buffer → kritischer Pfad nie getestet | tief | Code: `_make_pcm` identisch für beide Slots |

Folge: selbst zwei identische saubere Buffer scoren nur **0.42** (Schwelle
0.75). Das Feature kann strukturell nichts retten.

## Umsetzungsplan (nach Freigabe)

1. **`core/ap_lite.py:35`** → `AP_LITE_ENABLED = False`. Modul-Docstring +
   Inline-Kommentar ehrlich machen: inaktiv wegen ungelöster
   Phasenabhängigkeit der kohärenten Addition, nicht „nur Feldtest fehlt".
2. **`ui/main_window.py:395`** — der Kommentar sagt schon „deaktiviert,
   AP_LITE_ENABLED=False"; durch Schritt 1 wird er **automatisch korrekt**.
   Nur Wortlaut prüfen.
3. **`docs/explained/ap-lite_de.md`** — Status-Abschnitt ehrlich umschreiben:
   „experimentell / inaktiv — kohärente Addition über 15-s-Slots ist ohne
   Trägerphasen-Korrektur wirkungslos (0 dB Mittel). Reaktivierung erst
   nach grundlegender Überarbeitung." Auch die „+4-5 dB"-Aussage entschärfen.
4. **`README.md` + `README_DE.md`** — AP-Lite-Eintrag als
   **(experimentell / inaktiv)** kennzeichnen. *(GitHub-sichtbar → Mike
   entscheidet Wortlaut.)*
5. **`tests/test_ap_lite.py` + `test_ap_lite_e2e.py`** — PFLICHT-Anpassung:
   Der Konstruktor `APLite()` liest `AP_LITE_ENABLED`; mit `False` gibt
   `try_rescue` sofort `None` zurück → die Tests, die das Verhalten prüfen
   (`assert result is not None` etc.), würden brechen. Lösung: in den
   betroffenen Tests `ap.enabled = True` explizit setzen — sie testen den
   **Algorithmus**, nicht das Deployment-Flag. Plus Docstring-Notiz: „deckt
   aktuell inaktiven Code ab; kritischer phasen-inkohärenter Pfad ungetestet."
6. **`TODO.md`** — die veraltete Sektion „AP-Lite v2.2 Test-Pipeline bauen"
   schließen (Pipeline existiert seit v0.95.9) und die offene Zeile
   „AP-Lite Threshold 0.75 kalibrieren → AP_LITE_ENABLED=True" durch die
   B-Entscheidung ersetzen.

**Code bleibt erhalten** (verdrahtet, no-op bei Flag=False) — falls jemand
es später mit korrekter Phasenkorrektur + E2E-Test richtig bauen will.

## Nicht gemacht

- **Option A** (nur Costas-Referenz fixen): macht die Tests grün, das
  Feld-Verhalten bleibt 0 dB → grüner Test, totes Feature. Verworfen.
- **Option C** (LLR-/Soft-Symbol-Mittelung, der korrekte Weg): mehrere
  Tage, tiefer Decoder-Eingriff, ohne Radio nicht kalibrierbar →
  Overengineering für ein Hobby-Tool. Verworfen, Code als Basis bleibt.

## Aufwand

~1-2 h. Reine Doku-/Flag-/Test-Arbeit, kein Algorithmus-Code, ohne Radio
voll prüfbar. Test-Ziel: 1738 grün (mit angepassten AP-Lite-Tests).

## DeepSeek-Findings — Bilanz

- 4 Diagnosepunkte (A1, A2, B1, B2): **alle bestätigt**, 0 Halluzinationen.
- Strategie-Empfehlung B: **angenommen** (deckt sich mit Eigen-Analyse +
  Projekt-Philosophie).
- Pragmatischer Mittelweg (Phasenschätzung aus Costas, ~+3 dB, 2-3 Tage):
  von DeepSeek erwähnt, aber selbst **abgeraten** solange kein Feldtest
  möglich → nicht in V3 übernommen. Begründung: experimentell bliebe es
  trotzdem, Aufwand für ein nie-funktionierendes Feature unverhältnismäßig.
- Modell-Hinweis: Review lief über `deepseek-v4-pro` (Helper-Default), nicht
  `reasoner` — v4-pro ist laut Projekt-Bilanz der aktuelle Workhorse
  (47-Cycle, 0 Halluzinationen). Für Transparenz vermerkt.
