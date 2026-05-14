# DeepSeek — Staerken und Schwaechen (lebendes Dokument)

> ⚠️ **MIGRATIONS-HINWEIS 14.05.2026 Abend:** System-wide DeepSeek V4
> Migration abgeschlossen. Ab nächster Session nutzt
> `tools/deepseek_review.py` + alle PAL-MCP-Calls **deepseek-v4-pro**
> (1M Context, 131K Output). Die Lessons unten sind aus der V3-Ära
> (`deepseek-reasoner` = R1).
>
> **V4-Verhalten muss empirisch neu beobachtet werden** in den
> nächsten 2-3 Sessions. Erwartung (geschätzt aus 1M-Context +
> besserem Reasoning): ~20-30% weniger Halluzinationen, weniger
> File-Selektions-Probleme (V4 kann ganzen mw_radio.py + diversity.py
> + omni_cq.py auf einmal lesen — Bundle F R1-SOLLTE-1
> `_gain_measure_locked`-Halluzination wäre vermutlich vermieden).
>
> **V3-Lessons unten bleiben als historische Referenz** — viele
> Patterns (Race-Conditions, KISS-Bewertung, Atomic-Persist) sollten
> auch in V4 valide sein. Verifikation pro Pattern bei erstem
> V4-Sample.

**Zweck:** Wachsende Sammlung der Bereiche in denen DeepSeek
zuverlaessig hilft — und der Bereiche in denen DeepSeek regelmaessig
halluziniert oder Blindspots hat. Ziel: vor jedem Workflow-Prompt
wissen womit DeepSeek wirklich hilft und wo Claude besser selber denkt.

**Lese-Trigger:** Vor jedem DeepSeek-Review (V2→R1-Schritt im Workflow).
Reduziert Halluzinations-Trigger durch praeziseres Prompting + filtert
Findings besser.

**Schreib-Trigger:** Am Session-Ende (Phase 3 Feierabend), wenn neue
DeepSeek-Erfahrungen aufgetreten sind. Format unten.

---

## V4 Lessons (ab 15.05.2026) — Sektion noch leer

Wird gefüllt nach 2-3 V4-Pro-Review-Cycles. Erwartete Themen:
- Halluzinations-Vergleich V4 vs V3
- 1M-Context-Effekte (komplette Module-Reads vs File-Selektion)
- Reasoning-Tiefe-Verschiebung
- Format-/Stil-Veränderungen
- Neue V4-spezifische Blindspots

Bis dahin: V3-Patterns unten anwenden + Findings kritisch prüfen.

---

## V3 Lessons (historisch, bis 14.05.2026)

## Wann R1 SEHR gut hilft (R1 hier IMMER einbinden)

### 1. Race-Conditions im Threading
- **CPython-GIL-Atomizitaet:** R1 weiss dass `current_s * factor` NICHT
  atomar ist (mehrere Bytecode-Instruktionen) und braucht `threading.Lock`.
  → Bundle C 13.05.2026 R1-V2-KP-2 fand Race in `_Backoff.fail()`.
- **Konstruktor-only-State + Mutation-Bedarf:** R1 erkennt wenn ein
  Attribut nur 1× im Konstruktor gesetzt wird aber zur Laufzeit
  aktualisiert werden muss.
  → Bundle C Final-R1-KP-1 fand `PSKReporterClient._mode` Sync-Bug.

### 2. Algorithmus-Wurzel-Diagnose (Anti-Symptom-Fix)
- R1 fragt aktiv „warum hat der bestehende Algorithmus nicht
  funktioniert?" und blockiert Code wenn die Antwort fehlt.
  → P14 13.05.2026 R1-F2 KRITISCH: erzwang Sanity-Test mit einfachem
  Median bevor MAD-Filter eingebaut wurde.

### 3. Statistik / Numerik / Mathematische Korrektheit
- Trimmed-Median vs. MAD-Filter Trade-offs.
- Schwellenwert-Berechnung (Deadband, Threshold).
- Floating-Point-Vergleichs-Risiken.
  → P14 R1-F1 fand DEADBAND-Einfrier-Trap, F3 schlug MAD-Filter statt
  Trim vor, F4 erkannte Damping-Doppeländerung als KISS-Verstoß.

### 4. Architektur-Trade-offs / KISS-Bewertung
- R1 erkennt 2-Knoepfe-Aenderungen wenn 1 reicht.
- R1 markiert Overengineering (verfruehte Abstraktionen, zu viele
  Konfig-Parameter).
  → P14 R1-F4: „DAMPING-Aenderung 0.7→0.5 ist unnoetig und erhoeht
  Korrekturzeit ohne Mehrwert" — korrekt, abgelehnt in V3.

### 5. CSS / Frontend-Layout-Bugs
- Beweis-Fakt 15.03.2026: CSS flex-Bug nach 4 Claude-Fehlversuchen
  fand R1 sofort. CLAUDE.md-Memory bestaetigt das als „bewiesenen
  Fakt der DeepSeek-Pflicht".

