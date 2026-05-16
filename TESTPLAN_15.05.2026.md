# Mike's Testplan — 15.05.2026 nachmittags
**App-Stand:** v0.97.35 · Tests 1306 grün · Push pending

---

## Vorbereitung — App neu starten

```
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8" && ./venv/bin/python3 main.py
```

Versionsnummer unten rechts in Statusbar muss **0.97.35** zeigen.

---

## ⭐ Block A — P62 Bandwechsel-UX-Pause (NEU, NICHT getestet)

**Was wir gefixt haben:** Bei Bandwechsel auf ein neues Band ohne
gespeichertes Gain-Preset gibt's jetzt eine 1-Sekunden-Pause zwischen
TX-Stop und dem Start der Gain-Messung. Damit du den Übergang
„TX aus → neue Messung" klar siehst statt „80W springt direkt auf 10W".

### A1 — Pause bei Bandwechsel auf neues Band

1. **Diversity-Modus** aktivieren (Standard oder DX)
2. **Auto-Hunt starten** oder **OMNI CQ** klicken — irgendwas was TX macht
3. Wenn TX gerade läuft (RF-Meter hoch): **Band wechseln** auf ein Band
   das du heute noch nicht gemessen hast (z.B. 80m wenn Gain fehlt)

**Erwartet:**
- TX bricht sofort ab (RF-Meter fällt auf 0)
- **In Statusbar erscheint 1 Sekunde lang:** „TX gestoppt — Gain-Messung
  startet in 1s ..."
- Nach ~1s startet TUNE mit 10W

**Wenn du den Statusbar-Text siehst → A1 ✓**

### A2 — KEINE Pause bei Band MIT Preset

1. Auto-Hunt starten auf 20m (Gain heute schon gemessen)
2. Während TX läuft: Band wechseln auf **anderes Band das auch schon
   gemessen ist** (z.B. 30m falls gemessen)

**Erwartet:**
- TX bricht ab, kein „Gain-Messung startet"-Text
- Diversity startet sofort (kein TUNE)

**Wenn KEINE Pause → A2 ✓**

### A3 — KEINE Pause beim KALIBRIEREN-Button

1. Settings öffnen
2. **KALIBRIEREN**-Button klicken (im Diversity-Tab)

**Erwartet:**
- TUNE startet sofort, KEINE „TX gestoppt — Gain-Messung startet in 1s ..."

**Wenn direkt ohne Pause → A3 ✓**

### A4 — RF-Meter geht durch 0W (visueller Beweis)

Bei A1 schau auf das **RF-Meter** (FlexRadio-Anzeige). Du solltest sehen:

```
80W (alt) → ... 0W ... → 10W (TUNE)
```

Statt vorher:
```
80W (alt) → DIREKT 10W (TUNE, optisch wie „Dimming")
```

**Wenn 0W-Durchgang sichtbar → A4 ✓**

### A5 — Buttons während Pause gesperrt

Bei A1 versuche während der 1s Pause irgendeinen Button zu klicken
(Band, Modus, CQ, Auto-Hunt).

**Erwartet:** Klicks haben keine Wirkung (UI ist gesperrt durch
`_gain_measure_locked`).

**Wenn nichts klickbar → A5 ✓**

---

## Block B — Push-Vorbereitungs-Check (REGRESSIONS aus heutigen Bundles)

Schnell-Checks dass die heute eingebauten Bugfixes weiterhin halten:

### B1 — P61 Recent-QSO-Cooldown

- Auto-Hunt-QSO mit Station X durchführen
- Direkt danach: Auto-Hunt soll andere Station picken, NICHT X erneut

**Erwartet:** X wird 5 Min lang nicht von Auto-Hunt gewählt.

### B2 — Bundle K CQ-Button-Grün

- Normal-Modus: **CQ RUFEN** klicken → Button = **grün** (nicht rot/gelb)
- Diversity: **OMNI CQ** klicken → Button = grün
- Diversity: **AUTO HUNT** starten → Button = **grün**

### B3 — Bundle K SWR-Combo

- Settings → SWR-Limit → Dropdown mit 1.5/2.0/2.5/3.0/3.5/4.0/4.5/5.0
- Keine freie Tastatur-Eingabe möglich

### B4 — P60 User-Stop-Pfade

- OMNI CQ aktiv, während TX-Slot erneut OMNI klicken → bricht **sofort** ab
- Auto-Hunt aktiv, während TX-Slot erneut Auto-Hunt → bricht sofort ab
- Normal-CQ aktiv, während TX-Slot erneut CQ → bricht sofort ab
- HALT-Button während TX → alle Modi gestoppt

### B5 — P58 SWR-Limit Live-Speicher

- Settings → SWR-Limit auf 1.5 setzen → Speichern
- Terminal-Output: „set_swr_limit:1.5" sichtbar (Live an Radio gesendet)
- KEIN Neustart nötig

---

## Block C — Push-Entscheidung

Wenn **Block A (A1-A5)** alle ✓:

**Sag mir „push" und ich:**
1. Mache atomare Commits für P61 + Bundle K + P62 (~16 Commits insgesamt)
2. Verifiziere `git status` clean
3. Pushe nach `origin/main`
4. Tag-Vorschlag falls gewünscht

Wenn was knackt:
- Sag mir **welcher Punkt** (z.B. „A1 — Statusbar zeigt keinen Text")
- Ich debugge sofort

---

## Bonus — Was noch offen ist (NICHT testen, nur Übersicht)

| # | Was | Status |
|---|---|---|
| P56 | Gain-Messung kollabieren auf pro-Band | TODO mittel (Option A bestätigt von DeepSeek) |
| P52 | Statistik-Toggle raus + 90-Tage-Rolling | TODO klein |
| P54 | Auto-Tune bei Bandwechsel | TODO mittel |

Können wir nach dem Push als nächstes angehen.

---

## Stand-Zusammenfassung

| Heute fertig | Status |
|---|---|
| **P58** SWR-Limit Save-Hook | ✓ getestet |
| **P60** User-Stop-Pfade | ✓ F1-F6 |
| **P61** Auto-Hunt Recent-Cooldown | ✓ Kern bestätigt |
| **Bundle K** (P57 SWR-Combo + P59 CQ-Grün) | ✓ F1+F2+F4+F6, F5 implizit |
| **P62** Bandwechsel-UX-Pause | **← jetzt testen!** |

**Tests:** 1240 (Session-Start) → **1306** (jetzt) = +66 neue Tests heute.

**V4-pro 11-Cycle-Bilanz heute:** 0 Halluzinationen, 100% verifizierbar.
