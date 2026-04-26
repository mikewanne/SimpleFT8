# Auswertung — Anleitung für Tages-/Pooled-Mean-Vergleiche

**Wann lesen:** SOFORT bei jeder Mike-Anfrage Richtung „werte mal aus", „Tagesauswertung",
„20m heute", „Pooled Mean", „mit/ohne Rescue", „Normal vs Diversity".

**⚠ DEFAULT-FRAGE bei „Stundenschnitt am Tag":** siehe Sektion 12 (Stationen pro Stunde).
Das ist Mike's Standard-Format. Liefer EINE Tabelle, KEINE Diskussion.

**Warum diese Datei existiert:** Claude stolpert jedes Mal über drei Fakten:
(1) Tabellenformat pro Modus unterschiedlich, (2) Rescue liegt extern, (3) DX-Modus
ist NICHT direkt mit Normal vergleichbar. Hier steht die Kurzfassung.

---

## 1. Datenstruktur (was liegt wo?)

```
statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md     ← 1 Datei = 1 UTC-Stunde
                                  /stations/YYYY-MM-DD_HH.md  ← Pro-Station-Vergleiche (für Rescue)
```

**Modi-Verzeichnisse:**
- `Normal` — keine Diversity, alle Stationen
- `Diversity_Normal` — Diversity Standard (mit Antennen-Vergleich)
- `Diversity_Dx` — Diversity DX-Modus (zählt **nur** Stationen mit SNR < −10 dB)

**Filter-Realität:** seit v0.63 werden **nur 20m + 40m FT8** protokolliert. Andere Bänder
werden empfangen aber nicht in `statistics/` gespeichert.

---

## 2. Tabellen-Format pro Modus (HÄUFIGER STOLPERSTEIN!)

**`Normal`-Datei (3 Spalten):**
```markdown
| Zeit | Stationen | Ø SNR |
|------|-----------|-------|
| 07:32:13 | 41 | -18 |
```

**`Diversity_Normal` und `Diversity_Dx` (5 Spalten):**
```markdown
| Zeit | Stationen | Ø SNR | Ant2 Wins | Ø ΔSNR |
|------|-----------|-------|-----------|--------|
| 07:00:13 | 49 | -17 | 14 | -1.3 |
```

**→ Robustes Regex matcht NUR die ersten 2 Spalten** (Zeit + Stationen-Anzahl):
```python
ROW_RE = re.compile(r"^\|\s*(\d{2}:\d{2}:\d{2})\s*\|\s*(\d+)\s*\|")
```

**`stations/*.md` (5 Spalten, für Rescue-Berechnung):**
```markdown
| Zeit | Call | ANT1 dB | ANT2 dB | Δ dB |
|------|------|---------|---------|------|
| 07:08:13 | VK2VT | -25 | -22 | +3.0 |
```

**Rescue-Definition:** `ANT1 ≤ -24 dB UND ANT2 > -24 dB` → Station wäre ohne ANT2
nicht dekodiert worden.

---

## 3. Pooled-Mean-Methodik (wie der Wert berechnet wird)

```
Ø Sta./Zyklus = Σ(stationen über alle Zyklen) / Σ(Zyklen)
```

- KEIN Stunden-Filter, KEINE Tagesgewichtung — jeder Zyklus zählt gleich
- „Mit Rescue": `Σ(stationen + rescue_events) / Σ(zyklen)` — Rescue-Events
  separat aus `stations/*.md` zählen, dann auf Stundenfile-Sum addieren

---

## 4. STOLPERSTEIN: Fair-Vergleich erforderlich

Mike misst die 3 Modi nicht parallel sondern wechselt durch sie über den Tag.
Ein roher Vergleich aller Zyklen aller Modi vermischt Tageszeiten —
20m nachts ≈ 10 Stationen/Zyklus, mittags ≈ 50.

**Pflicht-Schritt vor jeder Tagesauswertung:**
1. Pro Modus die UTC-Stunden auflisten die vorhanden sind
2. Schnittmenge bilden = „faire Stunden" (alle 3 Modi gemessen)
3. Pooled Mean NUR über diese Stunden berechnen

Wenn die Schnittmenge zu klein ist (< 3 Stunden): Mike informieren,
nicht trotzdem auswerten und „nettes" Ergebnis melden.

---

## 5. STOLPERSTEIN: Diversity_Dx ≠ Normal/Standard vergleichbar