### 6. Atomic-Persist / Multi-Phase-Pipelines
- R1 erkennt Half-State-Risiken wenn Phase A schreibt + Phase B haengt.
  → P22 10.05.2026 R1-K1: staged-erst-nach-success Pattern.

### 7. Modal-Dialog-Race-Conditions in PySide6
- R1 fand `QTimer.singleShot(0, ...)`-Defer-Pattern fuer
  `exec()`-im-__init__-Blockade.
  → P26 10.05.2026 R1-K2: window.show() blockiert wenn exec() vor show
  laeuft.
- R1 erkennt PySide6-`RuntimeError`-on-destroyed-Object.
  → P26 R1-K1: try/except RuntimeError um emit auf zerstoerte Dialoge.

### 8. Test-Qualitaets-Review
- R1 erkennt wenn Tests das wegmocken was der Test prüfen sollte.
  → P14 Final-R1: HINWEIS `monkeypatch.delenv` Env-Var-Isolation.
- R1 fordert Sanity-Anker-Tests mit Identity-Stubs.

### 9. KOENNTE-Findings die spaeter wichtig werden
- R1's „KOENNTE"-Hinweise sind oft Bedingungen die in 6 Monaten beissen.
  Beispiel: T5-Notnagel-Pfad-Hinweis bei P14 — heute akademisch,
  morgen Edge-Case.

---

## Wann R1 KACKE baut (R1 hier vorsichtig prüfen oder nicht prompten)

### 1. Halluziniert „fehlende Files" bei selektiver File-Auswahl
- **Beweis:** 02.05.2026 Bandpilot Final-R1-Review mit 6 von 40 Files:
  R1 meldete 18 fehlende Doku-Files als BUG, ALLE existierten.
  Memory: `feedback_deepseek_partial_files_hallucination.md`.
- **Pflicht:** Bei selektiver File-Auswahl explizit im Prompt
  schreiben „Files X/Y/Z sind angehaengt, alle anderen werden NICHT
  erwartet" ODER alle relevanten Files anhaengen.

### 2. Verpasst Encoder-/Hardware-Busy-Races zwischen aufeinanderfolgenden TX-Slots
- **Beweis:** P4-V5 10.05.2026 — R1 hat Klaerungsfrage 3 (Decoder-
  Blockade) als KISS abgesegnet, aber den ECHTEN Bug verpasst:
  `_tx_worker.finally` zwischen Pos 0 und Pos 1.
- **Pflicht:** Bei TX-TX-Konsekutiv-Plaenen R1-Prompt explizit nach
  „Encoder-Throughput zwischen aufeinanderfolgenden Slots" fragen.
  Memory: `feedback_r1_encoder_busy_blindspot.md`.

### 3. Halluziniert ganze Bugs in V4-Modus
- **Beweis:** v0.74 V4 (deepseek-chat): „Phase haengt ewig" — falsch,
  ohne Existenz im Code. CLAUDE.md bestaetigt.
- **Pflicht:** Bei R1-Antworten IMMER Code-grep als Verifikation.
  Niemals R1-Aussage als autoritativ akzeptieren ohne grep.

### 4. „KRITISCH" kann manchmal Overstatement sein
- Beispiel: R1-V2-Findings haben oft KRITISCH bei Symptom-Bewertung
  obwohl die Wurzel noch unbestaetigt ist.
- **Pflicht:** R1-„KRITISCH" pruefen ob es Wurzel-Bug oder
  Symptom-Wahrnehmung ist. Bei Symptom: in V3 dokumentieren, nicht
  blind uebernehmen.

### 5. Mike's Designentscheidungen werden mit Konventionen ueberstimmt
- **Beweis:** P1.ANTENNE-COLLAPSE v0.95.11: R1 wollte „immer sichtbar",
  Mike's Vision war einklappbar — Mike's Vision gewinnt.
- **Pflicht:** Bei UI/UX-Designfragen R1-Prompt klauseln „Mike's
  Designentscheidung NICHT verhandelbar". Memory:
  `feedback_mike_design_overrides_convention.md`.

### 6. Bei Trivial-Tasks (<5 Zeilen, Tippfehler, pure Refactor)
- R1 overthinkt, gibt Findings die keinen Sinn machen.
- **Pflicht:** Trivial-Klausel im Workflow (V2c) — KEIN R1-Prompt bei
  Tippfehler/Style/<5 Zeilen.

### 7. Prompt-Token-Limits unterschaetzt
- 19000+ Token-Prompts machen R1 langsam (~30s) und qualitativ
  schwaecher. Lieber prompts splitten.
- **Pflicht:** Wenn Prompt > 15k Tokens — Files reduzieren oder Prompt
  fokussieren auf 1-2 Aspekte statt 8.

---

## Schreib-Format fuer neue Eintraege (Feierabend Phase 3)

