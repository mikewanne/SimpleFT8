# Bundle K V2 — Self-Review

## F1 — Existierende SWR-Werte 6.0/7.0/8.0 in User-Settings würden geclamped

ORANGE. Mike hat in der Vergangenheit (vor heute) evtl. einen Wert wie
6.0 oder 7.0 gespeichert. Mit neuer Range 1.5-5.0 würde der Load-Snap
auf 5.0 reduzieren → striktere Sperre als gewünscht.

**Risiko:** Mike merkt das nicht, TX bricht früher ab als erwartet.

**V3-Mitigation:** `print()`-Statement beim Load-Snap mit alter→neuer
Wert. Sichtbar im Terminal, Mike sieht Änderung. Plus: in HISTORY.md
Hinweis.

Eigentliche Frage: Soll ich die Obergrenze 5.0 nehmen oder 10.0 lassen?

**Re-Bewertung:** V1 sagte 5.0. Argument: Hobby-Praxis. Aber: Mike's
empfohlener Range war „1, 1.5, 2, 2.5, 3, 3.5" — ALSO maximal 3.5 in
seiner Vorstellung! Über 3.5 ist faktisch „Limit aus".

**V3-Entscheidung:** Range bleibt **1.5 bis 5.0** (etwas Headroom über
Mike's Aufzählung damit User mit speziellem Setup nicht eingesperrt
ist). 5.0 reicht. 10.0 ist sowieso unsinnig.

**Plus V3:** Snap auf nächst-NIEDRIGEREN Wert (also 6.0 → 5.0 NICHT
5.5 weil 5.5 nicht in Liste). Mike's gespeicherter Wert 1.7 → 1.5 (nicht
2.0). Begründung: User-Erwartung „mein gespeicherter Wert war eher
locker als strikt" — also locker bleiben.

ABER: aus V1-Q2 stand schärferer Snap empfohlen für Sicherheit. Konflikt.

**Re-Re-Bewertung:** Schärfere Variante (1.7 → 2.0) ist sicherer, weil
TX früher abbricht bei Spike. Locker (1.7 → 1.5) bricht spät ab. Für
Hardware-Sicherheit ist schärfer besser.

**V3-Final:** Snap auf nächst-HÖHEREN Wert in der Liste (sicherer, V1-
Position bestätigt). Ausnahme: wenn alter Wert >5.0, clamp auf 5.0
(Maximum). Wenn <1.5, clamp auf 1.5 (Minimum).

## F2 — P59 ändert auch `btn_auto_hunt`-Active-State