**Diversity_Dx-Modus zählt per Definition NUR Stationen mit SNR < −10 dB**
(`core/diversity.py`, scoring_mode="dx"). Die starken Lokalstationen werden
absichtlich rausgefiltert.

→ DX hat IMMER weniger Stationen/Zyklus als Normal/Standard, das ist KEIN
„Diversity-Verlust", sondern die DX-Modus-Definition. Bei Vergleich „Normal=100%"
ist DX strukturell unter 100% — auch wenn Diversity einwandfrei läuft.

**Bei Mike's Anfrage „Normal=100%" trotzdem so darstellen, aber im Fazit
explizit erklären:** „DX-Modus zählt nur SNR<-10, nicht direkt mit Normal
vergleichbar."

---

## 6. Code-Vorlage (kopieren + Datum/Band/Stunden anpassen)

```python
"""Pooled-Mean Tagesauswertung (DATE), fair vergleichbar (Stunden-Schnittmenge).
   Normal vs Diversity_Normal vs Diversity_Dx, mit + ohne Rescue, Normal=100%."""
import re
from pathlib import Path

DATE = "YYYY-MM-DD"
BAND = "20m"  # oder "40m"

ROW_RE = re.compile(r"^\|\s*(\d{2}:\d{2}:\d{2})\s*\|\s*(\d+)\s*\|")
STATION_RE = re.compile(
    r"^\|\s*\d{2}:\d{2}:\d{2}\s*\|\s*\S+\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|"
)

def hours_with_data(mode_dir):
    base = Path(f"statistics/{mode_dir}/{BAND}/FT8")
    return {int(f.stem.split("_")[1]) for f in base.glob(f"{DATE}_*.md")}

# Schritt 1: faire Stunden = Schnittmenge
fair = (hours_with_data("Normal")
        & hours_with_data("Diversity_Normal")
        & hours_with_data("Diversity_Dx"))

def collect(mode_dir, hours):
    base = Path(f"statistics/{mode_dir}/{BAND}/FT8")
    n_cyc, sum_st = 0, 0
    for f in sorted(base.glob(f"{DATE}_*.md")):
        if int(f.stem.split("_")[1]) not in hours:
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ROW_RE.match(line)
            if m and not line.startswith("|------"):
                n_cyc += 1
                sum_st += int(m.group(2))
    # Rescue-Events aus stations/*.md
    n_resc = 0
    sdir = base / "stations"
    if sdir.exists():
        for f in sorted(sdir.glob(f"{DATE}_*.md")):
            if int(f.stem.split("_")[1]) not in hours:
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                m = STATION_RE.match(line)
                if m:
                    a1, a2 = int(m.group(1)), int(m.group(2))
                    if a1 <= -24 and a2 > -24:
                        n_resc += 1
    return n_cyc, sum_st, n_resc

results = {}
for label in ("Normal", "Diversity_Normal", "Diversity_Dx"):
    results[label] = collect(label, fair)

# Output
print(f"=== {BAND} FT8 — {DATE}, faire Stunden {sorted(fair)} UTC ===\n")
n_norm, s_norm, _ = results["Normal"]
base_avg = s_norm / n_norm if n_norm else 1
for label in ("Normal", "Diversity_Normal", "Diversity_Dx"):
    n, s, r = results[label]
    avg, avg_r = (s/n, (s+r)/n) if n else (0, 0)
    pct, pct_r = avg/base_avg*100, avg_r/base_avg*100
    print(f"{label:18} | Ø {avg:5.2f} → {pct:6.1f}% (Δ {pct-100:+5.1f}%) | "
          f"+Rescue {pct_r:6.1f}% (Δ {pct_r-100:+5.1f}%)")
```

---

## 7. Antwort-Format an Mike

1. **Tabelle:** Modus | Ø Sta./Zyklus | ohne Rescue (Normal=100%) | mit Rescue
2. **Datenbasis:** Anzahl Zyklen, Anzahl Rescue-Events, faire Stunden
3. **Caveats EXPLIZIT:** DX-Modus-Filter, dünne Datenbasis, ANT1-Resonanz auf 20m
4. **Trend-Aussage:** Was sagt das im Tagesverlauf? (Mike will den Trend sehen)

---

## 8. Bekannte Daten-Eigenheiten 20m vs 40m

- **40m FT8 Pooled Mean global:** Diversity Standard +88%, DX +124%
  (Stand 25.04.2026, 22.696 Zyklen über 4 Tage)
