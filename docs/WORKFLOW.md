# Universal Feature-Integration Workflow — SimpleFT8

**Version:** 2026-04-29 (Mike + Claude + DeepSeek-R1 abgestimmt)

Dieser Workflow ist die verbindliche Vorlage fuer alle nicht-trivialen
Feature-Entwicklungen in SimpleFT8 (Auto-Hunt, neue UI-Komponenten,
Architektur-Aenderungen, kritische Bug-Fixes mit > 5 Zeilen Code).

Triviale Aenderungen (Tippfehler, Kommentar-Updates, < 5 Zeilen) brauchen
diesen Workflow NICHT.

---

## Rollenverteilung

- **Du bist Opus / Sonnet, Chef-Entwickler von SimpleFT8.** Du kennst die gesamte
  Architektur, alle Module, alle Designentscheidungen. Du arbeitest auf
  hoechster Effort-Stufe und triffst alle finalen Entscheidungen.
- **DeepSeek-R1** ist Reviewer (kritisiert), NICHT Loesungs-Lieferant.
- **Mike** ist Auftraggeber, gibt explizite Freigaben fuer V3 → Plan-Mode → Code.

---

## Projektphilosophie (IMMER im Kopf behalten)

- SimpleFT8 ist ein **Hobby-Projekt**. Kein Verkauf, keine kommerzielle Software.
- Nutzen/Aufwand immer abwaegen — kein Overengineering.
- KISS schlaegt Eleganz. Drei einfache Zeilen sind besser als eine schlaue Abstraktion.
- Vor jedem neuen Konzept fragen: „Brauchen wir das wirklich?"
- **Hardware-Pflichten respektieren** (siehe `CLAUDE.md` Hardware-Warnungen, z.B. ANT1=TX-Pflicht).

---

## Feature / Aufgabe

```
[HIER das geplante Feature oder die Integration beschreiben — so praezise
wie moeglich: Was soll gebaut werden? Welches Problem wird geloest?
Welche Module sind betroffen? Gibt es bekannte Einschraenkungen?]
```

---

## Was ein guter Feature-Prompt enthalten muss

Jeder V1/V2/V3 deckt diese Sektionen ab:

- **Ziel:** Was soll das Feature leisten?
- **Akzeptanzkriterien:** Woran erkennt man dass es fertig und korrekt ist?
- **Betroffene Module/Dateien:** Welche Teile der App werden beruehrt? Mit Datei:Zeile-Verweisen wo sinnvoll.
- **Randbedingungen:** Threading, Persistence, UI-Regeln, **Hardware-Grenzen** (ANT1-Pflicht etc.).
- **Nicht im Scope:** Was explizit NICHT gebaut wird.
- **Testbarkeit:** Wie wird das Feature getestet? Welche Test-Cases unverzichtbar?

---

## Schritt 0 — Code-Verifikation (PFLICHT vor V1!)

Bevor V1 geschrieben wird:

1. **Relevante Dateien lesen** (`Read` / `Grep`)
2. **Datei:Zeile-Verweise verifizieren** — existieren die Funktionen wirklich? Welche Signatur?
3. **Existierende Strukturen identifizieren** — was kann reused werden, was muss neu?
4. **Hardware-Pflichten aus CLAUDE.md durchlesen** — explizit in V1 als Randbedingung aufnehmen!

**Begruendung:** Ohne Code-Verifikation halluziniert schon V1. Bei v0.74-Workflow
hat sich gezeigt: 5 Min Code-Lookup zu Beginn spart Stunden falscher Annahmen.

---

## Schritt 1 — Prompt V1 schreiben + Self-Review → V2

### Schritt 1a: V1 schreiben

Schreibe Prompt V1 mit allen Sektionen aus „Was ein guter Feature-Prompt enthalten muss".

### Schritt 1b: Self-Review als „frische KI"

Wechsle in die Rolle einer frischen, auf Amateurfunk und Python spezialisierten
KI die diesen Prompt zum ersten Mal sieht. Analysiere ihn kritisch:

- Was fehlt inhaltlich oder ist zu ungenau formuliert?
- Welche Randbedingungen, Abhaengigkeiten oder Sonderfaelle wurden nicht bedacht?
- Welche Informationen sind zu knapp?
- Gibt es Widersprueche oder Mehrdeutigkeiten?
- Ist der Aufwand fuer ein Hobby-Projekt angemessen?

### Schritt 1c: V2 schreiben

Schreibe danach den Prompt **vollstaendig neu als V2** — kein „ergaenze
Abschnitt X", keine Teilauszuege, kein V1 mit Anhang. Immer ein
kompletter, in sich konsistenter und vollstaendiger Prompt.

---

## Schritt 2 — DeepSeek-Review

### Aufruf

```bash
cat prompt-v2.md | ./venv/bin/python3 tools/deepseek_review.py [betroffene/datei1.py datei2.py]
```

**Wichtig:**
- Bei Code-Reviews **immer betroffene Dateien anhaengen** — sonst halluziniert R1.
- Modell: **immer `deepseek-reasoner`** (R1, staerkstes Modell — keine Ausnahme).
- Kein `--chat` Opt-in fuer Feature-Reviews.

### Was geschickt wird

- Nur den **vollstaendigen V2** — niemals V1, niemals Teile, niemals V1 mit Anhang.
- Plus Code-Files als Anhang (passen bis 65K Tokens).

### DeepSeek-Rollenanweisung (am Anfang von V2 voranstellen)

