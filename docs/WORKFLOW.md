# Universal Feature-Integration Workflow

**Version:** 2026-04-29 v1.1
**Geltungsbereich:** Projekt-uebergreifend (SimpleFT8, IC-7300-Fork, Mobile-
App, andere Mike-Projekte). Sektionen mit `[PROJEKT-VARIABLE]` werden je
Projekt angepasst — die Workflow-Logik selbst bleibt identisch.

Dieser Workflow ist die verbindliche Vorlage fuer alle **nicht-trivialen**
Feature-Entwicklungen (>5 Zeilen Code, neue Module, Architektur-Aenderungen,
kritische Bug-Fixes). Triviale Aenderungen (Tippfehler, Kommentar-Updates,
< 5 Zeilen) brauchen den Workflow **nicht**.

Leitsatz: **Qualitaet > Zeit > Geld.** Lieber 30 Min laenger im Plan-Mode
als 3 Stunden nachbessern.

---

## Rollenverteilung

- **Claude (Opus / Sonnet)** ist Chef-Entwickler. Kennt die Architektur, alle
  Module, alle Designentscheidungen. Arbeitet auf hoechster Effort-Stufe.
  Trifft alle finalen Entscheidungen. Verantwortlich fuer Code-Qualitaet,
  Tests, Wartbarkeit.
- **DeepSeek-R1** (`deepseek-reasoner`) ist **Reviewer** — kritisiert Prompts
  und Code. Liefert KEINE Loesungen. Findings werden von Claude bewertet,
  nicht blind uebernommen.
- **Mike** ist Auftraggeber. Gibt explizite Freigaben fuer V3, Plan-Mode,
  Push, Releases. Entscheidet bei strategischen Architektur-Fragen.

---

## Projektphilosophie `[PROJEKT-VARIABLE]`

**Pro Projekt anpassen** — wird oben in V1/V2/V3 als Kontext mitgeschickt:

- **Was ist das Projekt?** (Hobby / Tool / Produkt / Forschung)
- **Wer benutzt es?** (Einzelner Operator / Team / Endkunden / KI)
- **Was ist KEIN Use-Case?** (Multi-Tenant / Contest-Mode / Enterprise / ...)
- **KISS-Praeferenz:** wie strikt? (Hobby = sehr strikt; Produkt = ausgewogen)
- **Domain-Pflichten:** Hardware-Constraints (z.B. ANT1=TX in SimpleFT8),
  Latenz-Anforderungen (z.B. FT8 0.5s DT-Toleranz), Datenschutz, Sicherheit.

**Beispiel SimpleFT8 (Stand 2026-04-29):**
```
- Hobby-Funker-Tool fuer einen einzelnen Operator (Mike, DA1MHH).
- KEIN Contest-Tool, KEIN Multi-Op, KEINE Pileup-Jagd.
- KISS strikt: drei einfache Zeilen > eine schlaue Abstraktion.
- Hardware-Pflicht: ANT1 = TX immer. ANT2 = nur RX. Vor jedem TX-
  Trigger muss set_tx_antenna("ANT1") verifiziert sein (Hardware-
  Schaden moeglich bei TX auf Regenrinne).
- Visuell: dunkles Theme, modern/Neon — KEIN macOS-Default-Grau.
```

---

## Was ein guter Feature-Prompt enthalten muss

Jeder V1/V2/V3 deckt diese Sektionen ab — sonst entstehen Luecken die
DeepSeek nicht ausgleichen kann:

1. **Ziel** — was soll das Feature leisten? Eine Sache pro Prompt.
2. **Akzeptanzkriterien** — woran erkennt man dass es fertig und korrekt
   ist? Konkret, messbar, pruefbar.
3. **Betroffene Module/Dateien** — mit `Datei:Zeile`-Verweisen wo sinnvoll.
4. **Randbedingungen** — Threading, Persistence, UI-Regeln, Hardware-/Domain-
   Pflichten (siehe Projektphilosophie).
5. **Nicht im Scope** — was explizit NICHT gebaut wird. Wichtig fuer R1
   damit es nicht versucht out-of-scope-Themen wieder reinzuholen.