- **20m FT8:** ANT1 (Kelemen DP-201510) ist **resonant** auf 20m → Diversity-Vorteil
  kleiner als auf 40m. Erwartung: +5–30 % Standard, Rescue gering.
- **20m DX-Modus:** glänzt am Tag→Nacht-Übergang (Skip-Zonen-Rand, ~18 UTC),
  +59% beobachtet bei dünner Datenbasis.

Wenn Mike sich über „nur +2 %" auf 20m wundert: das ist physikalisch konsistent.

---

## 9. Wenn Mike sagt „alles aufaddieren / Anteil am Tag"

Mike will dann **KEIN Stunden-Filter, KEINEN Pooled-Mean-Vergleich** —
sondern die rohen Total-Summen der Stationen pro Modus und das prozentuale
Verhältnis zueinander auf den ganzen Tag bezogen.

```python
# Pro Modus alle Zyklen UND alle Stationen aufaddieren (ohne Stunden-Filter)
n_cyc, sum_st = 0, 0
for f in sorted(base.glob(f"{DATE}_*.md")):
    for line in f.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if m and not line.startswith("|------"):
            n_cyc += 1
            sum_st += int(m.group(2))

# Anteil am Tagestotal (Normal + Div_Norm + Div_Dx = 100%)
total = sum_st_normal + sum_st_div_norm + sum_st_div_dx
anteil_normal = sum_st_normal / total * 100
```

**Antwort-Format:**

| Modus | Zyklen | Σ Stationen | Anteil am Tag |
|---|---|---|---|
| Normal | … | … | X % |
| Diversity Standard | … | … | Y % |
| Diversity DX | … | … | Z % |
| GESAMT | … | … | 100 % |

**Caveat klar nennen:** Der Anteil hängt davon ab wie LANGE Mike pro Modus
gemessen hat. DX-Modus läuft oft nachts durch (mehr Zyklen-Anteil), Normal
oft nur tagsüber. Anteil am Tag ist KEIN Diversity-Performance-Maß, sondern
zeigt nur die zeitliche Verteilung.

---

## 10. Wenn Mike sagt „Stundenschnitt / mehr-oder-weniger pro Stunde" — DEFAULT-VARIANTE!

**Das ist Mike's bevorzugte Variante** für den Tagestrend. Pro Stunde:
- Normal = 100 % (Baseline)
- Diversity Standard / DX als +/− % davon
- Mit + ohne Rescue als getrennte Spalten

Nur Stunden zeigen wo Normal gemessen hat (sonst fehlt die Baseline).

**Code-Vorlage:**

```python
import re
from pathlib import Path
from collections import defaultdict

DATE = "YYYY-MM-DD"; BAND = "20m"
ROW_RE = re.compile(r"^\|\s*(\d{2}):(\d{2}):(\d{2})\s*\|\s*(\d+)\s*\|")
STATION_RE = re.compile(
    r"^\|\s*(\d{2}):(\d{2}):(\d{2})\s*\|\s*\S+\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|"
)

def collect_per_hour(mode_dir):
    base = Path(f"statistics/{mode_dir}/{BAND}/FT8")
    per_h = defaultdict(lambda: [0, 0, 0])  # [n_cycles, sum_st, n_resc]
    for f in sorted(base.glob(f"{DATE}_*.md")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ROW_RE.match(line)
            if m and not line.startswith("|------"):
                per_h[int(m.group(1))][0] += 1
                per_h[int(m.group(1))][1] += int(m.group(4))
    sdir = base / "stations"
    if sdir.exists():
        for f in sorted(sdir.glob(f"{DATE}_*.md")):
            for line in f.read_text(encoding="utf-8").splitlines():
                m = STATION_RE.match(line)
                if m:
                    a1, a2 = int(m.group(4)), int(m.group(5))
                    if a1 <= -24 and a2 > -24:
                        per_h[int(m.group(1))][2] += 1
    return per_h

normal = collect_per_hour("Normal")
divN   = collect_per_hour("Diversity_Normal")
divDx  = collect_per_hour("Diversity_Dx")

# Pro Stunde: Normal=100%, Diversity in % davon (mit + ohne Rescue)
for h in sorted(normal.keys()):
    n_n, s_n, _ = normal[h]
    if n_n == 0:
        continue
    norm_avg = s_n / n_n
    # Div Standard
    if h in divN and divN[h][0] > 0:
        n, s, r = divN[h]
        avg, avg_r = s/n, (s+r)/n
        d_pct = avg/norm_avg*100 - 100
        d_pct_r = avg_r/norm_avg*100 - 100
    # ... analog fuer Div Dx, dann Tabelle ausgeben
```

