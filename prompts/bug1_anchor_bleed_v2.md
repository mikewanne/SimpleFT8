Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und
PySide6/Qt (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt ist ein
Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine Aufgabe: meine Bug-Diagnose UND meinen Fix-Plan kritisieren — beides.
Bitte NICHT einfach zustimmen. Prüfe besonders die Qt-Mechanik (ich bin mir bei
einem Detail unsicher) und ob mein Fix ALLE Bleeding-Fälle abdeckt.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Die Logik "welche Zeile ist klickbar" (insert_call) ist
   verifiziert korrekt und NICHT Teil des Bugs — bitte nicht als Finding melden.
2. KISS VOR DEFENSIV: minimaler Eingriff. Keine neue Klasse/Abstraktion wenn
   ein zentraler Helper reicht.
3. PROJEKT-BEZUG: reines UI-Rendering im GUI-Thread, kein Threading/Hardware.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).
Overengineering ist selbst ein Fehler, den du benennen sollst.

================================================================================
BUG (Field-belegt, Screenshots)
================================================================================
Im QSO-Verlauf (QTextBrowser `log_view` in ui/qso_panel.py) sollen NUR die
klickbaren Einschub-Zeilen ("← Empf. <wir> <fremder> R-XX", eine fremde Station
ruft uns während eines laufenden QSO) als HTML-Anchor dargestellt werden:
cyan (#7FE0FF) + unterstrichen + klickbar (href "huntinsert:<call>").

TATSÄCHLICH: Nach so einer Anchor-Zeile werden AUCH die nachfolgenden Zeilen
— vor allem unsere eigenen "→ Gesendet ..."-TX-Zeilen — cyan + unterstrichen
dargestellt und sind anklickbar (lösen fälschlich hunt_insert_clicked aus).
In manchen Screenshots wirken sogar Zeilen OBERHALB der Anchor-Zeile betroffen.
Der Timeout-Marker ("✗ ... — Timeout", rot) ist NICHT betroffen.

================================================================================
MEINE ROOT-CAUSE-ANALYSE
================================================================================
ui/qso_panel.py rendert jede Log-Zeile über eine von drei Methoden:

(A) `_append_colored(text, color)`  [Zeile 588]:
    cursor ans Ende → self.log_view.setTextColor(QColor(color))
    → self.log_view.append(text)              # Plain-Text

(B) `_append_two_color(t1,c1,t2,c2)` [Zeile 634]:
    setTextColor(c1) → append(t1); dann cursor.insertText(t2, QTextCharFormat mit c2)

(C) `_append_anchor_line(text, call, color)` [Zeile 603]:
    self.log_view.append('<a href="huntinsert:..." '
        'style="color:#7FE0FF; text-decoration:underline;">TEXT</a>')   # HTML

Hypothese: `append()` mit HTML-Anchor (C) hinterlässt im log_view ein
`currentCharFormat` mit foreground=cyan, fontUnderline=true und gesetztem
`anchorHref`. Die normalen Methoden (A)/(B) rufen danach nur `setTextColor()`,
das NUR die Vordergrundfarbe ändert — fontUnderline und anchorHref bleiben
bestehen → Folgezeilen erben Unterstrich + Klickbarkeit. Beim 30s-Auto-Trim
bzw. Spalten-Toggle wird `_rerender_all()` (Zeile 407) aufgerufen, das nach
`log_view.clear()` alle Einträge neu zeichnet — dabei verteilt sich das Kleben
neu (erklärt evtl. die scheinbar "oberhalb" betroffenen Zeilen, weil die
sichtbare Reihenfolge nach Re-Render eine andere Bleed-Quelle hat).

UNSICHER (bitte verifizieren): Nimmt QTextEdit.append() bei Plain-Text das
`currentCharFormat` ODER das Format des letzten Zeichens am Dokument-Ende?
Und reicht `setTextColor()` wirklich nicht, um Underline/Anchor zu löschen?

================================================================================
MEIN FIX-PLAN (KISS)
================================================================================
Statt `setTextColor()`+`append()` in (A)/(B) ein VOLLSTÄNDIGES, frisches
QTextCharFormat verwenden, das underline=False und anchorHref="" explizit setzt,
und den Text über cursor.insertBlock()+cursor.insertText(text, fmt) einfügen —
so erbt nichts das Anchor-Format. Zentraler Helper z.B.:

    def _plain_format(self, color: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontUnderline(False)
        fmt.setAnchor(False)
        fmt.setAnchorHref("")
        return fmt

(A) und (B) nutzen diesen Helper + insertText statt setTextColor/append.
(C) `_append_anchor_line` setzt nach dem Anchor das currentCharFormat explizit
zurück (Gürtel+Hosenträger), z.B. self.log_view.setCurrentCharFormat(QTextCharFormat()).

Akzeptanzkriterien:
1. Nach einer Anchor-Zeile hat die nächste TX/RX/Info-Zeile KEIN underline und
   KEIN anchorHref (per QTextCursor/charFormat im Test prüfbar).
2. Klick auf eine "→ Gesendet"-Zeile löst KEIN hunt_insert_clicked aus.
3. Nach _rerender_all() bleibt die Trennung erhalten.
4. Die echte Einschub-Zeile bleibt klickbar (hunt_insert_clicked feuert).
5. Bestehende Farben (TX #FFAA00/#E09600, RX #44BBFF, complete #44FF44,
   timeout #FF4444, info #666) und die zweifarbige ant_label-Darstellung
   unverändert. Auto-Scroll-Verhalten unverändert.

FRAGEN AN DICH:
- Ist die Root-Cause korrekt? Übersehe ich eine zweite Bleed-Quelle?
- Ist `cursor.insertBlock()+insertText(fmt)` der richtige Weg, oder bringt das
  Newline-/Leerzeilen-Probleme gegenüber dem bisherigen append() (das implizit
  einen neuen Paragraph erzeugt)? Bei leerem Dokument vs. nicht-leerem?
- Reicht es, NUR (A)/(B) zu härten, oder MUSS (C) auch zurücksetzen?
- Sind die `_append_colored("─"*30)`-Trennlinien und die OMNI-Leerzeile
  (`_append_colored("", "#000000")`) vom Umbau betroffen?
- KISS-Check: zu viel? Einfacherer Weg, der alle 5 Akzeptanzkriterien erfüllt?