6. **Testbarkeit** — wie wird das Feature getestet? Welche Test-Cases sind
   unverzichtbar? Was wird Mike manuell verifizieren?

---

## Schritt 0 — Code-Verifikation (PFLICHT vor V1!)

Bevor V1 geschrieben wird:

1. Relevante Dateien lesen (`Read` / `Grep`).
2. **Datei:Zeile-Verweise verifizieren** — existieren die Funktionen wirklich?
   Welche Signatur? Welche Rueckgabewerte?
3. Existierende Strukturen identifizieren — was kann reused werden, was
   muss neu sein?
4. Domain-Pflichten aus `CLAUDE.md` durchlesen — explizit in V1 als
   Randbedingung aufnehmen.
5. **Memory checken** — gibt es Lessons-Learned aus frueheren Features
   die hier relevant sind? (Z.B. „R1 braucht ALLE referenzierten Files".)

**Begruendung:** Ohne Code-Verifikation halluziniert schon V1. Bei v0.74
hat sich gezeigt: 5 Min Code-Lookup zu Beginn spart Stunden falscher
Annahmen weiter unten im Workflow.

---

## Schritt 1 — Prompt V1 schreiben + Self-Review → V2

### Schritt 1a — V1 schreiben

Schreibe Prompt V1 mit allen 6 Sektionen aus „Was ein guter Feature-Prompt
enthalten muss".

### Schritt 1b — Self-Review als „frische KI"

Wechsle in die Rolle einer **frischen, auf das Projekt-Domaene + Python
spezialisierten KI** die diesen Prompt zum ersten Mal sieht. Analysiere
ihn kritisch:

- Was fehlt inhaltlich oder ist zu ungenau formuliert?
- Welche Randbedingungen, Abhaengigkeiten oder Sonderfaelle wurden nicht
  bedacht?
- Welche Informationen sind zu knapp?
- Gibt es Widersprueche oder Mehrdeutigkeiten?
- Ist der Aufwand fuer das Projekt-Format (Hobby vs Produkt) angemessen?

**Erfahrung:** Dieser Schritt fuehrt typisch zu **70% der Verbesserungen**
— R1 ist die Verifikations-Schicht obendrauf, nicht der Hauptbug-Faenger.
Wer 1b skippt, schickt einen halb-garen Prompt an R1 und bekommt halb-gare
Findings.

### Schritt 1c — V2 schreiben

Schreibe danach den Prompt **vollstaendig neu** als V2 — kein „ergaenze
Abschnitt X", keine Teilauszuege, kein V1-mit-Anhang. Immer ein kompletter,
in sich konsistenter und vollstaendiger Prompt.

---

## Schritt 2 — DeepSeek-R1-Review

### Aufruf

```bash
cat prompts/feature_v2.md | ./venv/bin/python3 tools/deepseek_review.py \
    [betroffene/datei1.py datei2.py ...]
```

### Wichtige Regeln

- **Bei Code-Reviews immer ALLE referenzierten Files anhaengen** — sonst
  halluziniert R1 „fehlt"/„nicht verbunden"-Findings (siehe Memory
  `feedback_deepseek_files_attachment.md`). 65K Token Context-Limit ist
  grosszuegig — lieber zu viele als zu wenige Files.
- **Modell: immer `deepseek-reasoner` (R1)** — staerkstes Modell, KEINE
  Ausnahme. Kein `--chat` (V4) fuer Feature-Reviews.
- Was geschickt wird: nur **vollstaendiger V2** — niemals V1, niemals
  Teile, niemals V1 mit Anhang. Plus Code-Files als Anhang.

### Verschaerfte DeepSeek-Rollenanweisung (Pflicht-Kopf von V2)

Diese Anweisung am ANFANG jedes V2-Prompts voranstellen:

```
Du bist Senior Python-Entwickler mit Hobby-Projekt-Erfahrung,
spezialisiert auf [DOMAIN — z.B. Amateurfunk-Software] und
[FRAMEWORK — z.B. PySide6, NICHT PyQt5: Signal statt pyqtSignal,
Slot statt pyqtSlot]. Du weisst dass Code fuer einen einzelnen
Operator NICHT die gleichen Schutzmechanismen wie Multi-Tenant-
SaaS braucht.

Deine einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT
das Problem zu loesen. Erstelle eine strukturierte Liste mit:
Luecken, fehlenden Informationen, Unklarheiten, Widerspruechen,
Verbesserungsvorschlaegen und offenen Fragen.

KRITISCHE REGELN fuer deine Findings:

1. SCOPE-RESPEKT: Wenn der Prompt etwas explizit als „out-of-scope"
   oder „nicht im Scope" markiert, NICHT erneut als Finding melden.
   Respektiere bewusste Mike-Entscheidungen — sie sind keine
   Versehen.

2. UX-DENKEN BEI REGELN: Wenn du eine Schwellwert-Faustregel vor-
   schlaegst (z.B. „if X > N → tu Y"), denke die UX-Folgen durch.
   Eine Regel die im Edge-Case zu schlechter Bedienbarkeit fuehrt
   ist eine schlechte Regel — schlage sie nicht vor.

3. KISS VOR DEFENSIV: Bevor du Komplexitaet vorschlaegst (neue
   Klasse, Fallback-Mechanismus, Library, Wrapper-Schicht), frage
   dich: Wahrscheinlichkeit dass das Problem real auftritt > 50%?
   Wenn nein, weglassen. „Koennte vielleicht passieren" ist KEIN
   Grund fuer Code-Komplexitaet in einem Hobby-Projekt.

4. PROJEKT-BEZUG: Jedes Finding muss konkret am Projekt gemessen
   werden. Frage bei jedem Finding: „Hilft das dem konkreten User
   beim konkreten Use-Case?" Wenn nein — kein Finding. Generic
   Best-Practice-Rufe ohne Projekt-Bezug sind Noise.

5. FORMAT: Liefere eine Tabelle mit Spalten Schwere | Finding |
   Datei:Zeile | Empfehlung. Severity-Stufen: Bug (rot) /
   Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Bedenke: Overengineering ist selbst ein Fehler den du benennen sollst.
```

### DeepSeek nicht erreichbar?

Bei kein Token / Netzwerk / Timeout:

> Claude meldet sofort:
> „DeepSeek nicht erreichbar — [Grund falls bekannt].
> Ich warte auf deine Entscheidung:
>   A) Ich fuehre einen zweiten eigenen Self-Review als Ersatz durch
>      und markiere V3 als 'ohne DeepSeek-Review'.
>   B) Wir pausieren bis DeepSeek wieder verfuegbar ist.
> Was soll ich tun?"