ORANGE. V1 schreibt explizit „btn_auto_hunt aktiv = grün ✓ (Konsistenz
innerhalb „funkt aktiv"-Buttons)". Aber Mike hat im O-Ton nur „CQ button
... grün wie diversity modus" gesagt. Er meinte vielleicht NUR btn_cq.

**Re-Bewertung:** Mike's Wortlaut „einheidlich optisch nachvollziehbar"
ist klares Konsistenz-Signal. Wenn btn_omni_cq grün ist und btn_cq grün
wird, aber btn_auto_hunt rot/gelb bleibt → INKONSISTENT. Mike würde das
sofort sehen und in nächster Field-Test-Session monieren.

**V3-Entscheidung:** Alle 3 Buttons grün (`_mode_btn_style` ändern reicht).
Wenn Mike das nicht will → trivialer Rückbau. KISS-Risk-Reward sagt
„konsistent machen".

## F3 — Test T5 zu strikt — Hexcode-Match könnte falsche Positives haben

GELB. T5 prüft NICHT `#FFD700` mehr in `_mode_btn_style`. Aber wenn
andere Buttons (z.B. TUNE-Button, Diversity-Buttons) in derselben Datei
diesen Hexcode nutzen, ist der Test irreführend.

**Mitigation:** Test prüft Substring direkt in `_mode_btn_style`-String
(nicht in der ganzen Datei). Hierfür muss der Style-String entweder als
Konstante extrahiert sein ODER per Regex aus dem Code-Body gegrep-t.

**V3-Entscheidung:** Style-String als Modul-Konstante `_MODE_BTN_STYLE`
extrahieren → testbar via `from ui.control_panel import _MODE_BTN_STYLE`.
Bonus: Active-Style ist dann zentral, leichter wartbar.

Aber: Style ist heute innerhalb `__init__`-Body — verschieben würde
größeres Refactor. Trade-off.

**V3-Final:** Test prüft per `inspect.getsource(ControlPanel.__init__)`
auf den lokalen `_mode_btn_style`-Block. Keine Modul-Konstante nötig.
Pragmatisch.

## F4 — `_omni_btn_style` Active-Block ist redundant

GELB. Wenn `_mode_btn_style` Active = grün identisch mit
`_omni_btn_style` Active = grün → identische Code-Duplikation. Aufräumen?

**V3-Entscheidung:** KISS — beide Styles bleiben separat (sie haben
DIFFERENZIERTE Inaktiv-Farben: btn_cq dunkelrot-gelblich, btn_omni
dunkelrot-rötlich). Active gleich, Inaktiv unterschiedlich = beide
separat sinnvoll. Test T6 schützt davor dass omni_btn_style nicht
versehentlich mit umgebaut wird.

## F5 — `swr_limit.value()` vs `swr_limit.currentData()` Migration

ORANGE. Alle bestehenden Aufrufer von `swr_limit.value()`:

```bash
grep "swr_limit\." ui/settings_dialog.py
```

Ergebnis aus V1-Verifikation:
- Z.537 `self.swr_limit.setValue(...)` → wird `setCurrentIndex` mit
  Snap-Index
- Z.679 `self.swr_limit.value()` → wird `currentData()`
- Z.723 `self.swr_limit.setValue(3.0)` → wird `setCurrentIndex(3)`

**Helper-Funktion** `_swr_value_to_index(v)` für Snap-Logik:
```python
def _swr_value_to_index(value: float) -> int:
    """Snap auf nächst-höheren Wert in _SWR_VALUES."""
    for i, v in enumerate(_SWR_VALUES):
        if value <= v:
            return i
    return len(_SWR_VALUES) - 1  # Wert > max → Maximum
```

**V3-Code-Position:** Helper als Modul-Funktion in `settings_dialog.py`
oben. Testbar.

## F6 — Test T3 Snap-Verhalten

GELB. T3 prüft Snap 1.7 → 2.0. Aber V2-F1 hat das auf „nächst-höher"
fixiert. Test korrekt.

Zusätzlich: T3.1 — Snap 0.5 → 1.5 (Minimum). T3.2 — Snap 7.5 → 5.0
(Maximum).

**V3:** T3 in drei Sub-Tests aufgeteilt — Snap mitte/unter-Min/über-Max.

## F7 — APP_VERSION-Step

GELB. P61 war 0.97.32 → 0.97.33. Bundle K wäre 0.97.33 → 0.97.34. OK.

## F8 — Hardware-Pflicht ANT1

✓ Keine Berührung. Bundle K ändert nur UI (Settings-Dialog + Button-
Style). Keine TX-Logik.

## V2 → V3 Änderungen

| V1 | V3 |
|---|---|
| `setRange(1.5, 10.0)` Range | `setRange` 1.5-5.0 (8 Werte) |
| ComboBox-Snap unklar | Snap auf nächst-HÖHER, mit Helper-Funktion |
| 6 Tests | 8 Tests (T3 in 3 Sub-Tests) |
| Style-Test via Substring | Style-Test via `inspect.getsource(__init__)` |
| `auto_hunt`-Active grün impliziert | Explizit dokumentiert als gewünschte Konsistenz |

## V2-Verifikation Code-Stellen

- `ui/settings_dialog.py:206-213` — SWR-Widget aktuell
- `ui/settings_dialog.py:537,679,723` — Aufrufer von swr_limit.value()
- `ui/control_panel.py:986-1018` — _mode_btn_style + _omni_btn_style
- `radio/flexradio.py` set_swr_limit Clamp `[1.5, 10.0]`
  → bleibt unverändert (Subset)

Alles verifiziert. R1-Phase kann starten.