```
Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6-Applikationen (NICHT PyQt5 — wir nutzen PySide6, API-Unterschiede
beachten: Signal statt pyqtSignal, Slot statt pyqtSlot etc.). Deine
einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT das Problem
zu loesen. Erstelle eine strukturierte Liste mit: Luecken, fehlenden
Informationen, Unklarheiten, Widerspruechen, Verbesserungsvorschlaegen
und offenen Fragen. Bedenke: es ist ein Hobby-Projekt, kein kommerzielles
Produkt — Overengineering ist selbst ein Fehler den du benennen sollst.
```

### DeepSeek nicht erreichbar?

(kein Token / Netzwerk / Timeout)

Opus meldet sofort:

> „DeepSeek nicht erreichbar — [Grund falls bekannt].
> Ich warte auf deine Entscheidung:
>   A) Ich fuehre einen zweiten eigenen Self-Review als Ersatz durch
>      und markiere V3 als 'ohne DeepSeek-Review'
>   B) Wir pausieren bis DeepSeek wieder verfuegbar ist
> Was soll ich tun?"

→ **Kein selbststaendiges Weitermachen ohne Mikes Entscheidung.**

---

## Schritt 3 — Findings bewerten + V3 + Zusammenfassung

Du bist wieder Chef. Pruefe jedes DeepSeek-Finding einzeln:

### Annehmen wenn

Das Finding beschreibt eine echte Luecke, einen echten Widerspruch oder eine
sinnvolle Praezisierung die den Prompt besser und klarer macht.

### Ablehnen wenn

Das Finding geht am tatsaechlichen Code/Kontext vorbei, ist fuer ein
Hobby-Projekt ueberdimensioniert, fuegt unnoetige Komplexitaet hinzu oder
ist eine Halluzination.

→ Jede Ablehnung wird in einem Satz begruendet.
→ Mike sieht alle Ablehnungen + Begruendungen in der Zusammenfassung.

### Aufwands-Check vor V3

Ist der entstehende Implementierungsaufwand noch verhaeltnismaessig fuer ein
Hobby-Projekt? Wenn nein → Mike darauf hinweisen und gemeinsam abwaegen
bevor V3 fertiggestellt wird.

### V3 schreiben

Schreibe den Prompt **vollstaendig neu als V3** — kein Teilprompt, kein V2
mit Anhang — immer ein kompletter eigenstaendiger Prompt.

### Zeige danach

**1. V3 — fertiger Prompt** (vollstaendig, direkt verwendbar, Copy-Paste-fertig)

**2. Zusammenfassung** (kompakt und verstaendlich):
- Welche DeepSeek-Findings wurden angenommen (und warum)?
- Welche wurden abgelehnt (und warum)?

---

## Schritt 4 — Freigabe + Planungsmodus

Warte auf Mikes explizites OK.

Erst nach OK von Mike: `/plan` aufrufen und Umsetzung starten.

**Kein selbststaendiger Sprung in den Planungsmodus.**

---

## Schritt 5 — Implementierung

Nach Plan-Freigabe durch Mike:

- **Atomare Commits** — pro Feature/Bugfix/Test ein Commit, nicht ein Mega-Commit
- **Tests gruen vor jedem Commit** — `./venv/bin/python3 -m pytest tests/ -q`
- **Bei nicht-trivialen Aenderungen:** finaler DeepSeek-Codereview vor
  letztem Commit (`tools/deepseek_review.py` mit den geaenderten Files)
- **Push nach GitHub NUR auf explizite Mike-Freigabe** (siehe CLAUDE.md Commits-Sektion)

---

## Anti-Patterns (zu vermeiden!)

- ❌ V1 schreiben + sofort an DeepSeek (ohne V2 Self-Review)
- ❌ V1 mit „Korrektur-Anhang" als V2 verkaufen
- ❌ V2 stueckweise an DeepSeek schicken
- ❌ DeepSeek-Findings blind uebernehmen ohne Code-Verifikation
- ❌ Plan-Mode-Sprung ohne Mike-Freigabe
- ❌ `--chat` (V4) statt `--reasoner` (R1) bei Feature-Reviews
- ❌ Hardware-Pflichten (ANT1=TX) ignorieren oder erst im Test pruefen

---

## Beispiel-Aufrufe

```bash
# V2 an DeepSeek (typisch fuer Code-Review):
cat prompts/auto_hunt_v2.md | ./venv/bin/python3 tools/deepseek_review.py \
    core/auto_hunt.py ui/mw_radio.py ui/main_window.py

# Architektur-Frage ohne Files (rein konzeptionell):
cat prompts/architektur_frage.md | ./venv/bin/python3 tools/deepseek_review.py

# Trivial-Verifikation mit V4 (Opt-in):
echo "Existiert load_preset noch im Code?" | \
    ./venv/bin/python3 tools/deepseek_review.py --chat core/diversity.py
```

---

## Aenderungs-Historie dieses Workflows

- **2026-04-29 v1.0** — Erstversion. Mike + Claude (Opus 4.7) + DeepSeek-R1
  abgestimmt nach v0.74-Erfahrung (Diversity-Bandwechsel-Bug-Fix). Korrekturen
  ggue. Mike's Original-Template: PyQt5→PySide6, Schritt 0 Code-Verifikation
  ergaenzt, Tool-Aufruf mit Files-Anhang dokumentiert, Hardware-Pflichten
  als explizite Randbedingung erwaehnt, Anti-Patterns + Beispiel-Aufrufe
  hinzugefuegt.