→ **Kein selbststaendiges Weitermachen ohne Mikes Entscheidung.**

---

## Schritt 2.5 — R1-Findings gegen Code verifizieren

**NEU seit v1.1.** Pflicht-Schritt zwischen R1-Antwort und V3-Schreiben.

R1 halluziniert gelegentlich Code-Stellen die nicht existieren oder schon
gefixt sind. Bevor ein Finding ins V3 wandert:

1. Jede behauptete `Datei:Zeile`-Referenz mit `Read` oder `Grep` gegenchecken.
2. Bei „X fehlt"/„Y wird nicht aufgerufen": **immer** im Code verifizieren
   (Memory: v0.75-Auto-Hunt R1 behauptete `mw_radio.py:297` Hook fehle —
   war da, kostete 10 Min).
3. Halluzinierte Findings rausfiltern. Verifizierte Findings gehen weiter
   in Schritt 3 zur Bewertung.

**Aufwand:** ~5 Min/Zyklus. Spart locker das Doppelte an spaeterer
Diskussion.

---

## Schritt 3 — Findings bewerten + V3 + Zusammenfassung

Du bist wieder Chef. Pruefe **jedes** R1-Finding einzeln:

### Annehmen wenn

Das Finding beschreibt eine **echte Luecke**, einen **echten Widerspruch**
oder eine **sinnvolle Praezisierung** die den Prompt klarer und besser macht.

### Ablehnen wenn

Das Finding geht am tatsaechlichen Code/Kontext vorbei, ist fuer das
Projekt-Format (Hobby/Solo) ueberdimensioniert, fuegt unnoetige Komplexitaet
hinzu, oder ist eine Halluzination.

