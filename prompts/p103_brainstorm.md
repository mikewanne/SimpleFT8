# P103 — Brainstorm: Statusbar + RF-Presets-UX

## Mike-Spec 21.05. (nach P102-Push)

### Punkt A — Statusbar zeigt Diversity-Subtyp

Aktuell zeigt Statusbar nur `DIVERSITY` (siehe ui/main_window.py:1295-1299):

```python
mode_labels = {
    "normal": "Normal",
    "diversity": "DIVERSITY",
}
mode_str = mode_labels.get(self._rx_mode, "Normal")
```

Soll: analog zur Antennen-Kachel auch „Standard" / „DX" zeigen.
P97 hat in `ControlPanel` einen `_current_scoring_mode`-Tracker
(„normal" / „dx") der bei `update_diversity_ratio` gesetzt wird.

**Vorschlag KISS:**
```python
mode_str = mode_labels.get(self._rx_mode, "Normal")
if self._rx_mode == "diversity":
    sm = getattr(self.control_panel, '_current_scoring_mode', 'normal')
    mode_str = "DIVERSITY DX" if sm == 'dx' else "DIVERSITY STANDARD"
```

Ist das KISS-OK oder gibt's einen besseren Weg (z.B. Mode-State direkt im
MainWindow halten statt aus ControlPanel auslesen)?

### Punkt B — RF-Presets-UX (alles schon implementiert)

Mike-Screenshot zeigt die Settings-Sektion „RF-Presets pro Band+Watt":
- Tabelle (Band, Watt, RF, Letzte Speicherung)
- Band-Auswahl-Combo + „Band löschen"-Button
- „Alle löschen"-Button mit Confirm-Dialog
- TX-Lock (Buttons disabled während aktivem TX)

Mike fragt: „einfach ne einfache anzeige was vorhanden ist oder nicht …
oder nur die möglichkeit das jeweilige band oder alle zurückzusetzen
(neue kabel neue antenne)".

→ **Genau das ist bereits implementiert.** Mike's Screenshot zeigt
leere Tabelle weil sein FlexRadio noch keine Presets gespeichert hat
(Auto-TUNE bei Bandwechsel ist ausgeschaltet).

**Frage an R1:**

1. Ist das UI gut so wie es ist, oder fehlt was Wichtiges für den
   „neue Kabel/Antenne"-Use-Case?
2. Sollte ich Mike darauf hinweisen dass er für „Presets-Sammlung"
   die „Auto-TUNE bei Bandwechsel"-Checkbox aktivieren muss?
3. Wenn die Tabelle leer ist: aktuelle UX zeigt nichts. Sollte ein
   Hinweis-Text drinstehen wie „Noch keine Presets gespeichert —
   aktiviere Auto-TUNE bei Bandwechsel oder nutze manuellen TUNE"?

## Prioritäten

- Punkt A: schneller Fix (~5 Zeilen + 1 Test). Sofort umsetzen.
- Punkt B: vor allem User-Education-Frage. Vielleicht reicht ein
  Hint-Label unter der Tabelle. Bitte R1 bewerten.

## Antwort bitte knapp — Mike muss gleich weg.