**Antwort-Format:**

```
| Stunde | Normal Ø | DivStd Ø | DivStd % | +Rescue | DivDx Ø | DivDx % | +Rescue |
|--------|----------|----------|----------|---------|---------|---------|---------|
|  05    |  36.86   |  41.00   |  +11.2%  | +11.2%  |  36.20  |  -1.8%  |  -1.6%  |
| Schnitt|          |          |  +9.9%   | +10.0%  |         |  -1.1%  |  -1.0%  |
```

Schnitt-Zeile am Ende: arithmetisches Mittel der %-Werte über alle Stunden mit Daten.

**Trend-Aussage in der Antwort:**
- Welche Stunde war der Diversity-Peak?
- Welche Stunde war negativ (Diversity unter Normal)?
- Bringt Rescue heute was oder ist Δ zwischen mit/ohne Rescue klein?

---

## 11. Wenn Mike sagt „Tagestrend" (allgemein, ohne Spezifikation)

Defaultet zu Sektion 10 (Stundenschnitt mit Normal=100%). Nur wenn Mike
explizit „Pooled Mean" oder „Anteil am Tag" sagt → Sektion 8 / 9.

---

## 12. ⭐ DEFAULT-VARIANTE: „Stundenschnitt am Tag" / „Stationen pro Stunde"

**Mike's Standard-Frage. Wenn unsicher: DIESE Variante liefern.**

Pro Modus: alle Stationen-Counts aller Cycles aller Mess-Stunden aufaddieren,
durch Anzahl der Mess-Stunden teilen → "Stationen pro durchschnittliche Mess-Stunde".

Verhältnis: Normal = 100 %.

**Code-Vorlage (kompakt):**

```python
import re
from pathlib import Path

DATE = "YYYY-MM-DD"; BAND = "20m"
ROW_RE = re.compile(r"^\|\s*(\d{2}):(\d{2}):(\d{2})\s*\|\s*(\d+)\s*\|")
STATION_RE = re.compile(
    r"^\|\s*(\d{2}):(\d{2}):(\d{2})\s*\|\s*\S+\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|"
)

def collect(mode_dir):
    base = Path(f"statistics/{mode_dir}/{BAND}/FT8")
    sum_st, hours = 0, set()
    for f in sorted(base.glob(f"{DATE}_*.md")):
        h = int(f.stem.split("_")[1])
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ROW_RE.match(line)
            if m and not line.startswith("|------"):
                sum_st += int(m.group(4))
                hours.add(h)
    n_resc = 0
    sdir = base / "stations"
    if sdir.exists():
        for f in sorted(sdir.glob(f"{DATE}_*.md")):
            for line in f.read_text(encoding="utf-8").splitlines():
                m = STATION_RE.match(line)
                if m:
                    a1, a2 = int(m.group(4)), int(m.group(5))
                    if a1 <= -24 and a2 > -24:
                        n_resc += 1
    return sum_st, len(hours), n_resc

# Σ pro Modus / Mess-Stunden = Sta./Stunde-Schnitt
# Normal=100%, Diversity in % davon
```

**Antwort-Format (NUR diese 2 Tabellen, KEINE Diskussion):**

```
| Modus              | Σ Stationen | Mess-Std. | Sta./Stunde | mit Rescue |
| Normal             |    XXXXX    |     X     |    XXXX     |    XXXX    |
| Diversity Standard |    XXXXX    |     X     |    XXXX     |    XXXX    |
| Diversity DX       |    XXXXX    |     X     |    XXXX     |    XXXX    |

Normal = 100 %:
| Modus              | ohne Rescue | mit Rescue |
| Diversity Standard |    +X.X %   |    +X.X %  |
| Diversity DX       |    +X.X %   |    +X.X %  |
```

**Regeln für die Antwort:**
- KEINE „Caveats" oder „aber bedenke ..."
- KEINE Diskussion über DX-Filter, Tageszeit-Verteilung, Resonanz, etc.
- KEINE Empfehlungen
- Nur Zahlen liefern. Mike zieht die Schlüsse selbst.