→ **Jede Ablehnung wird in einem Satz begruendet.** Mike sieht alle
  Ablehnungen + Begruendungen in der Zusammenfassung.

### Aufwands-Check vor V3

Ist der entstehende Implementierungsaufwand noch verhaeltnismaessig fuer
das Projekt-Format? Wenn nein → Mike darauf hinweisen und gemeinsam
abwaegen bevor V3 fertiggestellt wird.

### V3 schreiben

Schreibe den Prompt **vollstaendig neu** als V3 — kein Teilprompt, kein
V2-mit-Anhang — immer ein kompletter eigenstaendiger Prompt.

### Zeige danach

1. **V3** — fertiger Prompt (vollstaendig, direkt verwendbar, Copy-Paste-fertig).

2. **Zusammenfassung** (kompakt und verstaendlich):
   - Welche R1-Findings wurden angenommen (und warum)?
   - Welche wurden abgelehnt (und warum)?
   - Halluzinierte Findings (Schritt 2.5 verworfen) gesondert nennen.

---

## Schritt 4 — Freigabe

Warte auf Mikes **explizites OK**.

Erst nach OK von Mike: `/plan` aufrufen ODER (bei klar strukturiertem V3)
direkt mit Schritt 5 starten.

**Kein selbststaendiger Sprung in den Planungsmodus oder die Implementierung.**

---

## Schritt 5 — Implementierung

Nach Freigabe durch Mike:

- **Atomare Commits** — pro Feature/Bugfix/Test ein Commit, nicht ein
  Mega-Commit. Beispiel: Refactoring + neue Tests + Doku = 3 Commits.
- **Tests gruen vor jedem Commit** — `./venv/bin/python3 -m pytest tests/ -q`
  oder das aequivalente Test-Kommando des Projekts.
- **Push nach Remote NUR auf explizite Mike-Freigabe** (siehe CLAUDE.md
  Commits-Sektion).

---

## Schritt 5b — Final-R1-Codereview (NEU seit v1.1)

**Pflicht-Schritt vor dem letzten Commit** bei nicht-trivialen Aenderungen.

```bash
echo "Reviewe [files] — Refactor [version]. Pruefe: Korrektheit, Bugs,
Best-Practice, KISS, Test-Abdeckung. Strukturiert antworten." | \
./venv/bin/python3 tools/deepseek_review.py [geaenderte/files.py ...]
```

**Findings auswerten:**

- 🔴 **Bug**: sofort fixen, in den letzten Commit integrieren oder
  separater Bug-Commit davor.
- 🟠 **Risiko / Lifecycle**: bewerten — bei klarem Mehrwert fixen, sonst
  als TODO/Memory dokumentieren.
- 🟡 **Verbesserung**: meist out-of-scope — bei billigem Fix integrieren,
  sonst weglassen.
- ⚪ **Hinweis**: dokumentieren, nicht fixen.

**Begruendung fuer den Schritt:** v0.76-Erfahrung — Final-Review fand
Timer-Lifecycle-Bug (Crash-Potenzial beim Dialog-Schliessen) der in Tests
unsichtbar war. **1 echter Bug pro 4 Reviews ist Gold.**

---

## Schritt 6 — Lessons-Learned (NEU seit v1.1)

**Pflicht-Schritt nach Feature-Abschluss.** Nicht skippen — das ist die
Quelle der langfristigen Workflow-Verbesserung.

Drei Fragen beantworten:

1. **Was war ueberraschend?** (Halluzinationen, unerwartetes Verhalten,
   Tool-Marotten, Edge-Cases)
2. **Was wuerde ich rueckblickend anders machen?** (Zeit-Verschwendung,
   Sackgasse, Werkzeug-Fehlwahl)
3. **Welches Memory soll geschrieben/aktualisiert werden?** (Pattern-
   Erkennung — wenn etwas zwei Mal nervt, ist es Memory-wuerdig)

**Beispiele aus der Vergangenheit:**

- v0.75: „R1 halluziniert wenn Files fehlen" → Memory
  `feedback_deepseek_files_attachment.md`.
- v0.76: „R1 ignoriert out-of-scope-Markierungen" → fuehrte zur
  verschaerften Rollenanweisung (Workflow v1.1).

