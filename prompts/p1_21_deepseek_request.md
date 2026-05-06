# SimpleFT8 P1.19 Sterne-Anzeige — UX-Konsultation an DeepSeek

**Kontext:** SimpleFT8 ist ein Hobby-FT8-Funker-Tool (PySide6/Qt). User Mike
(50+, erfahrener Funker, kein UI-Designer aber mit klarem Geschmack) hat die
gerade implementierte Sterne-Anzeige als „scheisse umgesetzt" bewertet:

> „die sterne sind scheiss umgesetzt keiner weiss was sie bedeuten wenigstens
> Lokale Empafngsqualität (hört sich scheisse an) mach vorschag, farbe
> scheisse abstände der sterne zu weit auseinander passt nicht zu decode und
> radio darüber optisch."

**Was der User sieht (Screenshot beschrieben):**
- STATUS-Block (Header in Gold #CC9944)
- `RADIO: Verbunden` (Gold #FFD700 fett, 11px)
- `Decode: 48 Stationen` (Grau #CCCCCC normal, 11px)
- DARUNTER: 5 blaue Cyan-Sterne ★★★★★ (Neon-Cyan #00DDFF, 14px) ohne Label
- `UTC: 02:28:05` rechts daneben
- `Status: IDLE  |  DT: +1.00s (n=9)` darunter

**Probleme die Mike sieht:**
1. **Kein Label** — niemand weiß was die Sterne bedeuten („Lokale
   Empfangsqualität" hört sich für ihn auch scheisse an, will Vorschlag)
2. **Farbe** — Cyan #00DDFF passt nicht zum Gold/Grau-Status-Block darüber
3. **Abstände der Sterne zu weit** trotz `padding: 0 1px` und `setSpacing(0)`
4. **Optik passt nicht** zu RADIO + Decode-Stil darüber (anderes
   Schriftgewicht, andere Farbe, anderes Format)

**Aktueller Code:**

```python
# ui/widgets/stars_widget.py
class StarsConditionWidget(QWidget):
    _STAR_ACTIVE_STYLE = (
        "color: #00DDFF; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )
    _STAR_INACTIVE_STYLE = (
        "color: #555; font-size: 14px; "
        "font-family: Menlo; padding: 0 1px;"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stars: list[QLabel] = []
        for _ in range(5):
            lbl = QLabel("★")
            lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
            self._stars.append(lbl)
            layout.addWidget(lbl)
        layout.addStretch()
        self.set_score(1, "0 Stationen")

    def set_score(self, score: int, tooltip: str = "") -> None:
        score = max(1, min(5, int(score)))
        for i, lbl in enumerate(self._stars):
            if i < score:
                lbl.setStyleSheet(self._STAR_ACTIVE_STYLE)
            else:
                lbl.setStyleSheet(self._STAR_INACTIVE_STYLE)
        self.setToolTip(tooltip)
```

**Style-Konvention um die Sterne herum (control_panel.py:850-878):**

```python
# STATUS Header
lbl_status = QLabel("STATUS")
lbl_status.setStyleSheet(
    f"color: #CC9944; font-size: 10px; font-family: {_FONT}; font-weight: bold;"
)

# RADIO-Label (gold fett)
self.connection_label = QLabel("RADIO: Suche...")
self.connection_label.setStyleSheet(
    f"color: #FFD700; font-family: {_FONT}; font-size: 11px; font-weight: bold;"
)

# Decode-Label (grau normal)
self.decode_label = QLabel("Decode: —")
self.decode_label.setStyleSheet(
    f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;"
)
# _TEXT = "#CCCCCC"

# Sterne + UTC in einer Zeile (das Problem)
snr_utc_row = QHBoxLayout()
snr_utc_row.setSpacing(8)
self.conditions_widget = StarsConditionWidget()
self.utc_label = QLabel("UTC: --:--:--")
self.utc_label.setStyleSheet(
    f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px;"
)
snr_utc_row.addWidget(self.conditions_widget)
snr_utc_row.addStretch()
snr_utc_row.addWidget(self.utc_label)
```

## Meine 4 konkreten Fragen an dich (DeepSeek):

### Q1: Label-Vorschlag (1 Wort + Doppelpunkt)
Mike findet „Lokale Empfangsqualität" zu lang/scheisse. Er will im Stil von
`RADIO:` und `Decode:` ein Wort + Doppelpunkt + Sterne. Meine Kandidaten:

- `Empfang:` (super klar, Funker-Sprache, 7 Zeichen wie „Decode:")
- `Pegel:` (technisch, aber missverständlich = SNR)
- `Signal:` (technisch, aber missverständlich)
- `Aktivität:` (zeigt „wie viel los ist")
- `Conditions:` (englisch, Funker-Slang)
- `Bandqualität:` (deutsch, präzise)

**Welche Wahl ist objektiv am besten? Begründung.**

### Q2: Farbgebung
Aktuelle Cyan #00DDFF passt nicht zum Status-Block (Gold #FFD700, Grau #CCCCCC).
Theme-Konstanten verfügbar: Gold #FFD700, Cyan #00DDFF, Rot #FF4444, Grau #CCCCCC.

Optionen:
- **A) Aktive Sterne in Gold** #FFD700 (passt zu RADIO-Label) — Sterne stehen
  visuell in einer Linie mit RADIO
- **B) Score-abhängig**: 5/4 Sterne in Grün #44FF88, 3 Sterne in Gelb/Gold
  #FFD700, 2/1 Sterne in Rot #FF4444 — semantische Farbe
- **C) Neon-Cyan beibehalten** aber kleiner (12px statt 14px)

**Welche Option ist UX-mäßig am besten und warum?**

### Q3: Stern-Abstände
Trotz `setSpacing(0)` + `padding: 0 1px` sehen Sterne weit auseinander aus.
Theorie: QLabel-Default-`contentsMargins` oder Schrift-Bearing für `★` (U+2605)
addiert ungewollte Breite.

**Wie kriegt man Sterne wirklich eng zusammen?**
- `lbl.setContentsMargins(0,0,0,0)` auf jedes Label?
- Statt 5 QLabels EINE QLabel mit `★★★★★` als Text und Color über RichText/HTML?
- HTML mit `<span style="color:#FFD700">★★★</span><span style="color:#444">★★</span>`
  in einer einzigen QLabel?

### Q4: Optik-Konsistenz mit RADIO/Decode darüber
Aktuell HBoxLayout mit Sterne links + UTC rechts. Aber Sterne sind 14px ohne
Label, RADIO/Decode sind 11px mit Label. Inkonsistent.

**Soll die Sterne-Zeile genauso wie RADIO/Decode strukturiert sein?**
- Format: `Empfang:  ★★★☆☆` (Label gleicher Stil wie Decode-Label, Sterne
  als zweiter Span, UTC bleibt rechts) → eine konsistente Status-Zeile?
- Oder Sterne als eigene Zeile UNTER UTC, klar abgesetzt?

### Q5: Score-Algorithmus ist auch falsch! (KRITISCH)

Mike-Befund Live-Test: er sieht **5 Sterne aktiv** obwohl die SNR-Werte
durchweg schlecht sind (Stationen bei -20 bis -25 dB). Stationen-Anzahl ist
hoch (~48), aber Empfangsqualität ist tatsächlich mies.

**Aktueller Algorithmus** in `ui/mw_cycle.py`:

```python
def compute_local_conditions(stations: dict) -> tuple[int, int, float]:
    if not stations:
        return 1, 0, -99.0
    snrs = sorted([float(s.snr) for s in stations.values()
                   if hasattr(s, 'snr') and s.snr is not None],
                  reverse=True)
    n = len(snrs)
    if n == 0:
        return 1, 0, -99.0
    top_half = snrs[:max(1, n // 2)]
    median = top_half[len(top_half) // 2] if top_half else -99.0
    if n >= 25 or median > -12:    # ← OR ist falsch!
        return 5, n, median
    if n >= 15 or median > -15:    # 48 Stationen × -25 dB → 5 Sterne falsch
        return 4, n, median
    ...
```

**Das `or` ist der Bug:** 48 Stationen alle bei -25 dB triggern `n >= 25` →
5 Sterne, obwohl die Qualität schlecht ist. Mike: „Anzahl passt nicht zu
den schlechten dB-Werten."

**Mögliche Fixes:**
- **A) `and` statt `or`:** beide Bedingungen müssen erfüllt sein. Risiko:
  zu streng — bei Top-Conditions mit nur 12 Stationen mit Median -10 nur
  3 Sterne (sollte 5).
- **B) Score = Mittelwert aus zwei Sub-Scores:** `score_n` (1-5 nach
  Stationsanzahl) und `score_snr` (1-5 nach Median-SNR), Final =
  `min(score_n, score_snr)` oder `round((score_n + score_snr) / 2)`.
- **C) Nur SNR zählt:** Stationsanzahl ist nur Indikator dass überhaupt
  decoded wird; die Qualität misst der Median-SNR. Wenn Stationen → 0,
  dann 1 Stern. Sonst nur SNR-basiert.
- **D) Gewichtetes Score**: `score = round(0.6 * snr_score + 0.4 * n_score)`.

Was empfiehlst du? Was ist intuitiv für Funker (Mike: 30 Jahre Erfahrung)?
Sind die SNR-Schwellen `-12 / -15 / -18 / -22` realistisch für FT8?

**Antworte mit konkreten Empfehlungen + Begründung. Keine generischen Tipps.
KISS bevorzugt — wenn EINE QLabel mit RichText reicht, lieber so.**

**Sprache: Deutsch.**