```markdown
### YYYY-MM-DD vX.YY — Kontext (P-Nummer oder Feature)
- **R1-Aktion:** Was R1 gemacht hat (Finding, Empfehlung, Vorschlag)
- **Ergebnis:** Hat R1 geholfen? Halluziniert? Blindspot?
- **Konsequenz:** Aufnahme in „Staerken" oder „Schwaechen" oben.
```

**Heuristik fuer Aufnahme:** nur wenn R1-Verhalten **wiederholbar
ueberraschend** war (positiv oder negativ). Einzelne Findings die R1
korrekt + erwartbar abgeliefert hat brauchen keinen Eintrag.

---

## Aktuelle Session-Logs

### 13.05.2026 v0.97.18 — Toast-Bundle (Medaillen + 6s)
- **R1-Aktion V2:** 1 SOLLTE-FIX (Emoji-Fallback fuer Systeme ohne
  Color-Emoji-Renderer) + 5 HINWEIS (alle KISS-Bewertungen positiv).
  V3 uebernahm Fallback via Env-Var. Final-R1: 0 Findings „Push
  freigegeben", 9/10.
- **Ergebnis:** SEHR gut — R1 bestaetigte Medaillen-Wahl 🥇🥈🥉 explizit
  als „perfekt, universell verstaendlich, hebt sich vom ●-Marker ab".
  R1-SOLLTE-Defensive (Env-Var-Fallback) war elegant: deterministische
  Tests + Robustheit gegen alte Linux-Distros ohne Performance-Kosten.
- **Konsequenz:** Bestaetigt Staerken #4 (KISS-Bewertung) + #8 (Test-
  Qualitaet). **Neue Beobachtung:** R1 ist sehr gut bei **„Defensive
  ohne Overengineering"** — schlaegt Env-Var-Mechanismus vor (KISS),
  nicht User-Settings-Dialog (Overengineering bei einem Mike-User).

### 13.05.2026 v0.97.17 — P46 Bandpilot Normal-Reintegration
- **R1-Aktion V2:** 1 KRITISCH (alte P35-Bug-E-Tests muessen geloescht/
  umgeschrieben werden — V1 hatte sie uebersehen, nur die 4 Workaround-
  Tests adressiert) + 2 SOLLTE (F2 Doppelaufruf `_apply_normal_mode` in
  `_set_rx_mode_direct`, F3 TX-pending nur Band-Konsistenz nicht Modus)
  + 1 KOENNTE (F4 Test rec=None). Bewertung 8/10. Final-R1: 9/10 „Push
  freigegeben", 1 KOENNTE (Doku bandpilot_de.md).
- **Ergebnis:** SEHR gut — R1-F1 (kritische Test-Loeschung) wurde von
  V1 uebersehen. R1-F2 (Doppelaufruf) war latent-Bug, durch Refactor
  beseitigt. R1-F3 (Modus-Konsistenz im pending) war echte Race-
  Condition (User aendert Modus waehrend TX). Alle Findings legitim.
- **Konsequenz:** Bestaetigt Staerken #1 (Race-Conditions), #4 (KISS-
  Bewertung), #8 (Test-Qualitaet). Plus neue Beobachtung: **R1 findet
  zuverlaessig Tests die OBSOLET sind nach Code-Aenderung** — V1 hatte
  4 Workaround-Tests anvisiert, R1 wies auf 2 weitere hin die direkt
  alte Logik testeten.

### 13.05.2026 v0.97.16 — P14 DT-Werte-Symmetrie
- **R1-Aktion:** V2-Review fand 2 KRITISCH (F1 Deadband-Einfrier, F2
  Wurzel-nicht-untersucht-Anti-Symptom-Fix) + 3 SOLLTE (F3 MAD statt
  Trim, F4 Damping-KISS, F5 Test-Grenzfaelle). Final-R1: 9/10, 1
  KOENNTE (T5-Notnagel-Test-Konstruktion) + 1 HINWEIS (Env-Var-Isolation).
- **Ergebnis:** SEHR gut — F1 + F2 wurden VOR Code-Schreiben abgefangen.
  Trim → MAD-Wechsel war signifikante Qualitaetsverbesserung. Final-R1
  Test-Qualitaets-Hinweise alle relevant und schnell fixbar.
- **Konsequenz:** Bestaetigt Staerken #2 (Algorithmus-Wurzel), #3
  (Statistik), #4 (KISS), #8 (Test-Qualitaet).

### 13.05.2026 v0.97.15 — Bundle C (P10 PSK + P13 RX)
- **R1-Aktion:** V2-Review fand KP-2 Race in `_Backoff.fail()`
  (CPython-GIL-Atomizitaet). Final-R1 fand zusaetzlich KP-1
  PSKReporterClient.set_mode-Bug (Mode-Sync).
- **Ergebnis:** SEHR gut — 2 echte Bugs gefunden die V1 und V2 alleine
  uebersehen haetten.
- **Konsequenz:** Bestaetigt Staerken #1 (Race-Conditions/Threading).