---

## Anti-Patterns (zu vermeiden!)

- ❌ V1 schreiben + sofort an DeepSeek (ohne V2-Self-Review).
- ❌ V1 mit „Korrektur-Anhang" als V2 verkaufen.
- ❌ V2 stueckweise an DeepSeek schicken.
- ❌ R1-Findings blind uebernehmen ohne Code-Verifikation (Schritt 2.5).
- ❌ R1-Findings blind ignorieren ohne Begruendung.
- ❌ Plan-Mode-Sprung ohne Mike-Freigabe.
- ❌ `--chat` (V4) statt `--reasoner` (R1) bei Feature-Reviews.
- ❌ Domain-Pflichten (Hardware, Sicherheit, Datenschutz) ignorieren oder
  erst im Test pruefen.
- ❌ Final-R1-Codereview ueberspringen weil „Tests sind ja gruen".
- ❌ Lessons-Learned-Schritt skippen weil „heute keine Zeit".

---

## Beispiel-Aufrufe

```bash
# V2 an DeepSeek (typisch fuer Code-Review):
cat prompts/auto_hunt_v2.md | ./venv/bin/python3 tools/deepseek_review.py \
    core/auto_hunt.py ui/mw_radio.py ui/main_window.py

# Final-R1-Codereview vor letztem Commit:
echo "Reviewe ui/settings_dialog.py — Refactor v0.76. Korrektheit?
Bugs? KISS-Bewertung? Test-Abdeckung?" | \
./venv/bin/python3 tools/deepseek_review.py \
    ui/settings_dialog.py tests/test_settings_dialog_smoke.py

# Architektur-Frage ohne Files (rein konzeptionell):
cat prompts/architektur_frage.md | ./venv/bin/python3 tools/deepseek_review.py

# Trivial-Verifikation mit V4 (Opt-in, nur fuer „existiert X?"-Fragen):
echo "Existiert load_preset noch im Code?" | \
./venv/bin/python3 tools/deepseek_review.py --chat core/diversity.py
```

---

## Wann Workflow uebersprungen werden darf

**Nur Triviales:**
- Tippfehler, Umbenennungen, < 5 Zeilen.
- Lokaler Patch in einer Methode ohne Architekturwirkung.
- Reines Doku-Update.
- Test-Anpassung an bereits gemergte API-Aenderung.
- Bugfix mit klarer `Datei:Zeile`-Diagnose und einzigem Akzeptanzkriterium.

**Bei Grenzfall:** lieber Workflow fahren als Sackgasse riskieren.

---

## Workflow-CHANGELOG

### v1.1 — 2026-04-29

**Auslöser:** v0.76 Settings-Tabs-Refactor — R1 zeigte 30% Noise-Quote
und ignorierte explizite Out-of-Scope-Markierungen aus V3. Final-Review
fand dafuer einen echten Lifecycle-Bug (Timer-Stop in `closeEvent`).

**Aenderungen:**
- DeepSeek-Rollenanweisung verschaerft (5 kritische Regeln statt 1).
- **Schritt 2.5 NEU:** R1-Findings gegen Code verifizieren (Pflicht).
- **Schritt 5b NEU:** Final-R1-Codereview als Pflicht-Schritt.
- **Schritt 6 NEU:** Lessons-Learned (3 Fragen + Memory-Update).
- **Universalisierung:** Projekt-Variablen statt SimpleFT8-spezifischer
  Hardcodes (Geltungsbereich auf alle Mike-Projekte erweitert).
- Mini-CHANGELOG am Ende fuer historische Nachvollziehbarkeit.

### v1.0 — 2026-04-29

**Auslöser:** v0.74 Diversity-Bandwechsel-Bug-Fix.

**Aenderungen ggue. Mike's Original-Template:**
- PyQt5 → PySide6 (API-Unterschiede in Rollenanweisung dokumentiert).
- Schritt 0 Code-Verifikation hinzugefuegt.
- Tool-Aufruf mit Files-Anhang dokumentiert (`tools/deepseek_review.py`).
- Hardware-Pflichten als explizite Randbedingung.
- Anti-Patterns + Beispiel-Aufrufe.
